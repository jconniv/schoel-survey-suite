import importlib.util
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN_PATH = os.path.join(BASE_DIR, "main.py")


def main():
    spec = importlib.util.spec_from_file_location("plotter_angle_main", MAIN_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load interior angle plotter from {MAIN_PATH}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["plotter_angle_main"] = mod
    spec.loader.exec_module(mod)
    if hasattr(mod, "App"):
        app = mod.App()
        app.mainloop()
    elif hasattr(mod, "main"):
        mod.main()
    else:
        raise RuntimeError("Interior angle plotter did not expose App or main().")


if __name__ == "__main__":
    main()
