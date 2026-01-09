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
) -> tuple[gpd.GeoDataFrame, dict[str, gpd.GeoDataFrame]]:
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
    lu_map: geopandas.GeoDataFrame
        Land use map as GeoDataFrame.
    layers: dict[str, geopandas.GeoDataFrame]
        Dictionary of individual land use layers.
    """
    # Clean and explode region
    region = region.copy()
    region["geometry"] = region.geometry.buffer(0)
    region = region.explode(index_parts=False, ignore_index=True)
    region = gpd.GeoDataFrame(geometry=[region.union_all()], crs=region.crs)
    region = region.explode(index_parts=False, ignore_index=True)

    # Merge line layers
    lines = pd.concat([roads, railways, waterways], ignore_index=True)
    lines = lines.merge(landuse_mapping, on="fclass", how="left")

    # Buffer and clip created polygons for line layers
    da_closed_paved = _linestring_buffer(lines, "closed_paved")
    da_closed_paved = _clip(region, da_closed_paved)

    da_open_paved = _linestring_buffer(lines, "open_paved")
    da_open_paved = _clip(region, da_open_paved)

    da_water_lines = _linestring_buffer(lines, "water")
    da_water_lines = _clip(region, da_water_lines)
    da_water_area = _clip(region, water_area)
    if not da_water_area.empty:
        da_water_area["reclass"] = "water"
    # Combine water from area and lines
    da_water = pd.concat([da_water_area, da_water_lines], ignore_index=True)

    # Clip building footprints
    da_paved_roof = _clip(region, buildings_area)
    if not da_paved_roof.empty:
        da_paved_roof["reclass"] = "paved_roof"

    # Combine all layers in correct overlay order
    da_unpaved = region.assign(reclass="unpaved")  # Base layer: unpaved
    lu_map = da_unpaved.copy()
    for layer in [da_water, da_open_paved, da_closed_paved, da_paved_roof]:
        lu_map = _combine_layers(lu_map, layer)

    # Final cleanup and dissolve by landuse
    lu_map = _clip(region, lu_map)
    lu_map = lu_map.dissolve(by="reclass", aggfunc="sum").reset_index()

    layers: dict[str, gpd.GeoDataFrame] = {
        "closed_paved": da_closed_paved,
        "open_paved": da_open_paved,
        "paved_roof": da_paved_roof,
        "water": da_water,
    }
    # Recompute unpaved as difference
    to_subtract = [
        layer for layer in layers.values() if layer is not None and not layer.empty
    ]
    if to_subtract:
        all_geom: gpd.GeoDataFrame = pd.concat(to_subtract, ignore_index=True)
        unpaved_geom = region.geometry.difference(all_geom.union_all())
        da_unpaved["geometry"] = unpaved_geom
        da_unpaved = da_unpaved.explode(index_parts=False, ignore_index=True)
    else:
        da_unpaved = region.assign(reclass="unpaved")
    layers.update(unpaved=da_unpaved)
    return lu_map, layers


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


def _clip(region: gpd.GeoDataFrame, to_clip: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Clipping geodataframe to region."""
    if to_clip is None or to_clip.empty:
        return gpd.GeoDataFrame(
            columns=["geometry"], geometry="geometry", crs=region.crs
        )

    gdf = to_clip.copy()
    gdf["geometry"] = gdf.geometry.buffer(0)
    gdf = gdf.explode(index_parts=False, ignore_index=True)
    clipped = gpd.overlay(gdf, region, how="intersection", keep_geom_type=True)

    if clipped.empty:
        return gpd.GeoDataFrame(
            columns=gdf.columns, geometry="geometry", crs=region.crs
        )

    return clipped
