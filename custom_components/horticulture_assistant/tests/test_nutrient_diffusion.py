from dafe.diffusion_model import (
    calculate_effective_diffusion,
    calculate_diffusion_flux,
    estimate_diffusion_mass,
)


def test_calculate_effective_diffusion():
    D = calculate_effective_diffusion(1e-5, 0.4, 0.5, 2.0)
    assert round(D, 8) == 6.4e-06


def test_calculate_diffusion_flux():
    flux = calculate_diffusion_flux(
        D_base=1e-5,
        vwc=0.4,
        porosity=0.5,
        tortuosity=2.0,
        conc_high=100.0,
        conc_low=50.0,
        distance_cm=1.0,
    )
    assert flux < 0
    assert round(flux, 7) == -3.2e-04


def test_estimate_diffusion_mass():
    mass = estimate_diffusion_mass(
        D_base=1e-5,
        vwc=0.4,
        porosity=0.5,
        tortuosity=2.0,
        conc_high=100.0,
        conc_low=50.0,
        distance_cm=1.0,
        area_cm2=10.0,
        duration_s=60.0,
    )
    assert mass > 0
    assert round(mass, 3) == 0.192


def test_invalid_parameters():
    import pytest
    with pytest.raises(ValueError):
        calculate_effective_diffusion(-1, 0.5, 0.5, 2.0)
    with pytest.raises(ValueError):
        calculate_diffusion_flux(1e-5, 0.5, 0.5, 2.0, 1, 0, 0)
    with pytest.raises(ValueError):
        estimate_diffusion_mass(1e-5, 0.5, 0.5, 2.0, 1, 0, 1, -1, 10)
