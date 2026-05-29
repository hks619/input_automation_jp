"""Value matching + geography resolution.

Two responsibilities:
    5A. Map cedent raw attribute values → valid RMS scheme codes
        (occupancy, construction, secondary modifiers).
    5B. Resolve geography (postal → CRESTA / prefecture).

The functions here are pure (no Streamlit dependency). The UI in
pages/03_geoprocess.py drives the interactive editing and persistence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import yaml
from rapidfuzz import fuzz, process


CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
MAPPINGS_DIR = CONFIG_DIR / "mappings"


# --------------------------------------------------------------------- loaders

def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_occ_codes() -> List[Dict]:
    return load_yaml(CONFIG_DIR / "occ_scheme.yaml").get("schemes", [])


def load_bldg_codes() -> List[Dict]:
    return load_yaml(CONFIG_DIR / "bldg_scheme.yaml").get("schemes", [])


def load_secondary_modifier_config() -> Dict:
    return load_yaml(CONFIG_DIR / "secondary_modifiers.yaml")


def load_postal_lookup() -> Dict:
    """Return the {prefix: {prefecture, cresta}} dict."""
    return load_yaml(CONFIG_DIR / "japan_postal_to_cresta.yaml").get("lookup", {})


def load_defaults() -> Dict:
    return load_yaml(CONFIG_DIR / "defaults.yaml")


def load_cedent_mapping(cedent_id: str) -> Dict:
    """Per-cedent confirmed mappings; pre-fills the UI on renewal."""
    return load_yaml(MAPPINGS_DIR / f"{cedent_id}.yaml")


def save_cedent_mapping(cedent_id: str, mapping: Dict) -> None:
    MAPPINGS_DIR.mkdir(parents=True, exist_ok=True)
    with (MAPPINGS_DIR / f"{cedent_id}.yaml").open("w", encoding="utf-8") as f:
        yaml.safe_dump(mapping, f, sort_keys=False, allow_unicode=True)


# ------------------------------------------------------------- value matching

@dataclass
class Suggestion:
    target: str       # the code (e.g. "311")
    description: str
    score: int        # 0..100 fuzzy match


def suggest_occ_codes(raw_value: str, codes: Iterable[Dict], top_k: int = 3) -> List[Suggestion]:
    """Return up to `top_k` best fuzzy matches for a raw cedent occupancy label."""
    pool = {f"{c.get('type','')} {c.get('description','')}": c for c in codes}
    if not pool:
        return []
    hits = process.extract(raw_value, list(pool.keys()), scorer=fuzz.WRatio, limit=top_k)
    out: List[Suggestion] = []
    for label, score, _ in hits:
        c = pool[label]
        out.append(Suggestion(target=str(c.get("type", "")),
                              description=str(c.get("description", "")),
                              score=int(score)))
    return out


def suggest_bldg_codes(raw_value: str, codes: Iterable[Dict], top_k: int = 3) -> List[Suggestion]:
    pool = {f"{c.get('class','')} {c.get('description','')}": c for c in codes}
    if not pool:
        return []
    hits = process.extract(raw_value, list(pool.keys()), scorer=fuzz.WRatio, limit=top_k)
    out: List[Suggestion] = []
    for label, score, _ in hits:
        c = pool[label]
        out.append(Suggestion(target=str(c.get("class", "")),
                              description=str(c.get("description", "")),
                              score=int(score)))
    return out


def unmapped_values(parsed_sheets: Dict, mapping: Dict) -> Dict[str, List[str]]:
    """Return raw values that are not yet mapped to RMS codes.

    Looks at:
        Occ.OCC      → mapping["occ"]
        Cons.Construction → mapping["cons"]
    """
    out: Dict[str, List[str]] = {"occ": [], "cons": []}
    occ_map = mapping.get("occ", {})
    cons_map = mapping.get("cons", {})
    if "Occ" in parsed_sheets:
        for v in parsed_sheets["Occ"].get("OCC", []):
            sv = str(v)
            if sv and sv != "nan" and sv not in occ_map:
                out["occ"].append(sv)
    if "Cons" in parsed_sheets:
        for v in parsed_sheets["Cons"].get("Construction", []):
            sv = str(v)
            if sv and sv != "nan" and sv not in cons_map:
                out["cons"].append(sv)
    out["occ"] = sorted(set(out["occ"]))
    out["cons"] = sorted(set(out["cons"]))
    return out


# -------------------------------------------------------- geography resolution

def resolve_postal(postal_code: str, lookup: Dict) -> Optional[Dict]:
    """Return {prefecture, cresta} for a Japan postal code, or None.

    Looks up the first 3 digits (Japan postal codes are "NNN-NNNN").
    """
    if not postal_code:
        return None
    prefix = str(postal_code).strip().split("-")[0][:3]
    return lookup.get(prefix)


def annotate_geography(exp_df, lookup: Dict):
    """Add resolved prefecture / cresta columns to a copy of EXP_EQ for display."""
    df = exp_df.copy()
    df["_resolved_prefecture"] = df["POSTCODE"].astype(str).map(
        lambda p: (resolve_postal(p, lookup) or {}).get("prefecture", "")
    )
    df["_resolved_cresta"] = df["POSTCODE"].astype(str).map(
        lambda p: (resolve_postal(p, lookup) or {}).get("cresta", "")
    )
    df["_postal_resolved"] = df["_resolved_prefecture"] != ""
    return df
