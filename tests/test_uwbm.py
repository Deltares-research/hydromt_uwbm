"""Testing UWBM high level methods."""

from pathlib import Path

import geopandas as gpd

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
        region={"geom": gpd.read_file(DATA_DIR / "Athens_Votris_region.geojson")},
        t_start="2020-03-01",
        t_end="2020-03-03",
        ts=3600,
        crs=3857,
    )

    model.setup_precip_forcing(precip_fn="era5_hourly")
    model.setup_pet_forcing(temp_pet_fn="era5_hourly", pet_method="debruin")
    model.setup_landuse(
        soiltype=1, croptype=11, source="osm", landuse_mapping_fn="osm_mapping"
    )
    model.write()

    _assert_equal_models(left=DATA_DIR / "Athens_Votris_model", right=model.root.path)


def _diff_dicts(left: dict, right: dict, prefix: str = "") -> dict:
    """
    Return a dict of differences between two nested dictionaries.
    Keys in the returned dict are full key-paths (e.g. "a.b.c").
    Values are human-readable messages describing the difference.
    """
    diffs = {}

    for key, lval in left.items():
        path = f"{prefix}.{key}" if prefix else key

        if key not in right:
            diffs[path] = f"Missing in right: {lval!r}"
            continue

        rval = right[key]

        if isinstance(lval, dict) and isinstance(rval, dict):
            nested = _diff_dicts(lval, rval, path)
            diffs.update(nested)
            continue

        if type(lval) is not type(rval):
            diffs[path] = (
                f"Type mismatch: {type(lval).__name__} != {type(rval).__name__}"
            )
            continue

        if lval != rval:
            diffs[path] = f"Value mismatch: {lval!r} != {rval!r}"

    # Detect extra keys in right that are missing in left
    for key, rval in right.items():
        path = f"{prefix}.{key}" if prefix else key
        if key not in left:
            diffs[path] = f"Extra key in right: {rval!r}"

    return diffs


def _assert_equal_models(left: Path, right: Path):
    l_model = UWBM(root=left, mode="r")
    r_model = UWBM(root=right, mode="r")

    assert len(l_model.config.data) > 0
    diffs = _diff_dicts(l_model.config.data, r_model.config.data)
    assert not diffs, "Config mismatch:\n" + "\n".join(
        f"{k}: {v}" for k, v in diffs.items()
    )

    assert len(l_model.geoms.data) > 0
    assert len(l_model.geoms.data) == len(r_model.geoms.data)
    for geom_name in l_model.geoms.data:
        l_geom = l_model.geoms.data[geom_name]
        r_geom = r_model.geoms.data[geom_name]
        assert l_geom.equals(r_geom)

    assert len(l_model.forcing.data) > 0
    assert len(l_model.forcing.data) == len(r_model.forcing.data)
    for f_name in l_model.forcing.data:
        l_forcing = l_model.forcing.data[f_name]
        r_forcing = r_model.forcing.data[f_name]
        assert l_forcing.equals(r_forcing)

    assert len(l_model.landuse.data) > 0
    assert len(l_model.landuse.data) == len(r_model.landuse.data)
    for t_name in l_model.landuse.data:
        l_table = l_model.landuse.data[t_name]
        r_table = r_model.landuse.data[t_name]
        assert l_table.equals(r_table)
