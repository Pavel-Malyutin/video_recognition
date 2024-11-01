workers = 2
threads = 4
bind = ":8000"
worker_class = 'uvicorn.workers.UvicornH11Worker'
worker_connections = 100
max_requests = 2000
timeout = 300