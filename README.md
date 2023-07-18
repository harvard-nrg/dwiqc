# dwiqc

DWIQC is a diffusion MRI quality control pipeline built on the Prequal and QSIPREP software packages. Working closely with neuroimaging experts, we designed an ergonomic user interface for the XNAT informatics and data management platform that allows users to quickly assess image quality and use those insights to get ahead of issues within the data acquisition workflow.

# USAGE

get mode:

dwiQC.py get --label XNATLABEL --bidsdir BIDSDIR --xnat-alias ALIAS

process mode:

dwiQC.py process --sub SUBJECT --ses SESSION --bids-dir BIDSDIR --xnat-alias ALIAS --xnat-upload

tandem mode (both get and process):

dwiQC.py tandem --label XNATLABEL --bidsdir BIDSDIR --xnat-alias ALIAS --xnat-upload
