from plant_engine.crop_advisor import CropAdvice, generate_crop_advice


def test_generate_crop_advice():
    env = {"temp_c": 35, "humidity_pct": 90, "light_ppfd": 100, "co2_ppm": 300}
    nutrients = {"N": 50, "P": 10, "K": 40}
    pests = ["aphids"]

    advice = generate_crop_advice(env, nutrients, pests, "lettuce", "seedling", volume_l=5.0)

    assert isinstance(advice, CropAdvice)
    assert "temperature" in advice.environment
    assert advice.nutrients.analysis.recommended["N"] == 80
    assert "aphids" in advice.pests
