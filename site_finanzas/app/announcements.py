from datetime import datetime, timezone

# Update CURRENT_ANNOUNCEMENT to the latest key when releasing a new version.
# New users created on or after 'released_at' skip the announcement automatically.
CURRENT_ANNOUNCEMENT = 'v2.6'

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
    'v2.2': {
        'key': 'v2.2',
        'released_at': datetime(2026, 5, 10, tzinfo=timezone.utc),
    },
    'v2.3': {
        'key': 'v2.3',
        'released_at': datetime(2026, 5, 10, tzinfo=timezone.utc),
    },
    'v2.5': {
        'key': 'v2.5',
        'released_at': datetime(2026, 6, 5, tzinfo=timezone.utc),
    },
    'v2.6': {
        'key': 'v2.6',
        'released_at': datetime(2026, 6, 20, tzinfo=timezone.utc),
    },
}
