#!/bin/bash
# Build script for Railway/Render deployment
set -e

echo "=== Installing Python dependencies ==="
pip install -r requirements.txt

echo "=== Running migrations ==="
python manage.py migrate --no-input

echo "=== Collecting static files ==="
python manage.py collectstatic --no-input

echo "=== Setting up demo user ==="
python manage.py setup_demo || true

echo "=== Build complete ==="
