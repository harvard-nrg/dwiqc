

import shutil
import os
import time
import sys
sys.path.insert(0, os.path.join(os.environ['MODULESHOME'], "init"))
from env_modules_python import module
sys.path.insert(0, '/n/home_fasse/dasay/dwiqc/dwiqc/tasks')
import __init__ as tasks
import logging
import subprocess
import json
from executors.models import Job


old_out = sys.stdout



class Task(tasks.BaseTask):
	def __init__(self, sub, ses, run, bids, outdir, parent=None, tempdir=None, pipenv=None):
		self._sub = sub
		self._ses = ses
		self._run = run
		self._bids = bids
		super().__init__(outdir, tempdir, pipenv)


	def build(self):

		log_file = open("eddy_quad.log", "w")		

		#load the fsl module
		module('load','fsl/6.0.4-centos7_64-ncf')
		while not os.path.exists(f'{self._outdir}/EDDY'):
			time.sleep(120)

		if os.path.isdir(f'{self._outdir}/EDDY'):
			os.chdir(f'{self._outdir}/EDDY')
			log_file = open(f"{self._outdir}/EDDY/eddy_quad.log", "w")	
			sys.stdout = log_file

		# copy the necessary file to EDDY directory

		while not os.path.exists('../PREPROCESSED/dwmri.nii.gz'):
			time.sleep(120)

		if os.path.isfile('../PREPROCESSED/dwmri.nii.gz'):
			shutil.copy('../PREPROCESSED/dwmri.nii.gz', 'eddy_results.nii.gz')

		# grab name of slspec file

		for file in os.listdir(self._outdir):
			if 'slspec' in file and file.endswith('.txt'):
				spec_file = file

		## run eddy quad

		eddy_quad = f"""eddy_quad \
		eddy_results \
		-idx index.txt \
		-par acqparams.txt \
		--mask=eddy_mask.nii.gz \
		--bvals=../PREPROCESSED/dwmri.bval \
		--bvecs=../PREPROCESSED/dwmri.bvec \
		--field ../TOPUP/topup_field.nii.gz \
		-s ../{spec_file} \
		-v"""

		proc1 = subprocess.Popen(eddy_quad, shell=True, stdout=subprocess.PIPE)
		proc1.communicate()

		sys.stdout = old_stdout

		log_file.close()


