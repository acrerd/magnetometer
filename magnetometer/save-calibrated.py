from __future__ import print_function, division

import sys
import time

from picolog.data import DataStore
from picolog.network import ServerSocket
from picolog.constants import Channel
import calibration
import fileio

"""
Saves magnetometer data calibrated in nT.

Run with `python save-calibrated.py <host> <port> <path>`

The PicoLog ADC utilities software (https://github.com/SeanDS/picolog-adc-python)
must be on your Python path.

Sean Leavey
https://github.com/SeanDS/
"""

def print_usage():
    """Prints usage instructions"""

    # print instructions
    print("Usage: python save-calibrated.py <host> <port> <path>")

    # exit program
    exit(0)

# get arguments
try:
    host = sys.argv[1]
    port = int(sys.argv[2])
    basepath = sys.argv[3]
except:
    print_usage()

# create a new server socket instance
server = ServerSocket(host, port)

# get sample time, in ms
sample_time = int(server.get_command_response("sampletime"))

# set sleep time
sleep_time = 10

# default timestamp
timestamp = 0

# get enabled channels
channels = server.get_command_response("enabledchannels").split(",")

# number of enabled channels
enabled_channels = len(channels)

# set channel conversion factors
calibration.conversion = [float(server.get_command_response( \
"voltsconversion {0}".format(channel))) for channel in channels]

# now loop, printing the data received from the ADC
while True:
    # sleep for specified time
    time.sleep(sleep_time)

    # get data
    data = server.get_command_response("dataafter {0}".format(timestamp))

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

        # write data to appropriate file
        fileio.save_readings(basepath, datastore)
    else:
        print("Skipped empty data from server [timestamp = {0}]".format( \
        timestamp, data))
