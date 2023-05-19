import os
import re
import sys
import json
import yaml
import yaxil
import glob
import math
import logging
import tarfile
import executors
import tempfile
import subprocess as sp
import shutil
from executors.models import Job, JobArray
from bids import BIDSLayout
from dwiqc.xnat import Report
import dwiqc.tasks.prequal as prequal
import dwiqc.tasks.qsiprep as qsiprep
import dwiqc.tasks.prequal_EQ as prequal_EQ
import dwiqc.tasks.qsiprep_EQ as qsiprep_EQ
from dwiqc.state import State

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

#   *************** INSERT CODE HERE THAT RUNS XNAT_TAGGER ***************


    # load data into pybids as layout

    layout = BIDSLayout(args.bids_dir)

    # grab the dwi and json files using pybids and os

    dwi_file = os.path.basename(layout.get(subject=args.sub, extension='.nii.gz', suffix='dwi', run=args.run, return_type='filename').pop())

    json_file = os.path.basename(layout.get(subject=args.sub, extension='.json', suffix='dwi', run=args.run, return_type='filename').pop())

    basename = os.path.splitext(json_file)[0]

    # ⬇️ not sure what to do with these... will come back here.
   
    #logger.debug('DWI raw: %s', raw)
    #logger.debug('T1vnav sourcedata: %s', source)


    # prequal job
    prequal_outdir = None
    if 'prequal' in args.sub_tasks:
        logger.debug('building prequal task')
        prequal_outdir = os.path.join(args.bids_dir, 'derivatives', 'dwiqc-prequal', f'sub-{args.sub}', f'ses-{args.ses}', basename, 'OUTPUTS')
        prequal_task = prequal.Task(
            sub=args.sub,
            ses=args.ses,
            run=args.run,
            bids=args.bids_dir,
            outdir=prequal_outdir,
            tempdir=tempfile.gettempdir(),
            pipenv='/sw/apps/prequal'
        )
        os.environ['OPENBLAS_NUM_THREADS'] = '1'
        logger.info(json.dumps(prequal_task.command, indent=1))
        jarray.add(prequal_task.job)

    # qsiprep job
    qsiprep_outdir = None
    if 'qsiprep' in args.sub_tasks:
        qsiprep_outdir = os.path.join(args.bids_dir, 'derivatives', 'dwiqc-qsiprep', f'sub-{args.sub}', f'ses-{args.ses}', basename, 'qsiprep_output')
        qsiprep_task = qsiprep.Task(
            sub=args.sub,
            ses=args.ses,
            run=args.run,
            bids=args.bids_dir,
            outdir=qsiprep_outdir,
            tempdir=tempfile.gettempdir(),
            pipenv='/sw/apps/qsiprep'
        )
        os.environ['OPENBLAS_NUM_THREADS'] = '1'
        logger.info(json.dumps(qsiprep_task.command, indent=1))
        #check_for_output(args, qsiprep_outdir)
        jarray.add(qsiprep_task.job)

    # submit jobs and wait for them to finish
    if not args.dry_run:
        logger.info('submitting jobs')
        jarray.submit(limit=args.rate_limit)
        logger.info('waiting for all jobs to finish')
        jarray.wait()
        numjobs = len(jarray.array)
        failed = len(jarray.failed)
        complete = len(jarray.complete)
        prequal_eddy(args, prequal_outdir)
        qsiprep_eddy(args, qsiprep_outdir)
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

    # create artifacts directory

    if not args.artifacts_dir:
        args.artifacts_dir = os.path.join(
            args.bids_dir,
            'xnat-artifacts'
        )



    # build data to upload to xnat
    R = Report(args.bids_dir, args.sub, args.ses, args.run)
    logger.info('building xnat artifacts to %s', args.artifacts_dir)
    R.build_assessment(args.artifacts_dir)



def prequal_eddy(args, prequal_outdir):
    if 'prequal' in args.sub_tasks:
        eq_task = prequal_EQ.Task(
            sub=args.sub,
            ses=args.ses,
            run=args.run,
            bids=args.bids_dir,
            outdir=prequal_outdir,
            tempdir=tempfile.gettempdir(),
        )

        eq_task.build()

def qsiprep_eddy(args, qsiprep_outdir):
    if 'qsiprep' in args.sub_tasks:
        eq_task = qsiprep_EQ.Task(
            sub=args.sub,
            ses=args.ses,
            run=args.run,
            bids=args.bids_dir,
            outdir=qsiprep_outdir,
            tempdir=tempfile.gettempdir(),
        )

        eq_task.build()   



#    # upload data to xnat over rest api
#    if args.xnat_upload:
#        logger.info('Uploading artifacts to XNAT')
#        auth = yaxil.auth2(args.xnat_alias)
#        yaxil.storerest(auth, args.artifacts_dir, 'dwiqc-resource')

