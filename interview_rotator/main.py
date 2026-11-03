"""Command-line entry point: choose the terminal (cli) or browser (web) interface."""

from __future__ import annotations

import argparse
import os
import sys

from .cli import Cli
from .core.cards import CardService
from .core.storage import JsonStorage


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m interview_rotator",
        description="Interview Prep Question Rotator - adaptive interview practice.",
    )
    parser.add_argument(
        "mode", nargs="?", choices=["cli", "web"], default="cli",
        help="'cli' = terminal menu (default), 'web' = browser interface",
    )
    parser.add_argument("--data", help="path to the JSON data file (default: data/cards.json)")
    parser.add_argument("--host", default="127.0.0.1", help="web: address to listen on (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="web: port (default: 8000)")
    args = parser.parse_args(argv)

    storage = JsonStorage(args.data)
    service = CardService(storage)  # loads the cards (may set storage.warning)

    if args.mode == "web":
        from .web.server import run_server

        return run_server(service, args.host, args.port, storage.warning)

    color = sys.stdout.isatty() and "NO_COLOR" not in os.environ
    return Cli(service, color=color, storage_warning=storage.warning).run()

