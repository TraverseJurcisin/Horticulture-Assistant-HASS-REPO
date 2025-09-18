#!/usr/bin/env python3

"""Migrate fertilizer dataset to the 2025-09-V3e schema."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable
from copy import deepcopy
from pathlib import Path
from typing import Any

SCHEMA_META: dict[str, str] = {"id": "fertilizer", "version": "2025-09-V3e"}

INDEX_SCHEMA: dict[str, str] = {"id": "fertilizer_index", "version": "2025-09-V3e"}

ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = ROOT / "custom_components" / "horticulture_assistant" / "data" / "fertilizers"

DETAIL_DIR = DATA_DIR / "detail"

INDEX_DIR = DATA_DIR / "index_sharded"


NPK_MAP_V1: dict[str, str] = {
    "Total Nitrogen (N)": "N_pct",
    "Available Phosphoric Acid (P2O5)": "P2O5_pct",
    "Soluble Potash (K2O)": "K2O_pct",
}

MACRO_MAP_V1: dict[str, str] = {
    "Calcium (Ca)": "Ca",
    "Magnesium (Mg)": "Mg",
    "Sulfur (S)": "S",
}

MICRO_MAP_V1: dict[str, str] = {
    "Iron (Fe)": "Fe",
    "Manganese (Mn)": "Mn",
    "Zinc (Zn)": "Zn",
    "Copper (Cu)": "Cu",
    "Boron (B)": "B",
    "Molybdenum (Mo)": "Mo",
    "Chlorine (Cl)": "Cl",
    "Nickel (Ni)": "Ni",
}

HEAVY_METAL_SYMBOLS_V1: dict[str, str] = {
    "Arsenic": "As",
    "Cadmium": "Cd",
    "Cobalt": "Co",
    "Mercury": "Hg",
    "Molybdenum": "Mo",
    "Nickel": "Ni",
    "Lead": "Pb",
    "Selenium": "Se",
    "Zinc": "Zn",
}

HEAVY_METALS_V6: Iterable[str] = ("As", "Cd", "Co", "Hg", "Mo", "Ni", "Pb", "Se", "Zn")


def parse_heavy_metal_value(raw: Any) -> tuple[Any, str | None]:
    if raw is None:
        return None, None

    text = str(raw).strip()

    if not text:
        return None, None

    qualifier_char = text[0] if text[0] in "<>=" else "="

    number_text = text[1:] if qualifier_char in "<=>" else text

    try:
        value = float(number_text)

    except ValueError:
        return None, None

    qualifier: str | None = None

    if qualifier_char == "=":
        qualifier = "eq"

    elif qualifier_char == "<":
        qualifier = "lt_dl"

    elif qualifier_char == ">":
        qualifier = "gt_ul"

    return value, qualifier


def build_metadata_v1(payload: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(payload.get("metadata") or {})

    legacy = dict(metadata.get("legacy") or {})

    schema_version = payload.get("schema_version")

    if schema_version is not None:
        legacy["schema_version"] = schema_version

    source_wsda = payload.get("source_wsda_record") or {}

    if source_wsda:
        legacy["wsda_record"] = source_wsda

        wsda_no = source_wsda.get("wsda_product_number")

        if wsda_no and not metadata.get("wsda_product_number"):
            metadata["wsda_product_number"] = wsda_no

        legacy["waste_derived_fertilizer"] = source_wsda.get("waste_derived_fertilizer")

        legacy["micronutrient_fertilizer"] = source_wsda.get("micronutrient_fertilizer")

    for key in ("physicochemical", "commerce"):
        if payload.get(key) is not None:
            legacy[key] = payload[key]

    metadata["legacy"] = legacy

    return metadata


def build_product_v1(payload: dict[str, Any]) -> dict[str, Any]:
    source_wsda = payload.get("source_wsda_record") or {}

    metadata = payload.get("metadata") or {}

    company_info = source_wsda.get("company_info") or {}

    manufacturer_name = company_info.get("company")

    name = source_wsda.get("product_name") or metadata.get("label_name") or payload.get("product_id")

    brand = metadata.get("registrant") or manufacturer_name

    aliases = {metadata.get("label_name"), source_wsda.get("product_name")}

    aliases.discard(None)

    aliases.discard(name)

    product: dict[str, Any] = {"name": name}

    if brand:
        product["brand"] = brand

    if aliases:
        product["aliases"] = sorted(aliases)

    if manufacturer_name:
        product["manufacturer"] = {"name": manufacturer_name}

    return product


def build_composition_v1(payload: dict[str, Any]) -> dict[str, Any]:
    composition: dict[str, Any] = {}

    source_composition = payload.get("composition") or {}

    ga = source_composition.get("guaranteed_analysis") or {}

    meta = payload.get("metadata") or {}

    npk: dict[str, Any] = {"basis": "oxide"}

    for legacy_key, new_key in NPK_MAP_V1.items():
        value = ga.get(legacy_key)

        if value is not None:
            npk[new_key] = float(value)

    composition["npk"] = npk

    macros: dict[str, Any] = {}

    for legacy_key, new_key in MACRO_MAP_V1.items():
        value = ga.get(legacy_key)

        if value is not None:
            macros[new_key] = float(value)

    if macros:
        composition["macros_pct"] = macros

    micros: dict[str, Any] = {}

    for legacy_key, new_key in MICRO_MAP_V1.items():
        value = ga.get(legacy_key)

        if value is not None:
            micros[new_key] = float(value)

    if micros:
        composition["micros_pct"] = micros

    heavy_metals_src = source_composition.get("heavy_metals") or {}

    if heavy_metals_src:
        heavy_metals: dict[str, Any] = {"basis": "as_sold"}

        results: dict[str, Any] = {}

        qualifiers: dict[str, str] = {}

        detection_limits: dict[str, Any] = {}

        typical: dict[str, Any] = {}

        for legacy_name, raw_value in heavy_metals_src.items():
            symbol = HEAVY_METAL_SYMBOLS_V1.get(legacy_name)

            if not symbol:
                continue

            value, qualifier = parse_heavy_metal_value(raw_value)

            if value is not None:
                results[symbol] = value

                if qualifier in (None, "eq"):
                    typical[symbol] = value

            if qualifier:
                qualifiers[symbol] = qualifier

                if qualifier == "lt_dl" and value is not None:
                    detection_limits[symbol] = value

        if results or detection_limits:
            date = meta.get("detail_updated_at") or meta.get("first_seen")

            if date and len(str(date)) == 10:
                date = f"{date}T00:00:00Z"

            if not date:
                date = "1970-01-01T00:00:00Z"

            sample: dict[str, Any] = {
                "sample_id": f"{payload.get('product_id')}-wsda",
                "date_utc": date,
                "basis": "as_sold",
                "results_ppm": results,
            }

            if detection_limits:
                sample["detection_limits_ppm"] = detection_limits

            if qualifiers:
                sample["qualifiers"] = qualifiers

            heavy_metals["samples"] = [sample]

        if typical:
            heavy_metals["typical_ppm"] = typical

        if heavy_metals.get("samples"):
            composition["heavy_metals"] = heavy_metals

    return composition


def transform_v1(payload: dict[str, Any]) -> dict[str, Any]:
    record_id = payload.get("product_id")

    record: dict[str, Any] = {
        "schema": SCHEMA_META,
        "id": record_id,
        "metadata": build_metadata_v1(payload),
        "product": build_product_v1(payload),
        "composition": build_composition_v1(payload),
    }

    chemistry = payload.get("physicochemical") or {}

    density = chemistry.get("density_kg_per_l")

    if density is not None:
        record.setdefault("chemistry", {})["density_g_ml"] = float(density)

    return record


def build_metadata_v6(payload: dict[str, Any], product: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}

    registrant = product.get("brand") or product.get("manufacturer")

    if registrant:
        metadata["registrant"] = registrant

    if product.get("label_name"):
        metadata["label_name"] = product["label_name"]

    wsda_no = (product.get("registration_numbers") or {}).get("WSDA")

    if wsda_no:
        metadata["wsda_reg_no"] = wsda_no

    last_updated = product.get("last_updated")

    if last_updated:
        metadata["detail_updated_at"] = last_updated

    metadata["legacy"] = payload

    return metadata


def build_product_v6(product: dict[str, Any]) -> dict[str, Any]:
    name = product.get("label_name") or product.get("product_id") or ""

    product_block: dict[str, Any] = {"name": name}

    if product.get("brand"):
        product_block["brand"] = product["brand"]

    manufacturer = product.get("manufacturer")

    if manufacturer:
        product_block["manufacturer"] = {"name": manufacturer}

    return product_block


def build_composition_v6(product: dict[str, Any]) -> dict[str, Any]:
    composition: dict[str, Any] = {}

    nutrients = product.get("nutrients") or {}

    npk: dict[str, Any] = {"basis": "elemental"}

    if nutrients.get("N_total") is not None:
        npk["N_pct"] = float(nutrients["N_total"])

    if nutrients.get("P") is not None:
        npk["P_pct"] = float(nutrients["P"])

    if nutrients.get("K") is not None:
        npk["K_pct"] = float(nutrients["K"])

    composition["npk"] = npk

    macros: dict[str, Any] = {}

    for source_key, target_key in (("Ca", "Ca"), ("Mg", "Mg"), ("S", "S")):
        value = nutrients.get(source_key)

        if value is not None:
            macros[target_key] = float(value)

    if macros:
        composition["macros_pct"] = macros

    micros: dict[str, Any] = {}

    for source_key, target_key in (
        ("Fe", "Fe"),
        ("Mn", "Mn"),
        ("Zn", "Zn"),
        ("Cu", "Cu"),
        ("B", "B"),
        ("Mo", "Mo"),
        ("Cl", "Cl"),
        ("Ni", "Ni"),
    ):
        value = nutrients.get(source_key)
        if value is not None:
            micros[target_key] = float(value)

    if micros:
        composition["micros_pct"] = micros

    heavy = product.get("heavy_metals") or {}

    heavy_metals: dict[str, Any] = {}

    results: dict[str, Any] = {}

    detection_limits: dict[str, Any] = {}

    qualifiers: dict[str, str] = {}

    for symbol in HEAVY_METALS_V6:
        entry = heavy.get(symbol) or {}

        value = entry.get("value")

        det_limit = entry.get("detection_limit")

        if value is not None:
            results[symbol] = float(value)

            qualifiers[symbol] = "eq"

        elif det_limit is not None:
            detection_limits[symbol] = float(det_limit)

            qualifiers[symbol] = "lt_dl"

    if results or detection_limits:
        sample: dict[str, Any] = {
            "sample_id": f"{product.get('product_id', 'unknown')}-v6",
            "date_utc": product.get("last_updated") or "1970-01-01T00:00:00Z",
            "basis": "as_sold",
            "results_ppm": results,
        }

        if detection_limits:
            sample["detection_limits_ppm"] = detection_limits

        if qualifiers:
            sample["qualifiers"] = qualifiers

        heavy_metals["basis"] = "as_sold"

        heavy_metals["samples"] = [sample]

    if results:
        heavy_metals["typical_ppm"] = results

    if heavy_metals:
        composition["heavy_metals"] = heavy_metals

    return composition


def transform_v6(payload: dict[str, Any]) -> dict[str, Any]:
    products = payload.get("products") or []

    if not products:
        raise ValueError("v6 payload missing products")

    product = dict(products[0])

    record_id = product.get("product_id") or payload.get("product_id")

    record: dict[str, Any] = {
        "schema": SCHEMA_META,
        "id": record_id,
        "metadata": build_metadata_v6(payload, product),
        "product": build_product_v6(product),
        "composition": build_composition_v6(product),
    }

    density = product.get("density_kg_l")

    if density is not None:
        record.setdefault("chemistry", {})["density_g_ml"] = float(density)

    return record


def transform_record(payload: dict[str, Any]) -> dict[str, Any]:
    schema_block = payload.get("schema")

    if (
        isinstance(schema_block, dict)
        and schema_block.get("id") == SCHEMA_META["id"]
        and schema_block.get("version") == SCHEMA_META["version"]
    ):
        return payload

    version = payload.get("schema_version")

    if version == "v6.0.0":
        return transform_v6(payload)

    return transform_v1(payload)


def migrate_detail_files() -> int:
    if not DETAIL_DIR.exists():
        raise SystemExit(f"Detail directory not found: {DETAIL_DIR}")

    count = 0

    for path in sorted(DETAIL_DIR.rglob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))

        updated = transform_record(data)

        text = json.dumps(updated, indent=2)

        if not text.endswith("\n"):
            text += "\n"

        path.write_text(text, encoding="utf-8")

        count += 1

    return count


def _composition_summary(composition: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}

    for key in ("npk", "macros_pct", "micros_pct"):
        value = composition.get(key)

        if value:
            summary[key] = deepcopy(value)

    return summary


def build_index_entry(detail: dict[str, Any]) -> dict[str, Any]:
    product = deepcopy(detail.get("product") or {})

    metadata = detail.get("metadata") or {}

    composition = detail.get("composition") or {}

    entry: dict[str, Any] = {
        "schema": INDEX_SCHEMA,
        "id": detail.get("id"),
        "product": product,
        "metadata": {},
        "composition": _composition_summary(composition),
    }

    meta_summary = {}

    for key in ("wsda_reg_no", "formulation", "first_seen", "detail_updated_at"):
        value = metadata.get(key)

        if value is not None:
            meta_summary[key] = value

    if meta_summary:
        entry["metadata"] = meta_summary

    chemistry = detail.get("chemistry")

    if chemistry:
        entry["chemistry"] = deepcopy(chemistry)

    return entry


def shard_name(entry: dict[str, Any]) -> str:
    product = entry.get("product") or {}

    name = str(product.get("name") or "").strip()

    first = name[:1].upper()

    if not first or not first.isalnum():
        first = "_"

    return f"idx_{first}.jsonl"


def rebuild_index() -> int:
    if not INDEX_DIR.exists():
        INDEX_DIR.mkdir(parents=True, exist_ok=True)

    entries_by_shard: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for path in sorted(DETAIL_DIR.rglob("*.json")):
        detail = json.loads(path.read_text(encoding="utf-8"))

        entry = build_index_entry(detail)

        shard = shard_name(entry)

        entries_by_shard[shard].append(entry)

    for shard_entries in entries_by_shard.values():
        shard_entries.sort(key=lambda e: ((e.get("product") or {}).get("name") or "", e.get("id") or ""))

    for existing in INDEX_DIR.glob("idx_*.jsonl"):
        existing.unlink()

    total = 0

    for shard, entries in entries_by_shard.items():
        path = INDEX_DIR / shard

        with path.open("w", encoding="utf-8") as handle:
            for entry in entries:
                handle.write(json.dumps(entry, separators=(",", ":")) + "\n")

                total += 1

    return total


def main() -> None:
    detail_count = migrate_detail_files()

    index_count = rebuild_index()

    print(f"Updated {detail_count} fertilizer detail records and built index with {index_count} entries")


if __name__ == "__main__":
    main()
