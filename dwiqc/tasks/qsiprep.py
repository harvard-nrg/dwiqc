
#### load necessary libraries

import subprocess
import os
import logging
from bids import BIDSLayout
import sys
import json
sys.path.insert(0, '/n/home_fasse/dasay/dwiqc/dwiqc/tasks')
import __init__ as tasks
import shutil
from executors.models import Job

#### To Do list: 

#		1) Add --output-resolution as optional command line argument in dwiqc.py



# currently loading modules via subprocess call. Is there a better way?


load_modules = 'module load qsiprep/0.14.0-ncf; unset DISPLAY; module load cuda/9.1.85-fasrc01; nvidia-smi; export SINGULARITY_NV=1'
proc1 = subprocess.Popen(load_modules, shell=True, stdout=subprocess.PIPE)
proc1.communicate()


logger = logging.getLogger(__name__)


class Task(tasks.BaseTask):
	def __init__(self, sub, ses, run, bids, outdir, tempdir=None, pipenv=None):
		self._sub = sub
		self._ses = ses
		self._run = run
		self._bids = bids
		self._layout = BIDSLayout(bids)
		super().__init__(outdir, tempdir, pipenv)



	def calc_mporder(self):
		pass


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

	def create_eddy_params(self, mporder, spec_path):

		params_file = {
          "flm": "quadratic",
          "slm": "linear",
          "fep": false,
          "interp": "spline",
          "nvoxhp": 1000,
          "fudge_factor": 10,
          "dont_sep_offs_move": false,
          "dont_peas": false,
          "niter": 5,
          "method": "jac",
          "repol": true,
          "num_threads": 1,
          "is_shelled": true,
          "use_cuda": true,
          "cnr_maps": true,
          "residuals": true,
          "output_type": "NIFTI_GZ",
          "estimate_move_by_susceptibility": true,
          "mporder": mporder,
          "slice_order": f"{self._bids}/{spec_file}",
          "args": "--ol_nstd=4 --ol_type=gw"
		}

		with open(f"{self._bids}/params_file.json", "w") as f:
			json.dump(params_file, f)




qsiprep ${1:-/n/home_fasse/dasay/qsiprep_test} ${2:-/n/home_fasse/dasay/qsiprep_test/qsiprep_output} participant --separate-all-dwis --output-space T1w --eddy-config eddy_params_s2v_mbs.json --recon-spec reorient_fslstd --notrack --n_cpus ${SLURM_JOB_CPUS_PER_NODE} --mem_mb ${MEM_IN_MB} --fs-license-file /ncf/nrg/sw/apps/freesurfer/6.0.0/license.txt -w ${WD} && cp -r ${WD} . && rm -r ${WD}


	def build(self):
		self._command = [
			'selfie',
			'--lock',
			'--output-file', self._prov,
			'singularity',
			'run',
			'-e',
			'--contain',
			'--nv',
			'-B',
			f'{inputs_dir}:/INPUTS/',
			'-B',
			f'{self._outdir}:/OUTPUTS',
			'-B',
			f'{self._tempdir}:/tmp',
			'-B',
			'/n/sw/ncf/apps/freesurfer/6.0.0/license.txt:/APPS/freesurfer/license.txt',
			'-B',
			'/n/helmod/apps/centos7/Core/cuda/9.1.85-fasrc01:/usr/local/cuda',
			'/n/sw/ncf/containers/masilab/prequal/1.0.8/prequal.sif',
			'j',
			'--eddy_cuda',
			'9.1',
			'--num_threads',
			'2',
			'--denoise',
			'off',
			'--degibbs',
			'off',
			'--rician',
			'off',
			'--prenormalize',
			'on',
			'--correct_bias',
			'on',
			'--topup_first_b0s_only',
			'--subject',
			self._sub,
			'--project',
			'SSBC',
			'--session',
			self._ses
		]

		logdir = self.logdir()
		logfile = os.path.join(logdir, 'dwiqc-prequal.log')
		self.job = Job(
			name='dwiqc-prequal',
			time='360',
			memory='20G',
			gpus=1,
			nodes=1,
			command=self._command,
			output=logfile,
			error=logfile
		)



