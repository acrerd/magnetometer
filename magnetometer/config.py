"""Configuration parser and defaults"""

import os.path
import logging
import abc
from configparser import RawConfigParser
import pkg_resources
import appdirs

THIS_DIR = os.path.dirname(os.path.realpath(__file__))

# logger
logger = logging.getLogger("magnetometer.config")


class MagnetometerConfig(RawConfigParser):
    """Magnetometer config parser"""

    DEFAULT_CONFIG_FILENAME = 'magnetometer.conf.dist'

    def __init__(self, *args, **kwargs):
        super(MagnetometerConfig, self).__init__(*args, **kwargs)

        self.load_config_file()

    def load_config_file(self):
        path = self.get_config_filepath()

        with open(path) as obj:
            logger.debug("Reading config from %s", path)
            self.read_file(obj)

    @classmethod
    def get_config_filepath(cls):
        """Find the path to the config file

        This creates the config file if it does not exist, using the distributed
        template.
        """

        config_dir = appdirs.user_config_dir("magnetometer")
        config_file = os.path.join(config_dir, "magnetometer.conf")

        # check the config file exists
        if not os.path.isfile(config_file):
            cls.create_user_config_file(config_file)

        return config_file

    @classmethod
    def create_user_config_file(cls, config_file):
        """Create config file in user directory"""

        directory = os.path.dirname(config_file)

        # create user config directory
        if not os.path.exists(directory):
            os.makedirs(directory)

        logger.debug("Creating config file at %s", directory)

        # copy across distribution template
        with open(config_file, 'wb') as user_file:
            # find distribution config file and copy it to the user config file
            user_file.writelines(
                pkg_resources.resource_stream(__name__,
                                              cls.DEFAULT_CONFIG_FILENAME)
            )
