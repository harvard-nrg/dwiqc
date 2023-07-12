
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
	def __init__(self, sub, ses, run, bids, outdir, no_gpu=False, tempdir=None, pipenv=None):
		self._sub = sub
		self._ses = ses
		self._run = run
		self._bids = bids
		self._no_gpu = no_gpu
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

		json_file = self._layout.get(subject=self._sub, session=self._ses, run=self._run, suffix='dwi', extension='.json', return_type='filename').pop()

		# Grab the slice timing info
		series_desc = dwi_file.get_metadata()['SeriesDescription']

		# sort it in ascending order
		slice_timing.sort()

		# remove any duplicates
		slice_timing = list(set(slice_timing))

		# get the total number of slices
		num_slices = len(slice_timing)

		# check if there's an even or odd number of slices, run corresponding helper method
		if num_slices % 2 == 0:
			self.even_slices(self, json_file, inputs_dir)

		else:
			self.odd_slices(self, json_file, inputs_dir)

		# call method that creates the necessary csv file for prequal
		self.create_csv(inputs_dir, dwi_file)

		# call method that adds an "IntendedFor" key-value pair to json file (for fieldmaps)
		self.add_intended_for()

		# call method that checks the manufacturer, scanner model and max bval. that will determine if --nonzero_shells argument needs to be passed to prequal
		self.check_shells(dwi_file)

	# helper method that creates slspec file for an acquisition with an even number of slices

	# if the number of slices is even, create spec file accordingly. source = https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/eddy/Faq#How_should_my_--slspec_file_look.3F
    # line 138 edited from `item - 1` to `item - 0`

	def even_slices(self, json_file, inputs_dir):
		# open the json file and 
		with open(json_file, 'r') as fp:
			fcont = fp.read()

		i1 = fcont.find('SliceTiming')
		i2 = fcont[i1:].find('[')
		i3 = fcont[i1 + i2:].find(']')
		cslicetimes = fcont[i1 + i2 + 1:i1 + i2 + i3]
		slicetimes = list(map(float, cslicetimes.split(',')))
		sortedslicetimes = sorted(slicetimes)
		sindx = sorted(range(len(slicetimes)), key=lambda k: slicetimes[k])
		mb = len(sortedslicetimes) // (sum(1 for a, b in zip(sortedslicetimes, sortedslicetimes[1:]) if a != b) + 1)
		slspec = [sindx[i:i + mb] for i in range(0, len(sindx), mb)]
		slspec = [[item - 0 for item in sublist] for sublist in slspec]

		spec_file = f"{inputs_dir}/even_slices_slspec.txt"

		with open(spec_file, 'w') as fp:
			for sublist in slspec:
				fp.write(' '.join(str(item) for item in sublist))
				fp.write('\n')

		os.makedirs(self._outdir)
		shutil.copy(f"{inputs_dir}/even_slices_slspec.txt", self._outdir)
		self._spec = "even"


	# helper method that generates slspec file for an acquisition with an odd number of slices

	def odd_slices(self, json_file, inputs_dir):
		## build the first column

		col1 = []

		for i in range(0, num_slices, 2):
			col1.append(i)

		for j in range(1, num_slices, 2):
			col1.append(j)

		col1 = np.array(col1)

		if len(col1) != num_slices:
			raise DWISpecError('Spec file column does not match length of slice timing file. Exiting.')

		## build second column

		col2 = []

		for col1_num in col1:
			col2_num = col1_num + num_slices
			col2.append(col2_num)
		col2 = np.array(col2)

		# build third column

		col3 = []

		for col2_num in col2:
			col3_num = col2_num + num_slices
			col3.append(col3_num)
		col3 = np.array(col3)

		all_cols = np.column_stack([col1, col2, col3])

		spec_file = f"{inputs_dir}/odd_slices_slspec.txt"

		np.savetxt(spec_file, data, fmt=['%d', '%d', '%d'])

		os.makedirs(self._outdir)
		shutil.copy(f"{inputs_dir}/odd_slices_slspec.txt", self._outdir)
		self._spec = "odd"

	# this method will grab the manufacturer name and model and the max bval value. 
	# if it is a Siemens Skyra and the max bval is 2000, the non-zero_shells argument needs to be passed to prequal
	def check_shells(self, dwi_file):
		# grab the Manufacturer and model from dwi file metadata
		manufacturer = dwi_file.get_metadata()['Manufacturer']
		scanner_model = dwi_file.get_metadata()['ManufacturersModelName']

		# load the f val and convert it to a python list. convert the elements from strings to integers
		bval_file = self._layout.get(subject=self._sub, session=self._ses, run=self._run, suffix='dwi', extension='.bval', return_type='filename').pop()

		bval = open(bval_file, 'r')
		data = bval.read()
		data = data.replace('\n', '').split(" ")
		int_data = [eval(i) for i in data]

		max_val = max(int_data)

		if manufacturer == "Siemens" and scanner_model == "Skyra" and max_val == 2000:
			self._nonzero_shells = True
		else:
			self._nonzero_shells = False



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
		if self._nonzero_shells == False:
			if self._no_gpu:
				self._command = [
					'selfie',
					'--lock',
					'--output-file', self._prov,
					'singularity',
					'run',
					'-e',
					'--contain',
					'-B',
					f'{inputs_dir}:/INPUTS/',
					'-B',
					f'{self._outdir}:/OUTPUTS',
					'-B',
					f'{self._tempdir}:/tmp',
					'-B',
					'/n/sw/ncf/apps/freesurfer/6.0.0/license.txt:/APPS/freesurfer/license.txt',
					'-B',
					'/n/nrg_l3/Lab/users/nrgadmin/PreQual/src/CODE/dtiQA_v7/run_dtiQA.py:/CODE/dtiQA_v7/run_dtiQA.py',
					'-B',
					'/n/nrg_l3/Lab/users/nrgadmin/PreQual/src/CODE/dtiQA_v7/vis.py:/CODE/dtiQA_v7/vis.py',
					'/n/sw/ncf/containers/masilab/prequal/1.0.8/prequal.sif',
					'--save_component_pngs',
					'j',
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
			else:
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

		elif self._nonzero_shells == True:
			if self._no_gpu:

				self._command = [
					'selfie',
					'--lock',
					'--output-file', self._prov,
					'singularity',
					'run',
					'-e',
					'--contain',
					'-B',
					f'{inputs_dir}:/INPUTS/',
					'-B',
					f'{self._outdir}:/OUTPUTS',
					'-B',
					f'{self._tempdir}:/tmp',
					'-B',
					'/n/sw/ncf/apps/freesurfer/6.0.0/license.txt:/APPS/freesurfer/license.txt',
					'-B',
					'/n/nrg_l3/Lab/users/nrgadmin/PreQual/src/CODE/dtiQA_v7/run_dtiQA.py:/CODE/dtiQA_v7/run_dtiQA.py',
					'-B',
					'/n/nrg_l3/Lab/users/nrgadmin/PreQual/src/CODE/dtiQA_v7/vis.py:/CODE/dtiQA_v7/vis.py',
					'/n/sw/ncf/containers/masilab/prequal/1.0.8/prequal.sif',
					'--save_component_pngs',
					'j',
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
			else:

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

		### ******** temporary check ***********
		print(self._command)
		sys.exit()

		logdir = self.logdir()
		logfile = os.path.join(logdir, 'dwiqc-prequal.log')
		if self._no_gpu:
			self.job = Job(
				name='dwiqc-prequal',
				time='3000',
				memory='40G',
				cpus=2,
				nodes=1,
				command=self._command,
				output=logfile,
				error=logfile
			)
		else:
			self.job = Job(
				name='dwiqc-prequal',
				time='3000',
				memory='40G',
				gpus=1,
				nodes=1,
				command=self._command,
				output=logfile,
				error=logfile
			)



class DWISpecError(Exception):
	pass





