"""University of Glasgow magnetometer FTP functionality"""

import os.path
import time
import datetime
import logging
from logging.handlers import TimedRotatingFileHandler
from threading import Thread
import signal
import configparser
import glob
from urllib.request import urlopen
from ftpsync.targets import FsTarget
from ftpsync.ftp_target import FtpTarget
from ftpsync.synchronizers import DownloadSynchronizer, UploadSynchronizer
from datalog.data import DataStore

from .config import FtpConfig

# create root logger
root_logger = logging.getLogger()

# load configuration
CONF = FtpConfig()

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

# get logger for FTP
logger = logging.getLogger("ftp")

def run():
    """Start FTP pipe"""

    logger.info("Starting FTP pipe")

    # create pipe
    pipe = FtpPipe()

    def stop(*args):
        # stop the thread and wait until it finishes
        pipe.stop()
        logger.info("Waiting for FTP pipe to stop")
        pipe.join()
        logger.info("FTP pipe stopped")

    # catch signals
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    # run
    pipe.start()

def stop():
    pipe.stop()
    logger.info("Waiting for FTP pipe to stop")
    pipe.join()
    logger.info("FTP pipe stopped")

class FtpPipe(Thread):
    """Client to pipe data from the magnetometer server to a remote FTP server"""

    FILE_DATE_FORMAT = "%Y-%m-%d"
    FILE_EXTENSION = "txt"

    def __init__(self):
        """Initialises the FTP pipe"""

        # initialise threading
        Thread.__init__(self)

        # time in ms between polls
        self.poll_time = int(CONF["ftp"]["poll_time"])
        logger.info("Poll time: {0:.2f} ms".format(self.poll_time))

        # default start time
        self.start_time = None

        # default next poll time
        self._next_poll_time = None

        # retrieval flag
        self.retrieving = False

    def run(self):
        """Starts piping magnetometer data"""

        # now
        now = datetime.datetime.utcnow()

        # start time (wait one poll time period to allow server to start)
        self.start_time = int(round(time.time() * 1000)) + self.poll_time

        # default next poll time
        self._next_poll_time = self.start_time

        # set status on
        self.retrieving = True

        # create local directory if it doesn't exist
        if not os.path.exists(CONF["ftp"]["local_dir"]):
            logger.debug("Creating local directory %s",
                         CONF["ftp"]["local_dir"])
            os.makedirs(CONF["ftp"]["local_dir"])

        # create local file target
        local_target = FsTarget(CONF["ftp"]["local_dir"])

        # remote FTP server
        remote_target = FtpTarget(path=CONF["ftp"]["remote_dir"],
                                  host=CONF["ftp"]["host"],
                                  port=int(CONF["ftp"]["port"]),
                                  username=CONF["ftp"]["username"],
                                  password=CONF["ftp"]["password"])

        # FTP options
        download_opts = {"force": True,
                         "resolve": "remote",
                         "verbose": 3,
                         "dry_run": False,
                         "match": [self.filename_from_date(now)]}
        upload_opts = {"force": True,
                       "resolve": "local",
                       "verbose": 3,
                       "dry_run": False}

        # create downloader and uploader
        self.ftp_downloader = DownloadSynchronizer(local_target,
                                                   remote_target,
                                                   download_opts)

        # look for existing file for today
        self.ftp_downloader.run()

        # create uploader
        self.ftp_uploader = UploadSynchronizer(local_target,
                                               remote_target,
                                               upload_opts)
        # HACK: disable remote readonly - bug in pyftpsync
        remote_target.readonly = False

        # main run loop
        while self.retrieving:
            self.process_records()

    def process_records(self):
        # current timestamp in ms
        now = int(round(time.time() * 1000))

        if now < self._next_poll_time:
            # nothing to do
            return

        # timestamp corresponding to last recorded measurement
        pivot_timestamp = self.latest_recorded_timestamp()

        # get readings since last time records were stored
        latest_data = self.next_readings(pivot_timestamp)

        # check if there are new readings to store
        if latest_data.num_readings:
            # get readings grouped into days
            groups = latest_data.get_datetime_grouped_readings()

            # loop over each day
            for current_date in sorted(groups):
                # this date's full data file path
                current_file_path = self.path_from_date(current_date)

                self.store_readings(current_file_path, groups[current_date],
                                    self.midnight_date(current_date))

            # upload latest version of the file
            logger.debug("Synchronising new readings to FTP")
            try:
                self.ftp_uploader.run()
            except Exception as e:
                # do nothing; try again next time
                # this prevents FTP comms issues from killing the thread
                logger.error("Failed to upload data to FTP: %s (will try "
                             "again)", str(e))

        # clean up old files
        self.remove_old_files()

        # set the next poll time
        self._next_poll_time += self.poll_time

    def stop(self):
        """Stops the FTP pipe"""

        # stop retrieving data
        self.retrieving = False

    def latest_recorded_timestamp(self):
        # search for previous reading in reverse chronological order
        logger.debug("Searching for latest recorded reading")
        for file_path in self.data_file_walk():
            if os.path.isfile(file_path):
                # filename without directory path
                filename = os.path.basename(file_path)

                # look for reading
                logger.debug("Searching %s", filename)
                latest_line = self.latest_line(file_path)

                if latest_line:
                    logger.debug("Found latest reading in %s", filename)

                    # filename without extension
                    file_date = os.path.splitext(filename)[0]

                    # date equivalent to filename
                    midnight_date = datetime.datetime.strptime(filename,
                        self.date_file_format())

                    # milliseconds since midnight
                    line_ms = int(latest_line.split()[0])

                    # pivot time as midnight timestamp plus reading time, both
                    # in milliseconds
                    return int(midnight_date.timestamp() * 1000) + line_ms

        logger.debug("Failed to find latest recorded reading")
        return 0

    @staticmethod
    def store_readings(filepath, readings, midnight):
        if not os.path.isfile(filepath):
            logger.debug("Creating %s", filepath)

        with open(filepath, 'a') as obj:
            for reading in readings:
                # midnight timestamp in milliseconds
                midnight_timestamp = int(midnight.timestamp()) * 1000

                # convert reading time to seconds since midnight
                reading.reading_time = int(round(reading.reading_time -
                                                 midnight_timestamp))

                # write line
                print(reading.whitespace_repr(), file=obj)

    def remove_old_files(self):
        # number of files to keep
        max_old_files = int(CONF["ftp"]["max_old_files"])

        if max_old_files < 2:
            raise ValueError("max_old_files must be >= 2")

        # loop over files older than max_old_files
        for filename in self.data_file_walk()[max_old_files:]:
            logger.debug("Removing old local file: %s", filename)
            os.remove(filename)

    def data_file_walk(self, reverse=True):
        # data directory
        data_dir = CONF["ftp"]["local_dir"]

        return sorted(glob.glob(os.path.join(data_dir, "*.txt")), reverse=reverse)

    @classmethod
    def filename_from_text(cls, base):
        return base + os.path.extsep + cls.FILE_EXTENSION

    @classmethod
    def filename_from_date(cls, file_time):
        return cls.filename_from_text(file_time.strftime(cls.FILE_DATE_FORMAT))

    @classmethod
    def data_file_path(cls, filename):
        return os.path.join(CONF["ftp"]["local_dir"], filename)

    @classmethod
    def path_from_text(cls, base):
        return cls.data_file_path(cls.filename_from_text(base))

    @classmethod
    def path_from_date(cls, file_time):
        return cls.data_file_path(cls.filename_from_date(file_time))

    @classmethod
    def latest_line(cls, file_path):
        if not cls.is_valid_file_path(file_path):
            return None

        last = None

        with open(file_path, 'r') as obj:
            for last in [line for line in obj if line.rstrip("\n")]:
                pass

        return last

    @classmethod
    def date_file_format(cls):
        return cls.FILE_DATE_FORMAT + os.path.extsep + cls.FILE_EXTENSION

    @classmethod
    def is_valid_file_path(cls, file_path):
        base_file_path = os.path.basename(file_path)

        try:
            datetime.datetime.strptime(base_file_path, cls.date_file_format())
        except ValueError:
            return False

        return True

    @staticmethod
    def midnight_date(date_now):
        return date_now.replace(hour=0, minute=0, second=0, microsecond=0)

    @staticmethod
    def after_url(pivot_timestamp):
        return "http://%s:%i/after/%i?fmt=json" % (CONF["server"]["host"],
                                                   int(CONF["server"]["port"]),
                                                   pivot_timestamp)

    @classmethod
    def next_readings(cls, pivot_timestamp):
        # reading url
        url = cls.after_url(pivot_timestamp)

        logger.debug("Fetching readings from %s", url)

        # fetch JSON document
        with urlopen(url) as response:
            # response encoding
            charset = response.headers.get_content_charset()

            # decode document
            document = response.read().decode(charset)

            # try to parse JSON
            try:
                datastore = DataStore.instance_from_json(document)

                logger.info("Found %i new readings",
                            datastore.num_readings)
            except Exception as e:
                logger.error(e)

                # return empty dataset
                datastore = DataStore()

        return datastore
