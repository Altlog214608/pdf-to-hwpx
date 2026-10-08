"""한글 시험지 파일(HWPX)의 바탕쪽을 웹/CLI에서 고르는 프리셋으로 만든다(개발자용, 한 번만).

  python tools/make_preset.py 시험지.hwpx --id hakwon1 --name "학원 1"

바탕쪽 XML과 그것이 쓰는 글자·문단 모양, 테두리, 탭, 글꼴, 그림만 담고(본문은 담지 않음), 제목 칸 글자는 비운다.
결과: pdf2hwpx/presets/<id>.json — 저장소에 넣는다. 웹사이트에서는 파일을 올려 뽑지 않고 이 프리셋만 고른다.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pdf2hwpx.master_template import _p_span, check_template, extract_template  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("hwpx")
    ap.add_argument("--id", required=True, help="영문 소문자·숫자, 예: hakwon1")
    ap.add_argument("--name", required=True, help="화면에 보일 이름, 예: 학원 1")
    a = ap.parse_args(argv)
    if not re.fullmatch(r"[a-z0-9_-]{1,32}", a.id):
        ap.error("--id 는 영문 소문자·숫자")
    pkg = extract_template(Path(a.hwpx).read_bytes())
    span = _p_span(pkg["inner"], pkg["title_index"])
    if span:  # 원래 파일의 제목 글자는 남기지 않는다(변환할 때 입력한 제목으로 바뀜)
        p = pkg["inner"][span[0]:span[1]]
        p = re.sub(r"<hp:t>[^<]*</hp:t>", "<hp:t>시험 제목</hp:t>", p, count=1)
        p = re.sub(r"(</hp:t>.*?)<hp:t>[^<]*</hp:t>", r"\1<hp:t/>", p, flags=re.S)
        pkg["inner"] = pkg["inner"][:span[0]] + p + pkg["inner"][span[1]:]
    pkg["title_text"] = "시험 제목"
    for r in pkg["title_runs"][:1]:
        r["t"] = "시험 제목"
    pkg["title_runs"] = pkg["title_runs"][:1]
    pkg.update(id=a.id, name=a.name)
    check_template(pkg)
    out = ROOT / "pdf2hwpx" / "presets" / f"{a.id}.json"
    out.write_text(json.dumps(pkg, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{out.relative_to(ROOT)}: 학원 칸 '{''.join(r['t'] for r in pkg['academy_runs'])}', "
          f"글꼴 {sorted({r['font'] for r in pkg['academy_runs'] + pkg['title_runs']})}, {out.stat().st_size // 1024}KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
