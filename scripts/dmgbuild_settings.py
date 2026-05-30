"""Minimal dmgbuild settings — drag-app-to-Applications layout.

Invoked by build_dist.py on macOS via:
    dmgbuild -s scripts/dmgbuild_settings.py <volume_name> <output.dmg>

dmgbuild executes this file with `appname` set to the volume name (first
positional). We rely on the convention that the matching .app bundle sits
at dist/<appname>.app, which is what PyInstaller produces with --name <appname>.
"""
import os

application = os.path.join("dist", f"{appname}.app")  # noqa: F821 — appname injected by dmgbuild

format = "UDZO"  # compressed read-only
files = [application]
symlinks = {"Applications": "/Applications"}
icon_locations = {
    os.path.basename(application): (140, 120),
    "Applications": (500, 120),
}
window_rect = ((100, 100), (640, 280))
icon_size = 96
text_size = 14
