"""HydroMT plugin UWBM: A HydroMT plugin for the Urban Water Balance Model."""

from os.path import abspath, dirname, join

from hydromt_uwbm.uwbm import *  # noqa: F403

DATADIR = abspath(join(dirname(__file__), "data"))

__version__ = "0.1.0"
