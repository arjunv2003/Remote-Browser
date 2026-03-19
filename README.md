## SocioShop Remote Browser (Phase 1)

This repo spins up **one remote Chromium browser per order** in a Docker container and exposes it via **noVNC** so an employee can complete checkout on any website from a phone/laptop.

### What you get

- `broker.py`: FastAPI “broker” that allocates a port, starts/stops a container, and returns a shareable `browser_url`.
- `dockerfile` + `supervisord.conf`: Container image that runs Xvfb + x11vnc + noVNC + Chromium.

### Quick start (local)

1) Set your LAN IP in `.env` (this is what your phone will use to open the session URL):

- `MY_IP=192.168.x.x`

2) Build the browser image:

- `docker build -t socioshop-browser:latest .`

3) Start the broker:

- `pip install -r requirements.txt`
- `uvicorn broker:app --host 0.0.0.0 --port 8000 --reload`

4) Open the broker UI:

- `http://localhost:8000/`

When you click **Start**, the UI will show an **Open Remote Browser** link like:

- `http://MY_IP:6080/?autoconnect=true&resize=scale&quality=8`

Open that from your phone (same network) to control the remote Chromium session.

### API (if you don’t want the UI)

- Start: `POST /sessions/start` with JSON `{"order_id":"order-123","start_url":"https://example.com"}`
- List: `GET /sessions`
- End: `DELETE /sessions/{order_id}`
