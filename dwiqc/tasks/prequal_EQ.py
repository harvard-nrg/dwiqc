import shutil
import os
import time
import sys
sys.path.insert(0, os.path.join(os.environ['MODULESHOME'], "init"))
from env_modules_python import module
import dwiqc.tasks as tasks
import logging
import subprocess
import json
from executors.models import Job



class Task(tasks.BaseTask):
	def __init__(self, sub, ses, run, bids, outdir, parent=None, tempdir=None, pipenv=None):
		self._sub = sub
		self._ses = ses
		self._run = run
		self._bids = bids
		super().__init__(outdir, tempdir, pipenv)


	def build(self):

		os.chdir(f"{self._outdir}/EDDY")

		# define log file
		logging.basicConfig(filename=f"{self._outdir}/logs/dwiqc-prequal.log", encoding='utf-8', level=logging.DEBUG)

		logging.info('Loading FSL module: fsl/6.0.6.4-centos7_x64-ncf')

		#load the fsl module
		module('load','fsl/6.0.6.4-centos7_x64-ncf')

		logging.info('module succesfully loaded!')

		# copy the necessary file to EDDY directory

		logging.info('copying dwmri.nii.gz file to EDDY dir')
		if os.path.isfile(f'{self._outdir}/PREPROCESSED/dwmri.nii.gz'):
			shutil.copy(f'{self._outdir}/PREPROCESSED/dwmri.nii.gz', f'{self._outdir}/EDDY/{self._sub}_{self._ses}.nii.gz')

		else:
			logging.error('PREPROCESSED/dwmri.nii.gz doesn\'t exist, which likely means prequal failed. exiting.')
			sys.exit()

		# grab name of slspec file
		logging.info(f'grabbing slspec file from {self._outdir}')
		try:
			for file in os.listdir(self._outdir):
				if 'slspec' in file and file.endswith('.txt'):
					spec_file = file
		except FileNotFoundError:
			logging.error('spec file not found. exiting.')
			sys.exit()


		# rename all the eddy_results files to be {self._sub}_{self._ses}

		for file in os.listdir():
			if file.startswith("eddy_results"):
				new_name = file.replace("eddy_results", f"{self._sub}_{self._ses}")
				os.rename(file, new_name)



		eddy_quad = f"""singularity exec \
		-B /n/home_fasse/dasay/eddy_quad_mofication/quad_mot.py:/APPS/fsl/fslpython/envs/fslpython/lib/python3.7/site-packages/eddy_qc/QUAD/quad_mot.py \
		/n/sw/ncf/containers/masilab/prequal/1.0.8/prequal.sif \
		/APPS/fsl/bin/eddy_quad \
		{self._sub}_{self._ses} \
		-idx index.txt \
		-par acqparams.txt \
		--mask=eddy_mask.nii.gz \
		--bvals={self._outdir}/PREPROCESSED/dwmri.bval \
		--bvecs={self._outdir}/PREPROCESSED/dwmri.bvec \
		--field {self._outdir}/TOPUP/topup_field.nii.gz \
		-s {self._outdir}/{spec_file} \
		-v"""


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

		eddy_results_dir = f'{self._outdir}/EDDY/{self._sub}_{self._ses}.qc'

		self.parse_json(eddy_results_dir)

		self.extract_b0_vol()


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

	def extract_b0_vol(self):
		os.chdir(f"{self._outdir}/PREPROCESSED")
		extract_command = "fslselectvols -i dwmri.nii.gz -o b0_volume --vols=0"
		proc1 = subprocess.Popen(extract_command, shell=True, stdout=subprocess.PIPE)
		proc1.communicate()



