from plant_engine import ec_conversions


def test_list_scales_contains_defaults():
    scales = ec_conversions.list_scales()
    assert "500" in scales
    assert "700" in scales


def test_ec_to_ppm_and_back():
    ppm = ec_conversions.ec_to_ppm(1.2, "500")
    assert ppm == 600.0
    ec = ec_conversions.ppm_to_ec(ppm, "500")
    assert ec == 1.2


def test_custom_factor():
    assert ec_conversions.ec_to_ppm(2.0, 640) == 1280.0
    assert ec_conversions.ppm_to_ec(1280, 640) == 2.0
