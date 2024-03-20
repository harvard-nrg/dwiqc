#### load necessary libraries
import tempfile
import subprocess
import yaml
import os
import logging
from bids import BIDSLayout
import sys
import json
import dwiqc.tasks as tasks
import shutil
from executors.models import Job
import dwiqc.config as config
import numpy as np
from pprint import pprint
import re
import nibabel as nib
from datetime import datetime


logger = logging.getLogger(__name__)


# pull in some parameters from the BaseTask class in the __init__.py directory

class Task(tasks.BaseTask):
	def __init__(self, sub, ses, run, bids, outdir, prequal_config, fs_license, container_dir=None, no_gpu=False, tempdir=None, pipenv=None):
		self._sub = sub
		self._ses = ses
		self._run = run
		self._bids = bids
		self._prequal_config = prequal_config
		self._fs_license = fs_license
		self._container_dir = container_dir
		self._no_gpu = no_gpu
		self._layout = BIDSLayout(bids)
		self._date = datetime.today().strftime('%Y-%m-%d')
		super().__init__(outdir, tempdir, pipenv)


	# create an INPUTS dir next to the OUTPUTS dir
	def copy_inputs(self, inputs_dir):
		"""
		try:
			os.makedirs(inputs_dir)
		except FileExistsError:
			pass
		"""

		os.makedirs(inputs_dir, exist_ok=True)
		
		all_files = self._layout.get(subject=self._sub, session=self._ses, return_type='filename') # get a list of all of the subject's files

		# copy the all the subject's files into the INPUTS directory
		for file in all_files:
			basename = os.path.basename(file)
			dest = os.path.join(inputs_dir, basename)
			shutil.copy(file, dest)

		self.create_bfiles(inputs_dir)
		

	# the fieldmap data needs accompanying 'dummy' bval and bvec files that consist of 0's
	def create_bfiles(self, inputs_dir):
		# get a list of all the fmap files that end with .json (this it's helpful to have a file with just one extension)

		fmap_files = self._layout.get(subject=self._sub, session=self._ses, suffix='epi', extension='.nii.gz', return_type='filename')

		if not fmap_files:
			self._layout.get(subject=self._sub, session=self._ses, suffix='epi', extension='.nii', return_type='filename')

		# get the basename of the file and then remove the extension
		for fmap in fmap_files:

			basename = os.path.basename(fmap)

			no_ext = basename.split('.', 1)[0]

			# get the number of volumes in the data file
			try:
				num_vols = nib.load(fmap).shape[3]
			except IndexError:
				num_vols = 1

			# create a .bval file same number of rows of 0 as there are volumes

			with open(f'{inputs_dir}/{no_ext}.bval', 'w') as bval:
				rows_written = 0
				while rows_written < num_vols:
					if rows_written == 0:
						bval.write('0')
					elif rows_written == num_vols - 1:
						bval.write(' 0\n')
					else:
						bval.write(' 0')
					rows_written += 1

			# create .bvec file with 3 row 0's equal to the number of volumes

			with open(f'{inputs_dir}/{no_ext}.bvec', 'w') as bvec:
				row_to_write = ''
				# write the same number of 0's as there are volumes
				for _ in range(num_vols):
					row_to_write += '0 '
				# remove any trailing whitespace
				row_to_write = row_to_write.strip()

				# add three rows to bvec file
				for _ in range(3):		
					bvec.write(f'{row_to_write}\n')

		self.create_spec(inputs_dir)
		


	# this method serves to create the accompanying spec file for prequal 
	# the contents of the file depends on the SeriesDescription stored in the metadata

	def create_spec(self, inputs_dir):
		dwi_file = self._layout.get(subject=self._sub, session=self._ses, run=self._run, suffix='dwi', extension='.nii.gz')
		#dwi_file = layout.get()[10]
		if len(dwi_file) > 1:
			logger.warning('PREQUAL_WARNING: More than one main DWI scan detected. Ensure scans were acquired using the same parameters.')
		if not dwi_file:
			raise DWISpecError(f'No dwi scan found for subject {self._sub} session {self._ses} run {self._run}')
		else:
			dwi_file = dwi_file.pop()

		json_file = self._layout.get(subject=self._sub, session=self._ses, run=self._run, suffix='dwi', extension='.json', return_type='filename').pop()

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
			self.even_slices(json_file, inputs_dir)

		else:
			self.odd_slices(json_file, inputs_dir, num_slices)

		# call method that creates the necessary csv file for prequal
		self.create_csv(inputs_dir, dwi_file)

		# call method that adds an "IntendedFor" key-value pair to json file (for fieldmaps)
		#self.add_intended_for()

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

		self._spec = "even_slices_slspec.txt"

		with open(spec_file, 'w') as fp:
			for sublist in slspec:
				fp.write(' '.join(str(item) for item in sublist))
				fp.write('\n')

		os.makedirs(self._outdir)
		shutil.copy(f"{inputs_dir}/even_slices_slspec.txt", self._outdir)
		#self._spec = "even"


	# helper method that generates slspec file for an acquisition with an odd number of slices

	def odd_slices(self, json_file, inputs_dir, num_slices):
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

		self._spec = "odd_slices_slspec.txt"

		np.savetxt(spec_file, all_cols, fmt=['%d', '%d', '%d'])

		os.makedirs(self._outdir)
		shutil.copy(f"{inputs_dir}/odd_slices_slspec.txt", self._outdir)
		#self._spec = "odd"

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

		# create dictionary of all the scans (dwi or epi) matched with their primary phase encoding direction
		phase_encode_pairs = {}

		# get all json files

		filenames = self._layout.get(subject=self._sub, session=self._ses, extension='.json', return_type='filename')

		remove_suffix = 'T1w.json'

		filtered_filenames = [file for file in filenames if not file.endswith(remove_suffix)] # create new list w/o T1w json file

		# get scan and phase encode direction pairs

		for file in filtered_filenames:
			phase_encode_pairs[file] = self.get_phase_encode(file)

		# remove the preceding path information and extension from each file name key to prepare for writing into csv file

		phase_encode_pairs_no_ext = {os.path.splitext(os.path.basename(key))[0]: value for key, value in phase_encode_pairs.items()}

		# iterate through each file, and create a line to write to the csv file based on metadata

		lines_to_write = []

		# find out what the primary phase encode direction is

		primary_phase_dir = self.get_primary_phase_dir(filtered_filenames)

		for key, value in phase_encode_pairs_no_ext.items():
			if value == primary_phase_dir:
				new_line = f'{key},+,{readout_time}'
			else:
				new_line = f'{key},-,{readout_time}'

			lines_to_write.append(new_line)

		# write each of the created lines into a csv file

		with open(f'{inputs_dir}/dtiQA_config.csv', 'w') as csv:
			for line in lines_to_write:
				csv.write(f'{line}\n')


	def get_phase_encode(self, json_file):

		with open(json_file, 'r') as foo:
			data = json.load(foo)

		phase_dir = data['PhaseEncodingDirection']

		return phase_dir

	def get_primary_phase_dir(self, file_list):

		# get all the phase encode directions as recorded in the json file of each 'main' dwi scan

		all_main_dwi_scan_dirs = []
		for file in file_list:
			if file.endswith('dwi.json'):
				phase_dir = self.get_phase_encode(file)
				all_main_dwi_scan_dirs.append(phase_dir)

		# verify that all values are the same. If they aren't the program will exit due to differing parameters
		first_element = all_main_dwi_scan_dirs[0]

		all_same_direction = all(element == first_element for element in all_main_dwi_scan_dirs)

		if not all_same_direction:
			raise DWISpecError('The primary phase encode direction differs across scans with the dwi suffix.\nVerify that scans were acquired with the same parameters. Exiting')
		else:
			return first_element

# this method will add an "IntendedFor" key-value pair to the fieldmap scans

	def add_intended_for(self):

		# need to find a way to get the fmap and dwi files matched up. Should be flexible enough to work for dedicate fieldmaps,
		# revpol scans, or single or multiple man scans

		# get the number of "main" and "fmap" scans. Call different methods based on those numbers

		dwi_files = self._layout.get(subject=self._sub, session=self._ses, suffix='dwi', extension='.nii.gz', return_type='filename')

		fmap_files = self._layout.get(subject=self._sub, session=self._ses, suffix='epi', extension='.nii.gz', return_type='filename')

		all_nii_files = dwi_files + fmap_files

		if len(dwi_files)*2 != len(fmap_files):

			self.uneven_main_and_fmaps(all_nii_files)

		else:

			self.even_main_and_fmaps(all_nii_files)

	def even_main_and_fmaps(self, all_nii_files):
		## try matching by acq group first

		dwi_acqusition_groups, fmap_acquisition_groups = self.acquistion_group_match(all_nii_files)

		if dwi_acqusition_groups and fmap_acquisition_groups:
			for fmap_key, fmap_value in fmap_acquisition_groups.items():
				for dwi_key, dwi_value in dwi_acqusition_groups.items():
					if fmap_value == dwi_value:
						try:
							json_file = fmap_key.replace('.nii.gz', '.json')
						except FileNotFoundError:
							json_file = fmap_key.replace('.nii', '.json')
						new_dwi_key = os.path.basename(dwi_key)
						self.insert_json_value('IntendedFor', f'ses-{self._ses}/dwi/{new_dwi_key}', json_file)

		else:
			logger.warning('No acquisition group specified. Searching based on run number.')

		## if there's no acquisition data, search by run number

			dwi_run_numbers, fmap_run_numbers = self.run_number_match(all_nii_files)

			if not dwi_run_numbers or not fmap_run_numbers:
				raise DWISpecError('No run numbers could be identified. Please add to BIDS specification for fieldmap and main dwi scan matching.')

			else:

				for fmap_key, fmap_value in fmap_run_numbers.items():
					for dwi_key, dwi_value in dwi_run_numbers.items():
						if fmap_value == dwi_value:
							try:
								json_file = fmap_key.replace('.nii.gz', '.json')
							except FileNotFoundError:
								json_file = fmap_key.replace('.nii', '.json')
							new_dwi_key = os.path.basename(dwi_key)
							self.insert_json_value('IntendedFor', f'ses-{self._ses}/dwi/{new_dwi_key}', json_file)



	def uneven_main_and_fmaps(self, all_nii_files):
		"""
		If there are not an even number of fmaps and main scans, add "IntendedFor" field to the fmap scans for all applicable main scans
		"""
		dwi_acqusition_groups, fmap_acquisition_groups = self.acquistion_group_match(all_nii_files)

		if not dwi_acqusition_groups or not fmap_acquisition_groups:
			raise DWISpecError('Uneven number of fieldmaps and main scans and no acqusition group specified. Please add to BIDS file names and retry. Exiting')

		## interate through all the fmap and dwi key-value pairs. if the values equal each other, insert into the fmap json file
		# and IntendedFor field that points to the matched dwi scan

		for fmap_key, fmap_value in fmap_acquisition_groups.items():
			for dwi_key, dwi_value in dwi_acqusition_groups.items():
				if fmap_value == dwi_value:
					try:
						json_file = fmap_key.replace('.nii.gz', '.json')
					except FileNotFoundError:
						json_file = fmap_key.replace('.nii', '.json')
					new_dwi_key = os.path.basename(dwi_key)
					self.insert_json_value('IntendedFor', f'ses-{self._ses}/dwi/{new_dwi_key}', json_file)



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
	def bind_environmentals(self):
	
		bind = [self._outdir, self._tempdir, self._fs_license]
		
		os.environ["SINGULARITY_BIND"] = ','.join(bind)


	# build the prequal sbatch command and create job

	def build(self):
		self.bind_environmentals()
		self.add_intended_for()
		self._tempdir = tempfile.gettempdir()
		inputs_dir = f'{self._tempdir}/PREQUAL_INPUTS_{self._date}/ses-{self._ses}'
		self.copy_inputs(inputs_dir)
		mporder = self.calc_mporder()
		if self._container_dir:
			try:
				prequal_sif = f'{self._container_dir}/prequal_nrg.sif'
			except FileNotFoundError:
				logger.error(f'{self._container_dir}/prequal_nrg.sif does not exist. Verify the path and file name.')
				sys.exit(1)
		else:
			home_dir = os.path.expanduser("~")
			prequal_sif = os.path.join(home_dir, '.config/dwiqc/containers/prequal_nrg.sif')
		try:
			prequal_command = yaml.safe_load(open(self._prequal_config))
		except yaml.parser.ParserError:
			print("There's an issue with the prequal config file.\nMake sure it is a .yaml file with proper formatting.")
			sys.exit(1)
		prequal_options = prequal_command['prequal']['shell']
		if self._no_gpu:
			if '--eddy_cuda' in prequal_options:
				prequal_options.remove('--eddy_cuda')
			if '10.2' in prequal_options:
				prequal_options.remove('10.2')
		num_opts = len(prequal_options)
		if self._nonzero_shells == False:
			self._command = [
				'selfie',
				'--lock',
				'--output-file', self._prov,
				'singularity',
				'run',
				'-e',
				'--env', 'PYTHONUNBUFFERED=1',
				'--pwd', self._tempdir,
				'--contain',
				'--nv',
				'-B', f'{inputs_dir}:/INPUTS/',
				'-B', f'{self._outdir}:/OUTPUTS',
				'-B', f'{self._tempdir}:/tmp',
				'-B', f'{self._fs_license}:/APPS/freesurfer/license.txt',
				f'{prequal_sif}',
				'--save_component_pngs',
				'--subject',
				self._sub,
				'--project',
				'Proj',
				'--session',
				self._ses
				]

			for item in prequal_options:
				self._command.append(item)

			eddy_args = f'--extra_eddy_args=--data_is_shelled+--ol_nstd=6+--ol_type=gw+--repol+--estimate_move_by_susceptibility+--cnr_maps+--flm=quadratic+--interp=spline+--resamp=jac+--mporder={mporder}+--niter=5+--nvoxhp=1000+--slspec=/INPUTS/{self._spec}+--slm=linear'
			self._command.append(eddy_args)

		elif self._nonzero_shells == True:
			self._command = [
				'selfie',
				'--lock',
				'--output-file', self._prov,
				'singularity',
				'run',
				'-e',
				'--env', 'PYTHONUNBUFFERED=1',
				'--pwd', self._tempdir,
				'--contain',
				'--nv',
				'-B', f'{inputs_dir}:/INPUTS/',
				'-B', f'{self._outdir}:/OUTPUTS',
				'-B', f'{self._tempdir}:/tmp',
				'-B', f'{self._fs_license}:/APPS/freesurfer/license.txt',
				f'{prequal_sif}',
				'--save_component_pngs',
				'--nonzero_shells',
				'350,650,1350,2000',
				'--subject',
				self._sub,
				'--project',
				'Proj',
				'--session',
				self._ses
				]

			for item in prequal_options:
				self._command.append(item)

			eddy_args = f'--extra_eddy_args=--data_is_shelled+--ol_nstd=6+--ol_type=gw+--repol+--estimate_move_by_susceptibility+--cnr_maps+--flm=quadratic+--interp=spline+--resamp=jac+--mporder={mporder}+--niter=5+--nvoxhp=1000+--slspec=/INPUTS/{self._spec}+--slm=linear'
			self._command.append(eddy_args)

		logdir = self.logdir()
		logfile = os.path.join(logdir, 'dwiqc-prequal.log')
		if self._no_gpu:
			self.job = Job(
				name='dwiqc-prequal',
				time='3000',
				memory='60G',
				cpus=2,
				nodes=1,
				command=self._command,
				output=logfile,
				error=logfile
			)
		else:
			self.job = Job(
				name='dwiqc-prequal',
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