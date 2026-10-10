#!/usr/bin/env python3
"""Delete expired partner leads and raw analytics events.

Run this from a trusted operator environment with CYRADUCT_DATABASE_URL set.
The command requires --confirm to prevent accidental deletion.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import storage


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    if args.days < 1 or args.days > 3650:
        raise SystemExit("--days must be between 1 and 3650")
    if not args.confirm:
        raise SystemExit("Refusing to delete data without --confirm")
    print(storage.purge_expired_partner_data(args.days))


if __name__ == "__main__":
    main()
