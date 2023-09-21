
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

home_dir = os.path.expanduser("~")
qsiprep_sif = os.path.join(home_dir, '.config/dwiqc/containers/qsiprep.sif')


logger = logging.getLogger(__name__)


class Task(tasks.BaseTask):
	def __init__(self, sub, ses, run, bids, outdir, qsiprep_config, fs_license, custom_eddy=False, no_gpu=False, output_resolution=None, tempdir=None, pipenv=None):
		self._sub = sub
		self._ses = ses
		self._run = run
		self._bids = bids
		self._qsiprep_config = qsiprep_config
		self._fs_license = fs_license
		self._custom_eddy = custom_eddy
		self._no_gpu = no_gpu
		self._layout = BIDSLayout(bids)
		self._output_resolution = output_resolution
		super().__init__(outdir, tempdir, pipenv)



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
			t1_file = self._layout.get(subject=self._sub, session=self._ses, run=self._run, suffix='T1w', extension='.nii.gz', return_type='filename').pop()

			self._output_resolution = str(nib.load(t1_file).header['pixdim'][1])


	# this method creates the nipype config file necessary for qsiprep. This file ensures that intermediate files
	# don't get deleted for subsequent run of eddy_quad	

	def create_nipype(self):
		nipype = """[logging]
		
		[execution]
		remove_unnecessary_outputs = false
		parameterize_dirs = false

		[monitoring]"""

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
			"args": "--ol_nstd=5 --ol_type=gw"
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

		if len(dwi_files) != len(fmap_files):

			self.uneven_main_and_fmaps(all_nii_files)

		else:

			self.even_main_and_fmaps(all_nii_files)


	def extract_vols(self):
		pass

	# create qsiprep command to be executed

	def build(self):
		self.create_eddy_params()
		self.create_nipype()
		self.check_output_resolution()
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
			qsiprep_sif,			
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
			self._tempdir
		]

		for item in qsiprep_options:
			self._command.append(item)

		if self._no_gpu:
			logdir = self.logdir()
			logfile = os.path.join(logdir, 'dwiqc-qsiprep.log')
			self.job = Job(
				name='dwiqc-qsiprep',
				time='3000',
				memory='40G',
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
				time='3000',
				memory='40G',
				gpus=1,
				nodes=1,
				command=self._command,
				output=logfile,
				error=logfile
			)




