# There are  few things this script will need in order to be successful. 


#### load necessary libraries

import subprocess
import os
import logging
from bids import BIDSLayout
import shutil
from executors.models import Job

# 1. Need to figure out how to load the necessary modules via the python script. subprocess call?

load_modules = 'module load masilab/prequal/1.0.8-ncf cuda/9.1.85-fasrc01;unset DISPLAY'
proc1 = subprocess.Popen(load_modules, shell=True, stdout=subprocess.PIPE)
proc1.communicate()


logger = logging.getLogger(__name__)


# pull in some parameters from the BaseTask class in the __init__.py directory

class Task(tasks.BaseTask):
	def __init__(self, sub, ses, run, bids, outdir, tempdir=None, pipenv=None):
		self._sub = sub
		self._ses = ses
		self._run = run
		self._bids = bids
		self._layout = BIDSLayout(bids)
		super().__init__(outdir, tempdir, pipenv)
		self._inputs = f'{self._tempdir}/INPUTS'


	# create an INPUTS dir next to the OUTPUTS dir
	def create_symlinks(self):
		os.makedirs(self._inputs)
		#layout = BIDSLayout(self._bids) # load the data layout into pybids
		all_files = self._layout.get(subject=self._sub, session=self._ses, run=self._run, return_type='filename') # get a list of all of the subject's files
		# copy the all the subject's files into the INPUTS directory
		for file in all_files:
			basename = os.path.basename(file)
			dest = os.path.join(self._inputs, basename)
			os.symlink(file, dest)

		self.create_bfiles(self, self._inputs)
		



			#shutil.copy(file, inputs)


	# the fieldmap data needs accompanying 'dummy' bval and bvec files that consist of 0's
	def create_bfiles(self, inputs):
		# get a list of all the fmap files that end with .json (this it's helpful to have a file with just one extension)

		#layout = BIDSLayout(self._bids)
		fmap_files = self._layout.get(subject=self._sub, session=self._ses, run=self._run, suffix='epi', extension='.json', return_type='filename')

		# get the basename of the file and then remove the extension
		for fmap in fmap_files:
			no_ext = os.path.splitext(os.path.basename(fmap))[0]
			print(no_ext)

			# create a .bval file with a single 0

			with open(f'{inputs}/{no_ext}.bval', 'w') as bval:
				bval.write('0')

			# create .bvec file with 3 0's

			with open(f'{inputs}/{no_ext}.bvec', 'w') as bvec:
				bvec.write('0\n0\n0')

		self.create_spec()


	# this method serves to create the accompanying spec file for prequal 
	# the contents of the file depends on the SeriesDescription stored in the metadata

	def create_spec(self):
		dwi_file = self._layout.get(subject=self._sub, session=self._ses, run=self._run, suffix='dwi', extension='.nii.gz', return_type='BIDSFile')
		#dwi_file = layout.get()[10]
		if len(dwi_file) > 1:
			#raise DWISpecError
		if not dwi_file:
			#raise DWISpecError
		else:
			dwi_file = dwi_file.pop()

		series_desc = dwi_file.get_metadata()['SeriesDescription']

		if 'ABCD_dMRI_lowSR' in series_desc:
			# Define the values
			ABCD_values = """0 27 54
			2 29 56
			4 31 58
			6 33 60
			8 35 62
			10 37 64
			12 39 66
			14 41 68
			16 43 70
			18 45 72
			20 47 74
			22 49 76
			24 51 78
			26 53 80
			1 28 55
			3 30 57
			5 32 59
			7 34 61
			9 36 63
			11 38 65
			13 40 67
			15 42 69
			17 44 71
			19 46 73
			21 48 75
			23 50 77
			25 52 79"""

			# Create a text file
			with open(f"{self._inputs}/slspec_ABCD_dMRI.txt", "w") as file:
			    # Write the values into the text file
			    file.write(ABCD_values)




	def build(self):
		self.create_symlink()
		self._command = [
			'selfie',
			'--lock',
			'--output-file', self._prov,
			'singularity run -e --contain --nv',
			f'-B {self._inputs}:/INPUTS',
			f'-B {self._outdir}:/OUTPUTS',
			f'-B {self._tempdir}:/tmp',
			f'-B /n/sw/ncf/apps/freesurfer/6.0.0/license.txt:/APPS/freesurfer/license.txt',
			f'-B /n/helmod/apps/centos7/Core/cuda/9.1.85-fasrc01:/usr/local/cuda',
			f'/n/sw/ncf/containers/masilab/prequal/1.0.8/prequal.sif',
			f'j --eddy_cuda 9.1 --num_threads ${SLURM_JOB_CPUS_PER_NODE} --denoise off --degibbs off --rician off --prenormalize on --correct_bias on --topup_first_b0s_only',
			f'--subject {self._sub} --project SSBC --session {self._ses}'
		]

		logdir = self.logdir()
		logfile = os.path.join(logdir, 'dwiqc-prequal.log')
		self.job = Job(
			name='dwiqc-prequal',
			time='360',
			memory='10G',
			gpus=1,
			nodes=1,
			command=self._command,
			output=logfile,
			error=logfile
		)


