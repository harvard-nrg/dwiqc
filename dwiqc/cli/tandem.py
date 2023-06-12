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
import dwiqc.cli.get as get
import dwiqc.cli.process as process
import collections as col
import yaxil.bids


logger = logging.getLogger(__name__)

def do(args):
    if args.insecure:
        logger.warning('disabling ssl certificate verification')
        yaxil.CHECK_CERTIFICATE = False


    # ******* potential idea here-- call and run tagger on the diffusion data ******


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

    # config file under anatqc/config/anatqc.yaml

    # query DWI, T1 and fieldmap scans from XNAT
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

    subject_label = scan['subject_label']


    logger.info(json.dumps(scans, indent=2))

    # iterate over the scans dictionary, search for the scans with the correct note/tag

    for run,scansr in scans.items():
        if 'dwi' in scansr:
            logger.info('getting dwi run=%s, scan=%s', run, scansr['dwi'])
            get.get_dwi(args, auth, run, scansr['dwi'], verbose=args.verbose)
        if 'pa' in scansr:
            logger.info('getting pa fieldmap run=%s, scan=%s', run, scansr['pa'])
            get.get_pa(args, auth, run, scansr['pa'], verbose=args.verbose)
        if 'ap' in scansr:
            logger.info('getting ap fieldmap run=%s, scan=%s', run, scansr['ap'])
            get.get_ap(args, auth, run, scansr['ap'], verbose=args.verbose)
        if 'anat' in scansr:
            logger.info('getting anat run=%s, scan=%s', run, scansr['anat'])
            get.get_anat(args, auth, run, scansr['anat'], verbose=args.verbose)

    # populate the necessary arguments for process, then call process
        args.run = int(run)
        bids_ses_label = yaxil.bids.legal.sub('', args.label)
        bids_sub_label = yaxil.bids.legal.sub('', subject_label)
        args.sub = bids_sub_label
        args.ses = bids_ses_label
        logger.debug('sub=%s, ses=%s', args.sub, args.ses)
        process.do(args)


def match(note, patterns):
    for pattern in patterns:
        m = re.match(pattern, note, flags=re.IGNORECASE)
        if m:
            return m
    return None


