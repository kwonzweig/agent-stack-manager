"""Check the downloaded archives from the disposable bulk export browser test."""
import sys
from pathlib import Path
from zipfile import ZipFile

import yaml


fixture, mixed, curated = sys.argv[1:]
root = Path(fixture)
for preset, skill in ((mixed, "native-mixed-keep"), (curated, "native-keep")):
    with ZipFile(root / f"{preset}-paperclip.zip") as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    output = root / "exports" / "paperclip" / preset
    assert files == {part.relative_to(output).as_posix(): part.read_bytes()
                     for part in output.rglob("*") if part.is_file()}, f"{preset} ZIP differs from its generated files"
    instruction = f"agents/{preset}/AGENTS.md"
    assert set(files) == {".paperclip.yaml", "COMPANY.md", instruction, f"skills/{skill}/SKILL.md"}, sorted(files)
    _, frontmatter, body = files[instruction].decode().split("---", 2)
    assert yaml.safe_load(frontmatter)["skills"] == [skill]
    assert body.strip() == f"Synthetic primary instruction for {preset}."
    package = yaml.safe_load(files[".paperclip.yaml"])
    assert package["agents"][preset]["runtime"]["heartbeat"]["enabled"] is False
