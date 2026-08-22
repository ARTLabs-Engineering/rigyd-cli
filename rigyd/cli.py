"""The `rigyd` command-line interface.

Conventions:
- Progress/log lines go to stderr; results (file paths or --json payloads) go to
  stdout, so ``$(rigyd convert ...)`` composes in scripts.
- ``--export`` accepts formats (usd, mjcf, all) or simulator aliases
  (isaac -> usd, mujoco -> mjcf). The CLI produces asset *files*; loading into a
  live simulator is the Isaac extension's / MuJoCo SDK's job.
- Exit codes: 0 success, 1 API/job failure, 2 usage error, 130 interrupted.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from typing import Optional

from . import config, tui
from ._version import __version__
from .client import RigydClient
from .composition import Composition
from .errors import RigydError
from .job import Job

EXPORT_ALIASES = {
    "usd": "usd", "isaac": "usd",
    "mjcf": "mjcf", "mujoco": "mjcf",
    "all": "all",
}


def _err(msg: str) -> None:
    print(msg, file=sys.stderr)


def _watch(status: "tui.StatusLine", job: Job) -> None:
    """Poll a job to completion, feeding the animated status line."""
    job.wait(on_progress=lambda j: status.update(
        j.stage or j.status or "...", (j.progress or 0) / 100.0))


def _watch_composition(status: "tui.StatusLine", composition: Composition) -> None:
    composition.wait(on_progress=lambda item: status.update(
        item.stage or item.status or "...", (item.progress or 0) / 100.0))


def _client(args) -> RigydClient:
    return RigydClient(
        config.resolve_base_url(getattr(args, "base_url", None)),
        config.resolve_api_key(getattr(args, "api_key", None)),
        client_tag="cli",
    )


def _resolve_export(value: str) -> str:
    fmt = EXPORT_ALIASES.get(value.lower())
    if not fmt:
        raise RigydError(
            f"Unknown export target '{value}'. "
            f"Use one of: {', '.join(sorted(EXPORT_ALIASES))}", status=None)
    return fmt


def _download(job: Job, fmt: str, output_base: str, as_json: bool,
              extra: Optional[dict] = None) -> int:
    """Download a completed job and print the result path (or JSON manifest)."""
    # Extract into a per-job subdir: Job.download clears its dest dir first, so
    # never hand it a user directory like "." directly.
    dest = os.path.join(os.path.abspath(output_base), job.id)
    status = tui.StatusLine().start(f"downloading {fmt}")
    try:
        main_path = job.download(fmt=fmt, dest=dest)
    except (RigydError, OSError) as exc:
        status.fail(str(exc))
        raise
    status.done(f"saved {fmt} package")
    if as_json:
        files = sorted(
            os.path.relpath(os.path.join(d, f), dest)
            for d, _dirs, fs in os.walk(dest) for f in fs
        )
        manifest = {"job_id": job.id, "format": fmt, "dir": dest,
                    "main": main_path, "files": files}
        manifest.update(extra or {})
        print(json.dumps(manifest, indent=2))
    else:
        print(dest if fmt == "all" else main_path)
    return 0


def _submit_and_run(args, label: str, client: RigydClient, create_fn) -> int:
    """One status line across submit -> queue -> pipeline -> done, then download."""
    status = tui.StatusLine().start(label)
    try:
        job = Job(client, create_fn())
        if not job.id:
            raise RigydError(f"Unexpected response: {job._data}")
        status.update("queued")
        _watch(status, job)
    except RigydError as exc:
        status.fail(str(exc))
        return 1
    except KeyboardInterrupt:
        status.fail("interrupted")
        raise
    status.done(f"completed - job {job.id}")
    return _download(job, _resolve_export(args.export), args.output, args.json)


# -- commands ---------------------------------------------------------------

def cmd_login(args) -> int:
    key = args.api_key or getpass.getpass("Rigyd API key (rgyd_live_...): ")
    if not key.strip():
        _err("No key entered.")
        return 2
    client = RigydClient(config.resolve_base_url(args.base_url), key.strip(),
                         client_tag="cli")
    me = client.me()  # validates the key; raises RigydError if bad
    path = config.save(api_key=key.strip(),
                       base_url=args.base_url if args.base_url else None)
    user = (me.get("user") or {}).get("email") or "unknown"
    _err(tui.ok_line(f"logged in as {user} - key saved to {path}"))
    return 0


def cmd_whoami(args) -> int:
    data = _client(args).me()
    if args.json:
        print(json.dumps(data, indent=2))
        return 0
    user = data.get("user") or {}
    sub = data.get("subscription") or {}
    out = sys.stdout
    print(f"{tui.glyph('+', stream=out)} "
          f"{tui.lime(user.get('email') or user.get('username') or 'unknown', stream=out)}")
    print(f"    plan: {((sub.get('plan') or {}).get('name')) or sub.get('status')}"
          f"  |  credits: {tui.lime(str(sub.get('credits_remaining')), stream=out)}")
    return 0


def cmd_pricing(args) -> int:
    data = _client(args).pricing()
    if args.json:
        print(json.dumps(data, indent=2))
        return 0
    out = sys.stdout
    for job_type, cost in (data.get("pricing") or data or {}).items():
        print(f"{tui.glyph('+', stream=out)} {job_type:24} "
              f"{tui.lime(str(cost), stream=out)} credit(s)")
    return 0


def _physical_context(args) -> Optional[dict]:
    context = {}
    if args.dimensions:
        context["dimensions_m"] = dict(zip(
            ("length", "width", "height"), args.dimensions))
    if args.mass_kg is not None:
        context["mass_kg"] = args.mass_kg
    if args.material:
        context["materials"] = args.material
    if args.fixed_base is not None:
        context["fixed_base"] = args.fixed_base
    return context or None


def cmd_compose(args) -> int:
    images = args.image or []
    if len(images) not in (0, 1, 4):
        _err(tui.err_line("Provide 0, 1, or 4 images (front, right, back, left)."))
        return 2
    for image_path in images:
        if not os.path.isfile(image_path):
            _err(tui.err_line(f"Image not found: {image_path}"))
            return 2

    client = _client(args)
    status = tui.StatusLine().start("composing asset")
    try:
        composition = Composition(client, client.create_composition(
            args.prompt,
            args.task,
            images=images,
            asset_class=args.asset_class,
            auto_submit=not args.review,
            negative_prompt=args.negative_prompt,
            physical_context=_physical_context(args),
        ))
        if not composition.id:
            raise RigydError(f"Unexpected response: {composition._data}")
        _watch_composition(status, composition)
    except RigydError as exc:
        status.fail(str(exc))
        return 1
    except KeyboardInterrupt:
        status.fail("interrupted")
        raise

    if args.review:
        status.done(f"prototype ready - composition {composition.id}")
        print(json.dumps(composition._data, indent=2) if args.json else composition.id)
        return 0

    try:
        job = composition.conversion_job()
    except RigydError as exc:
        status.fail(str(exc))
        return 1
    status.done(f"completed - composition {composition.id}, job {job.id}")
    return _download(job, _resolve_export(args.export), args.output, args.json,
                     {"composition_id": composition.id})


def cmd_convert(args) -> int:
    if not os.path.isfile(args.file):
        _err(tui.err_line(f"File not found: {args.file}"))
        return 2
    client = _client(args)
    return _submit_and_run(
        args, f"converting {os.path.basename(args.file)}", client,
        lambda: client.create_from_file(args.file, args.tris))


def cmd_jobs_list(args) -> int:
    body = _client(args).list_jobs(page=args.page, page_size=args.limit)
    jobs, meta = body.get("data", []), body.get("meta", {})
    if args.json:
        print(json.dumps(body, indent=2))
        return 0
    for j in jobs:
        print(f"{j.get('id')}  {j.get('status'):12} {j.get('progress') or 0:>3}%  "
              f"{j.get('job_type', ''):22} {j.get('filename') or ''}")
    _err(f"page {meta.get('page')}/{meta.get('pageCount')} - {meta.get('total')} total")
    return 0


def cmd_jobs_get(args) -> int:
    data = _client(args).get_job(args.job_id)
    if args.json:
        print(json.dumps(data, indent=2))
        return 0
    for key in ("id", "status", "stage", "progress", "job_type", "filename",
                "credits_charged", "error", "createdAt"):
        if data.get(key) is not None:
            print(f"{key:16} {data[key]}")
    out = data.get("output") or {}
    for key in ("model", "mjcf_package", "sim_video", "sim_gif"):
        if out.get(key):
            print(f"output.{key:9} {out[key].get('name')}")
    return 0


def cmd_compositions_list(args) -> int:
    body = _client(args).list_compositions(page=args.page, page_size=args.limit)
    compositions = body.get("data", [])
    if args.json:
        print(json.dumps(body, indent=2))
        return 0
    for item in compositions:
        workflow = item.get("workflow") or {}
        asset_brief = item.get("asset_brief") or {}
        status = workflow.get("status") or item.get("status") or ""
        asset_class = (item.get("requested_asset_class") or
                       asset_brief.get("asset_class") or "auto")
        mode = item.get("interaction_mode") or "interactive"
        print(f"{item.get('id')}  {status:10} "
              f"{workflow.get('progress') or 0:>3}%  "
              f"{mode:15} {asset_class:11} "
              f"{item.get('seed_input') or ''}")
    return 0


def cmd_compositions_get(args) -> int:
    data = _client(args).get_composition(args.composition_id)
    if args.json:
        print(json.dumps(data, indent=2))
        return 0
    workflow = data.get("workflow") or {}
    asset_brief = data.get("asset_brief") or {}
    rows = {
        "id": data.get("id"),
        "mode": data.get("interaction_mode"),
        "status": workflow.get("status") or data.get("status"),
        "stage": workflow.get("stage"),
        "progress": workflow.get("progress"),
        "asset_class": (data.get("requested_asset_class") or
                        asset_brief.get("asset_class")),
        "conversion_job": data.get("conversion_job_id"),
        "error": workflow.get("error"),
    }
    for key, value in rows.items():
        if value is not None:
            print(f"{key:16} {value}")
    return 0


def cmd_compositions_submit(args) -> int:
    client = _client(args)
    status = tui.StatusLine().start(f"submitting composition {args.composition_id}")
    try:
        job = Job(client, client.submit_composition(args.composition_id))
        if not job.id:
            raise RigydError(f"Unexpected response: {job._data}")
        _watch(status, job)
    except RigydError as exc:
        status.fail(str(exc))
        return 1
    status.done(f"completed - job {job.id}")
    return _download(job, _resolve_export(args.export), args.output, args.json,
                     {"composition_id": args.composition_id})


def cmd_download(args) -> int:
    job = Job(_client(args), {"id": args.job_id}).refresh()
    if not job.done:
        status = tui.StatusLine().start(f"waiting for job {job.id}")
        try:
            _watch(status, job)
        except RigydError as exc:
            status.fail(str(exc))
            return 1
        status.done(f"completed - job {job.id}")
    return _download(job, _resolve_export(args.export), args.output, args.json)


def cmd_simulate(args) -> int:
    client = _client(args)
    status = tui.StatusLine().start(f"simulating job {args.job_id}"
                                    + (f" ({args.scene})" if args.scene else ""))
    try:
        sim = Job(client, client.simulate(args.job_id, scene=args.scene))
        _watch(status, sim)
    except RigydError as exc:
        status.fail(str(exc))
        return 1
    status.done(f"simulation completed - job {sim.id}")
    final = client.get_job(sim.id)
    if args.json:
        print(json.dumps(final, indent=2))
        return 0
    out = final.get("output") or {}
    for key in ("sim_video", "sim_gif", "sim_log"):
        if out.get(key) and out[key].get("url"):
            print(f"{key}: {out[key]['url']}")
    return 0


# -- parser -----------------------------------------------------------------

class _HelpfulParser(argparse.ArgumentParser):
    """On usage errors (missing args/subcommand), show the command's full help
    instead of a terse usage line."""

    def error(self, message: str) -> "NoReturn":  # noqa: F821
        sys.stderr.write(tui.err_line(message) + "\n\n")
        self.print_help(sys.stderr)
        raise SystemExit(2)


class _BrandParser(_HelpfulParser):
    """Top-level parser whose help page opens with the Rigyd banner."""

    def format_help(self) -> str:
        tagline = f"Compose or convert SimReady assets  ·  v{__version__}  ·  rigyd.com"
        return tui.banner(sys.stdout, tagline=tagline) + "\n" + super().format_help()


def _add_common(p: argparse.ArgumentParser, export: bool = False,
                json_flag: bool = True) -> None:
    p.add_argument("--api-key", help="override the stored/env API key")
    p.add_argument("--base-url", help=argparse.SUPPRESS)
    if json_flag:
        p.add_argument("--json", action="store_true",
                       help="machine-readable JSON on stdout")
    if export:
        p.add_argument("--export", default="usd", metavar="TARGET",
                       help="usd | mjcf | all (aliases: isaac, mujoco) [default: usd]")
        p.add_argument("-o", "--output", default=".", metavar="DIR",
                       help="output directory (a per-job subfolder is created) [default: .]")


def build_parser() -> argparse.ArgumentParser:
    parser = _BrandParser(
        prog="rigyd",
        description="Compose or convert SimReady simulation assets.",
    )
    parser.add_argument("--version", action="version", version=f"rigyd {__version__}")
    # Subcommands: help-on-error, but banner-free (parser_class would inherit
    # _BrandParser otherwise).
    sub = parser.add_subparsers(dest="command", required=True,
                                parser_class=_HelpfulParser)

    p = sub.add_parser("login", help="store your API key (validates it first)")
    _add_common(p, json_flag=False)
    p.set_defaults(fn=cmd_login)

    p = sub.add_parser("whoami", help="signed-in user + credit balance")
    _add_common(p)
    p.set_defaults(fn=cmd_whoami)

    p = sub.add_parser("pricing", help="current workflow credit costs")
    _add_common(p)
    p.set_defaults(fn=cmd_pricing)

    p = sub.add_parser("compose", help="idea or reference images -> SimReady asset")
    p.add_argument("prompt", help="object description")
    p.add_argument("--task", required=True, help="robotic task the asset must support")
    p.add_argument("--image", action="append", metavar="PATH",
                   help="optional reference; pass once, or 4x for front/right/back/left")
    p.add_argument("--asset-class", choices=["auto", "rigid", "articulated"],
                   default="auto")
    p.add_argument("--negative-prompt")
    p.add_argument("--dimensions", type=float, nargs=3,
                   metavar=("LENGTH", "WIDTH", "HEIGHT"),
                   help="declared dimensions in metres")
    p.add_argument("--mass-kg", type=float)
    p.add_argument("--material", action="append",
                   help="declared material; repeat for multiple materials")
    base = p.add_mutually_exclusive_group()
    base.add_argument("--fixed-base", dest="fixed_base", action="store_true")
    base.add_argument("--free-base", dest="fixed_base", action="store_false")
    p.set_defaults(fixed_base=None)
    p.add_argument("--review", action="store_true",
                   help="stop when the prototype is ready instead of submitting to SimReady")
    _add_common(p, export=True)
    p.set_defaults(fn=cmd_compose)

    p = sub.add_parser("convert", help="3D file -> SimReady asset (free)")
    p.add_argument("file", help=".glb/.gltf/.fbx/.obj/.stl/.ply/.usd*")
    p.add_argument("--tris", type=int, metavar="N",
                   help="optimize to a target triangle count (1000-1000000)")
    _add_common(p, export=True)
    p.set_defaults(fn=cmd_convert)

    p = sub.add_parser("jobs", help="list or inspect conversion jobs")
    jobs_sub = p.add_subparsers(dest="jobs_command", required=True)
    pl = jobs_sub.add_parser("list", help="list your jobs")
    pl.add_argument("--limit", type=int, default=25)
    pl.add_argument("--page", type=int, default=1)
    _add_common(pl)
    pl.set_defaults(fn=cmd_jobs_list)
    pg = jobs_sub.add_parser("get", help="job status/details")
    pg.add_argument("job_id")
    _add_common(pg)
    pg.set_defaults(fn=cmd_jobs_get)

    p = sub.add_parser("compositions", help="list, inspect, or submit compositions")
    compositions_sub = p.add_subparsers(dest="compositions_command", required=True)
    pl = compositions_sub.add_parser("list", help="list composition workflows")
    pl.add_argument("--limit", type=int, default=25)
    pl.add_argument("--page", type=int, default=1)
    _add_common(pl)
    pl.set_defaults(fn=cmd_compositions_list)
    pg = compositions_sub.add_parser("get", help="composition status/details")
    pg.add_argument("composition_id")
    _add_common(pg)
    pg.set_defaults(fn=cmd_compositions_get)
    ps = compositions_sub.add_parser("submit", help="submit a ready prototype to SimReady")
    ps.add_argument("composition_id")
    _add_common(ps, export=True)
    ps.set_defaults(fn=cmd_compositions_submit)

    p = sub.add_parser("download", help="(re)download a job's assets - 0 credits")
    p.add_argument("job_id")
    _add_common(p, export=True)
    p.set_defaults(fn=cmd_download)

    p = sub.add_parser("simulate", help="run a physics demo on a completed job - 0 credits")
    p.add_argument("job_id")
    p.add_argument("--scene", choices=["demo", "drop"])
    _add_common(p)
    p.set_defaults(fn=cmd_simulate)

    return parser


def main(argv: Optional[list] = None) -> int:
    parser = build_parser()
    if not (argv if argv is not None else sys.argv[1:]):
        parser.print_help()  # bare `rigyd` -> branded help, not a usage error
        return 0
    args = parser.parse_args(argv)
    try:
        return args.fn(args)
    except RigydError as exc:
        _err(tui.err_line(f"error: {exc}"))
        return 1
    except KeyboardInterrupt:
        _err(tui.err_line("interrupted"))
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
