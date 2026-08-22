#!/usr/bin/env python3
"""Compose an articulated SimReady asset from intent and download its USD."""

import rigyd


def main():
    rigyd.configure()
    composition = rigyd.compose(
        prompt="A compact desktop stapler with a plastic shell",
        robot_task="Press the upper arm to staple paper",
        asset_class="articulated",
        auto_submit=True,
    )
    composition.wait(
        on_progress=lambda item: print(
            f"{item.status} - {item.stage} - {item.progress}%"))
    print(composition.conversion_job().download(fmt="usd"))


if __name__ == "__main__":
    main()
