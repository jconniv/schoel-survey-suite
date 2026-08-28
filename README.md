# Schoel Survey Suite

Schoel Survey Suite is an internal Windows launcher for Schoel surveying and deed-production tools, including bearing and interior-angle deed plotters, legal-description writers, coordinate and survey utilities, and QA helpers.

## Product information

- Current version: 25.0.2
- Build lineage: 2026.03.27.23a
- Status: pre-release/internal validation
- Intended users: Schoel Engineering survey personnel
- Repository maintainer: `jconniv`
- Product owner and support workflow: to be confirmed

The suite supports drafting and review. All geometry, closure, bearings, distances, curves, coordinates, units, and final survey deliverables require independent verification and appropriate licensed-surveyor review.

## Run from source

1. Install Python and the packages in `requirements.txt`.
2. Run `python suite.py`.

Embedded tools may have additional requirements documented in their own folders.

## Build

- Run `BUILD_ALL_IN_ONE_EXE_BUILD_23.bat` for the existing all-in-one build workflow.
- Run `Build_Release.bat` for the current release workflow.
- Run `Build_MSI.bat` to produce the Windows installer.

Compiled executables, installers, virtual environments, caches, signing material, and build-staging directories are excluded from source control.

## Update configuration

`update_config.json` is machine/environment-specific and is not committed. Copy `update_config.example.json` to `update_config.json` and configure the approved internal update manifest locally before building a distributable application.

## Validation

At minimum, run:

```powershell
python -m compileall -q .
python -c "import suite; print('suite import ok')"
```

Each embedded tool and the integrated Windows build still require workflow testing before release. A successful import or build is not professional or field validation.

## Repository safeguards

- Do not commit survey project inputs, client data, generated deliverables, credentials, certificates, or private signing keys.
- Never guess coordinate systems, datums, units, grid/ground status, point formats, or precision.
- Preserve the existing tool-specific calculation behavior unless a focused, tested change is approved.

See `CHANGELOG.md`, `BUILD_INFO.txt`, and the tool-specific documentation for additional history and behavior.
