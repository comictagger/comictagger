[![Build Status](https://travis-ci.org/comictagger/comictagger.svg?branch=develop)](https://travis-ci.org/comictagger/comictagger)
[![Gitter chat](https://badges.gitter.im/gitterHQ/gitter.png)](https://gitter.im/comictagger/community)
[![Google Group](https://img.shields.io/badge/discuss-on%20groups-%23207de5)](https://groups.google.com/forum/#!forum/comictagger)
[![Twitter](https://img.shields.io/badge/%40comictagger-twitter-lightgrey)](https://twitter.com/comictagger)
[![Facebook](https://img.shields.io/badge/comictagger-facebook-lightgrey)](https://www.facebook.com/ComicTagger-139615369550787/)

# ComicTagger

ComicTagger is a **multi-platform** app for **writing metadata to digital comics**, written in Python and PyQt.

![ComicTagger logo](https://raw.githubusercontent.com/comictagger/comictagger/develop/comictaggerlib/graphics/app.png)

## Features

* Runs on macOS, Microsoft Windows, and Linux systems
* Get comic information from [Comic Vine](https://comicvine.gamespot.com/)
* **Automatic issue matching** using advanced image processing techniques
* **Batch processing** in the GUI for tagging hundreds or more comics at a time
* Support for **ComicRack** and **ComicBookLover** tagging formats
* Native full support for **CBZ** digital comics
* Native read only support for **CBR** digital comics: full support enabled installing additional [rar tools](https://www.rarlab.com/download.htm)
* Command line interface (CLI) enabling **custom scripting** and **batch operations on large collections**

For details, screen-shots, release notes, and more, visit [the Wiki](https://github.com/comictagger/comictagger/wiki)


## Installation

### Binaries

Windows and macOS binaries are provided in the [Releases Page](https://github.com/comictagger/comictagger/releases). 

Just unzip the archive in any folder and run, no additional installation steps are required.

### PIP installation

A pip package is provided, you can install it with:

```
 $ pip3 install comictagger[GUI]
```

### From source

 1. Ensure you have a recent version of python3 installed
 2. Clone this repository `git clone https://github.com/comictagger/comictagger.git`
 3. `pip3 install -r requirements_dev.txt`
 4. Optionally install the GUI `pip3 install -r requirements-GUI.txt`
 5. Optionally install CBR support `pip3 install -r requirements-CBR.txt`
 6. `python3 comictagger.py`
