# Magnetometer
Scripts to operate and log data from the Acre Road magnetometer.

## Requirements ##
You must have the [Python PicoLog ADC library](https://github.com/SeanDS/picolog-adc-python) on your PYTHONPATH. It
has its own set of prerequisites.

## Quick Start ##
Run `save-calibrated.py` with `<host>`, `<port>` and `<path>` arguments to specify the [PicoLog ADC server](https://github.com/SeanDS/picolog-adc-python) host and port and the directory in which to create the data archive. For example:

```bash
python save-calibrated localhost 50000 data
```

will start logging data from the server running on `localhost` port `50000` into the `data` directory.

Sean Leavey  
https://github.com/SeanDS/
