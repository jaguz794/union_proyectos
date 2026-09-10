from __future__ import annotations

import argparse
import html
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "portal_config.json"
LOG_DIR = ROOT / "logs"

revisor_lock = threading.Lock()
revisor_process: subprocess.Popen[str] | None = None
revisor_log_path: Path | None = None
revisor_started_at: float | None = None


def load_config() -> dict[str, Any]:
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def get_app(app_id: str) -> dict[str, Any] | None:
    for app in load_config().get("apps", []):
        if app.get("id") == app_id:
            return app
    return None


def json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def escape(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def configured_path(value: object) -> Path:
    path = Path(str(value or ""))
    if path.is_absolute():
        return path
    return ROOT / path


def check_status(app: dict[str, Any]) -> dict[str, Any]:
    configured_state = str(app.get("state", "")).strip().lower()
    project_path_value = str(app.get("project_path", "")).strip()
    project_path = configured_path(project_path_value) if project_path_value else None
    exists = project_path.exists() if project_path is not None else True
    if configured_state == "construction":
        return {"id": app["id"], "state": "construction", "project_exists": exists}
    status_url = app.get("status_url")
    if not status_url:
        return {"id": app["id"], "state": "ready" if exists else "missing", "project_exists": exists}
    request = urllib.request.Request(
        str(status_url),
        headers={"User-Agent": "PortalAplicaciones/1.0"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            online = 200 <= int(response.status) < 500
            return {
                "id": app["id"],
                "state": "online" if online else "offline",
                "project_exists": exists,
                "status_code": int(response.status),
            }
    except urllib.error.HTTPError as exc:
        return {
            "id": app["id"],
            "state": "online" if int(exc.code) < 500 else "offline",
            "project_exists": exists,
            "status_code": int(exc.code),
        }
    except Exception:
        return {"id": app["id"], "state": "offline", "project_exists": exists}


def render_layout(title: str, body: str, extra_head: str = "") -> bytes:
    config = load_config()
    portal = config.get("portal", {})
    document = f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f7f9;
      --ink: #18212f;
      --muted: #5d6878;
      --line: #dfe4ea;
      --panel: rgba(255, 255, 255, 0.9);
      --shadow: 0 20px 45px rgba(21, 31, 45, 0.14);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      letter-spacing: 0;
      overflow-x: hidden;
      position: relative;
      isolation: isolate;
    }}
    body::before {{
      content: "";
      position: fixed;
      inset: 0;
      z-index: -2;
      background-image: url("/static/portal-background.png");
      background-position: center;
      background-size: cover;
      opacity: 0.42;
    }}
    body::after {{
      content: "";
      position: fixed;
      inset: 0;
      z-index: -1;
      background:
        linear-gradient(90deg, rgba(255,255,255,0.42), rgba(255,255,255,0.76) 52%, rgba(255,255,255,0.9)),
        rgba(255,255,255,0.22);
    }}
    a {{ color: inherit; text-decoration: none; }}
    .shell {{
      width: min(1180px, calc(100% - 32px));
      margin: 0 auto;
      padding: 30px 0 44px;
      position: relative;
      z-index: 1;
    }}
    .topbar {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 18px;
      padding: 14px 0 26px;
    }}
    .brand {{
      display: flex;
      align-items: center;
      gap: 14px;
      min-width: 0;
      border: 1px solid rgba(223, 228, 234, 0.72);
      border-radius: 8px;
      background: rgba(255,255,255,0.72);
      box-shadow: 0 10px 26px rgba(21, 31, 45, 0.07);
      padding: 10px 12px;
      backdrop-filter: blur(8px);
    }}
    .brand img {{
      width: 54px;
      height: 54px;
      object-fit: contain;
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 6px;
    }}
    .brand h1 {{
      margin: 0;
      font-size: clamp(1.55rem, 1.2rem + 1.1vw, 2.35rem);
      line-height: 1.05;
      letter-spacing: 0;
    }}
    .brand p {{
      margin: 6px 0 0;
      color: var(--muted);
      font-size: 0.98rem;
    }}
    .address {{
      display: flex;
      align-items: center;
      gap: 10px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgba(255,255,255,0.82);
      padding: 10px 12px;
      color: var(--muted);
      white-space: nowrap;
      box-shadow: 0 8px 22px rgba(21, 31, 45, 0.06);
    }}
    .address strong {{ color: var(--ink); font-weight: 700; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 16px;
      align-items: stretch;
    }}
    .app-card {{
      min-height: 244px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      gap: 20px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      box-shadow: var(--shadow);
      padding: 18px;
      position: relative;
      overflow: hidden;
      backdrop-filter: blur(9px);
      transition: transform 160ms ease, border-color 160ms ease, box-shadow 160ms ease;
    }}
    .app-card:focus-visible,
    .app-card:hover {{
      transform: translateY(-3px);
      border-color: color-mix(in srgb, var(--accent), #ffffff 35%);
      box-shadow: 0 24px 52px rgba(21, 31, 45, 0.16);
      outline: none;
    }}
    .app-card::before {{
      content: "";
      position: absolute;
      inset: 0 0 auto;
      height: 5px;
      background: var(--accent);
    }}
    .app-head {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: flex-start;
    }}
    .badge {{
      flex: 0 0 auto;
      display: grid;
      place-items: center;
      width: 44px;
      height: 44px;
      border-radius: 8px;
      background: color-mix(in srgb, var(--accent), #ffffff 88%);
      color: var(--accent);
      font-weight: 800;
      font-size: 0.95rem;
    }}
    .status {{
      display: inline-flex;
      align-items: center;
      gap: 7px;
      color: var(--muted);
      font-size: 0.82rem;
      line-height: 1;
      white-space: nowrap;
    }}
    .dot {{
      width: 9px;
      height: 9px;
      border-radius: 50%;
      background: #9aa4b2;
    }}
    .status.online .dot,
    .status.ready .dot {{ background: #16a34a; }}
    .status.offline .dot {{ background: #dc2626; }}
    .status.missing .dot,
    .status.construction .dot {{ background: #ca8a04; }}
    .app-card h2 {{
      margin: 18px 0 8px;
      font-size: 1.24rem;
      line-height: 1.18;
      letter-spacing: 0;
    }}
    .app-card p {{
      margin: 0;
      color: var(--muted);
      line-height: 1.48;
      font-size: 0.96rem;
    }}
    .meta {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      padding-top: 14px;
      border-top: 1px solid var(--line);
      color: var(--muted);
      font-size: 0.85rem;
    }}
    .open-label {{
      color: var(--accent);
      font-weight: 800;
      white-space: nowrap;
    }}
    .panel {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      box-shadow: var(--shadow);
      padding: 22px;
    }}
    .toolbar {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin: 4px 0 18px;
    }}
    .button {{
      appearance: none;
      border: 0;
      border-radius: 8px;
      background: #18212f;
      color: #fff;
      min-height: 42px;
      padding: 0 16px;
      font-weight: 800;
      cursor: pointer;
    }}
    .button.secondary {{
      background: #eef2f6;
      color: #18212f;
      border: 1px solid var(--line);
    }}
    .form-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
    }}
    label {{
      display: grid;
      gap: 7px;
      color: var(--muted);
      font-size: 0.88rem;
      font-weight: 700;
    }}
    input,
    textarea {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 11px 12px;
      font: inherit;
      color: var(--ink);
      background: #fff;
    }}
    textarea {{ min-height: 92px; resize: vertical; }}
    .span-2 {{ grid-column: 1 / -1; }}
    .switch-row {{
      display: flex;
      align-items: center;
      gap: 10px;
      color: var(--muted);
      font-weight: 700;
      margin: 14px 0;
    }}
    .switch-row input {{ width: 18px; height: 18px; }}
    pre {{
      min-height: 180px;
      max-height: 360px;
      overflow: auto;
      margin: 16px 0 0;
      padding: 14px;
      border-radius: 8px;
      border: 1px solid #263244;
      color: #dbeafe;
      background: #111827;
      white-space: pre-wrap;
      font-size: 0.86rem;
    }}
    .notice {{
      margin: 0 0 18px;
      color: var(--muted);
      line-height: 1.5;
    }}
    @media (max-width: 980px) {{
      .grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .topbar {{ align-items: flex-start; flex-direction: column; }}
      .address {{ white-space: normal; }}
    }}
    @media (max-width: 640px) {{
      .shell {{ width: min(100% - 22px, 1180px); padding-top: 18px; }}
      .grid, .form-grid {{ grid-template-columns: 1fr; }}
      .span-2 {{ grid-column: auto; }}
      .app-card {{ min-height: 212px; }}
      .brand img {{ width: 48px; height: 48px; }}
    }}
  </style>
  {extra_head}
</head>
<body>
  <main class="shell">
    <header class="topbar">
      <a class="brand" href="/">
        <img src="/static/logo-popular.png" alt="Logo Popular">
        <div>
          <h1>{escape(portal.get("title", "Portal de Aplicaciones"))}</h1>
          <p>{escape(portal.get("subtitle", ""))}</p>
        </div>
      </a>
      <div class="address"><span>Direccion</span><strong id="portal-address">http://{escape(portal.get("host", "127.0.0.1"))}:{escape(portal.get("port", "9000"))}</strong></div>
    </header>
    {body}
  </main>
  <script>
    const portalAddress = document.getElementById("portal-address");
    if (portalAddress) portalAddress.textContent = window.location.origin;
  </script>
</body>
</html>"""
    return document.encode("utf-8")


def app_initials(name: str) -> str:
    words = [part for part in name.replace("_", " ").split() if part]
    return "".join(word[0].upper() for word in words[:2]) or "AP"


def render_home() -> bytes:
    apps = load_config().get("apps", [])
    cards = []
    for app in apps:
        accent = escape(app.get("accent", "#2563eb"))
        href = f"/abrir/{escape(app.get('id', ''))}"
        cards.append(
            f"""<a class="app-card" href="{href}" style="--accent:{accent}" data-app-id="{escape(app.get("id"))}">
  <div>
    <div class="app-head">
      <span class="badge">{escape(app_initials(app.get("name", "")))}</span>
      <span class="status" data-status><span class="dot"></span><span data-label>Validando</span></span>
    </div>
    <h2>{escape(app.get("name"))}</h2>
    <p>{escape(app.get("summary"))}</p>
  </div>
  <div class="meta">
    <span>{escape(app.get("runtime"))} · {escape(app.get("port_label"))}</span>
    <span class="open-label">Ingresar</span>
  </div>
</a>"""
        )
    script = """
<script>
const labels = {
  online: "Disponible",
  ready: "Listo",
  offline: "Sin iniciar",
  missing: "Ruta no encontrada",
  construction: "En construccion"
};
async function refreshStatus() {
  try {
    const response = await fetch("/api/status", { cache: "no-store" });
    const payload = await response.json();
    for (const item of payload.apps || []) {
      const card = document.querySelector(`[data-app-id="${item.id}"]`);
      if (!card) continue;
      const status = card.querySelector("[data-status]");
      const label = card.querySelector("[data-label]");
      status.className = `status ${item.state}`;
      label.textContent = labels[item.state] || item.state;
    }
  } catch {
    for (const status of document.querySelectorAll("[data-status]")) {
      status.className = "status offline";
      status.querySelector("[data-label]").textContent = "Sin validar";
    }
  }
}
refreshStatus();
setInterval(refreshStatus, 12000);
</script>
"""
    return render_layout("Portal de Aplicaciones", f'<section class="grid">{"".join(cards)}</section>{script}')


def render_revisor_page() -> bytes:
    app = get_app("revisor-separata") or {}
    project_path = escape(app.get("project_path", ""))
    body = f"""<section class="panel" style="--accent:{escape(app.get("accent", "#7c3aed"))}">
  <div class="toolbar">
    <div>
      <h2 style="margin:0 0 6px;font-size:1.35rem;letter-spacing:0;">REVISOR DE OFERTAS</h2>
      <p class="notice">Proyecto: {project_path}</p>
    </div>
    <a class="button secondary" href="/">Volver</a>
  </div>
  <form id="runForm">
    <div class="form-grid">
      <label class="span-2">Carpeta PDF
        <input name="pdf_dir" value="C:\\Users\\jaguz\\Documents\\proyectos\\separata">
      </label>
      <label class="span-2">Excels de referencia
        <textarea name="reference_excel"></textarea>
      </label>
      <label>Escala OCR
        <input name="scale" type="number" min="1" max="4" step="0.25" value="2">
      </label>
      <label>Maximo de paginas
        <input name="max_pages" type="number" min="0" step="1" value="0">
      </label>
    </div>
    <label class="switch-row"><input name="reuse_ocr_cache" type="checkbox"> Reusar cache OCR</label>
    <button class="button" type="submit">Ejecutar</button>
    <button class="button secondary" type="button" id="refreshButton">Actualizar estado</button>
  </form>
  <pre id="logBox">Sin ejecucion activa.</pre>
</section>
<script>
const form = document.getElementById("runForm");
const logBox = document.getElementById("logBox");
const refreshButton = document.getElementById("refreshButton");

function formPayload() {{
  const data = new FormData(form);
  return {{
    pdf_dir: String(data.get("pdf_dir") || ""),
    reference_excel: String(data.get("reference_excel") || "").split(/\\r?\\n/).map(x => x.trim()).filter(Boolean),
    scale: Number(data.get("scale") || 2),
    max_pages: Number(data.get("max_pages") || 0),
    reuse_ocr_cache: Boolean(data.get("reuse_ocr_cache"))
  }};
}}

async function refreshStatus() {{
  const response = await fetch("/api/revisor/status", {{ cache: "no-store" }});
  const payload = await response.json();
  logBox.textContent = payload.message + "\\n\\n" + (payload.log || "");
}}

form.addEventListener("submit", async (event) => {{
  event.preventDefault();
  logBox.textContent = "Iniciando proceso...";
  const response = await fetch("/api/revisor/run", {{
    method: "POST",
    headers: {{ "Content-Type": "application/json" }},
    body: JSON.stringify(formPayload())
  }});
  const payload = await response.json();
  logBox.textContent = payload.message || "Solicitud enviada.";
  refreshStatus();
}});

refreshButton.addEventListener("click", refreshStatus);
setInterval(refreshStatus, 8000);
refreshStatus();
</script>"""
    return render_layout("REVISOR DE OFERTAS", body)


def render_construction_page(app_id: str) -> bytes:
    app = get_app(app_id)
    name = app.get("name", "Aplicativo") if app else "Aplicativo"
    accent = app.get("accent", "#64748b") if app else "#64748b"
    body = f"""<section class="panel" style="--accent:{escape(accent)}">
  <div class="toolbar">
    <div>
      <h2 style="margin:0 0 6px;font-size:1.45rem;letter-spacing:0;">{escape(name)}</h2>
      <p class="notice">En construccion. Este acceso queda reservado en el portal mientras el aplicativo se masifica.</p>
    </div>
    <a class="button secondary" href="/">Volver</a>
  </div>
</section>"""
    return render_layout(f"{name} - En construccion", body)


def read_request_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0") or 0)
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    return json.loads(raw.decode("utf-8") or "{}")


def latest_log_tail(path: Path | None, max_lines: int = 120) -> str:
    if not path or not path.exists():
        return ""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return "\n".join(lines[-max_lines:])


def revisor_status_payload() -> dict[str, Any]:
    with revisor_lock:
        process = revisor_process
        log_path = revisor_log_path
        started_at = revisor_started_at
    if process is None:
        return {
            "state": "idle",
            "message": "Sin ejecucion activa.",
            "log": latest_log_tail(log_path),
        }
    return_code = process.poll()
    if return_code is None:
        elapsed = int(time.time() - (started_at or time.time()))
        return {
            "state": "running",
            "message": f"Proceso en ejecucion. Tiempo: {elapsed}s.",
            "log": latest_log_tail(log_path),
        }
    return {
        "state": "finished" if return_code == 0 else "failed",
        "message": f"Proceso finalizado con codigo {return_code}.",
        "return_code": return_code,
        "log": latest_log_tail(log_path),
    }


def start_revisor(payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    global revisor_process, revisor_log_path, revisor_started_at

    app = get_app("revisor-separata")
    if not app:
        return 404, {"message": "No existe la configuracion del revisor."}

    project_path = Path(str(app.get("project_path", "")))
    script_path = project_path / "scripts" / "run_pipeline.ps1"
    pdf_dir = Path(str(payload.get("pdf_dir", "")).strip())
    refs = [Path(str(item).strip()) for item in payload.get("reference_excel", []) if str(item).strip()]
    scale = float(payload.get("scale") or 2.0)
    max_pages = int(payload.get("max_pages") or 0)
    reuse_cache = bool(payload.get("reuse_ocr_cache"))

    if not project_path.exists() or not script_path.exists():
        return 404, {"message": "No se encontro el proyecto o el script del revisor."}
    if not pdf_dir.exists() or not pdf_dir.is_dir():
        return 400, {"message": "La carpeta PDF no existe."}
    missing_refs = [str(ref) for ref in refs if not ref.exists()]
    if missing_refs:
        return 400, {"message": "Hay excels de referencia que no existen.", "missing": missing_refs}

    with revisor_lock:
        if revisor_process is not None and revisor_process.poll() is None:
            return 409, {"message": "Ya hay una ejecucion del revisor en curso."}

        LOG_DIR.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        revisor_log_path = LOG_DIR / f"revisor_separata_{stamp}.log"
        log_handle = revisor_log_path.open("w", encoding="utf-8")
        args = [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_path),
            "-PdfDir",
            str(pdf_dir),
            "-OutputRoot",
            "outputs",
            "-Scale",
            str(scale),
            "-MaxPages",
            str(max_pages),
        ]
        if refs:
            args.append("-ReferenceExcel")
            args.extend(str(ref) for ref in refs)
        if reuse_cache:
            args.append("-ReuseOcrCache")
        revisor_process = subprocess.Popen(
            args,
            cwd=str(project_path),
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            text=True,
        )
        revisor_started_at = time.time()
    return 202, {"message": "REVISOR DE OFERTAS iniciado.", "log_file": str(revisor_log_path)}


class PortalHandler(BaseHTTPRequestHandler):
    server_version = "PortalAplicaciones/1.0"

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def send_bytes(self, body: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, payload: Any, status: int = 200) -> None:
        self.send_bytes(json_bytes(payload), "application/json; charset=utf-8", status=status)

    def send_head_only(self, content_type: str, status: int = 200, length: int = 0) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.end_headers()

    def do_HEAD(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if path == "/":
            body = render_home()
            self.send_head_only("text/html; charset=utf-8", length=len(body))
            return
        if path == "/health":
            body = json_bytes({"ok": True})
            self.send_head_only("application/json; charset=utf-8", length=len(body))
            return
        if path == "/revisor-separata":
            body = render_revisor_page()
            self.send_head_only("text/html; charset=utf-8", length=len(body))
            return
        if path.startswith("/en-construccion/"):
            app_id = path.rsplit("/", 1)[-1]
            body = render_construction_page(app_id)
            self.send_head_only("text/html; charset=utf-8", length=len(body))
            return
        if path == "/static/portal-background.png":
            background = configured_path(load_config().get("portal", {}).get("background_path", ""))
            if background.exists():
                self.send_head_only("image/png", length=background.stat().st_size)
                return
            self.send_error(HTTPStatus.NOT_FOUND, "Fondo no encontrado")
            return
        if path == "/static/logo-popular.png":
            logo = configured_path(load_config().get("portal", {}).get("logo_path", ""))
            if logo.exists():
                self.send_head_only("image/png", length=logo.stat().st_size)
                return
            self.send_error(HTTPStatus.NOT_FOUND, "Logo no encontrado")
            return
        if path.startswith("/abrir/"):
            app_id = path.rsplit("/", 1)[-1]
            app = get_app(app_id)
            if not app:
                self.send_error(HTTPStatus.NOT_FOUND, "Aplicacion no encontrada")
                return
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", str(app.get("url", "/")))
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Ruta no encontrada")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if path == "/":
            self.send_bytes(render_home(), "text/html; charset=utf-8")
            return
        if path == "/health":
            self.send_json({"ok": True})
            return
        if path == "/api/status":
            apps = load_config().get("apps", [])
            self.send_json({"apps": [check_status(app) for app in apps]})
            return
        if path == "/api/revisor/status":
            self.send_json(revisor_status_payload())
            return
        if path == "/revisor-separata":
            self.send_bytes(render_revisor_page(), "text/html; charset=utf-8")
            return
        if path.startswith("/en-construccion/"):
            app_id = path.rsplit("/", 1)[-1]
            self.send_bytes(render_construction_page(app_id), "text/html; charset=utf-8")
            return
        if path == "/static/logo-popular.png":
            logo = configured_path(load_config().get("portal", {}).get("logo_path", ""))
            if logo.exists():
                self.send_bytes(logo.read_bytes(), "image/png")
                return
            self.send_error(HTTPStatus.NOT_FOUND, "Logo no encontrado")
            return
        if path == "/static/portal-background.png":
            background = configured_path(load_config().get("portal", {}).get("background_path", ""))
            if background.exists():
                self.send_bytes(background.read_bytes(), "image/png")
                return
            self.send_error(HTTPStatus.NOT_FOUND, "Fondo no encontrado")
            return
        if path.startswith("/abrir/"):
            app_id = path.rsplit("/", 1)[-1]
            app = get_app(app_id)
            if not app:
                self.send_error(HTTPStatus.NOT_FOUND, "Aplicacion no encontrada")
                return
            target = str(app.get("url", "/"))
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", target)
            self.end_headers()
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Ruta no encontrada")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if path == "/api/revisor/run":
            try:
                status, payload = start_revisor(read_request_json(self))
            except Exception as exc:
                status, payload = 500, {"message": str(exc)}
            self.send_json(payload, status=status)
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Ruta no encontrada")


def main() -> None:
    config = load_config()
    portal = config.get("portal", {})
    parser = argparse.ArgumentParser(description="Portal local de aplicaciones.")
    parser.add_argument("--host", default=os.getenv("PORTAL_HOST", str(portal.get("host", "127.0.0.1"))))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORTAL_PORT", str(portal.get("port", 9000)))))
    parser.add_argument("--open", action="store_true")
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), PortalHandler)
    url = f"http://{args.host}:{args.port}"
    print(f"Portal de aplicaciones: {url}")
    if args.open:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nPortal detenido.")


if __name__ == "__main__":
    main()
