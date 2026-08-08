FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY web_search_cli ./web_search_cli

RUN pip install --no-cache-dir . \
    && useradd --create-home --shell /usr/sbin/nologin wsp \
    && mkdir -p /home/wsp/.cache/web-search-cli /etc/web-search \
    && chown -R wsp:wsp /home/wsp /etc/web-search

USER wsp
ENV HOME=/home/wsp \
    WSP_CACHE_DIR=/home/wsp/.cache/web-search-cli

ENTRYPOINT ["web-search-plus"]
