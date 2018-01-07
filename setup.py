#!/usr/bin/env python3

from setuptools import setup
import platform

import magnetometer
from magnetometer.config import BaseConfig

with open("README.md") as readme_file:
    readme = readme_file.read()

__version__ = magnetometer.__version__

# prerequisites from pypi
requirements = [
    "appdirs",
    "datalog",
    "bottle",
    "pyftpsync==2.0.0"
]

# data files
data_files = []

# operating system
distro_name = platform.dist()[0]
distro_version = float(platform.dist()[1])

# add systemd service files if supported
if (distro_name == "debian" and distro_version >= 7.0) or (
    distro_name == "Ubuntu" and distro_version >= 16.04):
        # add systemd service files
        data_files.append(('/etc/systemd/system',
                           ['magnetometer-server.service',
                            'magnetometer-ftp.service']))

setup(
    name="Magnetometer",
    version=__version__,
    description="Python scripts to operate the University of Glasgow observatory magnetometer",
    long_description=readme,
    author="Sean Leavey",
    author_email="magnetometer@attackllama.com",
    url="https://github.com/acrerd/magnetometer",
    packages=[
        "magnetometer"
    ],
    package_data={
        "": ["README.md", "magnetometer-server.service",
             "magnetometer-ftp.service"],
        "magnetometer": ["server.conf.dist", "ftp.conf.dist"],
    },
    data_files=data_files,
    entry_points={
        'console_scripts': [
            'magnetometer-server = magnetometer.server:run',
            'magnetometer-ftp = magnetometer.ftp:run'
        ]
    },
    install_requires=requirements,
    license="GPLv3",
    zip_safe=False,
    classifiers=[
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5"
    ]
)
