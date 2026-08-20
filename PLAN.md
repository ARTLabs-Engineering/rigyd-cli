# Track C — `rigyd` unified SDK + CLI

> Status: executing. New repo (`rigyd-cli/`, dist name **`rigyd`** — PyPI name verified free 2026-06-08).
> Supersedes `rigyd-mujoco` (no backward compat needed — no users yet; that repo/package will be deleted later).

## Goal

`pip install rigyd` → `rigyd convert chair.glb --export isaac` from any
terminal, and the same zero-dependency core powers the SDK, the CLI, and (later) an
MCP server. One client codebase instead of three (Isaac extension keeps its vendored
copy since Kit can't pip-install, but mirrors this core).

## CLI surface (v1)

```
rigyd login | whoami | pricing
rigyd convert chair.glb [--tris 50000] [--export ...] [-o DIR]
rigyd jobs list [--limit N] | rigyd jobs get <id>
rigyd download <id> [--export ...]      # 0 credits
rigyd simulate <id> [--scene demo|drop] # 0 credits
```

- `--export` aliases: `isaac` → usd, `mujoco` → mjcf (default usd). CLI produces
  files; live-sim loading stays in the extension/SDK.
- Progress → stderr, result path → stdout (composable); `--json` for agents/CI.
- Exit codes: 0 ok, 1 API/job failure, 2 usage, 130 interrupted.
- Key resolution: `--api-key` > `RIGYD_API_KEY` > `~/.config/rigyd/config.json`
  (written by `rigyd login`, chmod 600).
- Attribution: CLI sends `X-Rigyd-Client: cli`; SDK default `python-sdk`.

## Architecture

```
rigyd/
  _version.py   single-source version
  client.py     stdlib urllib client (+ client_tag)
  job.py        Job: wait/download/load        (copied from rigyd-mujoco)
  cache.py      ZIP extraction + cache          (copied)
  errors.py     RigydError                      (copied)
  config.py     NEW key storage
  cli.py        NEW argparse CLI (console script `rigyd`)
  __init__.py   SDK: configure/convert/load_model/account
pyproject.toml  name=rigyd, zero deps, [mujoco] extra, scripts rigyd=rigyd.cli:main
```

## Milestones

- **C0** config + client_tag — done with scaffold
- **C1** CLI core: login/whoami/pricing/jobs/download (0-credit) — verify vs job `e8rflpin2iq1vfuov7f2lkeh`
- **C2** convert/simulate
- **C3** packaging (`pip install .` → `rigyd --help`; `[mujoco]` extra)
- **C4** release: push `ARTLabs-Engineering/rigyd-python`, publish `rigyd` to PyPI, tag v1.0.0; later delete `rigyd-mujoco` repo + yank PyPI 1.0.0

## Verification

1. Offline: `--help` for every subcommand; config round-trip with 600 perms; py3.9 compat (system python).
2. 0-credit live: `whoami`, `pricing`, `jobs list`, `jobs get`, `download <id> --export mujoco|isaac|all`.
3. One paid run: `rigyd convert test.glb --export all` → completed; job's `parameters.client == "cli"`.
4. Packaging: fresh venv `pip install .` → `rigyd --help`; `pip install .[mujoco]` → `rigyd.load_model` works.

## Later
- `rigyd-mcp` server on this core; more `--export` targets (gazebo/ros) as the API grows; shell completions.
