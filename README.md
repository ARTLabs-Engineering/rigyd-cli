# rigyd

SDK + CLI for [Rigyd](https://rigyd.com): convert any **3D model, text prompt,
or image** into a physics-enabled **SimReady** simulation asset — USD for
NVIDIA Isaac Sim, MJCF for MuJoCo — from your terminal or your Python code.

Zero dependencies. `pip install rigyd` and go.

## CLI

```bash
pip install rigyd
rigyd login                                   # stores your rgyd_live_... key

rigyd generate --text "wooden chair" --export isaac -o ./assets
rigyd generate --image front.png --image right.png --image back.png --image left.png
rigyd convert chair.glb --tris 50000 --export all

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
| Text prompt | `rigyd generate --text "..."` | 2 credits |
| 1 or 4 images | `rigyd generate --image ...` | 3 credits |
| 3D file (`.glb/.gltf/.fbx/.obj/.stl/.ply/.usd*`) | `rigyd convert FILE` | 1 credit |

## Python SDK

```python
import rigyd
rigyd.configure()                                  # key from login/env

job = rigyd.convert(prompt="a wooden dining chair")
job.wait(on_progress=lambda j: print(j.status, j.stage, j.progress))
xml_path = job.download(fmt="mjcf")                # or "usd" / "all"
print(rigyd.account())                             # user + credit balance
```

### MuJoCo extra

```bash
pip install "rigyd[mujoco]"
```

```python
model = rigyd.load_model(prompt="a wooden chair")  # -> mujoco.MjModel, ready to mj_step
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
