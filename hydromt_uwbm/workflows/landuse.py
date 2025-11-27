"""Landuse workflows for UWBM plugin."""

import logging

import geopandas as gpd
import pandas as pd

logger = logging.getLogger(__name__)

__all__ = ["landuse_from_osm", "landuse_table"]


def landuse_from_osm(
    region: gpd.GeoDataFrame,
    roads: gpd.GeoDataFrame,
    railways: gpd.GeoDataFrame,
    waterways: gpd.GeoDataFrame,
    buildings_area: gpd.GeoDataFrame,
    water_area: gpd.GeoDataFrame,
    landuse_mapping: pd.DataFrame,
):
    """Preparing landuse map from OpenStreetMap.

    Parameters
    ----------
    region: pandas.GeoDataFrame
        Project area polygon.
    roads: geopandas.GeoDataFrame
        Roads polylines.
    railway: geopandas.GeoDataFrame
        Railway polylines.
    waterways: geopandas.GeoDataFrame
        Waterways polylines.
    buildings_area: geopandas.GeoDataFrame
        Building footprints polygons.
    water_area: geopandas.GeoDataFrame
        Waterbody polygons.
    landuse_mapping: pandas.DataFrame
        DataFrame of OSM landuse translation table.

    Returns
    -------
    landuse_map: GeoJSON
        Landuse geometry.
    """
    # Create unpaved base layer from region
    da_unpaved = region.copy().assign(reclass="unpaved")

    # Merge all lines
    ds_joined = pd.concat([roads, railways, waterways])
    ds_joined = ds_joined.merge(landuse_mapping, on="fclass", how="left")

    # Buildings and water polygons
    da_paved_roof = buildings_area.assign(reclass="paved_roof")
    da_water_area = water_area.assign(reclass="water")

    # Buffer lines by width
    da_closed_paved = _linestring_buffer(ds_joined, "closed_paved")
    da_open_paved = _linestring_buffer(ds_joined, "open_paved")
    da_water_lines = _linestring_buffer(ds_joined, "water")

    # Add water lines to water areas
    da_water = pd.concat([da_water_area, da_water_lines])

    # Combine all layers
    layers: list[gpd.GeoDataFrame] = [
        da_unpaved,
        da_water,
        da_open_paved,
        da_closed_paved,
        da_paved_roof,
    ]
    lu_map = layers[0]
    for layer in layers[1:]:
        lu_map = _combine_layers(lu_map, layer)

    # Clip by project area to create neat land use map
    lu_map = gpd.clip(lu_map, region, keep_geom_type=True)

    # Dissolve by land use category
    lu_map = lu_map.dissolve(by="reclass", aggfunc="sum").reset_index()

    return lu_map


def landuse_table(lu_map: gpd.GeoDataFrame) -> pd.DataFrame:
    """Preparing landuse table based on provided land use map.

    Parameters
    ----------
    lu_map: gpd.GeoDataFrame
        polygon land use map.

    Returns
    -------
    landuse_table: pandas.DataFrame
        Table with landuse areas and percentages of total.
    """
    # Keep only polygonal geometries (_linestring_buffer ensures this)
    lu_map = lu_map[lu_map.geometry.type.isin(["Polygon", "MultiPolygon"])].copy()

    # Compute areas
    lu_map["area"] = lu_map.geometry.area
    lu_table = lu_map[["reclass", "area"]].copy()
    tot_area = float(lu_table["area"].sum().round(0))

    # Ensure water has at least 1% of total area
    water = lu_table[lu_table["reclass"] == "water"]
    if water.empty or water["area"].sum() < 0.01 * tot_area:
        if water.empty:
            lu_table = pd.concat(
                [lu_table, pd.DataFrame([{"reclass": "water", "area": 0}])],
                ignore_index=True,
            )
        area_tot_new = tot_area / 0.99
        lu_table.loc[lu_table["reclass"] == "water", "area"] += area_tot_new * 0.01
        lu_table["frac"] = (lu_table["area"] / area_tot_new).round(3)
    else:
        lu_table["frac"] = (lu_table["area"] / tot_area).round(3)

    # Add total area row
    lu_table = pd.concat(
        [
            lu_table,
            pd.DataFrame([{"reclass": "tot_area", "area": tot_area, "frac": 1}]),
        ],
        ignore_index=True,
    )

    # Rename to model conventions
    lu_table["reclass"] = lu_table["reclass"].replace(
        {
            "open_paved": "op",
            "water": "ow",
            "unpaved": "up",
            "paved_roof": "pr",
            "closed_paved": "cp",
        }
    )

    # Group by in case of multiple geometries per land use category
    lu_table = (
        lu_table.groupby("reclass", as_index=False)[["area", "frac"]].sum().round(3)
    )

    return lu_table


def _linestring_buffer(input_ds, reclass):
    """Generating buffers with varying sized depending on land use category.

    Parameters
    ----------
    input_ds: pandas.GeoDataFrame
        Pandas GeoDataFrame containing linestring elements.
    reclass: str
        Name of land use category.

    Returns
    -------
    output_ds: pandas.GeoDataFrame
        Pandas GeoDataFrame with buffered polygons.
    """
    input_ds_select = input_ds.loc[input_ds["reclass"] == reclass]
    output_ds = input_ds_select.buffer((input_ds_select["width_t"]) / 2, cap_style=2)
    output_ds = gpd.GeoDataFrame(geometry=gpd.GeoSeries(output_ds))
    output_ds = output_ds.assign(reclass=reclass)
    output_ds = output_ds.dissolve(by="reclass", aggfunc="sum")
    output_ds = output_ds.reset_index()
    return output_ds


def _combine_layers(ds_base, ds_add):
    """Combining two GeoDataFrame layers into a single GeoDataFrame layer.

    Parameters
    ----------
    ds_base: pandas.GeoDataFrame
        Pandas GeoDataFrame containing base layer.
    ds_add: pandas.GeoDataFrame
        Pandas GeoDataFrame containing additional layer

    Returns
    -------
    output_ds: pandas.GeoDataFrame
        Pandas GeoDataFrame with combined layers.
    """
    if not ds_add.empty:
        # Cut out new layer from base layer
        ds_out = gpd.overlay(ds_base, ds_add, how="difference")
        # Add new layer to base layer
        ds_out = pd.concat([ds_out, ds_add])
        return ds_out
    else:
        return ds_base
