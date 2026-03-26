FROM ghcr.io/m1k1o/neko/chromium:latest

COPY start-chromium-with-url.sh /usr/local/bin/start-chromium-with-url
RUN chmod +x /usr/local/bin/start-chromium-with-url

COPY neko-chromium.conf /etc/neko/supervisord/chromium.conf
