import pytest

pytest.importorskip("dafe.main")

from dafe import (  # noqa: E402
    calculate_effective_diffusion,
    generate_pulse_schedule,
    get_current_ec,
    get_media_profile,
    get_species_profile,
    load_config,
)


def test_generate_pulse_schedule():
    cfg = load_config()
    assert cfg["species"] == "Cannabis_sativa"
    assert cfg["media"] == "coco_coir"

    species = get_species_profile("Cannabis_sativa")
    media = get_media_profile("coco_coir")
    wc = species.ideal_wc_plateau - 0.01
    D_eff = calculate_effective_diffusion(1e-5, wc, media.porosity, media.tortuosity)
    base_volume = int(30 + D_eff * 100000)

    schedule = generate_pulse_schedule(
        wc,
        get_current_ec(),
        D_eff,
        species,
        media,
        nutrient_params={"D_base": 1e-5},
        start_hour=10,
        hours=6,
    )
    assert schedule
    assert all("time" in p and "volume" in p and "mass_mg" in p for p in schedule)

    high_ec_schedule = generate_pulse_schedule(wc, 3.0, D_eff, species, media, nutrient_params={"D_base": 1e-5})
    assert all(p["volume"] <= base_volume for p in high_ec_schedule)

    low_ec_schedule = generate_pulse_schedule(wc, 1.0, D_eff, species, media, nutrient_params={"D_base": 1e-5})
    assert all(p["volume"] >= base_volume for p in low_ec_schedule)


def test_custom_pulse_window():
    from datetime import datetime, timedelta

    species = get_species_profile("Cannabis_sativa")
    media = get_media_profile("coco_coir")
    wc = species.ideal_wc_plateau - 0.01
    D_eff = calculate_effective_diffusion(1e-5, wc, media.porosity, media.tortuosity)

    schedule = generate_pulse_schedule(
        wc,
        get_current_ec(),
        D_eff,
        species,
        media,
        nutrient_params={"D_base": 1e-5},
        start_hour=8,
        hours=3,
    )
    assert len(schedule) == 3
    base = datetime.now().replace(minute=0, second=0, microsecond=0)
    expected = [(base + timedelta(hours=8 + i)).strftime("%H:%M") for i in range(3)]
    assert [p["time"] for p in schedule] == expected


@pytest.mark.skip(reason="dafe CLI not available")
def test_main_json_output():
    import json
    import subprocess
    import sys

    result1 = subprocess.run(
        [sys.executable, "-m", "dafe.main", "--json", "--hours=2"],
        capture_output=True,
        text=True,
        check=True,
    )
    result2 = subprocess.run(
        [
            sys.executable,
            "-m",
            "dafe.main",
            "--json",
            "--D-base=2e-5",
            "--conc-high=200",
            "--hours=2",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    data1 = json.loads(result1.stdout)
    data2 = json.loads(result2.stdout)
    assert isinstance(data1, list) and isinstance(data2, list)
    assert data1 and data2
    assert len(data1) == 2 and len(data2) == 2
    m1 = data1[0]["mass_mg"]
    m2 = data2[0]["mass_mg"]
    assert m2 > m1 * 5.9 and m2 < m1 * 6.1


def test_recommend_fertigation_schedule():
    from dafe import recommend_fertigation_schedule

    schedule = recommend_fertigation_schedule("citrus", "vegetative", 10)
    assert schedule["N"] == 0.8
    assert schedule["P"] == 0.3
    assert schedule["K"] == 0.6


def test_profile_data_files(tmp_path, monkeypatch):
    """Species and media profiles load from dataset files."""

    data_dir = tmp_path / "media"
    data_dir.mkdir()
    species_file = data_dir / "dafe_species_profiles.json"
    species_file.write_text(
        '{"testplant": {"root_depth": "shallow", "dryback_tolerance": "low",'
        ' "oxygen_min": 7, "ideal_wc_plateau": 0.5, "generative_threshold": 0.1,'
        ' "ec_low": 1.0, "ec_high": 2.0}}'
    )
    media_file = data_dir / "dafe_media_profiles.json"
    media_file.write_text('{"rockwool": {"porosity": 0.9, "fc": 0.7, "pwp": 0.1, "tortuosity": 1.5}}')

    monkeypatch.setenv("HORTICULTURE_DATA_DIR", str(tmp_path))

    from plant_engine.utils import clear_dataset_cache

    clear_dataset_cache()
    get_species_profile.cache_clear()
    get_media_profile.cache_clear()

    sp = get_species_profile("testplant")
    mp = get_media_profile("rockwool")

    assert sp is not None
    assert mp is not None
    assert sp.ec_high == 2.0 and mp.porosity == 0.9
