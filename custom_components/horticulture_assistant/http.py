"""HTTP views exposing BioProfile data for external consumers."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .profile.schema import BioProfile, ResolvedTarget
from .utils.entry_helpers import BY_PLANT_ID

_HTTP_REGISTERED = "http_registered"


def _iter_registries(hass: HomeAssistant) -> Iterable:
    domain_data = hass.data.get(DOMAIN, {})
    for key, value in domain_data.items():
        if key in {BY_PLANT_ID, _HTTP_REGISTERED}:
            continue
        registry = value.get("profile_registry")
        if registry is not None:
            yield registry


def _find_profile(hass: HomeAssistant, profile_id: str) -> BioProfile | None:
    for registry in _iter_registries(hass):
        getter = getattr(registry, "get_profile", None)
        if getter is None:
            continue
        profile = getter(profile_id)
        if profile is not None:
            return profile
    return None


def _serialise_target(target: ResolvedTarget) -> dict:
    return {
        "value": target.value,
        "annotation": target.annotation.to_json(),
        "citations": [asdict(cit) for cit in target.citations],
        "provenance": target.annotation.provenance_payload(),
    }


class ProfilesCollectionView(HomeAssistantView):
    """Return a high-level summary of every configured profile."""

    url = "/api/horticulture_assistant/profiles"
    name = "api:horticulture_assistant:profiles"
    requires_auth = True

    async def get(self, request):  # type: ignore[override]
        hass: HomeAssistant = request.app["hass"]
        summaries: list[dict] = []
        for registry in _iter_registries(hass):
            for profile in getattr(registry, "iter_profiles", lambda: [])():
                summary = profile.summary()
                if profile.statistics:
                    summary["statistics"] = [stat.to_json() for stat in profile.statistics]
                if profile.computed_stats:
                    summary["computed_stats"] = [snapshot.to_json() for snapshot in profile.computed_stats]
                summaries.append(summary)
        return self.json({"profiles": summaries})


class ProfileDetailView(HomeAssistantView):
    """Return the full BioProfile payload including provenance metadata."""

    url = "/api/horticulture_assistant/profiles/{profile_id}"
    name = "api:horticulture_assistant:profile"
    requires_auth = True

    async def get(self, request, profile_id):  # type: ignore[override]
        hass: HomeAssistant = request.app["hass"]
        profile = _find_profile(hass, profile_id)
        if profile is None:
            return self.json({"error": "not_found", "message": f"Profile {profile_id} not found"}, status_code=404)
        profile.refresh_sections()
        payload = profile.to_json()
        payload["summary"] = profile.summary()
        payload["resolved_values"] = profile.resolved_values()
        payload["provenance_summary"] = profile.provenance_summary()
        payload["computed_stats"] = [snapshot.to_json() for snapshot in profile.computed_stats]
        return self.json(payload)


class ProfileTargetView(HomeAssistantView):
    """Return a single resolved target with provenance metadata."""

    url = "/api/horticulture_assistant/profiles/{profile_id}/targets/{field}"
    name = "api:horticulture_assistant:profile_target"
    requires_auth = True

    async def get(self, request, profile_id, field):  # type: ignore[override]
        hass: HomeAssistant = request.app["hass"]
        profile = _find_profile(hass, profile_id)
        if profile is None:
            return self.json({"error": "not_found", "message": f"Profile {profile_id} not found"}, status_code=404)
        profile.refresh_sections()
        target = profile.resolved_targets.get(str(field))
        if target is None:
            return self.json(
                {"error": "missing", "message": f"Field {field} has not been resolved for profile {profile_id}"},
                status_code=404,
            )
        return self.json(
            {
                "profile_id": profile_id,
                "field": str(field),
                "target": _serialise_target(target),
            }
        )


def async_register_http_views(hass: HomeAssistant) -> None:
    """Register HTTP API endpoints exactly once per Home Assistant instance."""

    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get(_HTTP_REGISTERED):
        return
    hass.http.register_view(ProfilesCollectionView())
    hass.http.register_view(ProfileDetailView())
    hass.http.register_view(ProfileTargetView())
    domain_data[_HTTP_REGISTERED] = True
