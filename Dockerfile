FROM node:22-alpine AS assets
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY static ./static
RUN npm run vendor

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN groupadd --gid 1000 app && useradd --uid 1000 --gid app --create-home app
COPY --chown=app:app . .
COPY --from=assets /app/static/vendor ./static/vendor
RUN mkdir -p /app/data /app/media /app/staticfiles && chown -R app:app /app
USER app
RUN python manage.py collectstatic --noinput
CMD ["sh", "-c", "python manage.py migrate && gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --timeout 30 --max-requests 1000 --max-requests-jitter 100 --access-logfile - --error-logfile -"]
