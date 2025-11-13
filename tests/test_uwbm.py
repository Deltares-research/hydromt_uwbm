"""Testing UWBM high level methods."""

from pathlib import Path

import geopandas as gpd
import pandas as pd

from hydromt_uwbm import UWBM

DATA_DIR = Path(__file__).parent / "data"


def test_model(tmp_path: Path):
    local_data_catalog = DATA_DIR / "local_data_catalog.yml"
    model = UWBM(
        root=tmp_path,
        data_libs=["deltares_data", local_data_catalog.as_posix()],
    )

    region_geojson = DATA_DIR / "Shapefile_Area_priority.geojson"
    model.setup_project(
        name="Logrono",
        region={"geom": region_geojson},
        t_start="1990-01-01",
        t_end="2020-03-01",
        ts=3600,
        crs="EPSG:3857",
    )

    model.setup_precip_forcing(precip_fn="era5_hourly")
    model.setup_pet_forcing(temp_pet_fn="era5_hourly", pet_method="debruin")
    model.setup_landuse(source="osm", landuse_mapping_fn="osm_mapping")
    model.write()

    _assert_equal_model_output(model_root=Path(model.root))


def _assert_equal_model_output(model_root: Path):
    landuse_csv = "landuse_Athens_Votris.csv"
    assert (model_root / landuse_csv).exists()
    landuse_df = pd.read_csv(model_root / landuse_csv)
    expected_landuse_df = pd.read_csv(DATA_DIR / landuse_csv)
    assert landuse_df.equals(expected_landuse_df)

    forcing_csv = "Forcing_Logrono_30y_1h.csv"
    assert (model_root / forcing_csv).exists()
    forcing_df = pd.read_csv(model_root / forcing_csv)
    expected_forcing_df = pd.read_csv(DATA_DIR / forcing_csv)
    assert forcing_df.equals(expected_forcing_df)

    landuse_geojson = "landuse_Athens_Votris.geojson"
    assert (model_root / landuse_geojson).exists()
    landuse_gdf = gpd.read_file(model_root / landuse_geojson)
    expected_landuse_gdf = gpd.read_file(DATA_DIR / landuse_geojson)
    assert landuse_gdf.equals(expected_landuse_gdf)
