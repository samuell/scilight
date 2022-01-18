import os
import sys

try:
    from setuptools import setup
except:
    from distutils.core import setup

with open("README.md") as fh:
    long_description = fh.read()

setup(
    name="scilight",
    version="0.5.0",
    description="Workflow library in pure python, for executing shell commands saving data to the file system without re-executing already executed tasks.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Samuel Lampa",
    author_email="samuel.lampa@rilnet.com",
    url="https://github.com/samuell/scilight",
    license="MIT",
    keywords="workflows workflow pipeline task",
    packages=[
        "scilight",
    ],
    install_requires=[],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
    ],
)
