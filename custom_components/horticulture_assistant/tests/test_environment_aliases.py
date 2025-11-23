from ..engine.plant_engine import environment_manager as em


def test_get_environment_aliases_contains_temperature():
    aliases = em.get_environment_aliases()
    assert "temp_c" in aliases
    assert "temperature" in aliases["temp_c"]


def test_resolve_environment_alias():
    assert em.resolve_environment_alias("temperature") == "temp_c"
    assert em.resolve_environment_alias("unknown") is None
