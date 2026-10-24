import importlib.util
from datetime import datetime, timezone
from pathlib import Path


def _announcements_module():
    path = Path(__file__).parents[1] / 'app' / 'announcements.py'
    spec = importlib.util.spec_from_file_location('announcements', path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_mobile_app_announcement_is_the_current_release():
    announcements = _announcements_module()

    assert announcements.CURRENT_ANNOUNCEMENT == 'v2.8'
    assert announcements.ANNOUNCEMENTS['v2.8']['released_at'] == datetime(2026, 9, 15, tzinfo=timezone.utc)
