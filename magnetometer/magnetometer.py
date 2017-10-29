"""University of Glasgow magnetometer run script"""

import sys
import logging
from logging.handlers import TimedRotatingFileHandler
import configparser
from datalog.adc.config import AdcConfig
from datalog.adc.adc import Adc
from datalog.data import DataStore

from .config import MagnetometerConfig
from .calibration import set_conversion, scale_counts_to_volts, \
                         scale_volts_to_nt_and_degrees
from .network import run_server
from .ftp import run_ftp

# load configuration
conf = MagnetometerConfig()

# create root logger
logger = logging.getLogger()

def run():
    # open log file with handler
    try:
        handler = TimedRotatingFileHandler(
            conf["logging"]["file"],
            when="D",
            backupCount=int(conf["logging"]["file_count"]))
    except PermissionError as e:
        logger.error("Log file at %s cannot be modified. Check it exists and that "
                     "the current user has write permissions.",
                     conf["logging"]["file"])
        sys.exit(1)

    # configure logging output
    handler.setFormatter(logging.Formatter(conf["logging"]["format"]))
    logger.addHandler(handler)
    logger.setLevel(logging.getLevelName(conf["logging"]["level"].upper()))

    # create ADC device
    adc = Adc.load_from_config(AdcConfig())

    # create datastore with conversion to nT
    datastore = DataStore(conf["datastore"]["size"],
                          conversion_callbacks=[scale_counts_to_volts,
                                                scale_volts_to_nt_and_degrees])

    # get retriever and FTP contexts
    with adc.get_retriever(datastore) as retriever, run_ftp() as ftp_pipe:
        # set conversion factors
        set_conversion([adc.get_calibration(channel) for channel
                        in sorted(adc.enabled_channels)])

        # run server within contexts
        run_server(datastore)
