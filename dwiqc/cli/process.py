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
import shutil
from executors.models import Job, JobArray
from bids import BIDSLayout
sys.path.insert(0, '/n/home_fasse/dasay/dwiqc/dwiqc/tasks')
import prequal
import qsiprep
import prequal_EQ
import qsiprep_EQ
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

    # ⬇️ not sure what to do with these... will come back here.
   
    #logger.debug('DWI raw: %s', raw)
    #logger.debug('T1vnav sourcedata: %s', source)


    # prequal job
    prequal_outdir = None
    if 'prequal' in args.sub_tasks:
        logger.debug('building prequal task')
        chopped_bids = os.path.dirname(args.bids_dir)
        prequal_outdir = os.path.join(chopped_bids, 'dwiqc-prequal', 'OUTPUTS')
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

        # eq_task = prequal_EQ.Task(
        #     sub=args.sub,
        #     ses=args.ses,
        #     run=args.run,
        #     bids=args.bids_dir,
        #     outdir=prequal_outdir,
        #     tempdir=tempfile.gettempdir(),
        #     parent=prequal_task
        # )
        # jarray.add(eq_task.job)

    # qsiprep job
    qsiprep_outdir = None
    if 'qsiprep' in args.sub_tasks:
        chopped_bids = os.path.dirname(args.bids_dir)
        qsiprep_outdir = os.path.join(chopped_bids, 'dwiqc-qsiprep', 'qsiprep_output')
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
        check_for_output(args, qsiprep_outdir)
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
        copy_eddy_files(args,qsiprep_outdir)
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

        eq_task.run()

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

        eq_task.run()   

def copy_eddy_files(args, qsiprep_outdir):
    if 'qsiprep' in args.sub_tasks:
        #tempdir = '/n/holyscratch01/LABS/nrg/Lab/dasay/2251028'
        tempdir=tempfile.gettempdir()
        try:
            shutil.copytree(tempdir, f'{qsiprep_outdir}/qsiprep/eddy_files')
        except:
            print('files have already been copied')
        #os.remove(self._tempdir)

#### this function is primarily for debugging and development purposes
def check_for_output(args, qsiprep_outdir):
    if os.path.isfile(f'{qsiprep_outdir}/qsiprep/sub-{args.sub}.html'):
        print('Qsiprep has already been run on this subject.\nRunning eddy quad.')
        copy_eddy_files(args, qsiprep_outdir)
        # write the qsiprep_EQ.py script
        qsiprep_eddy(args, qsiprep_outdir)




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

