import types

from custom_components.horticulture_assistant.const import DOMAIN
from custom_components.horticulture_assistant.http import (
    _HTTP_REGISTERED,
    _iter_cloud_managers,
    _iter_registries,
    async_register_http_views,
)
from custom_components.horticulture_assistant.utils.entry_helpers import BY_PLANT_ID


def test_register_http_views_idempotent() -> None:
    class DummyHTTP:
        def __init__(self) -> None:
            self.views: list = []

        def register_view(self, view) -> None:  # pragma: no cover - simple list append
            self.views.append(view)

    class DummyHass:
        def __init__(self) -> None:
            self.data: dict = {}
            self.http = DummyHTTP()

    # When HTTP is unavailable, the function should exit without marking the views as registered.
    pending = DummyHass()
    pending.http = None

    async_register_http_views(pending)
    domain_data = pending.data.get(DOMAIN, {})
    assert _HTTP_REGISTERED not in domain_data

    pending.http = DummyHTTP()
    async_register_http_views(pending)
    assert len(pending.http.views) == 5

    hass = DummyHass()

    async_register_http_views(hass)
    first_registered = list(hass.http.views)
    assert len(first_registered) == 5

    async_register_http_views(hass)
    assert hass.http.views == first_registered


def test_http_iterators_skip_non_mapping_domain_entries() -> None:
    hass = types.SimpleNamespace(
        data={
            DOMAIN: {
                "dataset_monitor_unsub": object(),
                "dataset_monitor_refs": 1,
                BY_PLANT_ID: {},
                _HTTP_REGISTERED: True,
                "entry": {
                    "profile_registry": "registry",
                    "cloud_sync_manager": "manager",
                },
            }
        }
    )

    registries = list(_iter_registries(hass))
    assert registries == ["registry"]

    managers = list(_iter_cloud_managers(hass))
    assert managers == ["manager"]


def test_http_iterators_handle_non_mapping_domain_container() -> None:
    hass = types.SimpleNamespace(data={DOMAIN: object()})

    assert list(_iter_registries(hass)) == []
    assert list(_iter_cloud_managers(hass)) == []
