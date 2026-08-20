#!/usr/bin/env python3
"""Convert a 3D model to a SimReady MuJoCo asset and open it in the viewer.

    pip install "rigyd[mujoco]"
    rigyd login                       # or: export RIGYD_API_KEY=rgyd_live_xxx
    python examples/quickstart.py chair.glb
"""

import sys

import mujoco
import mujoco.viewer

import rigyd


def main():
    source = sys.argv[1] if len(sys.argv) > 1 else "chair.glb"
    rigyd.configure()

    print(f"Converting: {source!r}")
    model = rigyd.load_model(
        file=source,
        on_progress=lambda j: print(f"  {j.status} - {j.stage} - {j.progress}%"),
    )
    print(f"Loaded: {model.ngeom} geoms, {model.nbody} bodies")

    data = mujoco.MjData(model)
    mujoco.viewer.launch(model, data)


if __name__ == "__main__":
    main()
