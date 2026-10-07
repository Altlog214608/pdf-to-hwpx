"""이용 기록(관리자 화면용). SQLite 파일 하나에 '누가·언제·무엇을·얼마나'만 남긴다.

저작권 보호 원칙: 업로드한 파일의 내용·파일 이름·제목은 기록하지 않는다. 쪽수·문제 수·변환 결과 상태 같은 숫자만 남긴다.
보관 기간(USAGE_KEEP_DAYS)이 지난 기록은 서버가 켜질 때와 하루 한 번 지운다.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Optional

EVENTS = {
    "join": "초대 링크 접속",
    "upload": "PDF 올리기",
    "convert": "변환",
    "merge": "통합본 만들기",
    "zip": "ZIP 묶기",
    "download": "내려받기",
    "error": "오류",
}


def device_of(user_agent: str) -> str:
    """기기 종류만 대략 구분한다(브라우저 문자열 전체는 남기지 않는다)."""
    ua = (user_agent or "").lower()
    if "iphone" in ua or "ipad" in ua:
        return "iPhone/iPad"
    if "android" in ua:
        return "Android"
    if "windows" in ua:
        return "Windows"
    if "mac os" in ua or "macintosh" in ua:
        return "Mac"
    if "linux" in ua:
        return "Linux"
    return "기타"


class UsageLog:
    def __init__(self, path: Path, keep_days: float = 365):
        self.path = Path(path)
        self.keep_days = keep_days
        self.lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.path), check_same_thread=False)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS usage (id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, "
            "event TEXT NOT NULL, user TEXT NOT NULL, files INTEGER, pages INTEGER, questions INTEGER, "
            "status TEXT, seconds REAL, detail TEXT)")
        self.db.execute("CREATE INDEX IF NOT EXISTS usage_ts ON usage(ts)")
        self.db.commit()
        self._pruned = 0.0
        self.prune()

    def prune(self) -> None:
        with self.lock:
            self.db.execute("DELETE FROM usage WHERE ts < ?", (time.time() - self.keep_days * 86400,))
            self.db.commit()
            self._pruned = time.time()

    def add(self, event: str, user: str, files: Optional[int] = None, pages: Optional[int] = None,
            questions: Optional[int] = None, status: str = "", seconds: Optional[float] = None,
            **detail) -> None:
        """기록 실패가 서비스 동작을 막지 않도록 예외는 삼킨다."""
        try:
            with self.lock:
                self.db.execute(
                    "INSERT INTO usage (ts, event, user, files, pages, questions, status, seconds, detail) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (time.time(), event, user or "?", files, pages, questions, status,
                     round(seconds, 2) if seconds is not None else None,
                     json.dumps(detail, ensure_ascii=False) if detail else ""))
                self.db.commit()
            if time.time() - self._pruned > 86400:
                self.prune()
        except Exception:
            pass

    def recent(self, limit: int = 200, user: str = "") -> list[dict]:
        q = "SELECT ts, event, user, files, pages, questions, status, seconds, detail FROM usage"
        args: list = []
        if user:
            q += " WHERE user = ?"
            args.append(user)
        q += " ORDER BY ts DESC, id DESC LIMIT ?"
        args.append(max(1, min(int(limit), 5000)))
        with self.lock:
            rows = self.db.execute(q, args).fetchall()
        out = []
        for ts, event, u, files, pages, questions, status, seconds, detail in rows:
            out.append({"ts": ts, "event": event, "label": EVENTS.get(event, event), "user": u,
                        "files": files, "pages": pages, "questions": questions, "status": status,
                        "seconds": seconds, "detail": json.loads(detail) if detail else {}})
        return out

    def summary(self, since: float, user: str = "") -> dict:
        """since 이후(user 를 주면 그 사람만): 사람별 변환 횟수·파일 수·쪽수·문제 수, 날짜별 변환 횟수."""
        conv = ("convert", "merge")
        uf, ua = (" AND user = ?", (user,)) if user else ("", ())
        with self.lock:
            by_user = self.db.execute(
                "SELECT user, COUNT(*), COALESCE(SUM(files),0), COALESCE(SUM(pages),0), COALESCE(SUM(questions),0), "
                "MAX(ts) FROM usage WHERE ts >= ? AND event IN (?,?)" + uf + " GROUP BY user ORDER BY COUNT(*) DESC",
                (since, *conv, *ua)).fetchall()
            last_seen = dict(self.db.execute(
                "SELECT user, MAX(ts) FROM usage WHERE ts >= ?" + uf + " GROUP BY user", (since, *ua)).fetchall())
            days = self.db.execute(
                "SELECT date(ts, 'unixepoch', 'localtime') d, COUNT(*) FROM usage WHERE ts >= ? AND event IN (?,?)"
                + uf + " GROUP BY d ORDER BY d", (since, *conv, *ua)).fetchall()
            errors = self.db.execute(
                "SELECT COUNT(*) FROM usage WHERE ts >= ? AND (event = 'error' OR status = 'FAIL')" + uf, (since, *ua)).fetchone()[0]
            downloads = self.db.execute(
                "SELECT COUNT(*) FROM usage WHERE ts >= ? AND event = 'download'" + uf, (since, *ua)).fetchone()[0]
        users = [{"user": u, "conversions": n, "files": f, "pages": p, "questions": q, "last_seen": last_seen.get(u, t)}
                 for u, n, f, p, q, t in by_user]
        for u, t in last_seen.items():  # 올리기만 하고 변환은 안 한 사람도 보이게
            if not any(x["user"] == u for x in users):
                users.append({"user": u, "conversions": 0, "files": 0, "pages": 0, "questions": 0, "last_seen": t})
        return {
            "conversions": sum(x["conversions"] for x in users),
            "files": sum(x["files"] for x in users),
            "pages": sum(x["pages"] for x in users),
            "questions": sum(x["questions"] for x in users),
            "downloads": downloads,
            "errors": errors,
            "users": users,
            "days": [{"date": d, "conversions": n} for d, n in days],
        }
