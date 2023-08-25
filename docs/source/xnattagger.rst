xnattagger Documentation
=========================

*xnattagger* is a python command line tool that labels or "tags" scans within an XNAT instance according to user specifications. 

Tagging Convention Overview
---------------------------

"Tagging" refers to adding notes to your scans' notes field in XNAT. The example below shows the tag that will be added to the notes field for each of the different modalities using *xnattagger* along with some example series names for each modality.

=========== ================================  ==================================================
Type        Example series                    Note
=========== ================================  ==================================================
DWI         ``UKbioDiff_ABCDseq_ABCDdvs``     ``#DWI_MAIN_001, #DWI_MAIN_002, ..., #DWI_MAIN_N``
DWI_PA_FMAP ``UKbioDiff_ABCDseq_DistMap_PA``  ``#DWI_PA_001, #DWI_PA_002, ..., #DWI_PA_N``
DWI_AP_FMAP ``UKbioDiff_ABCDseq_DistMap_AP``  ``#DWI_AP_001, #DWI_AP_002, ..., #DWI_AP_N``
BOLD        ``ABCD_fMRI_rest_noPMU``          ``#BOLD_001, #BOLD_002, ..., #BOLD_N``
BOLD_PA     ``ABCD_fMRI_DistortionMap_PA``    ``#BOLD_PA_001, #BOLD_PA_002, ..., #BOLD_PA_N``
BOLD_AP     ``ABCD_fMRI_DistortionMap_AP``    ``#BOLD_AP_001, #BOLD_AP_002, ..., #BOLD_AP_N``
T1w         ``ABCD_T1w_MPR_vNav``             ``#T1w_001, #T1w_001, ..., #T1w_N``
T1w_MOVE    ``ABCD_T1w_MPR_vNav_setter``      ``#T1w_MOVE_001, #T1w_MOVE_002, ..., #T1w_MOVE_N``
T2w         ``ABCD_T2w_SPC_vNav``             ``#T2w_001, #T2w_002, ..., #T2w_N``
T2w_MOVE    ``ABCD_T2w_SPC_vNav_setter``      ``#T2w_MOVE_001, #T2w_MOVE_002, ..., #T2w_MOVE_N``
=========== ================================  ==================================================

The image below displays an MR Session report page with populated notes.

.. note::
   Note that if a ``DWI`` scan has corresponding ``PA`` and ``AP`` scans, they should be assigned matching numbers. For example, ``#DWI_MAIN_001`` would correspond to ``#DWI_PA_001`` and ``#DWI_AP_001``.

.. image:: images/xnat-scan-notes.png

Installation
------------

Install *xnattagger* via pip:

.. code-block:: shell

    pip install xnattagger

Verify that it installed sucessfully:

.. code-block:: shell

	pip show xnattagger

Configuring xnattagger
----------------------

In order for *xnattagger* to work properly, it has to know what it's looking for, as it parses information about the scans. Particularly, it needs to know the series name and image type that correspond to the different modalities. That's where the *tagger.yaml* config file comes in. Take a look at the example below. Notice that each modality has a series description and image type associated with it.

.. code-block:: yaml

	t1w:
	    - series_description: ABCD_T1w_MPR_vNav
	      image_type: [ORIGINAL, PRIMARY, M, ND, NORM]
	t1w_move:
	    - series_description: ABCD_T1w_MPR_vNav_setter
	      image_type: [ORIGINAL, PRIMARY, M, ND, MOSAIC]
	t2w:
	    - series_description: ABCD_T2w_SPC_vNav
	      image_type: [ORIGINAL, PRIMARY, M, ND, NORM]
	t2w_move:
	    - series_description: ABCD_T2w_SPC_vNav_setter
	      image_type: [ORIGINAL, PRIMARY, M, ND, MOSAIC]
	dwi:
	    - series_description: ABCD_dMRI_lowSR
	      image_type: [ORIGINAL, PRIMARY, DIFFUSION, NONE, ND, MOSAIC]
	    - series_description: UKbioDiff_ABCDseq_ABCDdvs
	      image_type: [ORIGINAL, PRIMARY, DIFFUSION, NONE, ND, MOSAIC]
	dwi_PA:
	    - series_description: ABCD_dMRI_DistortionMap_PA
	      image_type: [ORIGINAL, PRIMARY, DIFFUSION, NONE, ND]
	    - series_description: UKbioDiff_ABCDseq_DistMap_PA
	      image_type: [ORIGINAL, PRIMARY, DIFFUSION, NONE, ND]
	dwi_AP:
	    - series_description: ABCD_dMRI_DistortionMap_AP
	      image_type: [ORIGINAL, PRIMARY, DIFFUSION, NONE, ND]
	    - series_description: UKbioDiff_ABCDseq_DistMap_AP
	      image_type: [ORIGINAL, PRIMARY, DIFFUSION, NONE, ND]
	bold:
	    - series_description: ABCD_fMRI_rest_noPMU
	      image_type: [ORIGINAL, PRIMARY, M, ND, MOSAIC]
	bold_PA:
	    - series_description: ABCD_fMRI_DistortionMap_PA
	      image_type: [ORIGINAL, PRIMARY, M, ND]
	bold_AP:
	    - series_description: ABCD_fMRI_DistortionMap_AP
	      image_type: [ORIGINAL, PRIMARY, M, ND]

Running xnattagger
------------------

Required Arguments
^^^^^^^^^^^^^^^^^^

*xnattagger* requires three arguments: `1) ---label` `2) ---target-modality` `3) ---xnat-alias`

| 1. ``--label`` refers to the XNAT MR Session ID, which is found under XNAT PROJECT ---> SUBJECT ---> MR_SESSION

.. image:: images/MR-Session.png

| 2. ``--target-modality`` refers to which modalities you want to tag. This argument may be **one** of the following: ``dwi``, ``anat``, ``bold``, ``all``

.. code-block:: shell

	--target modality {dwi, anat, bold, all}

| 3. ``--xnat-alias`` is the alias containing credentials associated with your XNAT instance. It can be created in a few `steps <https://yaxil.readthedocs.io/en/latest/xnat_auth.html>`_ with yaxil.


