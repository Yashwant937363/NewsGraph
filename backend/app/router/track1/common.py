from collections import OrderedDict
from typing import List, Dict, Any, Optional

LABEL_COLORS = {
    "Event": "#3B82F6",
    "Country": "#10B981",
    "Company": "#F59E0B",
    "Industry": "#8B5CF6",
    "Organization": "#06B6D4",
    "Location": "#EC4899",
    "Person": "#F43F5E",
    "Article": "#64748B",
    "Story": "#A855F7",
}


def _get_color(labels: List[str]) -> str:
    """Returns the visual hex color for a node or edge based on its labels."""
    for lbl in labels:
        if lbl in LABEL_COLORS:
            return LABEL_COLORS[lbl]
    return "#94A3B8"


def _clean_props(props: Optional[Dict[str, Any] | OrderedDict]) -> Dict[str, Any]:
    """Strips internal vector embeddings and centroids from node and relationship properties."""
    if not props:
        return {}
    cleaned = dict(props)
    cleaned.pop("centroid", None)
    cleaned.pop("embedding", None)
    return cleaned
