"""HydroMT plugin UWBM: A HydroMT plugin for the Urban Water Balance Model."""

from pathlib import Path

from hydromt_uwbm.uwbm import UWBM

DATA_DIR = Path(__file__).parent / "data"

__all__ = ["UWBM"]
__version__ = "0.1.0"
