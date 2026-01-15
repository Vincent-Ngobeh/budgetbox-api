#!/usr/bin/env bash
# Exit on error
set -o errexit

# Install dependencies
pip install -r requirements.txt

# Collect static files
python manage.py collectstatic --no-input

# Run database migrations
python manage.py migrate

# Seed demo user data (creates testuser with demo financial data)
# Only seeds if testuser doesn't exist, safe to run multiple times
python manage.py seed_user_data --user demo --password demo1234 --email demo@budgetbox.app
