"""바탕쪽 프리셋: 선생님이 한글에서 만든 시험지의 바탕쪽(tools/make_preset.py 로 한 번 뽑아 둔 JSON).

웹·CLI에서는 파일을 올려 뽑지 않고 여기 있는 프리셋 이름(id)만 고른다.
"""
from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Optional


def _files() -> dict[str, object]:
    return {f.name[:-5]: f for f in resources.files(__name__).iterdir() if f.name.endswith(".json")}


@lru_cache(maxsize=None)
def load(preset_id: str) -> Optional[dict]:
    """id 의 바탕쪽 묶음(master_template 형식). 없으면 None."""
    f = _files().get(str(preset_id))
    return json.loads(f.read_text(encoding="utf-8")) if f else None


def list_presets() -> list[dict]:
    """화면에 보일 요약(바탕쪽 XML 없이): id, 이름, 학원 칸·제목 칸 글자 모양, 글꼴 이름."""
    out = []
    for pid in sorted(_files()):
        p = load(pid)
        out.append({"id": pid, "name": p.get("name", pid), "academy_runs": p.get("academy_runs", []),
                    "title_runs": p.get("title_runs", []), "font_names": p.get("font_names", [])})
    return out
