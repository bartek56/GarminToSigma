## Garmin to Sigma

The script downloads cycling and running activities directly from Garmin
Connect and converts them to Sigma SMF files. Activity statistics come from
the original Garmin FIT file, while Garmin Connect's corrected elevation,
temperature, and available weather data are used where available.

### Requirements

Use Python 3 and install the project dependencies from the repository root:

```bash
python -m pip install -r requirements.txt
```

The `requirements.txt` file lists `fitdecode` and `garminconnect` for Garmin
activity conversion, plus `gpxpy` for the GPX merge utility.

### Usage

1. Install the required Python packages.
2. If no saved tokens exist yet, run `GarminActivity.py` once with
   `GARMIN_EMAIL` and `GARMIN_PASSWORD` set in the environment. This saves the
   Garmin Connect tokens in `garmin_tokens`.
3. Run `GarminToSigma.py` from the project directory and enter the earliest
   activity date to search in `YYYY-MM-DD` format. The script checks Garmin
   Connect in pages of 20 activities, continuing until it reaches an activity
   older than the requested date or runs out of results. Cycling and running
   activities from the requested date onward are listed newest first.
   Enter one index to convert that activity; the remaining list is shown again
   so another activity can be selected. Enter `q` to quit. Enter the trip
   profile, feeling, and evaluation for each selected activity. Before creating
   the SMF file, the script asks for confirmation; enter `t` or `tak` to save,
   or press Enter to skip.

Downloaded FIT files are kept in the project directory as
`<activity_id>_<activity-date>_ACTIVITY.fit`. When the same activity is
selected again, the existing FIT file is reused instead of downloading it
again. Activities with a cached FIT file are omitted from the selection list.

For each selected activity, a GPX file is also downloaded to the project
directory. It uses the same base name as the generated SMF file, for example
`Activity name_2026-10-17_123456.gpx`; an existing non-empty GPX file is reused.

Weather from Garmin Connect is converted for Sigma: temperature is saved in
Celsius, the weather description is mapped to a Sigma weather code, and wind
speed (returned by Garmin in mph) is converted to m/s before deriving the
Beaufort value.

When the FIT file contains them, its minimum and maximum recorded temperatures
are also shown in the activity summary. Some FIT files do not include these
values; Garmin Connect's weather response may only provide a single
temperature.

The script uses the saved tokens in `garmin_tokens`; it does not require
Garmin account credentials in source code or environment variables. Treat this
directory as sensitive and do not share or commit it.
