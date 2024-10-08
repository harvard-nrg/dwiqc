#!/usr/bin/env python
import sys
import dwiqc
import dwiqc.cli as cli
import logging
import argparse as ap
import os
import dwiqc.config as config
import xnattagger.config as tagger_config


logger = logging.getLogger(__name__)
home_dir = os.path.expanduser("~")



def main():
    parser = ap.ArgumentParser()
    parser.add_argument('-v', '--verbose', action='store_true',
        help='Enable verbose logging')
    parser.add_argument('--insecure', action='store_true',
        help='Disable SSL certificate verification')
    subparsers = parser.add_subparsers(help='sub-command help')

    # install mode
    parser_install = subparsers.add_parser('install-containers', help='install-containers -h')
    parser_install.add_argument('--install-location', default=os.path.join(home_dir, '.config/dwiqc/containers/'),
        help='Path to desired container installation location')
    parser_install.set_defaults(func=cli.install_containers.do)
    
    # get mode
    parser_get = subparsers.add_parser('get', help='get -h')
    parser_get.add_argument('--label', required=True,
        help='XNAT MR Session name')
    parser_get.add_argument('--project',
        help='XNAT Project name')
    parser_get.add_argument('--download-config', required=True,
        help='dwiqc XNAT configuration file')
    parser_get.add_argument('--bids-dir', required=True,
        help='Output BIDS directory')
    parser_get.add_argument('--xnat-alias',
        help='YAXIL authentication alias')
    parser_get.add_argument('--xnat-host',
        help='XNAT host')
    parser_get.add_argument('--xnat-user',
        help='XNAT username')
    parser_get.add_argument('--xnat-pass',
        help='XNAT password')
    parser_get.add_argument('--tagger-config', default=tagger_config.default(),
        help='Path to xnattagger config file')
    parser_get.add_argument('--run-tagger', action='store_true', default=False,
        help='Run xnattagger')
    parser_get.add_argument('--in-mem', action='store_true', default=False,
        help='Tell yaxil to download data in memory. This can help with download speeds')
    parser_get.add_argument('--dry-run', action='store_true',
        help='Do not execute any jobs')
    parser_get.set_defaults(func=cli.get.do)

    # process mode
    parser_process = subparsers.add_parser('process', help='process -h')
    parser_process.add_argument('--partition', required=True,
        help='Job scheduler partition')
    parser_process.add_argument('--scheduler', default=None,
        help='Choose a specific job scheduler')
    parser_process.add_argument('--rate-limit', type=int, default=None, 
        help='Rate limit the number of tasks executed in parallel (1=serial)')
    parser_process.add_argument('--sub', required=True,
        help='BIDS subject')
    parser_process.add_argument('--ses', required=True,
        help='BIDS session')
    parser_process.add_argument('--mod', default='dwi',
        help='BIDS modality')
    parser_process.add_argument('--run', default=1, type=int,
        help='BIDS run')
    parser_process.add_argument('--bids-dir', required=True,
        help='BIDS root directory')
    parser_process.add_argument('--output-resolution-process',
        help='Resolution of output data. Default is resolution of input data.')
    parser_process.add_argument('--dry-run', action='store_true',
        help='Do not execute any jobs')
    parser_process.add_argument('--prequal-config', default=config.prequal_command(),
        help='Config file for custom prequal command.')
    parser_process.add_argument('--qsiprep-config', default=config.qsiprep_command(),
        help='Config file for custom qsiprep command.')
    parser_process.add_argument('--no-gpu', action='store_true',
        help='Run prequal and qsiprep without gpu functionality.')
    parser_process.add_argument('--sub-tasks', nargs='+', default=['prequal', 'qsiprep'],
        help='Run only certain sub tasks')
    parser_process.add_argument('--fs-license', required=True,
        help='Base64 encoded FreeSurfer license file')
    parser_process.add_argument('--xnat-alias',
        help='YAXIL authentication alias')
    parser_process.add_argument('--xnat-host',
        help='XNAT host')
    parser_process.add_argument('--xnat-user',
        help='XNAT username')
    parser_process.add_argument('--xnat-pass',
        help='XNAT password')
    parser_process.add_argument('--artifacts-dir',
        help='Location for generated assessors and resources')
    parser_process.add_argument('--custom-eddy-qsiprep',
        help='Feed in path to customized eddy parameters file for qsiprep.')
    parser_process.add_argument('--custom-eddy-prequal_stdev', default='6',
        help='Feed in path to customized eddy parameters file for prequal.')
    parser_process.add_argument('--xnat-upload', action='store_true',
        help='Upload results to XNAT over REST API')
    parser_process.add_argument('--container-dir',
        help='Pass path to downloaded DWIQC containers')
    parser_process.add_argument('--exclude-nodes', nargs='+',
        help='List of cluster nodes to exclude from use.')
    parser_process.add_argument('--work-dir',
        help='Working directory that is shared across compute cluster')
    parser_process.add_argument('--truncate-qsiprep-fmap', action='store_true',
        help='Truncate the fmap created from the main diffusion scan to just one b0 volume.')
    parser_process.set_defaults(func=cli.process.do)

    # tandem mode
    parser_tandem = subparsers.add_parser('tandem', help='tandem -h')
    parser_tandem.add_argument('--label', required=True,
        help='XNAT MR Session name')
    parser_tandem.add_argument('--project',
        help='XNAT Project name')
    parser_tandem.add_argument('--download-config', required=True,
        help='dwiqc XNAT configuration file')
    parser_tandem.add_argument('--bids-dir', required=True,
        help='Output BIDS directory')
    parser_tandem.add_argument('--run', default=1, type=int,
        help='BIDS run')
    parser_process.add_argument('--output-resolution',
        help='Resolution of output data. Default is resolution of input data.')
    parser_tandem.add_argument('--partition', required=True,
        help='Job scheduler partition')
    parser_tandem.add_argument('--scheduler', default=None,
        help='Choose a specific job scheduler')
    parser_tandem.add_argument('--rate-limit', type=int, default=None, 
        help='Rate limit the number of tasks executed in parallel (1=serial)')
    parser_tandem.add_argument('--dry-run', action='store_true',
        help='Do not execute any jobs')
    parser_tandem.add_argument('--prequal-config', default=config.prequal_command(),
        help='Config file for custom prequal command.')
    parser_tandem.add_argument('--qsiprep-config', default=config.qsiprep_command(),
        help='Config file for custom qsiprep command.')
    parser_tandem.add_argument('--no-gpu', action='store_true',
        help='Run prequal and qsiprep without gpu functionality.')
    parser_tandem.add_argument('--sub-tasks', nargs='+', default=['prequal', 'qsiprep'],
        help='Run only certain sub tasks')
    parser_tandem.add_argument('--fs-license', required=True,
        help='Base64 encoded FreeSurfer license')
    parser_tandem.add_argument('--xnat-alias',
        help='YAXIL authentication alias')
    parser_tandem.add_argument('--xnat-host',
        help='XNAT host')
    parser_tandem.add_argument('--xnat-user',
        help='XNAT username')
    parser_tandem.add_argument('--xnat-pass',
        help='XNAT password')
    parser_tandem.add_argument('--tagger-config', default=tagger_config.default(),
        help='Path to xnattagger config file')
    parser_tandem.add_argument('--run-tagger', action='store_true', default=False,
        help='Run xnattagger')
    parser_tandem.add_argument('--artifacts-dir',
        help='Location for generated assessors and resources')
    parser_tandem.add_argument('--custom-eddy-qsiprep',
        help='Feed in path to customized eddy parameters file for qsiprep.')
    parser_tandem.add_argument('--custom-eddy-prequal_stdev', default='6',
        help='Feed in path to customized eddy parameters file for prequal.')
    parser_tandem.add_argument('--xnat-upload', action='store_true',
        help='Upload results to XNAT over REST API')
    parser_tandem.add_argument('--container-dir',
        help='Pass path to downloaded DWIQC containers')
    parser_tandem.add_argument('--exclude-nodes', nargs='+',
        help='List of cluster nodes to exclude from use.')
    parser_tandem.add_argument('--work-dir',
        help='Working directory that is shared across compute cluster')
    parser_tandem.add_argument('--in-mem', action='store_true', default=False,
        help='Tell yaxil to download data in memory. This can help with download speeds')
    parser_tandem.add_argument('--truncate-qsiprep-fmap', action='store_true',
        help='Truncate the fmap created from the main diffusion scan to just one b0 volume.')
    parser_tandem.set_defaults(func=cli.tandem.do)
    args = parser.parse_args()


    configure_logging(args.verbose)
    logger.info('Welcome to dwiQC version %s', dwiqc.version())

    # fire parser_*.set_defaults(func=<function>)
    args.func(args)

def configure_logging(verbose):
    level = logging.INFO
    if verbose:
        level = logging.DEBUG
    logging.basicConfig(
        level=level,
        format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

if __name__ == '__main__':
   main()
