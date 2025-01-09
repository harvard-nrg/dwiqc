---
title: 'DWIQC: A Python package for preprocessing and quality assurance of diffusion weighted images'
tags:
  - Python
  - neuroimaging
  - diffusion
  - DTI
  - qsiprep
  - prequal
  - fsl
  - mrtrix
authors:
  - name: Daniel J. Asay
    orcid: 0000-0002-6691-7706
    affiliation: 1
  - name: Timothy M. O'Keefe
    affiliation: 1
  - name: Randy L. Buckner
    affiliation: "1, 2, 3" 
  - name: Ross W. Mair
    affiliation: "1, 2"
affiliations:
 - name: Center for Brain Science, Harvard University, Cambridge, Massachusetts, United States
   index: 1
 - name: Athinoula A. Martinos Center for Biomedical Imaging, Massachusetts General Hospital, Charlestown, Massachusetts, United States
   index: 2
 - name: Department of Psychiatry, Massachusetts General Hospital, Charlestown, Massachusetts, United States
   index: 3
date: 26 March 2024
bibliography: citations.bib
---

# Summary

Diffusion weighted neuroimaging is an MR modality that maps white-matter microstructure in the human brain. `DWIQC` serves as a robust quality assurance preprocessing tool for diffusion weighted images as well as a means to facilitate data management and sharing via the XNAT platform. `DWIQC` utilizes analysis tools developed by FSL [@smith_advances_2004], Prequal [@cai_prequal:_2021], Qsiprep [@cieslak_qsiprep:_2021] and MRtrix [@tournier_mrtrix:_2012] to perform first level preprocessing of diffusion weighted images and to assess data quality through quantitative metrics. `DWIQC` utilizes containerized versions of the aforementioned software to ensure reproducibility of results and portability. `DWIQC` generates an aggregated report of summary metrics and images from the output of analysis software, including parametric maps and connectivity matrices from Prequal and Qsiprep, which can be uploaded to the XNAT [@marcus_extensible_2007] data management platform, though uploading to XNAT is not necessary. All outputs from software used are stored in the user specified output directory.


# Statement of need

Diffusion neuroimaging is a burgeoning field with huge potential to deepen our understanding of the brain. While exciting, it also means that acquisition parameters, study designs, and theoretical analysis frameworks vary greatly. `DWIQC` is an effort to make diffusion imaging analysis and quality assurance accessible to researchers with diverse experimental designs. By leveraging the respective strengths of various diffusion imaging analysis tools, `DWIQC` appeals to a broad range of users who employ different data acquisition approaches. Additionally, large, multi-site studies can can use the standardized preprocessing to ensure uniformity in data preprocessing, data quality metrics and downstream analysis. `DWIQC` serves as a one stop destination for users who want a seamless integration of Prequal, Qsiprep and FSL Eddy Quad with the flexibility of catering to diverse acquisition protocols. Users can configure settings in `DWIQC` that will be applied across all the software that is used, abstracting away the sometimes convoluted task of doing so for each software pipeline individually.

Furthermore, `DWIQC's` integration with the XNAT data management platform facilitates ease of adoption due to XNAT's widespread use at neuroimaging centers. Sites that use `DWIQC` and upload its results to an XNAT instance provide transparency in analysis practices for collaborating sites. Multi-site studies benefit by seeing diffusion analysis reports in the same format across sites and subjects.

`DWIQC` benefits researchers by catching problems in data quality in real-time. The robustness `DWIQC's` pipelines allows even minor data quality issues to be caught. By running the diffusion weighted data through large-scale preprocessing pipelines, researchers are privy to data quality problems that would not be caught otherwise. As such, adjustments can be made mid-study to data collection protocols as necessary, rather than waiting until data collection has stopped only to discover data quality issues.


# Acknowledgements

We thank the Center for Brain Science at Harvard and the Harvard Faculty of Arts and Sciences for the financial support of this project.

# References
