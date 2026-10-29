FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PORT=8000 APP_ENV=production
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
COPY backend/engine/requirements.txt backend/engine/requirements.txt
RUN python -m pip install --no-cache-dir --only-binary=:all: --upgrade "pip>=26.2.0" \
    && python -m pip install --no-cache-dir -r backend/requirements.txt \
    && python -m pip uninstall --yes pip
COPY backend/ backend/
COPY LICENSE LICENSE
RUN useradd --create-home appuser
USER appuser
EXPOSE 8000
CMD ["sh", "-c", "exec python -m uvicorn main:app --app-dir backend --host 0.0.0.0 --port $PORT --workers 1 --no-access-log"]
