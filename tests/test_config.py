import tomllib
from datetime import datetime
from pathlib import Path

import pytest

from hydromt_uwbm.components.config import UwbmConfig


@pytest.fixture
def starttime() -> datetime:
    return datetime(2024, 1, 1, 0, 0, 0)


@pytest.fixture
def endtime() -> datetime:
    return datetime(2024, 1, 2, 0, 0, 0)


@pytest.fixture
def minimal_config(starttime: datetime, endtime: datetime) -> UwbmConfig:
    return UwbmConfig(
        name="Minimal config",
        starttime=starttime,
        endtime=endtime,
        timestep=3600,
    )


def test_write_read_cycle(tmp_path: Path, minimal_config: UwbmConfig):
    path = tmp_path / "config.ini"
    with open(path, "w") as f:
        f.write(minimal_config.to_ini())
    with open(path, "rb") as f:
        read_data = tomllib.load(f)
    read_cfg = UwbmConfig.create(read_data)
    assert read_cfg == minimal_config


# --------------------------------------------------------------------------
# Test validation errors
# --------------------------------------------------------------------------
def test_missing_field_serialization_error(tmp_path: Path, minimal_config: UwbmConfig):
    minimal_config._SECTIONS.pop(0)  # remove a section to cause serialization error
    with pytest.raises(ValueError, match="Some required fields were not serialized:"):
        minimal_config.to_ini()


def test_missing_required_fields(minimal_config: UwbmConfig):
    minimal_config.name = None  # required field

    with pytest.raises(ValueError, match="Some required fields were not serialized:"):
        minimal_config.to_ini()


def test_invalid_fraction(starttime, endtime):
    with pytest.raises(ValueError, match="Input should be less than or equal to 1"):
        UwbmConfig(
            name="Bad fraction",
            starttime=starttime,
            endtime=endtime,
            timestep=3600,
            pr_frac=1.5,  # invalid >1
        )


def test_create_validation_messages():
    # deliberately leave out required fields and add invalid/unknown values
    test_data = {
        "name": "Test Config",
        "soiltype": -1,  # invalid (should be >=0)
        "croptype": 1,
        "area_type": 0,
        "tot_pr_area": 5000,
        "pr_frac": 1.5,  # invalid (should be <=1)
        "frac_pr_aboveGW": 0.5,
        "discfrac_pr": 0.2,
        "intstorcap_pr": 10,
        "intstor_pr_t0": 0,
        "unknown_param": 123,  # unknown
    }

    with pytest.raises(ValueError) as excinfo:  # noqa: PT011
        UwbmConfig.create(test_data)

    msg = str(excinfo.value)
    print(msg)  # for debugging

    # Check invalid/missing fields are reported
    assert "Invalid/missing parameters:" in msg
    assert "soiltype" in msg
    assert "pr_frac" in msg

    # Check unknown fields are reported
    assert "Unknown parameters:" in msg
    assert "unknown_param" in msg
