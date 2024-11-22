"""Define all rules for HABApp."""

import pathlib

import pytz

__version__ = "7.0.0"
BASE_PATH = pathlib.Path(__file__).parent.parent.resolve()
TIMEZONE = pytz.timezone("Europe/Berlin")
