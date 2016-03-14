from __future__ import print_function, division

import sys
import time
import ConfigParser

from picolog.data import DataStore
from picolog.network import ServerSocket
from picolog.constants import Channel
import calibration
import destinations

"""
Sends calibrated magnetometer data to the web server.

Run with `python send-calibrated.py <config path>``

The PicoLog ADC utilities software (https://github.com/SeanDS/picolog-adc-python)
must be on your Python path.

Sean Leavey
https://github.com/SeanDS/
"""

def print_usage():
    """Prints usage instructions"""

    # print instructions
    print("Usage: python send-calibrated.py <config path>")

    # exit program
    exit(0)

# get arguments
try:
    config_path = sys.argv[1]
except:
    print_usage()

###
# Config
config = ConfigParser.RawConfigParser()
config.read(config_path)

# create a new server socket instance
server = ServerSocket(config.get('source', 'host'), \
config.get('source', 'port'))

# set sleep time
sleep_time = 10

# default timestamp
timestamp = 0

# get enabled channels
channels = server.get_command_response("enabledchannels").split(",")

# set channel conversion factors
calibration.conversion = [float(server.get_command_response( \
"voltsconversion {0}".format(channel))) for channel in channels]

# now loop, sending the data received from the ADC to the remote server
while True:
    # sleep for specified time
    time.sleep(sleep_time)

    # get data
    try:
        data = server.get_command_response("dataafter {0}".format(timestamp))
    except Exception:
        # skip this iteration
        continue

    # only do something if the data is useful
    if data is not None:
        # create datastore
        try:
            datastore = DataStore.instance_from_json(data, \
            conversion_callbacks=[calibration.scale_counts_to_volts, \
            calibration.scale_volts_to_nt_and_degrees])
        except Exception:
            print("Data appears to be invalid: {0}".format(data))

            continue

        # do we have any new readings?
        if len(datastore.readings) < 1:
            # skip this iteration
            continue

        # update timestamp
        timestamp = datastore.readings[-1].reading_time

        # send data to server
        try:
            destinations.send_to_server(datastore, config)
        except Exception as e:
            print("Error processing dataafter {0}: {1}".format(timestamp, e))
    else:
        print("Skipped empty data from server [timestamp = {0}]".format( \
        timestamp))
