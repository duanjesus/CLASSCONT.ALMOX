FROM python:3.13-slim

# - dependências ficam no venv DENTRO da imagem (não no bind mount do código);
# - caches de ferramentas vão para /cache (volume nomeado): no Windows/macOS,
#   escrever milhares de arquivos no bind mount deixa tudo muito lento.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    RUFF_CACHE_DIR=/cache/ruff \
    MYPY_CACHE_DIR=/cache/mypy \
    PYTEST_ADDOPTS="-o cache_dir=/cache/pytest" \
    TZ=America/Sao_Paulo

# Pango/HarfBuzz: exigidos pelo WeasyPrint (PDF). Fontes DejaVu para o PDF ter acentos.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-dejavu-core curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Tailwind CSS standalone (binário único, sem Node) para o CSS do painel em templates Django
ARG TAILWIND_VERSION=v4.3.3
ARG TARGETARCH
RUN case "$TARGETARCH" in arm64) arq=arm64 ;; *) arq=x64 ;; esac \
    && curl -fsSL -o /usr/local/bin/tailwindcss \
        "https://github.com/tailwindlabs/tailwindcss/releases/download/${TAILWIND_VERSION}/tailwindcss-linux-${arq}" \
    && chmod +x /usr/local/bin/tailwindcss

RUN python -m venv "$VIRTUAL_ENV"
WORKDIR /app
COPY backend/requirements.txt backend/requirements-dev.txt /tmp/
RUN pip install -r /tmp/requirements-dev.txt

COPY docker/python/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["entrypoint.sh"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
