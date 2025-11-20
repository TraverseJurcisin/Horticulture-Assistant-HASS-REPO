from custom_components.horticulture_assistant.utils.labor_tracker import LaborLog


def test_log_and_summary(tmp_path):
    file_path = tmp_path / "labor.json"
    log = LaborLog(data_file=str(file_path))
    log.log_time("mixing", 30.0, zone_id="1")
    log.log_time("pruning", 15.0, zone_id="1")
    log.log_time("cleaning", 60.0, zone_id="2")
    assert log.total_minutes(zone_id="1") == 45.0
    assert log.total_minutes(task="cleaning") == 60.0


def test_roi_and_high_effort(tmp_path):
    file_path = tmp_path / "labor.json"
    log = LaborLog(data_file=str(file_path))
    log.log_time("harvesting", 120.0, zone_id="A")
    log.log_time("mixing", 60.0, zone_id="B")
    yields = {"A": 600.0, "B": 200.0}
    roi = log.compute_roi(yields)
    assert round(roi["A"], 2) == 300.0  # 600 g over 2 hours
    assert round(roi["B"], 2) == 200.0  # 200 g over 1 hour
    low = log.high_effort_low_return(yields, threshold=250.0)
    assert low == ["B"]


def test_task_minutes_and_high_effort(tmp_path):
    file_path = tmp_path / "labor.json"
    log = LaborLog(data_file=str(file_path))
    log.log_time("mixing", 30.0, zone_id="1")
    log.log_time("mixing", 40.0, zone_id="2")
    log.log_time("harvesting", 10.0, zone_id="2")
    totals = log.minutes_by_task()
    assert totals["mixing"] == 70.0
    high = log.high_effort_tasks(50.0)
    assert high == ["mixing"]
