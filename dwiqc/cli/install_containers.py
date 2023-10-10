#!/bin/env/python
import os
import re
import sys
import json
import yaml
import yaxil
import glob
import math
import time
import logging
import subprocess
import shutil
from executors.models import Job, JobArray
from bids import BIDSLayout
from tenacity import retry, retry_if_exception_type, stop_after_attempt


# This script will install the qsiprep, prequal and chromium sif files in the .config directory under the user's home directory.
# If an install location is specified, a symlink will be created in that location.

logger = logging.getLogger(__name__)

chromium_link = 'https://www.dropbox.com/scl/fi/wgh2d6xtdgi87zaxc5m5l/chromium.sif?rlkey=go0y0yrgbdns6b2j8i55ufwro&dl=1'

#prequal_link = 'https://www.dropbox.com/scl/fi/p58pbj4v662ji1ax19lka/prequal_nrg.sif?rlkey=lmm9jspl81w6jjfvkmsmbd595&dl=1'

#prequal_link = 'https://www.dropbox.com/scl/fi/az4mmv9dzd9gmeuoilnqd/prequal_nrg2.sif?rlkey=nimyvlrf9hgq2yle19m2yxgq0&dl=1'

prequal_link = 'https://www.dropbox.com/scl/fi/vklkupolvs34kn8rpzsyo/prequal_nrg3.sif?rlkey=kd1r20clr7xipe7gegi7htsho&dl=1'

fsl_link = 'https://www.dropbox.com/scl/fi/qboi0izu211j8fd5ffyym/fsl_6.0.4.sif?rlkey=qu7qsappf0w9ktluuqmvd8e8i&dl=1'

qsiprep_link = 'https://www.dropbox.com/scl/fi/s8asxwmykyw7paqdcnaev/qsiprep.sif?rlkey=lnuffrzn9mf894q6j9tl2l2mc&dl=1'

containers = ['chromium.sif','prequal_nrg.sif', 'qsiprep.sif', 'fsl_6.0.4.sif']



home_dir = os.path.expanduser("~")

symlink_location = os.path.join(home_dir, '.config/dwiqc/containers/')

def do(args):

	os.makedirs(args.install_location, exist_ok=True)

	os.makedirs(symlink_location, exist_ok=True)

	check_storage(args.install_location)

	logger.info('installing chromium...')

	### check if chromium already there

	if os.path.isfile(f"{args.install_location}/chromium.sif"):
		logger.warning(f'Chromium has already been downloaded to {args.install_location}.\nDelete to re-download. Skipping to prequal...')
		print('\n')

	else:

		#download_chromium = f'curl -L -o {args.install_location}/chromium.sif {chromium_link}'
		#proc1 = subprocess.Popen(download_chromium, shell=True, stdout=subprocess.PIPE)
		#proc1.communicate()

		chromium_location = f'{args.install_location}/chromium.sif'
		download(chromium_link, chromium_location)

		print("\n")

	chromium_target_bytes = 281231360

	chromium_bytes = os.path.getsize(f'{args.install_location}/chromium.sif')

	if chromium_bytes != chromium_target_bytes:
		logger.error("Chomium sif file did not download correctly. Delete and try again.")


	### check if prequal already there

	if os.path.isfile(f"{args.install_location}/prequal_nrg.sif"):
		logger.warning(f'Prequal has already been downloaded to {args.install_location}.\nDelete to re-download. Skipping to qsiprep...')
		print('\n')

	else:

		logger.info('installing prequal...')

		#download_prequal = f'curl -L -o {args.install_location}/prequal_nrg.sif {prequal_link}'
		#proc2 = subprocess.Popen(download_prequal, shell=True, stdout=subprocess.PIPE)
		#proc2.communicate()

		prequal_location = f'{args.install_location}/prequal_nrg.sif'
		download(prequal_link, prequal_location)

		print("\n")

	prequal_target_bytes = 14161645568

	prequal_bytes = os.path.getsize(f"{args.install_location}/prequal_nrg.sif")

	if prequal_target_bytes != prequal_bytes:
		logger.error("Prequal sif file did not download correctly. Delete and try again.")

	### check if qsiprep already there

	if os.path.isfile(f"{args.install_location}/qsiprep.sif"):
		logger.warning(f'Qsiprep has already been downloaded to {args.install_location}.\nDelete to re-download. Skipping to fsl...')
		print('\n')

	else:
	
		logger.info('installing qsiprep...')

		#download_qsiprep = f'curl -L -o {args.install_location}/qsiprep.sif {qsiprep_link}'
		#proc3 = subprocess.Popen(download_qsiprep, shell=True, stdout=subprocess.PIPE)
		#proc3.communicate()

		qsiprep_location = f'{args.install_location}/qsiprep.sif'
		download(qsiprep_link, qsiprep_location)

		print('\n')

	qsiprep_target_bytes = 8172097536

	qsiprep_bytes = os.path.getsize(f"{args.install_location}/qsiprep.sif")

	if qsiprep_target_bytes != qsiprep_bytes:
		logger.error("Qsiprep sif file did not download correctly. Delete and try again.")

	### check if fsl already there

	if os.path.isfile(f"{args.install_location}/fsl_6.0.4.sif"):
		logger.warning(f'FSL has already been downloaded to {args.install_location}.\nDelete to re-download. Skipping...')
		print('\n')

	else:

		logger.info('installing fsl...')

		#download_fsl = f'curl -L -o {args.install_location}/fsl_6.0.4.sif {fsl_link}'
		#proc4 = subprocess.Popen(download_fsl, shell=True, stdout=subprocess.PIPE)
		#proc4.communicate()

		fsl_location = f'{args.install_location}/fsl_6.0.4.sif'
		download(fsl_link, fsl_location)

	fsl_target_bytes = 6803890176

	fsl_bytes = os.path.getsize(f'{args.install_location}/fsl_6.0.4.sif')

	if fsl_target_bytes != fsl_bytes:
		print('\n')
		logger.error("FSL sif file did not download correctly. Delete and try again.")


	create_symlinks(args.install_location)

	all_files = [file for file in os.listdir()]
	if 'chromium.sif' in all_files and 'qsiprep.sif' in all_files and 'prequal_nrg.sif' in all_files:
		logger.info(f'Containers successfully downloaded to {args.install_location}')
	else:
		logger.error(f'At least one container hit an error downloading. Check internet connection and try again.')


def create_symlinks(source):

	if source == symlink_location:
		return

	os.chdir(source)
	for file in os.listdir(source):
		if file in containers:
			abs_path = os.path.abspath(file)
			try:
				os.symlink(abs_path, f"{symlink_location}{file}")
			except FileExistsError:
				continue
		else:
			continue

	

def check_storage(directory):
	# run df -Ph and tokenize each line's values into a list of 2 elements.
	df_output_lines = [s.split() for s in os.popen(f"df -Ph --block-size=1GB {directory}").read().splitlines()]

	# this line grabs the value attached to 'Avail' from the above df -Ph command. It then 
	# gets rid of the non numeric characters using re and converts that number from a string
	# to an integer

	avail_gigs = int(re.sub("[^0-9]", "", [line[3] for line in df_output_lines][1]))

	if avail_gigs < 30:
		logger.error(f'Not enough desk space at {directory}.\nPlease select a different directory using the --install-location argument.')
		sys.exit(1)

	else:
		logger.info(f'This directory has {avail_gigs}GB of available space.\nThe dwiqc containers will take up 30GB of storage.')
		print("\n")
		time.sleep(5)

class PartialFileError(Exception):
	pass

@retry(
	retry=retry_if_exception_type(PartialFileError),
	stop=stop_after_attempt(50),
	reraise=True
)

def download(url, output, retry=50):
	cmd = [
		'curl',
		'-L',
		'-C', '-',
		'-o', output,
		url
	]
	try:
		subprocess.check_output(cmd)
	except subprocess.CalledProcessError as e:
		if e.returncode == 18:
			raise PartialFileError(url)







