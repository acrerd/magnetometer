import sys

from picolog.network import Server

"""
Starts the magnetometer server.

Run with `python run-server.py <config path> <channel config path>`

Set <config path> to None if you don't want to change default config values such
as sample rate. The <channel config path> on the other hand should be pointed at
something, otherwise no channels will be recorded.

The PicoLog ADC utilities software (https://github.com/SeanDS/picolog-adc-python)
must be on your Python path.

Sean Leavey
https://github.com/SeanDS/
"""

# get server instance
server = Server(*sys.argv[1:])

try:
    # start server
    server.start()
except:
    server._adc.close_unit()
    # close open sockets if necessary
    if server.socket_open():
        server.stop()

    # raise the original exception
    raise
