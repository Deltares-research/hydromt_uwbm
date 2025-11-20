from datetime import datetime
from pathlib import Path

import pytest

from hydromt_uwbm import DATA_DIR
from hydromt_uwbm.config import (
    DATETIME_FORMAT,
    ConfigSection,
    ConfigWriter,
    UWMBConfigWriter,
    read_inifile,
)


# ----------------------------------#
# ConfigSection tests               #
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
        name="dicts",
        parameters={
            "flat_dict": {"a": 1, "b": "ok"},
            "nested_list_dict": [{"x": 1, "y": 2}, {"x": 3, "y": 4}],
        },
    )
    serialized = section.serialize()
    assert 'flat_dict = { a = 1, b = "ok" }' in serialized
    assert "nested_list_dict = [{ x = 1, y = 2 }, { x = 3, y = 4 }]" in serialized


def test_datetime_serialization():
    dt = datetime(2025, 1, 1)
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


# ----------------------------------#
# ConfigWriter tests                #
# ----------------------------------#
@pytest.fixture
def dummy_config() -> ConfigWriter:
    writer = ConfigWriter()
    writer.sections = [
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
            parameters={"created": datetime(2025, 1, 1)},
        ),
    ]
    return writer


@pytest.mark.parametrize(
    ("parameter", "expected_value", "expected_section"),
    [
        ("str_param", "hello", "test_basic"),
        ("int_param", 42, "test_basic"),
        ("float_param", 3.14, "test_basic"),
        ("bool_true", True, "test_basic"),
        ("bool_false", False, "test_basic"),
        ("none_param", None, "test_basic"),
        ("list_int", [1, 2, 3], "test_list"),
        ("list_str", ["a", "b", "c"], "test_list"),
        ("list_mixed", [1, "x", True], "test_list"),
        (
            "nested_table",
            {
                "a": 1,
                "b": "ok",
                "more_nested": {"x": 10, "y": [1, 2, 3]},
            },
            "test_dict",
        ),
        ("created", datetime(2025, 1, 1), "test_datetime"),
    ],
)
def test_get_parameter_finds_correct_section(
    dummy_config: ConfigWriter, parameter, expected_value, expected_section
):
    value, section = dummy_config.get_parameter(parameter)
    assert value == expected_value
    assert section == expected_section


def test_get_parameter_returns_none_on_missing(dummy_config: ConfigWriter):
    value, section = dummy_config.get_parameter("nonexistent_key")
    assert value is None
    assert section is None


def test_set_parameter_updates_correct_section(dummy_config: ConfigWriter):
    dummy_config.set_parameter("str_param", "new_value", section_name="test_basic")

    updated, section_name = dummy_config.get_parameter("str_param")
    assert updated == "new_value"
    assert section_name == "test_basic"


def test_serialize_contains_sections_and_parameters(dummy_config: ConfigWriter):
    serialized = dummy_config.serialize()

    assert "# Basic types section" in serialized
    assert "# test_basic #" in serialized
    assert 'str_param = "hello"' in serialized
    assert "# List section" in serialized
    assert "list_int = [1, 2, 3]" in serialized
    assert "# Nested dict section" in serialized
    assert (
        'nested_table = { a = 1, b = "ok", more_nested = { x = 10, y = [1, 2, 3] } }'
        in serialized
    )
    assert "# Datetime section" in serialized
    assert "created = 2025-01-01 00:00:00" in serialized


def test_write_outputs_file(tmp_path: Path, dummy_config: ConfigWriter):
    file = tmp_path / "config.out"
    dummy_config.write(file)
    assert file.exists()


def test_write_and_read_integration(dummy_config: ConfigWriter, tmp_path: Path):
    file_path = tmp_path / "config.toml"

    dummy_config.write(file_path)
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
    assert data["created"] == datetime(2025, 1, 1)


# ----------------------------------#
# UWMBConfigWriter tests            #
# ----------------------------------#
@pytest.fixture
def template_file() -> Path:
    return DATA_DIR / "UWBM" / "neighbourhood_params.ini"


@pytest.fixture
def template_contents(template_file: Path) -> list[str]:
    return template_file.read_text().splitlines()


def test_from_dict_updates_all_parameters_in_correct_sections():
    starttime = datetime(2025, 1, 1)
    data = {
        "timestepsecs": 86400,
        "tot_pr_area": 99999,
        "storcap_mss": 123,
        "starttime": starttime,
    }
    writer = UWMBConfigWriter()
    writer.from_dict(data)

    assert writer.get_parameter("timestepsecs") == (86400, "runtime")
    assert writer.get_parameter("tot_pr_area") == (99999, "paved roof")
    assert writer.get_parameter("storcap_mss") == (123, "sewer system")

    # not in the template, so it was added to runtime
    assert writer.get_parameter("starttime") == (starttime, "runtime")


def test_from_dict_adds_unknown_parameter_to_runtime():
    writer = UWMBConfigWriter()
    writer.from_dict({"unknown_parameter": 123})
    value, section = writer.get_parameter("unknown_parameter")
    assert value == 123
    assert section == "runtime"


def test_write_output_equal_template_params(tmp_path: Path, template_file: Path):
    file = tmp_path / "config.ini"
    UWMBConfigWriter().write(file)

    template_params = read_inifile(template_file)
    output_params = read_inifile(file)

    assert template_params == output_params


def test_write_output_equal_comments(tmp_path: Path, template_contents: list[str]):
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
    UWMBConfigWriter().write(file)

    output_lines = file.read_text().splitlines()
    template_comments = _extract_and_normalize_comments(template_contents)
    output_comments = _extract_and_normalize_comments(output_lines)
    mismatched = []
    for comment in template_comments:
        if comment not in output_comments:
            mismatched.append(comment)

    assert not mismatched, f"Mismatched comments in output: {mismatched}"
