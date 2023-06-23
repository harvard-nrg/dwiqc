XNAT user documentation
=======================
.. _XNAT: https://doi.org/10.1385/NI:5:1:11
.. _command.json: https://github.com/harvard-nrg/anatqc/blob/xnat-1.7.6/command.json
.. _T1w: https://tinyurl.com/hhru8ytz
.. _vNav: https://doi.org/10.1002/mrm.23228
.. _FreeSurfer: https://doi.org/10.1016/j.neuroimage.2012.01.021
.. _FreeSurfer license: https://surfer.nmr.mgh.harvard.edu/registration.html
.. _MRIQC: https://doi.org/10.1371/journal.pone.0184661
.. _SNR Tot: https://mriqc.readthedocs.io/en/latest/iqms/t1w.html
.. _Image Quality Metrics: https://mriqc.readthedocs.io/en/latest/iqms/t1w.html
.. _EFC: https://mriqc.readthedocs.io/en/latest/iqms/t1w.html
.. _FWHM Avg: https://mriqc.readthedocs.io/en/latest/iqms/t1w.html
.. _GM SNR: https://mriqc.readthedocs.io/en/latest/iqms/t1w.html
.. _Euler Holes: https://surfer.nmr.mgh.harvard.edu/fswiki/mris_euler_number
.. _Entropy Focus Criterion: http://dx.doi.org/10.1109/42.650886

Tagging your scans
------------------
For DWIQC to discover Diffusion and Fieldmap scans to process, you need to add notes to those scans in `XNAT`_. You can add notes using the ``Edit`` button located within the ``Actions`` box on the MR Session report page.

========= ================================  ===========================================================
Type      Example series                    Note
========= ================================  ===========================================================
DWI       ``UKbioDiff_ABCDseq_ABCDdvs``     ``#DWI_MAIN_001, #DWI_MAIN_002, ..., #DWI_MAIN_N``
PA_FMAP   ``UKbioDiff_ABCDseq_DistMap_PA``  ``#DWI_PA_001, #DWI_PA_002, ..., #DWI_PA_N``
AP_FMAP   ``UKbioDiff_ABCDseq_DistMap_AP``  ``#DWI_AP_001, #DWI_AP_002, ..., #DWI_AP_N``
========= ================================  ===========================================================

The image below displays an MR Session report page with populated notes.

.. note::
   Note that if a ``DWI`` scan has corresponding ``PA`` and ``AP`` scans, they should be assigned matching numbers. For example, ``#DWI_MAIN_001`` would correspond to ``#DWI_PA_001`` and ``#DWI_AP_001``.

.. image:: images/xnat-scan-notes.png

Running the pipeline
--------------------
To run the DWIQC pipeline, use the ``Run Containers > dwiqc-session`` button located within the ``Actions`` box on the MR Session report page

.. note::
   If you don't see the ``Run Containers`` menu, please refer to `Setting up the container <developers.html#setting-up-the-container>`_.

.. image:: images/xnat-run-button.png


This should bring up a small form with several configurable settings. Continue reading for a description of each setting

.. image:: images/xnat-container-form.png

run
^^^
This should be set to the integer value of the scan you want to process. If there's a corresponding ``move`` scan, that scan will also be processed

================= =======
DWI scan          run
================= =======
``#DWI_MAIN_001`` 1
``#DWI_MAIN_002`` 2
``#DWI_MAIN_999`` 999
================= =======

subtasks
^^^^^^^^
Under most circumstances you'll want to leave this field set to its default value ::

    prequal qsiprep

fslicense
^^^^^^^^^
This field should be set to a base64 encoded `FreeSurfer license`_. If you have a license file on a Linux or macOS machine, you can use the ``openssl`` command ::

    openssl base64 < license.txt

or you can use the ``base64`` command, if that utility is installed :: 

    base64 license.txt

Understanding the report page
-----------------------------
The following section will break down each section of the DWIQC report page.

.. image:: images/logo.png

Left pane
^^^^^^^^^
The left pane is broken up into several distinct sections. Each section will be described below.

Summary
"""""""
The ``Summary`` pane orients the user to what MR Session they're currently looking at and various processing details.

.. image:: images/xnat-acq-left-summary.png

============== ==================================
Key            Description
============== ==================================
MR Session     MR Session label
Date Processed Processing date
PA Fmap Scan   PA Fieldmap used
AP Fmap Scan   AP Fieldmap used
DWI Scan       DWI scan used
============== ==================================

SNR/CNR Metrics
""""""""""
The ``SNR/CNR Metrics`` pane displays SNR/CNR metrics computed *for each individual shell*.

.. image:: images/xnat-acq-left-snr-metrics.png

=========== ======================= =================================================
Metric      From                    Description                              
=========== ======================= =================================================
B0 SNR      Eddy Quad (Prequal/FSL) Signal-to-noise ratio for B0 Shell
BN CNR      Eddy Quad (Prequal/FSL) Contrast-to-noise ratio for each shell
=========== ======================= =================================================

.. note::
      Anywhere you see "Eddy Quad (Prequal/FSL)" means that FSL's Eddy Quad tool was run on Prequal output.

Motion Metrics
"""""""""""
The ``Motion Metrics`` pane displays motion metrics computed over dwi scan(s).

.. image:: images/xnat-acq-left-motion.png

================= ======================= ===========================================================
Metric            From                    Description
================= ======================= ===========================================================
Avg Abs Motion    Eddy Quad (Prequal/FSL) Estimated amount of all motion in any direction
Avg Rel Motion    Eddy Quad (Prequal/FSL) Estimated motion relative to initial head position
Avg X Translation Eddy Quad (Prequal/FSL) Estimated X translation motion
Avg Y Translation Eddy Quad (Prequal/FSL) Estimated Y translation motion
Avg Z Translation Eddy Quad (Prequal/FSL) Estimated Z translation motion
================= ======================= ===========================================================

Files
"""""
The ``Files`` pane contains the most commonly requested files. Clicking on any of these files will display that file in the browser.

.. image:: images/xnat-acq-left-files.png

======================= ======================= ======================================================
File                    From                    Description
======================= ======================= ======================================================
B0 Average              Eddy Quad (Prequal/FSL) BO Shell Average Image
Brain Mask              Qsiprep                 Gray Matter, White Matter and Pial Boundaries
FA Map                  Prequal                 Fractional Anisotropy Map
MD Map                  Prequal                 Mean Diffusivity Map
Eddy Outlier Sices      Prequal                 Plot of Slices with Motion Outliers
T1 Registration         Qsiprep                 GIF of T1w image to Template Registration
Denoise                 Qsiprep                 GIF of DWI Image Pre and Post Denoising
Motion Plot             Eddy Quad (Prequal/FSL) Translational and rotational motion, displacement
Prequal Report          Prequal                 Prequal PDF Report
Eddy Quad Report        Eddy Quad (Prequal/FSL) Eddy Quad PDF Report
Qsiprep Report          Qsiprep                 Qsiprep HTML Report
Carpet Plot             Qsiprep                 Maximum Framewise Displacement Plot
======================= ======================= ======================================================

.. note:: 
      Clicking on any of the ``Report`` files will open the complete report in a new tab in your browser for viewing. You can also download them from the new tab.

Tabs
^^^^
To the right of the `left pane <#left-pane>`_ you'll find a tab container. The following section explains the contents of each tab.

Images
""""""
The ``Images`` tab displays a zoomed out view of the FA and MD image maps, motion plots, brain mask, motion outlier slices, average shell images and a maximum framewise displacement plot.

.. image:: images/logo.png

Clicking on an image within the ``Images`` tab will display a larger version of that image in the browser.

.. image:: images/motion-plot.png

Prequal Report tab
""""""""""""""""
The ``Prequal Report`` tab displays the complete Prequal PDF report.

.. image:: images/prequal-tab.png

Eddy Quad Report Tab
""""""""""
The ``Eddy Quad Report`` tab displays key metrics and figures from the FSL Eddy command. 

.. image:: images/eddy-quad-tab.png

Qsiprep Report Tab
""""""""""
The ``Qsiprep Report`` tab displays the complete Qsiprep HTML report.

.. image:: images/qsiprep-tab.png

All Stored Files
""""""""""""""""
The ``All Stored Files`` tab contains a list of *every file* stored by DWIQC.

.. image:: images/all-stored-files-tab.png

.. note::
   Clicking on a file within the ``All Stored Files`` tab will download that file.

================================= =================================================
File                              Description
================================= =================================================
B0 Image                          B0 Volume/Shell
BN Images                         Images from Each Shell
FA Map                            Fractional Anisotropy Map
MD Map                            Mead Diffusivity Map
Eddy Outlier Slices               Plot of Slices with Motion Outliers
Motion Translations               Plot of motion translations across DWI scan
Motion Rotations                  Plot of motion rorations acorss DWI scan
Motion Displacements              Plot of motion displacements across DWI scan
Prequal PDF Report                Complete Prequal Report
Eddy Quad PDF Report              Complete Eddy Quad Report (run on Prequal output)
Qsiprep HTML Report               Complete Qsiprep Report in HTML Format
Qsiprep PDF Report                Complete Qsiprep Report in PDF Format
T1 Registration                   GIF of T1w image to Template Registration
Complete Motion Plot              Motion plot including transl, rot, displacements
Brain Mask/Segmentations          Gray Matter/White Matter Segmentations and Mask
B0 Volume                         B0 Volume from DWI Scan
================================= =================================================
