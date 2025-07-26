from dafe import (
    get_species_profile,
    get_media_profile,
    calculate_effective_diffusion,
    generate_pulse_schedule,
    get_current_ec,
    get_current_wc,
    load_config,
)


def test_generate_pulse_schedule():
    cfg = load_config()
    assert cfg["species"] == "Cannabis_sativa"
    assert cfg["media"] == "coco_coir"

    species = get_species_profile("Cannabis_sativa")
    media = get_media_profile("coco_coir")
    wc = species["ideal_wc_plateau"] - 0.01
    D_eff = calculate_effective_diffusion(
        1e-5, wc, media["porosity"], media["tortuosity"]
    )
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
    assert all(
        "time" in p and "volume" in p and "mass_mg" in p for p in schedule
    )

    high_ec_schedule = generate_pulse_schedule(
        wc, 3.0, D_eff, species, media, nutrient_params={"D_base": 1e-5}
    )
    assert all(p["volume"] <= base_volume for p in high_ec_schedule)

    low_ec_schedule = generate_pulse_schedule(
        wc, 1.0, D_eff, species, media, nutrient_params={"D_base": 1e-5}
    )
    assert all(p["volume"] >= base_volume for p in low_ec_schedule)


def test_custom_pulse_window():
    from datetime import datetime, timedelta

    species = get_species_profile("Cannabis_sativa")
    media = get_media_profile("coco_coir")
    wc = species["ideal_wc_plateau"] - 0.01
    D_eff = calculate_effective_diffusion(
        1e-5, wc, media["porosity"], media["tortuosity"]
    )

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


def test_main_json_output():
    import json
    import sys
    import subprocess

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
