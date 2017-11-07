# Magnetometer
Scripts to operate and log data from the Acre Road magnetometer.

## Requirements
  * Python 3.5+
  * [DataLog](https://github.com/SeanDS/datalog)
  * python3-dev
  * libssl-dev
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
This will handle Python dependency installation, but not system prerequisites
as listed above (e.g. `libssl-dev`). Be sure to first install these using your
system package manager.

The software can be later upgraded with:
```bash
pip3 install git+https://github.com/acrerd/magnetometer.git --upgrade
```

## Usage
The magnetometer server and FTP client can be run from the terminal, although
it is not recommended. To run the server in a terminal, type:
```bash
magnetometer-server
```
To do the same for the FTP client:
```bash
magnetometer-ftp
```

The best way to run the system on supported platforms is with a `systemd`
service. This is currently supported for Debian 7.0+, Ubuntu 16.04+ and
Raspbian derivatives.

The service configurations are installed automatically on supported platforms;
however, in order to enable the services on boot, you must activate them:
```bash
sudo systemctl enable magnetometer-server
sudo systemctl enable magnetometer-ftp
```

You can then start them immediately with the following, though it is recommended
to first configure the software (see below):
```bash
sudo systemctl start magnetometer-server
sudo systemctl start magnetometer-ftp
```

The configuration files are located at `~/.config/magnetometer/server.conf` and
`~/.config/magnetometer/ftp.conf` on most Debian-based operating systems. These
contain parameters for setting the server, FTP, logging and other behaviours.
Note that they are not created until the programs are first executed. Note: as
the services are run as root, the configuration files listed above will be
at the locations `/root/config/magnetometer`.

Sean Leavey  
https://github.com/SeanDS/
