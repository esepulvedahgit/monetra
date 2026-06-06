FROM python:3.12-slim

RUN groupadd --system appgroup && \
    useradd --system --gid appgroup --home /home/appuser --create-home appuser

WORKDIR /app

# Install MySQL client tools (mysqldump + mysql) needed for DB backup/restore.
RUN apt-get update && \
    apt-get install -y --no-install-recommends default-mysql-client && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x entrypoint.sh && \
    chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

CMD ["sh", "entrypoint.sh"]
