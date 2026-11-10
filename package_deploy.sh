#!/bin/sh
# Packages the FastAPI backend into a clean deployment ZIP for RamNaym Cloud
set -e

cd "$(dirname "$0")"
rm -f ../sortmyplate-backend-deploy.zip
zip -r ../sortmyplate-backend-deploy.zip app main.py requirements.txt Procfile .env.example \
  -x "*/__pycache__/*" "*.pyc" "*.DS_Store"

echo "✓ Created ../sortmyplate-backend-deploy.zip successfully!"
