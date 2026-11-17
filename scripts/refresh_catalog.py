"""Refresh what catalog/components.json copies from each source, and the day each copy was read.

ASM reaches no network (tests/test_standalone.py), so the catalog keeps copies:
- each repository's GitHub stars: repositories[].stars and starsCheckedOn;
- each item's description, word for word from its source: description, descriptionUrl (the page
  it was copied from) and descriptionCheckedOn. A skill's comes from its SKILL.md front matter,
  a plugin's from its plugin.json, and anything else's from its repository's GitHub description;
- each skill's skills.sh install count, when skills.sh lists the skill: installs and installsCheckedOn.

An item without a repository, such as a hook defined in the catalog, is its own source and is left alone.

Run from the repository root:  python scripts/refresh_catalog.py
GitHub allows 60 unauthenticated requests an hour; set GITHUB_TOKEN to raise that.
"""
import json
import os
import sys
import time
from datetime import date
from pathlib import Path, PurePosixPath
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from asm_app.store import _item_source, _repository_key, _skill_labels, _source_url  # noqa: E402

CATALOG = ROOT / "catalog" / "components.json"


def get(url):
    headers = {"User-Agent": "agent-stack-manager-catalog-refresh"}
    if url.startswith("https://api.github.com/"):
        headers["Accept"] = "application/vnd.github+json"
        if os.environ.get("GITHUB_TOKEN"):
            headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    for attempt in range(6):
        try:
            with urlopen(Request(url, headers=headers), timeout=30) as response:
                return response.read()
        except HTTPError as error:
            # skills.sh limits how fast it is asked; wait as long as it says, and try again.
            if error.code != 429 or attempt == 5:
                raise
            time.sleep(int(error.headers.get("Retry-After") or 0) or 5 * (attempt + 1))


def owner_repo(url):
    return urlsplit(url).path.strip("/").removesuffix(".git")


def raw(source, path):
    ref = quote(source.get("ref") or "HEAD", safe="")
    return get(f"https://raw.githubusercontent.com/{owner_repo(source['repositoryUrl'])}/{ref}/{quote(path)}")


def description(row, source, repository):
    """The item's own description and the page it is copied from."""
    path = source.get("path") or ""
    if row["kind"] == "skill":
        return _skill_labels(path, raw(source, path))[1], _source_url(source)
    if row["kind"] == "plugin":
        manifest = str(PurePosixPath(path, ".claude-plugin", "plugin.json"))
        text = json.loads(raw(source, manifest)).get("description")
        return (text or "").strip(), _source_url({**source, "path": manifest})
    return (repository.get("description") or "").strip(), source["repositoryUrl"]


def installs(row, source):
    """The skill's install count on skills.sh, or None when skills.sh does not list it."""
    repository = owner_repo(source["repositoryUrl"])
    names = {row["name"], PurePosixPath(source.get("path") or "").parent.name or repository.split("/")[-1]}
    for query in (row["name"], f"{repository.split('/')[-1]} {row['name']}"):
        time.sleep(1)
        found = json.loads(get("https://skills.sh/api/search?q=" + quote(query)))
        for entry in found.get("skills", []):
            if entry.get("source", "").casefold() == repository.casefold() and {entry.get("skillId"), entry.get("name")} & names:
                return entry["installs"]
    return None


def with_copies(row, fields):
    """The row with fresh copies in place of the old ones, kept together where its description was."""
    ordered = {}
    for key, value in row.items():
        if key == "description":
            ordered.update((field, copy) for field, copy in fields.items() if copy is not None)
        elif key not in fields:
            ordered[key] = value
    return ordered


def main():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    today = date.today().isoformat()
    repositories = {}
    for row in catalog["repositories"]:
        info = json.loads(get("https://api.github.com/repos/" + owner_repo(row["url"])))
        row["stars"], row["starsCheckedOn"] = info["stargazers_count"], today
        repositories[_repository_key(row["url"])] = info
    missing = []
    for index, row in enumerate(catalog["items"]):
        source = _item_source(row)
        if not source:
            continue
        text, url = description(row, source, repositories[_repository_key(source["repositoryUrl"])])
        # Word for word, on one line: a card shows it on one line and an export writes it as one YAML value.
        fields = {"description": " ".join(text.split()), "descriptionUrl": url, "descriptionCheckedOn": today,
                  "installs": None, "installsCheckedOn": None}
        if row["kind"] == "skill":
            count = installs(row, source)
            if count is None:
                missing.append(row["name"])
            else:
                fields.update(installs=count, installsCheckedOn=today)
        catalog["items"][index] = with_copies(row, fields)
    CATALOG.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"Refreshed {len(catalog['repositories'])} repositories and {len(catalog['items'])} items on {today}.")
    if missing:
        print("skills.sh does not list: " + ", ".join(missing))


if __name__ == "__main__":
    main()
