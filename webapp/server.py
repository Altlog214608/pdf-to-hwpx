"""PDF -> HWPX 변환 웹 서버 (FastAPI).

작업(job) 흐름
  1. POST /api/jobs                PDF 업로드 -> 분석(1쪽 그림, 제목 후보, 지문/문제 샘플)
  2. POST /api/jobs/{id}/logo      (선택) 학원 로고 그림
  3. POST /api/jobs/{id}/convert   스타일 옵션으로 HWPX 생성 -> 시간 제한 다운로드 링크
  4. GET  /api/jobs/{id}/download/{token}
  5. DELETE /api/jobs/{id}         페이지를 떠나면 브라우저가 호출(sendBeacon은 POST .../delete)

보관 정책(저작권 보호): 업로드 파일과 결과물은 서버 디스크의 작업 폴더에만 있고,
작업 보관 시간(JOB_TTL_MIN)이 지나거나 사용자가 페이지를 떠나면 폴더째 삭제된다.
다운로드 링크는 변환 후 DOWNLOAD_TTL_MIN 동안만 유효하다.
"""
from __future__ import annotations

import os
import secrets
import shutil
import sys
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pdf2hwpx import VERSION  # noqa: E402
from pdf2hwpx.convert import convert  # noqa: E402
from pdf2hwpx.preview import analyze  # noqa: E402
from pdf2hwpx.style import FONTS, DocStyle  # noqa: E402

DATA_DIR = Path(os.environ.get("DATA_DIR") or Path(tempfile.gettempdir()) / "pdf2hwpx_jobs")
JOB_TTL_MIN = float(os.environ.get("JOB_TTL_MIN", "30"))         # 업로드 후 작업 보관 시간
DOWNLOAD_TTL_MIN = float(os.environ.get("DOWNLOAD_TTL_MIN", "10"))  # 변환 후 다운로드 가능 시간
MAX_MB = float(os.environ.get("MAX_MB", "40"))
MAX_PAGES = int(os.environ.get("MAX_PAGES", "80"))
MAX_LOGO_KB = 2048
DATA_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class Job:
    id: str
    dir: Path
    filename: str
    created: float = field(default_factory=time.time)
    logo: Optional[bytes] = None
    token: Optional[str] = None
    download_until: float = 0.0
    hwpx: Optional[Path] = None
    lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def pdf(self) -> Path:
        return self.dir / "source.pdf"

    @property
    def expires(self) -> float:
        return self.created + JOB_TTL_MIN * 60


JOBS: dict[str, Job] = {}
JOBS_LOCK = threading.Lock()


def _delete(job_id: str) -> None:
    with JOBS_LOCK:
        job = JOBS.pop(job_id, None)
    if job:
        shutil.rmtree(job.dir, ignore_errors=True)


def _sweeper() -> None:
    while True:
        time.sleep(30)
        now = time.time()
        for jid, job in list(JOBS.items()):
            if now > job.expires:
                _delete(jid)
        # 서버 재시작 등으로 남은 폴더 정리
        for d in DATA_DIR.iterdir():
            if d.is_dir() and d.name not in JOBS and now - d.stat().st_mtime > JOB_TTL_MIN * 60:
                shutil.rmtree(d, ignore_errors=True)


threading.Thread(target=_sweeper, daemon=True).start()

app = FastAPI(title="PDF → HWPX", version=VERSION, docs_url=None, redoc_url=None)


def _get(job_id: str) -> Job:
    job = JOBS.get(job_id)
    if job is None or time.time() > job.expires:
        _delete(job_id)
        raise HTTPException(404, "작업이 만료되었거나 없습니다. PDF를 다시 올려 주세요.")
    return job


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "version": VERSION, "jobs": len(JOBS)}


@app.get("/api/config")
def config() -> dict:
    return {"version": VERSION, "fonts": FONTS, "max_mb": MAX_MB, "max_pages": MAX_PAGES,
            "job_ttl_min": JOB_TTL_MIN, "download_ttl_min": DOWNLOAD_TTL_MIN}


@app.post("/api/jobs")
def create_job(file: UploadFile = File(...)) -> JSONResponse:
    data = file.file.read(int(MAX_MB * 1024 * 1024) + 1)
    if len(data) > MAX_MB * 1024 * 1024:
        raise HTTPException(413, f"파일이 너무 큽니다 (최대 {MAX_MB:g}MB).")
    if not data.startswith(b"%PDF"):
        raise HTTPException(415, "PDF 파일만 올릴 수 있습니다.")
    jid = uuid.uuid4().hex
    jdir = DATA_DIR / jid
    jdir.mkdir(parents=True)
    job = Job(jid, jdir, Path(file.filename or "document.pdf").name)
    job.pdf.write_bytes(data)
    try:
        info = analyze(str(job.pdf))
    except Exception as e:
        shutil.rmtree(jdir, ignore_errors=True)
        raise HTTPException(422, f"PDF를 읽을 수 없습니다: {type(e).__name__}")
    tl = info["text_layer"]
    if tl["pages"] > MAX_PAGES:
        shutil.rmtree(jdir, ignore_errors=True)
        raise HTTPException(413, f"페이지가 너무 많습니다 (최대 {MAX_PAGES}쪽).")
    (jdir / "page1.png").write_bytes(info.pop("page1_png"))
    with JOBS_LOCK:
        JOBS[jid] = job
    return JSONResponse({
        "id": jid, "filename": job.filename, "expires_at": job.expires, "job_seconds": int(JOB_TTL_MIN * 60),
        "page1": f"/api/jobs/{jid}/page1.png", **info,
    })


@app.get("/api/jobs/{job_id}/page1.png")
def page1(job_id: str) -> FileResponse:
    job = _get(job_id)
    return FileResponse(job.dir / "page1.png", media_type="image/png", headers={"Cache-Control": "private, max-age=600"})


@app.post("/api/jobs/{job_id}/logo")
def upload_logo(job_id: str, file: UploadFile = File(...)) -> dict:
    job = _get(job_id)
    data = file.file.read(MAX_LOGO_KB * 1024 + 1)
    if len(data) > MAX_LOGO_KB * 1024:
        raise HTTPException(413, "로고 그림은 2MB까지 올릴 수 있습니다.")
    try:
        import pymupdf as fitz
        pix = fitz.Pixmap(data)
        w, h = pix.width, pix.height
    except Exception:
        raise HTTPException(415, "PNG 또는 JPG 그림만 올릴 수 있습니다.")
    job.logo = data
    return {"ok": True, "width": w, "height": h}


@app.delete("/api/jobs/{job_id}/logo")
def delete_logo(job_id: str) -> dict:
    _get(job_id).logo = None
    return {"ok": True}


@app.post("/api/jobs/{job_id}/convert")
async def convert_job(job_id: str, request: Request) -> dict:
    job = _get(job_id)
    try:
        opts = await request.json()
    except Exception:
        opts = {}
    style = DocStyle.from_dict(opts or {}, logo=job.logo if opts.get("use_logo", True) else None)
    from starlette.concurrency import run_in_threadpool

    def work() -> dict:
        with job.lock:
            out = job.dir / "out"
            shutil.rmtree(out, ignore_errors=True)
            out.mkdir()
            name = Path(job.filename).stem + ".hwpx"
            res = convert(str(job.pdf), hwpx_path=str(out / name), write_json=False, style=style)
            job.hwpx = out / name
            job.token = secrets.token_urlsafe(16)
            job.download_until = min(time.time() + DOWNLOAD_TTL_MIN * 60, job.expires)
            return res

    try:
        res = await run_in_threadpool(work)
    except Exception as e:
        raise HTTPException(500, f"변환 중 오류가 발생했습니다: {type(e).__name__}")
    v = res["validation"]
    c = v["checks"]
    return {
        "download_url": f"/api/jobs/{job_id}/download/{job.token}",
        "download_until": job.download_until,
        "seconds_left": max(0, int(job.download_until - time.time())),
        "filename": job.hwpx.name, "size": job.hwpx.stat().st_size,
        "status": v["status"], "root_causes": v["root_causes"], "warnings": v["warnings"][:5],
        "summary": {"questions": c.get("question_count"), "objective": c.get("objective"),
                    "subjective": c.get("subjective"), "boxes": c.get("box_groups"),
                    "pictures": c.get("pictures"), "answers": c.get("answer_count"),
                    "coverage": c.get("text_coverage")},
    }


@app.get("/api/jobs/{job_id}/download/{token}")
def download(job_id: str, token: str) -> FileResponse:
    job = _get(job_id)
    if not job.token or not secrets.compare_digest(token, job.token) or job.hwpx is None:
        raise HTTPException(404, "다운로드 링크가 올바르지 않습니다.")
    if time.time() > job.download_until:
        raise HTTPException(410, "다운로드 가능 시간이 지났습니다. 다시 변환해 주세요.")
    disp = f"attachment; filename=\"document.hwpx\"; filename*=UTF-8''{quote(job.hwpx.name)}"
    return FileResponse(job.hwpx, media_type="application/hwp+zip", headers={"Content-Disposition": disp})


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str) -> dict:
    _delete(job_id)
    return {"ok": True}


@app.post("/api/jobs/{job_id}/delete")  # navigator.sendBeacon 용 (페이지를 떠날 때)
def delete_job_beacon(job_id: str) -> Response:
    _delete(job_id)
    return Response(status_code=204)


app.mount("/", StaticFiles(directory=str(Path(__file__).parent / "static"), html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "8000")))
