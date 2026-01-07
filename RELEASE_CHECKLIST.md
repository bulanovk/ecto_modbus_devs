# Release checklist — Ectocontrol Modbus Adapter v2

Follow these steps before publishing a release and submitting to HACS.

1. Bump version
   - Update `custom_components/ectocontrol_modbus/manifest.json` `version` field (semver).

2. Run tests

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt  # if present
pip install pytest pytest-asyncio pytest-cov
python -m pytest --maxfail=1 -q --cov=custom_components --cov-report=term-missing
```

3. Update CHANGELOG / Release notes
   - Add a `CHANGELOG.md` entry describing fixes and features.

4. Tag & push

```bash
git add -A
git commit -m "Release vX.Y.Z"
git tag vX.Y.Z
git push origin main --tags
```

5. Create GitHub release
   - Draft release with changelog and binaries (if any).

6. Open HACS PR (if required)
   - Update the HACS repository index if your project is not auto-indexed.
   - Ensure `hacs.json` is present at repo root and `manifest.json` metadata is correct.

7. Verify CI & coverage
   - Ensure the GitHub Actions CI run passes on the release tag.

8. Publish and announce
   - Once approved in HACS (if applicable), announce the release and update documentation.

Optional: Create a maintenance branch and backport fixes as needed.
