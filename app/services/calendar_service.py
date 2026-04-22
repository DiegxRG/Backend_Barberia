from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

from cryptography.fernet import Fernet
import httpx
import jwt

from app.config import settings
from app.database.queries import calendar_tokens as queries
from app.models.calendar import CalendarStatusResponse, CalendarCallbackResponse
from app.utils.errors import BusinessRuleError, UnauthorizedError, InternalError


class CalendarService:
    def __init__(self):
        self.auth_uri = "https://accounts.google.com/o/oauth2/v2/auth"
        self.token_uri = "https://oauth2.googleapis.com/token"
        self.calendar_api_base = "https://www.googleapis.com/calendar/v3"

    def get_connect_url(self, current_user: dict) -> str:
        self._ensure_enabled_and_configured()
        state = self._build_state(current_user["id"], current_user.get("role", "cliente"))
        params = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": settings.GOOGLE_SCOPES,
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
            "state": state,
        }
        return f"{self.auth_uri}?{urlencode(params)}"

    def handle_callback(self, code: str, state: str) -> CalendarCallbackResponse:
        self._ensure_enabled_and_configured()
        state_payload = self._parse_state(state)
        user_id = state_payload["sub"]

        token_data = self._exchange_code_for_tokens(code)
        expires_in = int(token_data.get("expires_in", 3600))
        token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        existing = queries.get_token_by_user(user_id)
        refresh_token = token_data.get("refresh_token")
        if not refresh_token and existing:
            refresh_token = self._decrypt(existing["refresh_token"])

        if not refresh_token:
            raise InternalError("Google no devolvio refresh_token. Reintenta autorizando con prompt=consent")

        encrypted_access = self._encrypt(token_data["access_token"])
        encrypted_refresh = self._encrypt(refresh_token)

        queries.upsert_token(
            user_id=user_id,
            access_token=encrypted_access,
            refresh_token=encrypted_refresh,
            token_expires_at=token_expires_at,
            calendar_id="primary",
        )

        return CalendarCallbackResponse(
            connected=True,
            message="Google Calendar conectado correctamente",
            role=state_payload.get("role"),
        )

    def get_status(self, current_user: dict) -> CalendarStatusResponse:
        token_row = queries.get_token_by_user(current_user["id"])
        if not token_row:
            return CalendarStatusResponse(connected=False)
        return CalendarStatusResponse(
            connected=True,
            calendar_id=token_row.get("calendar_id", "primary"),
            token_expires_at=datetime.fromisoformat(token_row["token_expires_at"].replace("Z", "+00:00")),
        )

    def disconnect(self, current_user: dict) -> CalendarStatusResponse:
        queries.deactivate_token(current_user["id"])
        return CalendarStatusResponse(connected=False)

    def upsert_booking_event(
        self,
        user_id: str,
        booking: dict,
        *,
        service_name: Optional[str] = None,
        barber_name: Optional[str] = None,
    ) -> Optional[str]:
        """
        Crea o actualiza un evento en Google Calendar para una reserva.
        Si el usuario no tiene calendar conectado, retorna None.
        """
        context = self._get_active_calendar_context(user_id)
        if not context:
            return None

        access_token = context["access_token"]
        calendar_id = context["calendar_id"]
        event_payload = self._build_booking_event_payload(
            booking=booking,
            service_name=service_name,
            barber_name=barber_name,
        )

        existing_event_id = booking.get("calendar_event_id")
        if existing_event_id:
            url = f"{self.calendar_api_base}/calendars/{calendar_id}/events/{existing_event_id}"
            response = httpx.patch(
                url,
                headers=self._calendar_headers(access_token),
                json=event_payload,
                timeout=20,
            )
            if response.status_code == 404:
                existing_event_id = None
            elif response.status_code in {401, 403}:
                queries.deactivate_token(user_id)
                raise UnauthorizedError("Google Calendar no autorizado. Reconecta tu cuenta.")
            elif response.status_code >= 400:
                raise InternalError(f"No se pudo actualizar evento de Calendar: {response.text}")
            else:
                return response.json().get("id", booking.get("calendar_event_id"))

        create_url = f"{self.calendar_api_base}/calendars/{calendar_id}/events"
        create_response = httpx.post(
            create_url,
            headers=self._calendar_headers(access_token),
            json=event_payload,
            timeout=20,
        )
        if create_response.status_code in {401, 403}:
            queries.deactivate_token(user_id)
            raise UnauthorizedError("Google Calendar no autorizado. Reconecta tu cuenta.")
        if create_response.status_code >= 400:
            raise InternalError(f"No se pudo crear evento de Calendar: {create_response.text}")
        return create_response.json().get("id")

    def delete_booking_event(self, user_id: str, event_id: Optional[str]) -> None:
        """
        Elimina evento de calendar si existe.
        Si no hay calendar conectado o event_id es vacío, no hace nada.
        """
        if not event_id:
            return

        context = self._get_active_calendar_context(user_id)
        if not context:
            return

        access_token = context["access_token"]
        calendar_id = context["calendar_id"]
        url = f"{self.calendar_api_base}/calendars/{calendar_id}/events/{event_id}"
        response = httpx.delete(url, headers=self._calendar_headers(access_token), timeout=20)
        if response.status_code == 404:
            return
        if response.status_code in {401, 403}:
            queries.deactivate_token(user_id)
            raise UnauthorizedError("Google Calendar no autorizado. Reconecta tu cuenta.")
        if response.status_code >= 400:
            raise InternalError(f"No se pudo eliminar evento de Calendar: {response.text}")

    def _exchange_code_for_tokens(self, code: str) -> dict:
        payload = {
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        }
        try:
            response = httpx.post(self.token_uri, data=payload, timeout=20)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise UnauthorizedError(f"No se pudo intercambiar code con Google: {str(e)}")

    def _get_active_calendar_context(self, user_id: str) -> Optional[dict]:
        self._ensure_enabled_and_configured()
        token_row = queries.get_token_by_user(user_id)
        if not token_row:
            return None

        access_token = self._decrypt(token_row["access_token"])
        refresh_token = self._decrypt(token_row["refresh_token"])
        expires_at = datetime.fromisoformat(token_row["token_expires_at"].replace("Z", "+00:00"))
        calendar_id = token_row.get("calendar_id", "primary")

        if expires_at <= datetime.now(timezone.utc) + timedelta(seconds=60):
            access_token = self._refresh_access_token(
                user_id=user_id,
                refresh_token=refresh_token,
                calendar_id=calendar_id,
            )

        return {
            "access_token": access_token,
            "calendar_id": calendar_id,
        }

    def _refresh_access_token(self, user_id: str, refresh_token: str, calendar_id: str) -> str:
        payload = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
        response = httpx.post(self.token_uri, data=payload, timeout=20)
        if response.status_code >= 400:
            if "invalid_grant" in response.text.lower():
                queries.deactivate_token(user_id)
                raise UnauthorizedError("Google revocó el acceso. Conecta tu cuenta nuevamente.")
            raise UnauthorizedError(f"No se pudo refrescar token de Google: {response.text}")

        data = response.json()
        new_access = data.get("access_token")
        if not new_access:
            raise UnauthorizedError("Google no devolvió access_token al refrescar")

        new_refresh = data.get("refresh_token", refresh_token)
        expires_in = int(data.get("expires_in", 3600))
        token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        queries.upsert_token(
            user_id=user_id,
            access_token=self._encrypt(new_access),
            refresh_token=self._encrypt(new_refresh),
            token_expires_at=token_expires_at,
            calendar_id=calendar_id,
        )
        return new_access

    def _build_booking_event_payload(
        self,
        *,
        booking: dict,
        service_name: Optional[str],
        barber_name: Optional[str],
    ) -> dict:
        start_at = booking["start_at"]
        end_at = booking["end_at"]
        status = booking.get("status", "pending")
        summary_service = service_name or "Servicio"
        summary = f"Cita Barberia - {summary_service}"
        description_lines = [
            f"Reserva #{booking.get('id')}",
            f"Estado: {status}",
        ]
        if barber_name:
            description_lines.append(f"Barbero: {barber_name}")
        if booking.get("notes"):
            description_lines.append(f"Notas: {booking['notes']}")

        return {
            "summary": summary,
            "description": "\n".join(description_lines),
            "start": {"dateTime": start_at},
            "end": {"dateTime": end_at},
        }

    def _calendar_headers(self, access_token: str) -> dict:
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    def _build_state(self, user_id: str, role: str) -> str:
        payload = {
            "sub": user_id,
            "role": role,
            # Ventana amplia para evitar expiraciones durante pruebas/demo.
            "exp": datetime.now(timezone.utc) + timedelta(minutes=60),
            "iat": datetime.now(timezone.utc),
        }
        return jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")

    def _parse_state(self, state: str) -> dict:
        try:
            return jwt.decode(
                state,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                leeway=300,  # tolera desfasaje de reloj (5 min)
            )
        except jwt.ExpiredSignatureError:
            raise UnauthorizedError("State OAuth expirado. Vuelve a conectar Google Calendar.")
        except jwt.InvalidTokenError:
            raise UnauthorizedError("State OAuth invalido. Vuelve a iniciar la conexion con Google.")

    def _get_fernet(self) -> Fernet:
        key = settings.TOKEN_ENCRYPTION_KEY.strip()
        if not key:
            raise InternalError("TOKEN_ENCRYPTION_KEY no esta configurada")
        try:
            return Fernet(key.encode())
        except Exception:
            raise InternalError("TOKEN_ENCRYPTION_KEY invalida (debe ser Fernet)")

    def _encrypt(self, plain_text: str) -> str:
        fernet = self._get_fernet()
        return fernet.encrypt(plain_text.encode()).decode()

    def _decrypt(self, cipher_text: str) -> str:
        fernet = self._get_fernet()
        return fernet.decrypt(cipher_text.encode()).decode()

    def _ensure_enabled_and_configured(self) -> None:
        if not settings.GOOGLE_CALENDAR_ENABLED:
            raise BusinessRuleError("Google Calendar esta deshabilitado")
        if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET or not settings.GOOGLE_REDIRECT_URI:
            raise InternalError("Faltan variables de configuracion de Google OAuth")


calendar_service = CalendarService()
