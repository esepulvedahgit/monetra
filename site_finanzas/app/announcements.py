from datetime import datetime, timezone

# Update CURRENT_ANNOUNCEMENT to the latest key when releasing a new version.
# New users created on or after 'released_at' skip the announcement automatically.
CURRENT_ANNOUNCEMENT = 'v1.8'

ANNOUNCEMENTS = {
    'v1.7': {
        'key': 'v1.7',
        'released_at': datetime(2026, 4, 29, tzinfo=timezone.utc),
    },
    'v1.8': {
        'key': 'v1.8',
        'released_at': datetime(2026, 4, 29, tzinfo=timezone.utc),
    },
}
