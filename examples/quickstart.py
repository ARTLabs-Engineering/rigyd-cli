#!/usr/bin/env python3
"""Generate a SimReady MuJoCo asset from a prompt and open it in the viewer.

    pip install "rigyd[mujoco]"
    rigyd login                       # or: export RIGYD_API_KEY=rgyd_live_xxx
    python examples/quickstart.py "a wooden dining chair"
"""

import sys

import mujoco
import mujoco.viewer

import rigyd


def main():
    prompt = sys.argv[1] if len(sys.argv) > 1 else "a wooden dining chair"
    rigyd.configure()

    print(f"Converting: {prompt!r}")
    model = rigyd.load_model(
        prompt=prompt,
        on_progress=lambda j: print(f"  {j.status} - {j.stage} - {j.progress}%"),
    )
    print(f"Loaded: {model.ngeom} geoms, {model.nbody} bodies")

    data = mujoco.MjData(model)
    mujoco.viewer.launch(model, data)


if __name__ == "__main__":
    main()
