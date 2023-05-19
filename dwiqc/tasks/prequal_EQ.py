
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


old_out = sys.stdout



class Task(tasks.BaseTask):
	def __init__(self, sub, ses, run, bids, outdir, parent=None, tempdir=None, pipenv=None):
		self._sub = sub
		self._ses = ses
		self._run = run
		self._bids = bids
		super().__init__(outdir, tempdir, pipenv)


	def build(self):

		log_file = open("eddy_quad.log", "w")		

		#load the fsl module
		module('load','fsl/6.0.4-centos7_64-ncf')
		#while not os.path.exists(f'{self._outdir}/EDDY'):
		#	time.sleep(120)

		if os.path.isdir(f'{self._outdir}/EDDY'):
			os.chdir(f'{self._outdir}/EDDY')
			log_file = open(f"{self._outdir}/EDDY/eddy_quad.log", "w")	
			sys.stdout = log_file

		# copy the necessary file to EDDY directory

		#while not os.path.exists('../PREPROCESSED/dwmri.nii.gz'):
		#	time.sleep(120)

		if os.path.isfile('../PREPROCESSED/dwmri.nii.gz'):
			shutil.copy('../PREPROCESSED/dwmri.nii.gz', 'eddy_results.nii.gz')

		else:
			print("prequal failed... exiting.")
			sys.exit()

		# grab name of slspec file

		for file in os.listdir(self._outdir):
			if 'slspec' in file and file.endswith('.txt'):
				spec_file = file


		eddy_quad = f"""singularity exec \
		-B /n/home_fasse/dasay/eddy_quad_mofication/quad_mot.py:/APPS/fsl/fslpython/envs/fslpython/lib/python3.7/site-packages/eddy_qc/QUAD/quad_mot.py \
		/n/sw/ncf/containers/masilab/prequal/1.0.8/prequal.sif \
		/APPS/fsl/bin/eddy_quad \
		eddy_results \
		-idx index.txt \
		-par acqparams.txt \
		--mask=eddy_mask.nii.gz \
		--bvals=../PREPROCESSED/dwmri.bval \
		--bvecs=../PREPROCESSED/dwmri.bvec \
		--field ../TOPUP/topup_field.nii.gz \
		-s ../{spec_file} \
		-v"""

		try:
			proc1 = subprocess.Popen(eddy_quad, shell=True, stdout=subprocess.PIPE)
			proc1.communicate()
		except ValueError:
			print('Output directory already exists. Removing and trying again...')
			os.rmdir("eddy_results.qc")
			proc1 = subprocess.Popen(eddy_quad, shell=True, stdout=subprocess.PIPE)
			proc1.communicate()

		eddy_results_dir = f'{self._outdir}/EDDY/eddy_results.qc'

		self.parse_json(eddy_results_dir)

		log_file.close()


	def parse_json(self, eddy_dir):
		with open(f'{eddy_dir}/qc.json', 'r') as file:
			data = json.load(file)

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

			# avg cnr (b=500)		

			metrics_dict["Average_CNR_b500"] = round(data['qc_cnr_avg'][1], 2)

			# avg cnr (b=1000)		

			metrics_dict["Average_CNR_b1000"] = round(data['qc_cnr_avg'][2], 2)

			# avg cnr (b=2000)		

			metrics_dict["Average_CNR_b2000"] = round(data['qc_cnr_avg'][3], 2)

			# avg cnr (b=3000)		

			metrics_dict["Average_CNR_b3000"] = round(data['qc_cnr_avg'][4], 2)




		## Write out all these values to json file


		with open('eddy_metrics.json', 'w') as outfile:
			json.dump(metrics_dict, outfile, indent=1)

