import datetime
import logging
from pathlib import Path

import geopandas as gpd
import hydromt.model.processes.meteo as hmt_meteo
import hydromt.model.processes.region as hmt_region
import pandas as pd
from hydromt import Model
from hydromt.model.components import GeomsComponent, TablesComponent

from hydromt_uwbm.components.config import UWBMConfigComponent
from hydromt_uwbm.components.forcing import UWBMForcingComponent
from hydromt_uwbm.workflows import landuse

__all__ = ["UWBM"]
__hydromt_eps__ = ["UWBM"]  # core entrypoints

DATADIR = Path(__file__).parent / "data"

logger = logging.getLogger(__name__)


class UWBM(Model):
    """This is the uwbm class."""

    name: str = "UWBM"

    def __init__(
        self,
        root: str | Path | None = None,
        mode: str = "w+",
        data_libs: list[str] | str | None = None,
    ):
        """Initialize the uwbm model class UWBM.

        Contains methods to read, write, setup and update uwbm models.

        Parameters
        ----------
        root : str, Path, optional
            Path to the model folder
        mode : {'w', 'w+', 'r', 'r+'}, optional
            Mode to open the model, by default 'w'
        config_fn : str, Path, optional
            Path to the model configuration file, by default None to read
            from template in build mode or default name in update mode.
        data_libs : list of str, optional
            list of data catalogs to use, by default None.
        logger : logging.Logger, optional
            Logger to use, by default logger
        """
        self.config = UWBMConfigComponent(
            self,
            filename="input/neighbourhood_params.ini",
            default_template_filename=(
                DATADIR / "UWBM/neighbourhood_params.ini"
            ).as_posix(),
        )
        self.forcing = UWBMForcingComponent(self, filename="input/{name}.csv")
        self.geoms = GeomsComponent(
            self,
            filename="geoms/{name}.geojson",
            region_filename="geoms/region.geojson",
        )
        self.landuse = TablesComponent(self, filename="landuse/{name}.csv")

        components = {
            "config": self.config,
            "forcing": self.forcing,
            "geoms": self.geoms,
            "landuse": self.landuse,
        }

        data_libs = data_libs or []
        param_data = (DATADIR / "parameters_data.yml").as_posix()
        if isinstance(data_libs, str):
            data_libs = [data_libs]
        if param_data not in data_libs:
            data_libs.append(param_data)

        super().__init__(
            root=root,
            mode=mode,
            components=components,
            data_libs=data_libs,
            region_component="geoms",
        )

    # ==================================================================================
    # SETUP METHODS
    def setup_project(
        self,
        region: dict,
        name: str,
        t_start: str | datetime.datetime,
        t_end: str | datetime.datetime,
        ts: int = 3600,
        crs: int = 3857,
    ):
        """Setup project geometry from vector."""
        if ts not in [3600, 86400]:
            raise ValueError("Timestep must be either 3600 (hours) or 86400 (days)")

        if not isinstance(t_start, datetime.datetime):
            t_start = pd.to_datetime(t_start)
        if not isinstance(t_end, datetime.datetime):
            t_end = pd.to_datetime(t_end)

        gdf = self._parse_region(region, crs=crs)
        self.geoms.set(gdf, name="region")

        self.config.set("starttime", t_start)
        self.config.set("endtime", t_end)
        self.config.set("timestep", ts)
        self.config.set("name", name)

    def setup_precip_forcing(
        self,
        precip_fn: str = "era5_hourly",
        **kwargs,
    ) -> None:
        """Generate area-averaged, tabular precipitation forcing for geom.

        Adds model layer:

        * **precip**: precipitation [mm]

        Parameters
        ----------
        precip_fn : str, default era5_hourly
            Precipitation data source.

            * Required variable: ['precip']
        """
        if precip_fn is None:
            return
        starttime = self.config.get_value("starttime")
        endtime = self.config.get_value("endtime")
        freq = pd.to_timedelta(self.config.get_value("timestep"), unit="s")
        geom = self.region

        precip = self.data_catalog.get_rasterdataset(
            precip_fn,
            geom=geom,
            buffer=2,
            time_range=(starttime, endtime),
            variables=["precip"],
        )
        precip = hmt_meteo.resample_time(precip, freq=freq, downsampling="sum")
        precip_out = precip.raster.zonal_stats(
            geom,
            stats=["mean"],
            all_touched=True,
        )
        precip_out = precip_out["precip_mean"].to_dataframe(name="P_atm")
        precip_out = precip_out.reset_index().set_index("time")
        precip_out = precip_out[["P_atm"]]
        precip_out.attrs.update({"precip_fn": precip_fn})
        precip_out = precip_out.round(3)
        self.forcing.set(precip_out, name="precip")

    def setup_pet_forcing(
        self,
        temp_pet_fn: str = "era5_hourly",
        pet_method: str = "debruin",
    ) -> None:
        """Generate area-averaged, tabular reference evapotranspiration forcing for geom

        Adds model layer:

        * **pet**: reference evapotranspiration [mm]

        Parameters
        ----------
        temp_pet_fn : str, optional
            Name or path of data source with variables to calculate temperature
            and reference evapotranspiration, see data/forcing_sources.yml.
            By default 'era5_hourly'.

            * Required variable for temperature: ['temp']

            * Required variables for De Bruin reference evapotranspiration: \
                ['temp', 'press_msl', 'kin', 'kout']

            * Required variables for Makkink reference evapotranspiration: \
                ['temp', 'press_msl', 'kin']
        pet_method : str, optional
            Method to calculate reference evapotranspiration. Options are
            'debruin' (default) or 'makkink'.
        """
        if temp_pet_fn is None:
            return
        starttime = self.config.get_value("starttime")
        endtime = self.config.get_value("endtime")
        timestep = self.config.get_value("timestep")
        freq = pd.to_timedelta(timestep, unit="s")
        geom = self.region

        variables = ["temp"]
        if pet_method == "debruin":
            variables += ["press_msl", "kin", "kout"]
        elif pet_method == "makkink":
            variables += ["press_msl", "kin"]
        else:
            methods = [
                "debruin",
                "makking",
            ]
            raise ValueError(f"Unknown pet method {pet_method}, select from {methods}")

        ds = self.data_catalog.get_rasterdataset(
            temp_pet_fn,
            geom=geom,
            buffer=2,
            time_range=(starttime, endtime),
            variables=variables,
            single_var_as_array=False,
        )
        ds_out = ds.raster.zonal_stats(
            geom,
            stats=["mean"],
            all_touched=True,
        )
        ds_out = ds_out.rename_vars({f"{var}_mean": var for var in variables})

        if pet_method == "debruin":
            pet_out = hmt_meteo.pet_debruin(
                ds_out["temp"],
                ds_out["press_msl"],
                ds_out["kin"],
                ds_out["kout"],
                timestep=timestep,
                cp=1005.0,
                beta=20.0,
                cs=110.0,
            )

        elif pet_method == "makkink":
            pet_out = hmt_meteo.pet_makkink(
                ds_out["temp"],
                ds_out["press_msl"],
                ds_out["kin"],
                timestep=timestep,
                cp=1005.0,
            )

        pet_out = hmt_meteo.resample_time(pet_out, freq=freq, downsampling="mean")

        pet_df = pet_out.to_dataframe(name="E_pot_OW")
        pet_df = pet_df.reset_index().set_index("time")
        pet_df = pet_df[["E_pot_OW"]]

        pet_df["Ref.grass"] = pet_df["E_pot_OW"] * 0.8982

        # Update meta attributes with setup opt
        opt_attr = {
            "pet_fn": temp_pet_fn,
            "pet_method": pet_method,
        }
        pet_df.attrs.update(opt_attr)
        pet_df = pet_df.round(3)
        self.forcing.set(pet_df, name="pet")

    def setup_landuse(
        self,
        source: str = "osm",
        landuse_mapping_fn: str | None = None,
    ):
        """Generate landuse map for region based on provided base files.

        Adds model layer:
        * **lu_map**: polygon layer containing urban land use
        * **lu_table**: table containing urban land use surface areas [m2]

        Updates config:
        * **soiltype**: soil type code according to UWB model documentation
        * **croptype**: crop type code according to UWB model documentation
        * **landuse_area**: surface area of the land use clasess [m2]
        * **landuse_frac**: surface area fraction of the land use clasess [-]
        * **tot_*_area**: total area of the UWB land use classes [m2]
        * **tot_*_frac**: total area fraction of the UWB land use classes [-]

        Parameters
        ----------
        source: str, optional
            Source of landuse base files. Current default is "osm".
        landuse_mapping_fn: str, optional
            Name of landuse mapping translation table. Default is "osm_mapping_default".
        """
        logger.info("Preparing landuse map.")

        sources = ["osm"]
        if source not in sources:
            raise IOError(f"Provide source of landuse files from {sources}")

        if source == "osm":
            if landuse_mapping_fn is None:
                logger.info(
                    f"No landuse translation table provided. Using default translation "
                    f"table for source {source}."
                )
                fn_map = f"{source}_mapping_default"
            else:
                fn_map = landuse_mapping_fn
            if not Path(fn_map).exists() and not self.data_catalog.contains_source(
                fn_map
            ):
                raise ValueError(f"LULC mapping file not found: {fn_map}")

            table = self.data_catalog.get_dataframe(fn_map)
            if not all(
                item in table.columns for item in ["fclass", "width_t", "reclass"]
            ):
                raise IOError(
                    "Provide translation table with columns 'fclass', 'width_t', "
                    "'reclass'"
                )
            if not all(
                item in ["paved_roof", "closed_paved", "open_paved", "unpaved", "water"]
                for item in table["reclass"]
            ):
                raise IOError(
                    "Valid translation classes are 'paved_roof', 'closed_paved', "
                    "'open_paved', 'unpaved', 'water'"
                )
            if table["width_t"].dtypes not in ["float64", "int", "int64"]:
                raise IOError("Provide total width (width_t) values as float or int'")

            layers = [
                "osm_roads",
                "osm_railways",
                "osm_waterways",
                "osm_buildings",
                "osm_water",
            ]

            for layer in layers:
                osm_layer = self.data_catalog.get_geodataframe(
                    layer, geom=self.region, handle_nodata="warn"
                )
                if osm_layer is None or osm_layer.empty:
                    osm_layer = gpd.GeoDataFrame(
                        columns=["geometry"], geometry="geometry", crs=self.region.crs
                    )
                self.geoms.set(osm_layer, name=layer)

            lu_map = landuse.landuse_from_osm(
                region=self.region,
                roads=self.geoms.data["osm_roads"],
                railways=self.geoms.data["osm_railways"],
                waterways=self.geoms.data["osm_waterways"],
                buildings_area=self.geoms.data["osm_buildings"],
                water_area=self.geoms.data["osm_water"],
                landuse_mapping=table,
            )

        # Add landuse map to geoms
        self.geoms.set(lu_map, name="landuse_map")
        # Create landuse table from landuse map
        lu_table = landuse.landuse_table(lu_map=self.geoms.data["landuse_map"])
        # Add landuse table to tables
        self.landuse.set(lu_table, name="landuse_table")
        # Add landuse categories to config
        df_landuse = self.landuse.data["landuse_table"]

        for reclass in df_landuse["reclass"]:
            self.config.set(
                f"landuse_area.{reclass}",
                float(df_landuse.loc[df_landuse["reclass"] == reclass, "area"].iloc[0]),
            )
            self.config.set(
                f"landuse_frac.{reclass}",
                float(df_landuse.loc[df_landuse["reclass"] == reclass, "frac"].iloc[0]),
            )

        keys = ["op", "ow", "up", "pr", "cp"]
        for key in keys:
            self.config.set(
                f"tot_{key}_area", self.config.get_value(f"landuse_area.{key}")
            )
            self.config.set(f"{key}_frac", self.config.get_value(f"landuse_frac.{key}"))

        self.config.set("tot_area", self.config.get_value("landuse_area.tot_area"))

    # ==================================================================================
    # IO METHODS
    def write(self, components: list[str] | None = None) -> None:
        for p in ["input", "results", "model_run"]:
            (self.root.path / p).mkdir(parents=True, exist_ok=True)
        return super().write(components)

    # --------------------------------------------------------------------------
    def _parse_region(self, region: dict, crs: int) -> gpd.GeoDataFrame:
        crs = region.get("crs") or crs
        if region.get("bbox") is not None:
            gdf = hmt_region.parse_region_bbox(region, crs=crs)
        elif region.get("geom") is not None:
            gdf = hmt_region.parse_region_geom(region, crs=crs)
        else:
            raise IOError(
                "Provide region as either 'geom' with a gpd.GeoDataFrame or "
                "'bbox' with a list of coordinates."
            )

        return gdf
