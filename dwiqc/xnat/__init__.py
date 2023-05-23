import re
import os
import io
import sys
import glob
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

EDDY_METRICS = [
    'Average_SNR_b0', 'Average_CNR_b500','Average_CNR_b1000', 'Average_CNR_b2000', 
    'Average_CNR_b3000', 'Average_abs_motion_mm', 'Average_rel_motion_mm', 'Average_x_translation_mm',
    'Average_y_translation_mm', 'Average_z_translation_mm'
]


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
        aid = '{0}_DWI_{1}_AQC'.format(DWI_ds['experiment'], DWI_ds['scan'])
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

        # compile a list of files to be added to xnat:out section

        # pull images from eddy_quad output

        resources = [
            {
                'source': os.path.join(self.dirs['prequal'], 'OUTPUTS', 'EDDY', 'eddy_results.qc', 'avg_b0.png'),
                'dest': os.path.join('b0_avg', '{0}_preprocessed_b0.png'.format(aid))
            },
            {
                'source': os.path.join(self.dirs['prequal'], 'OUTPUTS', 'EDDY', 'eddy_results.qc', 'avg_b500.png'),
                'dest': os.path.join('b500_avg', '{0}_preprocessed_b500.png'.format(aid))
            },
            {
                'source': os.path.join(self.dirs['prequal'], 'OUTPUTS', 'EDDY', 'eddy_results.qc', 'avg_b1000.png'),
                'dest': os.path.join('b1000_avg', '{0}_preprocessed_b1000.png'.format(aid))
            },
            {
                'source': os.path.join(self.dirs['prequal'], 'OUTPUTS', 'EDDY', 'eddy_results.qc', 'avg_b2000.png'),
                'dest': os.path.join('b2000_avg', '{0}_preprocessed_b2000.png'.format(aid))
            },
            {
                'source': os.path.join(self.dirs['prequal'], 'OUTPUTS', 'EDDY', 'eddy_results.qc', 'avg_b3000.png'),
                'dest': os.path.join('b3000_avg', '{0}_preprocessed_b3000.png'.format(aid))
            },
            {
                'source': os.path.join(self.dirs['prequal'], 'OUTPUTS', 'EDDY', 'eddy_results.qc', 'qc.pdf'),
                'dest': os.path.join('eddy_pdf', '{0}_eddy_quad_qc.pdf'.format(aid))
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

            # pull files from qsiprep output

            {
                'source': os.path.join(self.dirs['qsiprep'], 'qsiprep_output', 'qsiprep',  self.sub + '.html'),
                'dest': os.path.join('qsiprep-html', '{0}_qsiprep.html'.format(aid))
            },
            {
                'source': os.path.join(self.dirs['qsiprep'], 'qsiprep_output', 'qsiprep',  self.sub, 'figures', self.sub + '_ses-' + self.ses + '_run-' + self.run + '_carpetplot.svg'),
                'dest': os.path.join('carpet-plot', '{0}_carpetplot.svg'.format(aid))
            },
            {
                'source': os.path.join(self.dirs['qsiprep'], 'qsiprep_output', 'qsiprep',  self.sub, 'figures', self.sub + '_t1_2_mni.svg'),
                'dest': os.path.join('t1-registration', '{0}_t1_registration.svg'.format(aid))
            }
        ]
        # start building XML
        xnatns = '{%s}' % ns['xnat']
        etree.SubElement(root, xnatns + 'imageSession_ID').text = DWI_ds['experiment_id']
        etree.SubElement(root, 'PA_fmap_scan_id').text = PA_ds['scan']
        etree.SubElement(root, 'AP_fmap_scan_id').text = AP_ds['scan']
        etree.SubElement(root, 'dwi_scan_id').text = DWI_ds['scan']
        etree.SubElement(root, 'session_label').text = DWI_ds['experiment']

        # add <eddy_quad> element
        eddy_quad_elm = etree.SubElement(root, 'eddy_quad')
        fname = os.path.join(
            self.dirs['prequal'],
            'OUTPUTS',
            'EDDY',
            'eddy_results.qc',
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
        # add <morph> element
#        morph_elm = etree.SubElement(root, 'morph')
#        # -- add mri_cnr data
#        fname = os.path.join(self.dirs['morph'], 'morphometrics', 'stats', 'mri_cnr.json')
#        with open(fname) as fo:
#            mri_cnr = json.load(fo)
#        etree.SubElement(morph_elm, 'mri_cnr_tot').text = floatfmt(mri_cnr['tot_cnr'])
#        # add wm_anat_snr data
#        fname = os.path.join(self.dirs['morph'], 'morphometrics', 'stats', 'wm_anat_snr.json')
#        with open(fname) as fo:
#            wm_anat_snr = json.load(fo)
#        etree.SubElement(morph_elm, 'wm_anat_snr').text = floatfmt(wm_anat_snr['snr'])
#        # add lh euler holes, cnr, gray/white, gray/csf
#        fname = os.path.join(self.dirs['morph'], 'morphometrics', 'stats', 'lh.mris_euler_number.json')
#        with open(fname) as fo:
#            lh_euler = json.load(fo)
#        etree.SubElement(morph_elm, 'lh_euler_holes').text = str(lh_euler['holes'])
#        etree.SubElement(morph_elm, 'lh_cnr').text = floatfmt(mri_cnr['lh_cnr'])
#        etree.SubElement(morph_elm, 'lh_gm_wm_cnr').text = floatfmt(mri_cnr['lh_gm_wm_cnr'])
#        etree.SubElement(morph_elm, 'lh_gm_csf_cnr').text = floatfmt(mri_cnr['lh_gm_csf_cnr'])
#        # add rh euler holes, cnr, gray/white, gray/csf
#        fname = os.path.join(self.dirs['morph'], 'morphometrics', 'stats', 'rh.mris_euler_number.json')
#        with open(fname) as fo:
#            rh_euler = json.load(fo)
#        etree.SubElement(morph_elm, 'rh_euler_holes').text = str(rh_euler['holes'])
#        etree.SubElement(morph_elm, 'rh_cnr').text = floatfmt(mri_cnr['rh_cnr'])
#        etree.SubElement(morph_elm, 'rh_gm_wm_cnr').text = floatfmt(mri_cnr['rh_gm_wm_cnr'])
#        etree.SubElement(morph_elm, 'rh_gm_csf_cnr').text = floatfmt(mri_cnr['rh_gm_csf_cnr'])
#        # add <vnav> element
#        if self.dirs['vnav']:
#            vnav_elm = etree.SubElement(root, 'vnav')
#            # count the number of vNav transforms
#            fname = os.path.join(self.dirs['vnav'], 'vNav_Motion.json')
#            with open(fname) as fo:
#                vnav = json.load(fo)
#            n_vnav_acq = len(vnav['Transforms'])
#            rms_per_min = vnav['MeanMotionScoreRMSPerMin']
#            max_per_min = vnav['MeanMotionScoreMaxPerMin']
#            moco_fail = '0'
#            if vnav['Failed']:
#                moco_fail = vnav['Failed']['Acquisition']
#            T1w_protocol = self.protocol('morph')
#            vnav_min = PROTOCOL_SETTINGS[T1w_protocol]['min']
#            vnav_max = PROTOCOL_SETTINGS[T1w_protocol]['max']
#            logger.info('vNav min=%s, max=%s (%s)', vnav_min, vnav_max, T1w_protocol)
#            etree.SubElement(vnav_elm, 'vnav_min').text = str(vnav_min)
#            etree.SubElement(vnav_elm, 'vnav_max').text = str(vnav_max)
#            etree.SubElement(vnav_elm, 'vnav_acq_tot').text = str(n_vnav_acq)
#            etree.SubElement(vnav_elm, 'vnav_reacq').text = str(n_vnav_acq - vnav_min)
#            etree.SubElement(vnav_elm, 'mean_mot_rms_per_min').text = floatfmt(rms_per_min)
#            etree.SubElement(vnav_elm, 'mean_mot_max_per_min').text = floatfmt(max_per_min)
#            etree.SubElement(vnav_elm, 'vnav_failed').text = str(moco_fail)

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


#instance = Report('/n/home_fasse/dasay/mockup_dwiqc_output', 'PE161458', 'PE161458220526', '1')

#instance.build_assessment('/n/home_fasse/dasay/mockup_dwiqc_output/xnat-artifacts')


