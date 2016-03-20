from __future__ import print_function, division

import sys
import time
import ConfigParser

from picolog.data import DataStore
from picolog.network import ServerSocket
from picolog.constants import Channel
import calibration
from destinations import DataServer, ConnectionException

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

# create new data server instance
send_server = DataServer(config.get('destination', 'host'), \
config.get('destination', 'port'), config.get('destination', 'base_path'), \
config.get('destination', 'key'), config.get('destination', 'timeout'))

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

    # get the client's last data point
    try:
        last_data_time = send_server.get_latest_time()
    except ConnectionException as e:
        print(e)

        # skip this iteration
        continue

    # get timestamp from datetime object
    last_data_timestamp = time.mktime(last_data_time.timetuple())

    # get data
    try:
        data = server.get_command_response("dataafter {0}".format( \
        str(last_data_timestamp)))
    except Exception as e:
        print(e)

        # skip this iteration
        continue

    # only do something if the data is useful
    if data is None:
        print("Skipped empty data from server [timestamp = {0}]".format( \
        timestamp))

        # skip this iteration
        continue

    # create datastore
    try:
        datastore = DataStore.instance_from_json(data, \
        conversion_callbacks=[calibration.scale_counts_to_volts, \
        calibration.scale_volts_to_nt_and_degrees])
    except Exception as e:
        print("Data \"{0}\" appears to be invalid: {1}".format(data, e))

        # skip this iteration
        continue

    # do we have any new readings?
    if len(datastore.readings) < 1:
        # skip this iteration
        continue

    # send data to server
    try:
        send_server.send_datastore(datastore)
    except ConnectionException as e:
        print("Error processing dataafter {0}: {1}".format(timestamp, e))
