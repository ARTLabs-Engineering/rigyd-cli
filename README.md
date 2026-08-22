# rigyd

SDK + CLI for [Rigyd](https://rigyd.com): compose an asset from intent and
optional reference images, or convert an existing **3D model**, into a
physics-enabled **SimReady** simulation asset — USD for NVIDIA Isaac Sim and
MJCF for MuJoCo.

Zero dependencies. `pip install rigyd` and go.

## CLI

```bash
pip install rigyd
rigyd login                                   # stores your rgyd_live_... key

rigyd compose "compact desktop stapler" \
  --task "press the upper arm to staple paper" \
  --asset-class articulated --export all

rigyd convert chair.glb --tris 50000 --export all

rigyd compositions list
rigyd compositions get <composition_id>
rigyd compositions submit <composition_id> --export all
rigyd jobs list
rigyd jobs get <job_id>
rigyd download <job_id> --export mujoco       # re-download any job, 0 credits
rigyd simulate <job_id> --scene drop          # physics demo video, 0 credits
rigyd whoami                                  # user + credit balance
```

- `--export` takes a format (`usd`, `mjcf`, `all`) or a simulator alias
  (`isaac` → USD, `mujoco` → MJCF). Default: `usd`.
- Progress goes to **stderr**, the result path to **stdout**, so it composes:
  `blender $(rigyd convert scan.obj --export usd)`. Add `--json` for a
  machine-readable manifest (agents/CI).

| Input | Command | Cost |
|------|---------|------|
| Idea + optional 1 or 4 images | `rigyd compose PROMPT --task TASK` | prototype price from `rigyd pricing` |
| 3D file (`.glb/.gltf/.fbx/.obj/.stl/.ply/.usd*`) | `rigyd convert FILE` | free |

`rigyd compose` submits to SimReady automatically and downloads the result.
Add `--review` to stop when the prototype is ready; later run
`rigyd compositions submit <composition_id>`.

## Python SDK

```python
import rigyd
rigyd.configure()                                  # key from login/env

job = rigyd.convert(file="chair.glb")
job.wait(on_progress=lambda j: print(j.status, j.stage, j.progress))
xml_path = job.download(fmt="mjcf")                # or "usd" / "all"
print(rigyd.account())                             # user + credit balance
```

```python
composition = rigyd.compose(
    prompt="compact desktop stapler",
    robot_task="press the upper arm to staple paper",
    asset_class="articulated",
    auto_submit=True,
    physical_context={
        "dimensions_m": {"length": 0.15, "width": 0.04, "height": 0.08},
        "materials": ["ABS plastic", "steel"],
        "fixed_base": False,
    },
)
composition.wait()
job = composition.conversion_job()
usd_path = job.download(fmt="usd")
```

### MuJoCo extra

```bash
pip install "rigyd[mujoco]"
```

```python
model = rigyd.load_model(file="chair.glb")  # -> mujoco.MjModel, ready to mj_step
```

## Loading into a live simulator

- **NVIDIA Isaac Sim** — use the [Rigyd SimReady Importer extension](https://github.com/ARTLabs-Engineering/rigyd-isaac-sim)
  (Omniverse Community Registry: `rigyd.simready`) to generate and load assets
  onto the stage without leaving the app. This CLI produces the same USD files
  for offline/scripted pipelines.
- **MuJoCo** — `rigyd.load_model(...)` above, or
  `mujoco.MjModel.from_xml_path(<path from rigyd download --export mujoco>)`.

## Configuration

Key resolution order: `--api-key` flag → `RIGYD_API_KEY` env →
`~/.config/rigyd/config.json` (written by `rigyd login`, mode 600).

## License

MIT — see [LICENSE](./LICENSE).
