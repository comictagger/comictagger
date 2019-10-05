[![Build Status](https://travis-ci.org/davide-romanini/comictagger.svg?branch=develop)](https://travis-ci.org/davide-romanini/comictagger)

# ComicTagger

ComicTagger is a **multi-platform** app for **writing metadata to digital comics**, written in Python and PyQt.

![ComicTagger logo](comictaggerlib/graphics/app.png?raw=true)

## Features

* Runs on macOS, Microsoft Windows, and Linux systems
* Get comic information from [Comic Vine](https://comicvine.gamespot.com/)
* **Automatic issue matching** using advanced image processing techniques
* **Batch processing** in the GUI for tagging hundreds or more comics at a time
* Support for **ComicRack** and **ComicBookLover** tagging formats
* Native full support for **CBZ** digital comics
* Native read only support for **CBR** digital comics: full support enabled installing additional [rar tools](https://www.rarlab.com/download.htm)
* Command line interface (CLI) enabling **custom scripting** and **batch operations on large collections**

For details, screen-shots, release notes, and more, visit [the Wiki](https://github.com/davide-romanini/comictagger/wiki)


## Installation

### Binaries

Windows and macOS binaries are provided in the [Releases Page](https://github.com/davide-romanini/comictagger/releases). 

Just unzip the archive in any folder and run, no additional installation steps are required.

### PIP installation

A pip package is provided, you can install it with:

```
 $ pip install comictagger
```

### From source

 1. ensure you have a recent version of python3 and setuptools installed
 2. clone this repository `git clone https://github.com/davide-romanini/comictagger.git`
 3. `pip install -r requirements.txt`
 4. `python comictagger.py`