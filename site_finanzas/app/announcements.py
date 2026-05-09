from datetime import datetime, timezone

# Update CURRENT_ANNOUNCEMENT to the latest key when releasing a new version.
# New users created on or after 'released_at' skip the announcement automatically.
CURRENT_ANNOUNCEMENT = 'v2.1'

ANNOUNCEMENTS = {
    'v1.7': {
        'key': 'v1.7',
        'released_at': datetime(2026, 4, 29, tzinfo=timezone.utc),
    },
    'v1.8': {
        'key': 'v1.8',
        'released_at': datetime(2026, 4, 29, tzinfo=timezone.utc),
    },
    'v2.0': {
        'key': 'v2.0',
        'released_at': datetime(2026, 5, 4, tzinfo=timezone.utc),
    },
    'v2.1': {
        'key': 'v2.1',
        'released_at': datetime(2026, 5, 9, tzinfo=timezone.utc),
    },
}
