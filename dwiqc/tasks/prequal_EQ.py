
import PyPDF2
import shutil
import os
import time
import sys
sys.path.insert(0, os.path.join(os.environ['MODULESHOME'], "init"))
from env_modules_python import module
sys.path.insert(0, '/n/home_fasse/dasay/dwiqc/dwiqc/tasks')
import __init__ as tasks
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

		proc1 = subprocess.Popen(eddy_quad, shell=True, stdout=subprocess.PIPE)

		try:
			proc1.communicate()
		except ValueError:
			print('Output directory already exists. Removing and trying again...')
			os.rmdir("eddy_results.qc")
			proc1.communicate()

		eddy_results_dir = f'{self._outdir}/EDDY/eddy_results.qc'

		self.parse_json(eddy_results_dir)

		log_file.close()


	def parse_json(self, eddy_dir):
		with open(f'{eddy_dir}/qc.json', 'r') as file:
			data = json.load(file)

				## grab the needed metrics

		#	****** Volume to Volume Motion ******

			metrics_list = []

			# average absolute motion

			avg_abs_motion = {"Average abs. motion (mm)": data['qc_mot_abs']}
			metrics_list.append(avg_abs_motion)

			# average relative motion

			avg_rel_motion = {"Average rel. motion (mm)": data['qc_mot_rel']}
			metrics_list.append(avg_rel_motion)		

			# average x translation		

			avg_x_translation = {"Average x translation (mm)": round(data['qc_params_avg'][0], 2)}
			metrics_list.append(avg_x_translation)		

			# average y translation		

			avg_y_translation = {"Average y translation (mm)": round(data['qc_params_avg'][1], 2)}
			metrics_list.append(avg_y_translation)		

			# average z translation		

			avg_z_translation = {"Average z translation (mm)": round(data['qc_params_avg'][2], 2)}
			metrics_list.append(avg_z_translation)		

			#	****** SNR/CNR ******		

			# average snr (b=0)		

			avg_snr_b0 = {"Average SNR (b=0)": round(data['qc_cnr_avg'][0], 2)}
			metrics_list.append(avg_snr_b0)		

			# avg cnr (b=500)		

			avg_cnr_b500 = {"Average CNR (b=500)": round(data['qc_cnr_avg'][1], 2)}
			metrics_list.append(avg_cnr_b500)		

			# avg cnr (b=1000)		

			avg_cnr_b1000 = {"Average CNR (b=1000)": round(data['qc_cnr_avg'][2], 2)}
			metrics_list.append(avg_cnr_b1000)		

			# avg cnr (b=2000)		

			avg_cnr_b2000 = {"Average CNR (b=2000)": round(data['qc_cnr_avg'][3], 2)}
			metrics_list.append(avg_cnr_b2000)		

			# avg cnr (b=3000)		

			avg_cnr_b3000 = {"Average CNR (b=3000)": round(data['qc_cnr_avg'][4], 2)}
			metrics_list.append(avg_cnr_b3000)

