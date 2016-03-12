from __future__ import print_function, division

import sys
import os
import datetime
import urllib
import httplib

"""File I/O functions"""

def save_readings(basepath, datastore):
    """Saves the readings to the specified path, in a directory representing \
    its date

    This method only works if the readings are in chronological order. If the
    readings aren't, then they will be saved in incorrect locations and order.

    :param basepath: base path to save reading directory structure in
    :param datastore: datastore to save
    """

    # last time (by default, the first time)
    last_time = datetime.datetime.utcfromtimestamp( \
    int(datastore.readings[0].reading_time) / 1000)

    # open up file for first reading
    f = open_with_create(get_storage_path(basepath, last_time), "a")

    # loop over readings
    for reading in datastore.readings:
        # create date object from reading time
        this_time = datetime.datetime.utcfromtimestamp( \
        int(reading.reading_time) / 1000)

        # have we passed midnight?
        if this_time.date() > last_time.date():
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
        reading.reading_time = int(delta.seconds * 1000 + delta.microseconds / 1000)

        # write data to file, forcing floating point format
        f.write(reading.whitespace_repr() + "\n")

	# update last time
	last_time = this_time

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
    time_obj.strftime("%m"), filename)

    return path

def send_to_server(datastore, config):
    """Sends the data in the specified datastore to the server in the config

    :param datastore: datastore to send
    :param config: config settings for destination
    """

    # create path with GET key
    path = config.get('destination', 'path') + "?" \
    + config.get('destination', 'key')

    # get URL-encoded data
    data = urllib.urlencode({'data': datastore.json_repr()})

    # create connection
    connection = httplib.HTTPConnection(config.get('destination', 'host'), \
    int(config.get('destination', 'port')), \
    timeout=int(config.get('destination', 'timeout')))

    # create headers
    headers = {"Content-type": "application/x-www-form-urlencoded", \
    "Accept": "text/plain"}

    # make request
    connection.request('POST', path, data, headers)

    # response
    response = connection.getresponse()

    # check response
    if response.status is not 200:
        raise Exception('There was an issue sending data: {0}'.format(response))
