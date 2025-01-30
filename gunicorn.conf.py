import os

# Gunicorn configuration
bind = "0.0.0.0:3000"  # Bind to all interfaces on port 3000
workers = 1             # Number of worker processes
timeout = 120           # Timeout for requests in seconds