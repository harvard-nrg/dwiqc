import base64
import logging
import subprocess
logger = logging.getLogger(__name__)

def snapshot(url, saveto):
	proc1 = f'chromium.sif --no-sandbox --headless --print-to-pdf={saveto} {url}'
	output = subprocess.Popen(proc1, shell=True, stderr=subprocess.PIPE)
	output.communicate()
