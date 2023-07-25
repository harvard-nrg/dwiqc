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
import subprocess as sp
import shutil
from executors.models import Job, JobArray
from bids import BIDSLayout


# This script will install the qsiprep, prequal and chromium sif files in the .config directory under the user's home directory.
# If an install location is specified, a symlink will be created in that location.

logger = logging.getLogger(__name__)

chromium_link = 'https://www.dropbox.com/scl/fi/wgh2d6xtdgi87zaxc5m5l/chromium.sif?rlkey=go0y0yrgbdns6b2j8i55ufwro&dl=1'

prequal_link = ''

qsiprep_link = 'https://www.dropbox.com/scl/fi/s8asxwmykyw7paqdcnaev/qsiprep.sif?rlkey=lnuffrzn9mf894q6j9tl2l2mc&dl=1'


def do(args):

	print(args.install_location)
	