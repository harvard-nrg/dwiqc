

import shutil
import os
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

		#### copy tempdir

		print('copying all eddy output files...')

		shutil.copytree(self._tempdir, f'{self._outdir}/qsiprep/eddy_files')

		log_file = open(f"{self._outdir}/qsiprep/eddy_files/eddy_quad.log", "w")	
		sys.stdout = log_file

		#load the fsl module
		module('load','fsl/6.0.4-centos7_64-ncf')


		# Find your way to eddy files. All files will be copied there.

		eddy_dir = (f'{self._outdir}/qsiprep/eddy_files')

		os.chdir(eddy_dir)

		hmc_dir = f'{eddy_dir}/qsiprep_wf/single_subject_{self._sub}_wf/dwi_preproc_ses_{self._ses}_run_{self._run}_wf/hmc_sdc_wf'

		# copy over all files from eddy directory

		for file in os.listdir(f'{hmc_dir}/eddy'):
			if os.path.isfile(file):
				shutil.copy(f'{hmc_dir}/eddy/{file}', eddy_dir)

		#shutil.copy(f'{hmc_dir}/eddy/eddy_corrected.eddy_rotated_bvecs', eddy_dir)
		#shutil.copy(f'{hmc_dir}/eddy/eddy_corrected.nii.gz', eddy_dir)
		print("copy success #1/6")

		# copy all files that end with txt and start with eddy in qsiprep/eddy_files/qsiprep_wf/single_subject_PE161458_wf/dwi_preproc_ses_PE161458221111_run_1_wf/hmc_sdc_wf/gather_inputs

		for file in os.listdir(f'{hmc_dir}/gather_inputs'):
			if file.endswith('.txt') and file.startswith('eddy'):
				shutil.copy(f'{hmc_dir}/gather_inputs/{file}', eddy_dir)

		print("copy success #2/6")

		# copy topup_imain_corrected_avg_mask.nii.gz from qsiprep/eddy_files/qsiprep_wf/single_subject_PE161458_wf/dwi_preproc_ses_PE161458221111_run_1_wf/hmc_sdc_wf/pre_eddy_b0_ref_wf/enhance_and_mask_b0

		shutil.copy(f'{hmc_dir}/pre_eddy_b0_ref_wf/enhance_and_mask_b0/topup_imain_corrected_avg_mask.nii.gz', eddy_dir)
		print("copy success #3/6")

		# copy topup_reg_image_flirt.mat from qsiprep/eddy_files/qsiprep_wf/single_subject_PE161458_wf/dwi_preproc_ses_PE161458221111_run_1_wf/hmc_sdc_wf/topup_to_eddy_reg

		shutil.copy(f'{hmc_dir}/topup_to_eddy_reg/topup_reg_image_flirt.mat', eddy_dir)
		print("copy success #4/6")

		# copy  fieldmap_HZ.nii.gz from qsiprep/eddy_files/qsiprep_wf/single_subject_PE161458_wf/dwi_preproc_ses_PE161458221111_run_1_wf/hmc_sdc_wf/topup

		shutil.copy(f'{hmc_dir}/topup/fieldmap_HZ.nii.gz', eddy_dir)
		print("copy success #5/6")

		# copy sub-PE161458_ses-PE161458221111_run-1_space-T1w_desc-preproc_space-T1w_fslstd_dwi.bval (rename to bval) from /qsirecon/sub-PE161458/ses-PE161458221111/dwi

		shutil.copy(f'{self._outdir}/qsirecon/sub-{self._sub}/ses-{self._ses}/dwi/sub-{self._sub}_ses-{self._ses}_run-{self._run}_space-T1w_desc-preproc_space-T1w_fslstd_dwi.bval', eddy_dir)

		os.rename(f'{eddy_dir}/sub-{self._sub}_ses-{self._ses}_run-{self._run}_space-T1w_desc-preproc_space-T1w_fslstd_dwi.bval', f'{self._sub}.bval')

		print('copy success #6/6')


		for file in os.listdir(self._bids):
			if 'slspec' in file and file.endswith('.txt'):
				spec_file = file

  		## run eddy_quad command

		eddy_quad = f"""eddy_quad \
		eddy_corrected \
		-idx eddy_index.txt \
		-par eddy_acqp.txt \
		--mask=topup_imain_corrected_avg_mask.nii.gz \
		--bvals={self._sub}.bval \
		--bvecs=eddy_corrected.eddy_rotated_bvecs \
		--field fieldmap_HZ.nii.gz \
		-s {self._bids}/{spec_file} \
		-v"""

		proc1 = subprocess.Popen(eddy_quad, shell=True, stdout=subprocess.PIPE)
		proc1.communicate()

		log_file.close()




