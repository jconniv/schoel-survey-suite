# Changelog

## [Unreleased]

### Maintenance

- Added an automatic-on-`main`, manually runnable, non-deleting GitHub-to-SharePoint source mirror with protected credential handling and generated-file exclusions.

## [25.0.2] - 2026-07-01

### Changed

- Preserved the latest located Schoel Survey Suite source and release tooling as the repository baseline.
- Includes the DXF bearing-distance grip-fix build lineage identified by the source folder.
- Maintains isolated embedded legal-writer executables so bearing and interior-angle CW/CCW behavior does not cross between tools.

### Repository

- Added source-control exclusions for generated executables, installers, virtual environments, build staging, signing material, and machine-specific update configuration.
- Added repository documentation and a safe update-configuration template.

### Survey/data impact

- Repository preparation did not change survey calculations, coordinates, elevations, units, datums, precision, imports, exports, or embedded-tool behavior.
