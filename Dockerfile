# Bot image. Deliberately excludes the research stack: matplotlib and yfinance
# add ~144 MB and nothing under core/ or bot/ imports them.
FROM python:3.14-slim AS builder

WORKDIR /build
COPY requirements-bot.txt .
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
 && /opt/venv/bin/pip install --no-cache-dir -r requirements-bot.txt


FROM python:3.14-slim

# Run unprivileged: the bot holds live broker credentials.
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin bot

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY core/ ./core/
COPY bot/ ./bot/

# State lives here. Owned by the runtime user so a named volume inherits the
# right ownership; a host bind mount must be chowned to 10001 on the host, or
# SQLite cannot create the file.
RUN mkdir -p /app/data && chown -R bot:bot /app/data
VOLUME ["/app/data"]
ENV BOT_DB_PATH=/app/data/bot.db

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER bot

# One-shot: evaluate the latest bar, act, exit. Scheduling is external
# (systemd timer or cron), so there is no daemon loop to supervise.
CMD ["python", "-m", "bot.run"]
