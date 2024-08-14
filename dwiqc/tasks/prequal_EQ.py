import shutil
import os
import time
import sys
import dwiqc.tasks as tasks
import logging
import subprocess
import json
from pathlib import Path
from executors.models import Job

logger = logging.getLogger()

class Task(tasks.BaseTask):
	def __init__(self, sub, ses, run, bids, outdir, slurm_job_id, container_dir=None, parent=None, tempdir=None, pipenv=None):
		self._sub = sub
		self._ses = ses
		self._run = run
		self._bids = bids
		self._slurm_job_id=slurm_job_id
		self._container_dir = container_dir
		super().__init__(outdir, tempdir, pipenv)


	def build(self):

		self.bind_environmentals()


		if self._container_dir:
			try:
				self._fsl_sif = f'{self._container_dir}/fsl_6.0.4.sif'
			except FileNotFoundError:
				logger.error(f'{self._container_dir}/fsl_6.0.4.sif does not exist. Verify the path and file name.')
				sys.exit(1)

		else:

			home_dir = os.path.expanduser("~")

			self._fsl_sif = os.path.join(home_dir, '.config/dwiqc/containers/fsl_6.0.4.sif')

		os.chdir(f"{self._outdir}/EDDY")

		# define log file
		logging.basicConfig(filename=f"{self._outdir}/logs/dwiqc-prequal.log", encoding='utf-8', level=logging.DEBUG)

		# grab name of slspec file
		logging.info(f'grabbing slspec file from {self._outdir}')
		try:
			for file in os.listdir(self._outdir):
				if 'slspec' in file and file.endswith('.txt'):
					self._spec_file = file
		except FileNotFoundError:
			logging.error('spec file not found. exiting.')
			sys.exit()


		self.check_split_preproc()

	def check_split_preproc(self):
		# copy the necessary file to EDDY directory

		all_files = [file for file in os.listdir(f'{self._outdir}/PREPROCESSED')]
		if 'dwmri.nii.gz' in all_files:
			logging.info('only one preproc file found, running eddy quad')
			self.run_eddy_quad('dwmri.nii.gz','dwmri.bval', 'dwmri.bvec')
			self.extract_b0_vol_regular()

		else:
			logging.error(f'{self._outdir}/PREPROCESSED/dwmri.nii.gz file not found. check prequal log dir for errors.')
			sys.exit(1)
			'''
			logging.warning('PREPROCESSED/dwmri.nii.gz doesn\'t exist, checking for split output')
			main_scans = [file for file in all_files if '_dwi_' in file and file.endswith('preproc.nii.gz')]
			logger.info(f'found these main diffusion scans {main_scans}')
			self.split_output_processing(main_scans)
			'''

	def split_output_processing(self, scans):
		if scans:
			logger.info('split scans found')

			for idx,scan in enumerate(scans, 1):
				self.edit_index_file()
				self.run_eddy_quad(scan, scan.replace('.nii.gz', '.bval'), scan.replace('.nii.gz', '.bvec'), idx)
				self.extract_b0_vol_split(scans, idx)

		else:
			logger.error('split scan output not found, exiting')
			sys.exit()

	def edit_index_file(self):
		index_file = Path(f'{self._outdir}/EDDY/index.txt')
		with open(index_file, 'r') as file:
		    content = file.read()

		integers = content.split()
		filtered_integers = [i for i in integers if i == '1']
		result_content = ' '.join(filtered_integers)

		with open(index_file, 'w') as file:
			file.write(result_content)

	def rename_eddy_files(self):
		# rename all the eddy_results files to be {self._sub}_{self._ses}_{run}

		os.chdir(f"{self._outdir}/EDDY")

		for file in os.listdir():
			if file.startswith("eddy_results"):
				new_name = file.replace("eddy_results", f"{self._sub}_{self._ses}")
				os.rename(file, new_name)
			elif file == 'dwmri.nii.gz':
				new_name = f"{self._sub}_{self._ses}.nii.gz"
				os.rename(file, new_name)
			elif file.endswith('_preproc.nii.gz'):
				os.rename(file, f"{self._sub}_{self._ses}.nii.gz")

	def copy_nii(self, nii):
		shutil.copy(f'{self._outdir}/PREPROCESSED/{nii}', f'{self._outdir}/EDDY/{self._sub}_{self._ses}.nii.gz')


	def run_eddy_quad(self, nii, bval, bvec, run=1):

		self.copy_nii(nii)

		self.rename_eddy_files()

		eddy_quad = f"""singularity exec \
		--pwd {self._outdir}/EDDY \
		{self._fsl_sif} \
		/APPS/fsl/bin/eddy_quad \
		{self._sub}_{self._ses} \
		-idx index.txt \
		-par acqparams.txt \
		--mask=eddy_mask.nii.gz \
		--bvals={self._outdir}/PREPROCESSED/{bval} \
		--bvecs={self._outdir}/PREPROCESSED/{bvec} \
		--field {self._outdir}/TOPUP/topup_field.nii.gz \
		-s {self._outdir}/{self._spec_file} \
		-v"""

		logger.info(f'{json.dumps(eddy_quad, indent=2)}')

		if os.path.isdir(f'{self._sub}_{self._ses}.qc'):
			logging.warning('Output directory already exists. Removing and trying again.')
			shutil.rmtree(f'{self._sub}_{self._ses}.qc')

		logging.info('Running eddy_quad...')
		proc1 = subprocess.Popen(eddy_quad, shell=True, stdout=subprocess.PIPE)
		proc1.communicate()
		code = proc1.returncode

		if code == 0:
			logging.info('eddy quad ran without errors!')
		else:
			logging.error('eddy quad threw an error. exiting.')
			sys.exit()

		#os.remove(f'{self._outdir}/EDDY/{nii}')

		eddy_results_dir = f'{self._outdir}/EDDY/{self._sub}_{self._ses}.qc'

		self.parse_json(eddy_results_dir)
			


	def parse_json(self, eddy_dir):
		logging.info('parsing qc.json file.')
		with open(f'{eddy_dir}/qc.json', 'r') as file:
			data = json.load(file)

			shells = []

			for shell in data['data_unique_bvals']:
				shells.append(shell)

		## grab the needed metrics

		#	****** Volume to Volume Motion ******

			metrics_dict = {}

			# average absolute motion

			metrics_dict["Average_abs_motion_mm"] = data['qc_mot_abs']

			# average relative motion

			metrics_dict["Average_rel_motion_mm"] = data['qc_mot_rel']

			# average x translation		

			metrics_dict["Average_x_translation_mm"] = round(data['qc_params_avg'][0], 2)

			# average y translation		

			metrics_dict["Average_y_translation_mm"] = round(data['qc_params_avg'][1], 2)

			# average z translation		

			metrics_dict["Average_z_translation_mm"] = round(data['qc_params_avg'][2], 2)

			#	****** SNR/CNR ******		

			# average snr (b=0)		

			metrics_dict["Average_SNR_b0"] = round(data['qc_cnr_avg'][0], 2)

			# grab all shell values from qc.json file

			for idx, shell in enumerate(shells, start=1):
				metrics_dict[f"Average_CNR_b{shell}"] = round(data['qc_cnr_avg'][idx], 2)





		## Write out all these values to json file


		with open('eddy_metrics.json', 'w') as outfile:
			json.dump(metrics_dict, outfile, indent=1)

		logging.info('successfully parsed json and wrote out results to eddy_metrics.json')

	def extract_b0_vol_regular(self):
		dwmri = f'{self._outdir}/PREPROCESSED/dwmri.nii.gz'
		logger.info(f'checking for input file "{dwmri}"')
		if not os.path.exists(dwmri):
			raise FileNotFoundError(dwmri)
		logger.info(f'found input file "{dwmri}"')
		bindings = os.environ.get('SINGULARITY_BIND', None)
		logger.info(f'SINGULARITY_BIND environment variable is set to "{bindings}"')
		preproc_dir = f'{self._outdir}/PREPROCESSED'
		cmd = [
			'singularity',
			'exec',
			'--pwd', preproc_dir,
			self._fsl_sif,
			'/APPS/fsl/bin/fslselectvols',
			'-i', 'dwmri.nii.gz',
			'-o', 'b0_volume',
			'--vols=0'
		]
		cmdline = subprocess.list2cmdline(cmd)
		logger.info(f'running {cmdline}')
		proc = subprocess.Popen(cmdline, shell=True, stdout=subprocess.PIPE)
		proc.communicate()
		if proc.returncode > 0:
			logger.critical(f'fslselectvols command failed')
			raise subprocess.CalledProcessError(returncode=proc.returncode, cmd=cmdline)
		logging.info(f'fslselectvols exited with returncode={proc.returncode}')
		b0vol = os.path.join(preproc_dir, 'b0_volume.nii.gz')
		logging.info(f'checking for output file "{b0vol}"')
		if not os.path.exists(b0vol):
			raise FileNotFoundError(b0vol)
		logger.info(f'found output file "{b0vol}"')

	def extract_b0_vol_split(self, scans, run):
		bindings = os.environ.get('SINGULARITY_BIND', None)
		logger.info(f'SINGULARITY_BIND environment variable is set to "{bindings}"')
		preproc_dir = f'{self._outdir}/PREPROCESSED'
		for scan in scans:
			cmd = [
				'singularity',
				'exec',
				'--pwd', preproc_dir,
				self._fsl_sif,
				'/APPS/fsl/bin/fslselectvols',
				'-i', scan,
				'-o', f'b0_volume',
				'--vols=0'
			]
			cmdline = subprocess.list2cmdline(cmd)
			logger.info(f'running {cmdline}')
			proc = subprocess.Popen(cmdline, shell=True, stdout=subprocess.PIPE)
			proc.communicate()
			if proc.returncode > 0:
				logger.critical(f'fslselectvols command failed')
				raise subprocess.CalledProcessError(returncode=proc.returncode, cmd=cmdline)
			logging.info(f'fslselectvols exited with returncode={proc.returncode}')
			b0vol = os.path.join(preproc_dir, f'b0_volume.nii.gz')
			logging.info(f'checking for output file "{b0vol}"')
			if not os.path.exists(b0vol):
				raise FileNotFoundError(b0vol)
			logger.info(f'found output file "{b0vol}"')

	def bind_environmentals(self):
	
		bind = [self._bids, self._tempdir]
		
		os.environ["SINGULARITY_BIND"] = ','.join(bind)



