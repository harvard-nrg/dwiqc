#!/bin/env/python
import os
import re
import sys
import json
import yaml
import yaxil
import glob
import math
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

default_location = '~/.config/dwiqc/containers/'

def do(args):

	os.makedirs(default_location, exist_ok=True)

	logger.info('installing chromium...')

	download_chromium = f'curl -L -s {chromium_link}'
	proc1 = subprocess.Popen(download_chromium, shell=True, stdout=subprocess.PIPE)
	proc1.communicate()

	logger.info('installing prequal...')

	download_prequal = f'curl -L -s {prequal_link}'
	proc2 = subprocess.Popen(download_prequal, shell=True, stdout=subprocess.PIPE)
	proc2.communicate()
	
	logger.info('installing qsiprep...')

	download_qsiprep = f'curl -L -s {qsiprep_link}'
	proc3 = subprocess.Popen(download_qsiprep, shell=True, stdout=subprocess.PIPE)
	proc3.communicate()


def symlink()
	