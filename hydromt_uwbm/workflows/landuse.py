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
) -> dict[str, gpd.GeoDataFrame]:
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
    landuse_geometries: dict[str, geopandas.GeoDataFrame]
        Dictionary with landuse geometries and landuse table.
    """
    # Clean and explode region
    region = region.copy()
    region["geometry"] = region.geometry.buffer(0)
    region = region.explode(index_parts=False, ignore_index=True)
    region_geom = region.union_all()
    region_gdf = gpd.GeoDataFrame(geometry=[region_geom], crs=region.crs)
    region_gdf = region_gdf.explode(index_parts=False, ignore_index=True)

    # Base layer: unpaved
    da_unpaved = region_gdf.assign(reclass="unpaved")

    # Merge line layers and map landuse
    lines = pd.concat([roads, railways, waterways], ignore_index=True)
    lines = lines.merge(landuse_mapping, on="fclass", how="left")

    # Buffer lines by type
    da_closed_paved = _linestring_buffer(lines, "closed_paved")
    da_open_paved = _linestring_buffer(lines, "open_paved")
    da_water_lines = _linestring_buffer(lines, "water")

    # Explode multipolygons before clipping
    for layer in [da_closed_paved, da_open_paved, da_water_lines]:
        if not layer.empty:
            layer["geometry"] = layer.geometry.buffer(0)
            layer = layer.explode(index_parts=False, ignore_index=True)

    # Clip all line buffers to region
    if not da_closed_paved.empty:
        da_closed_paved = gpd.overlay(
            da_closed_paved, region_gdf, how="intersection", keep_geom_type=True
        )
    if not da_open_paved.empty:
        da_open_paved = gpd.overlay(
            da_open_paved, region_gdf, how="intersection", keep_geom_type=True
        )
    if not da_water_lines.empty:
        da_water_lines = gpd.overlay(
            da_water_lines, region_gdf, how="intersection", keep_geom_type=True
        )

    # Clip buildings to region
    if not buildings_area.empty:
        buildings = buildings_area.copy()
        buildings["geometry"] = buildings.geometry.buffer(0)
        buildings = buildings.explode(index_parts=False, ignore_index=True)
        da_paved_roof = gpd.overlay(
            buildings, region_gdf, how="intersection", keep_geom_type=True
        ).assign(reclass="paved_roof")
    else:
        da_paved_roof = gpd.GeoDataFrame(
            columns=["geometry", "reclass"], crs=region.crs
        )

    # Clip water areas to region
    if not water_area.empty:
        water = water_area.copy()
        water["geometry"] = water.geometry.buffer(0)
        water = water.explode(index_parts=False, ignore_index=True)
        da_water_area = gpd.overlay(
            water, region_gdf, how="intersection", keep_geom_type=True
        ).assign(reclass="water")
    else:
        da_water_area = gpd.GeoDataFrame(
            columns=["geometry", "reclass"], crs=region.crs
        )

    # Combine water layers
    da_water = pd.concat([da_water_area, da_water_lines], ignore_index=True)

    # Combine all layers in correct overlay order
    layers = {
        "da_unpaved": da_unpaved,
        "da_water": da_water,
        "da_open_paved": da_open_paved,
        "da_closed_paved": da_closed_paved,
        "da_paved_roof": da_paved_roof,
    }

    lu_map = layers["da_unpaved"]
    for key in ["da_water", "da_open_paved", "da_closed_paved", "da_paved_roof"]:
        lu_map = _combine_layers(lu_map, layers[key])

    # Final cleanup and dissolve by landuse
    lu_map["geometry"] = lu_map.geometry.buffer(0)
    lu_map = lu_map.explode(index_parts=False, ignore_index=True)
    lu_map = lu_map.dissolve(by="reclass", aggfunc="sum").reset_index()
    layers["landuse_map"] = lu_map
    return layers


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
            # Add water row to the end if not present
            lu_table.loc[len(lu_table)] = {"reclass": "water", "area": 0}
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


def _linestring_buffer(input_ds: gpd.GeoDataFrame, reclass: str) -> gpd.GeoDataFrame:
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
    sel = input_ds.loc[input_ds["reclass"] == reclass].copy()
    if sel.empty:
        return gpd.GeoDataFrame(columns=["geometry", "reclass"], crs=input_ds.crs)

    sel["geometry"] = sel.geometry.buffer(sel["width_t"] / 2)
    sel["reclass"] = reclass

    return sel[["reclass", "geometry"]]


def _combine_layers(
    ds_base: gpd.GeoDataFrame, ds_add: gpd.GeoDataFrame
) -> gpd.GeoDataFrame:
    if ds_add.empty:
        return ds_base

    if ds_base.crs != ds_add.crs and ds_base.crs is not None:
        ds_add = ds_add.to_crs(ds_base.crs)

    ds_base = ds_base.copy()
    ds_add = ds_add.copy()
    ds_base["geometry"] = ds_base.geometry.buffer(0)
    ds_add["geometry"] = ds_add.geometry.buffer(0)

    base_cut = gpd.overlay(ds_base, ds_add, how="difference")

    out = pd.concat([base_cut, ds_add], ignore_index=True)
    out = out.explode(index_parts=False, ignore_index=True)

    return out
