## SocioShop Remote Browser (Phase 1)

This repo spins up **one remote Chromium browser per order** in a Docker container and exposes it via **Neko** so an employee can complete checkout on any website from a phone/laptop.

### What you get

- `broker.py`: FastAPI “broker” that allocates a port, starts/stops a container, and returns a shareable `browser_url`.
- `dockerfile`: Thin wrapper image built from `ghcr.io/m1k1o/neko/chromium:latest`.

### Quick start (local)

1) Set your LAN IP in `.env` (this is what your phone will use to open the session URL):

- `MY_IP=192.168.x.x`
- `NEKO_UDP_PORT_START=52000`
- `NEKO_UDP_PORTS_PER_SESSION=32`

2) Build the browser image:

- `docker build -t socioshop-browser:latest .`

3) Start the broker:

- `pip install -r requirements.txt`
- `uvicorn broker:app --host 0.0.0.0 --port 8000 --reload`

4) Open the broker UI:

- `http://localhost:8000/`

When you click **Start**, the UI will show an **Open Remote Browser** link like:

- `http://MY_IP:6080/?usr=order-123&pwd=shopper`

Open that from your phone (same network) to control the remote Chromium session.

Notes:

- Neko uses WebRTC, so each session needs one TCP port for the web UI plus a dedicated UDP range for media/control traffic.
- The broker maps a unique UDP block per order using `NEKO_UDP_PORT_START` and `NEKO_UDP_PORTS_PER_SESSION`.
- The returned URL prefills the Neko username/password for the regular shopper role.

### API (if you don’t want the UI)

- Start: `POST /sessions/start` with JSON `{"order_id":"order-123","start_url":"https://example.com"}`
- List: `GET /sessions`
- End: `DELETE /sessions/{order_id}`

Startup behavior:

- `start_url` is passed into the container and opened by Chromium on session boot.
