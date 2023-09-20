import os
from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))

requires = [
    'yaxil>=0.9.8',
    'pyaml',
    'xnattagger>=0.4.13',
    'PyBIDS',
    'executors==0.6a1',
    'selfie',
    'lxml',
    'numpy',
    'dcm2niix',
    'tenacity',
    'nibabel'
]

about = dict()
with open(os.path.join(here, 'dwiqc', '__version__.py'), 'r') as f:
    exec(f.read(), about)

setup(
    name=about['__title__'],
    version=about['__version__'],
    description=about['__description__'],
    author=about['__author__'],
    author_email=about['__author_email__'],
    url=about['__url__'],
    packages=find_packages(),
    package_data={
        '': ['*.yaml']
    },
    include_package_data=True,
    scripts=[
        'scripts/dwiQC.py'
    ],
    install_requires=requires
)
