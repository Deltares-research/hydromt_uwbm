"""Testing UWBM high level methods."""

from pathlib import Path

import pytest

from hydromt_uwbm import UWBM


@pytest.fixture
def model() -> UWBM:
    model = UWBM()
    model.setup_project(
        name="test_model",
        region={"bbox": [10.0, 59.0, 11.0, 60.0]},
        ts="hours",
        t_start="2020-01-01",
        t_end="2020-01-10",
    )
    return model


def test_model_has_name():
    model = UWBM()
    assert hasattr(model, "_NAME")


def test_model_class(model: UWBM):
    non_compliant = model._test_model_api()
    assert len(non_compliant) == 0, non_compliant


def test_write(model: UWBM, tmp_path: Path):
    model.set_root(root=tmp_path)
    model.write()

    assert Path(model.root).exists()
    for sub_dir in model._FOLDERS:
        assert (Path(model.root) / sub_dir).exists()

    assert Path(model.root, "landuse", f"landuse_{model._NAME}.geojson").exists()
