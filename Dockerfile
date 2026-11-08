FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
# gunicorn is the production server; it runs on Linux only, so it lives here rather than in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt gunicorn==23.0.0
COPY . .
EXPOSE 5000
# --preload builds the app once before the workers start: one database setup, one shared secret key
CMD ["gunicorn", "--preload", "--workers", "2", "--bind", "0.0.0.0:5000", "run:app"]
