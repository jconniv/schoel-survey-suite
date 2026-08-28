Schoel Survey Suite CAD Ribbon Setup

Installed EXE path:
C:\Program Files\SchoelTools\SchoelSurveySuite\SchoelSurveySuite.exe

Installed LSP path:
C:\Program Files\SchoelTools\SchoelSurveySuite\SchoelSurveySuite.lsp

AutoCAD/Civil 3D command loaded by SchoelSurveySuite.lsp:
SCHOELSURVEY

Ribbon button macro:
^C^C(if (not c:SCHOELSURVEY) (load "C:/Program Files/SchoelTools/SchoelSurveySuite/SchoelSurveySuite.lsp"));SCHOELSURVEY;

Button label:
Schoel Survey Suite

Tooltip:
Launch Schoel Survey Suite.

Versioning:
Use Build_Release.bat to build releases. With no argument it bumps patch version.
Use Build_Release.bat 25.1.0 to set an exact version.

Deployment note:
For company rollout, point every ribbon button to the installed LSP path above.
The LSP launches the installed MSI-managed EXE.

Auto-update check:
update_config.json points to:
R:\Technology\Publish\SchoelSurveySuite\version.json

Put both files in that shared folder after each release:
SchoelSurveySuite-25.0.2.msi
version.json

On launch, the app reads version.json. If the version is newer, it prompts the user to open the MSI.
