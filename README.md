# Ectocontrol Modbus Adapter v2 — Home Assistant Integration

This repository contains a Home Assistant custom integration (HACS-ready) to integrate GAS boilers through the Ectocontrol Modbus Adapter v2 (RS-485 Modbus RTU).

Quick start (development):

```bash
# create virtualenv
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

The integration folder is `custom_components/ectocontrol_modbus`.

Next steps: implement full gateway, coordinator, entities and config flow according to `IMPLEMENTATION_PLAN.md`.

HACS installation
-----------------

To install via HACS:

1. In HACS, go to _Custom repositories_ and add this repository with category _Integration_.
2. Install the integration from HACS and restart Home Assistant.
3. Add the integration via Settings → Devices & Services → Add Integration.

If you are releasing to HACS, ensure `hacs.json` is present at repository root and `manifest.json` has accurate metadata.
