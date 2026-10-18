#!/bin/sh
set -e

echo "Starting Bulwark DeFi Intelligence Platform..."

# If FalkorDB host is specified, test connection and seed graph
if [ -n "$FALKORDB_HOST" ]; then
  echo "Connecting to FalkorDB at $FALKORDB_HOST:${FALKORDB_PORT:-6379}..."
  
  python3 - << 'EOF'
import os
import time
import sys
from falkordb import FalkorDB

host = os.getenv("FALKORDB_HOST", "localhost")
port = int(os.getenv("FALKORDB_PORT", "6379"))
password = os.getenv("FALKORDB_PASSWORD") or None

print(f"Waiting for FalkorDB at {host}:{port}...")
connected = False
for attempt in range(1, 16):
    try:
        kwargs = {"host": host, "port": port}
        if password:
            kwargs["password"] = password
        db = FalkorDB(**kwargs)
        db.list_graphs()
        print(f"Connected to FalkorDB successfully on attempt {attempt}!")
        connected = True
        break
    except Exception as exc:
        print(f"FalkorDB not ready yet (attempt {attempt}/15)... retrying in 2s")
        time.sleep(2)

if not connected:
    print("Warning: Could not connect to FalkorDB after 15 attempts. Continuing to start web server...")
EOF

  echo "Running graph schema initialization and curated relationship seeding..."
  python3 scripts/seed_curated_relationships.py || echo "Warning: seed script finished with warnings, continuing..."
fi

# Launch Next.js web application
echo "Starting Next.js frontend on port ${PORT:-3000} (0.0.0.0)..."
cd Frontend
exec npx next start -p "${PORT:-3000}" -H 0.0.0.0
