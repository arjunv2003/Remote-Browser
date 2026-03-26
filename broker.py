"""
broker.py — SocioShop Browser Broker
Run:  uvicorn broker:app --host 0.0.0.0 --port 8000 --reload
"""

import asyncio
import os
import re
import socket
import hashlib
import docker
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from urllib.parse import urlencode

load_dotenv()

app = FastAPI(title="SocioShop Browser Broker")

MY_IP = os.getenv("MY_IP", "localhost")
PORT_START = int(os.getenv("PORT_START", "6080"))
PORT_END = int(os.getenv("PORT_END", "6180"))
NEKO_UDP_PORT_START = int(os.getenv("NEKO_UDP_PORT_START", "52000"))
NEKO_UDP_PORTS_PER_SESSION = int(os.getenv("NEKO_UDP_PORTS_PER_SESSION", "32"))
NEKO_IMAGE = os.getenv("NEKO_IMAGE", "socioshop-browser:latest")
NEKO_USER_PASSWORD = os.getenv("NEKO_USER_PASSWORD", "shopper")
NEKO_ADMIN_PASSWORD = os.getenv("NEKO_ADMIN_PASSWORD", "admin")
NEKO_SCREEN = os.getenv("NEKO_SCREEN", "1280x720@30")
SESSION_BOOT_SECONDS = int(os.getenv("SESSION_BOOT_SECONDS", "10"))

sessions: dict[str, dict] = {}
docker_client = docker.from_env()


class StartRequest(BaseModel):
    order_id: str
    start_url: str = "https://www.google.com"


class SessionResponse(BaseModel):
    order_id: str
    container_id: str
    browser_url: str
    status: str
    created_at: str


def free_port() -> int:
    used = {s["port"] for s in sessions.values()}
    for p in range(PORT_START, PORT_END + 1):
        if p not in used and _port_available(p):
            return p
    raise Exception("No free ports")


def free_udp_block() -> tuple[int, int]:
    size = max(1, NEKO_UDP_PORTS_PER_SESSION)
    used_ports = set()
    for session in sessions.values():
        used_ports.update(range(session["udp_start"], session["udp_end"] + 1))

    candidate = NEKO_UDP_PORT_START
    while candidate + size - 1 <= 65535:
        block = range(candidate, candidate + size)
        if all(port not in used_ports for port in block) and _port_range_available(
            candidate, candidate + size - 1, socket.SOCK_DGRAM
        ):
            return candidate, candidate + size - 1
        candidate += size

    raise Exception("No free UDP port blocks")


def container_name(order_id: str) -> str:
    # Docker name must match: [a-zA-Z0-9][a-zA-Z0-9_.-]+
    # Use a short stable hash suffix to avoid collisions.
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "-", order_id).strip("-._")
    if not safe:
        safe = "order"
    suffix = hashlib.sha1(order_id.encode("utf-8")).hexdigest()[:8]
    return f"browser-{safe[:30]}-{suffix}".lower()


def _port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("0.0.0.0", port))
        except OSError:
            return False
        return True


def _port_range_available(start: int, end: int, sock_type: int) -> bool:
    sockets = []
    try:
        for port in range(start, end + 1):
            sock = socket.socket(socket.AF_INET, sock_type)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("0.0.0.0", port))
            sockets.append(sock)
    except OSError:
        return False
    finally:
        for sock in sockets:
            sock.close()
    return True


@app.post("/sessions/start", response_model=SessionResponse)
async def start_session(req: StartRequest):
    try:
        docker_client.ping()
    except Exception as e:
        raise HTTPException(
            503,
            f"Docker not reachable from broker. Is Docker running and do you have access to the Docker socket? ({e})",
        )

    # Return existing session if already running
    if req.order_id in sessions:
        s = sessions[req.order_id]
        return SessionResponse(
            **{k: v for k, v in s.items() if k in SessionResponse.model_fields}
        )

    port = free_port()
    udp_start, udp_end = free_udp_block()
    name = container_name(req.order_id)

    # Clean up any leftover container with the same name
    try:
        docker_client.containers.get(name).remove(force=True)
        print(f"  🧹 Removed old container: {name}")
    except Exception:
        pass

    print(f"\n🚀 Order {req.order_id} → port {port}...")

    port_bindings = {"8080/tcp": port}
    for udp_port in range(udp_start, udp_end + 1):
        port_bindings[f"{udp_port}/udp"] = udp_port

    environment = {
        "NEKO_DESKTOP_SCREEN": NEKO_SCREEN,
        "NEKO_MEMBER_MULTIUSER_USER_PASSWORD": NEKO_USER_PASSWORD,
        "NEKO_MEMBER_MULTIUSER_ADMIN_PASSWORD": NEKO_ADMIN_PASSWORD,
        "NEKO_WEBRTC_EPR": f"{udp_start}-{udp_end}",
        "NEKO_WEBRTC_NAT1TO1": MY_IP,
        "NEKO_WEBRTC_ICELITE": "1",
        "START_URL": req.start_url,
    }

    container = docker_client.containers.run(
        image=NEKO_IMAGE,
        detach=True,
        auto_remove=True,
        name=name,
        ports=port_bindings,
        environment=environment,
        cap_add=["SYS_ADMIN"],
        shm_size="2g",
        mem_limit="1g",
    )

    await asyncio.sleep(SESSION_BOOT_SECONDS)

    browser_url = f"http://{MY_IP}:{port}/?{urlencode({'usr': req.order_id, 'pwd': NEKO_USER_PASSWORD})}"

    session = {
        "order_id": req.order_id,
        "container_id": container.id[:12],
        "container_name": name,
        "port": port,
        "udp_start": udp_start,
        "udp_end": udp_end,
        "browser_url": browser_url,
        "status": "ready",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    sessions[req.order_id] = session

    print(f"  ✅ Ready → {browser_url}")
    return SessionResponse(
        **{k: v for k, v in session.items() if k in SessionResponse.model_fields}
    )


@app.delete("/sessions/{order_id}")
async def end_session(order_id: str, background_tasks: BackgroundTasks):
    if order_id not in sessions:
        raise HTTPException(404, "Session not found")
    s = sessions.pop(order_id)

    def stop():
        try:
            docker_client.containers.get(s["container_name"]).stop(timeout=5)
            print(f"  🗑  Stopped: {s['container_name']}")
        except Exception:
            pass

    background_tasks.add_task(stop)
    return {"message": "Session ended", "order_id": order_id}


@app.get("/sessions")
async def list_sessions():
    return {
        "active": len(sessions),
        "sessions": [
            {
                "order_id": s["order_id"],
                "browser_url": s["browser_url"],
                "status": s["status"],
            }
            for s in sessions.values()
        ],
    }


@app.get("/health")
async def health():
    try:
        docker_client.ping()
        docker_ok = True
    except Exception:
        docker_ok = False
    return {"status": "ok", "docker": docker_ok, "active_sessions": len(sessions)}


@app.get("/", response_class=HTMLResponse)
async def ui():
    # Minimal ops UI for phase-1 testing (no auth).
    return HTMLResponse(
        f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>SocioShop Browser Broker</title>
  <style>
    body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; padding: 16px; max-width: 920px; margin: 0 auto; }}
    input {{ padding: 10px; width: 100%; box-sizing: border-box; }}
    button {{ padding: 10px 14px; cursor: pointer; }}
    .row {{ display: grid; grid-template-columns: 1fr 2fr auto; gap: 10px; align-items: end; }}
    .card {{ border: 1px solid #ddd; border-radius: 12px; padding: 12px; margin-top: 16px; }}
    .muted {{ color: #666; }}
    .sessions {{ display: grid; gap: 10px; margin-top: 10px; }}
    .session {{ border: 1px solid #eee; border-radius: 10px; padding: 10px; display: grid; gap: 6px; }}
    a {{ color: #0b57d0; }}
    code {{ background: #f6f6f6; padding: 2px 6px; border-radius: 6px; }}
  </style>
</head>
<body>
  <h2>SocioShop Browser Broker</h2>
  <div class="muted">Creates per-order Neko remote browser containers on TCP ports <code>{PORT_START}</code>–<code>{PORT_END}</code> plus per-session UDP WebRTC ranges starting at <code>{NEKO_UDP_PORT_START}</code>.</div>

  <div class="card">
    <div class="row">
      <div>
        <label>Order ID</label>
        <input id="order_id" placeholder="order-123" />
      </div>
      <div>
        <label>Start URL</label>
        <input id="start_url" value="https://www.google.com" />
        
      </div>
      <div>
        <button id="start_btn">Start</button>
      </div>
    </div>
  </div>

  <div class="card">
    <div style="display:flex; align-items:center; justify-content:space-between; gap:10px;">
      <h3 style="margin:0;">Active Sessions</h3>
      <button id="refresh_btn">Refresh</button>
    </div>
    <div id="sessions" class="sessions"></div>
    <div id="empty" class="muted" style="margin-top:10px; display:none;">No sessions.</div>
  </div>

  <script>
    async function refresh() {{
      const res = await fetch('/sessions');
      const data = await res.json();
      const root = document.getElementById('sessions');
      root.innerHTML = '';
      document.getElementById('empty').style.display = data.sessions.length ? 'none' : 'block';
      for (const s of data.sessions) {{
        const div = document.createElement('div');
        div.className = 'session';
        div.innerHTML = `
          <div><b>${{s.order_id}}</b> <span class="muted">(${{s.status}})</span></div>
          <div><a href="${{s.browser_url}}" target="_blank" rel="noreferrer">Open Remote Browser</a></div>
          <div style="display:flex; gap:8px; align-items:center;">
            <button data-end="${{s.order_id}}">End</button>
            <span class="muted">${{s.browser_url}}</span>
          </div>
        `;
        div.querySelector('button').addEventListener('click', async (e) => {{
          const orderId = e.target.getAttribute('data-end');
          await fetch(`/sessions/${{encodeURIComponent(orderId)}}`, {{ method: 'DELETE' }});
          await refresh();
        }});
        root.appendChild(div);
      }}
    }}

    document.getElementById('refresh_btn').addEventListener('click', refresh);
    document.getElementById('start_btn').addEventListener('click', async () => {{
      const order_id = document.getElementById('order_id').value.trim();
      const start_url = document.getElementById('start_url').value.trim() || 'https://www.google.com';
      if (!order_id) {{
        alert('Order ID required');
        return;
      }}
      const res = await fetch('/sessions/start', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ order_id, start_url }})
      }});
      if (!res.ok) {{
        const txt = await res.text();
        alert(txt);
        return;
      }}
      await refresh();
    }});

    refresh();
  </script>
</body>
</html>
""".strip()
    )
