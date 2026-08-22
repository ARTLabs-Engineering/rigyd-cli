"""Rigyd SDK + CLI — compose or convert SimReady simulation assets.

    import rigyd
    rigyd.configure(api_key="rgyd_live_...")          # or `rigyd login` / RIGYD_API_KEY

    job = rigyd.convert(file="chair.glb")
    job.wait(on_progress=lambda j: print(j.status, j.progress))
    xml = job.download(fmt="mjcf")                    # or "usd" / "all"

    model = rigyd.load_model(file="chair.glb")        # -> mujoco.MjModel (needs rigyd[mujoco])

    composition = rigyd.compose(
        prompt="a compact desktop stapler",
        robot_task="press the upper arm to staple paper",
        asset_class="articulated",
        auto_submit=True,
    )
    composition.wait()
    job = composition.conversion_job()

Command line (installed as `rigyd`):
    rigyd login
    rigyd convert chair.glb --tris 50000 --export all
"""

from __future__ import annotations

from typing import Callable, Optional

from . import config as _config
from ._version import __version__
from .client import DEFAULT_CLIENT_TAG, RigydClient
from .composition import Composition
from .errors import RigydError
from .job import Job

__all__ = ["configure", "compose", "convert", "load_model", "account",
           "Composition", "Job", "RigydError", "RigydClient", "__version__"]

_DEFAULT = {"client": None}


def configure(api_key: Optional[str] = None, base_url: Optional[str] = None,
              client_tag: str = DEFAULT_CLIENT_TAG) -> RigydClient:
    """Set the default client. Falls back to env vars, then ~/.config/rigyd/."""
    _DEFAULT["client"] = RigydClient(
        _config.resolve_base_url(base_url),
        _config.resolve_api_key(api_key),
        client_tag=client_tag,
    )
    return _DEFAULT["client"]


def _client() -> RigydClient:
    if _DEFAULT["client"] is None:
        configure()
    client = _DEFAULT["client"]
    if not client.api_key:
        raise RigydError(
            "No API key. Run `rigyd login`, set RIGYD_API_KEY, or call "
            "rigyd.configure(api_key=...)."
        )
    return client


def convert(*, file: str,
            target_triangle_count: Optional[int] = None) -> Job:
    """Start a 3D-file conversion and return a Job."""
    client = _client()
    data = client.create_from_file(file, target_triangle_count)
    return Job(client, data)


def compose(*, prompt: str, robot_task: str,
            images: Optional[list] = None,
            asset_class: str = "auto",
            auto_submit: bool = False,
            negative_prompt: Optional[str] = None,
            physical_context: Optional[dict] = None) -> Composition:
    """Start a SimReady Asset Composer workflow and return a Composition."""
    if images and len(images) not in (1, 4):
        raise RigydError("Provide exactly 1 image, or 4 (front, right, back, left).")
    if asset_class not in ("auto", "rigid", "articulated"):
        raise RigydError("asset_class must be auto, rigid, or articulated")
    client = _client()
    data = client.create_composition(
        prompt,
        robot_task,
        images=images,
        asset_class=asset_class,
        auto_submit=auto_submit,
        negative_prompt=negative_prompt,
        physical_context=physical_context,
    )
    return Composition(client, data)


def load_model(*, file: str,
               target_triangle_count: Optional[int] = None,
               on_progress: Optional[Callable[[Job], None]] = None,
               dest: Optional[str] = None):
    """Convert, wait, and return a ready ``mujoco.MjModel`` (needs rigyd[mujoco])."""
    job = convert(file=file, target_triangle_count=target_triangle_count)
    job.wait(on_progress=on_progress)
    return job.load(dest=dest)


def account() -> dict:
    """Signed-in user + credit balance: {user, subscription}."""
    return _client().me()
