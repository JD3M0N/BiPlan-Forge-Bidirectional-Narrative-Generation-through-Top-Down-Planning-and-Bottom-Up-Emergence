"""Load and validate the ordered narrative catalog distributed with the package."""

import hashlib
import json
from importlib.resources import files

from .catalog_types import PlotSkeleton


def load_catalog() -> tuple[str, str, tuple[PlotSkeleton, ...]]:
    """Validate packaged entries and their directed editorial references."""
    raw = files(__package__).joinpath("data/skeletons.json").read_bytes()
    document = json.loads(raw)
    entries = tuple(PlotSkeleton.model_validate(row) for row in document["skeletons"])
    ids = {entry.id for entry in entries}
    if not entries or len(ids) != len(entries):
        raise ValueError("plot skeleton ids must be unique and the catalog nonempty")
    for entry in entries:
        for values in (entry.layers, entry.pairs_well_with, entry.tensions_with):
            if len(values) != len(set(values)):
                raise ValueError(f"skeleton {entry.id} contains duplicate references or layers")
        for reference in (*entry.pairs_well_with, *entry.tensions_with):
            if reference not in ids or reference == entry.id:
                raise ValueError(f"skeleton {entry.id} has invalid reference {reference}")
        if set(entry.pairs_well_with) & set(entry.tensions_with):
            raise ValueError(f"skeleton {entry.id} has contradictory editorial references")
    return str(document["version"]), hashlib.sha256(raw).hexdigest(), entries


CATALOG_VERSION, CATALOG_HASH, PLOT_SKELETONS = load_catalog()
SKELETONS_BY_ID = {entry.id: entry for entry in PLOT_SKELETONS}
