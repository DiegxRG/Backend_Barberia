"""
Excepciones personalizadas y códigos de error estándar.
Formato de respuesta consistente en toda la API.
"""

from fastapi import HTTPException


class AppException(Exception):
    """
    Excepción base de la aplicación.
    Todas las excepciones de negocio heredan de esta.

    Formato de respuesta:
    {
        "detail": "Mensaje descriptivo del error",
        "code": "ERROR_CODE",
        "timestamp": "2026-04-20T10:30:00+00:00"
    }
    """

    def __init__(self, status_code: int, detail: str, code: str):
        self.status_code = status_code
        self.detail = detail
        self.code = code


# ── Errores de Autenticación ─────────────────────────────────

class UnauthorizedError(AppException):
    """Token inválido, expirado o no proporcionado."""
    def __init__(self, detail: str = "Token inválido o expirado"):
        super().__init__(status_code=401, detail=detail, code="UNAUTHORIZED")


class ForbiddenError(AppException):
    """Usuario no tiene permisos para esta acción."""
    def __init__(self, detail: str = "No tienes permisos para esta acción"):
        super().__init__(status_code=403, detail=detail, code="FORBIDDEN")


# ── Errores de Recursos ─────────────────────────────────────

class NotFoundError(AppException):
    """Recurso no encontrado."""
    def __init__(self, resource: str = "Recurso", detail: str | None = None):
        message = detail or f"{resource} no encontrado"
        super().__init__(status_code=404, detail=message, code="NOT_FOUND")


class ValidationError(AppException):
    """Datos de entrada inválidos."""
    def __init__(self, detail: str = "Datos de entrada inválidos"):
        super().__init__(status_code=400, detail=detail, code="VALIDATION_ERROR")


# ── Errores de Negocio ───────────────────────────────────────

class BookingConflictError(AppException):
    """Slot ya ocupado o reserva duplicada."""
    def __init__(self, detail: str = "El horario seleccionado ya no está disponible"):
        super().__init__(status_code=409, detail=detail, code="BOOKING_CONFLICT")


class BusinessRuleError(AppException):
    """Violación de regla de negocio."""
    def __init__(self, detail: str = "Operación no permitida por reglas de negocio"):
        super().__init__(status_code=422, detail=detail, code="BUSINESS_RULE_VIOLATION")


class InternalError(AppException):
    """Error interno del servidor."""
    def __init__(self, detail: str = "Error interno del servidor"):
        super().__init__(status_code=500, detail=detail, code="INTERNAL_ERROR")
