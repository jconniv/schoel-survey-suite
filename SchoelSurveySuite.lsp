; ============================================================
; Schoel Survey Suite - Civil 3D / AutoCAD LISP Launcher
;
; Commands:
;   SCHOELSURVEY       Launch the Schoel Survey Suite EXE
;   SCHOELSURVEYPATH   Pick and save the EXE path
;   SCHOELSURVEYTEST   Test the saved EXE path
;
; Ribbon macro:
;   ^C^C(if (not c:SCHOELSURVEY) (load "C:/SchoelTools/SchoelSurveySuite/SchoelSurveySuite.lsp"));SCHOELSURVEY;
; ============================================================

(vl-load-com)

(setq *SCHOELSURVEY_REGKEY* "HKEY_CURRENT_USER\\Software\\Schoel\\SurveySuite")
(setq *SCHOELSURVEY_DEFAULT_EXE* "C:\\Program Files\\SchoelTools\\SchoelSurveySuite\\SchoelSurveySuite.exe")

(defun schoelsurvey-getpath ( / p )
  (setq p (vl-registry-read *SCHOELSURVEY_REGKEY* "ExePath"))
  (if (or (null p) (= p ""))
    (setq p *SCHOELSURVEY_DEFAULT_EXE*)
  )
  p
)

(defun schoelsurvey-setpath (p)
  (vl-registry-write *SCHOELSURVEY_REGKEY* "ExePath" p)
  p
)

(defun schoelsurvey-exists (p)
  (and p (/= p "") (findfile p))
)

(defun c:SCHOELSURVEYPATH ( / p )
  (setq p (getfiled "Pick SchoelSurveySuite.exe" (schoelsurvey-getpath) "exe" 0))
  (if p
    (progn
      (schoelsurvey-setpath p)
      (princ (strcat "\nSaved Schoel Survey Suite EXE path: " p))
    )
    (princ "\nNo EXE selected.")
  )
  (princ)
)

(defun c:SCHOELSURVEYTEST ( / p )
  (setq p (schoelsurvey-getpath))
  (princ (strcat "\nSaved EXE path: " p))
  (if (schoelsurvey-exists p)
    (princ "\nEXE FOUND. Run SCHOELSURVEY to launch.")
    (princ "\nEXE NOT FOUND. Run SCHOELSURVEYPATH and pick the EXE.")
  )
  (princ)
)

(defun c:SCHOELSURVEY ( / p )
  (setq p (schoelsurvey-getpath))
  (if (not (schoelsurvey-exists p))
    (progn
      (alert
        (strcat
          "SchoelSurveySuite.exe was not found.\n\n"
          "Saved path:\n" p "\n\n"
          "Pick the EXE now."
        )
      )
      (c:SCHOELSURVEYPATH)
      (setq p (schoelsurvey-getpath))
    )
  )
  (if (schoelsurvey-exists p)
    (progn
      (startapp p)
      (princ (strcat "\nLaunching Schoel Survey Suite: " p))
    )
    (alert
      "Still cannot find the EXE.\n\nInstall Schoel Survey Suite from the MSI, then run SCHOELSURVEYPATH if needed."
    )
  )
  (princ)
)

(princ "\nSchoel Survey Suite LISP loaded.")
(princ "\nCommands: SCHOELSURVEY, SCHOELSURVEYPATH, SCHOELSURVEYTEST")
(princ)

