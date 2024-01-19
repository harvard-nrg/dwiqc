import shutil
import os
import sys
import dwiqc.tasks as tasks
import logging
import subprocess
import json
from executors.models import Job


class Task(tasks.BaseTask):
	def __init__(self, sub, ses, run, bids, outdir, container_dir=None, parent=None, tempdir=None, pipenv=None):
		self._sub = sub
		self._ses = ses
		self._run = run
		self._bids = bids
		self._container_dir = container_dir
		super().__init__(outdir, tempdir, pipenv)


	def build(self):

		self.bind_environmentals()


		if self._container_dir:
			try:
				self._fsl_sif = f'{self._container_dir}/fsl_6.0.4.sif'
			except FileNotFoundError:
				logging.error(f'{self._container_dir}/fsl_6.0.4.sif does not exist. Verify the path and file name.')
				sys.exit(1)

		else:

			home_dir = os.path.expanduser("~")

			self._fsl_sif = os.path.join(home_dir, '.config/dwiqc/containers/fsl_6.0.4.sif')


		# Define working directory for the subject

		qsiprep_work_dir = f'{self._tempdir}/qsiprep_wf/single_subject_{self._sub}_wf/dwi_preproc_ses_{self._ses}_acq_A_run_1_wf/hmc_sdc_wf'

		# Define eddy quad destination directory

		eddy_quad_dir = f'{self._outdir}/qsiprep/EDDY'

		os.makedirs(eddy_quad_dir, exist_ok=True)

		logging.info('copying qsiprep output files for eddy quad')

		# copy over all files from eddy directory

		for file in os.listdir(f'{qsiprep_work_dir}/eddy'):
			if file.startswith('eddy'):
				shutil.copy(f'{qsiprep_work_dir}/eddy/{file}', eddy_quad_dir)

		# copy all files that end with txt and start with eddy in gather_inputs

		for file in os.listdir(f'{qsiprep_work_dir}/gather_inputs'):
			if file.endswith('.txt') and file.startswith('eddy'):
				shutil.copy(f'{qsiprep_work_dir}/gather_inputs/{file}', eddy_quad_dir)

		# copy topup_imain_corrected_avg_trans_mask_trans.nii.gz from pre_eddy_b0_ref_wf/synthstrip_wf/mask_to_original_grid

		self.copy_file(f'{qsiprep_work_dir}/pre_eddy_b0_ref_wf/synthstrip_wf/mask_to_original_grid/topup_imain_corrected_avg_trans_mask_trans.nii.gz', eddy_quad_dir)

		# copy  fieldmap_HZ.nii.gz from topup

		self.copy_file(f'{qsiprep_work_dir}/topup/fieldmap_HZ.nii.gz', eddy_quad_dir)

		# copy and rename bval file from qsiprep output dir

		self.copy_file(f'{self._outdir}/qsiprep/sub-{self._sub}/ses-{self._ses}/dwi/sub-{self._sub}_ses-{self._ses}_acq-A_run-1_space-T1w_desc-preproc_dwi.bval', eddy_quad_dir)

		self.rename_file(f'{eddy_quad_dir}/sub-{self._sub}_ses-{self._ses}_acq-A_run-1_space-T1w_desc-preproc_dwi.bval', f'{eddy_quad_dir}/{self._sub}.bval')

		# copy slspec file from bids dir

		for file in os.listdir(self._bids):
			if 'slspec' in file and file.endswith('.txt'):
				self._spec_file = f'{self._bids}/{file}'

		# rename all the files in eddy_quad_dir that start with "eddy_results"

		os.chdir(eddy_quad_dir)

		for file in os.listdir():
			if file.startswith("eddy_corrected"):
				new_name = file.replace("eddy_corrected", f"{self._sub}_{self._ses}")
				self.rename_file(file, new_name)

		# run eddy_quad on output

		self.run_eddy_quad(eddy_quad_dir)

		eddy_results_dir = f'{eddy_quad_dir}/{self._sub}_{self._ses}.qc'

		self.parse_json(eddy_results_dir)


	def bind_environmentals(self):
	
		bind = [self._outdir, self._tempdir]
		
		os.environ["SINGULARITY_BIND"] = ','.join(bind)

	def copy_file(self, source, destination):
		shutil.copy(source, destination)

	def rename_file(self, old_name, new_name):
		os.rename(old_name, new_name)

	def run_eddy_quad(self, eddy_quad_dir):
		command = f"""singularity exec \
		--pwd {eddy_quad_dir} \
		{self._fsl_sif} \
		/APPS/fsl/bin/eddy_quad \
		{self._sub}_{self._ses} \
		-idx eddy_index.txt \
		-par eddy_acqp.txt \
		--mask=topup_imain_corrected_avg_trans_mask_trans.nii.gz \
		--bvals={self._sub}.bval \
		--bvecs={self._sub}_{self._ses}.eddy_rotated_bvecs \
		--field fieldmap_HZ.nii.gz \
		-s {self._spec_file} \
		-v
		"""

		if os.path.isdir(f'{self._sub}_{self._ses}.qc'):
			logging.warning('Output directory already exists. Removing and trying again.')
			shutil.rmtree(f'{self._sub}_{self._ses}.qc')

		logging.info('Running eddy_quad...')
		proc1 = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
		proc1.communicate()
		code = proc1.returncode

		if code == 0:
			logging.info('eddy quad ran without errors!')
		else:
			logging.error('eddy quad threw an error. exiting.')
			sys.exit()

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






