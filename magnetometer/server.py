"""University of Glasgow magnetometer run script"""

import sys
import time
import logging
from logging.handlers import TimedRotatingFileHandler
from bottle import Bottle, request, run, abort
from datalog.adc.config import AdcConfig
from datalog.adc.adc import Adc
from datalog.data import DataStore

from .config import MagnetometerConfig
from .calibration import set_conversion, scale_counts_to_volts, \
                         scale_volts_to_nt_and_degrees

# create root logger
root_logger = logging.getLogger()

# load configuration
CONF = MagnetometerConfig()

# open log file with handler
try:
    handler = TimedRotatingFileHandler(
        CONF["logging"]["file"],
        when="D",
        backupCount=int(CONF["logging"]["file_count"]))
except PermissionError as e:
    root_logger.error("Log file at %s cannot be modified. Check it exists and that "
                 "the current user has write permissions.",
                 CONF["logging"]["file"])
    sys.exit(1)

# configure logging output
handler.setFormatter(logging.Formatter(CONF["logging"]["format"]))
root_logger.addHandler(handler)
root_logger.setLevel(logging.getLevelName(CONF["logging"]["level"].upper()))

# get logger for server
logger = logging.getLogger("server")

def run():
    runner = MagnetometerRunner()
    runner.run()

class MagnetometerRunner(object):
    def __init__(self):
        # create ADC device
        self.adc = Adc.load_from_config(AdcConfig())

        # create datastore with conversion to nT
        self.datastore = DataStore(CONF["datastore"]["size"],
            conversion_callbacks=[scale_counts_to_volts,
                                  scale_volts_to_nt_and_degrees])

        # start time
        self.start_time = None

        # create web app and routes
        self.app = Bottle()
        self.create_routes()

    def run(self):
        host = str(CONF["server"]["host"])
        port = int(CONF["server"]["port"])

        # get retriever and FTP contexts
        with self.adc.get_retriever(self.datastore) as retriever:
            # set conversion factors
            set_conversion([self.adc.get_calibration(channel) for channel
                            in sorted(self.adc.enabled_channels)])

            logger.info("Magnetometer ready")

            # set start time
            self.start_time = int(round(time.time() * 1000))

            logger.info("Starting web server")
            self.app.run(host=host, port=port)

    def create_routes(self):
        self.app.route("/earliest", method="GET", callback=self.earliest)
        self.app.route("/latest", method="GET", callback=self.latest)
        self.app.route("/before/<pivot_time:int>", method="GET",
                       callback=self.before)
        self.app.route("/after/<pivot_time:int>", method="GET",
                       callback=self.after)
        self.app.route("/info", method="GET", callback=self.info)

    def earliest(self):
        """Get earliest readings in datastore

        :return: formatted data
        :rtype: string
        """

        return self.handle_fixed_list(desc=False, **self.data_query_args())

    def latest(self):
        """Get latest readings in datastore

        :return: formatted data
        :rtype: string
        """

        return self.handle_fixed_list(desc=True, **self.data_query_args())

    def before(self, pivot_time):
        """Get readings before a certain time in datastore

        :param pivot_time: time to get readings before
        :type pivot_time: int
        :return: formatted data
        :rtype: string
        """

        try:
            return self.handle_fixed_list(pivot_time=pivot_time,
                                          pivot_after=False,
                                          **self.data_query_args())
        except TypeError:
            abort(400, "Invalid parameter")

    def after(self, pivot_time):
        """Get readings after a certain time in datastore

        :param pivot_time: time to get readings after
        :type pivot_time: int
        :return: formatted data
        :rtype: string
        """

        try:
            return self.handle_fixed_list(pivot_time=pivot_time,
                                          pivot_after=True,
                                          **self.data_query_args())
        except TypeError:
            abort(400, "Invalid parameter")

    def info():
        """Get server info

        :return: formatted server info
        :rtype: string
        """

        fmt = request.query.get("fmt", default=CONF["server"]["default_format"])

        # uptime
        up_time = int(round(time.time() * 1000)) - self.start_time

        data = {
            "datalog_version": datalog.__version__,
            "start_time": self.start_time,
            "up_time": up_time
        }

        if fmt == "json":
            return json.dumps(data)
        elif fmt == "csv":
            return "\n".join(["\"{}\",\"{}\"".format(key, val)
                              for key, val in data.items()])
        else:
            abort(400, "Invalid format")

    def handle_fixed_list(self, fmt, *args, **kwargs):
        """Generate a string representation of the data given specified filters

        :param fmt: data format
        :type fmt: string
        :return: formatted data
        :rtype: string
        """

        if fmt == "json":
            return self.datastore.json_repr(*args, **kwargs)
        elif fmt == "csv":
            return self.datastore.csv_repr(*args, **kwargs)
        else:
            abort(400, "Invalid format")

    def data_query_args(self):
        """Extract query arguments

        :return: collection of query keys and values
        :rtype: dict
        """

        fmt = request.query.get("fmt", default=CONF["server"]["default_format"])
        amount = request.query.get("amount",
            CONF["server"]["default_readings_per_request"])

        return {
            "fmt": fmt,
            "amount": amount
        }
