"""Fechas en hora local. La base guarda UTC sin zona; la web debe mostrar la hora del usuario."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import current_app

DEFAULT_TIMEZONE = 'America/Santiago'


def app_timezone() -> ZoneInfo:
    name = current_app.config.get('APP_TIMEZONE') or DEFAULT_TIMEZONE
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return ZoneInfo(DEFAULT_TIMEZONE)


def to_local(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(app_timezone())
