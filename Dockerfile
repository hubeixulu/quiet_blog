FROM node:22-alpine AS assets
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm config set registry https://registry.npmmirror.com \
    && npm config set replace-registry-host always \
    && npm ci
COPY static ./static
COPY assets ./assets
RUN npm run vendor

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN find /etc/apt -type f \( -name "*.list" -o -name "*.sources" \) \
        -exec sed -i \
        -e 's|https*://deb.debian.org/debian-security|https://mirrors.aliyun.com/debian-security|g' \
        -e 's|https*://deb.debian.org/debian|https://mirrors.aliyun.com/debian|g' {} + \
    && apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir \
        --index-url https://mirrors.aliyun.com/pypi/simple/ \
        -r requirements.txt
RUN groupadd --gid 1000 app && useradd --uid 1000 --gid app --create-home app
COPY --chown=app:app . .
COPY --from=assets /app/static/vendor ./static/vendor
RUN mkdir -p /app/data /app/media /app/staticfiles && chown -R app:app /app
USER app
# Build static assets with the same storage backend used at runtime. The
# temporary key is used only during image construction and is not shipped as
# the production application secret.
RUN DJANGO_DEBUG=false \
    DJANGO_SECRET_KEY=collectstatic-only-build-key-000000000000000000000000 \
    python manage.py collectstatic --noinput
CMD ["sh", "-c", "python manage.py migrate && python manage.py collectstatic --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --timeout 30 --max-requests 1000 --max-requests-jitter 100 --access-logfile - --error-logfile -"]
