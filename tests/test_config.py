from pathlib import Path

import pytest

from hydromt_uwbm.config import UWMBConfig, UWMBConfigWriter


@pytest.fixture
def minimal_config() -> UWMBConfig:
    return UWMBConfig(
        title="Test Config",
        soiltype=11,
        croptype=1,
        tot_area=1000,
        area_type=0,
        tot_pr_area=100,
        pr_frac=0.1,
        frac_pr_aboveGW=0.5,
        discfrac_pr=0.1,
        intstorcap_pr=3,
        intstor_pr_t0=0,
        tot_cp_area=50,
        cp_frac=0.05,
        discfrac_cp=0.02,
        intstorcap_cp=2,
        intstor_cp_t0=0,
        tot_op_area=30,
        op_frac=0.03,
        discfrac_op=0.01,
        intstorcap_op=4,
        infilcap_op=20,
        intstor_op_t0=0,
        tot_up_area=500,
        up_frac=0.5,
        intstorcap_up=5,
        infilcap_up=40,
        fin_intstor_up_t0=0,
        w=100,
        seepage_define=0,
        down_seepage_flux=0,
        head_deep_gw=10,
        vc=1000,
        gwl_t0=2,
        tot_ow_area=20,
        ow_frac=0.02,
        frac_ow_aboveGW=0,
        storcap_ow=100,
        q_ow_out_cap=5,
        swds_frac=0.2,
        storcap_swds=2,
        storcap_mss=2,
        rainfall_swds_so=5,
        rainfall_mss_ow=5,
        stor_swds_t0=0,
        so_swds_t0=0,
        stor_mss_t0=0,
        so_mss_t0=0,
    )


def test_write_read_cycle(tmp_path: Path, minimal_config: UWMBConfig):
    path = tmp_path / "config.ini"
    writer = UWMBConfigWriter(minimal_config)
    writer.write(path)
    cfg_read = UWMBConfigWriter.from_file(path).config

    assert cfg_read == minimal_config


def test_missing_field_serialization_error(tmp_path: Path, minimal_config: UWMBConfig):
    minimal_config._SECTIONS.pop(0)  # remove a section to cause serialization error
    writer = UWMBConfigWriter(minimal_config)
    with pytest.raises(ValueError, match="Some fields were not serialized"):
        writer.write(tmp_path / "dummy_path.ini")


# --------------------------------------------------------------------------
# Test validation errors
# --------------------------------------------------------------------------
def test_missing_required_fields():
    with pytest.raises(ValueError, match="Field required"):
        UWMBConfig(
            title="Invalid Config",
            soiltype=11,
            croptype=1,
            tot_area=1000,
            area_type=0,
            tot_pr_area=100,
            pr_frac=0.1,
            # Missing frac_pr_aboveGW
            discfrac_pr=0.1,
            intstorcap_pr=3,
            intstor_pr_t0=0,
            tot_cp_area=50,
            cp_frac=0.05,
            discfrac_cp=0.02,
            intstorcap_cp=2,
            intstor_cp_t0=0,
            tot_op_area=30,
            op_frac=0.03,
            discfrac_op=0.01,
            intstorcap_op=4,
            infilcap_op=20,
            intstor_op_t0=0,
            tot_up_area=500,
            up_frac=0.5,
            intstorcap_up=5,
            infilcap_up=40,
            fin_intstor_up_t0=0,
            w=100,
            seepage_define=0,
            down_seepage_flux=0,
            head_deep_gw=10,
            vc=1000,
            gwl_t0=2,
            tot_ow_area=20,
            ow_frac=0.02,
            frac_ow_aboveGW=0,
            storcap_ow=100,
            q_ow_out_cap=5,
            swds_frac=0.2,
            storcap_swds=2,
            storcap_mss=2,
            rainfall_swds_so=5,
            rainfall_mss_ow=5,
            stor_swds_t0=0,
            so_swds_t0=0,
            stor_mss_t0=0,
            so_mss_t0=0,
        )


def test_invalid_fraction():
    with pytest.raises(ValueError, match="Input should be less than or equal to 1"):
        UWMBConfig(
            title="Bad Fraction",
            soiltype=11,
            croptype=1,
            tot_area=1000,
            area_type=0,
            tot_pr_area=100,
            pr_frac=1.5,  # invalid >1
            frac_pr_aboveGW=0.5,
            discfrac_pr=0.1,
            intstorcap_pr=3,
            intstor_pr_t0=0,
            tot_cp_area=50,
            cp_frac=0.05,
            discfrac_cp=0.02,
            intstorcap_cp=2,
            intstor_cp_t0=0,
            tot_op_area=30,
            op_frac=0.03,
            discfrac_op=0.01,
            intstorcap_op=4,
            infilcap_op=20,
            intstor_op_t0=0,
            tot_up_area=500,
            up_frac=0.5,
            intstorcap_up=5,
            infilcap_up=40,
            fin_intstor_up_t0=0,
            w=100,
            seepage_define=0,
            down_seepage_flux=0,
            head_deep_gw=10,
            vc=1000,
            gwl_t0=2,
            tot_ow_area=20,
            ow_frac=0.02,
            frac_ow_aboveGW=0,
            storcap_ow=100,
            q_ow_out_cap=5,
            swds_frac=0.2,
            storcap_swds=2,
            storcap_mss=2,
            rainfall_swds_so=5,
            rainfall_mss_ow=5,
            stor_swds_t0=0,
            so_swds_t0=0,
            stor_mss_t0=0,
            so_mss_t0=0,
        )


def test_create_validation_messages():
    # deliberately leave out required fields and add invalid/unknown values
    test_data = {
        "title": "Test Config",
        "soiltype": -1,  # invalid (should be >=0)
        "croptype": 1,
        # missing tot_area
        "area_type": 0,
        "tot_pr_area": 5000,
        "pr_frac": 1.5,  # invalid (should be <=1)
        "frac_pr_aboveGW": 0.5,
        "discfrac_pr": 0.2,
        "intstorcap_pr": 10,
        "intstor_pr_t0": 0,
        "unknown_param": 123,  # unknown
    }

    with pytest.raises(ValueError) as excinfo:  # noqa: PT011
        UWMBConfig.create(test_data)

    msg = str(excinfo.value)
    print(msg)  # for debugging

    # Check invalid/missing fields are reported
    assert "Invalid/missing parameters:" in msg
    assert "tot_area" in msg
    assert "soiltype" in msg
    assert "pr_frac" in msg

    # Check unknown fields are reported
    assert "Unknown parameters:" in msg
    assert "unknown_param" in msg
