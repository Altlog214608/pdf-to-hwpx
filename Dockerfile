# PDF -> HWPX 웹 서비스 (FastAPI). 한글(Hancom) 없이 Linux에서 동작한다.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 PORT=8000 DATA_DIR=/tmp/pdf2hwpx_jobs \
    JOB_TTL_MIN=30 DOWNLOAD_TTL_MIN=10 MAX_MB=40 MAX_PAGES=80 MAX_FILES=10 MAX_TOTAL_PAGES=200

WORKDIR /app
# 두 requirements.txt는 이름이 같으므로 따로 복사한다. pytest(테스트용)는 넣지 않는다.
COPY requirements.txt ./req/core.txt
COPY webapp/requirements.txt ./req/web.txt
RUN sed -i '/pytest/d' req/core.txt && pip install --no-cache-dir -r req/core.txt -r req/web.txt

COPY pdf2hwpx ./pdf2hwpx
COPY webapp ./webapp

RUN useradd --create-home --uid 10001 app
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request,os;urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/healthz')"
CMD ["python", "webapp/server.py"]
