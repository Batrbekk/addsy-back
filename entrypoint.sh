#!/bin/bash
set -e

echo "Waiting for PostgreSQL at ${POSTGRES_HOST:-db}:${POSTGRES_PORT:-5432}..."

python << 'EOF'
import socket, time, os
host = os.getenv("POSTGRES_HOST", "db")
port = int(os.getenv("POSTGRES_PORT", "5432"))
for i in range(30):
    try:
        sock = socket.create_connection((host, port), timeout=2)
        sock.close()
        print(f"PostgreSQL is ready at {host}:{port}")
        break
    except OSError:
        print(f"Waiting... ({i+1}/30)")
        time.sleep(1)
else:
    print("Could not connect to PostgreSQL")
    exit(1)
EOF

echo "Running Alembic migrations..."
alembic upgrade head

echo "Starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 ${UVICORN_EXTRA_ARGS:-}
