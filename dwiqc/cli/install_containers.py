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


# This script will install the qsiprep, prequal and chromium sif files in the .config directory under the user's home directory.
# If an install location is specified, a symlink will be created in that location.

logger = logging.getLogger(__name__)

chromium_link = 'https://www.dropbox.com/scl/fi/wgh2d6xtdgi87zaxc5m5l/chromium.sif?rlkey=go0y0yrgbdns6b2j8i55ufwro&dl=1'

prequal_link = 'https://www.dropbox.com/scl/fi/p58pbj4v662ji1ax19lka/prequal_nrg.sif?rlkey=lmm9jspl81w6jjfvkmsmbd595&dl=1'

qsiprep_link = 'https://www.dropbox.com/scl/fi/s8asxwmykyw7paqdcnaev/qsiprep.sif?rlkey=lnuffrzn9mf894q6j9tl2l2mc&dl=1'

home_dir = os.path.expanduser("~")

symlink_location = os.path.join(home_dir, '.config/dwiqc/containers/')

def do(args):

	os.makedirs(args.install_location, exist_ok=True)

	check_storage(args.install_location)

	logger.info('installing chromium...')

	### check if chromium already there

	if os.path.isfile(f"{args.install_location}/chromium.sif"):
		logger.warning(f'Chromium has already been downloaded to {args.install_location}.\nDelete to re-download. Skipping to prequal...')
		print('\n')

	else:

		download_chromium = f'curl -L -o {args.install_location}/chromium.sif {chromium_link}'
		proc1 = subprocess.Popen(download_chromium, shell=True, stdout=subprocess.PIPE)
		proc1.communicate()

		print("\n\n")

	if os.path.isfile(f"{args.install_location}/prequal_nrg.sif"):
		logger.warning(f'Prequal has already been downloaded to {args.install_location}.\nDelete to re-download. Skipping to qsiprep...')
		print('\n')

	else:

		logger.info('installing prequal...')

		download_prequal = f'curl -L -o {args.install_location}/prequal_nrg.sif {prequal_link}'
		proc2 = subprocess.Popen(download_prequal, shell=True, stdout=subprocess.PIPE)
		proc2.communicate()

		print("\n\n")

	if os.path.isfile(f"{args.install_location}/qsiprep.sif"):
		logger.warning(f'Qsiprep has already been downloaded to {args.install_location}.\nDelete to re-download. Skipping...')
		print('\n')

	else:
	
		logger.info('installing qsiprep...')

		download_qsiprep = f'curl -L -o {args.install_location}/qsiprep.sif {qsiprep_link}'
		proc3 = subprocess.Popen(download_qsiprep, shell=True, stdout=subprocess.PIPE)
		proc3.communicate()

	create_symlinks(args.install_location)

	print('\n')

	logger.info(f'Containers successfully downloaded to {args.install_location}')


def create_symlinks(source):

	if source == symlink_location:
		return

	os.chdir(source)
	for file in os.listdir(source):
		os.symlink(file, f"{symlink_location}{file}")
		print(f'creating symlink for {file}')

	

def check_storage(directory):
	# run df -Ph and tokenize each line's values into a list of 2 elements.
	df_output_lines = [s.split() for s in os.popen(f"df -Ph {directory}").read().splitlines()]

	# this line grabs the value attached to 'Avail' from the above df -Ph command. It then 
	# gets rid of the non numeric characters using re and converts that number from a string
	# to an integer

	avail_gigs = int(re.sub("[^0-9]", "", [line[3] for line in df_output_lines][1]))

	if avail_gigs < 22:
		logger.error(f'Not enough desk space at {directory}.\nPlease select a different directory using the --install-location argument.')
		sys.exit(1)

	else:
		logger.info(f'This directory has {avail_gigs}GB of available space. The dwiqc containers will take up 22GB of storage.')
		print("\n")
		time.sleep(5)







