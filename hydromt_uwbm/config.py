import codecs
import datetime
from pathlib import Path
from typing import Any

import tomli_w
import tomllib

__all__ = ["UWMBConfigWriter", "write_inifile", "read_inifile"]

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


class ConfigSection:
    def __init__(
        self,
        name: str,
        parameters: dict[str, Any] | None = None,
        comments: list[str] | None = None,
    ):
        self.name: str = name
        self.comments: list[str] = comments or []
        self.parameters: dict[str, Any] = parameters or {}

    def serialize(self) -> str:
        lines = []
        if self.name:
            lines.append("#" * (len(self.name) + 4))
            lines.append(f"# {self.name} #")
            lines.append("#" * (len(self.name) + 4))
            lines.append("\n")

        if self.comments:
            for c in self.comments:
                lines.append(f"# {c}")
            lines.append("\n")

        if self.parameters:
            for key, value in self.parameters.items():
                if toml_line := self._toml_compatible_key_value(key, value):
                    lines.append(toml_line)
            lines.append("\n")
        return "\n".join(lines)

    @staticmethod
    def _toml_compatible_key_value(key: str, value: Any) -> str | None:
        """
        Convert a key/value pair into a TOML-compatible line.

        The logic is simple:
        - Everything is serialized via _to_toml().
        - Inline tables are used for dicts.
        - Lists are always inline arrays.
        """
        if value is None:
            return None

        return f"{key} = {ConfigSection._to_toml(value)}"

    @staticmethod
    def _to_toml(value: Any) -> str:
        """
        Convert a Python object to a TOML-compatible string.
        Handles:
          - primitive types
          - datetime
          - inline dicts (inline tables)
          - lists of primitives, datetime, dicts
        """
        # primitive types
        if isinstance(value, str):
            return f'"{value}"'
        elif isinstance(value, bool):
            return f"{value}".lower()
        elif isinstance(value, (int, float)):
            return f"{value}"
        elif isinstance(value, datetime.datetime):
            return f"{value.strftime(DATETIME_FORMAT)}"
        # inline table
        elif isinstance(value, dict):
            items = [f"{k} = {ConfigSection._to_toml(v)}" for k, v in value.items()]
            return "{ " + ", ".join(items) + " }"
        # inline list
        elif isinstance(value, list):
            items = [ConfigSection._to_toml(v) for v in value]
            return "[" + ", ".join(items) + "]"

        raise TypeError(f"Unsupported type for TOML serialization: {type(value)}")

    def set_parameter(self, name: str, value: Any) -> None:
        self.parameters[name] = value

    def add_comment(self, comment: str) -> None:
        self.comments.append(comment)


class ConfigWriter:
    def __init__(self):
        self.sections: list[ConfigSection] = [ConfigSection(name="runtime")]

    def has_parameter(self, parameter_name: str) -> bool:
        for section in self.sections:
            if parameter_name in section.parameters:
                return True
        return False

    def get_parameter(self, parameter_name: str) -> tuple[Any | None, str | None]:
        for section in self.sections:
            if parameter_name in section.parameters:
                return section.parameters.get(parameter_name), section.name
        return None, None

    def get_section_name_with_parameter(self, parameter_name: str) -> str | None:
        for section in self.sections:
            if parameter_name in section.parameters:
                return section.name
        return "runtime"  # default to runtime if not found

    def set_parameter(
        self,
        parameter_name: str,
        value: Any,
        section_name: str | None = None,
    ) -> None:
        section_name = (
            section_name
            or self.get_section_name_with_parameter(parameter_name)
            or "runtime"
        )
        for section in self.sections:
            if section.name == section_name:
                section.set_parameter(parameter_name, value)
                return

    def from_dict(self, config_dict: dict[str, Any]) -> None:
        for parameter_name, parameter_value in config_dict.items():
            section_name = self.get_section_name_with_parameter(parameter_name)
            self.set_parameter(
                parameter_name=parameter_name,
                value=parameter_value,
                section_name=section_name,
            )

    def from_file(self, path: Path) -> None:
        self.from_dict(read_inifile(path))

    def serialize(self) -> str:
        return "\n".join([section.serialize() for section in self.sections])

    def write(self, filepath: str | Path) -> None:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(self.serialize())


class UWMBConfigWriter(ConfigWriter):
    def __init__(self):
        self.sections: list[ConfigSection] = [
            ConfigSection(
                name="UWBM neighbourhood configuration",
                comments=[
                    "This is a TOML-format neighbourhood (base) configuration file.",
                    "[-] indicates fraction, please type 0.75 to represent 75%.",
                ],
                parameters={
                    "title": "Neighbourhood config",
                },
            ),
            ConfigSection(
                name="runtime",
                comments=[
                    "runtime parameters set during model building / execution",
                    "timestep [s]: 1 hour = 3600 sec(default), 1 day = 86400 sec",
                    "area input type [0: fraction(default), 1: area]",
                ],
                parameters={
                    "timestepsecs": 3600,
                    "area_type": 0,
                },
            ),
            ConfigSection(
                name="paved roof",
                comments=[
                    "total area of paved roof [m2]",
                    "paved roof fraction of total [-]",
                    "part of buildings above Groundwater [-]",
                    "part of paved roof disconnected from sewer system [-]",
                    "interception storage capacity on paved roof [mm]",
                    "initial interception storage on paved roof (at t=0) [mm]",
                ],
                parameters={
                    "tot_pr_area": 61297,
                    "pr_frac": 0.262,
                    "frac_pr_aboveGW": 1,
                    "discfrac_pr": 0.1,
                    "intstorcap_pr": 3,
                    "intstor_pr_t0": 0,
                },
            ),
            ConfigSection(
                name="closed paved",
                comments=[
                    "total area of closed paved [m2]",
                    "closed paved fraction of total [-]",
                    "part of closed paved disconnected from sewer system [-]",
                    "interception storage capacity on closed paved [mm]",
                    "initial interception storage on closed paved (at t=0) [mm]",
                ],
                parameters={
                    "tot_cp_area": 44594,
                    "cp_frac": 0.190,
                    "discfrac_cp": 0.05,
                    "intstorcap_cp": 2,
                    "intstor_cp_t0": 0,
                },
            ),
            ConfigSection(
                name="open paved",
                comments=[
                    "total area of open paved [m2]",
                    "open paved fraction of total [-]",
                    "part of open paved disconnected from sewer system [-]",
                    "interception storage capacity on open paved [mm]",
                    "infiltration capacity on open paved [mm/d]",
                    "initial interception storage on open paved (at t=0) [mm]",
                ],
                parameters={
                    "tot_op_area": 5355,
                    "op_frac": 0.023,
                    "discfrac_op": 0.5,
                    "intstorcap_op": 4,
                    "infilcap_op": 24,
                    "intstor_op_t0": 0,
                },
            ),
            ConfigSection(
                name="unsaturated zone",
                comments=["parameters for unsaturated zone are endogenous"],
            ),
            ConfigSection(
                name="unpaved",
                comments=[
                    "total area of unpaved [m2]",
                    "unpaved fraction of total [-]",
                    "interception storage capacity on unpaved [mm]",
                    "infiltration capacity on unpaved [mm/d]",
                    "initial final remaining interception storage on unpaved (at t=0) [mm]",
                ],
                parameters={
                    "tot_up_area": 120464,
                    "up_frac": 0.514,
                    "intstorcap_up": 5,
                    "infilcap_up": 48,
                    "fin_intstor_up_t0": 0,
                },
            ),
            ConfigSection(
                name="groundwater",
                comments=[
                    "groundwater area is endogenous, calculated from the formula: `tot_gw_area = tot_area * gw_frac` = tot_area * (pr_frac * frac_pr_aboveGW + cp_frac + op_frac + up_frac + ow_frac * frac_ow_aboveGW)",
                    "drainage resistance from groundwater to open water (w) [d]",
                    "seepage to deep groundwater defined as either constant downward flux",
                    "or dynamic computed flux determined by head difference and resistance [0=flux; 1=level]",
                    "constant downward flux from shallow groundwater to deep groundwater [mm/d]",
                    "hydraulic head of deep groundwater [m below ground level]",
                    "vertical flow resistance from shallow groundwater to deep groundwater (vc) [d]",
                    "initial groudwater level (at t=0), usually taken as target water level, relating to `storcap_ow` [m-SL]",
                ],
                parameters={
                    "seepage_define": 0,
                    "w": 1000,
                    "down_seepage_flux": 0,
                    "head_deep_gw": 20,
                    "vc": 100_000,
                    "gwl_t0": 4,
                },
            ),
            ConfigSection(
                name="open water",
                comments=[
                    "total area of open water [m^2]",
                    "open water fraction of total [-]",
                    "part of open water above Groundwater [-]",
                    "storage capacity of open water (divided by 1000 is target open water level) [mm]",
                    "predefined discharge capacity from open water (internal) to outside water (external) [mm/d over total area]",
                ],
                parameters={
                    "tot_ow_area": 2668,
                    "ow_frac": 0.011,
                    "frac_ow_aboveGW": 0,
                    "storcap_ow": 4000,
                    "q_ow_out_cap": 3,
                },
            ),
            ConfigSection(
                name="sewer system",
                comments=[
                    "part of urban paved area with storm water drainage system (SWDS) [-]",
                    "storage capacity of storm water drainage system (SWDS) [mm]",
                    "storage capacity of mixed sewer system (MSS) [mm]",
                    "rainfall intensity when swds overflow occurs on street [mm/timestep]",
                    "rainfall intensity when combined overflow to open water occurs [mm/timestep]",
                    "",
                    "initial states of sewer system, often taken as zeros",
                    "initial storage in storm water drainage system (SWDS) [mm]",
                    "initial sewer overflow from storm water drainage system (SWDS) [mm]",
                    "initial storage in mixed sewer system (MSS) [mm]",
                    "initial sewer overflow from mixed sewer system (MSS) [mm]",
                ],
                parameters={
                    "swds_frac": 0.25,
                    "storcap_swds": 2,
                    "storcap_mss": 2,
                    "rainfall_swds_so": 8,
                    "rainfall_mss_ow": 8,
                    "stor_swds_t0": 0,
                    "so_swds_t0": 0,
                    "stor_mss_t0": 0,
                    "so_mss_t0": 0,
                },
            ),
        ]


def write_inifile(data: dict, path: str | Path) -> None:
    """Write ini file from dictionary without headers.

    Parameters
    ----------
    data : dict
        Dictionary with key-value pairs to write to ini file.
    path : Path
        Path to output ini file.
    """
    with codecs.open(path, "wb") as f:
        tomli_w.dump(data, f)


def read_inifile(path: str | Path) -> dict:
    """Read ini file into dictionary without headers.

    Parameters
    ----------
    path : Path
        Path to input ini file.

    Returns
    -------
    dict
        Dictionary with key-value pairs from ini file.
    """
    with codecs.open(path, "rb") as f:
        data = tomllib.load(f)
    return data
