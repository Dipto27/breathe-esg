#!/usr/bin/env bash
set -e

echo "=== [1/4] Installing Node & building React frontend ==="
cd ../frontend
npm install
npm run build
cd ../backend

echo "=== [2/4] Installing Python dependencies ==="
pip install -r requirements.txt

echo "=== [3/4] Django: migrate + collectstatic ==="
python manage.py migrate --no-input
python manage.py collectstatic --no-input

echo "=== [4/4] Creating demo users ==="
python manage.py setup_demo || true

echo "=== Build complete ==="
