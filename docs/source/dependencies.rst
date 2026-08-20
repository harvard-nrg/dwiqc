Dependencies
============
.. _prequal: https://github.com/MASILab/PreQual
.. _qsiprep: https://qsiprep.readthedocs.io/en/latest/
.. _FSL: https://fsl.fmrib.ox.ac.uk/fsl/fslwiki
.. _chromium: https://www.chromium.org/chromium-projects/
.. _Singularity: https://sylabs.io/singularity/

DWIQC is built upon `prequal`_, `qsiprep`_, and `FSL`_ software packages. `chromium`_ is used for creating PNG files. The containers are based on `Singularity`_.

.. list-table::
   :header-rows: 1

   * - Package
     - Version
   * - `prequal`_
     - 1.1.0
   * - `qsiprep`_
     - 0.18.0
   * - `FSL`_
     - 6.0.7.16
   * - `chromium`_
     - 102.0.5005.115

PreQual
-------
DWIQC runs PreQual with the following command:

.. code-block:: shell

   singularity run -e --env PYTHONUNBUFFERED=1 \
     --pwd /tmp \
     --contain \
     --nv \
     -B /path/to/inputs:/INPUTS/ \
     -B /path/to/outputs:/OUTPUTS \
     -B /tmp:/tmp \
     -B /path/to/freesurfer/license.txt:/APPS/freesurfer/license.txt \
     prequal_nrg.sif \
     --save_component_pngs \
     --subject <SUBJECT> \
     --project Proj \
     --session <SESSION> \
     --eddy_cuda 10.2 j \
     --num_threads 2 \
     --denoise on \
     --degibbs off \
     --rician off \
     --prenormalize on \
     --correct_bias on \
     --topup_first_b0s_only \
     --extra_eddy_args=--data_is_shelled+--ol_nstd=<STDEV>+--ol_type=gw+--repol+--estimate_move_by_susceptibility+--cnr_maps+--flm=quadratic+--interp=spline+--resamp=jac+--mporder=<MPORDER>+--niter=5+--nvoxhp=1000+--slspec=/INPUTS/<SPEC>+--slm=linear

QSIPrep
-------
DWIQC runs QSIPrep with the following command:

.. code-block:: shell

   singularity run --nv \
     qsiprep.sif \
     /path/to/bids \
     /path/to/outputs \
     participant \
     --output-resolution <RESOLUTION> \
     --eddy-config /path/to/bids/eddy_params_s2v_mbs.json \
     --fs-license-file /path/to/freesurfer/license.txt \
     -w /path/to/workdir \
     --pepolar-method TOPUP \
     --prefer_dedicated_fmaps \
     --b1-biascorrect-stage final \
     --separate-all-dwis \
     --notrack \
     --n_cpus 2 \
     --mem_mb 40000
