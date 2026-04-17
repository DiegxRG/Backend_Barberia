"""
Helpers de zona horaria para el sistema de reservas.

REGLA DE ORO:
- La DB almacena TIMESTAMPTZ (UTC).
- availability_rules y breaks usan TIME (hora local del negocio).
- El motor de slots opera en hora local del negocio.
- Solo se convierte a UTC al comparar con bookings de la DB.

CONVENCIÓN day_of_week: ISO 8601
- 1=Lunes, 2=Martes, ..., 7=Domingo
- Python: date.isoweekday()  (⚠️ NO date.weekday())
- PostgreSQL: EXTRACT(ISODOW FROM date) (⚠️ NO EXTRACT(DOW ...))
"""

from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
from app.config import settings

# Zonas horarias del sistema
BUSINESS_TZ = ZoneInfo(settings.BUSINESS_TIMEZONE)  # ej: "America/Lima" (UTC-5)
UTC_TZ = ZoneInfo("UTC")


def to_business_tz(dt_utc: datetime) -> datetime:
    """
    Convierte datetime UTC a zona horaria del negocio.

    Ejemplo: 14:00 UTC → 09:00 America/Lima (UTC-5)
    """
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=UTC_TZ)
    return dt_utc.astimezone(BUSINESS_TZ)


def to_utc(dt_local: datetime) -> datetime:
    """
    Convierte datetime local del negocio a UTC.

    Ejemplo: 09:00 America/Lima → 14:00 UTC
    """
    if dt_local.tzinfo is None:
        dt_local = dt_local.replace(tzinfo=BUSINESS_TZ)
    return dt_local.astimezone(UTC_TZ)


def make_local_datetime(local_date: date, local_time: time) -> datetime:
    """
    Combina fecha + hora local en un datetime con zona horaria del negocio.

    Ejemplo: date(2026,4,20) + time(9,0) → 2026-04-20T09:00:00-05:00
    """
    naive = datetime.combine(local_date, local_time)
    return naive.replace(tzinfo=BUSINESS_TZ)


def get_day_bounds_utc(target_date: date) -> tuple[datetime, datetime]:
    """
    Retorna el inicio y fin del día en UTC, basado en la zona horaria del negocio.
    Útil para buscar bookings de un día específico.

    Ejemplo para 2026-04-20 en America/Lima (UTC-5):
    - Inicio: 2026-04-20T00:00:00-05:00 → 2026-04-20T05:00:00Z
    - Fin:    2026-04-20T23:59:59-05:00 → 2026-04-21T04:59:59Z
    """
    day_start_local = make_local_datetime(target_date, time(0, 0, 0))
    day_end_local = make_local_datetime(target_date, time(23, 59, 59))
    return to_utc(day_start_local), to_utc(day_end_local)


def now_local() -> datetime:
    """Retorna la hora actual en la zona horaria del negocio."""
    return datetime.now(BUSINESS_TZ)


def now_utc() -> datetime:
    """Retorna la hora actual en UTC."""
    return datetime.now(UTC_TZ)
