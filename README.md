# Sidewalk Joy — public data feed

Auto-generated, public data mirror for the **Sidewalk Joy** app.

`spots.json` is regenerated once a day by a GitHub Action from the public
Google My Maps KML feed behind worldwidesidewalkjoy.com. The app reads it at:

```
https://raw.githubusercontent.com/admiller007/sidewalk-joy-data/main/spots.json
```

This repo contains **only already-public map data** plus the script that
normalizes it — no application source. The app's source lives in a separate
private repository.

- `import_sidewalk_joy_kml.py` — KML → normalized JSON.
- `.github/workflows/update-spots.yml` — daily cron + manual run.

Run locally: `python3 import_sidewalk_joy_kml.py spots.json`
