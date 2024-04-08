#### load necessary libraries

import subprocess
import os
import yaml
import logging
from bids import BIDSLayout
import sys
import json
import nibabel as nib
import dwiqc.tasks as tasks
import shutil
from executors.models import Job
import dwiqc.config as config
import numpy as np
from pprint import pprint
import re
import shutil
from dipy.io import read_bvals_bvecs
from dipy.core.gradients import gradient_table
from datetime import datetime

date = datetime.today().strftime('%Y-%m-%d')

logger = logging.getLogger(__name__)


class Task(tasks.BaseTask):
	def __init__(self, sub, ses, run, bids, outdir, qsiprep_config, fs_license, container_dir=None, custom_eddy=False, no_gpu=False, output_resolution=None, tempdir=None, pipenv=None):
		self._sub = sub
		self._ses = ses
		self._run = run
		self._bids = bids
		self._qsiprep_config = qsiprep_config
		self._fs_license = fs_license
		self._container_dir = container_dir
		self._custom_eddy = custom_eddy
		self._no_gpu = no_gpu
		self._layout = BIDSLayout(bids)
		self._output_resolution = output_resolution
		super().__init__(outdir, tempdir, pipenv)


	def check_container_path(self):
		if self._container_dir:
			try:
				self._qsiprep_sif = f'{self._container_dir}/qsiprep.sif'
			except FileNotFoundError:
				logger.error(f'{self._container_dir}/qsiprep.sif does not exist. Verify the path and file name.')
				sys.exit(1)
			try:
				self._fsl_sif = f'{self._container_dir}/fsl_6.0.4.sif'
			except FileNotFoundError:
				logger.error(f'{self._container_dir}/fsl_6.0.4.sif does not exist. Verify the path and file name.')
				sys.exit(1)

		else:
			home_dir = os.path.expanduser("~")
			self._qsiprep_sif = os.path.join(home_dir, '.config/dwiqc/containers/qsiprep.sif')
			self._fsl_sif = os.path.join(home_dir, '.config/dwiqc/containers/fsl_6.0.4.sif')


	def calc_mporder(self):
		## if --no-gpu argument is passed, make mporder equal to 1
		if self._no_gpu:
			mporder = 1
			return mporder

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
			t1_file = self._layout.get(subject=self._sub, session=self._ses, suffix='T1w', extension='.nii.gz', return_type='filename').pop()

			self._output_resolution = str(nib.load(t1_file).header['pixdim'][1])


	# this method creates the nipype config file necessary for qsiprep. This file ensures that intermediate files
	# don't get deleted for subsequent run of eddy_quad	

	def create_nipype(self):
		nipype = """[logging]
		
		[execution]
		remove_unnecessary_outputs = false
		parameterize_dirs = false

		[monitoring]"""

		home_dir = os.path.expanduser("~")

		os.makedirs(f"{home_dir}/.nipype", exist_ok=True)

		with open(f"{home_dir}/.nipype/nipype.cfg", "w") as file:
			file.write(nipype)


	def create_spec(self):
		dwi_file = self._layout.get(subject=self._sub, session=self._ses, suffix='dwi', extension='.nii.gz')
		#dwi_file = layout.get()[10]
		if len(dwi_file) > 1:
			logger.warning('QSIPREP_WARNING: More than one main DWI scan detected. Ensure scans were acquired using the same parameters.')
		if not dwi_file:
			raise DWISpecError(f'No dwi scan found for subject {self._sub} session {self._ses}')
		else:
			dwi_file = dwi_file.pop()

		json_file = self._layout.get(subject=self._sub, session=self._ses, suffix='dwi', extension='.json', return_type='filename').pop()

		# Grab the slice timing info
		slice_timing = dwi_file.get_metadata()['SliceTiming']

		# sort it in ascending order
		slice_timing.sort()

		# remove any duplicates
		slice_timing = list(set(slice_timing))

		# get the total number of slices
		num_slices = len(slice_timing)

		# check if there's an even or odd number of slices, run corresponding helper method
		if num_slices % 2 == 0:
			self.even_slices(json_file)

		else:
			self.odd_slices(json_file, num_slices)

	# helper method that creates slspec file for an acquisition with an even number of slices

	# if the number of slices is even, create spec file accordingly. source = https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/eddy/Faq#How_should_my_--slspec_file_look.3F
    # line 138 edited from `item - 1` to `item - 0`

	def even_slices(self, json_file):
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

		spec_file = f"{self._bids}/even_slices_slspec.txt"

		with open(spec_file, 'w') as fp:
			for sublist in slspec:
				fp.write(' '.join(str(item) for item in sublist))
				fp.write('\n')

		self._spec = spec_file


	# helper method that generates slspec file for an acquisition with an odd number of slices

	def odd_slices(self, json_file, num_slices):
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

		spec_file = f"{self._bids}/odd_slices_slspec.txt"

		np.savetxt(spec_file, all_cols, fmt=['%d', '%d', '%d'])

		self._spec = spec_file

	# create necessary fsl eddy parameters json file using output from create_spec and calc_mporder

	def create_eddy_params(self):
		mporder = self.calc_mporder()
		self.create_spec()
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
			"slice_order": self._spec,
			"args": "--ol_nstd=6 --ol_type=gw"
		}
		
		if not self._custom_eddy:
			with open(f"{self._bids}/eddy_params_s2v_mbs.json", "w") as f:
				json.dump(params_file, f)
		else:
			print('Custom eddy_params file being fed in by user.')

	def check_fieldmaps(self):
		"""
		This method checks if there are dedicated fieldmaps for each "main" diffusion scan. If not, it will extract volumes from each main scan
		and place them into the fmap directory. Then an "IntendedFor" key-value pair will be added into the json file of the newly created fmap file
		(and any fmap files that already existed)
		"""

		dwi_files = self._layout.get(subject=self._sub, session=self._ses, suffix='dwi', extension='.nii.gz', return_type='filename')

		fmap_files = self._layout.get(subject=self._sub, session=self._ses, suffix='epi', extension='.nii.gz', return_type='filename')

		all_nii_files = dwi_files + fmap_files

		if len(dwi_files)*2 != len(fmap_files):

			self.uneven_main_and_fmaps(all_nii_files, dwi_files)

		else:

			self.even_main_and_fmaps(all_nii_files)

	def uneven_main_and_fmaps(self, all_nii_files, dwi_files):
		"""
		First, this function will attempt to match fmap and main dwi runs together by acquisition group, exit if unable to. It will then
		add the necessary 'IntendedFor' field to the json of the supplied fmap
		Next, this function will create a fieldmap file from each "main" dwi scan. It will also create a json file for
		said new fieldmap and add the 'IntendedFor' field.
		"""

		dwi_acq_groups, fmap_acq_groups = self.acquistion_group_match(all_nii_files)

		if not dwi_acq_groups or not fmap_acq_groups:
			raise DWISpecError('Uneven number of fieldmaps and main scans and no acqusition group specified. Please add to BIDS file names and retry. Exiting')

		## interate through all the fmap and dwi key-value pairs. if the values equal each other, insert into the fmap json file
		# and IntendedFor field that points to the matched dwi scan

		for fmap_key, fmap_value in fmap_acq_groups.items():
			for dwi_key, dwi_value in dwi_acq_groups.items():
				if fmap_value == dwi_value:
					try:
						json_file = fmap_key.replace('.nii.gz', '.json')
					except FileNotFoundError:
						json_file = fmap_key.replace('.nii', '.json')
					new_dwi_key = os.path.basename(dwi_key)
					self.insert_json_value('IntendedFor', f'ses-{self._ses}/dwi/{new_dwi_key}', json_file)

		for dwi_file in dwi_files:
			dwi_basename = os.path.basename(dwi_file)

			self.extract_vols(dwi_file, dwi_basename)


	def even_main_and_fmaps(self, all_nii_files):
		"""
		If there are two fieldmaps for even main dwi scan, then there just needs to be IntendedFor added to each fmap json file
		This method may not be completely necessary...
		"""

		pass



	def extract_vols(self, dwi_full_path, dwi_basename):

		# provide path to bval file

		try:
			bval = dwi_full_path.replace('.nii.gz', '.bval')
		except FileNotFoundError:
			bval = dwi_full_path.replace('.nii', '.bval')

		# provide name of output file

		epi_output = dwi_full_path.replace('_dwi.', '_epi.')

		epi_output_path = epi_output.replace('/dwi/', '/fmap/')
		
		self.run_extract(dwi_full_path, bval, epi_output_path)


		# create an output file path for the new fmap's json file

		try:
			fmap_json_file_path = epi_output_path.replace('.nii.gz', '.json')
		except FileNotFoundError:
			fmap_json_file_path = epi_output_path.replace('.nii', '.json')

		# find the main dwi json file that needs to be copied

		try:
			dwi_json_file_path = dwi_full_path.replace('.nii.gz', '.json')
		except FileNotFoundError:
			dwi_json_file_path = dwi_full_path.replace('.nii', '.json')

		shutil.copy(dwi_json_file_path, fmap_json_file_path)

		## Add IntendedFor to the new json files

		self.insert_json_value('IntendedFor', f'ses-{self._ses}/dwi/{dwi_basename}', fmap_json_file_path)

	def run_extract(self, dwi_full_path, bval_path, epi_out_path):

		bvec_path = bval_path.replace('.bval', '.bvec')

		bvals, bvecs = read_bvals_bvecs(bval_path, bvec_path)

		list_of_bvals = []

		gtab = gradient_table(bvals, bvecs)

		for val in gtab.bvals:
			list_of_bvals.append(str(val))

		b0_volumes = []

		for idx, bval in enumerate(list_of_bvals):
			if bval == '0.0':
				b0_volumes.append(str(idx))

		b0_string = ','.join(b0_volumes)


		os.makedirs(self._outdir, exist_ok=True)

		try:

			extract_command = f"singularity exec /{self._fsl_sif} /APPS/fsl/bin/fslselectvols -i {dwi_full_path} -o {epi_out_path} --vols={b0_string}"

			proc1 = subprocess.check_output(extract_command, shell=True, stderr=subprocess.STDOUT, text=True)

		except subprocess.CalledProcessError as e:
			print(e.stdout)


	def insert_json_value(self, key, value, json_file):
		"""
		This helper method will load in the given json file and check if the given key already exists.
		If it does but it's not a list, it will be made into a list. 
		The new value will be appended to the value list
		If it doesn't exist, it will be added to the json file as a key-value pair
		re-open the json file and write new contents
		"""
		with open(json_file, 'r') as f:
			data = json.load(f)

		if key in data:
			if not isinstance(data[key], list):
				data[key] = [data[key]]

			if value not in data[key]:
				data[key].append(value)


		else:
			data[key] = [value]
		
		with open(json_file, 'w') as file:
			json.dump(data, file, indent=2)

	def acquistion_group_match(self, all_nii_files):
		"""
		This helper method exists to match a given list of nii files (dwi and fmap scans) to each other based on acquisition group
		"""
		dwi_acqusition_groups = {}

		fmap_acquisition_groups = {}

		for scan in all_nii_files:

			no_path_name = os.path.basename(scan)

			pattern = r'acq-(.*?)_'

			acq_value = self.match(pattern, no_path_name)

			if acq_value:
				if 'dwi.nii' in no_path_name:
					dwi_acqusition_groups[scan] = acq_value
				elif 'epi.nii' in no_path_name:
					fmap_acquisition_groups[scan] = acq_value

		return dwi_acqusition_groups, fmap_acquisition_groups

	def run_number_match(self, all_nii_files):
		"""
		This method will attempt to match fmap and dwi scans based on their run number
		"""

		dwi_run_numbers = {}

		fmap_run_numbers = {}

		for scan in all_nii_files:

			no_path_name = os.path.basename(scan)

			pattern = r'run-(.*?)_'

			run_number = self.match(pattern, no_path_name)

			if run_number:
				if 'dwi.nii' in no_path_name:
					dwi_run_numbers[scan] = run_number
				elif 'epi.nii' in no_path_name:
					fmap_run_numbers[scan] = run_number

			return dwi_run_numbers, fmap_run_numbers

	def match(self, pattern, text):
		"""
		Check if a particular pattern exists inside given text using regex
		"""

		match = re.search(pattern, text)

		if match:
			result = match.group(1)
			return result

		else:
			return None

	def delete_bval_bvec(self):
		cwd = os.getcwd()
		logging.info('cleaning fmap bids directory')
		fmap_dir = os.path.join(f'{self._bids}/sub-{self._sub}/ses-{self._ses}/fmap')
		os.chdir(fmap_dir)
		for file in os.listdir():
			if file.endswith('.bval') or file.endswith('.bvec'):
				os.remove(file)
		os.chdir(cwd)

	def bind_environmentals(self):
	
		bind = [self._outdir, self._tempdir, self._fs_license]
		
		os.environ["SINGULARITY_BIND"] = ','.join(bind)

	# create qsiprep command to be executed

	def build(self):
		self.bind_environmentals()
		self.check_container_path()
		self.create_eddy_params()
		self.create_nipype()
		self.check_output_resolution()
		self.check_fieldmaps()
		self.delete_bval_bvec()
		try:
			qsiprep_command = yaml.safe_load(open(self._qsiprep_config))
		except yaml.parser.ParserError:
			print("There's an issue with the prequal config file.\nMake sure it is a .yaml file with proper formatting.")
			sys.exit()
		qsiprep_options = qsiprep_command['qsiprep']['shell']
		
		self._command = [
			'selfie',
			'--lock',
			'--output-file', self._prov,
			'singularity',
			'run',
			'--nv',
			self._qsiprep_sif,			
			self._bids,
			self._outdir,
			'participant',
			'--output-resolution',
			self._output_resolution,
			'--eddy-config',
			f'{self._bids}/eddy_params_s2v_mbs.json',
			'--fs-license-file',
			self._fs_license,
			'-w',
			f'{self._tempdir}/qsiprep_{date}/{self._ses}'
		]

		for item in qsiprep_options:
			self._command.append(item)

		if self._no_gpu:
			logdir = self.logdir()
			logfile = os.path.join(logdir, 'dwiqc-qsiprep.log')
			self.job = Job(
				name='dwiqc-qsiprep',
				time='4000',
				memory='60G',
				cpus=2,
				nodes=1,
				command=self._command,
				output=logfile,
				error=logfile
			)

		else:
			logdir = self.logdir()
			logfile = os.path.join(logdir, 'dwiqc-qsiprep.log')
			self.job = Job(
				name='dwiqc-qsiprep',
				time='4000',
				memory='60G',
				gpus=1,
				nodes=1,
				command=self._command,
				output=logfile,
				error=logfile
			)

class DWISpecError(Exception):
	pass


