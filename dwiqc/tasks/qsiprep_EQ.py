

import shutil
import os
import sys
sys.path.insert(0, os.path.join(os.environ['MODULESHOME'], "init"))
from env_modules_python import module
sys.path.insert(0, '/n/home_fasse/dasay/dwiqc/dwiqc/tasks')
import __init__ as tasks
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

		#### copy tempdir

		#load the fsl module
		module('load','fsl/6.0.4-centos7_64-ncf')


		# Find your way to eddy files. All files will be copied there.

		eddy_dir = (f'{self._outdir}/qsiprep/eddy_files')

		os.chdir(eddy_dir)

		hmc_dir = f'{eddy_dir}/qsiprep_wf/single_subject_{self._sub}_wf/dwi_preproc_ses_{self._ses}_run_{self._run}_wf/hmc_sdc_wf'

		# copy over eddy_corrected.eddy_rotated_bvecs

		shutil.copy(f'{hmc_dir}/eddy/eddy_corrected.eddy_rotated_bvecs', eddy_dir)
		print("copy success #1/6")

		# copy all files that end with txt and start with eddy in qsiprep/eddy_files/qsiprep_wf/single_subject_PE161458_wf/dwi_preproc_ses_PE161458221111_run_1_wf/hmc_sdc_wf/gather_inputs

		for file in os.listdir(f'{hmc_dir}/gatherinputs'):
			if file.endswith('.txt') and file.startswith('eddy'):
				shutil.copy(file, eddy_dir)

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

		shutil.copy(f'{self._outdir}/qsirecon/sub-{self._sub}/ses-{self._ses}/dwi/sub-{self._sub}_ses-{self._ses}_run_{self._run}_space-T1w_desc-preproc_space-T1w_fslstd_dwi.bval', eddy_dir)

		os.rename(f'{eddy_dir}/sub-{self._sub}_ses-{self._ses}_run_{self._run}_space-T1w_desc-preproc_space-T1w_fslstd_dwi.bval', f'{self._sub}.bval')

		print('copy success #6/6')


  		## run eddy_quad command

#		eddy_quad = f"""eddy_quad \
#		eddy_results \
#		-idx index.txt \
#		-par acqparams.txt \
#		--mask=eddy_mask.nii.gz \
#		--bvals=../PREPROCESSED/dwmri.bval \
#		--bvecs=../PREPROCESSED/dwmri.bvec \
#		--field ../TOPUP/topup_field.nii.gz \
#		-s ../{spec_file} \
#		-v"""






#		while not os.path.exists(f'{self._outdir}/EDDY'):
#			time.sleep(120)#

#		if os.path.isdir(f'{self._outdir}/EDDY'):
#			os.chdir(f'{self._outdir}/EDDY')#

#		# copy the necessary file to EDDY directory#

#		while not os.path.exists('../PREPROCESSED/dwmri.nii.gz'):
#			time.sleep(120)#

#		if os.path.isfile('../PREPROCESSED/dwmri.nii.gz'):
#			shutil.copy('../PREPROCESSED/dwmri.nii.gz', 'eddy_results.nii.gz')#

#		# grab name of slspec file#

#		for file in os.listdir(self._outdir):
#			if 'slspec' in file and file.endswith('.txt'):
#				spec_file = file#

#		## run eddy quad#

#		eddy_quad = f"""eddy_quad \
#		eddy_results \
#		-idx index.txt \
#		-par acqparams.txt \
#		--mask=eddy_mask.nii.gz \
#		--bvals=../PREPROCESSED/dwmri.bval \
#		--bvecs=../PREPROCESSED/dwmri.bvec \
#		--field ../TOPUP/topup_field.nii.gz \
#		-s ../{spec_file} \
#		-v"""#

#		proc1 = subprocess.Popen(eddy_quad, shell=True, stdout=subprocess.PIPE)
#		proc1.communicate()


