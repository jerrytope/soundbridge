FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000
WORKDIR /app
# mysqlclient publishes no Linux wheels, so it is compiled here: pkg-config and
# the client headers are needed at build time, and the shared library at runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
      clamav ca-certificates build-essential pkg-config default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
RUN useradd --create-home soundbridge && mkdir -p /app/.data/artifacts /var/lib/clamav && chown -R soundbridge:soundbridge /app /var/lib/clamav /var/log/clamav
COPY --chown=soundbridge:soundbridge . .
USER soundbridge
RUN SOUNDBRIDGE_PUBLIC_ORIGIN='' python manage.py collectstatic --noinput
EXPOSE 8000
# Any HTTP response means Gunicorn is serving. A 403 is the expected answer here:
# the request policy compares the Host header against the configured public
# origin, and this probe connects to the loopback address instead.
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import os, urllib.request, urllib.error; url='http://127.0.0.1:'+os.environ.get('PORT','8000')+'/api/health';\
 exec('try:\n urllib.request.urlopen(url, timeout=4)\nexcept urllib.error.HTTPError:\n pass')" || exit 1
CMD ["sh", "-c", "gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 70"]
