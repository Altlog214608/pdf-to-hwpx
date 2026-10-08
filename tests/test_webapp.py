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


def _upload(client, pdf, name):
    r = client.post("/api/jobs", files={"file": (name, pdf, "application/pdf")})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_merge_bundle(env):
    client, server, pdf = env
    ids = [_upload(client, pdf, f"단원{k}.pdf") for k in range(3)]
    lr = client.post(f"/api/jobs/{ids[0]}/logo", files={"file": ("logo.png", _png(), "image/png")})
    assert lr.status_code == 200
    assert client.post("/api/bundles/merge", json={"jobs": ids[:1]}).status_code == 400
    r = client.post("/api/bundles/merge", json={"jobs": ids, "options": {"title": "통합", "use_logo": True}})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["files"] == 3 and b["summary"]["questions"] == 15 and b["status"] == "PASS", b
    assert b["filename"] == "단원0 외 2개 통합.hwpx"
    d = client.get(b["download_url"])
    assert d.status_code == 200 and d.headers["content-type"] == "application/hwp+zip"
    z = zipfile.ZipFile(io.BytesIO(d.content))
    assert "binaryItemIDRef" in z.read("Contents/masterpage0.xml").decode()  # 첫 파일 로고
    # 쪽수 제한
    old = server.MAX_TOTAL_PAGES
    server.MAX_TOTAL_PAGES = 1
    try:
        assert client.post("/api/bundles/merge", json={"jobs": ids}).status_code == 413
    finally:
        server.MAX_TOTAL_PAGES = old
    # 묶음 작업도 페이지 이탈 시 삭제
    bdir = server.JOBS[b["id"]].dir
    assert client.post(f"/api/jobs/{b['id']}/delete").status_code == 204 and not bdir.exists()


def test_zip_bundle_and_limits(env):
    client, server, pdf = env
    ids = [_upload(client, pdf, n) for n in ("같은이름.pdf", "같은이름.pdf", "다른.pdf")]
    assert client.post("/api/bundles/zip", json={"jobs": ids}).status_code == 409  # 아직 변환 전
    for jid in ids:
        c = client.post(f"/api/jobs/{jid}/convert", json={"logo_job": ids[0]})
        assert c.status_code == 200 and c.json()["status"] == "PASS"
    r = client.post("/api/bundles/zip", json={"jobs": ids})
    assert r.status_code == 200, r.text
    zr = r.json()
    d = client.get(zr["download_url"])
    assert d.status_code == 200 and d.headers["content-type"] == "application/zip"
    z = zipfile.ZipFile(io.BytesIO(d.content))
    assert z.namelist() == ["같은이름.hwpx", "같은이름 (2).hwpx", "다른.hwpx"]
    assert zipfile.ZipFile(io.BytesIO(z.read("다른.hwpx"))).read("mimetype") == b"application/hwp+zip"
    # 묶음을 다시 묶을 수 없고, 개수 제한이 있다
    assert client.post("/api/bundles/zip", json={"jobs": [zr["id"]]}).status_code == 400
    old = server.MAX_FILES
    server.MAX_FILES = 2
    try:
        assert client.post("/api/bundles/zip", json={"jobs": ids}).status_code == 413
    finally:
        server.MAX_FILES = old
    assert client.get("/api/config").json()["max_files"] == server.MAX_FILES


def test_access_gate(env, monkeypatch):
    """ACCESS_KEYS가 있으면 초대 링크(/join/키)로 쿠키를 받은 브라우저만 쓸 수 있다."""
    client, server, pdf = env
    monkeypatch.setattr(server, "ACCESS_KEYS", server._parse_keys("나:key-for-me-123, 친구:key-for-friend-456, short:abc"))
    assert set(server.ACCESS_KEYS.values()) == {"나", "친구"}  # 짧은 키는 무시
    from fastapi.testclient import TestClient
    c = TestClient(server.app)
    assert c.get("/healthz").status_code == 200           # 로드밸런서 헬스체크는 열어 둔다
    r = c.get("/")
    assert r.status_code == 401 and "초대 링크" in r.text
    assert c.get("/api/config").status_code == 401
    assert c.post("/api/jobs", files={"file": ("a.pdf", pdf, "application/pdf")}).status_code == 401
    assert c.get("/join/wrong-key-000", follow_redirects=False).status_code == 403
    r = c.get("/join/key-for-friend-456", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/"
    sc = r.headers["set-cookie"]
    assert "HttpOnly" in sc and "Max-Age=15552000" in sc and "Secure" not in sc
    assert c.get("/").status_code == 200 and c.get("/api/config").status_code == 200
    assert c.get("/").headers["x-robots-tag"].startswith("noindex")
    # https(로드밸런서 뒤)이면 Secure 쿠키
    r = TestClient(server.app).get("/join/key-for-me-123", headers={"x-forwarded-proto": "https"}, follow_redirects=False)
    assert "Secure" in r.headers["set-cookie"]
    # 키를 지우면(다시 배포) 그 사람은 끊긴다
    monkeypatch.setattr(server, "ACCESS_KEYS", server._parse_keys("나:key-for-me-123"))
    assert c.get("/api/config").status_code == 401


def test_usage_log_and_admin(env, monkeypatch, tmp_path):
    """이용 기록: 누가·무엇을·몇 쪽만 남고(파일 이름 없음), 관리자만 /admin 에서 본다."""
    client, server, pdf = env
    from webapp.usage import UsageLog
    log = UsageLog(tmp_path / "usage.sqlite3")
    monkeypatch.setattr(server, "USAGE", log)
    monkeypatch.setattr(server, "ACCESS_KEYS", server._parse_keys("me:key-for-me-123,guest:key-for-guest-456"))
    monkeypatch.setattr(server, "ADMIN_USERS", {"me"})
    from fastapi.testclient import TestClient
    guest, me = TestClient(server.app), TestClient(server.app)
    guest.get("/join/key-for-guest-456", headers={"user-agent": "Mozilla/5.0 (Windows NT 10.0)"}, follow_redirects=False)
    me.get("/join/key-for-me-123", follow_redirects=False)

    jid = guest.post("/api/jobs", files={"file": ("비밀 제목.pdf", pdf, "application/pdf")}).json()["id"]
    c = guest.post(f"/api/jobs/{jid}/convert", json={"answers_as_endnotes": True}).json()
    assert guest.get(c["download_url"]).status_code == 200
    ids = [guest.post("/api/jobs", files={"file": (f"{k}.pdf", pdf, "application/pdf")}).json()["id"] for k in range(2)]
    assert guest.post("/api/bundles/merge", json={"jobs": ids}).status_code == 200

    # 관리자만
    assert guest.get("/api/config").json()["admin"] is False
    assert me.get("/api/config").json()["admin"] is True
    assert guest.get("/admin").status_code == 403 and guest.get("/api/admin/usage").status_code == 403
    assert guest.get("/admin.html").status_code == 403
    assert me.get("/admin").status_code == 200

    d = me.get("/api/admin/usage?days=7").json()
    ev = [(r["event"], r["user"]) for r in d["recent"]]
    assert ("join", "guest") in ev and ("upload", "guest") in ev and ("convert", "guest") in ev
    assert ("download", "guest") in ev and ("merge", "guest") in ev
    conv = next(r for r in d["recent"] if r["event"] == "convert")
    assert conv["pages"] == 3 and conv["questions"] == 5 and conv["status"] == "PASS" and conv["detail"]["endnotes"] is True
    s = d["summary"]
    assert s["conversions"] == 2 and s["files"] == 3 and s["questions"] == 15 and s["downloads"] == 1
    assert {u["user"] for u in d["everyone"]} == {"guest", "me"}
    assert sum(x["conversions"] for x in s["days"]) == 2
    assert me.get("/api/admin/usage?user=me").json()["summary"]["conversions"] == 0
    joined = next(r for r in d["recent"] if r["event"] == "join" and r["user"] == "guest")
    assert joined["detail"]["device"] == "Windows"
    csv_text = me.get("/api/admin/usage.csv").content.decode("utf-8-sig")
    assert "변환" in csv_text and "guest" in csv_text
    # 파일 이름·제목은 어디에도 남지 않는다
    raw = (tmp_path / "usage.sqlite3").read_bytes()
    assert "비밀 제목".encode() not in raw and "비밀 제목" not in csv_text

    # 오래된 기록은 보관 기간이 지나면 지운다
    log.db.execute("UPDATE usage SET ts = ts - 400 * 86400 WHERE event = 'join'")
    log.db.commit()
    log.prune()
    assert not [r for r in log.recent(500) if r["event"] == "join"]


def test_usage_causes_have_no_source_text(env):
    """검사 실패 원인은 이용 기록에 남기되, 원문 글자(누락 줄 예시)는 지운다."""
    _, server, _ = env
    d = server._causes_detail({"root_causes": [
        "원문 텍스트 커버리지 91.2% (누락 줄 예: ['p3: 어느 날 마을 사람들이'])",
        "정답 수(20) != 문제 수(21)"]})
    assert d == {"causes": ["원문 텍스트 커버리지 91.2%", "정답 수(20) != 문제 수(21)"]}
    assert server._causes_detail({"root_causes": []}) == {}
