FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# static、templates 都在 app/ 內；seed 與 migrations 一併帶入（見 deploy/README.md 的打包注意事項）
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./
COPY seed ./seed
RUN useradd -r -u 10001 appuser && chown -R appuser /srv
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/healthz', timeout=3)"
# --proxy-headers：在 DSM 反向代理後面才拿得到真實協定；真實 IP 另由 TRUST_PROXY 控制
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
