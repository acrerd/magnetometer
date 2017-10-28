"""University of Glasgow magnetometer FTP functionality"""

import os.path
import time
import datetime
import logging
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

    def __init__(self):
        """Initialises the FTP pipe"""

        # initialise threading
        Thread.__init__(self)

        # default start time
        self.start_time = None

        # default next poll time
        self._next_poll_time = None

        # retrieval flag
        self.retrieving = False

    def run(self):
        """Starts piping magnetometer data"""

        # time in ms between polls
        poll_time = int(CONFIG["ftp"]["poll_time"])
        logger.info("Poll time: {0:.2f} ms".format(poll_time))

        # now
        now = datetime.datetime.utcnow()

        # start time (wait 10 seconds to allow server to start)
        self.start_time = int(round(time.time() * 1000)) + 10000

        # default next poll time
        self._next_poll_time = self.start_time

        # set status on
        self.retrieving = True

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
                         "match": [self.date_filename(now)]}
        upload_opts = {"force": True,
                       "resolve": "local",
                       "verbose": 3,
                       "dry_run": False}

        # create downloader and uploader
        ftp_downloader = DownloadSynchronizer(local_target,
                                              remote_target,
                                              download_opts)

        # look for existing file for today
        ftp_downloader.run()

        # create uploader
        ftp_uploader = UploadSynchronizer(local_target,
                                          remote_target,
                                          upload_opts)
        # HACK: disable remote readonly - bug in pyftpsync
        remote_target.readonly = False

        # main run loop
        while self.retrieving:
            # time in ms
            current_time = int(round(time.time() * 1000))

            if current_time < self._next_poll_time:
                # skip this loop
                continue

            # date
            current_date = datetime.datetime.utcnow()

            # midnight timestamp in ms
            midnight_timestamp = self.midnight_time(current_date).timestamp() * 1000

            # ms since start
            time_since_start = current_time - self.start_time

            # get today's file path
            file_path = self.date_path(current_date)

            # default pivot is midnight
            pivot_timestamp = midnight_timestamp

            # create path if it doesn't exist
            if not os.path.isfile(file_path):
                # touch file
                open(file_path, 'a').close()
            else:
                # get latest line from file
                latest_line = self.latest_line(file_path)

                if latest_line:
                    # last reading's time since midnight
                    latest_time_ms = int(latest_line.split()[0])

                    # equivalent timestamp
                    pivot_timestamp += latest_time_ms

            # pivot time for latest reading
            latest_data = self.next_readings(pivot_timestamp)

            if latest_data:
                # readings to store
                with open(file_path, 'a') as obj:
                    for reading in latest_data.get_readings():
                        # convert reading time to seconds since midnight
                        reading.reading_time = int(round(reading.reading_time -
                                                         midnight_timestamp))

                        # write line
                        print(reading.whitespace_repr(), file=obj)

            # upload latest version of the file
            logger.debug("Uploading latest data to FTP")
            ftp_uploader.run()

            # set the next poll time
            self._next_poll_time += poll_time

    def stop(self):
        """Stops the FTP pipe"""

        # stop retrieving data
        self.retrieving = False

    @staticmethod
    def date_filename(file_time):
        return "%s-%s-%s.txt" % (file_time.year, file_time.month, file_time.day)

    @classmethod
    def date_path(cls, file_time):
        return os.path.join(CONFIG["ftp"]["local_dir"],
                            cls.date_filename(file_time))

    @classmethod
    def latest_line(cls, file_path):
        last = None

        with open(file_path, 'r') as obj:
            for last in [line for line in obj if line.rstrip("\n")]:
                pass

        return last

    @staticmethod
    def midnight_time(date_now):
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
