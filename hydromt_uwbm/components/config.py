import logging
import tomllib
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from hydromt import hydromt_step
from hydromt._utils.path import _make_config_paths_relative
from hydromt.model.components.config import ConfigComponent
from pydantic import BaseModel, Field, ValidationError
from pydantic_core import PydanticUndefined

if TYPE_CHECKING:
    pass

__all__ = ["UWBMConfigComponent", "UwbmConfig"]

logger = logging.getLogger(__name__)


class UWBMConfigComponent(ConfigComponent):
    @hydromt_step
    def write(self, file_path: str | None = None) -> None:
        """Write configuration data to files."""
        self.root._assert_write_mode()

        if not self.data:
            logger.info(
                f"{self.model.name}.{self.name_in_model}: No config data found, skip writing."
            )
            return

        path = file_path or self._filename
        path = self.root.path / path
        path.parent.mkdir(parents=True, exist_ok=True)
        logger.info(
            f"{self.model.name}.{self.name_in_model}: Writing model config to {path}."
        )

        write_data = _make_config_paths_relative(self.data, self.root.path)

        config = UwbmConfig.create(write_data)
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            f.write(config.to_ini())


class UwbmConfig(BaseModel):
    # run
    title: str = Field(
        default="Neighbourhood config",
        description="Title of the configuration",
    )
    name: str = Field(
        default=...,
        description="Name of the simulation",
    )
    starttime: datetime = Field(
        default=...,
        description="Simulation start time in format YYYY-MM-DD HH:MM:SS",
    )
    endtime: datetime = Field(
        default=...,
        description="Simulation end time in format YYYY-MM-DD HH:MM:SS",
    )
    timestep: Literal[3600, 86400] = Field(
        default=...,
        description="Timestep length in seconds [3600: hourly, 86400: daily]",
    )
    soiltype: int = Field(
        default=7,
        description="Soil type",
        ge=0,
    )
    croptype: int = Field(
        default=1,
        description="Crop type",
        ge=0,
    )

    # landuse
    tot_area: float | None = Field(
        default=None,
        description="Total area of the study area [m2]",
        ge=0,
    )
    area_type: Literal[0, 1] = Field(
        default=0,
        description="Area input type [0: fraction(default), 1: area]",
    )
    landuse_area: dict[str, float] | None = Field(
        default=None,
        description="Land use area values [m2]",
    )
    landuse_frac: dict[str, float] | None = Field(
        default=None,
        description="Land use area fractions [-]",
    )

    # paved roof
    tot_pr_area: float | None = Field(
        default=None,
        description="Total area of paved roof [m2]",
        ge=0,
    )
    pr_frac: float | None = Field(
        default=None,
        description="Paved roof fraction of total area [-]",
        ge=0,
        le=1,
    )
    frac_pr_aboveGW: float = Field(
        default=1.0,
        description="Part of buildings above Groundwater [-]",
        ge=0,
        le=1,
    )
    discfrac_pr: float = Field(
        default=0.1,
        description="Part of paved roof disconnected from sewer system [-]",
        ge=0,
        le=1,
    )
    intstorcap_pr: float = Field(
        default=3.0,
        description="Interception storage capacity of paved roof [mm]",
        ge=0,
    )
    intstor_pr_t0: float = Field(
        default=0.0,
        description="Initial interception storage of paved roof (at t=0) [mm]",
        ge=0,
    )

    # closed paved
    tot_cp_area: float | None = Field(
        default=None,
        description="Total area of closed paved in square meters",
        ge=0,
    )
    cp_frac: float | None = Field(
        default=None,
        description="Closed paved fraction of total area [-]",
        ge=0,
        le=1,
    )
    discfrac_cp: float = Field(
        default=0.05,
        description="Part of closed paved disconnected from sewer system [-]",
        ge=0,
        le=1,
    )
    intstorcap_cp: float = Field(
        default=2.0,
        description="Interception storage capacity of closed paved",
        ge=0,
    )
    intstor_cp_t0: float = Field(
        default=0.0,
        description="Initial interception storage of closed paved (at t=0) [mm]",
        ge=0,
    )

    # open paved
    tot_op_area: float | None = Field(
        default=None,
        description="Total area of open paved [m2]",
        ge=0,
    )
    op_frac: float | None = Field(
        default=None,
        description="Open paved fraction of total area [-]",
        ge=0,
        le=1,
    )
    discfrac_op: float = Field(
        default=0.5,
        description="Part of open paved disconnected from sewer system [-]",
        ge=0,
        le=1,
    )
    intstorcap_op: float = Field(
        default=4.0,
        description="Interception storage capacity of open paved [mm]",
        ge=0,
    )
    infilcap_op: float = Field(
        default=24.0,
        description="Infiltration capacity of open paved [mm/d]",
        ge=0,
    )
    intstor_op_t0: float = Field(
        default=0.0,
        description="Initial interception storage of open paved (at t=0) [mm]",
        ge=0,
    )

    # unpaved
    tot_up_area: float | None = Field(
        default=None,
        description="Total area of unpaved [m2]",
        ge=0,
    )
    up_frac: float | None = Field(
        default=None,
        description="Unpaved fraction of total area [-]",
        ge=0,
        le=1,
    )
    intstorcap_up: float = Field(
        default=5.0,
        description="Interception storage capacity of unpaved [mm]",
        ge=0,
    )
    infilcap_up: float = Field(
        default=48.0,
        description="Infiltration capacity of unpaved [mm/d]",
        ge=0,
    )
    fin_intstor_up_t0: float = Field(
        default=0.0,
        description="Initial interception storage of unpaved (at t=0) [mm]",
        ge=0,
    )

    # groundwater
    w: float = Field(
        default=1000.0,
        description="Drainage resistance from groundwater to open water (w) [d]",
        ge=0,
    )
    seepage_define: Literal[0, 1] = Field(
        default=0,
        description="Seepage to deep groundwater defined as either constant downward flux or dynamic computed flux determined by head difference and resistance [0=flux; 1=level]",
    )
    down_seepage_flux: float = Field(
        default=0.0,
        description="Constant downward flux from shallow groundwater to deep groundwater [mm/d]",
        ge=0,
    )
    head_deep_gw: float = Field(
        default=20.0,
        description="Hydraulic head of deep groundwater [m below ground level]",
    )
    vc: float = Field(
        default=100000.0,
        description="Vertical flow resistance from shallow groundwater to deep groundwater (vc) [d]",
        ge=0,
    )
    gwl_t0: float = Field(
        default=1.5,
        description='Initial groudwater level (at t=0), usually taken as target water level, relating to "storcap_ow" [m-SL]',
    )

    # open water
    tot_ow_area: float | None = Field(
        default=None, description="Total area of open water [m2]", ge=0
    )
    ow_frac: float | None = Field(
        default=None, description="Open water fraction of total area [-]", ge=0, le=1
    )
    frac_ow_aboveGW: float = Field(
        default=0.0, description="Part of open water above Groundwater [-]", ge=0, le=1
    )
    storcap_ow: float = Field(
        default=1500.0,
        description="Storage capacity of open water (divided by 1000 is target open water level) [mm]",
        ge=0,
    )
    q_ow_out_cap: float = Field(
        default=3.0,
        description="predefined discharge capacity from open water (internal) to outside water (external) [mm/d over total area]",
        ge=0,
    )

    # sewer system
    swds_frac: float = Field(
        default=0.25,
        description="Part of urban paved area with storm water drainage system (SWDS) [-]",
        ge=0,
        le=1,
    )
    storcap_swds: float = Field(
        default=2.0,
        description="Storage capacity of storm water drainage system (SWDS) [mm]",
        ge=0,
    )
    storcap_mss: float = Field(
        default=2.0,
        description="Storage capacity of mixed sewer system (MSS) [mm]",
        ge=0,
    )
    rainfall_swds_so: float = Field(
        default=8.0,
        description="Rainfall intensity when SWDS overflow occurs on street [mm/timestep]",
        ge=0,
    )
    rainfall_mss_ow: float = Field(
        default=8.0,
        description="Rainfall intensity when combined overflow to open water occurs [mm/timestep]",
        ge=0,
    )

    stor_swds_t0: float = Field(
        default=0.0,
        description="Initial storage in storm water drainage system (SWDS) [mm]",
        ge=0,
    )
    so_swds_t0: float = Field(
        default=0.0,
        description="Initial sewer overflow from storm water drainage system (SWDS) [mm]",
        ge=0,
    )
    stor_mss_t0: float = Field(
        default=0.0,
        description="Initial storage in mixed sewer system (MSS) [mm]",
        ge=0,
    )
    so_mss_t0: float = Field(
        default=0.0,
        description="Initial sewer overflow from mixed sewer system (MSS) [mm]",
        ge=0,
    )

    # Define sections for serialization
    _SECTIONS = [
        ("run", ["title", "name", "starttime", "endtime", "timestep"]),
        (
            "landuse",
            [
                "soiltype",
                "croptype",
                "tot_area",
                "area_type",
                "landuse_area",
                "landuse_frac",
            ],
        ),
        (
            "paved roof",
            [
                "tot_pr_area",
                "pr_frac",
                "frac_pr_aboveGW",
                "discfrac_pr",
                "intstorcap_pr",
                "intstor_pr_t0",
            ],
        ),
        (
            "closed paved",
            ["tot_cp_area", "cp_frac", "discfrac_cp", "intstorcap_cp", "intstor_cp_t0"],
        ),
        (
            "open paved",
            [
                "tot_op_area",
                "op_frac",
                "discfrac_op",
                "intstorcap_op",
                "infilcap_op",
                "intstor_op_t0",
            ],
        ),
        (
            "unpaved",
            [
                "tot_up_area",
                "up_frac",
                "intstorcap_up",
                "infilcap_up",
                "fin_intstor_up_t0",
            ],
        ),
        (
            "groundwater",
            [
                "w",
                "seepage_define",
                "down_seepage_flux",
                "head_deep_gw",
                "vc",
                "gwl_t0",
            ],
        ),
        (
            "open water",
            ["tot_ow_area", "ow_frac", "frac_ow_aboveGW", "storcap_ow", "q_ow_out_cap"],
        ),
        (
            "sewer system",
            [
                "swds_frac",
                "storcap_swds",
                "storcap_mss",
                "rainfall_swds_so",
                "rainfall_mss_ow",
                "stor_swds_t0",
                "so_swds_t0",
                "stor_mss_t0",
                "so_mss_t0",
            ],
        ),
    ]

    class Config:
        keep_untouched = ()  # keep order stable

    def to_ini(self) -> str:
        def fmt(v: Any) -> str:
            if isinstance(v, str):
                return f'"{v}"'
            elif isinstance(v, bool):
                return "true" if v else "false"
            elif isinstance(v, dict):
                items = ", ".join(f'"{k}" = {fmt(val)}' for k, val in v.items())
                return f"{{ {items} }}"
            elif isinstance(v, list):
                items = ", ".join(fmt(item) for item in v)
                return f"[ {items} ]"
            return str(v)

        lines: list[str] = []
        serialized_fields = set()

        # Header
        lines.append("# This is a TOML-format neighbourhood (base) configuration file.")
        lines.append("# [-] indicates fraction, please type 0.75 to represent 75%.")
        lines.append("")
        for header, fields in self._SECTIONS:
            # Add section header
            lines.append("#" * (len(header) + 4))
            lines.append(f"# {header} #")
            lines.append("#" * (len(header) + 4))
            lines.append("")

            # Prepare simple/complex separation
            simple_entries = []
            other_entries = []
            for name in fields:
                value = getattr(self, name)
                if value is None:
                    continue
                serialized_fields.add(name)
                desc = UwbmConfig.model_fields[name].description
                assignment = f"{name} = {fmt(value)}"
                if isinstance(value, (int, float, str, bool, datetime)):
                    simple_entries.append((assignment, desc))
                else:
                    other_entries.append((name, value, desc))

            # Align simple entries
            if simple_entries:
                max_width = max(len(a) for a, _ in simple_entries)
            else:
                max_width = 0

            for assignment, desc in simple_entries:
                if desc:
                    lines.append(f"{assignment:<{max_width}} # {desc}")
                else:
                    lines.append(assignment)

            for name, value, desc in other_entries:
                if desc:
                    lines.append(f"# {desc}")
                lines.append(f"{name} = {fmt(value)}")
                lines.append("")
            lines.append("")

        fields_with_defaults = {
            name
            for name, field in UwbmConfig.model_fields.items()
            if field.default is not PydanticUndefined and field.default is not None
        }
        required_fields = {
            name
            for name, field in UwbmConfig.model_fields.items()
            if field.default is PydanticUndefined
        }
        expected_fields = fields_with_defaults | required_fields
        missing = expected_fields - serialized_fields
        if missing:
            # If you want to add an optional / required var to the config, please add them to the correct section in ``UwbmConfig._SECTIONS``.
            raise ValueError(
                f"Some required fields were not serialized: {missing}.\nPlease set these using functions ``UWMB.setup_x`` and/or ``UWMB.set_config()``."
            )

        return "\n".join(lines)

    @staticmethod
    def from_file(path: Path) -> "UwbmConfig":
        with open(path, "rb") as f:
            cfg = tomllib.load(f)
        return UwbmConfig.create(cfg)

    @staticmethod
    def create(data: dict) -> "UwbmConfig":
        """
        Validate a config dict against UwbmConfig and return nicely formatted messages.
        Returns:
            invalid_params: list of "param_name: value, error message, param_description"
            unknown_params: list of unknown keys
        """
        try:
            return UwbmConfig(**data)
        except ValidationError as e:
            all_keys = set(UwbmConfig.model_fields.keys())
            unknown_keys = [k for k in data.keys() if k not in all_keys]
            invalid_params: list[str] = []

            for err in e.errors():
                loc = err.get("loc", [])
                msg = err.get("msg", "")
                if not loc:
                    continue
                key = loc[0]
                # Grab description if available
                desc = (
                    UwbmConfig.model_fields[key].description
                    if key in UwbmConfig.model_fields
                    else None
                )

                value = data.get(key)
                invalid_params.append(f"{key}: {value=}, {msg=}, {desc=}")

            if invalid_params or unknown_keys:
                # raise a single error with nicely formatted messages
                msg_lines = []
                if invalid_params:
                    msg_lines.append(
                        "Invalid/missing parameters:\n  " + "\n  ".join(invalid_params)
                    )
                    msg_lines.append(
                        "Please set correct values using `UWBM.set_config` and retry."
                    )
                if unknown_keys:
                    msg_lines.append(
                        "Unknown parameters:\n  " + "\n  ".join(unknown_keys)
                    )
                    msg_lines.append("Please remove these parameters and retry.")
                raise ValueError("\n\n".join(msg_lines))
            else:
                # re-raise original error if no specific info could be extracted
                raise
