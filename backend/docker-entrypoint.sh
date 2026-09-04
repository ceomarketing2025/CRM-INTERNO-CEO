#!/bin/sh
set -e

python manage.py check
# V3: si aún no existen migraciones, las genera para permitir levantar el demo inmediatamente.
python manage.py makemigrations accounts clients plans projects domains questionnaires design resources marketing operations reminders finance audit --noinput
python manage.py migrate --noinput
python manage.py seed_initial_data

if [ "${AUTO_BOOTSTRAP_MANAGER:-false}" = "true" ]; then
  python manage.py bootstrap_manager
fi

python manage.py runserver 0.0.0.0:8000 --noreload
