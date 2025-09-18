from plant_engine import fertigation_optimizer


def test_generate_fertigation_plan_basic(monkeypatch):
    def fake_recommend(pt, st, vol):
        return {"urea": 3.15, "map": 1.545, "kcl": 2.04}, 0.0, {}, {}, {}

    def fake_interval(pt, st):
        return 1

    monkeypatch.setattr(fertigation_optimizer, "recommend_loss_adjusted_fertigation", fake_recommend)
    monkeypatch.setattr(fertigation_optimizer, "get_fertigation_interval", fake_interval)

    plan = fertigation_optimizer.generate_fertigation_plan("lettuce", "seedling", 10)
    assert plan["interval_days"] == 1
    assert plan["schedule_g"]["urea"] == 3.15
    assert plan["schedule_g"]["map"] == 1.545
    assert plan["schedule_g"]["kcl"] == 2.04
    assert plan["cost"] == 0.0
