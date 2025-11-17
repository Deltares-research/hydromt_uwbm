from datetime import datetime
from pathlib import Path

import pytest

from hydromt_uwbm import DATA_DIR
from hydromt_uwbm.config import (
    DATETIME_FORMAT,
    ConfigSection,
    UWMBConfigWriter,
    read_inifile,
)


@pytest.fixture
def template_file() -> Path:
    return DATA_DIR / "UWBM" / "neighbourhood_params.ini"


@pytest.fixture
def template_contents(template_file: Path) -> list[str]:
    return template_file.read_text().splitlines()


@pytest.fixture
def default_config() -> UWMBConfigWriter:
    return UWMBConfigWriter.default()


def test_get_parameter_finds_correct_section(default_config: UWMBConfigWriter):
    value, section = default_config._get_parameter("timestep")
    assert value == 3600
    assert section == "overall"


def test_get_parameter_returns_none_on_missing(default_config: UWMBConfigWriter):
    value, section = default_config._get_parameter("nonexistent_key")
    assert value is None
    assert section is None


def test_set_parameter_updates_correct_section(default_config: UWMBConfigWriter):
    default_config._set_parameter("timestep", 7200, "overall")

    updated, _ = default_config._get_parameter("timestep")
    assert updated == 7200


def test_from_dict_updates_all_parameters_in_correct_sections(
    default_config: UWMBConfigWriter,
):
    starttime = datetime(2025, 1, 1)
    data = {
        "timestep": 1800,
        "tot_pr_area": 99999,
        "storcap_mss": 123,
        "starttime": starttime,
    }

    default_config.from_dict(data)

    assert default_config._get_parameter("timestep") == (1800, "overall")
    assert default_config._get_parameter("tot_pr_area") == (99999, "paved roof")
    assert default_config._get_parameter("storcap_mss") == (123, "sewer system")
    assert default_config._get_parameter("starttime") == (
        starttime,
        None,
    )  # not in the template, so add to global


def test_from_dict_adds_unknown_parameter_to_global(default_config: UWMBConfigWriter):
    default_config.from_dict({"unknown_parameter": 123})
    value, section = default_config._get_parameter("unknown_parameter")
    assert value == 123
    assert section is None  # global section


def test_serialize_contains_sections_and_parameters(default_config: UWMBConfigWriter):
    serialized = default_config.serialize()

    assert "timestep = 3600" in serialized
    assert "# overall #" in serialized
    assert "tot_pr_area = 61297" in serialized


def test_write_outputs_file(tmp_path: Path, default_config: UWMBConfigWriter):
    file = tmp_path / "config.out"

    default_config.write(file)

    assert file.exists()
    content = file.read_text()
    assert "timestep = 3600" in content


def test_write_output_equal_template_params(
    tmp_path: Path, template_file: Path, default_config: UWMBConfigWriter
):
    file = tmp_path / "config.ini"
    default_config.write(file)

    template_params = read_inifile(template_file)
    output_params = read_inifile(file)

    assert template_params == output_params


def test_write_output_equal_comments(
    tmp_path: Path, template_contents: list[str], default_config: UWMBConfigWriter
):
    def _extract_and_normalize_comments(contents: list[str]) -> list[str]:
        comments = []
        for line in contents:
            line = line.strip()
            if not line.startswith("#"):
                continue
            # Remove leading '#' characters, normalize spaces, and skip empty comments
            if comment := line.lstrip("#").rstrip("#").strip():
                comments.append(comment)
        return comments

    file = tmp_path / "config.ini"
    default_config.write(file)

    output_lines = file.read_text().splitlines()
    template_comments = _extract_and_normalize_comments(template_contents)
    output_comments = _extract_and_normalize_comments(output_lines)
    mismatched = []
    for comment in template_comments:
        if comment not in output_comments:
            mismatched.append(comment)

    assert not mismatched, f"Mismatched comments in output: {mismatched}"


def test_write_and_read_integration(tmp_path: Path):
    dt = datetime(2023, 11, 17)

    sections = [
        ConfigSection(
            name="test_basic",
            comments=["Basic types section"],
            parameters={
                "str_param": "hello",
                "int_param": 42,
                "float_param": 3.14,
                "bool_true": True,
                "bool_false": False,
                "none_param": None,
            },
        ),
        ConfigSection(
            name="test_list",
            comments=["List section"],
            parameters={
                "list_int": [1, 2, 3],
                "list_str": ["a", "b", "c"],
                "list_mixed": [1, "x", True],
            },
        ),
        ConfigSection(
            name="test_dict",
            comments=["Nested dict section"],
            parameters={
                "nested_table": {
                    "a": 1,
                    "b": "ok",
                    "more_nested": {"x": 10, "y": [1, 2, 3]},
                }
            },
        ),
        ConfigSection(
            name="test_datetime",
            comments=["Datetime section"],
            parameters={"created": dt},
        ),
    ]

    cfg = UWMBConfigWriter(sections)
    file_path = tmp_path / "config.toml"

    cfg.write(file_path)
    data = read_inifile(file_path)

    # Basic types
    assert data["str_param"] == "hello"
    assert data["int_param"] == 42
    assert data["float_param"] == 3.14
    assert data["bool_true"] is True
    assert data["bool_false"] is False
    assert data.get("none_param") is None

    # Lists
    assert data["list_int"] == [1, 2, 3]
    assert data["list_str"] == ["a", "b", "c"]
    assert data["list_mixed"] == [1, "x", True]

    # Nested dict
    nested = data["nested_table"]
    assert nested["a"] == 1
    assert nested["b"] == "ok"

    # Datetime
    assert data["created"] == dt


# ----------------------------------#
# ConfigSection serialization tests #
# ----------------------------------#
def test_basic_types_serialization():
    params = {
        "str_param": "hello",
        "int_param": 42,
        "float_param": 3.14,
        "bool_true": True,
        "bool_false": False,
        "none_param": None,
    }
    section = ConfigSection(name="basic", parameters=params)
    output = section.serialize()

    assert 'str_param = "hello"' in output
    assert "int_param = 42" in output
    assert "float_param = 3.14" in output
    assert "bool_true = true" in output
    assert "bool_false = false" in output
    assert "none_param" not in output


def test_list_serialization():
    params = {
        "list_int": [1, 2, 3],
        "list_str": ["a", "b", "c"],
        "list_mixed": [1, "x", True],
    }
    section = ConfigSection(name="lists", parameters=params)
    output = section.serialize()

    assert "list_int = [1, 2, 3]" in output
    assert 'list_str = ["a", "b", "c"]' in output
    assert 'list_mixed = [1, "x", true]' in output


def test_inline_dict_serialization():
    section = ConfigSection(
        parameters={
            "flat_dict": {"a": 1, "b": "ok"},
            "nested_list_dict": [{"x": 1, "y": 2}, {"x": 3, "y": 4}],
        }
    )
    serialized = section.serialize()
    assert 'flat_dict = { a = 1, b = "ok" }' in serialized
    assert "nested_list_dict = [{ x = 1, y = 2 }, { x = 3, y = 4 }]" in serialized


def test_datetime_serialization():
    dt = datetime(2020, 2, 1, 12, 30)
    section = ConfigSection(name="datetime", parameters={"starttime": dt})
    output = [l.strip() for l in section.serialize().splitlines()]
    assert f"starttime = {dt.strftime(DATETIME_FORMAT)}" in output


def test_combined_serialization_with_comments():
    section = ConfigSection(
        name="test_section",
        comments=["Comment line 1", "Comment line 2"],
        parameters={
            "str_val": "hello",
            "num_val": 99,
            "nested_dict": {"a": 1, "b": "ok"},
            "list_val": [1, 2, 3],
        },
    )
    serialized = section.serialize()
    # Check section header
    assert "# test_section #" in serialized
    # Check comments
    assert "# Comment line 1" in serialized
    assert "# Comment line 2" in serialized
    # Check parameters
    assert 'str_val = "hello"' in serialized
    assert "num_val = 99" in serialized
    assert 'nested_dict = { a = 1, b = "ok" }' in serialized
    assert "list_val = [1, 2, 3]" in serialized
