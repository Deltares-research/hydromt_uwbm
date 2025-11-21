import datetime
import logging
from pathlib import Path

import geopandas as gpd
import hydromt
import pandas as pd
from hydromt.models import VectorModel

from hydromt_uwbm.config import UWMBConfigWriter, read_inifile
from hydromt_uwbm.workflows import landuse

__all__ = ["UWBM"]

DATADIR = Path(__file__).parent / "data"

logger = logging.getLogger(__name__)


class UWBM(VectorModel):
    """This is the uwbm class."""

    _NAME: str = "UWBM"
    _CONF: str = "neighbourhood_params.ini"
    _DATADIR: Path = DATADIR
    _GEOMS = {"OSM": "OpenStreetMap"}
    _FORCING = {
        "time": "date",
        "precip": "P_atm",
        "PET": "E_pot_OW",
    }
    _FORCING_COLUMN_ORDER = ["P_atm", "Ref.grass", "E_pot_OW"]
    # Name of default folders to create in the model directory
    _FOLDERS: list[str] = [
        "input",
        "input/project_area",
        "input/landuse",
        "input/config",
        "output",
        "output/forcing",
        "output/landuse",
        "output/config",
    ]

    _CATALOGS = [(_DATADIR / "parameters_data.yml").as_posix()]
    # Cli args forwards the region and res arguments to the correct functions
    # Uncomment, check and overwrite if needed
    # _CLI_ARGS = {"region": <your func>, "res": <your func>}

    def __init__(
        self,
        root: str | Path | None = None,
        mode: str = "w+",
        config_fn: str | None = None,
        data_libs: list[str] | str | None = None,
        logger: logging.Logger = logger,
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
        # Add model _CATALOGS to the data_libs
        if self._CATALOGS:
            if isinstance(data_libs, str):
                data_libs = [data_libs]
            if data_libs is None:
                data_libs = []
            data_libs = data_libs + self._CATALOGS

        super().__init__(
            root=root,
            mode=mode,
            config_fn=config_fn,
            data_libs=data_libs,
            logger=logger,
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
        crs: str = "EPSG:3857",
    ):
        """Setup project geometry from vector."""
        if ts not in [3600, 86400]:
            raise ValueError("Timestep must be either 3600 (hours) or 86400 (days)")

        if not isinstance(t_start, datetime.datetime):
            t_start = pd.to_datetime(t_start)
        if not isinstance(t_end, datetime.datetime):
            t_end = pd.to_datetime(t_end)

        kind, region = hydromt.workflows.parse_region(
            region,
            data_catalog=self.data_catalog,
            logger=self.logger,
        )

        if kind in ["geom", "bbox"]:
            self.setup_region(region=region, hydrography_fn=None, basin_index_fn=None)
        else:
            raise IOError(
                "Provide project region as either GeoPandas DataFrame or BoundingBox."
            )

        region = self.geoms["region"].to_crs(crs)
        self.set_geoms(region, name="region")

        self.set_config("starttime", t_start)
        self.set_config("endtime", t_end)
        self.set_config("timestepsecs", ts)
        self.set_config("name", name)

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
        starttime = self.get_config("starttime")
        endtime = self.get_config("endtime")
        freq = pd.to_timedelta(self.get_config("timestepsecs"), unit="s")
        geom = self.region

        precip = self.data_catalog.get_rasterdataset(
            precip_fn,
            geom=geom,
            buffer=2,
            time_tuple=(starttime, endtime),
            variables=["precip"],
        )
        precip = hydromt.workflows.resample_time(precip, freq=freq, downsampling="sum")
        precip_out = precip.raster.zonal_stats(
            geom,
            stats=["mean"],
            all_touched=True,
        )
        precip_out = precip_out["precip_mean"].to_dataframe(name="P_atm")
        precip_out = precip_out.reset_index().set_index("time")
        precip_out = precip_out[["P_atm"]]
        precip_out.attrs.update({"precip_fn": precip_fn})

        self.set_forcing(precip_out, name="precip")

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
        starttime = self.get_config("starttime")
        endtime = self.get_config("endtime")
        timestep = self.get_config("timestepsecs")
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
            buffer=1,
            time_tuple=(starttime, endtime),
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
            pet_out = hydromt.workflows.pet_debruin(
                ds_out["temp"],
                ds_out["press_msl"],
                ds_out["kin"],
                ds_out["kout"],
                timestep=timestep,
                cp=1005.0,
                beta=20.0,
                Cs=110.0,
            )

        elif pet_method == "makkink":
            pet_out = hydromt.workflows.pet_makkink(
                ds_out["temp"],
                ds_out["press_msl"],
                ds_out["kin"],
                timestep=timestep,
                cp=1005.0,
            )

        pet_out = hydromt.workflows.resample_time(
            pet_out, freq=freq, downsampling="mean"
        )

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
        self.set_forcing(pet_df, name="pet")

    def setup_landuse(
        self,
        soiltype: int,
        croptype: int,
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
        soiltype: int
            Soil type code according to UWB model documentation.
        croptype: int
            Crop type code according to UWB model documentation.
        source: str, optional
            Source of landuse base files. Current default is "osm".
        landuse_mapping_fn: str, optional
            Name of landuse mapping translation table. Default is "osm_mapping_default".
        """
        self.logger.info("Preparing landuse map.")

        sources = ["osm"]
        if source not in sources:
            raise IOError(f"Provide source of landuse files from {sources}")

        if source == "osm":
            if landuse_mapping_fn is None:
                self.logger.info(
                    f"No landuse translation table provided. Using default translation "
                    f"table for source {source}."
                )
                fn_map = f"{source}_mapping_default"
            else:
                fn_map = landuse_mapping_fn
            if not Path(fn_map).exists() and fn_map not in self.data_catalog:
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
                try:
                    osm_layer = self.data_catalog.get_geodataframe(
                        layer, geom=self.region, crs=self.crs
                    )
                    osm_layer = osm_layer.to_crs(self.crs)
                    self.set_geoms(osm_layer, name=layer)
                except Exception:
                    osm_layer = gpd.GeoDataFrame(
                        columns=["geometry"], geometry="geometry", crs=self.crs
                    )
                    osm_layer = osm_layer.to_crs(self.crs)
                    self.set_geoms(osm_layer, name=layer)

            lu_map = landuse.landuse_from_osm(
                region=self.region,
                roads=self.geoms["osm_roads"],
                railways=self.geoms["osm_railways"],
                waterways=self.geoms["osm_waterways"],
                buildings_area=self.geoms["osm_buildings"],
                water_area=self.geoms["osm_water"],
                landuse_mapping=table,
            )

        # Add landuse map to geoms
        self.set_geoms(lu_map, name="landuse_map")
        # Create landuse table from landuse map
        lu_table = landuse.landuse_table(lu_map=self.geoms["landuse_map"])
        # Add landuse table to tables
        self.set_tables(lu_table, name="landuse_table")
        # Add landuse categories to config
        df_landuse = self.tables["landuse_table"]

        for reclass in df_landuse["reclass"]:
            self.set_config(
                "landuse_area",
                f"{reclass}",
                float(df_landuse.loc[df_landuse["reclass"] == reclass, "area"].iloc[0]),
            )
            self.set_config(
                "landuse_frac",
                f"{reclass}",
                float(df_landuse.loc[df_landuse["reclass"] == reclass, "frac"].iloc[0]),
            )

        self.set_config("soiltype", soiltype)
        self.set_config("croptype", croptype)

        keys = ["op", "ow", "up", "pr", "cp"]
        for key in keys:
            self.set_config(f"tot_{key}_area", self.get_config("landuse_area", key))
            self.set_config(f"{key}_frac", self.get_config("landuse_frac", key))

        self.set_config("tot_area", self.get_config("landuse_area", "tot_area"))

    def write_model_config(
        self,
        config_fn: str | None = None,
    ):
        """Write TOML configuration file based on landuse calculations.

        Parameters
        ----------
        config_fn: str, optional
            Path to the config file. Default is self.config['name']
        """
        if config_fn is None:
            if "name" not in self.config:
                raise ValueError(
                    "Set model name in config before setting up model "
                    "config by calling `setup_project` first."
                )
            config_fn = f"ep_neighbourhood_{self.config['name']}.ini"

        path = Path(self.root, "input", "config", config_fn).as_posix()
        self._configwrite(path)

    # ==================================================================================
    # I/O METHODS
    def read(self, components: list[str] | None = None):
        """Generic read function for all model workflows."""
        if components is None:
            components = ["config", "forcing", "tables", "geoms"]

        if "config" in components:
            self.read_config()
        if "forcing" in components:
            self.read_forcing()
        if "tables" in components:
            self.read_tables()
        if "geoms" in components:
            self.read_geoms()

    def write(self, components: list[str] | None = None):
        """Generic write function for all model workflows."""
        if components is None:
            components = ["config", "forcing", "tables", "geoms"]
        if "config" in components:
            self.write_config()
            self.write_model_config()
        if "forcing" in components:
            self.write_forcing()
        if "tables" in components:
            self.write_tables()
        if "geoms" in components:
            self.write_geoms()

    def read_forcing(self, fn: str = "output/forcing/*.csv", **kwargs):
        """Read forcing from model folder in model ready format (.csv)."""
        self._assert_read_mode()
        path = Path(self.root, fn)
        files = path.parent.glob(path.name)

        for path in files:
            df = pd.read_csv(path, sep=",", parse_dates=["date"], **kwargs)
            df = df.set_index("date")

            for col in df.columns:
                self.set_forcing(df[[col]], name=col)

    def write_forcing(self, fn: str | None = None, decimals: int = 2, **kwargs):
        """Write forcing at ``fn`` in model ready format (.csv).

        Parameters
        ----------
        fn: str, Path, optional
            Path to save output csv file. Default folder is output/forcing.
        decimals: int, optional
            Round the ouput data to the given number of decimals.
        """
        if len(self.forcing) > 0:
            self._assert_write_mode()
            self.logger.info("Writing forcing file")

            start = self.get_config("starttime")
            end = self.get_config("endtime")
            ts = datetime.timedelta(seconds=self.get_config("timestepsecs"))
            time_index = pd.date_range(start=start, end=end, freq=ts, name="date")
            df = pd.DataFrame(data=self.forcing, index=time_index)
            df.index.name = "date"

            if not all(col in df.columns for col in self._FORCING_COLUMN_ORDER):
                raise ValueError(
                    f"Not all required forcing columns found in data.\n"
                    f"Required columns are {self._FORCING_COLUMN_ORDER}\n"
                    f"Found columns are {df.columns.tolist()}"
                )
            df = df.loc[:, self._FORCING_COLUMN_ORDER]

            if decimals is not None:
                df = df.round(decimals)

            if fn is None:
                years = int((end - start).days / 365.25)
                h = int(ts.total_seconds() / 3600)
                fn = f"output/forcing/Forcing_{self.config['name']}_{years}y_{h}h.csv"

            path = Path(self.root, fn)
            df.to_csv(path, sep=",", date_format="%d-%m-%Y %H:%M", **kwargs)

    def read_geoms(self, fn: str = "output/landuse/*.geojson", **kwargs):
        return super().read_geoms(fn, **kwargs)

    def write_geoms(
        self,
        fn: str = "output/landuse/{name}.geojson",
        to_wgs84: bool = False,
        **kwargs,
    ) -> None:
        super().write_geoms(fn=fn, to_wgs84=to_wgs84, **kwargs)

    def read_tables(self, fn: str = "output/landuse/*.csv", **kwargs):
        return super().read_tables(fn, **kwargs)

    def write_tables(self, fn: str = "output/landuse/{name}.csv", **kwargs):
        super().write_tables(fn=fn, **kwargs)

    def read_config(self, config_fn: str | None = None):
        if config_fn is not None:
            path = Path(self.root, config_fn)
        elif not self._read:  # write-only mode > read default config.
            path = Path(self._DATADIR, self._NAME, self._CONF)
        else:
            path = Path(
                self.root,
                "output",
                "config",
                self._config_fn,
            )
        return super().read_config(path.as_posix())

    def write_config(
        self, config_name: str | None = None, config_root: str | None = None
    ):
        config_root = Path(self.root, "output", "config").as_posix()
        return super().write_config(config_name, config_root=config_root)

    def _configread(self, fn: str) -> dict:
        """Read TOML configuration file.

        This function serves as alternative to the default read_config function
        to support ini files without headers.
        """
        return read_inifile(fn)

    def _configwrite(self, fn: str):
        """Write TOML configuration file."""
        UWMBConfigWriter.from_dict(self.config).write(fn)
