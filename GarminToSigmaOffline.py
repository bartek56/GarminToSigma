"""Backward-compatible command name for offline conversion."""

import sys

from garmin_to_sigma.cli import main


if __name__ == "__main__":
    main(["--offline", *sys.argv[1:]])
