import re
from glob import glob
import os
import io
import sys
import yaml
import json
import lxml
import shutil
import zipfile
import logging
import numpy as np
from lxml import etree
from bids import BIDSLayout

logger = logging.getLogger(__name__)




class Report:
    def __init__(self, bids, sub, ses, run):
        self.module = os.path.dirname(__file__)
        self.bids = bids
        self.sub = sub
        self.run = run
        self.ses = ses if ses else ''
 
    def getdirs(self):
        self.dirs = {
            'prequal': None,
            'qsiprep': None,
        }
        for task in self.dirs.keys():
            d = os.path.join(
                self.bids,
                'derivatives',
                'dwiqc-' + task,
                'sub-' + self.sub.replace('sub-', ''),
                'ses-' + self.ses.replace('ses-', ''),
            )

            # get bids layout structure

            self.layout = BIDSLayout(self.bids)

            json_file = self.layout.get(subject=self.sub, session=self.ses, suffix='dwi', extension='.json', return_type='filename').pop()

            self.basename = self.strip_extension(json_file)

            dirname = os.path.join(d, self.basename)
            if os.path.exists(dirname):
                self.dirs[task] = dirname
        logger.debug('prequal dir: %s', self.dirs['prequal'])
        logger.debug('qsiprep dir: %s', self.dirs['qsiprep'])


    def build_assessment(self, output):
        '''
        Build XNAT assessment

        :param output: Base output directory
        '''
        self.getdirs()
        if not self.dirs['prequal'] or not self.dirs['qsiprep']:
            raise AssessmentError('need prequal and qsiprep data to build assessment')
        # initialize namespaces
        ns = {
            None: 'http://www.neuroinfo.org/neuroinfo',
            'xs': 'http://www.w3.org/2001/XMLSchema',
            'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
            'xnat': 'http://nrg.wustl.edu/xnat',
            'neuroinfo': 'http://www.neuroinfo.org/neuroinfo'
        }
        # read dwi json sidecar for scan number
        dwi_file = self.layout.get(subject=self.sub, session=self.ses, suffix='dwi', extension='.nii.gz').pop()
        PA_file = self.layout.get(subject=self.sub, session=self.ses, suffix='epi', extension='.nii.gz', direction='PA').pop()
        AP_file = self.layout.get(subject=self.sub, session=self.ses, suffix='epi', extension='.nii.gz', direction='AP').pop()
        DWI_ds = dwi_file.get_metadata()['DataSource']['application/x-xnat']
        PA_ds = PA_file.get_metadata()['DataSource']['application/x-xnat']
        AP_ds = AP_file.get_metadata()['DataSource']['application/x-xnat']
        logger.info('DWI info %s', '|'.join(DWI_ds))
        logger.info('FMAP PA info %s', '|'.join(PA_ds))
        logger.info('FMAP AP info %s', '|'.join(AP_ds))
        # assessment id
        aid = '{0}_DWI_{1}_DWIQC'.format(DWI_ds['experiment'], DWI_ds['scan'])
        logger.info('Assessor ID %s', aid)
        # root element
        xnatns = '{%s}' % ns['xnat']
        root = etree.Element('DWIQC', nsmap=ns)
        root.attrib['project'] = DWI_ds['project']
        root.attrib['ID'] = aid
        root.attrib['label'] = aid
        # get start date and time from morph provenance
        fname = os.path.join(self.dirs['prequal'], 'OUTPUTS', 'logs', 'provenance.json')
        with open(fname) as fo:
            prov = json.load(fo)
        # add date and time
        etree.SubElement(root, xnatns + 'date').text = prov['start_date']
        etree.SubElement(root, xnatns + 'time').text = prov['start_time']

        if not self.sub.startswith('sub-'):
            self.sub = 'sub-' + self.sub

        no_prefix_sub = f"{self.sub[4:]}"

        # compile a list of files to be added to xnat:out section
	
        # pull images from eddy_quad output

        resources = [
            {
                'source': os.path.join(self.dirs['prequal'], 'OUTPUTS', 'EDDY', f'{no_prefix_sub}_{self.ses}.qc', 'qc.pdf'),
                'dest': os.path.join('eddy_pdf', '{0}_eddy_quad_qc.pdf'.format(aid))
            },
            {
                'source': os.path.join(self.dirs['prequal'], 'OUTPUTS', 'EDDY', 'motion_plot.png'),
                'dest': os.path.join('motion-plot', '{0}_motion_plot.png'.format(aid))
            },

            # pull images from prequal output
            {
                'source': os.path.join(self.dirs['prequal'], 'OUTPUTS', 'PDF', 'png', 'FA.png'),
                'dest': os.path.join('FA_map', '{0}_FA.png'.format(aid))
            },
            {
                'source': os.path.join(self.dirs['prequal'], 'OUTPUTS', 'PDF', 'png', 'MD.png'),
                'dest': os.path.join('MD_map', '{0}_MD.png'.format(aid))
            },
            {
                'source': os.path.join(self.dirs['prequal'], 'OUTPUTS', 'PDF', 'png', 'eddy_outlier_slices.png'),
                'dest': os.path.join('eddy_outliers', '{0}_eddy_outlier_slices.png'.format(aid))
            },
            {
                'source': os.path.join(self.dirs['prequal'], 'OUTPUTS', 'PDF', 'png', 'rotations.png'),
                'dest': os.path.join('rotations', '{0}_rotations.png'.format(aid))
            },
            {
                'source': os.path.join(self.dirs['prequal'], 'OUTPUTS', 'PDF', 'png', 'translations.png'),
                'dest': os.path.join('translations', '{0}_translations.png'.format(aid))
            },
            {
                'source': os.path.join(self.dirs['prequal'], 'OUTPUTS', 'PDF', 'png', 'displacements.png'),
                'dest': os.path.join('displacements', '{0}_displacements.png'.format(aid))
            },
            {
                'source': os.path.join(self.dirs['prequal'], 'OUTPUTS', 'PDF', 'dtiQA.pdf'),
                'dest': os.path.join('prequal_pdf', '{0}_prequal_qc.pdf'.format(aid))
            },
            {
                'source': os.path.join(self.dirs['prequal'], 'OUTPUTS', 'PREPROCESSED', 'b0_volume.nii.gz'),
                'dest': os.path.join('b0-volume', '{0}_b0_volume.nii.gz'.format(aid))
            },

            # pull files from qsiprep output

            {
                'source': os.path.join(self.dirs['qsiprep'], 'qsiprep_output', 'qsiprep',  'qsiprep.pdf'),
                'dest': os.path.join('qsiprep-pdf', '{0}_qsiprep.pdf'.format(aid))
            },
            {
                'source': os.path.join(self.dirs['qsiprep'], 'qsiprep_output', 'qsiprep',  self.sub + '-imbedded_images.html'),
                'dest': os.path.join('qsiprep-html', '{0}_qsiprep.html'.format(aid))
            },
            {
                'source': os.path.join(self.dirs['qsiprep'], 'qsiprep_output', 'qsiprep',  self.sub, 'figures', self.sub + '_ses-' + self.ses + '_run-' + str(self.run) + '_carpetplot.svg'),
                'dest': os.path.join('carpet-plot', '{0}_carpetplot.svg'.format(aid))
            },
            {
                'source': os.path.join(self.dirs['qsiprep'], 'qsiprep_output', 'qsiprep',  self.sub, 'figures', self.sub + '_t1_2_mni.svg'),
                'dest': os.path.join('t1-registration', '{0}_t1_registration.svg'.format(aid))
            },
            {
                'source': os.path.join(self.dirs['qsiprep'], 'qsiprep_output', 'qsiprep',  self.sub, 'figures', self.sub + '_seg_brainmask.svg'),
                'dest': os.path.join('seg-brainmask', '{0}_seg_brainmask.svg'.format(aid))
            },
            {
                'source': os.path.join(self.dirs['qsiprep'], 'qsiprep_output', 'qsiprep',  self.sub, 'figures', self.sub + '_ses-' + self.ses + '_run-' + str(self.run) + '_dwi_denoise_ses_' + self.ses + '_run_' + str(self.run) + '_dwi_wf_denoising.svg'),
                'dest': os.path.join('denoise', '{0}_denoise.svg'.format(aid))
            },
            {
                'source': os.path.join(self.dirs['qsiprep'], 'qsiprep_output', 'qsiprep',  self.sub, 'figures', self.sub + '_ses-' + self.ses + '_run-' + str(self.run) + '_dwi_denoise_ses_' + self.ses + '_run_' + str(self.run) + '_dwi_wf_biascorr.svg'),
                'dest': os.path.join('bias-corr', '{0}_bias_correction.svg'.format(aid))
            },
            {
                'source': os.path.join(self.dirs['qsiprep'], 'qsiprep_output', 'qsiprep',  self.sub, 'figures', self.sub + '_ses-' + self.ses + '_run-' + str(self.run) + '_desc-resampled_b0ref.svg'),
                'dest': os.path.join('b0-ref', '{0}_b0_reference.svg'.format(aid))
            },
            {
                'source': os.path.join(self.dirs['qsiprep'], 'qsiprep_output', 'qsiprep',  self.sub, 'figures', self.sub + '_ses-' + self.ses + '_run-' + str(self.run) + '_sampling_scheme.gif'),
                'dest': os.path.join('sampling-scheme', '{0}_sampling_scheme.gif'.format(aid))
            },
            {
                'source': os.path.join(self.dirs['qsiprep'], 'qsiprep_output', 'qsiprep',  self.sub, 'figures', self.sub + '_ses-' + self.ses + '_run-' + str(self.run) + '_desc-sdc_b0.svg'),
                'dest': os.path.join('distortion', '{0}_distortion.svg'.format(aid))
            },
            {
                'source': os.path.join(self.dirs['qsiprep'], 'qsiprep_output', 'qsiprep',  self.sub, 'figures', self.sub + '_ses-' + self.ses + '_run-' + str(self.run) + '_coreg.svg'),
                'dest': os.path.join('coreg', '{0}_coreg.svg'.format(aid))
            }
        ]

        # get all the b-shell values from eddy-quad
        shells = list()
        qcdir = os.path.join(self.dirs['prequal'], 'OUTPUTS', 'EDDY', f'{no_prefix_sub}_{self.ses}.qc')
        for filename in os.listdir(qcdir):
            fullfile = os.path.join(qcdir, filename)
            match = re.match('avg_b(\d+).png', filename)
            if not match:
                continue
            shells.append(int(match.group(1)))
            shell_dict = {
                'source': fullfile,
                'dest': os.path.join('bval-avg', '{0}_{1}'.format(aid, filename))
            }
            resources.append(shell_dict)
        # start building XML
        xnatns = '{%s}' % ns['xnat']
        etree.SubElement(root, xnatns + 'imageSession_ID').text = DWI_ds['experiment_id']
        etree.SubElement(root, 'PA_fmap_scan_id').text = PA_ds['scan']
        etree.SubElement(root, 'AP_fmap_scan_id').text = AP_ds['scan']
        etree.SubElement(root, 'dwi_scan_id').text = DWI_ds['scan']
        etree.SubElement(root, 'session_label').text = DWI_ds['experiment']


        EDDY_METRICS = [
            'Average_SNR_b0', 'Average_abs_motion_mm', 'Average_rel_motion_mm', 'Average_x_translation_mm',
            'Average_y_translation_mm', 'Average_z_translation_mm'
            ]

        # add <eddy_quad> element
        eddy_quad_elm = etree.SubElement(root, 'eddy_quad')
        fname = os.path.join(
            self.dirs['prequal'],
            'OUTPUTS',
            'EDDY',
            'eddy_metrics.json'
        )

        floatfmt = '{:.5f}'.format
        with open(fname) as fo:
            eddy = json.load(fo)
        for metric in EDDY_METRICS:
            value = eddy[metric]
            if isinstance(value, float):
                value = floatfmt(value)
            etree.SubElement(eddy_quad_elm, metric).text = str(value)

        shells = sorted(shells)
        shells.pop(0)

        shell_elm = etree.SubElement(eddy_quad_elm, 'shell_cnr')
        for shell in shells:
            metric = f"Average_CNR_b{shell}"
            value = eddy[metric]
            if isinstance(value, float):
                value = floatfmt(value)
            s = etree.SubElement(shell_elm, 'cnr')
            s.text = str(value)
            s.attrib['shell'] = str(shell)

        # write assessor to output mount location.
        xmlstr = etree.tostring(root, pretty_print=True, xml_declaration=True, encoding='UTF-8')
        assessor_dir = os.path.join(output, 'assessor')
        os.makedirs(assessor_dir, exist_ok=True)
        assessment_xml = os.path.join(assessor_dir, 'assessment.xml')
        with open(assessment_xml, 'wb') as fo:
            fo.write(xmlstr)

        # copy resources to output mount location
        resources_dir = os.path.join(output, 'resources')
        os.makedirs(resources_dir, exist_ok=True)
        for resource in resources:
            src = resource['source']
            dest = os.path.join(resources_dir, resource['dest'])
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copyfile(src, dest)


    def protocol(self, task):
        basename = os.path.basename(self.dirs[task])
        sidecar = os.path.join(self.dirs[task], 'logs', basename + '.json')
        if not os.path.exists(sidecar):
            raise FileNotFoundError(sidecar)
        with open(sidecar) as fo:
            js = json.load(fo)
        return js['ProtocolName']


    def strip_extension(self, filename):
        basename = os.path.splitext(os.path.basename(filename))[0]

        no_extension = os.path.splitext(basename)[0]

        return no_extension


class AssessmentError(Exception):
    pass




