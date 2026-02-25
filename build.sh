#!/usr/bin/env bash
# exit on error
set -o errexit

# 1. Install dependencies
pip install -r requirements.txt

# 2. Go to backend folder (where manage.py lives)
cd backend

# 3. Collect Static Files (CSS/JS)
python manage.py collectstatic --noinput

# 4. Migrate Database (Apply changes to Postgres)
python manage.py migrate

# 5. Asked in the terminal to create a new SuperUser (Admin) is not created. (RENDER)
python create_superuser.py