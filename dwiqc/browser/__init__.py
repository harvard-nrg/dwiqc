import os
import sys
import base64
import logging
import mimetypes
import subprocess
from pathlib import Path
from lxml import etree, html

logger = logging.getLogger(__name__)

def snapshot(url, saveto, container_dir):
    """
    Function to convert the qsiprep html file to a pdf file with the chromium container
    """
    proc1 = f"""
    singularity run \
    {container_dir}/chromium.sif \
    --no-sandbox \
    --headless \
    --print-to-pdf={saveto} \
    {url}
    """
    output = subprocess.Popen(proc1, shell=True, stdout=subprocess.PIPE)
    output.communicate()
    code = output.returncode
    print(type(output.returncode))
    if code == 0:
        logger.info('pdf conversion successful!')
    else:
        logger.critical('pdf conversion failed')
        raise ChromiumConvertError(output.errors)

def imbed_images(infile, outfile=None):
    """
    Function that will take the qsiprep.html file and imbed the images into the html file
    """
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


class ChromiumConvertError(Exception):
    pass