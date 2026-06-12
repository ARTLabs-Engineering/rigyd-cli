"""Rigyd SDK + CLI — convert 3D / text / images into SimReady simulation assets.

    import rigyd
    rigyd.configure(api_key="rgyd_live_...")          # or `rigyd login` / RIGYD_API_KEY

    job = rigyd.convert(prompt="a wooden chair")      # or file= / images=[...]
    job.wait(on_progress=lambda j: print(j.status, j.progress))
    xml = job.download(fmt="mjcf")                    # or "usd" / "all"

    model = rigyd.load_model(prompt="a wooden chair") # -> mujoco.MjModel (needs rigyd[mujoco])

Command line (installed as `rigyd`):
    rigyd login
    rigyd generate --text "wooden chair" --export isaac -o ./assets
    rigyd convert chair.glb --tris 50000 --export all
"""

from __future__ import annotations

from typing import Callable, List, Optional

from . import config as _config
from ._version import __version__
from .client import DEFAULT_CLIENT_TAG, RigydClient
from .errors import RigydError
from .job import Job

__all__ = ["configure", "convert", "generate", "load_model", "account",
           "Job", "RigydError", "RigydClient", "__version__"]

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


def convert(*, file: Optional[str] = None, prompt: Optional[str] = None,
            images: Optional[List[str]] = None,
            target_triangle_count: Optional[int] = None) -> Job:
    """Start a conversion and return a Job. Provide exactly one input."""
    client = _client()
    given = [name for name, val in
             (("file", file), ("prompt", prompt), ("images", images)) if val]
    if len(given) != 1:
        raise RigydError("Provide exactly one of file=, prompt=, or images=.")
    if file:
        data = client.create_from_file(file, target_triangle_count)
    elif prompt:
        data = client.generate_from_prompt(prompt)
    else:
        if len(images) not in (1, 4):
            raise RigydError("Provide exactly 1 image, or 4 (front, right, back, left).")
        data = client.generate_from_images(images)
    return Job(client, data)


# `generate` reads more naturally for text/image inputs; same call.
generate = convert


def load_model(*, file: Optional[str] = None, prompt: Optional[str] = None,
               images: Optional[List[str]] = None,
               target_triangle_count: Optional[int] = None,
               on_progress: Optional[Callable[[Job], None]] = None,
               dest: Optional[str] = None):
    """Convert, wait, and return a ready ``mujoco.MjModel`` (needs rigyd[mujoco])."""
    job = convert(file=file, prompt=prompt, images=images,
                  target_triangle_count=target_triangle_count)
    job.wait(on_progress=on_progress)
    return job.load(dest=dest)


def account() -> dict:
    """Signed-in user + credit balance: {user, subscription}."""
    return _client().me()
