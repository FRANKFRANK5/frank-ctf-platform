#!/bin/bash
set -euo pipefail
set -x

# Mpangilio wa msingi (Defaults)
WORKERS=${WORKERS:-1}
WORKER_CLASS=${WORKER_CLASS:-gevent}
ACCESS_LOG=${ACCESS_LOG:--}
ERROR_LOG=${ERROR_LOG:--}
WORKER_TEMP_DIR=${WORKER_TEMP_DIR:-/dev/shm}
SECRET_KEY=${SECRET_KEY:-}
SKIP_DB_PING=${SKIP_DB_PING:-false}

# 1. USALAMA: Angalia Secret Key
# Kama una workers wengi, sessions lazima ziwe signed kwa key moja inayofanana
echo "[ STEP 1 ] Checking SECRET_KEY configuration..."
if [ ! -f .ctfd_secret_key ] && [ -z "$SECRET_KEY" ]; then
    if [ "$WORKERS" -gt 1 ]; then
        echo "----------------------------------------------------------------------"
        echo "[ ERROR ] You are configured to use more than 1 worker ($WORKERS)."
        echo "[ ERROR ] To do this, you must define the SECRET_KEY environment variable."
        echo "[ ERROR ] Tip: Generate one using: python -c 'import os; print(os.urandom(16).hex())'"
        echo "----------------------------------------------------------------------"
        exit 1
    fi
fi

# 2. DATABASE PING: Hakikisha MySQL/MariaDB imeshawaka kabisa
if [[ "$SKIP_DB_PING" == "false" ]]; then
  echo "[ STEP 2 ] Checking database connection via ping.py..."
  python - <<'EOF' || { echo "[ ERROR ] ping.py failed — database may be unreachable. Check DATABASE_URL and that the database service is running."; exit 1; }
import sys
try:
    import time
    from sqlalchemy import create_engine
    from sqlalchemy.engine.url import make_url
    from CTFd.config import Config

    url = make_url(Config.DATABASE_URL)

    if url.drivername.startswith("sqlite"):
        print("SQLite detected — skipping ping.")
        sys.exit(0)

    url = url._replace(database=None)
    engine = create_engine(url)
    print(f"Waiting for {url.host} to be ready")
    while True:
        try:
            engine.raw_connection()
            break
        except Exception as e:
            print(f"  Connection attempt failed: {e}")
            print("  Waiting 1s for database connection")
            time.sleep(1)

    print(f"{url.host} is ready")
    time.sleep(1)
except Exception as e:
    print(f"[ ERROR ] Unexpected error in database ping: {e}", file=sys.stderr)
    sys.exit(1)
EOF
  echo "[ STEP 2 ] Database ping succeeded."
fi

# 3. DATABASE UPGRADE: Tengeneza au sasisha table za database
echo "[ STEP 3 ] Running database migrations (flask db upgrade)..."
flask db upgrade || { echo "[ ERROR ] flask db upgrade failed — check migration files and database connectivity."; exit 1; }
echo "[ STEP 3 ] Database migrations completed successfully."

# 4. START GUNICORN: Washa injini ya CTFd
echo "[ STEP 4 ] Starting CTFd with $WORKERS workers..."
exec gunicorn 'CTFd:create_app()' \
    --bind '0.0.0.0:8000' \
    --workers "$WORKERS" \
    --worker-tmp-dir "$WORKER_TEMP_DIR" \
    --worker-class "$WORKER_CLASS" \
    --access-logfile "$ACCESS_LOG" \
    --error-logfile "$ERROR_LOG"