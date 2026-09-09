FROM python:3.12-slim

RUN groupadd --system appgroup && \
    useradd --system --gid appgroup --home /home/appuser --create-home appuser

WORKDIR /app

# Install MySQL client tools (mysqldump + mysql) and Android APK signature
# verifier. The private signing key remains in EAS; the server only verifies.
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends default-mysql-client apksigner && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data/mobile-releases && \
    chmod 0750 /app/data/mobile-releases && \
    chmod +x entrypoint.sh && \
    chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

CMD ["sh", "entrypoint.sh"]
