"""Command-line entry point."""

import argparse
import datetime
import os

from .Garmin.client import GarminClient
from .workflow import ConversionWorkflow, OfflineWorkflow


def main(argv=None) -> None:
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    token_dir = os.path.join(project_dir, "garmin_tokens")
    activities_dir = os.path.join(project_dir, "activities")
    os.makedirs(activities_dir, exist_ok=True)

    parser = argparse.ArgumentParser(description="Convert Garmin activities to Sigma SMF.")
    parser.add_argument(
        "date",
        nargs="?",
        metavar="DATE",
        help="earliest activity date in YYYY-MM-DD format",
    )
    parser.add_argument(
        "--offline",
        nargs="?",
        const=activities_dir,
        metavar="DIRECTORY",
        help="search for FIT files in DIRECTORY (default: activities directory) without Garmin Connect",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="convert selected listed activities without manual ratings",
    )
    parser.add_argument(
        "--date",
        dest="date_option",
        metavar="DATE",
        help="earliest activity date in YYYY-MM-DD format",
    )
    args = parser.parse_args(argv)

    if args.date and args.date_option:
        parser.error("provide the date either positionally or with --date, not both")
    date_value = args.date_option or args.date
    start_date = None
    if date_value:
        try:
            start_date = datetime.date.fromisoformat(date_value)
        except ValueError:
            parser.error("date must use YYYY-MM-DD format")

    workflow = ConversionWorkflow(
        client=None if args.offline is not None else GarminClient(token_dir, activities_dir),
        output_dir=activities_dir,
    )
    if args.offline is not None:
        OfflineWorkflow(workflow).run(
            os.path.abspath(os.path.expanduser(args.offline)), args.auto
        )
    else:
        workflow.run_online(args.auto, start_date=start_date)
