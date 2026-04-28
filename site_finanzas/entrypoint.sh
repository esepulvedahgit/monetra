#!/bin/sh
set -e

echo "Waiting for MySQL..."
until python -c "
import os, pymysql, sys
try:
    pymysql.connect(
        host=os.getenv('DB_HOST','mysql'),
        port=int(os.getenv('DB_PORT',3306)),
        user=os.getenv('DB_USER',''),
        password=os.getenv('DB_PASSWORD',''),
        db=os.getenv('DB_NAME',''),
        connect_timeout=3
    ).close()
    sys.exit(0)
except Exception as e:
    print(e)
    sys.exit(1)
" 2>/dev/null; do
    sleep 2
done
echo "MySQL ready."

python init_db.py
exec gunicorn --workers 2 --bind 0.0.0.0:8000 --timeout 120 "run:app"
