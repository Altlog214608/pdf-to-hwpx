"""PDF -> HWPX 변환 웹 서버 (FastAPI).

작업(job) 흐름
  1. POST /api/jobs                PDF 업로드 -> 분석(1쪽 그림, 제목 후보, 지문/문제 샘플)
  2. POST /api/jobs/{id}/logo      (선택) 학원 로고 그림
  3. POST /api/jobs/{id}/convert   스타일 옵션으로 HWPX 생성 -> 시간 제한 다운로드 링크
  4. GET  /api/jobs/{id}/download/{token}
  5. DELETE /api/jobs/{id}         페이지를 떠나면 브라우저가 호출(sendBeacon은 POST .../delete)

여러 파일: 파일마다 1번으로 작업을 만든 뒤
  - POST /api/bundles/merge  {jobs, options}  한 파일로 잇기(문제·정답 번호를 이어서) -> 통합본 작업
  - POST /api/bundles/zip    {jobs}           따로 변환한 결과들을 ZIP 하나로 -> 묶음 작업
  묶음 작업도 일반 작업과 같은 다운로드/삭제/만료 규칙을 따른다.
변환은 서버 전체에서 한 번에 하나씩(CONVERT_LOCK) 처리한다: 작은 서버에서도 메모리가 넘치지 않게.

접속 제한(ACCESS_KEYS="이름:키,이름:키"): 설정하면 초대 링크 /join/{키}로 한 번 들어온 브라우저만
쿠키로 계속 쓸 수 있다. 사람마다 키가 따로라 한 사람만 끊을 수도 있다(키를 지우고 다시 배포).
설정하지 않으면(내 PC 실행) 제한 없음.

이용 기록(usage.py): 누가·언제·무엇을·몇 쪽/몇 문제만 SQLite(USAGE_DB)에 남긴다(파일 내용·이름은 남기지 않음).
관리자(ADMIN_USERS, 기본: ACCESS_KEYS의 첫 사람)만 /admin 에서 본다.

보관 정책(저작권 보호): 업로드 파일과 결과물은 서버 디스크의 작업 폴더에만 있고,
작업 보관 시간(JOB_TTL_MIN)이 지나거나 사용자가 페이지를 떠나면 폴더째 삭제된다.
다운로드 링크는 변환 후 DOWNLOAD_TTL_MIN 동안만 유효하다.
예외: 변환 결과가 '문제 있음'이거나 오류가 난 파일만 고치기 위해 SAMPLE_KEEP_DAYS(기본 14일) 동안 보관하고
관리자만 /admin 에서 내려받는다(samples.py, SAMPLE_KEEP_DAYS=0 이면 끔). 화면에 이 사실을 알린다.
"""
from __future__ import annotations

import os
import re
import secrets
import shutil
import sys
import tempfile
import threading
import time
import traceback
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pdf2hwpx import VERSION  # noqa: E402
from pdf2hwpx.convert import convert, convert_many  # noqa: E402
from pdf2hwpx.master_template import TemplateError, extract_template  # noqa: E402
from pdf2hwpx.preview import analyze  # noqa: E402
from pdf2hwpx.style import FONTS, DocStyle  # noqa: E402
from webapp.samples import SampleStore  # noqa: E402
from webapp.usage import EVENTS, UsageLog, device_of  # noqa: E402

DATA_DIR = Path(os.environ.get("DATA_DIR") or Path(tempfile.gettempdir()) / "pdf2hwpx_jobs")
JOB_TTL_MIN = float(os.environ.get("JOB_TTL_MIN", "30"))         # 업로드 후 작업 보관 시간
DOWNLOAD_TTL_MIN = float(os.environ.get("DOWNLOAD_TTL_MIN", "10"))  # 변환 후 다운로드 가능 시간
MAX_MB = float(os.environ.get("MAX_MB", "40"))
MAX_PAGES = int(os.environ.get("MAX_PAGES", "80"))
MAX_FILES = int(os.environ.get("MAX_FILES", "10"))                # 한 번에 올릴 수 있는 PDF 수
MAX_TOTAL_PAGES = int(os.environ.get("MAX_TOTAL_PAGES", "200"))  # 통합본 전체 쪽수
MAX_LOGO_KB = 2048
CONVERT_LOCK = threading.Lock()  # 변환 대기열: 동시에 여러 요청이 와도 하나씩
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _parse_keys(raw: str) -> dict[str, str]:
    """"나:abc,친구:def" -> {키: 이름}. 이름을 빼고 키만 써도 된다."""
    out: dict[str, str] = {}
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        name, _, key = part.rpartition(":")
        if len(key) >= 8:  # 너무 짧은 키는 추측될 수 있어 무시
            out[key] = name or "user"
    return out


ACCESS_KEYS = _parse_keys(os.environ.get("ACCESS_KEYS", ""))
# 이용 기록을 볼 수 있는 사람(초대 이름). 따로 정하지 않으면 ACCESS_KEYS 의 첫 사람(배포 스크립트의 'me').
ADMIN_USERS = {x.strip() for x in os.environ.get("ADMIN_USERS", "").split(",") if x.strip()} or \
    set(list(ACCESS_KEYS.values())[:1])
USAGE = UsageLog(Path(os.environ.get("USAGE_DB") or DATA_DIR.parent / "pdf2hwpx_usage.sqlite3"),
                 keep_days=float(os.environ.get("USAGE_KEEP_DAYS", "365")))
# 문제 생긴 파일(FAIL·오류)만 고치기 위해 보관. 0일이면 끈다.
SAMPLES = SampleStore(Path(os.environ.get("SAMPLES_DIR") or DATA_DIR.parent / "pdf2hwpx_samples"),
                      keep_days=float(os.environ.get("SAMPLE_KEEP_DAYS", "14")),
                      max_count=int(os.environ.get("SAMPLE_MAX", "30")),
                      max_mb=float(os.environ.get("SAMPLE_MAX_MB", "1000")))
ACCESS_COOKIE = "pdf2hwpx_access"
ACCESS_DAYS = int(os.environ.get("ACCESS_DAYS", "180"))


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
    pages: int = 0
    members: list = field(default_factory=list)  # 묶음(통합본/ZIP) 작업이면 원본 작업 id들
    user: str = ""        # 올린 사람(초대 이름). 이용 기록용
    questions: int = 0    # 분석에서 찾은 문제 수. 이용 기록용

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
        SAMPLES.maybe_prune()


threading.Thread(target=_sweeper, daemon=True).start()

app = FastAPI(title="PDF → HWPX", version=VERSION, docs_url=None, redoc_url=None)

GATE_HTML = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex">
<title>초대 링크 필요</title><style>
:root{color-scheme:light dark;--bg:#f6f7f9;--card:#fff;--text:#1d2129;--muted:#6b7280}
@media (prefers-color-scheme:dark){:root{--bg:#111318;--card:#1a1d24;--text:#eceef2;--muted:#9aa1ad}}
body{margin:0;min-height:100vh;display:grid;place-items:center;background:var(--bg);color:var(--text);
font-family:Pretendard,"Malgun Gothic",sans-serif;padding:16px}
div{max-width:420px;background:var(--card);border-radius:16px;padding:28px 24px;box-shadow:0 2px 12px rgba(0,0,0,.08)}
h1{font-size:19px;margin:0 0 10px}p{margin:0;color:var(--muted);line-height:1.6;font-size:14.5px}
</style></head><body><div><h1>초대 링크로 들어와 주세요</h1>
<p>이 사이트는 초대받은 사람만 쓸 수 있어요. 받은 초대 링크를 한 번 열면 이 브라우저에서는 계속 쓸 수 있어요.</p>
</div></body></html>"""


def _access_name(key: str) -> Optional[str]:
    found = None
    for k, name in ACCESS_KEYS.items():  # 모든 키와 비교(시간 차로 키를 추측하지 못하게)
        if secrets.compare_digest(key.encode(), k.encode()):
            found = name
    return found


def _is_admin(user: str) -> bool:
    return not ACCESS_KEYS or user in ADMIN_USERS  # 내 PC 실행(제한 없음)이면 누구나


def _user(request: Request) -> str:
    return getattr(request.state, "user", "") or "local"


@app.middleware("http")
async def access_gate(request: Request, call_next):
    path = request.url.path
    request.state.user = "local"
    if ACCESS_KEYS and path != "/healthz":
        if path.startswith("/join/"):
            key = path[len("/join/"):].strip("/")
            name = _access_name(key)
            if name is None:
                return HTMLResponse(GATE_HTML, status_code=403)
            USAGE.add("join", name, device=device_of(request.headers.get("user-agent", "")))
            resp = RedirectResponse("/", status_code=303)
            secure = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
            resp.set_cookie(ACCESS_COOKIE, key, max_age=ACCESS_DAYS * 86400, httponly=True,
                            secure=secure, samesite="lax")
            return resp
        name = _access_name(request.cookies.get(ACCESS_COOKIE, ""))
        if name is None:
            if path.startswith("/api/"):
                return JSONResponse({"detail": "초대 링크로 다시 들어와 주세요."}, status_code=401)
            return HTMLResponse(GATE_HTML, status_code=401)
        request.state.user = name
    if (path.startswith("/admin") or path.startswith("/api/admin/")) and not _is_admin(request.state.user):
        return JSONResponse({"detail": "관리자만 볼 수 있습니다."}, status_code=403)
    resp = await call_next(request)
    resp.headers["X-Robots-Tag"] = "noindex, nofollow"  # 검색 엔진에 나오지 않게
    return resp


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
def config(request: Request) -> dict:
    return {"version": VERSION, "fonts": FONTS, "max_mb": MAX_MB, "max_pages": MAX_PAGES,
            "job_ttl_min": JOB_TTL_MIN, "download_ttl_min": DOWNLOAD_TTL_MIN,
            "max_files": MAX_FILES, "max_total_pages": MAX_TOTAL_PAGES,
            "keep_failed_days": SAMPLES.keep_days if SAMPLES.enabled else 0,
            "admin": _is_admin(_user(request))}


def _keep(user: str, kind: str, jobs: list["Job"], status: str, res: Optional[dict] = None,
          result: Optional[Path] = None, style: Optional[DocStyle] = None, error: str = "") -> Optional[str]:
    """문제 생긴 파일만 관리자 확인용으로 보관(samples.py). 보관에 실패해도 변환 응답에는 영향이 없다."""
    v = (res or {}).get("validation") or {}
    return SAMPLES.save(user, kind, [(j.pdf, j.filename) for j in jobs], status, result=result,
                        causes=v.get("root_causes"), warnings=v.get("warnings"),
                        settings=_style_detail(style) if style else None, error=error,
                        pages=sum(j.pages for j in jobs), questions=(v.get("checks") or {}).get("question_count"))


def _kept(sid: Optional[str]) -> dict:
    """이용 기록에는 보관했다는 표시만 남긴다(보관 id 는 시각+난수)."""
    return {"kept": sid} if sid else {}


def _kept_note(sid: Optional[str]) -> str:
    return f" 고칠 수 있게 이 파일을 관리자에게 보관했어요({SAMPLES.keep_days:g}일 뒤 삭제)." if sid else ""


@app.post("/api/jobs")
def create_job(request: Request, file: UploadFile = File(...)) -> JSONResponse:
    data = file.file.read(int(MAX_MB * 1024 * 1024) + 1)
    if len(data) > MAX_MB * 1024 * 1024:
        raise HTTPException(413, f"파일이 너무 큽니다 (최대 {MAX_MB:g}MB).")
    if not data.startswith(b"%PDF"):
        raise HTTPException(415, "PDF 파일만 올릴 수 있습니다.")
    jid = uuid.uuid4().hex
    jdir = DATA_DIR / jid
    jdir.mkdir(parents=True)
    job = Job(jid, jdir, Path(file.filename or "document.pdf").name, user=_user(request))
    job.pdf.write_bytes(data)
    try:
        info = analyze(str(job.pdf))
    except Exception as e:
        sid = _keep(job.user, "upload", [job], "error", error=traceback.format_exc())
        shutil.rmtree(jdir, ignore_errors=True)
        USAGE.add("error", job.user, status="unreadable", where="upload", error=type(e).__name__, **_kept(sid))
        raise HTTPException(422, f"PDF를 읽을 수 없습니다: {type(e).__name__}." + _kept_note(sid))
    tl = info["text_layer"]
    if tl["pages"] > MAX_PAGES:
        shutil.rmtree(jdir, ignore_errors=True)
        raise HTTPException(413, f"페이지가 너무 많습니다 (최대 {MAX_PAGES}쪽).")
    (jdir / "page1.png").write_bytes(info.pop("page1_png"))
    job.pages = int(tl["pages"])
    job.questions = int((info.get("stats") or {}).get("questions") or 0)
    USAGE.add("upload", job.user, files=1, pages=job.pages, questions=job.questions, status=tl.get("status", ""))
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


def _style(opts: dict, job: Job) -> DocStyle:
    logo = job.logo
    if logo is None and opts.get("logo_job") in JOBS:  # 여러 파일: 로고는 첫 파일에만 올린다
        logo = JOBS[opts["logo_job"]].logo
    try:
        return DocStyle.from_dict(opts or {}, logo=logo if opts.get("use_logo", True) else None)
    except ValueError as e:  # 바탕쪽 묶음이 깨졌을 때 등
        raise HTTPException(400, str(e) or "설정 값이 올바르지 않습니다.")


@app.post("/api/template")
def upload_template(request: Request, file: UploadFile = File(...)) -> dict:
    """내 한글 파일(HWPX)에서 바탕쪽만 뽑아 돌려준다. 서버에는 남기지 않고, 브라우저가 보관했다가 변환할 때 보낸다."""
    data = file.file.read(int(MAX_MB * 1024 * 1024) + 1)
    if len(data) > MAX_MB * 1024 * 1024:
        raise HTTPException(413, f"파일이 너무 큽니다 (최대 {MAX_MB:g}MB).")
    try:
        pkg = extract_template(data)
    except TemplateError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        raise HTTPException(422, f"한글 파일을 읽을 수 없습니다: {type(e).__name__}")
    USAGE.add("template", _user(request), fonts=len(pkg.get("font_names") or []))
    return pkg


def _finish(job: Job, path: Path) -> None:
    job.hwpx = path
    job.token = secrets.token_urlsafe(16)
    job.download_until = min(time.time() + DOWNLOAD_TTL_MIN * 60, job.expires)


def _result(job: Job, res: Optional[dict] = None) -> dict:
    out = {
        "id": job.id,
        "download_url": f"/api/jobs/{job.id}/download/{job.token}",
        "download_until": job.download_until,
        "seconds_left": max(0, int(job.download_until - time.time())),
        "filename": job.hwpx.name, "size": job.hwpx.stat().st_size,
    }
    if res is None:
        return out
    v = res["validation"]
    c = v["checks"]
    out.update({
        "status": v["status"], "root_causes": v["root_causes"], "warnings": v["warnings"][:5],
        "summary": {"questions": c.get("question_count"), "objective": c.get("objective"),
                    "subjective": c.get("subjective"), "boxes": c.get("box_groups"),
                    "pictures": c.get("pictures"), "answers": c.get("answer_count"),
                    "endnotes": c.get("endnotes"),
                    "coverage": c.get("text_coverage")},
    })
    return out


async def _json(request: Request) -> dict:
    try:
        d = await request.json()
    except Exception:
        d = {}
    return d if isinstance(d, dict) else {}


@app.post("/api/jobs/{job_id}/convert")
async def convert_job(job_id: str, request: Request) -> dict:
    job = _get(job_id)
    opts = await _json(request)
    style = _style(opts, job)
    from starlette.concurrency import run_in_threadpool

    user = _user(request)
    t0 = time.time()
    kept: dict = {}  # 오류가 나도 보관 id 를 바깥에서 알 수 있게

    def work() -> tuple[dict, Optional[str]]:
        with CONVERT_LOCK, job.lock:
            out = job.dir / "out"
            shutil.rmtree(out, ignore_errors=True)
            out.mkdir()
            name = Path(job.filename).stem + ".hwpx"
            try:
                res = convert(str(job.pdf), hwpx_path=str(out / name), write_json=False, style=style)
            except Exception:
                kept["sid"] = _keep(user, "convert", [job], "error", style=style, error=traceback.format_exc())
                raise
            _finish(job, out / name)
            sid = None
            if res["validation"]["status"] == "FAIL":
                sid = _keep(user, "convert", [job], "FAIL", res=res, result=job.hwpx, style=style)
            return res, sid

    try:
        res, sid = await run_in_threadpool(work)
    except Exception as e:
        sid = kept.get("sid")
        USAGE.add("error", user, files=1, pages=job.pages, where="convert", error=type(e).__name__, **_kept(sid))
        raise HTTPException(500, f"변환 중 오류가 발생했습니다: {type(e).__name__}." + _kept_note(sid))
    out = dict(_result(job, res), kept=bool(sid), kept_days=SAMPLES.keep_days)
    USAGE.add("convert", user, files=1, pages=job.pages, questions=out["summary"].get("questions"),
              status=out["status"], seconds=time.time() - t0, **_style_detail(style), **_causes_detail(out),
              **_kept(sid))
    return out


def _causes_detail(out: dict) -> dict:
    """이용 기록용 검사 실패 원인: 숫자만 남기고 원문 글자(누락 줄 예시)는 지운다."""
    causes = [re.sub(r"\s*\(누락 줄 예:.*$", "", c)[:80] for c in out.get("root_causes") or []]
    return {"causes": causes[:4]} if causes else {}


def _style_detail(style: DocStyle) -> dict:
    """이용 기록에 남길 설정(학원 이름·제목 같은 글자는 남기지 않는다)."""
    return {"endnotes": style.answers_as_endnotes, "auto_number": style.auto_number,
            "font": style.body_font, "size": style.body_size, **({"template": True} if style.template else {})}


def _members(d: dict) -> list[Job]:
    ids = d.get("jobs")
    if not isinstance(ids, list) or not ids:
        raise HTTPException(400, "파일 목록이 비어 있습니다.")
    if len(ids) > MAX_FILES:
        raise HTTPException(413, f"한 번에 {MAX_FILES}개까지 묶을 수 있습니다.")
    jobs = [_get(str(i)) for i in ids]
    if len({j.id for j in jobs}) != len(jobs) or any(j.members for j in jobs):
        raise HTTPException(400, "파일 목록이 올바르지 않습니다.")
    return jobs


def _new_bundle(filename: str, members: list[Job]) -> Job:
    bid = uuid.uuid4().hex
    bdir = DATA_DIR / bid
    bdir.mkdir(parents=True)
    return Job(bid, bdir, filename, members=[j.id for j in members])


def _unique_names(jobs: list[Job]) -> list[str]:
    seen: dict[str, int] = {}
    out = []
    for j in jobs:
        stem = Path(j.filename).stem
        n = seen.get(stem, 0) + 1
        seen[stem] = n
        out.append(f"{stem}.hwpx" if n == 1 else f"{stem} ({n}).hwpx")
    return out


@app.post("/api/bundles/merge")
async def merge_jobs(request: Request) -> dict:
    """여러 PDF를 순서대로 이어 한 HWPX로(문제·정답 번호를 이어서 매긴다)."""
    d = await _json(request)
    jobs = _members(d)
    if len(jobs) < 2:
        raise HTTPException(400, "통합본은 PDF가 2개 이상일 때 만들 수 있습니다.")
    if sum(j.pages for j in jobs) > MAX_TOTAL_PAGES:
        raise HTTPException(413, f"통합본은 모두 합쳐 {MAX_TOTAL_PAGES}쪽까지 만들 수 있습니다.")
    opts = d.get("options") if isinstance(d.get("options"), dict) else {}
    opts.setdefault("logo_job", jobs[0].id)
    style = _style(opts, jobs[0])
    stem = Path(jobs[0].filename).stem
    bundle = _new_bundle(f"{stem} 외 {len(jobs) - 1}개 통합.hwpx", jobs)
    user = _user(request)
    t0 = time.time()
    kept: dict = {}
    from starlette.concurrency import run_in_threadpool

    def work() -> tuple[dict, Optional[str]]:
        with CONVERT_LOCK:
            path = bundle.dir / bundle.filename
            try:
                res = convert_many([str(j.pdf) for j in jobs], str(path), style=style,
                                   names=[j.filename for j in jobs])
            except Exception:
                kept["sid"] = _keep(user, "merge", jobs, "error", style=style, error=traceback.format_exc())
                raise
            _finish(bundle, path)
            sid = None
            if res["validation"]["status"] == "FAIL":
                sid = _keep(user, "merge", jobs, "FAIL", res=res, result=path, style=style)
            return res, sid

    try:
        res, sid = await run_in_threadpool(work)
    except Exception as e:
        sid = kept.get("sid")
        shutil.rmtree(bundle.dir, ignore_errors=True)
        USAGE.add("error", user, files=len(jobs), pages=sum(j.pages for j in jobs), where="merge",
                  error=type(e).__name__, **_kept(sid))
        raise HTTPException(500, f"통합 중 오류가 발생했습니다: {type(e).__name__}." + _kept_note(sid))
    with JOBS_LOCK:
        JOBS[bundle.id] = bundle
    out = dict(_result(bundle, res), files=len(jobs), kept=bool(sid), kept_days=SAMPLES.keep_days)
    USAGE.add("merge", user, files=len(jobs), pages=sum(j.pages for j in jobs),
              questions=out["summary"].get("questions"), status=out["status"], seconds=time.time() - t0,
              **_style_detail(style), **_causes_detail(out), **_kept(sid))
    return out


@app.post("/api/bundles/zip")
async def zip_jobs(request: Request) -> dict:
    """따로 변환한 HWPX들을 ZIP 하나로 묶는다(변환은 파일마다 /convert로 먼저). 변환 횟수는 /convert 에서 센다."""
    jobs = _members(await _json(request))
    now = time.time()
    if any(j.hwpx is None or not j.hwpx.exists() or now > j.download_until for j in jobs):
        raise HTTPException(409, "아직 변환되지 않았거나 다운로드 시간이 지난 파일이 있습니다. 다시 변환해 주세요.")
    bundle = _new_bundle(f"한글 변환 {len(jobs)}개.zip", jobs)
    bundle.user = _user(request)
    path = bundle.dir / bundle.filename
    with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as z:  # HWPX는 이미 압축돼 있다
        for j, name in zip(jobs, _unique_names(jobs)):
            z.write(j.hwpx, name)
    _finish(bundle, path)
    bundle.download_until = min(bundle.download_until, min(j.download_until for j in jobs))
    with JOBS_LOCK:
        JOBS[bundle.id] = bundle
    USAGE.add("zip", bundle.user, files=len(jobs), pages=sum(j.pages for j in jobs))
    return dict(_result(bundle), files=len(jobs))


@app.get("/api/jobs/{job_id}/download/{token}")
def download(job_id: str, token: str, request: Request) -> FileResponse:
    job = _get(job_id)
    if not job.token or not secrets.compare_digest(token, job.token) or job.hwpx is None:
        raise HTTPException(404, "다운로드 링크가 올바르지 않습니다.")
    if time.time() > job.download_until:
        raise HTTPException(410, "다운로드 가능 시간이 지났습니다. 다시 변환해 주세요.")
    is_zip = job.hwpx.suffix.lower() == ".zip"
    kind = "zip" if is_zip else "merged" if job.members else "hwpx"
    USAGE.add("download", _user(request), files=len(job.members) or 1, kind=kind)
    ascii_name = "documents.zip" if is_zip else "document.hwpx"
    disp = f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(job.hwpx.name)}"
    return FileResponse(job.hwpx, media_type="application/zip" if is_zip else "application/hwp+zip",
                        headers={"Content-Disposition": disp})


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str) -> dict:
    _delete(job_id)
    return {"ok": True}


@app.post("/api/jobs/{job_id}/delete")  # navigator.sendBeacon 용 (페이지를 떠날 때)
def delete_job_beacon(job_id: str) -> Response:
    _delete(job_id)
    return Response(status_code=204)


# ---------------------------------------------------------------- 관리자: 이용 기록 --
@app.get("/admin")
def admin_page() -> FileResponse:
    return FileResponse(Path(__file__).parent / "static" / "admin.html", headers={"Cache-Control": "no-store"})


@app.get("/api/admin/usage")
def admin_usage(request: Request, days: float = 30, limit: int = 200, user: str = "") -> dict:
    days = max(1.0, min(days, 3650.0))
    return {
        "me": _user(request), "days": days, "keep_days": USAGE.keep_days, "events": EVENTS,
        "people": sorted(set(ACCESS_KEYS.values())),
        "summary": USAGE.summary(time.time() - days * 86400, user=user),
        "everyone": USAGE.summary(time.time() - days * 86400)["users"],
        "recent": USAGE.recent(limit, user=user),
        "now": {"jobs": len([j for j in JOBS.values() if not j.members]), "converting": CONVERT_LOCK.locked()},
    }


@app.get("/api/admin/usage.csv")
def admin_usage_csv(user: str = "") -> PlainTextResponse:
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["시각", "사람", "동작", "파일 수", "쪽수", "문제 수", "결과", "걸린 초", "기타"])
    for r in USAGE.recent(5000, user=user):
        w.writerow([time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r["ts"])), r["user"], r["label"],
                    r["files"] or "", r["pages"] or "", r["questions"] or "", r["status"], r["seconds"] or "",
                    " ".join(f"{k}={v}" for k, v in r["detail"].items())])
    # 엑셀에서 한글이 깨지지 않게 BOM
    return PlainTextResponse("\ufeff" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": "attachment; filename=\"usage.csv\"; "
                                                            "filename*=UTF-8''%EC%9D%B4%EC%9A%A9%EA%B8%B0%EB%A1%9D.csv"})


# ------------------------------------------------- 관리자: 문제 생긴 파일(samples.py) --
@app.get("/api/admin/samples")
def admin_samples() -> dict:
    return {"enabled": SAMPLES.enabled, "keep_days": SAMPLES.keep_days, "max_count": SAMPLES.max_count,
            "items": SAMPLES.list()}


@app.get("/api/admin/samples/{sid}/download")
def admin_sample_download(sid: str) -> FileResponse:
    fd, tmp = tempfile.mkstemp(suffix=".zip")
    os.close(fd)
    name = SAMPLES.zip(sid, Path(tmp))
    if name is None:
        os.unlink(tmp)
        raise HTTPException(404, "보관된 파일이 없습니다(기간이 지나 지워졌을 수 있어요).")
    disp = f"attachment; filename=\"sample.zip\"; filename*=UTF-8''{quote(name)}"
    return FileResponse(tmp, media_type="application/zip", headers={"Content-Disposition": disp},
                        background=BackgroundTask(os.unlink, tmp))


@app.delete("/api/admin/samples/{sid}")
def admin_sample_delete(sid: str) -> dict:
    if not SAMPLES.delete(sid):
        raise HTTPException(404, "보관된 파일이 없습니다.")
    return {"ok": True}


app.mount("/", StaticFiles(directory=str(Path(__file__).parent / "static"), html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    # 접속 기록은 기본으로 끈다(초대 링크의 키가 로그에 남지 않게). 로드밸런서 뒤에서는 https 여부를 헤더로 받는다.
    uvicorn.run(app, host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "8000")),
                access_log=os.environ.get("ACCESS_LOG") == "1", proxy_headers=True, forwarded_allow_ips="*")
