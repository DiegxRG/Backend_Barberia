from urllib.parse import urlencode
import html

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse, HTMLResponse

from app.config import settings
from app.dependencies import require_role
from app.models.calendar import (
    CalendarStatusResponse,
    CalendarCallbackResponse,
    CalendarConnectUrlResponse,
)
from app.services.calendar_service import calendar_service
from app.utils.errors import AppException

router = APIRouter()


@router.get("/connect-url", response_model=CalendarConnectUrlResponse, summary="Obtener URL OAuth de Google Calendar")
def connect_google_calendar_url(current_user: dict = Depends(require_role("admin", "barbero"))):
    auth_url = calendar_service.get_connect_url(current_user)
    return CalendarConnectUrlResponse(auth_url=auth_url)


@router.get("/connect", summary="Iniciar OAuth con Google Calendar")
def connect_google_calendar(current_user: dict = Depends(require_role("admin", "barbero"))):
    auth_url = calendar_service.get_connect_url(current_user)
    return RedirectResponse(url=auth_url, status_code=302)


def _frontend_calendar_settings_url(params: dict[str, str] | None = None) -> str:
    frontend_base = settings.CORS_ORIGINS.split(",")[0].strip().rstrip("/")
    target = f"{frontend_base}/settings/calendar"
    if params:
        return f"{target}?{urlencode(params)}"
    return target


def _oauth_feedback_page(*, title: str, subtitle: str, redirect_url: str, success: bool) -> str:
    safe_title = html.escape(title)
    safe_subtitle = html.escape(subtitle)
    safe_redirect = html.escape(redirect_url, quote=True)
    accent = "#d7b67d" if success else "#f87171"
    chip_bg = "rgba(201, 167, 102, 0.18)" if success else "rgba(248, 113, 113, 0.14)"
    chip_text = "Conexion completada" if success else "Conexion con observaciones"

    return f"""
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta http-equiv="Cache-Control" content="no-store" />
  <title>{safe_title}</title>
  <link rel="icon" href="data:," />
  <style>
    :root {{
      color-scheme: dark;
      --bg: #0d0f14;
      --card: #151922;
      --text: #f4f5f8;
      --muted: #a5adbd;
      --accent: {accent};
      --chip-bg: {chip_bg};
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
      background:
        radial-gradient(120% 90% at 50% 0%, rgba(255,255,255,0.06), transparent 50%),
        linear-gradient(180deg, #0d0f14 0%, #090b10 100%);
      color: var(--text);
      padding: 20px;
    }}
    .card {{
      width: min(540px, 100%);
      background: linear-gradient(160deg, rgba(21,25,34,0.95), rgba(18,22,30,0.95));
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 18px;
      box-shadow: 0 24px 50px rgba(0,0,0,0.45);
      padding: 32px 28px;
      text-align: center;
    }}
    .chip {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      margin: 0 auto 14px;
      padding: 8px 14px;
      border-radius: 999px;
      background: var(--chip-bg);
      color: var(--accent);
      font-size: 12px;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      font-weight: 700;
    }}
    .title {{
      margin: 0;
      font-size: clamp(1.35rem, 2.5vw, 1.9rem);
      line-height: 1.2;
    }}
    .subtitle {{
      margin: 10px 0 0;
      color: var(--muted);
      font-size: 0.98rem;
      line-height: 1.45;
    }}
    .spinner-wrap {{
      margin: 24px auto 10px;
      width: 74px;
      height: 74px;
      position: relative;
      display: grid;
      place-items: center;
    }}
    .spinner {{
      width: 74px;
      height: 74px;
      border-radius: 50%;
      border: 4px solid rgba(255,255,255,0.12);
      border-top-color: var(--accent);
      animation: spin 1s linear infinite;
      position: absolute;
      inset: 0;
    }}
    .count {{
      font-size: 1.35rem;
      font-weight: 800;
      color: var(--accent);
    }}
    .hint {{
      margin: 12px 0 0;
      color: var(--muted);
      font-size: 0.9rem;
    }}
    .btn {{
      margin-top: 18px;
      border: 1px solid rgba(255,255,255,0.2);
      background: transparent;
      color: var(--text);
      border-radius: 10px;
      padding: 10px 14px;
      font-size: 0.9rem;
      cursor: pointer;
    }}
    .btn:hover {{ border-color: var(--accent); color: var(--accent); }}
    @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
  </style>
</head>
<body>
  <main class="card">
    <div class="chip">{chip_text}</div>
    <h1 class="title">{safe_title}</h1>
    <p class="subtitle">{safe_subtitle}</p>

    <div class="spinner-wrap" aria-hidden="true">
      <div class="spinner"></div>
      <div id="countdown" class="count">5</div>
    </div>

    <p class="hint">Redirigiendo a configuracion en <strong id="countdown-text">5</strong> segundos...</p>
    <button id="continue" class="btn" type="button">Ir ahora</button>
  </main>

  <script>
    (function() {{
      const targetUrl = "{safe_redirect}";
      const countdownEl = document.getElementById('countdown');
      const countdownTextEl = document.getElementById('countdown-text');
      const continueBtn = document.getElementById('continue');
      let seconds = 5;
      let done = false;

      const goToApp = () => {{
        if (done) return;
        done = true;

        try {{
          if (window.opener && !window.opener.closed) {{
            window.opener.location.href = targetUrl;
            window.close();
            return;
          }}
        }} catch (err) {{
          // Si falla por politica de origen, continua con redirect local.
        }}

        window.location.replace(targetUrl);
      }};

      const timer = window.setInterval(() => {{
        seconds -= 1;
        countdownEl.textContent = String(Math.max(seconds, 0));
        countdownTextEl.textContent = String(Math.max(seconds, 0));
        if (seconds <= 0) {{
          window.clearInterval(timer);
          goToApp();
        }}
      }}, 1000);

      continueBtn.addEventListener('click', () => {{
        window.clearInterval(timer);
        goToApp();
      }});
    }})();
  </script>
</body>
</html>
"""


def _success_message_for_role(role: str | None, fallback_message: str) -> tuple[str, str]:
    normalized = (role or "").strip().lower()
    if normalized == "admin":
        return (
            "Conexion exitosa para Administracion",
            "Google Calendar quedo conectado para tu panel admin. Te redirigimos a Configuracion Calendar.",
        )
    if normalized == "barbero":
        return (
            "Conexion exitosa para tu agenda",
            "Google Calendar quedo conectado para tu cuenta de barbero. Te redirigimos a Configuracion Calendar.",
        )
    return ("Conexion exitosa", fallback_message)


@router.get("/callback", summary="Callback OAuth de Google")
def google_callback(code: str = Query(...), state: str = Query(...)):
    try:
        result: CalendarCallbackResponse = calendar_service.handle_callback(code, state)
        success_title, success_subtitle = _success_message_for_role(result.role, result.message)
        redirect_url = _frontend_calendar_settings_url({"google_calendar": "connected"})
        return HTMLResponse(
            _oauth_feedback_page(
                title=success_title,
                subtitle=success_subtitle,
                redirect_url=redirect_url,
                success=True,
            ),
            status_code=200,
        )
    except AppException as exc:
        redirect_url = _frontend_calendar_settings_url({"google_calendar": "error"})
        return HTMLResponse(
            _oauth_feedback_page(
                title="No se pudo completar la conexion",
                subtitle=exc.detail,
                redirect_url=redirect_url,
                success=False,
            ),
            status_code=200,
        )


@router.get("/status", response_model=CalendarStatusResponse, summary="Estado de conexion a Google Calendar")
def calendar_status(current_user: dict = Depends(require_role("admin", "barbero"))):
    return calendar_service.get_status(current_user)


@router.delete("/disconnect", response_model=CalendarStatusResponse, summary="Desconectar Google Calendar")
def disconnect_calendar(current_user: dict = Depends(require_role("admin", "barbero"))):
    return calendar_service.disconnect(current_user)
