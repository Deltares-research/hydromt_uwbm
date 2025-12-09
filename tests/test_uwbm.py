"""Testing UWBM high level methods."""

from pathlib import Path

import geopandas as gpd
import pytest

from hydromt_uwbm import UWBM

DATA_DIR = Path(__file__).parent / "data"
P_DRIVE = Path("P:/")


@pytest.fixture
def athens_votris_model() -> Path:
    return DATA_DIR / "Athens_Votris_model"


@pytest.mark.skipif(
    not P_DRIVE.exists(), reason="Requires access to the P drive via the Deltares vpn."
)
def test_model(tmp_path: Path, athens_votris_model: Path):
    model = UWBM(
        root=tmp_path,
        data_libs=[
            "deltares_data",
            (DATA_DIR / "landuse" / "local_data_catalog.yml").as_posix(),
        ],
    )

    model.setup_project(
        name="Athens_Votris",
        region={"geom": gpd.read_file(DATA_DIR / "Athens_Votris_region.geojson")},
        t_start="2020-03-01",
        t_end="2020-03-03",
        ts=3600,
        crs=3857,
    )

    model.setup_precip_forcing(precip_fn="era5_hourly")
    model.setup_pet_forcing(temp_pet_fn="era5_hourly", pet_method="debruin")
    model.setup_landuse(source="osm", landuse_mapping_fn="osm_mapping")
    model.write()

    _assert_equal_models(left=athens_votris_model, right=model.root.path)


def _assert_equal_models(left: Path, right: Path):
    l_model = UWBM(root=left, mode="r")
    r_model = UWBM(root=right, mode="r")

    equal, errors = l_model.test_equal(r_model)
    assert equal, errors
