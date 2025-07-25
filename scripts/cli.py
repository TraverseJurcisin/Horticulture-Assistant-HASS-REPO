"""Unified command line interface for scripts.

Usage::

    python -m scripts <command> [args]

The available commands correspond to modules in the ``scripts`` package
that contain a ``main`` entrypoint.
"""

from __future__ import annotations

import argparse
import pkgutil
import runpy
import sys
from pathlib import Path
from typing import Dict


def _discover_commands() -> Dict[str, str]:
    """Return mapping of command names to module paths."""
    package_dir = Path(__file__).resolve().parent
    commands: Dict[str, str] = {}
    for mod in pkgutil.iter_modules([str(package_dir)]):
        if mod.ispkg or mod.name in {"cli", "__init__"}:
            continue
        commands[mod.name.replace("_", "-")] = f"scripts.{mod.name}"
    return commands


def main(argv: list[str] | None = None) -> None:
    """Run a script subcommand."""
    commands = _discover_commands()
    parser = argparse.ArgumentParser(description="Horticulture Assistant utilities")
    parser.add_argument("command", choices=sorted(commands))
    parser.add_argument("args", nargs=argparse.REMAINDER)
    ns = parser.parse_args(argv)

    module_name = commands[ns.command]
    sys.argv = [module_name] + ns.args
    runpy.run_module(module_name, run_name="__main__", alter_sys=True)


if __name__ == "__main__":  # pragma: no cover - manual execution
    main()
