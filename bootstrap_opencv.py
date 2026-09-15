from __future__ import annotations

import importlib
import subprocess
import sys

HEADLESS_PACKAGE = "opencv-contrib-python-headless==4.10.0.84"


def cv2_works() -> bool:
    try:
        import cv2  # noqa: F401
        return True
    except Exception as exc:
        print(f"[bootstrap] cv2 import failed: {exc}", flush=True)
        return False


def repair_cv2() -> None:
    print(
        "[bootstrap] Installing headless OpenCV binary compatible with PaddleX...",
        flush=True,
    )
    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-cache-dir",
            "--force-reinstall",
            "--no-deps",
            HEADLESS_PACKAGE,
        ]
    )
    importlib.invalidate_caches()


if __name__ == "__main__":
    if not cv2_works():
        repair_cv2()
        # Verify in a clean Python process because a failed native import may leave
        # partially initialized modules in this interpreter.
        subprocess.check_call(
            [sys.executable, "-c", "import cv2; print('[bootstrap] cv2 OK', cv2.__version__)"]
        )
    else:
        print("[bootstrap] cv2 OK; no repair needed.", flush=True)
