"""문제 생긴 파일 보관(관리자 확인용).

변환 결과가 '문제 있음'(FAIL)이거나 변환 중 오류가 난 PDF만, 그때의 결과 HWPX·검사 원인·설정과 함께
보관 기간(SAMPLE_KEEP_DAYS, 기본 14일) 동안 남긴다. 관리자만 /admin 에서 내려받거나 지울 수 있고,
기간·개수(SAMPLE_MAX)·용량(SAMPLE_MAX_MB)을 넘으면 오래된 것부터 지운다. 같은 파일이 다시 실패하면 새로 쌓지 않고
횟수만 늘린다. 그 밖의 업로드 파일은 지금처럼 작업 폴더에만 두었다가 지운다(저작권). 화면에도 이 예외를 알린다.
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
import shutil
import threading
import time
import zipfile
from pathlib import Path
from typing import Optional

SID_RE = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{6}$")
KINDS = {"convert": "변환", "merge": "통합본", "upload": "올리기"}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _safe_name(name: str, default: str) -> str:
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", Path(name or "").name).strip(" .")
    return name[:120] or default


class SampleStore:
    def __init__(self, root: Path, keep_days: float = 14, max_count: int = 30, max_mb: float = 1000):
        self.root = Path(root)
        self.keep_days = keep_days
        self.max_count = max_count
        self.max_mb = max_mb
        self.lock = threading.Lock()
        self._pruned = 0.0
        if self.enabled:
            self.root.mkdir(parents=True, exist_ok=True)
            self.prune()

    @property
    def enabled(self) -> bool:
        return self.keep_days > 0 and self.max_count > 0

    def _dir(self, sid: str) -> Optional[Path]:
        if not SID_RE.match(sid or ""):
            return None
        d = self.root / sid
        return d if (d / "info.json").is_file() else None

    @staticmethod
    def _read(d: Path) -> dict:
        return json.loads((d / "info.json").read_text(encoding="utf-8"))

    @staticmethod
    def _write(d: Path, info: dict) -> None:
        tmp = d / "info.json.tmp"
        tmp.write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(d / "info.json")

    def save(self, user: str, kind: str, sources: list[tuple[Path, str]], status: str,
             result: Optional[Path] = None, causes: Optional[list] = None, warnings: Optional[list] = None,
             settings: Optional[dict] = None, error: str = "", pages: int = 0,
             questions: Optional[int] = None) -> Optional[str]:
        """원본 PDF(들)와 결과·원인을 보관하고 보관 id 를 돌려준다. 보관 실패가 서비스 동작을 막지 않도록 예외는 삼킨다."""
        if not self.enabled or not sources:
            return None
        try:
            hashes = [_sha256(Path(p)) for p, _ in sources]
            key = hashlib.sha256((kind + ":" + ",".join(hashes)).encode()).hexdigest()[:20]
            now = time.time()
            last = {"ts": now, "user": user or "?", "status": status, "causes": list(causes or [])[:8],
                    "warnings": list(warnings or [])[:8], "settings": settings or {}, "error": (error or "")[-4000:],
                    "questions": questions}
            with self.lock:
                for d in self.root.iterdir():  # 같은 파일이 다시 실패하면 횟수만 늘리고 최신 결과로 바꾼다
                    if SID_RE.match(d.name) and (d / "info.json").is_file():
                        info = self._read(d)
                        if info.get("key") == key:
                            info.update(last, count=info.get("count", 1) + 1)
                            if result is not None and Path(result).is_file():
                                shutil.copyfile(result, d / "result.hwpx")
                            else:  # 이번엔 결과 없이 오류: 지난번 결과는 지금 상태와 맞지 않으니 지운다
                                (d / "result.hwpx").unlink(missing_ok=True)
                            self._write(d, info)
                            return d.name
                sid = time.strftime("%Y%m%d-%H%M%S", time.localtime(now)) + "-" + secrets.token_hex(3)
                tmp = self.root / (sid + ".tmp")
                tmp.mkdir()
                files = []
                for i, (p, name) in enumerate(sources, 1):
                    stored = "source.pdf" if len(sources) == 1 else f"source_{i:02d}.pdf"
                    shutil.copyfile(p, tmp / stored)
                    files.append({"stored": stored, "name": _safe_name(name, stored), "sha256": hashes[i - 1]})
                if result is not None and Path(result).is_file():
                    shutil.copyfile(result, tmp / "result.hwpx")
                self._write(tmp, {"id": sid, "key": key, "kind": kind, "first_ts": now, "count": 1,
                                  "files": files, "pages": pages, **last})
                tmp.rename(self.root / sid)
            self.prune()
            return sid
        except Exception:
            return None

    def list(self) -> list[dict]:
        if not self.enabled:
            return []
        out = []
        with self.lock:
            for d in self.root.iterdir():
                if not SID_RE.match(d.name) or not (d / "info.json").is_file():
                    continue
                try:
                    info = self._read(d)
                except Exception:
                    continue
                info.pop("key", None)
                info["size"] = sum(f.stat().st_size for f in d.iterdir() if f.is_file())
                info["expires_at"] = info["ts"] + self.keep_days * 86400
                info["kind_label"] = KINDS.get(info.get("kind"), info.get("kind"))
                info["has_result"] = (d / "result.hwpx").is_file()
                out.append(info)
        return sorted(out, key=lambda x: x["ts"], reverse=True)

    def zip(self, sid: str, dest: Path) -> Optional[str]:
        """원본 PDF(원래 이름)·결과 HWPX·info.json 을 ZIP 하나로. 내려받을 파일 이름을 돌려준다."""
        d = self._dir(sid)
        if d is None:
            return None
        with self.lock:
            info = self._read(d)
            with zipfile.ZipFile(dest, "w", zipfile.ZIP_STORED) as z:  # PDF·HWPX는 이미 압축돼 있다
                many = len(info["files"]) > 1
                for i, f in enumerate(info["files"], 1):
                    z.write(d / f["stored"], f"{i:02d}_{f['name']}" if many else f["name"])
                if (d / "result.hwpx").is_file():
                    z.write(d / "result.hwpx", "result.hwpx")
                info.pop("key", None)
                z.writestr("info.json", json.dumps(info, ensure_ascii=False, indent=1))
        return f"문제파일_{sid}.zip"

    def delete(self, sid: str) -> bool:
        d = self._dir(sid)
        if d is None:
            return False
        with self.lock:
            shutil.rmtree(d, ignore_errors=True)
        return True

    def prune(self) -> None:
        """보관 기간이 지난 것, 개수·용량을 넘는 것(오래된 것부터), 저장하다 만 임시 폴더를 지운다."""
        if not self.enabled or not self.root.is_dir():
            return
        now = time.time()
        with self.lock:
            kept = []
            for d in self.root.iterdir():
                if not d.is_dir():
                    continue
                if d.name.endswith(".tmp"):
                    if now - d.stat().st_mtime > 3600:
                        shutil.rmtree(d, ignore_errors=True)
                    continue
                try:
                    ts = self._read(d)["ts"]
                except Exception:
                    ts = d.stat().st_mtime
                if not SID_RE.match(d.name) or now - ts > self.keep_days * 86400:
                    shutil.rmtree(d, ignore_errors=True)
                    continue
                kept.append((ts, d, sum(f.stat().st_size for f in d.iterdir() if f.is_file())))
            kept.sort(key=lambda x: x[0])
            total = sum(s for _, _, s in kept)
            while kept and (len(kept) > self.max_count or total > self.max_mb * 1024 * 1024):
                _, d, s = kept.pop(0)
                shutil.rmtree(d, ignore_errors=True)
                total -= s
            self._pruned = now

    def maybe_prune(self) -> None:
        """청소 스레드가 자주 불러도 한 시간에 한 번만 정리한다."""
        if time.time() - self._pruned > 3600:
            self.prune()
