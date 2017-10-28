#!/usr/bin/env python3

from setuptools import setup

import magnetometer

with open("README.md") as readme_file:
    readme = readme_file.read()

__version__ = magnetometer.__version__

requirements = [
    "DataLog",
    "bottle",
    "pyftpsync"
]

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
        "magnetometer": ["magnetometer.conf.dist"]
    },
    entry_points={
        'console_scripts': [
            'magnetometer = magnetometer.magnetometer:run'
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
