import argparse
import os
import subprocess
import sys


def main():
    base_dir = os.path.dirname(__file__)
    if base_dir:
        os.chdir(base_dir)
    parser = argparse.ArgumentParser(description="Run linters and formatters.")
    parser.add_argument("--check", action="store_true", help="Only run formatters in check mode")
    args = parser.parse_args()

    failed = False
    isort_args = ""
    black_args = ""

    if args.check:
        isort_args = "--check-only"
        black_args = "--check"

    failed |= subprocess.call(f"isort . {isort_args}", shell=True) > 0
    failed |= subprocess.call(f"black . --config black.toml {black_args}", shell=True) > 0
    failed |= subprocess.call("flake8 . --exclude .idea", shell=True) > 0

    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
