"""Local cache + result-ZIP extraction.

Pure stdlib — usable (and testable) without ``mujoco`` installed. Preserves the
``meshes/`` + ``textures/`` layout MuJoCo's compiler expects relative to the XML.
"""

import os
import shutil
import zipfile
from typing import Optional, Tuple

# Main asset file extensions per download format.
_MAIN: dict = {
    "mjcf": (".xml",),
    "usd": (".usd", ".usda", ".usdc"),
    "all": (".xml", ".usd", ".usda", ".usdc"),
}


def cache_root() -> str:
    return os.environ.get("RIGYD_CACHE") or os.path.join(
        os.path.expanduser("~"), ".cache", "rigyd"
    )


def job_dir(job_id: str) -> str:
    return os.path.join(cache_root(), job_id)


def unzip_and_find(zip_path: str, dest_dir: str, fmt: str = "mjcf") -> str:
    """Extract ``zip_path`` into ``dest_dir`` and return the main asset file path."""
    if os.path.isdir(dest_dir):
        shutil.rmtree(dest_dir, ignore_errors=True)
    os.makedirs(dest_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest_dir)
    exts = _MAIN.get(fmt, (".xml",))
    found = _find(dest_dir, exts)
    if not found:
        raise FileNotFoundError(f"No {'/'.join(exts)} file found in result ZIP")
    return found


def _find(root: str, exts: Tuple[str, ...]) -> Optional[str]:
    candidates = []
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            if name.lower().endswith(exts):
                candidates.append(os.path.join(dirpath, name))
    # Shallowest path wins (the asset root file, not a nested payload).
    candidates.sort(key=lambda p: (p.count(os.sep), len(p)))
    return candidates[0] if candidates else None
