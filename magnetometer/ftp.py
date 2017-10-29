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

        # start time (wait 10 seconds to allow server to start)
        self.start_time = int(round(time.time() * 1000)) + 10000

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
                         "match": [self.date_filename(now)]}
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
        # time in ms
        now = int(round(time.time() * 1000))

        if now < self._next_poll_time:
            # nothing to do
            return

        # UTC dates
        one_day = datetime.timedelta(days=1)
        today = datetime.datetime.utcnow()
        tomorrow = today + one_day
        yesterday = today - one_day
        day_before_yesterday = yesterday - one_day

        # midnight timestamps in ms
        midnight_today = self.midnight_date(today).timestamp() * 1000
        midnight_tomorrow = self.midnight_date(tomorrow).timestamp() * 1000
        midnight_yesterday = self.midnight_date(yesterday).timestamp() * 1000

        # get file paths
        today_file_path = self.date_path(today)
        yesterday_file_path = self.date_path(yesterday)
        day_before_yesterday_file_path = self.date_path(day_before_yesterday)

        # default pivot is midnight (used when no local data has been recorded
        # in last day)
        pivot_timestamp = midnight_today

        # default latest local record line
        latest_line = None

        # create path if it doesn't exist
        if not os.path.isfile(today_file_path):
            logger.debug("Today's file doesn't exist; creating today's")

            if os.path.isfile(yesterday_file_path):
                # get last reading from yesterday
                logger.debug("Reading latest timestamp from yesterday's file")
                latest_line = self.latest_line(yesterday_file_path)

                # set pivot timestamp to yesterday's
                pivot_timestamp = midnight_yesterday

            # touch file
            open(today_file_path, 'a').close()
        else:
            logger.debug("Reading latest timestamp from today's file")

            # get latest line from file
            latest_line = self.latest_line(today_file_path)

        if latest_line:
            # last reading's time since midnight
            latest_time_ms = int(latest_line.split()[0])

            # equivalent timestamp
            pivot_timestamp += latest_time_ms

        # latest reading
        latest_data = self.next_readings(pivot_timestamp)

        new_data_count = 0

        if latest_data.num_readings:
            # there are new readings to store
            with open(today_file_path, 'a') as obj:
                for reading in latest_data.get_readings():
                    # check reading still applies to today
                    if reading.reading_time >= midnight_tomorrow:
                        continue

                    # convert reading time to seconds since midnight
                    reading.reading_time = int(round(reading.reading_time -
                                                     midnight_today))

                    # write line
                    print(reading.whitespace_repr(), file=obj)

                    new_data_count += 1

        if new_data_count:
            # upload latest version of the file
            logger.debug("Uploading %i readings to FTP", new_data_count)
            self.ftp_uploader.run()

        # clean up old files
        if os.path.isfile(day_before_yesterday_file_path):
            logger.debug("Removing old local file: %s",
                         day_before_yesterday_file_path)
            os.remove(day_before_yesterday_file_path)

        # set the next poll time
        self._next_poll_time += self.poll_time

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
