#!/usr/bin/python
#
"""Setup.py: build, distribute, clean."""

from distutils.core import setup

PROJECT_NAME = 'hydra-slave'
VERSION = '0.2'

scripts = [
    'bin/hydra-slave',
]

data_files = [
    ('/etc', ['etc/hydra-slave.conf']),
]

setup(name=PROJECT_NAME,
      version=VERSION,
      description='Hydra slave daemon',
      author='Johannes Morgenroth',
      author_email='morgenroth@ibr.cs.tu-bs.de',
      maintainer='Johannes Morgenroth',
      maintainer_email='morgenroth@ibr.cs.tu-bs.de',
      long_description='The hydra slave daemon is part of the hydra emulation framework for large-scale software testing in disrupted networks.',
      scripts=scripts,
      packages=['hydraslave'],
      license='GPL v3',
      data_files=data_files,
     )

