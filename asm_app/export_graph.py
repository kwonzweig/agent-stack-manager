"""Resolve the saved APM packages both exporters account for."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Member:
    ancestry: tuple[str, ...]
    component: dict
    dependency: str | None = None
    error: str | None = None

    @property
    def owner(self):
        return self.ancestry[-1]


def expand(package, store, *, include_empty_instruction=False):
    packages, members = {}, []

    def visit(current, ancestry):
        packages[current["id"]] = current
        components = current["components"]
        primary = len(ancestry) == 1 and include_empty_instruction
        if primary and not any(component["id"] == "instruction" for component in components):
            components = [{"id": "instruction", "name": "Instruction", "kind": "instruction"}, *components]
        for component in components:
            if component["id"] == "instruction" and not (primary or current["instruction"].strip()):
                continue
            if component["kind"] != "package":
                members.append(Member(ancestry, component))
                continue

            dependency = (component.get("configuration") or {}).get("packageId")
            child = error = None
            if not dependency:
                error = "The APM dependency has no local stack to expand."
            elif dependency in ancestry:
                error = f"Stack dependency cycle at {dependency}."
            elif dependency not in packages:
                try:
                    child = store.get(dependency)
                except (ValueError, LookupError, OSError):
                    error = f"Local stack {dependency} could not be read."
            members.append(Member(ancestry, component, dependency, error))
            if child is not None:
                visit(child, (*ancestry, dependency))

    visit(package, (package["id"],))
    return packages, members


def origin(package):
    return {"id": package["id"], "title": package.get("title") or package["id"]}
