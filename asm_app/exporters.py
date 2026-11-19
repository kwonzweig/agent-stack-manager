"""Assess saved presets and expose the same artifacts through every caller."""

from collections.abc import Callable
from dataclasses import dataclass
import hashlib
import json
from typing import TYPE_CHECKING

from . import cc_switch, export_graph, paperclip

if TYPE_CHECKING:
    from .store import Store


@dataclass(frozen=True)
class Assessment:
    preview: dict
    artifact: dict | None
    reason: str = ""

    def require_artifact(self):
        if self.artifact is None:
            raise ValueError(self.reason)
        return self.artifact

    def revision(self):
        if self.artifact is None:
            return None
        return hashlib.sha256(json.dumps(self.artifact, sort_keys=True).encode()).hexdigest()


def _assess_paperclip(package, store):
    report = paperclip.convert(package, root=store.root, store=store)
    preview = {key: value for key, value in report.items() if key != "files"}
    if package["kind"] == "preset":
        return Assessment(preview, report)
    reason = "Paperclip needs a single agent preset. Include this stack in a preset to export it."
    preview["items"] = [
        {**row, "target": None, "conversion": {"status": "unconverted", "cause": "not-in-format", "reason": reason}}
        if row["conversion"]["status"] == "converted" else row
        for row in report["items"]
    ]
    preview["summary"] = {"total": len(report["items"]), "converted": 0, "unconverted": len(report["items"])}
    return Assessment(preview, None, reason)


def _assess_cc_switch(package, store):
    packages, members = export_graph.expand(package, store)
    native, inventory = [], []
    for member in members:
        row = member.component
        if row.get("managedByInventory"):
            continue
        unsupported = row["kind"] in cc_switch.UNSUPPORTED_KINDS
        result = {field: row[field] for field in ("id", "name", "kind")}
        if member.owner != package["id"]:
            result.update(id=f"{member.owner}/{row['id']}", originPackage=export_graph.origin(packages[member.owner]))
        if member.error:
            status, reason = "unsupported", member.error
        elif member.dependency:
            status, reason = "manual", "The review lists this stack's members separately."
        elif unsupported:
            status, reason = "unsupported", cc_switch.UNSUPPORTED_REASON
        else:
            status, reason = "manual", "No Codex or Claude Code selection is recorded for this APM component."
        native.append({**result, "status": status, "reason": reason})

    identifiers = {item["id"] for item in package.get("appInventory", [])}
    for owner, current in packages.items():
        observations = current.get("appInventory", [])
        if owner == package["id"]:
            inventory.extend(observations)
            continue

        scoped_ids = {}
        for item in observations:
            identifier = f"{owner}/{item['id']}"
            while identifier in identifiers:
                identifier = f"stack/{identifier}"
            identifiers.add(identifier)
            scoped_ids[item["id"]] = identifier
        for item in observations:
            apps = {}
            for app, state in item["apps"].items():
                parent_id = state.get("parentId")
                apps[app] = {**state, "parentId": scoped_ids.get(parent_id)} if isinstance(parent_id, str) else state
            inventory.append({**item, "apps": apps, "id": scoped_ids[item["id"]],
                              "originPackage": export_graph.origin(current)})
    if not inventory:
        return Assessment({"items": native}, None, "This preset has no app inventory.")
    review = cc_switch.convert({**package, "appInventory": inventory})
    if native:
        review["unassignedItems"] = native
    return Assessment({"items": review["items"] + native}, review)


@dataclass(frozen=True)
class Exporter:
    id: str
    name: str
    download: str
    assess: Callable[[dict, "Store"], Assessment]
    content_type: str
    file_suffix: str
    encode: Callable[[dict], dict | bytes] = dict

    def describe(self, package, store):
        assessment = self.assess(package, store)
        result = {"id": self.id, "name": self.name, "available": assessment.artifact is not None,
                  "reason": assessment.reason, "preview": assessment.preview}
        if result["available"]:
            result["download"] = f"{self.download}?revision={assessment.revision()}"
            result["filename"] = package["id"] + self.file_suffix
        return result

    def produce(self, package, store, revision=None):
        assessment = self.assess(package, store)
        if revision is not None and revision != assessment.revision():
            from .store import StoreError
            raise StoreError("The saved export changed. Reload the preview before downloading.", 409)
        artifact = assessment.require_artifact()
        return self.encode(artifact), self.content_type, package["id"] + self.file_suffix


EXPORTERS = {
    exporter.id: exporter for exporter in (
        Exporter("paperclip", "Paperclip", "/paperclip/export", _assess_paperclip,
                 "application/zip", "-paperclip.zip", paperclip.export_package),
        Exporter("ccswitch", "CC Switch", "/cc-switch", _assess_cc_switch,
                 "application/json", "-cc-switch.json"),
    )
}
DOWNLOADS = {exporter.download: exporter for exporter in EXPORTERS.values()}


def choices(package, store):
    return {"targets": [exporter.describe(package, store) for exporter in EXPORTERS.values()]}
