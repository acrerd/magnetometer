from __future__ import print_function, division

import sys
import os
import datetime

"""File I/O functions"""

def save_readings(basepath, stream_start_timestamp, readings):
    """Saves the readings to the specified path, in a directory representing \
    its date

    This method only works if the readings are in chronological order. If the
    readings aren't, then they will be saved in incorrect locations and order.
    """

    # last time (by default, the first time)
    last_time = datetime.datetime.utcfromtimestamp( \
    (int(readings[0][0]) + stream_start_timestamp) / 1000)

    # open up file for first reading
    f = open_with_create(get_storage_path(basepath, last_time), "a")

    # loop over readings
    for reading in readings:
        # create date object from reading time
        this_time = datetime.datetime.utcfromtimestamp( \
        (int(reading[0]) + stream_start_timestamp) / 1000)

        if (this_time - last_time).days > 0:
            # new day - open a new file

            # close current file
            f.close()

            # open new one
            f = open_with_create(get_storage_path(basepath, this_time), "a")

        # this time tuple
        this_time_tuple = this_time.timetuple()

        # date delta since midnight
        delta = (this_time - datetime.datetime(*this_time_tuple[0:3]))

        # replace time with ms since midnight
        reading[0] = int(delta.seconds * 1000 + delta.microseconds / 1000)

        # write data to file, forcing floating point format
        f.write(" ".join([str(column) for column in reading]) + "\n")

    # close file pointer
    f.close()

def open_with_create(path, mode):
    """Opens a file at the specified path, creating directories as necessary"""

    # from http://stackoverflow.com/questions/12517451/python-automatically-creating-directories-with-file-output
    if not os.path.exists(os.path.dirname(path)):
        try:
            os.makedirs(os.path.dirname(path))
        except OSError as exc: # Guard against race condition
            if exc.errno != errno.EEXIST:
                raise

    return open(path, mode)

def get_storage_path(basepath, time_obj):
    """Returns a file path for the given timestamp"""

    # filename
    filename = time_obj.strftime("%Y-%m-%d.txt")

    # full path
    path = os.path.join(basepath, time_obj.strftime("%Y"), \
    time_obj.strftime("%m"), time_obj.strftime("%d"), filename)

    return path
