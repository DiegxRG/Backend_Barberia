from datetime import datetime, timedelta, timezone
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

    def _build_state(self, user_id: str, role: str) -> str:
        payload = {
            "sub": user_id,
            "role": role,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=10),
        }
        return jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")

    def _parse_state(self, state: str) -> dict:
        try:
            return jwt.decode(state, settings.SUPABASE_JWT_SECRET, algorithms=["HS256"])
        except jwt.InvalidTokenError:
            raise UnauthorizedError("State OAuth invalido o expirado")

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
