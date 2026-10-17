# Part B: the web harness in one container.
# The Part A project (CLAUDE.md, .claude/, scripts/, data/, outputs/) is baked
# in unchanged; every run works on its own copy under $RUNS_DIR.
FROM python:3.13-slim

# poppler-utils: pdftotext/pdfinfo for the agents and verifiers;
# perl: shasum, which the agent procedures use for hash checks.
RUN apt-get update \
 && apt-get install -y --no-install-recommends poppler-utils perl grep findutils \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./requirements.txt
COPY harness/requirements.txt ./harness/requirements.txt
RUN pip install --no-cache-dir -r harness/requirements.txt

COPY . .

# Agents run shell commands, so the server runs as an unprivileged user that
# can write only to the runs volume.
RUN useradd --create-home --uid 10001 app \
 && mkdir -p /data/runs && chown -R app:app /data/runs
USER app

ENV RUNS_DIR=/data/runs \
    PYTHONUNBUFFERED=1 \
    PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn harness.app:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
