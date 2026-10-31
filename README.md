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
   activity date to search in `YYYY-MM-DD` format. The date can also be passed
   directly with `--date 2026-10-01` or as a positional argument
   `GarminToSigma.py 2026-10-01`. The script checks Garmin
   Connect in pages of 20 activities, continuing until it reaches an activity
   older than the requested date or runs out of results. Cycling and running
   activities from the requested date onward are listed oldest first.
   Enter one index to convert that activity; the remaining list is shown again
   so another activity can be selected. Enter `q` to quit. Without `--auto`,
   the script asks for `Feelings` and `Evaluation` for the selected activity.
   The SMF file is then saved automatically.

   To process selected activities with automatically calculated values, run
   `python GarminToSigma.py --auto`. After the list is displayed, press Enter
   or type `all` for all activities, or enter selections such as `1,3,5` or
   `1-5`. The automatic feeling value is `3`.

Downloaded FIT files are kept in the `activities` directory as
`<activity-date>_<activity-name>_<activity_id>_ACTIVITY.fit`. When the same activity is
selected again, the existing FIT file is reused instead of downloading it
again. Activities with a cached FIT file are omitted from the selection list.

For each selected activity, a GPX file is also downloaded to the `activities`
directory. It uses the same base name as the generated SMF file, for example
`2026-10-17_Activity name_123456.gpx`; an existing non-empty GPX file is reused.

Temperature recorded in the FIT file is preferred. If FIT has no temperature,
the script falls back to Garmin Connect's weather response, where temperature
is converted to Celsius. The weather endpoint also supplies conditions and
wind not present in the FIT; conditions are mapped to a Sigma weather code and
wind speed (returned by Garmin in mph) is converted to m/s before deriving the
Beaufort value. If neither FIT nor Garmin Connect provides a temperature, the
script asks for it in °C before saving the SMF file, including in `--auto` mode.

When the FIT file contains them, its minimum and maximum recorded temperatures
are also shown in the activity summary. Some FIT files do not include these
values; Garmin Connect's weather response may only provide a single
temperature.

The script uses the saved tokens in `garmin_tokens`; it does not require
Garmin account credentials in source code or environment variables. Treat this
directory as sensitive and do not share or commit it.

### Offline conversion

Run `python GarminToSigma.py --offline [DIRECTORY]` to convert a local FIT
without connecting to Garmin Connect. If `DIRECTORY` is omitted, the
`activities` directory is searched recursively. The script asks you to confirm a FIT file
before processing it, then uses its recorded sport, date, and available
statistics and continues with the usual trip profile, feeling, evaluation,
and summary. Without `--auto`, the script asks for `Feelings` and `Evaluation`.
With `--auto`, press Enter or type `all` to convert all listed FIT files, or
enter selections such as `1,3,5` or `1-5`. If the FIT does not identify cycling or
running, the script asks you to choose the activity type. Weather and GPX
downloads are unavailable offline; temperature is used when present in the FIT
and is requested from the user if the FIT has no temperature.

### Tests

Run the unit tests with:

```bash
python -m unittest discover -s tests -v
```

The application is split into source, format, and shared layers:

```text
garmin_to_sigma/
├── Garmin/       # Garmin Connect client and FIT parser
├── Sigma/        # Sigma SMF writer
├── Utils/        # source- and format-independent helpers
├── models.py     # shared activity data models
├── metrics.py    # shared activity analysis
└── workflow.py   # source-independent conversion workflow
```

Another activity source can provide the same `Activity` and `FitData` models
without changing the Sigma writer.
