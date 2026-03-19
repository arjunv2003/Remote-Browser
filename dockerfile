FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV DISPLAY=:1

RUN apt-get update && apt-get install -y \
    xvfb \
    x11vnc \
    novnc \
    websockify \
    chromium \
    supervisor \
    ca-certificates \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Run Chromium as a non-root user so we don't need `--no-sandbox`.
RUN useradd -m -u 1000 -s /bin/bash browser \
    && mkdir -p /tmp/chrome-profile \
    && chown -R browser:browser /tmp/chrome-profile

# Hide Chromium's "unsupported command-line flag: --no-sandbox" infobar.
# Note: this does NOT make `--no-sandbox` safe; it only suppresses the warning UI.
RUN mkdir -p /etc/chromium/policies/managed \
    && printf '%s\n' '{"CommandLineFlagSecurityWarningsEnabled": false}' \
      > /etc/chromium/policies/managed/socioshop.json

# noVNC index page
RUN ln -sf /usr/share/novnc/vnc.html /usr/share/novnc/index.html

COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

EXPOSE 6080

CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
