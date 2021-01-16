import codecs
import os

from setuptools import find_packages, setup

VERSION = "1.0.0"
AUTHOR = "Free Law Project"
EMAIL = "info@free.law"
HERE = os.path.abspath(os.path.dirname(__file__))

with open("requirements.txt") as f:
    required = f.read().splitlines()


def read(*parts):
    """
    Build an absolute path from *parts* and and return the contents of the
    resulting file.  Assume UTF-8 encoding.
    """
    with codecs.open(os.path.join(HERE, *parts), "rb", "utf-8") as f:
        return f.read()


setup(
    name="eyecite",
    description="A citation extraction tool.",
    license="BSD",
    url="https://github.com/freelawproject/eyecite",
    version=VERSION,
    author=AUTHOR,
    author_email=EMAIL,
    maintainer=AUTHOR,
    maintainer_email=EMAIL,
    keywords=["legal", "citations", "cites"],
    long_description=read("README.rst"),
    packages=find_packages(exclude=("tests",)),
    package_data={"eyecite": ["*.json"]},
    include_package_data=True,
    classifiers=[
        "Development Status :: 1 - Planning",
        "Intended Audience :: Developers",
        "Natural Language :: English",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    install_requires=required,
    test_suite="tests",
)
