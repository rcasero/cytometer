#!/usr/bin/env python
# This Python file uses the following encoding: utf-8

from setuptools import setup
from setuptools import find_packages

setup(name='cytometer',
      version='0.1.0',
      description='Cell segmentation and quantification',
      author='Ramón Casero',
      author_email='rcasero@gmail.com',
      url='http://phobos.mrch.har.mrc.ac.uk/r.casero/cytometer/',
      license='GPLv3',
      packages=find_packages(),
      data_files=[('data', ['data/*'])],
      install_requires=['python>=3.6', 'gcc>=4.8.5',
                            'keras>=2.0.8', 'theano>=0.10.0', 'tensorflow-gpu>=1.3.0', 'pysto>=1.1.1',
                            'pyyaml>=3.12', 'nose-parameterized>=0.6.0']
     )
