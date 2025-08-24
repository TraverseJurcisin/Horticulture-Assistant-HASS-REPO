from custom_components.horticulture_assistant.utils.nutrient_use_efficiency import efficiency_report


def test_efficiency_report_basic():
    eff = {"N": 5.0, "P": 8.0, "K": 6.5}
    report = efficiency_report(eff, "tomato")
    assert report["N"]["difference"] == 0
    assert report["N"]["pct_of_target"] == 100.0
    assert report["P"]["pct_of_target"] == 100.0
    assert report["K"]["target"] == 6.5
