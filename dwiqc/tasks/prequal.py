
#### load necessary libraries
import tempfile
import subprocess
import os
import logging
from bids import BIDSLayout
import sys
import json
import dwiqc.tasks as tasks
import shutil
from executors.models import Job
sys.path.insert(0, os.path.join(os.environ['MODULESHOME'], "init"))
from env_modules_python import module


logger = logging.getLogger(__name__)


module('load', 'cuda/9.1.85-fasrc01')

# pull in some parameters from the BaseTask class in the __init__.py directory

class Task(tasks.BaseTask):
	def __init__(self, sub, ses, run, bids, outdir, tempdir=None, pipenv=None):
		self._sub = sub
		self._ses = ses
		self._run = run
		self._bids = bids
		self._layout = BIDSLayout(bids)
		super().__init__(outdir, tempdir, pipenv)


	# create an INPUTS dir next to the OUTPUTS dir
	def copy_inputs(self, inputs_dir):
		try:
			os.makedirs(inputs_dir)
		except FileExistsError:
			pass
		#layout = BIDSLayout(self._bids) # load the data layout into pybids
		all_files = self._layout.get(subject=self._sub, session=self._ses, run=self._run, return_type='filename') # get a list of all of the subject's files
		# copy the all the subject's files into the INPUTS directory
		for file in all_files:
			basename = os.path.basename(file)
			dest = os.path.join(inputs_dir, basename)
			shutil.copy(file, dest)

		self.create_bfiles(inputs_dir)
		


		## keeping this code here just in case the symlinks don't work
			#shutil.copy(file, inputs)


	# the fieldmap data needs accompanying 'dummy' bval and bvec files that consist of 0's
	def create_bfiles(self, inputs_dir):
		# get a list of all the fmap files that end with .json (this it's helpful to have a file with just one extension)

		#layout = BIDSLayout(self._bids)
		fmap_files = self._layout.get(subject=self._sub, session=self._ses, run=self._run, suffix='epi', extension='.json', return_type='filename')

		# get the basename of the file and then remove the extension
		for fmap in fmap_files:
			no_ext = os.path.splitext(os.path.basename(fmap))[0]

			# create a .bval file with a single 0

			with open(f'{inputs_dir}/{no_ext}.bval', 'w') as bval:
				bval.write('0')

			# create .bvec file with 3 0's

			with open(f'{inputs_dir}/{no_ext}.bvec', 'w') as bvec:
				bvec.write('0\n0\n0')

		self.create_spec(inputs_dir)
		


	# this method serves to create the accompanying spec file for prequal 
	# the contents of the file depends on the SeriesDescription stored in the metadata

	def create_spec(self, inputs_dir):
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
			with open(f"{inputs_dir}/slspec_ABCD_dMRI.txt", "w") as file:
				# Write the values into the text file
				file.write(ABCD_values)
			os.makedirs(self._outdir)
			shutil.copy(f"{inputs_dir}/slspec_ABCD_dMRI.txt", self._outdir)
			self._spec = "ABCD"




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
			with open(f"{inputs_dir}/slspec_UKBio_dMRI.txt", "w") as file:
				# Write the values into the text file
				file.write(UKBio_values)

			os.makedirs(self._outdir)
			shutil.copy(f"{inputs_dir}/slspec_UKBio_dMRI.txt", self._outdir)
			self._spec = "UKBio"
		

		else:
			logger.info('Unable to determine dwi scan type. Moving on without creating slspec file.')


		self.create_csv(inputs_dir, dwi_file)
		self.add_intended_for()

	# this method will grab the phase encode direction and total readout time for the main dwi scan and both fieldmaps and place them into a csv file named
	# dtiQA_config.csv

	def create_csv(self, inputs_dir, dwi_file):


		# grab TotalReadoutTime from json file

		readout_time = dwi_file.get_metadata()['TotalReadoutTime']

		# get phase encode directions of the PA and AP files

		PA_dir, AP_dir = self.get_phase_encode()


		# get all three json files (dwi, PA, AP)

		filenames = self._layout.get(subject=self._sub, session=self._ses, run=self._run, extension='.json', return_type='filename')

		# remove the extension from each file name to prepare for writing into csv file

		no_ext = [os.path.splitext(os.path.basename(file))[0] for file in filenames]

		# iterate through each file, checking for dwi, PA or AP in the file name. Check phase encoding direction for
		# the PA and AP files. Assign a + or - depending on the direction

		for file in no_ext:
			if file.endswith('dwi'):
				dwi_line = f'{file},+,{readout_time}'
			elif 'PA' in file:
				if PA_dir == 'j':
					PA_line = f'{file},+,{readout_time}'
				else:
					PA_line = f'{file},-,{readout_time}'
			elif 'AP' in file:
				if AP_dir == 'j':
					AP_line = f'{file},+,{readout_time}'
				else:
					AP_line = f'{file},-,{readout_time}'

		# write each of the created lines into a csv file

		with open(f'{inputs_dir}/dtiQA_config.csv', 'w') as csv:
			csv.write(f'{dwi_line}\n')
			csv.write(f'{PA_line}\n')
			csv.write(f'{AP_line}\n')



	def get_phase_encode(self):
		PA_file = self._layout.get(subject=self._sub, session=self._ses, run=self._run, suffix='epi', direction='PA', extension='.nii.gz').pop()

		PA_phase = PA_file.get_metadata()['PhaseEncodingDirection']

		AP_file = self._layout.get(subject=self._sub, session=self._ses, run=self._run, suffix='epi', direction='AP', extension='.nii.gz').pop()

		AP_phase = AP_file.get_metadata()['PhaseEncodingDirection']

		return PA_phase, AP_phase


	# ******** this will also need to be added to qsiprep.py ***********



# this method will add an "IntendedFor" key-value pair to the fieldmap scans

	def add_intended_for(self):

		fmap_json_files = self._layout.get(run=self._run, suffix='epi', extension='.json', return_type='filename')

		dwi_file = os.path.basename(self._layout.get(subject=self._sub, session=self._ses, run=self._run, suffix='dwi', extension='.nii.gz', return_type='filename').pop())

		intended_for = {"IntendedFor":f"ses-{self._ses}/dwi/{dwi_file}"}

		for file in fmap_json_files:
			with open(file, 'r+') as f:
				file_data = json.load(f)
				if "IntendedFor" in file_data:
					continue
				else:
					file_data.update(intended_for)
					f.seek(0)
					json.dump(file_data, f, indent = 2)


	# build the prequal sbatch command and create job

	def build(self):
		self.add_intended_for()
		self._tempdir = tempfile.gettempdir()
		inputs_dir = f'{self._tempdir}/INPUTS/'
		self.copy_inputs(inputs_dir)
		if self._spec == "ABCD":
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
				'/n/sw/helmod-rocky8/apps/Core/cuda/9.1.85-fasrc01:/usr/local/cuda',
				'-B',
				'/n/nrg_l3/Lab/users/nrgadmin/PreQual/src/CODE/dtiQA_v7/run_dtiQA.py:/CODE/dtiQA_v7/run_dtiQA.py',
				'-B',
				'/n/nrg_l3/Lab/users/nrgadmin/PreQual/src/CODE/dtiQA_v7/vis.py:/CODE/dtiQA_v7/vis.py',
				'/n/sw/ncf/containers/masilab/prequal/1.0.8/prequal.sif',
				'--save_component_pngs',
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

		elif self._spec == "UKBio":

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
				'/n/sw/helmod-rocky8/apps/Core/cuda/9.1.85-fasrc01:/usr/local/cuda',
				'-B',
				'/n/nrg_l3/Lab/users/nrgadmin/PreQual/src/CODE/dtiQA_v7/run_dtiQA.py:/CODE/dtiQA_v7/run_dtiQA.py',
				'-B',
				'/n/nrg_l3/Lab/users/nrgadmin/PreQual/src/CODE/dtiQA_v7/vis.py:/CODE/dtiQA_v7/vis.py',
				'/n/sw/ncf/containers/masilab/prequal/1.0.8/prequal.sif',
				'--save_component_pngs',
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
				'--nonzero_shells',
				'350,650,1350,2000',
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




class DWISpecError(Exception):
	pass





