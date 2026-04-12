# Gunicorn configuration for Captain Taxi Customer Service Agent
# Used in production on the Hostinger Linux VPS

import multiprocessing

# ── Workers ───────────────────────────────────────────────────────────────────
workers     = multiprocessing.cpu_count()      # 1 worker per CPU core
worker_class = "uvicorn.workers.UvicornWorker"
threads     = 1   # Uvicorn is async, no extra threads needed

# ── Network ───────────────────────────────────────────────────────────────────
bind        = "127.0.0.1:8000"
backlog     = 256

# ── Timeouts ──────────────────────────────────────────────────────────────────
timeout     = 60
keepalive   = 5
graceful_timeout = 30

# ── Logging ───────────────────────────────────────────────────────────────────
accesslog   = "/var/log/captain-taxi/customer-access.log"
errorlog    = "/var/log/captain-taxi/customer-error.log"
loglevel    = "info"
access_log_format = '%(h)s "%(r)s" %(s)s %(b)s %(D)sµs'

# ── Process name ─────────────────────────────────────────────────────────────
proc_name   = "captain-taxi-customer"

# ── Security ──────────────────────────────────────────────────────────────────
limit_request_line   = 8192
limit_request_fields = 100
