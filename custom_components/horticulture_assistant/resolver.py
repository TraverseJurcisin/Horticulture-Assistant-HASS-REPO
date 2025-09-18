from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.core import HomeAssistant

from .const import OPB_FIELD_MAP, VARIABLE_SPECS
from .profile.schema import VariableValue

UTC = getattr(datetime, "UTC", timezone.utc)  # type: ignore[attr-defined]  # noqa: UP017


@dataclass
class ResolveResult:
    value: float | None
    mode: str
    detail: str
    confidence: float | None = None


class PreferenceResolver:
    """Resolves per-variable values from manual/clone/opb/ai with TTL + citations."""

    def __init__(self, hass: HomeAssistant):
        self.hass = hass

    async def resolve_profile(self, entry, profile_id: str) -> dict[str, Any]:
        prof = entry.options.get("profiles", {}).get(profile_id, {})
        sources = dict(prof.get("sources", {}))
        thresholds = dict(prof.get("thresholds", {}))
        citations = dict(prof.get("citations", {}))
        changed = False

        for key, *_ in VARIABLE_SPECS:
            res = await self._resolve_variable(entry, profile_id, key, sources.get(key), thresholds, entry.options)
            if res is None:
                continue
            if thresholds.get(key) != res.value:
                thresholds[key] = res.value
                citations[key] = {
                    "mode": res.mode,
                    "ts": datetime.now(UTC).isoformat(),
                    "source_detail": res.detail,
                }
                changed = True

        if changed:
            # Persist back to options
            opts = dict(entry.options)
            prof = dict(opts.get("profiles", {}).get(profile_id, {}))
            prof["thresholds"] = thresholds
            prof["citations"] = citations
            prof["needs_resolution"] = False
            prof["last_resolved"] = datetime.now(UTC).isoformat()
            allp = dict(opts.get("profiles", {}))
            allp[profile_id] = prof
            opts["profiles"] = allp
            self.hass.config_entries.async_update_entry(entry, options=opts)

        return thresholds

    async def _resolve_variable(
        self,
        entry,
        profile_id: str,
        key: str,
        src: dict | None,
        thresholds: dict,
        options: dict,
    ) -> ResolveResult | None:
        if not src:
            return None
        mode = src.get("mode")
        if mode == "manual":
            return ResolveResult(value=src.get("value"), mode=mode, detail="manual")

        if mode == "clone":
            other = src.get("copy_from")
            if other and other in options.get("profiles", {}):
                val = options["profiles"][other].get("thresholds", {}).get(key)
                return ResolveResult(value=val, mode=mode, detail=f"clone:{other}")

        if mode == "opb":
            opb = src.get("opb", {}) or {}
            species = opb.get("species")
            field = opb.get("field")
            if species and field:
                from .opb_client import OpenPlantbookClient

                session = self.hass.helpers.aiohttp_client.async_get_clientsession()
                token = await self._get_opb_token(entry)
                client = OpenPlantbookClient(session, token)
                detail = await client.species_details(species)
                val = self._extract(detail, field)
                return ResolveResult(value=val, mode=mode, detail=f"opb:{species}.{field}")

        if mode == "ai":
            ai = src.get("ai", {}) or {}
            ttl_h = int(ai.get("ttl_hours", 720))
            last_run = ai.get("last_run")
            if last_run:
                ts = datetime.fromisoformat(last_run.replace("Z", "+00:00"))
                if datetime.now(UTC) - ts < timedelta(hours=ttl_h):
                    return ResolveResult(
                        value=thresholds.get(key),
                        mode=mode,
                        detail="ai:cached",
                        confidence=ai.get("confidence"),
                    )
            from .ai_client import AIClient

            client = AIClient(self.hass, ai.get("provider", "openai"), ai.get("model", "gpt-4o-mini"))
            context = {
                "species": entry.options.get("profiles", {}).get(profile_id, {}).get("species"),
                "location": self.hass.config.location_name,
                "unit_system": self.hass.config.units.name,
                "key": key,
            }
            val, conf, notes, links = await client.generate_setpoint(context=context)
            self._update_ai_cache(entry, profile_id, key, val, conf, notes, links)
            return ResolveResult(value=val, mode=mode, detail=f"ai:{client.model}", confidence=conf)

        return None

    def _extract(self, detail: dict, dotted: str):
        cur = detail
        for part in dotted.split('.'):
            if isinstance(cur, dict):
                cur = cur.get(part)
            else:
                return None
        try:
            return float(cur)
        except Exception:
            return None

    async def _get_opb_token(self, entry):
        return entry.options.get("opb_token")

    def _update_ai_cache(self, entry, pid, key, val, conf, notes, links):
        opts = dict(entry.options)
        prof = dict(opts.get("profiles", {}).get(pid, {}))
        sources = dict(prof.get("sources", {}))
        ai = dict(sources.get(key, {}).get("ai", {}))
        ai["last_run"] = datetime.now(UTC).isoformat()
        ai["confidence"] = conf
        ai["notes"] = notes
        ai["links"] = links
        s = dict(sources.get(key, {}))
        s["ai"] = ai
        sources[key] = s
        prof["sources"] = sources
        allp = dict(opts.get("profiles", {}))
        allp[pid] = prof
        opts["profiles"] = allp
        self.hass.config_entries.async_update_entry(entry, options=opts)


async def generate_profile(
    hass: HomeAssistant,
    entry,
    profile_id: str,
    mode: str,
    source_profile_id: str | None = None,
) -> None:
    """Populate all variables for a profile from a single source and resolve immediately."""

    opts = dict(entry.options)
    prof = dict(opts.get("profiles", {}).get(profile_id, {}))
    sources = dict(prof.get("sources", {}))
    species = prof.get("species")
    slug = species.get("slug") if isinstance(species, dict) else species

    if mode == "clone":
        if not source_profile_id:
            raise ValueError("source_profile_id required for clone")
        other = opts.get("profiles", {}).get(source_profile_id, {})
        thresholds = dict(other.get("thresholds", {}))
        prof["thresholds"] = thresholds
        for key, *_ in VARIABLE_SPECS:
            sources[key] = {"mode": "clone", "copy_from": source_profile_id}
    else:
        for key, *_ in VARIABLE_SPECS:
            if mode == "opb":
                field = OPB_FIELD_MAP.get(key, key)
                sources[key] = {
                    "mode": "opb",
                    "opb": {"species": slug, "field": field},
                }
            else:
                sources[key] = {
                    "mode": "ai",
                    "ai": {
                        "provider": "openai",
                        "model": "gpt-4o-mini",
                        "ttl_hours": 720,
                    },
                }

    prof["sources"] = sources
    prof["needs_resolution"] = True
    allp = dict(opts.get("profiles", {}))
    allp[profile_id] = prof
    opts["profiles"] = allp
    hass.config_entries.async_update_entry(entry, options=opts)

    resolver = PreferenceResolver(hass)
    await resolver.resolve_profile(entry, profile_id)

    from .profile.store import async_save_profile_from_options

    await async_save_profile_from_options(hass, entry, profile_id)


async def resolve_variable_from_source(
    hass: HomeAssistant,
    *,
    plant_id: str,
    key: str,
    source: str,
    manual_value: Any | None = None,
    clone_from: str | None = None,
    opb_args: dict[str, Any] | None = None,
    ai_args: dict[str, Any] | None = None,
) -> VariableValue:
    """Resolve a single variable based on the selected source."""
    from .ai_client import async_recommend_variable
    from .opb_client import async_fetch_field
    from .profile.citations import ai_ref, clone_ref, manual_note, opb_ref
    from .profile.schema import VariableValue
    from .profile.store import async_get_profile

    citations = []
    if source == "manual":
        citations.append(manual_note("Set via options UI"))
        return VariableValue(value=manual_value, source=source, citations=citations)

    if source == "clone":
        if not clone_from:
            raise ValueError("clone_from required")
        src = await async_get_profile(hass, clone_from)
        if not src or key not in src.get("variables", {}):
            raise ValueError("Clone source missing variable")
        val = src["variables"][key]["value"]
        citations.append(clone_ref(clone_from, key))
        return VariableValue(value=val, source=source, citations=citations)

    if source == "openplantbook":
        field = (opb_args or {}).get("field")
        species = (opb_args or {}).get("species")
        val, url = await async_fetch_field(hass, species=species, field=field)
        citations.append(opb_ref(species, field, url))
        return VariableValue(value=val, source=source, citations=citations)

    if source == "ai":
        result = await async_recommend_variable(hass, key=key, plant_id=plant_id, **(ai_args or {}))
        citations.append(ai_ref(result.get("summary", ""), result.get("links", [])))
        return VariableValue(value=result["value"], source=source, citations=citations)

    raise ValueError(f"Unknown source: {source}")
