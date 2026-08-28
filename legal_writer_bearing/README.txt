Schoel Legal Description Generator from DXF

Changes in this version
- Boilerplate paragraph is always included (editable)
- Word DOCX spacing matches the Schoel template style: Times New Roman 12 and double spaced
- Underlines "Point of Beginning" in the DOCX
- No Schoel logo is exported into DOCX, RTF, or TXT
- The logo shown in the program is smaller

How to use
1. Select DXF
2. Choose the closed boundary polyline
3. Click the vertex that is your Point of Beginning
4. Choose clockwise or counterclockwise
5. Edit the boilerplate paragraph if needed
6. Type your Commencing / intro paragraph
7. Export DOCX RTF TXT

DXF requirement
Boundary must be a closed LWPOLYLINE or POLYLINE in modelspace
Curves must be bulges on the polyline

Build exe
1. Install Python 3.10 or newer
2. Unzip this folder
3. Delete .venv if it exists
4. Double click build_exe.bat
5. EXE will be in dist
