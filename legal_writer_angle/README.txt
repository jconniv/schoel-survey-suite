Birmingham Legal Description Writer

This build keeps the legal description wording updates and switches the EXE read aloud to a native Windows speech path through hidden PowerShell and System.Speech.
That means the office computers only need the EXE and standard Windows components. No Python install is needed on those machines.

What changed in this version:
1. Read Aloud now uses native Windows speech instead of bundled Python speech drivers.
2. Play by Highlight moves call by call based on semicolons, not sentence by sentence.
3. The read speed is faster.
4. The black command window stays hidden.
5. P.C., P.T., P.C.C., and P.R.C. wording stays the same as the working legal output.

Windows build:
1. Open Command Prompt in this folder
2. Delete old build and dist folders if they exist
3. Run build_exe.bat
4. The EXE will be created in dist\BirminghamLegalDescriptionWriter.exe

Read aloud notes:
1. Read Aloud reads the current preview without yellow highlighting
2. Play by Highlight reads the current preview and highlights each legal call while it is spoken
3. Pause, Resume, and Stop work between legal calls
4. The EXE does not require Python on the target computer after it is built
