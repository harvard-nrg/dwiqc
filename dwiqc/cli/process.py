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
import dwiqc.browser as browser


logger = logging.getLogger(__name__)

def do(args):
    if args.insecure:
        logger.warning('disabling ssl certificate verification')
        yaxil.CHECK_CERTIFICATE = False

    if args.exclude_nodes:
        excluded_nodes = list(args.exclude_nodes)
    else:
        excluded_nodes = ['']

    # create job executor and job array
    if args.scheduler:
        E = executors.get(args.scheduler, partition=args.partition)
    else:
        E = executors.probe(args.partition, exclude=excluded_nodes)
    jarray = JobArray(E)

    if args.work_dir:
        os.environ['TMPDIR'] = args.work_dir


    # load data into pybids as layout

    layout = BIDSLayout(args.bids_dir)

    # verify the existence of diffusion data and/or fieldmaps

    try:
        dwi_file = os.path.basename(layout.get(subject=args.sub, extension='.nii.gz', suffix='dwi', run=args.run, return_type='filename').pop())
    except IndexError:
        logger.error("No diffusion data found. Double check bids directory to verify. Exiting.")
        sys.exit()

    try:
        ap_file = os.path.basename(layout.get(subject=args.sub, extension='.nii.gz', suffix='epi', direction='AP', run=args.run, return_type='filename').pop())
    except IndexError:
        #logger.warning("No AP field map data found. Double check bids directory to verify.")
        pass

    try:
        pa_file = os.path.basename(layout.get(subject=args.sub, extension='.nii.gz', suffix='epi', direction='PA', run=args.run, return_type='filename').pop())
    except IndexError:
        #logger.warning("No PA field map data found. Double check bids directory to verify.")
        pass

    json_file = os.path.basename(layout.get(subject=args.sub, extension='.json', suffix='dwi', run=args.run, return_type='filename').pop())

    basename = os.path.splitext(json_file)[0]

    os.system('mkdir -p $TMPDIR')

    # prequal job
    prequal_outdir = None
    if 'prequal' in args.sub_tasks:
        logger.debug('building prequal task')
        prequal_outdir = os.path.join(args.bids_dir, 'derivatives', 'dwiqc-prequal', f'sub-{args.sub}', f'ses-{args.ses}', 'OUTPUTS')
        prequal_task = prequal.Task(
            sub=args.sub,
            ses=args.ses,
            run=args.run,
            bids=args.bids_dir,
            outdir=prequal_outdir,
            fs_license = args.fs_license,
            container_dir = args.container_dir,
            prequal_config=args.prequal_config,
            no_gpu=args.no_gpu,
            tempdir=tempfile.gettempdir(),
            pipenv='/sw/apps/prequal'
        )
        os.environ['OPENBLAS_NUM_THREADS'] = '1'
        logger.info(f'SINGULARITY_BIND: {os.environ["SINGULARITY_BIND"]}')
        logger.info(json.dumps(prequal_task.command, indent=1))
        jarray.add(prequal_task.job)

    # qsiprep job
    qsiprep_outdir = None
    if 'qsiprep' in args.sub_tasks:
        qsiprep_outdir = os.path.join(args.bids_dir, 'derivatives', 'dwiqc-qsiprep', f'sub-{args.sub}', f'ses-{args.ses}', 'qsiprep_output')
        qsiprep_trick = tempfile.TemporaryDirectory(dir='/tmp', suffix='.qsiprep')
        #os.symlink(qsiprep_outdir, f"{qsiprep_trick}/q")
        qsiprep_task = qsiprep.Task(
            sub=args.sub,
            ses=args.ses,
            run=args.run,
            bids=args.bids_dir,
            outdir=qsiprep_outdir,
            qsiprep_config=args.qsiprep_config,
            fs_license=args.fs_license,
            container_dir = args.container_dir,
            custom_eddy=args.custom_eddy,
            no_gpu=args.no_gpu,
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
        if 'prequal' in args.sub_tasks:
            prequal_eddy(args, prequal_outdir)
        if 'qsiprep' in args.sub_tasks:
            qsiprep_eddy(args, qsiprep_outdir)
            browser.snapshot(f"{qsiprep_outdir}/qsiprep/sub-{args.sub}.html", f"{qsiprep_outdir}/qsiprep/qsiprep.pdf", args.container_dir)
            browser.imbed_images(f"{qsiprep_outdir}/qsiprep/sub-{args.sub}.html")
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

    # upload data to xnat over rest api
    if args.xnat_upload:
        logger.info('Uploading artifacts to XNAT')
        auth = yaxil.auth2(args.xnat_alias)
        yaxil.storerest(auth, args.artifacts_dir, 'dwiqc-resource')




def prequal_eddy(args, prequal_outdir):
    if 'prequal' in args.sub_tasks:
        eq_task = prequal_EQ.Task(
            sub=args.sub,
            ses=args.ses,
            run=args.run,
            bids=args.bids_dir,
            outdir=prequal_outdir,
            container_dir = args.container_dir,
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
            container_dir = args.container_dir,
            tempdir=tempfile.gettempdir(),
        )

        eq_task.build()





