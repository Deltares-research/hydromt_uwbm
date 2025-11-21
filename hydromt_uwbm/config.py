from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import tomllib
from pydantic import BaseModel, Field, ValidationError

__all__ = ["UWMBConfig", "UWMBConfigWriter", "read_inifile"]


class UWMBConfig(BaseModel):
    # run
    title: str = Field(..., description="Title of the configuration")
    name: str | None = Field(default=None, description="Name of the simulation")
    starttime: datetime | None = Field(
        default=None, description="Simulation start time in format YYYY-MM-DD HH:MM:SS"
    )
    endtime: datetime | None = Field(
        default=None, description="Simulation end time in format YYYY-MM-DD HH:MM:SS"
    )
    timestepsecs: Literal[3600, 86400] | None = Field(
        default=None,
        description="Timestep length in seconds, must be 3600(hour) or 86400(day)",
    )

    # landuse
    soiltype: int = Field(default=..., description="Soil type", ge=0)
    croptype: int = Field(default=..., description="Crop type", ge=0)
    tot_area: float = Field(
        default=..., description="Total area of the study area in square meters", ge=0
    )
    area_type: Literal[0, 1] = Field(
        default=..., description="Area input type [0: fraction(default), 1: area]"
    )
    landuse_area: dict[str, float] | None = Field(
        default=None, description="Land use area values"
    )
    landuse_frac: dict[str, float] | None = Field(
        default=None, description="Land use area fractions"
    )

    # paved roof
    tot_pr_area: int = Field(
        default=..., description="Total area of paved roof in square meters", ge=0
    )
    pr_frac: float = Field(
        default=..., description="Paved roof fraction of total area [-]", ge=0, le=1
    )
    frac_pr_aboveGW: float = Field(
        ..., description="Part of buildings above Groundwater [-]", ge=0, le=1
    )
    discfrac_pr: float = Field(
        ...,
        description="Part of paved roof disconnected from sewer system [-]",
        ge=0,
        le=1,
    )
    intstorcap_pr: float = Field(
        ..., description="Internal storage capacity of paved roof", ge=0
    )
    intstor_pr_t0: float = Field(
        ..., description="Initial interception storage of paved roof", ge=0
    )

    # closed paved
    tot_cp_area: int = Field(
        default=..., description="Total area of closed paved in square meters", ge=0
    )
    cp_frac: float = Field(
        default=..., description="Closed paved fraction of total area [-]", ge=0, le=1
    )
    discfrac_cp: float = Field(
        ...,
        description="Part of closed paved disconnected from sewer system [-]",
        ge=0,
        le=1,
    )
    intstorcap_cp: float = Field(
        ..., description="Internal storage capacity of closed paved", ge=0
    )
    intstor_cp_t0: float = Field(
        ..., description="Initial interception storage of closed paved", ge=0
    )

    # open paved
    tot_op_area: int = Field(
        default=..., description="Total area of open paved in square meters", ge=0
    )
    op_frac: float = Field(
        default=..., description="Open paved fraction of total area [-]", ge=0, le=1
    )
    discfrac_op: float = Field(
        ...,
        description="Part of open paved disconnected from sewer system [-]",
        ge=0,
        le=1,
    )
    intstorcap_op: float = Field(
        ..., description="Internal storage capacity of open paved", ge=0
    )
    infilcap_op: float = Field(
        ..., description="Infiltration capacity of open paved", ge=0
    )
    intstor_op_t0: float = Field(
        ..., description="Initial interception storage of open paved", ge=0
    )

    # unpaved
    tot_up_area: int = Field(
        default=..., description="Total area of unpaved in square meters", ge=0
    )
    up_frac: float = Field(
        default=..., description="Unpaved fraction of total area [-]", ge=0, le=1
    )
    intstorcap_up: float = Field(
        ..., description="Internal storage capacity of unpaved", ge=0
    )
    infilcap_up: float = Field(
        ..., description="Infiltration capacity of unpaved", ge=0
    )
    fin_intstor_up_t0: float = Field(
        ..., description="Initial interception storage of unpaved", ge=0
    )

    # groundwater
    w: float = Field(
        ...,
        description="Drainage resistance from groundwater to open water (w) [d]",
        ge=0,
    )
    seepage_define: int = Field(
        ...,
        description="Seepage to deep groundwater defined as either constant downward flux or dynamic computed flux determined by head difference and resistance [0=flux; 1=level]",
        ge=0,
        le=1,
    )
    down_seepage_flux: float = Field(
        ...,
        description="Constant downward flux from shallow groundwater to deep groundwater [mm/d]",
        ge=0,
    )
    head_deep_gw: float = Field(
        ..., description="Hydraulic head of deep groundwater [m below ground level]"
    )
    vc: float = Field(
        ...,
        description="Vertical flow resistance from shallow groundwater to deep groundwater (vc) [d]",
        ge=0,
    )
    gwl_t0: float = Field(
        ...,
        description='Initial groundwater level (at t=0) relating to "storcap_ow" [m-SL]',
    )

    # open water
    tot_ow_area: int = Field(
        default=..., description="Total area of open water in square meters", ge=0
    )
    ow_frac: float = Field(
        default=..., description="Open water fraction of total area [-]", ge=0, le=1
    )
    frac_ow_aboveGW: float = Field(
        ..., description="Part of open water above Groundwater [-]", ge=0, le=1
    )
    storcap_ow: float = Field(..., description="Storage capacity of open water", ge=0)
    q_ow_out_cap: float = Field(..., description="Outflow capacity of open water", ge=0)

    # sewer system
    swds_frac: float = Field(
        ..., description="Part of urban paved area with SWDS [-]", ge=0, le=1
    )
    storcap_swds: float = Field(..., description="Storage capacity of SWDS", ge=0)
    storcap_mss: float = Field(..., description="Storage capacity of MSS", ge=0)
    rainfall_swds_so: float = Field(
        ..., description="Rainfall intensity for SWDS overflow [mm/timestep]", ge=0
    )
    rainfall_mss_ow: float = Field(
        ..., description="Rainfall intensity for MSS overflow [mm/timestep]", ge=0
    )
    stor_swds_t0: float = Field(..., description="Initial storage of SWDS at t=0", ge=0)
    so_swds_t0: float = Field(..., description="Initial outflow from SWDS at t=0", ge=0)
    stor_mss_t0: float = Field(..., description="Initial storage of MSS at t=0", ge=0)
    so_mss_t0: float = Field(..., description="Initial outflow from MSS at t=0", ge=0)

    # Define sections for serialization
    _SECTIONS = [
        ("run", ["title", "name", "starttime", "endtime", "timestepsecs"]),
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
        all_entries = set()

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
                all_entries.add(name)
                value = getattr(self, name)
                if value is None:
                    continue
                desc = UWMBConfig.model_fields[name].description
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

        if not set(UWMBConfig.model_fields.keys()).issubset(all_entries):
            missing = set(UWMBConfig.model_fields.keys()) - all_entries
            raise ValueError(
                f"Some fields were not serialized: {missing}. Please add them to the correct section in ``UWMBConfig._SECTIONS``."
            )

        return "\n".join(lines)

    @staticmethod
    def from_file(path: Path) -> "UWMBConfig":
        with open(path, "rb") as f:
            cfg = tomllib.load(f)
        return UWMBConfig.create(cfg)

    @staticmethod
    def create(data: dict) -> "UWMBConfig":
        """
        Validate a config dict against UWMBConfig and return nicely formatted messages.
        Returns:
            invalid_params: list of "param_name: value, error message, param_description"
            unknown_params: list of unknown keys
        """
        try:
            return UWMBConfig(**data)
        except ValidationError as e:
            known_keys = set(UWMBConfig.model_fields.keys())
            unknown_keys = [k for k in data.keys() if k not in known_keys]
            invalid_params: list[str] = []

            for err in e.errors():
                loc = err.get("loc", [])
                msg = err.get("msg", "")
                if not loc:
                    continue
                key = loc[0]
                # Grab description if available
                desc = (
                    UWMBConfig.model_fields[key].description
                    if key in UWMBConfig.model_fields
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


class UWMBConfigWriter:
    def __init__(self, config: UWMBConfig):
        self.config = config

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "UWMBConfigWriter":
        config = UWMBConfig.create(data)
        return UWMBConfigWriter(config)

    @staticmethod
    def from_file(path: Path) -> "UWMBConfigWriter":
        cfg = UWMBConfig.from_file(path)
        return UWMBConfigWriter(cfg)

    def serialize(self) -> str:
        return self.config.to_ini()

    def write(self, path: Path | str) -> None:
        with open(path, "w") as f:
            f.write(self.serialize())


def read_inifile(path: Path) -> dict[str, Any]:
    with open(path, "rb") as f:
        cfg = tomllib.load(f)
    return cfg
