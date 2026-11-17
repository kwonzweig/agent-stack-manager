# Design policy

How the dashboard shows things. Follow these rules when you add or change a page, card or dialog. A change that breaks one either fixes the page or changes the rule here in the same pull request.

## A detail page shows at least what its card shows

A page about one item shows every property its card or list row showed, in the same form, and may add more. Someone who opens an item keeps what they saw a click before.

In the Catalog, `frontend/src/catalog/ItemProperties.tsx` renders the kind, the component count, the repository, the GitHub stars and the skills.sh installs on both the card and the item page. A new card property goes in that component, not on the card alone.

## One look for one kind of label

A label that names the same thing looks the same on every page. Component kinds (Instruction, Skill, MCP, Hook, Plugin, Preset, Stack) use `KindBadge` from `frontend/src/components/ComponentUI.tsx` on the Presets pages, in the Catalog, on item pages and in the Paperclip export report.

## A card's properties sit at its bottom

Cards in one grid row share a height. The title and description sit at the top of a card and its property row at the bottom, so the properties line up across the row however long a title is.

## A page opened from a list has a way back

A page opened from a list has a back button at its top left that names where it returns to, such as "Catalog" or the preset's name. A Catalog item's page has its own address, the browser's Back button does the same as the back button, and returning keeps the list's filters and scroll position.

## Text from a source is the source's own

A description, star count or install count that comes from a component's source is copied from it, never written or summarized by hand, and shows the day it was read. `scripts/refresh_catalog.py` makes these copies; [docs/api-contract.md](../docs/api-contract.md) lists the fields.
