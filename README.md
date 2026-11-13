# Page 888

Live US National Weather Service alerts as retro teletext-style pages: 40x24 character grid, eight block colours, numbered pages, no JavaScript, each page under 50 KB. Built to be readable on constrained devices and with assistive technology (manual accessibility checks are still pending; see [docs/CHECKS.md](docs/CHECKS.md)).

Built for the Kiroween 2026 hackathon (Resurrection category) with Kiro. Specs, steering, hooks and a custom review agent live in [`.kiro/`](.kiro/).

Live site: LIVE_URL_TBD

Status: build phase. The generator and tests are implemented; hosting is configured through GitHub Actions and has not been confirmed live yet.

## Run

```
python3.12 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest -q
PAGE888_USER_AGENT="MyApp (https://example.org/contact)" PAGE888_AREA=CA python -m page888
python tools/check_pages.py site --strict
```

Full documentation: [docs/README.md](docs/README.md).

Weather data: [api.weather.gov](https://www.weather.gov/documentation/services-web-api). Not an official NWS product and not an official warning channel.

License: MIT.
