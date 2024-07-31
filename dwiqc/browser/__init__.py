import os
import sys
import base64
import logging
import mimetypes
import subprocess
from pathlib import Path
from lxml import etree, html
home_dir = os.path.expanduser("~")
logger = logging.getLogger(__name__)


def snapshot(url, saveto, container_dir=None):
    chromium_sif = check_container_path(container_dir)
    proc1 = f"""singularity run \
    {chromium_sif} \
    --no-sandbox \
    --headless \
    --print-to-pdf={saveto} \
    {url}"""
    output = subprocess.Popen(proc1, shell=True, stdout=subprocess.PIPE)
    output.communicate()
    code = output.returncode
    if code == 0:
        logging.info('pdf conversion successful!')
    else:
        logging.error('pdf conversion threw an error. exiting.')
        sys.exit(1)

def imbed_images(infile, outfile=None):
    infile = Path(infile)
    if not outfile:
        outfile = infile.with_stem(f'{infile.stem}-imbedded_images')
    os.chdir(infile.parent)
    logger.info(f'reading {infile}')
    with open(infile) as fo:
        content = fo.read().encode('utf-8')
    root = etree.HTML(content)
    for obj in root.xpath('//object'):
        filename = obj.attrib['data']
        mimetype = mimetypes.guess_type(filename)[0]
        with open(filename, 'rb') as image_file:
            content = image_file.read()
            if mimetype == 'image/svg+xml':
                svg = etree.XML(content)
                obj.getparent().replace(obj, svg)
            else:
                content = base64.b64encode(content).decode('utf-8')
                newdata = f'data:{mimetype};base64,{content}'
                obj.attrib['data'] = newdata
    logger.info(f'writing {outfile}')
    with open(outfile, 'wb') as fo:
        fo.write(etree.tostring(root))

def check_container_path(container_dir):
    if container_dir:
        try:
            chromium_sif = f'{container_dir}/chromium.sif'
            return chromium_sif
        except FileNotFoundError:
            logger.error(f'{container_dir}/chromium.sif does not exist. Verify the path and file name.')
            sys.exit(1)
    else:
        home_dir = os.path.expanduser("~")
        try:
            chromium_sif = os.path.join(home_dir, '.config/dwiqc/containers/chromium.sif')
            return chromium_sif
        except FileNotFoundError:
            logger.error(f"No --container-dir argument was supplied and unable to find chromium sif at default location: {os.path.join(home_dir, '.config/dwiqc/containers}')}")
            sys.exit(1)