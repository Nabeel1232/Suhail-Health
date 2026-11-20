FROM python:3.13.11-slim@sha256:2b9c9803c6a287cafa0a8c917211dddd23dcd2016f049690ee5219f5d3f1636e
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY services services
COPY integrations integrations
COPY pathways pathways
COPY evals evals
COPY scripts scripts
COPY docs docs
RUN useradd -u 10001 -m suhail && mkdir -p /app/runtime /app/.runtime /app/reports/runs && chown -R suhail:suhail /app
USER suhail
EXPOSE 8000
CMD ["python","-m","services.api.serve"]
