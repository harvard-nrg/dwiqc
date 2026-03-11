import os
import re
import sys
import pdb
import json
import yaml
import yaxil
import logging
import argparse as ap
import subprocess as sp
import collections as col
from xnattagger import Tagger
from bids import BIDSLayout
import xnattagger.config as config


logger = logging.getLogger(__name__)

def do(args):
    if args.insecure:
        logger.warning('disabling ssl certificate verification')
        yaxil.CHECK_CERTIFICATE = False


    # call and run xnattagger on the diffusion data if argument passed

    if args.run_tagger:
        run_xnattagger(args)

    logger.info('downloading data from xnat...')


    # load authentication data and set environment variables for ArcGet.py
    auth = yaxil.auth2(
        args.xnat_alias,
        args.xnat_host,
        args.xnat_user,
        args.xnat_pass
    )
    os.environ['XNAT_HOST'] = auth.url
    os.environ['XNAT_USER'] = auth.username
    os.environ['XNAT_PASS'] = auth.password

    conf = yaml.safe_load(open(args.download_config)) # load yaml config file

    scan_labels = get_scans(conf) ### get a list of the scan types/labels

    # query dwi and T1w scans from XNAT
    scans_to_download = parse_scan_notes(scan_labels, conf, auth, args.label, args.project)

    # iterate over the scans dictionary, search for the scans with the correct note/tag

    for run,scansr in scans_to_download.items():
        for scan_label in scan_labels:
            if scan_label in scansr:
                logger.info('getting run=%s, scan=%s', run, scansr[scan_label])
                download_scan(args, auth, run, scansr[scan_label], scan_label, conf, verbose=args.verbose)

def parse_scan_notes(scan_labels, conf, auth, label, project):
    """
    Iterate through all scans of the given session
    Check for matches in the user provided config file
    If there is more than one T1w image found, do additional
    processing
    """
    anat_tags = {}
    with yaxil.session(auth) as ses:
        scans = col.defaultdict(dict)
        for scan in ses.scans(label=label, project=project):
            note = scan['note']
            for scan_label in scan_labels:
                is_match = match(note, conf['dwiqc'][scan_label]['tag'])
                if is_match:
                    run = is_match.group('run')
                    run = re.sub('[^0-9]', '', run or '1') # get rid of any character that is not a digit between 0-9 and if run is None, make it 1.
                    scans[run][scan_label] = scan['id']
                    if scan_label.lower() == 't1w':
                        anat_tags[scan['ID']] = note
    if count_t1w(scans) > 1:
        winning_t1w = determine_t1w(anat_tags)
        if winning_t1w:
            scans = assign_winning_t1w(scans, winning_t1w)
        else:
            logger.warning('Unable to determine which t1w image to use. See <documentation link> for more details.')
            logger.warning('Continuing pipeline without t1w image. Pipeline quality may be affected or crash altogether.')
    pdb.set_trace()
    logger.info('downloading the following scans:')
    logger.info(json.dumps(scans, indent=2))
    return scans


def assign_winning_t1w(scans, winning_t1w):
    """
    Remove all non-winning t1w entries from scans, delete any run that is
    left with only a 't1w' entry, then insert the winning t1w scan ID into
    every run that contains a 'dwi_main' key.
    """
    # Strip out any t1w entry that isn't the winner
    for run_num in list(scans.keys()):
        if 't1w' in scans[run_num] and scans[run_num]['t1w'] != winning_t1w:
            logger.info(f'Removing non-winning t1w from run {run_num}')
            del scans[run_num]['t1w']

    # Delete any run that only contains a t1w entry
    for run_num in list(scans.keys()):
        if list(scans[run_num].keys()) == ['t1w']:
            logger.info(f'Deleting run {run_num} as it only contains a t1w entry')
            del scans[run_num]
        elif not list(scans[run_num].keys()):
            logger.info(f'Deleting run {run_num} as it is empty')
            del scans[run_num]

    # Pair the winning t1w with every run that has a dwi_main
    for run_num in scans.keys():
        if 'dwi_main' in scans[run_num]:
            logger.info(f'Assigning winning t1w {winning_t1w} to run {run_num}')
            scans[run_num]['t1w'] = winning_t1w

    return scans


def count_t1w(scans):
    '''
    Count the number of t1w images found in session
    '''
    num_t1w = 0
    for _, inner_dict in scans.items():
        if isinstance(inner_dict, dict) and 't1w' in inner_dict:
            num_t1w += 1
    return num_t1w


def determine_t1w(anat_tags):
    '''
    Try to determine which T1w image to use if more
    than one is supplied. It will take the following
    steps serially.
    1. Look for the #t1w_dwiqc tag uniquely exists. If
    so, use that image.
    2. Check if any of the T1w images have been 
    set to "unusable" in XNAT. If a remaining one is usable,
    use that T1w image.
    3. Use Otsu thresholding to run a rough SNR calculation
    on each T1 and use the one with the higher SNR
    '''
    winning_scan = check_t1w_tag(anat_tags)
    if winning_scan:
        return winning_scan



def check_t1w_tag(anat_tags):
    t1_scan_num = [key for key, value in anat_tags.items() if value.lower() == '#t1w_001'][0] # DONT FORGET TO CHANGE BACK TO #t1w_dwiqc !!!!!!!!
    if t1_scan_num:
        logger.info('Found T1w image with #t1w_dwiqc tag, discarding others')    
        return t1_scan_num
    else:
        logger.info('No T1w image note contains #t1w_dwiqc (case insensitive), checking for XNAT usability.')
        return

def run_xnattagger(args):
    """
    This function will run xnattagger with the supplied (or default) config file

    """

    logging.info('Running xnattagger...')

    with open(args.tagger_config) as fo:
        filters = yaml.load(fo, Loader=yaml.SafeLoader)

    tagger = Tagger(args.xnat_alias, filters, 'dwi', args.label)
    tagger.generate_updates()
    tagger.apply_updates()

def get_scans(conf):

    """
    Helper function to dynamically create a list of all the modalities/scans listed in the config file
    
    """
    
    scan_types = [scan_type for scan_type in conf['dwiqc']]

    return scan_types

def download_scan(args, auth, run, scan, config_label, input_config, verbose=False):

    """
    Function that downloads an individual scan based on information from the config input file and command line arguments.
   
    """

    # check for bids sub-directory specification in config file
    try:
        bids_subdir = input_config['dwiqc'][config_label]['bids_subdir'][0]
    except KeyError:
        logger.error('no bids sub-directory specified in config file. see documentation for details:\nhttps://dwiqc.readthedocs.io/en/latest/xnat.html#get-advanced-usage')
        sys.exit(1)

    # check for phase encode direction specification in config file
    try:
        direction = input_config['dwiqc'][config_label]['direction'][0]
    except KeyError:
        logger.warning('no phase encode direction specified. will not be included in BIDS filename')
        direction = None

    # check for acquisition specification in config file
    try:
        acq = input_config['dwiqc'][config_label]['acquisition_group'][0]
    except KeyError:
        logger.warning('no acquisition_group specified. will not be included in BIDS filename')
        acq = None

    ## determine and assign bids_suffix variable

    suffix_mapping = {
        'dwi': 'dwi',
        'fmap': 'epi',
        'anat': 'T1w',
    }   

    bids_suffix = suffix_mapping.get(bids_subdir, None)

    # create config file for ArcGet.py

    config = {
        bids_subdir: {
            bids_suffix: [
                {
                    'run': int(run),
                    'scan': scan,
                }
            ]
        }
    }

    # if phase encode direction and acquisition group are supplied, add them to config file

    if direction:
        config[bids_subdir][bids_suffix][0]['direction'] = direction

    if acq:
        config[bids_subdir][bids_suffix][0]['acquisition'] = acq

    config = yaml.safe_dump(config)

    # create ArcGet.py command to download scan
    cmd = [
        'ArcGet.py',
        '--label', args.label,
        '--output-dir', args.bids_dir,
        '--output-format', 'bids',
    ]
    if args.in_mem:
        cmd.extend([
            '--in-mem'
        ])
    if args.project:
        cmd.extend([
            '--project', args.project
        ])
    if args.insecure:
        cmd.extend([
            '--insecure'
        ])
    cmd.extend([
        '--config', '-'
    ])
    if verbose:
        cmd.append('--debug')
    logger.info(sp.list2cmdline(cmd))
    if not args.dry_run:
        sp.check_output(cmd, input=config.encode('utf-8'))

def match(note, patterns):

    """
    This function uses regular expression matching to match the tags in the scan note field to the config file

    """
    for pattern in patterns:
        m = re.match(pattern, note, flags=re.IGNORECASE)
        if m:
            return m
    return None

