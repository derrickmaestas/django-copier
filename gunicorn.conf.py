import multiprocessing

# Bind to all interfaces on port 8000
bind = "0.0.0.0:8000"

# Workers: 2 * CPU cores + 1 (gunicorn recommendation)
workers = multiprocessing.cpu_count() * 2 + 1

# Graceful restart timeout
timeout = 30
graceful_timeout = 30

# Access logging to stdout
accesslog = "-"
errorlog = "-"
loglevel = "info"
