from __future__ import print_function, division

import sys
import time

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

def convert_to_list(csv):
    """Converts a simple CSV-like string to a list"""

    # empty data
    data = []

    # loop over lines
    for line in csv.split("\n"):
        # append list containing columns
        data.append(line.split(","))

    return data

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

# get stream start timestamp
start_time = int(server.get_command_response("streamstarttimestamp"))

# set sleep time
sleep_time = 10

# default timestamp
timestamp = 0

# check buffer length is adequate
# number of channels in ADC * length of a long int in string form + commas and
# newline required
if server.buffer_length < Channel.MAX_ANALOG_CHANNEL * 11 \
+ Channel.MAX_ANALOG_CHANNEL + 1:
    raise Exception("The socket buffer length must be long enough to receive \
at least one complete reading")

# get enabled channels
channels = server.get_command_response("enabledchannels").split(",")

# number of enabled channels
enabled_channels = len(channels)

# get channel conversion factors
conversion = []

for channel in channels:
    conversion.append(float(server.get_command_response(\
    "voltsconversion {0}".format(channel))))

# the length of the last line of the data payload
last_line_length = None

# now loop, printing the data received from the ADC
while True:
    # sleep for specified time
    time.sleep(sleep_time)
    
    # get data
    data = server.get_command_response("dataafter {0}".format(timestamp))

    # only do something if the data is useful
    if data is not None:
        # convert data to CSV
        datalist = convert_to_list(data)

        # check if we have data and it is valid
        if datalist is None or len(datalist) == 0:
            print("Data appears to be invalid: {0}".format(data))

            continue

        # delete last row to prevent buffer overflow issues
        del(datalist[-1])
        
        # without the last entry, do we have any new readings?
        if len(datalist) < 1:
            # skip this iteration
            continue

        # loop over data, converting the counts to volts
        for i in xrange(len(datalist)):
            # check the length is consistent (enabled_channels + 1 to
            # include time)
            if len(datalist[i]) is not enabled_channels + 1:
                print("Number of samples in reading {0} is not consistent \
with enabled channels".format(i))

                continue

            # scale to volts
            readings = [int(sample) * factor for sample, factor \
            in zip(datalist[i][1:], conversion)]

            # scale to nanotesla and degrees
            readings = calibration.scale_magnetometer_data(readings)

            # save the readings
            datalist[i][1:] = readings

        # update timestamp
        timestamp = datalist[-1][0]

        # write data to appropriate file
        fileio.save_readings(basepath, start_time, datalist)
    else:
        print("Skipped empty data from server. Timestamp: {0}, \
received data: {1}".format(timestamp, data))