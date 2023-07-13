import os
import yaml

__dir__ = os.path.dirname(__file__)

def xnat_download():
    conf = os.path.join(
        __dir__,
        'dwiqc.yaml'
    )
    return conf

def prequal_command():
    cmd = os.path.join(
        __dir__,
        'prequal.yaml'
    )
    return cmd

def qsiprep_command():
    cmd = os.path.join(
        __dir__,
        'qsiprep.yaml'
    )
    return cmd