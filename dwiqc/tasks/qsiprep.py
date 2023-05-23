
#### load necessary libraries

import subprocess
import os
import logging
from bids import BIDSLayout
import sys
import json
import nibabel as nib
import dwiqc.tasks as tasks
sys.path.insert(0, os.path.join(os.environ['MODULESHOME'], "init"))
from env_modules_python import module
import shutil
from executors.models import Job


module('load', 'cuda/9.1.85-fasrc01')


logger = logging.getLogger(__name__)


class Task(tasks.BaseTask):
	def __init__(self, sub, ses, run, bids, outdir, output_resolution=None, tempdir=None, pipenv=None):
		self._sub = sub
		self._ses = ses
		self._run = run
		self._bids = bids
		self._layout = BIDSLayout(bids)
		self._output_resolution = output_resolution
		super().__init__(outdir, tempdir, pipenv)



	def calc_mporder(self):
		# need to get the length of the SliceTiming File (i.e. number of slices) divided by the "MultibandAccelerationFactor". From there, 
		# divide that number by 3. That's the number passed to mporder.

		# this will grab the dwi file, pop it off the list, get the slice timing metadata, then grab the length of the slice timing array
		num_slices = len(self._layout.get(subject=self._sub, session=self._ses, run=self._run, suffix='dwi', extension='.nii.gz').pop().get_metadata()['SliceTiming'])

		multiband_factor = self._layout.get(subject=self._sub, session=self._ses, run=self._run, suffix='dwi', extension='.nii.gz').pop().get_metadata()['MultibandAccelerationFactor']

		mporder = (num_slices / multiband_factor) // 3

		return int(mporder)



	# this method checks if the user has passed a desired output resolution to dwiqc.py
	# if they haven't, the resolution of the T1w input image will be used.

	def check_output_resolution(self):
		if not self._output_resolution:
			t1_file = self._layout.get(subject=self._sub, session=self._ses, run=self._run, suffix='T1w', extension='.nii.gz', return_type='filename').pop()

			self._output_resolution = str(nib.load(t1_file).header['pixdim'][1])


	# this method creates the nipype config file necessary for qsiprep. This file ensures that intermediate files
	# don't get deleted for subsequent run of eddy_quad	

	def create_nipype(self):
		nipype = """[logging]
		
		[execution]
		remove_unnecessary_outputs = false

		[monitoring]"""

		with open(f"{self._bids}/nipype.cfg", "w") as file:
			file.write(nipype)


	def create_spec(self):
		dwi_file = self._layout.get(subject=self._sub, session=self._ses, run=self._run, suffix='dwi', extension='.nii.gz')
		#dwi_file = layout.get()[10]
		if len(dwi_file) > 1:
			raise DWISpecError('Found more than one dwi file. Please verify there are no duplicates.')
		if not dwi_file:
			raise DWISpecError(f'No dwi scan found for subject {self._sub} session {self._ses} run {self._run}')
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
			with open(f"{self._bids}/slspec_ABCD_dMRI.txt", "w") as file:
				# Write the values into the text file
				file.write(ABCD_values)

			return 'slspec_ABCD_dMRI.txt'


		# check for the UK Bio bank version of the scan and then create the slspec file accordingly

		elif 'UKbioDiff_ABCDseq_ABCDdvs' in series_desc:
			# Define Values
			UKBio_values = """1 25 49
			3 27 51
			5 29 53
			7 31 55
			9 33 57
			11 35 59
			23 47 71
			13 37 61
			15 39 63
			17 41 65
			19 43 67
			21 45 69
			2 26 50
			4 28 52
			6 30 54
			8 32 56
			10 34 58
			12 36 60
			0 24 48
			14 38 62
			16 40 64
			18 42 66
			20 44 68
			22 46 70"""


			# Create a text file
			with open(f"{self._bids}/slspec_UKBio_dMRI.txt", "w") as file:
				# Write the values into the text file
				file.write(UKBio_values)

			return 'slspec_UKBio_dMRI.txt'


		

		else:
			logger.info('Unable to determine dwi scan type. Moving on without creating slspec file.')


	# create necessary fsl eddy parameters json file using output from create_spec and calc_mporder

	def create_eddy_params(self):
		mporder = self.calc_mporder()
		spec_file = self.create_spec()
		params_file = {
			"flm": "quadratic",
			"slm": "linear",
			"fep": False,
			"interp": "spline",
			"nvoxhp": 1000,
			"fudge_factor": 10,
			"dont_sep_offs_move": False,
			"dont_peas": False,
			"niter": 5,
			"method": "jac",
			"repol": True,
			"num_threads": 1,
			"is_shelled": True,
			"use_cuda": True,
			"cnr_maps": True,
			"residuals": True,
			"output_type": "NIFTI_GZ",
			"estimate_move_by_susceptibility": True,
			"mporder": mporder,
			"slice_order": f"{self._bids}/{spec_file}",
			"args": "--ol_nstd=4 --ol_type=gw"
		}

		with open(f"{self._bids}/eddy_params_s2v_mbs.json", "w") as f:
			json.dump(params_file, f)

	# create qsiprep command to be executed

	def build(self):
		self.create_eddy_params()
		self.create_nipype()
		self.check_output_resolution()
		self._command = [
			'selfie',
			'--lock',
			'--output-file', self._prov,
			#'qsiprep',
			'singularity',
			'run',
			'--nv',
			'/n/sw/ncf/apps/qsiprep/0.14.0/qsiprep.sif',			
			self._bids,
			self._outdir,
			'participant',
			'--output-resolution',
			self._output_resolution,
			'--separate-all-dwis',
			'--output-space',
			'T1w',
			'--eddy-config',
			f'{self._bids}/eddy_params_s2v_mbs.json',
			'--recon-spec',
			'reorient_fslstd',
			'--notrack',
			'--n_cpus',
			'2',
			'--mem_mb',
			'40000',
			'--fs-license-file',
			'/n/helmod/apps/centos7/Core/freesurfer/6.0.0-fasrc01/license.txt',
			'-w',
			self._tempdir#,
			#'&&',
			#'cp',
			#'-r',
			#self._tempdir,
			#self._bids,
			#'&&',
			#'rm',
			#'-r',
			#self._tempdir
		]

		logdir = self.logdir()
		logfile = os.path.join(logdir, 'dwiqc-qsiprep.log')
		self.job = Job(
			name='dwiqc-qsiprep',
			time='2000',
			memory='40G',
			gpus=1,
			nodes=1,
			command=self._command,
			output=logfile,
			error=logfile
		)



