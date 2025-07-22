"""CLI wrapper around :mod:`plant_engine.et_model`."""

from __future__ import annotations

import argparse
from plant_engine.et_model import calculate_et0, calculate_eta


def main() -> None:
    parser = argparse.ArgumentParser(description="Calculate ET0 and ETA")
    parser.add_argument("temperature_c", type=float)
    parser.add_argument("rh_percent", type=float)
    parser.add_argument("solar_rad_w_m2", type=float)
    parser.add_argument("--wind", type=float, default=1.0)
    parser.add_argument("--elevation", type=float, default=200)
    parser.add_argument("--kc", type=float, default=1.0)
    args = parser.parse_args()

    et0 = calculate_et0(
        args.temperature_c,
        args.rh_percent,
        args.solar_rad_w_m2,
        wind_m_s=args.wind,
        elevation_m=args.elevation,
    )
    eta = calculate_eta(et0, args.kc)
    print({"et0_mm_day": et0, "eta_mm_day": eta})


if __name__ == "__main__":
    main()
