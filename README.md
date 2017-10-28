# Magnetometer
Scripts to operate and log data from the Acre Road magnetometer.

## Requirements
  * Python 3.5+
  * [DataLog](https://github.com/SeanDS/datalog)
  * libffi-dev
  * bottle
  * appdirs
  * pyftpsync

You must have the [DataLog library](https://github.com/SeanDS/datalog),
installed via `pip`, as well as `libffi-dev`, installed e.g. via `apt-get`.
After that, installation is easily achieved via `pip`.

## Installation
Installation is handled by `setup.py`. This is most easily handled by `pip`:
```bash
pip3 install git+https://github.com/acrerd/magnetometer.git
```

## Quick Start
Run in a terminal:
```bash
magnetometer
```

The configuration file is located at `~/.config/magnetometer/magnetometer.conf`
on most Debian-based operating systems. This contains parameters for setting the
server, FTP, logging and other behaviours.

Sean Leavey  
https://github.com/SeanDS/
