from harness.claude_review_guard import quota_ok


def test_quota_guard():
    good = {"status": "allowed", "isUsingOverage": False,
            "unifiedWindows": {"five_hour": {"utilization": .1}, "seven_day": {"utilization": .54}}}
    assert quota_ok(good)
    assert not quota_ok(None)
    assert not quota_ok({**good, "isUsingOverage": True})
    assert not quota_ok({**good, "status": "rejected"})
    assert not quota_ok({**good, "unifiedWindows": {}})
    assert not quota_ok({**good, "unifiedWindows": {"five_hour": {"utilization": .80}}})
