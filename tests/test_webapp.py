"""웹 서버 API 흐름: 업로드 -> 미리보기 데이터 -> 로고 -> 변환 -> 다운로드 -> 만료/삭제."""
import io
import time
import zipfile

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from tests.synth_pdf import build  # noqa: E402


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    import os
    d = tmp_path_factory.mktemp("web")
    os.environ["DATA_DIR"] = str(d / "jobs")
    from webapp import server
    server.DATA_DIR = d / "jobs"
    server.DATA_DIR.mkdir(parents=True, exist_ok=True)
    pdf = d / "synth.pdf"
    build(str(pdf))
    return TestClient(server.app), server, pdf.read_bytes()


def _png() -> bytes:
    import pymupdf as fitz
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 120, 22), 0)
    pix.clear_with(0)
    return pix.tobytes("png")


def test_rejects_non_pdf(env):
    client, _, _ = env
    r = client.post("/api/jobs", files={"file": ("a.pdf", b"hello", "application/pdf")})
    assert r.status_code == 415


def test_full_flow(env):
    client, server, pdf = env
    assert client.get("/").status_code == 200
    cfg = client.get("/api/config").json()
    assert "함초롬바탕" in cfg["fonts"]

    r = client.post("/api/jobs", files={"file": ("시험.pdf", pdf, "application/pdf")})
    assert r.status_code == 200, r.text
    job = r.json()
    jid = job["id"]
    assert job["text_layer"]["status"] == "ok"
    assert job["sample"]["passage"] and job["sample"]["question"]
    assert client.get(job["page1"]).headers["content-type"] == "image/png"

    assert client.post(f"/api/jobs/{jid}/logo", files={"file": ("x.png", b"nope", "image/png")}).status_code == 415
    lr = client.post(f"/api/jobs/{jid}/logo", files={"file": ("logo.png", _png(), "image/png")}).json()
    assert lr["width"] == 120

    opts = {"body_font": "나눔명조", "body_size": 11, "title": "[중간 대비] 테스트",
            "academy_name": "테스트학원", "use_logo": True, "frame": True}
    c = client.post(f"/api/jobs/{jid}/convert", json=opts).json()
    assert c["status"] == "PASS", c
    assert c["seconds_left"] > 0

    d = client.get(c["download_url"])
    assert d.status_code == 200
    z = zipfile.ZipFile(io.BytesIO(d.content))
    names = z.namelist()
    assert "Contents/masterpage0.xml" in names
    mp = z.read("Contents/masterpage0.xml").decode()
    assert "[중간 대비] 테스트" in mp and "binaryItemIDRef" in mp
    assert "나눔명조" in z.read("Contents/header.xml").decode()

    # 잘못된 토큰 / 다운로드 시간 만료
    assert client.get(f"/api/jobs/{jid}/download/wrong").status_code == 404
    server.JOBS[jid].download_until = time.time() - 1
    assert client.get(c["download_url"]).status_code == 410

    # 페이지 이탈(sendBeacon) -> 작업 폴더 삭제
    jdir = server.JOBS[jid].dir
    assert client.post(f"/api/jobs/{jid}/delete").status_code == 204
    assert not jdir.exists()
    assert client.get(job["page1"]).status_code == 404


def test_job_ttl_expiry(env):
    client, server, pdf = env
    jid = client.post("/api/jobs", files={"file": ("a.pdf", pdf, "application/pdf")}).json()["id"]
    server.JOBS[jid].created -= server.JOB_TTL_MIN * 60 + 1
    assert client.post(f"/api/jobs/{jid}/convert", json={}).status_code == 404
    assert jid not in server.JOBS
