#!/bin/sh
set -e

echo "» Aplicando migrations"
python manage.py migrate --noinput

if [ "${CARREGAR_DEMO:-0}" = "1" ]; then
    echo "» Dados de demonstração (só se o banco estiver vazio)"
    python manage.py carregar_demo --se-vazio
fi

echo "» Compilando o CSS do painel (Tailwind)"
tailwindcss -i assets/painel.css -o static/painel/painel.css --minify

exec "$@"
