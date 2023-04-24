#!/usr/bin/env python




import sys
sys.path.insert(0, 'PATH to cli folder')
import get
import logging
import argparse as ap
#import dwiqc.cli as cli
#import dwiqc.config as config

logger = logging.getLogger(__name__)




def main():
    parser = ap.ArgumentParser()
    parser.add_argument('-v', '--verbose', action='store_true',
        help='Enable verbose logging')
    parser.add_argument('-c', '--config', #default=config.default(),
        help='dwiQC configuration file')
    parser.add_argument('--insecure', action='store_true',
        help='Disable SSL certificate verification')
    subparsers = parser.add_subparsers(help='sub-command help')
    # get mode
    parser_get = subparsers.add_parser('get', help='get -h')
    parser_get.add_argument('--label', required=True,
        help='XNAT MR Session name')
    parser_get.add_argument('--project',
        help='XNAT Project name')
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
    parser_get.add_argument('--dry-run', action='store_true',
        help='Do not execute any jobs')
    parser_get.set_defaults(func=get.do) #(func=cli.get.do)

    args = parser.parse_args()


    configure_logging(args.verbose)
    #logger.info('Welcome to dwiQC version %s', dwiqc.version())

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
