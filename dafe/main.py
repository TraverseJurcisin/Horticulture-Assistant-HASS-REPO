"""Example command-line entry point for DAFE."""

from __future__ import annotations

from .species_profiles import get_species_profile
from .media_models import get_media_profile
from .wc_monitor import get_current_wc
from .ec_tracker import get_current_ec
from .diffusion_model import calculate_effective_diffusion
from .pulse_scheduler import generate_pulse_schedule
from .utils import load_config

import argparse
import json
from typing import Sequence


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Return parsed command line arguments."""
    parser = argparse.ArgumentParser(
        description="Diffusion-Aware Fertigation Engine"
    )
    parser.add_argument(
        "--config", help="Path to configuration file", default=None
    )
    parser.add_argument("--species", help="Override species from config")
    parser.add_argument("--media", help="Override media from config")
    parser.add_argument(
        "--json", action="store_true", help="Output schedule as JSON"
    )
    parser.add_argument(
        "--D-base",
        dest="D_base",
        type=float,
        help="Override diffusion coefficient in cm^2/s",
    )
    parser.add_argument(
        "--start-hour",
        type=int,
        default=10,
        help="Hour offset from now for first pulse",
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=6,
        help="Number of hourly pulses to schedule",
    )
    parser.add_argument(
        "--conc-high",
        type=float,
        help="Nutrient concentration at the source in mg/cm^3",
    )
    parser.add_argument(
        "--conc-low",
        type=float,
        help="Nutrient concentration at the sink in mg/cm^3",
    )
    parser.add_argument(
        "--distance-cm",
        type=float,
        help="Distance between concentrations in cm",
    )
    parser.add_argument(
        "--area-cm2",
        type=float,
        help="Exchange area in cm^2",
    )
    parser.add_argument(
        "--duration-s",
        type=float,
        help="Exchange duration in seconds",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    config = load_config(args.config) if args.config else load_config()
    species = args.species or config.get("species", "Cannabis_sativa")
    media = args.media or config.get("media", "coco_coir")
    D_base = (
        float(args.D_base)
        if args.D_base is not None
        else float(config.get("D_base", 1e-5))
    )

    species_profile = get_species_profile(species)
    media_profile = get_media_profile(media)

    wc = get_current_wc()
    ec = get_current_ec()

    D_eff = calculate_effective_diffusion(
        D_base=D_base,
        vwc=wc,
        porosity=media_profile["porosity"],
        tortuosity=media_profile["tortuosity"],
    )

    nutrient_params = {"D_base": D_base}
    if args.conc_high is not None:
        nutrient_params["conc_high"] = args.conc_high
    if args.conc_low is not None:
        nutrient_params["conc_low"] = args.conc_low
    if args.distance_cm is not None:
        nutrient_params["distance_cm"] = args.distance_cm
    if args.area_cm2 is not None:
        nutrient_params["area_cm2"] = args.area_cm2
    if args.duration_s is not None:
        nutrient_params["duration_s"] = args.duration_s
    pulse_plan = generate_pulse_schedule(
        wc=wc,
        ec=ec,
        D_eff=D_eff,
        species_profile=species_profile,
        media_profile=media_profile,
        nutrient_params=nutrient_params,
        start_hour=args.start_hour,
        hours=args.hours,
    )

    if args.json:
        print(json.dumps(pulse_plan, indent=2))
    else:
        if not pulse_plan:
            print("No irrigation pulses scheduled.")
        else:
            for pulse in pulse_plan:
                print(
                    f"Pulse at {pulse['time']} - Volume: {pulse['volume']} mL - Estimated mass: {pulse['mass_mg']:.3f} mg"
                )


if __name__ == "__main__":
    main()
