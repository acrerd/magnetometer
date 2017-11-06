"""University of Glasgow magnetometer FTP functionality"""

import os.path
import time
import datetime
import logging
import glob
from threading import Thread
import configparser
from contextlib import contextmanager
from urllib.request import urlopen
from ftpsync.targets import FsTarget
from ftpsync.ftp_target import FtpTarget
from ftpsync.synchronizers import DownloadSynchronizer, UploadSynchronizer
from datalog.data import DataStore

from .config import MagnetometerConfig

# load configuration
CONFIG = MagnetometerConfig()

# logger
logger = logging.getLogger("magnetometer.ftp")


@contextmanager
def run_ftp():
    """Start FTP pipe"""

    logger.info("Starting FTP pipe")

    # create pipe
    pipe = FtpPipe()

    # run
    pipe.start()

    # yield the pipe inside a try/finally block to handle any unexpected events
    try:
        # return the pipe to the caller
        yield pipe
    finally:
        # stop the thread and wait until it finishes
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
        self.poll_time = int(CONFIG["ftp"]["poll_time"])
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
        if not os.path.exists(CONFIG["ftp"]["local_dir"]):
            logger.debug("Creating local directory %s",
                         CONFIG["ftp"]["local_dir"])
            os.makedirs(CONFIG["ftp"]["local_dir"])

        # create local file target
        local_target = FsTarget(CONFIG["ftp"]["local_dir"])

        # remote FTP server
        remote_target = FtpTarget(path=CONFIG["ftp"]["remote_dir"],
                                  host=CONFIG["ftp"]["host"],
                                  port=int(CONFIG["ftp"]["port"]),
                                  username=CONFIG["ftp"]["username"],
                                  password=CONFIG["ftp"]["password"])

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
            except RuntimeError:
                # do nothing; try again next time
                # this prevents FTP comms issues from killing the thread
                pass

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
        max_old_files = int(CONFIG["ftp"]["max_old_files"])

        if max_old_files < 2:
            raise ValueError("max_old_files must be >= 2")

        # loop over files older than max_old_files
        for filename in self.data_file_walk()[max_old_files:]:
            logger.debug("Removing old local file: %s", filename)
            os.remove(filename)

    def data_file_walk(self, reverse=True):
        # data directory
        data_dir = CONFIG["ftp"]["local_dir"]

        return sorted(glob.glob(os.path.join(data_dir, "*.txt")), reverse=reverse)

    @classmethod
    def filename_from_text(cls, base):
        return base + os.path.extsep + cls.FILE_EXTENSION

    @classmethod
    def filename_from_date(cls, file_time):
        return cls.filename_from_text(file_time.strftime(cls.FILE_DATE_FORMAT))

    @classmethod
    def data_file_path(cls, filename):
        return os.path.join(CONFIG["ftp"]["local_dir"], filename)

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
        return "http://%s:%i/after/%i?fmt=json" % (CONFIG["server"]["host"],
                                                   int(CONFIG["server"]["port"]),
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
