"""Testing UWBM high level methods."""

from hydromt_uwbm import UWBM


def test_model_has_name():
    model = UWBM()
    assert hasattr(model, "_NAME")


def test_model_class():
    model = UWBM()
    model.setup_project(
        name="test_model",
        region={"bbox": [10.0, 59.0, 11.0, 60.0]},
        ts="hours",
        t_start="2020-01-01",
        t_end="2020-01-10",
    )

    non_compliant = model._test_model_api()
    assert len(non_compliant) == 0, non_compliant
