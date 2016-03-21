from __future__ import print_function, division

import sys
import os
import datetime
import urllib
import httplib
import socket

"""Network and local I/O functions"""

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

class Server(object):
    """Represents a server to send data to"""

    """Host"""
    host = None

    """Port"""
    port = None

    """Base path"""
    base_path = None

    """Key"""
    key = None

    """Timeout"""
    timeout = None

    """Connection"""
    connection = None

    def __init__(self, host, port, base_path, key, timeout=5):
        self.host = host
        self.port = port
        self.base_path = base_path
        self.key = key
        self.timeout = timeout

    def create_path_string(self, path, parameters):
        """Creates a path string using the specified base path and additional \
        arguments, transparently adding the key

        :param path: path, without arguments
        :param parameters: dict containing additional arguments
        """

        # create full path
        full_path = "{0}/{1}".format(self.base_path, path)

        # return GET string
        return "{0}?{1}".format(full_path, "&".join( \
        ["{0}={1}".format(key, value) for key, value in parameters.items()]))

    def _get_connection(self):
        # debug output
        httplib.HTTPConnection.debuglevel = 1

        # get connection, with same timeout as socket
        connection = httplib.HTTPConnection(self.host, int(self.port), \
        timeout=int(self.timeout))
	
	# set the socket timeout (necessary for _proper_ timeout handling,
        # otherwise the above timeout setting is ignored in favour of a usually
        # shorter socket timeout)
        connection.sock.settimeout(int(self.timeout))
	
	return connection

    def get(self, path, connection=None, parameters={}, **kwargs):
        """Returns the response to the specified command"""

        # create the path
        full_path = self.create_path_string(path, parameters)

        # whether to close connection
        close_connection = False

        # create connection if necessary
        if connection is None:
            # create a new connection
            connection = self._get_connection()

            # close the connection
            close_connection = True

        # get the response
        response = self._get_response(full_path, connection, **kwargs)

        # return response status and message
        response_info = (response.status, response.read())

        # close the connection
        if close_connection:
            connection.close()

        return response_info

    def put(self, data, path, connection=None, parameters={}, **kwargs):
        """Returns the respose to the specified command containing PUSH data

        :param data: data dict to send to the server
        """

        # create the path
        full_path = self.create_path_string(path, parameters)

        # whether to close connection
        close_connection = False

        # create connection if necessary
        if connection is None:
            # create a new connection
            connection = self._get_connection()

            # close the connection
            close_connection = True

        # get the response
        response = self._put_response(data, full_path, connection, **kwargs)

        # return response status and message
        response_info = (response.status, response.read())

        # close the connection
        if close_connection:
            connection.close()

        return response_info

    def puts(self, data, parameters={}, headers={}, **kwargs):
        """Returns responses to the specified command for each set of data \
        provided, using the same connection

        :param data: list of dicts containing the path and data to send
        """

        # create a persistent connection
        connection = self._get_connection()

        # set keep-alive clause to the headers
        headers["Connection"] = "keep-alive"

        # loop over data, getting responses
        responses = [self.put(row["data"], row["path"], connection, parameters, \
        **kwargs) for row in data]

        # close the connection
        connection.close()

        # return the list of responses
        return responses

    def _get_response(self, full_path, connection, **kwargs):
        """Returns the response to the specified command"""

        # get response
        return self._get_request(full_path, connection, **kwargs)

    def _put_response(self, data, full_path, connection, **kwargs):
        """Returns the respose to the specified command containing PUT data

        :param data: data dict to send to the server
        """

        # get response
        return self._put_request(full_path, connection, data, **kwargs)

    def _get_request(self, full_path, connection, **kwargs):
        """Returns the server's message and status to the specified command \
        using an HTTP GET request.

        :param path: GET path
        :param connection: connection to use
        """

        # make request
        connection.request("GET", full_path, **kwargs)

        # return the response
        return connection.getresponse()

    def _put_request(self, full_path, connection, data, **kwargs):
        """Returns the server's message and status to the specified data.

        Uses the specified connection if not None.

        :param full_path: URL path
        :param connection: connection to use
        :param data: data to send
        """

        # make request
        connection.request("PUT", full_path, data, **kwargs)

        # return the response
        return connection.getresponse()

    def default_parameters(self):
        """Returns the default parameters dict"""

        # empty
        return {}

class DataServer(Server):
    """Represents a data server"""

    """Data command"""
    DATA_COMMAND = "data"

    """Latest data command"""
    LATEST_DATA_COMMAND = "data/latest"

    """Timestamp command"""
    TIMESTAMP_COMMAND = "timestamp"

    def send_datastore(self, datastore):
        """Sends the data in the specified datastore to the server

        :param datastore: datastore to send
        """

        # get parameters
        parameters = self.default_parameters()

        # create JSON header
        headers = {"Content-Type": "application/json"}

        # create list of dicts representing each reading
        data = [{"data": reading.json_repr(), \
        "path": "{0}/{1}/{2}".format(str(self.key), self.DATA_COMMAND, \
        str(reading.reading_time))} for reading in datastore.readings]

        # get responses
        responses = self.puts(data, parameters, headers)

        # check the responses are all 201
        for status, message in responses:
            # check if there was a problem
            if status is not 201:
                raise ConnectionException("There was a problem with the request: \
    [{0}] {1}".format(status, message))

        # if we get this far without an exception, everything was ok
        # return the number of successful responses
        return len(responses)

    def get_latest_time(self):
        """Gets the datetime of the server's latest data"""

        # get timestamp response
        status, message = self.get("{0}/{1}/{2}".format(str(self.key), \
        self.LATEST_DATA_COMMAND, self.TIMESTAMP_COMMAND))

        # check response
        if status is not 200:
            raise ConnectionException("There was a problem with the request: \
[{0}] {1}".format(status, message))

        # convert timestamp from ms to s and return datetime object
        return datetime.datetime.utcfromtimestamp(float(message) / 1000)

class ConnectionException(Exception):
    pass
