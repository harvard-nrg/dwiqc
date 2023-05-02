sys.path.insert(0, os.path.join(os.environ['MODULESHOME'], "init"))
from env_modules_python import module
import shutil
import os
import sys


class Task(tasks.BaseTask):
	def __init__(self, sub, ses, run, bids, outdir,  tempdir=None, pipenv=None):
		self._sub = sub
		self._ses = ses
		self._run = run
		self._bids = bids
		self._layout = BIDSLayout(bids)
		super().__init__(outdir, tempdir, pipenv)


	def build(self):
		#load the fsl module
		module('load', 'fsl/6.0.4-ncf')
		os.chdir(f'{self._outdir}/EDDY')

		# copy the necessary file to EDDY directory
		shutil.copy('../PREPROCESSED/dwmri.nii.gz', 'eddy_results.nii.gz')

		# grab name of slspec file

		for file in os.listdir('..'):
			if 'slspec' in file and file.endswith('.txt'):
				spec_file = file

		## run eddy quad

		self._command = [
		'eddy_quad',
		'eddy_results',
		'-idx',
		'index.txt',
		'-par',
		'acqparams.txt',
		'--mask=eddy_mask.nii.gz',
		'--bvals=../PREPROCESSED/dwmri.bval',
		'--bvecs=../PREPROCESSED/dwmri.bvec',
		'--field',
		'../TOPUP/topup_field.nii.gz',
		'-s',
		f'../{spec_file}'
		'-v'
		]

		logdir = self.logdir()
		logfile = os.path.join(logdir, 'dwiqc-prequal_EQ.log')
		self.job = Job(
			name='dwiqc-prequal_EQ',
			time='180',
			memory='10G',
			cpus=1,
			nodes=1,
			command=self._command,
			output=logfile,
			error=logfile
		)
