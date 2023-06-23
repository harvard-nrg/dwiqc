import os
import re
import sys
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

tagger_conf = config.default()


#### Need to add support for downloading the T1w data as well. Primarily for qsiprep.

logger = logging.getLogger(__name__)

def do(args):
    if args.insecure:
        logger.warning('disabling ssl certificate verification')
        yaxil.CHECK_CERTIFICATE = False


    # call and run xnattagger on the diffusion data

    with open(tagger_conf) as fo:
        filters = yaml.load(fo, Loader=yaml.SafeLoader)

    tagger = Tagger(args.xnat_alias, filters, 'dwi', args.label)
    tagger.generate_updates()
    tagger.apply_updates()


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

    conf = yaml.safe_load(open(args.config)) # load 

    # query T1w and vNav scans from XNAT
    with yaxil.session(auth) as ses:
        scans = col.defaultdict(dict)
        for scan in ses.scans(label=args.label, project=args.project):
            note = scan['note']
            dwi_match = match(note, conf['dwiqc']['dwi']['tags'])
            pa_match = match(note, conf['dwiqc']['dwi_PA']['tags'])
            ap_match = match(note, conf['dwiqc']['dwi_AP']['tags'])
            anat_match = match(note, conf['dwiqc']['t1w']['tags'])

            if dwi_match:
                run = dwi_match.group('run')
                run = re.sub('[^0-9]', '', run or '1') # get rid of any character that is not a digit between 0-9 and if run is None, make it 1.
                scans[run]['dwi'] = scan['id']
            if pa_match:
                run = pa_match.group('run')
                run = re.sub('[^0-9]', '', run or '1')
                scans[run]['pa'] = scan['id']
            if ap_match:
                run = ap_match.group('run')
                run = re.sub('[^0-9]', '', run or '1')
                scans[run]['ap'] = scan['id']
            if anat_match:
                run = anat_match.group('run')
                run = re.sub('[^0-9]', '', run or '1')
                scans[run]['anat'] = scan['id']


    logger.info(json.dumps(scans, indent=2))


    # iterate over the scans dictionary, search for the scans with the correct note/tag

    for run,scansr in scans.items():
        if 'dwi' in scansr:
            logger.info('getting dwi run=%s, scan=%s', run, scansr['dwi'])
            get_dwi(args, auth, run, scansr['dwi'], verbose=args.verbose)
        if 'pa' in scansr:
            logger.info('getting pa fieldmap run=%s, scan=%s', run, scansr['pa'])
            get_pa(args, auth, run, scansr['pa'], verbose=args.verbose)
        if 'ap' in scansr:
            logger.info('getting ap fieldmap run=%s, scan=%s', run, scansr['ap'])
            get_ap(args, auth, run, scansr['ap'], verbose=args.verbose)
        if 'anat' in scansr:
            logger.info('getting anat run=%s, scan=%s', run, scansr['anat'])
            get_anat(args, auth, run, scansr['anat'], verbose=args.verbose)



def get_dwi(args, auth, run, scan, verbose=False):
    config = {
        'dwi': {
            'dwi': [
                {
                    'run': int(run),
                    'scan': scan
                }
            ]
        }
    }
    config = yaml.safe_dump(config)
    cmd = [
        'ArcGet.py',
        '--label', args.label,
        '--output-dir', args.bids_dir,
        '--output-format', 'bids',
    ]
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


def get_pa(args, auth, run, scan, verbose=False):
    config = {
        'fmap': {
            'epi': [
                {
                    'run': int(run),
                    'scan': scan,
                    'direction': 'PA'
                }
            ]
        }
    }
    config = yaml.safe_dump(config)
    cmd = [
        'ArcGet.py',
        '--label', args.label,
        '--output-dir', args.bids_dir,
        '--output-format', 'bids',
    ]
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


def get_ap(args, auth, run, scan, verbose=False):
    config = {
        'fmap': {
            'epi': [
                {
                    'run': int(run),
                    'scan': scan,
                    'direction': 'AP'
                }
            ]
        }
    }
    config = yaml.safe_dump(config)
    cmd = [
        'ArcGet.py',
        '--label', args.label,
        '--output-dir', args.bids_dir,
        '--output-format', 'bids',
    ]
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

 
def get_anat(args, auth, run, scan, verbose=False):
    config = {
        'anat': {
            'T1w': [
                {
                    'run': int(run),
                    'scan': scan
                }
            ]
        }
    }
    config = yaml.safe_dump(config)
    cmd = [
        'ArcGet.py',
        '--label', args.label,
        '--output-dir', args.bids_dir,
        '--output-format', 'bids',
    ]
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
    for pattern in patterns:
        m = re.match(pattern, note, flags=re.IGNORECASE)
        if m:
            return m
    return None




