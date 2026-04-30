FROM python:3.12-slim

RUN groupadd --system appgroup && \
    useradd --system --gid appgroup --home /home/appuser --create-home appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x entrypoint.sh && \
    chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

CMD ["./entrypoint.sh"]
