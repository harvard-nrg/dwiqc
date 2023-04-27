import os
import re
import sys
import json
import yaml
import yaxil
import glob
import math
import anatqc
import logging
import tarfile
import executors
import tempfile
import subprocess as sp
from executors.models import Job, JobArray
from bids import BIDSLayout
sys.path.insert(0, '/n/home_fasse/dasay/dwiqc/dwiqc/tasks')
import prequal
#import dwiqc.tasks.mriqc as mriqc
#from anatqc.bids import BIDS
#from anatqc.xnat import Report
#import anatqc.tasks.vnav as vnav
#import anatqc.tasks.morph as morph
#from anatqc.state import State

logger = logging.getLogger(__name__)

def do(args):
    if args.insecure:
        logger.warning('disabling ssl certificate verification')
        yaxil.CHECK_CERTIFICATE = False

    # create job executor and job array
    if args.scheduler:
        E = executors.get(args.scheduler, partition=args.partition)
    else:
        E = executors.probe(args.partition)
    jarray = JobArray(E)


    # load data into pybids as layout

    layout = BIDSLayout(args.bids_dir)


    # create BIDS

    # grab the dwi and T1w files using pybids and os

    dwi_file = os.path.basename(layout.get(subject=args.sub, extension='.nii.gz', suffix='dwi', run=args.run, return_type='file').pop())

    #t1w_file = os.path.basename(layout.get(subject=args.sub, extension='.nii.gz', suffix='T1w', run=args.run, return_type='file').pop())


    # ⬇️ not sure what to do with these... will come back here.
   
    #logger.debug('DWI raw: %s', raw)
    #logger.debug('T1vnav sourcedata: %s', source)


    # prequal job
    prequal_outdir = None
    if 'prequal' in args.sub_tasks:
        chopped_bids = os.path.dirname(args.bids_dir)
        prequal_outdir = os.path.join(chopped_bids, 'dwiqc-prequal', 'OUTPUTS') # path to output dir, change for prequal
        task = prequal.Task(
            sub=args.sub,
            ses=args.ses,
            run=args.run,
            bids=args.bids_dir,
            outdir=prequal_outdir,
            tempdir=tempfile.gettempdir(),
            pipenv='/sw/apps/prequal'
        )
        os.environ['OPENBLAS_NUM_THREADS'] = '1'
        logger.info(json.dumps(task.command, indent=1))
        jarray.add(task.job)

    # qsiprep job
    qsiprep_outdir = None
    if 'qsiprep' in args.sub_tasks:
        chopped_bids = os.path.dirname(args.bids_dir)
        qsiprep_outdir = os.path.join(chopped_bids, 'dwiqc-qsiprep', 'qsiprep_output') # path to output dir, change for prequal
        task = prequal.Task(
            sub=args.sub,
            ses=args.ses,
            run=args.run,
            bids=args.bids_dir,
            outdir=mriqc_outdir,
            tempdir=tempfile.gettempdir(),
            venv='/sw/apps/qsiprep'
        )
        os.environ['OPENBLAS_NUM_THREADS'] = '1'
        logger.info(json.dumps(task.command, indent=1))
        jarray.add(task.job)

    # submit jobs and wait for them to finish
    if not args.dry_run:
        logger.info('submitting jobs')
        jarray.submit(limit=args.rate_limit)
        logger.info('waiting for all jobs to finish')
        jarray.wait()
        numjobs = len(jarray.array)
        failed = len(jarray.failed)
        complete = len(jarray.complete)
        if failed:
            logger.info('%s/%s jobs failed', failed, numjobs)
            for pid,job in iter(jarray.failed.items()):
                logger.error('%s exited with returncode %s', job.name, job.returncode)
                with open(job.output, 'r') as fp:
                    logger.error('standard output\n%s', fp.read())
                with open(job.error, 'r') as fp:
                    logger.error('standard error\n%s', fp.read())
        logger.info('%s/%s jobs completed', complete, numjobs)
        if failed > 0:
            sys.exit(1)


# this section will get updated when we get to the xnat phase

#    # build data to upload to xnat
#    R = Report(args.bids_dir, args.sub, args.ses, args.run)
#    logger.info('building xnat artifacts to %s', args.artifacts_dir)
#    R.build_assessment(args.artifacts_dir)#

#    # upload data to xnat over rest api
#    if args.xnat_upload:
#        logger.info('Uploading artifacts to XNAT')
#        auth = yaxil.auth2(args.xnat_alias)
#        yaxil.storerest(auth, args.artifacts_dir, 'anatqc-resource')
