# Setup file for comictagger python source  (no wheels yet)
#
# An entry point script called "comictagger" will be created
#
# Currently commented out, an experiment at desktop integration.
# It seems that post installation tweaks are broken by wheel files.
# Kept here for further research

import glob
import os

from setuptools import setup


def read(fname):
    """
    Read the contents of a file.
    Parameters
    ----------
    fname : str
        Path to file.
    Returns
    -------
    str
        File contents.
    """
    with open(os.path.join(os.path.dirname(__file__), fname)) as f:
        return f.read()


install_requires = read("requirements.txt").splitlines()

# Dynamically determine extra dependencies
extras_require = {}
extra_req_files = glob.glob("requirements-*.txt")
for extra_req_file in extra_req_files:
    name = os.path.splitext(extra_req_file)[0].replace("requirements-", "", 1)
    extras_require[name] = read(extra_req_file).splitlines()

# If there are any extras, add a catch-all case that includes everything.
# This assumes that entries in extras_require are lists (not single strings),
# and that there are no duplicated packages across the extras.
if extras_require:
    extras_require["all"] = sorted({x for v in extras_require.values() for x in v})


setup(
    name="comictagger",
    install_requires=install_requires,
    extras_require=extras_require,
    python_requires=">=3",
    description="A cross-platform GUI/CLI app for writing metadata to comic archives",
    author="ComicTagger team",
    author_email="comictagger@gmail.com",
    url="https://github.com/comictagger/comictagger",
    packages=["comictaggerlib", "comicapi"],
    package_data={
        "comictaggerlib": ["ui/*", "graphics/*"],
    },
    entry_points=dict(console_scripts=["comictagger=comictaggerlib.main:ctmain"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Environment :: Win32 (MS Windows)",
        "Environment :: MacOS X",
        "Environment :: X11 Applications :: Qt",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: Apache Software License",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Topic :: Utilities",
        "Topic :: Other/Nonlisted Topic",
        "Topic :: Multimedia :: Graphics",
    ],
    keywords=["comictagger", "comics", "comic", "metadata", "tagging", "tagger"],
    license="Apache License 2.0",
    long_description=read("README.md"),
    long_description_content_type='text/markdown'
)
