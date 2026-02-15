"""Validate a DPM config file and create any missing database files.

Reads the same JSON config format used by DomainCatalog.from_json_config,
resolves each database path, creates parent directories and SQLite files
as needed, and validates that ModelDB can open each one.
"""
import argparse
import json
import sys
from pathlib import Path

from dpm.store.wrappers import ModelDB
from dpm.store.domains import DomainMode


def prep_config(config_path: Path) -> None:
    config_path = config_path.resolve()
    print(f"Config: {config_path}")

    with open(config_path) as f:
        config = json.load(f)

    if "databases" not in config or not isinstance(config["databases"], dict):
        print("ERROR: config must contain a 'databases' dict")
        sys.exit(1)

    for name, data in config["databases"].items():
        if "path" not in data:
            print(f"  [{name}] ERROR: missing 'path' key")
            sys.exit(1)
        if "description" not in data:
            print(f"  [{name}] ERROR: missing 'description' key")
            sys.exit(1)

        path_str = data["path"]
        if path_str.startswith("/"):
            db_path = Path(path_str)
        elif path_str.startswith("./"):
            db_path = config_path.parent / path_str
        else:
            print(f"  [{name}] ERROR: path must start with '/' or './' — got {path_str!r}")
            sys.exit(1)

        # Validate domain_mode if present
        if "domain_mode" in data:
            try:
                DomainMode(data["domain_mode"])
            except ValueError:
                print(f"  [{name}] ERROR: invalid domain_mode {data['domain_mode']!r}")
                sys.exit(1)

        db_path = db_path.resolve()
        existed = db_path.exists()

        # Create parent directory if needed
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize ModelDB (creates the SQLite file if missing)
        ModelDB(store_dir=db_path.parent, name_override=db_path.name, autocreate=True)

        if existed:
            print(f"  [{name}] OK (existing) — {db_path}")
        else:
            print(f"  [{name}] CREATED — {db_path}")

    print(f"All {len(config['databases'])} database(s) ready.")


def main():
    parser = argparse.ArgumentParser(
        description="Validate a DPM config and create any missing databases.",
    )
    default_config = Path(__file__).parent.parent / "example_dbs" / "config.json"
    parser.add_argument(
        "-c", "--config",
        type=Path,
        default=default_config,
        help=f"Path to config file (default: {default_config})",
    )
    args = parser.parse_args()
    prep_config(args.config)


if __name__ == "__main__":
    main()
