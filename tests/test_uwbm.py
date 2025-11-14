"""Testing UWBM high level methods."""

from pathlib import Path

from hydromt_uwbm import UWBM

DATA_DIR = Path(__file__).parent / "data"


def test_model(tmp_path: Path):
    model = UWBM(
        root=tmp_path,
        data_libs=[
            "deltares_data",
            (DATA_DIR / "landuse" / "local_data_catalog.yml").as_posix(),
        ],
    )

    model.setup_project(
        name="Athens_Votris",
        region={"geom": DATA_DIR / "Athens_Votris_region.geojson"},
        t_start="2020-02-01",
        t_end="2020-03-01",
        ts=3600,
        crs="EPSG:3857",
    )

    model.setup_precip_forcing(precip_fn="era5_hourly")
    model.setup_pet_forcing(temp_pet_fn="era5_hourly", pet_method="debruin")
    model.setup_landuse(source="osm", landuse_mapping_fn="osm_mapping")
    model.setup_model_config()
    model.write()

    _assert_equal_models(left=DATA_DIR / "Athens_Votris_model", right=Path(model.root))


def _assert_equal_models(left: Path, right: Path):
    l_model = UWBM(root=left, mode="r")
    r_model = UWBM(root=right, mode="r")

    assert len(l_model.config) > 0
    assert l_model.config == r_model.config

    assert len(l_model.geoms) > 0
    assert len(l_model.geoms) == len(r_model.geoms)
    for geom_name in l_model.geoms:
        l_geom = l_model.geoms[geom_name]
        r_geom = r_model.geoms[geom_name]
        assert l_geom.equals(r_geom)

    assert len(l_model.forcing) > 0
    assert len(l_model.forcing) == len(r_model.forcing)
    for f_name in l_model.forcing:
        l_forcing = l_model.forcing[f_name]
        r_forcing = r_model.forcing[f_name]
        assert l_forcing.equals(r_forcing)

    assert len(l_model.tables) > 0
    assert len(l_model.tables) == len(r_model.tables)
    for t_name in l_model.tables:
        l_table = l_model.tables[t_name]
        r_table = r_model.tables[t_name]
        assert l_table.equals(r_table)
