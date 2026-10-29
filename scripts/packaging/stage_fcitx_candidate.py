"""Explicitly stage or deactivate an experimental Fcitx user addon.

Neither command refreshes, stops, starts, or changes the running Fcitx process.
Deactivation keeps the native library because an existing process may use it.
"""

import argparse
import platform
import re
import subprocess
from pathlib import Path

from inkecho.platform.fcitx5_staging import StagingError, deactivate, stage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("stage", "deactivate"))
    parser.add_argument("--data-home", required=True, type=Path)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--digest")
    parser.add_argument("--fcitx-version")
    args = parser.parse_args()
    if args.action == "stage":
        if args.candidate is None:
            parser.error("stage requires --candidate")
        try:
            version = subprocess.run(
                ["fcitx5", "--version"],
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
            )
            matches = re.findall(r"\b\d+\.\d+\.\d+\b", version.stdout)
            if len(matches) != 1:
                raise StagingError("fcitx_version_unavailable")
            release = platform.freedesktop_os_release()
            digest = stage(
                args.candidate,
                args.data_home,
                os_id=release.get("ID", ""),
                os_version=release.get("VERSION_ID", ""),
                architecture=platform.machine(),
                fcitx_version=matches[0],
            )
        except (OSError, subprocess.SubprocessError, StagingError, ValueError) as error:
            parser.exit(1, f"Staging failed: {type(error).__name__}: {error}\n")
        print(f"Staged: {digest} (Fcitx {matches[0]}). No refresh was performed.")
    else:
        if not args.digest or not args.fcitx_version:
            parser.error("deactivate requires --digest and --fcitx-version")
        try:
            deactivate(
                args.data_home, digest=args.digest, fcitx_version=args.fcitx_version
            )
        except (OSError, StagingError, ValueError) as error:
            parser.exit(1, f"Deactivation failed: {type(error).__name__}: {error}\n")
        print(
            "Description removed. A running Fcitx may still use the retained library."
        )


if __name__ == "__main__":
    main()
