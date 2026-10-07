#!/usr/bin/env python3
"""Merge the Hermes efficiency overlays into config.yaml.

Usage:
  merge_config.py --config ~/.hermes/config.yaml --overlays ./overlays --tier fast|claude [--dry-run]

Prints a unified diff of the YAML before and after. Writes atomically.
Exit codes: 0 changed (or would change), 3 nothing to change, 1 error.
Comments in config.yaml are not preserved by this merge; apply.sh keeps a
timestamped backup of the original next to it.
"""
import argparse
import copy
import difflib
import os
import sys
import tempfile

try:
    import yaml
except ImportError:
    sys.exit(
        "PyYAML is not available to this Python. apply.sh picks the Hermes venv "
        "Python automatically; by hand, run: python3 -m pip install pyyaml"
    )


def deep_merge(base, overlay):
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_merge(base[key], value)
        else:
            base[key] = copy.deepcopy(value)
    return base


def load_yaml(path):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        sys.exit(f"{path} is not a YAML mapping; refusing to merge")
    return data


def dump_yaml(data):
    return yaml.safe_dump(
        data, sort_keys=False, allow_unicode=True, default_flow_style=False, width=100
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--overlays", required=True)
    ap.add_argument("--tier", required=True, choices=["fast", "claude"])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    config_path = os.path.expanduser(args.config)
    overlay_paths = [
        os.path.join(args.overlays, "common.yaml"),
        os.path.join(args.overlays, f"tier-{args.tier}.yaml"),
    ]
    for p in overlay_paths:
        if not os.path.exists(p):
            sys.exit(f"overlay missing: {p}")

    base = load_yaml(config_path)
    merged = copy.deepcopy(base)
    for p in overlay_paths:
        deep_merge(merged, load_yaml(p))

    before = dump_yaml(base)
    after = dump_yaml(merged)
    if before == after:
        print("config.yaml already has every overlay value; nothing to change.")
        return 3

    diff = difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile="config.yaml (before)",
        tofile="config.yaml (after)",
    )
    sys.stdout.writelines(diff)
    print()

    if args.dry_run:
        print("dry run: config.yaml not written.")
        return 0

    directory = os.path.dirname(config_path) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".config.yaml.", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(after)
        if os.path.exists(config_path):
            os.chmod(tmp_path, os.stat(config_path).st_mode & 0o777)
        os.replace(tmp_path, config_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
    print(f"wrote {config_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
