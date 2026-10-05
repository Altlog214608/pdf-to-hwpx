"""명령줄 실행: python v0_5_pdf_to_hwpx.py "파일.pdf" [더 많은 파일/폴더 ...]"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from . import VERSION
from .convert import convert
from .style import DocStyle


def _expand(inputs: list[str]) -> list[Path]:
    out: list[Path] = []
    for s in inputs:
        p = Path(s)
        if p.is_dir():
            out.extend(sorted(p.glob("*.pdf")))
        else:
            out.append(p)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=f"PDF -> HWPX 변환기 v{VERSION} (한글 설치 불필요)")
    ap.add_argument("inputs", nargs="+", help="PDF 파일 또는 PDF가 들어 있는 폴더")
    ap.add_argument("--out-dir", help="출력 폴더 (기본: PDF와 같은 폴더)")
    ap.add_argument("--overwrite", action="store_true", help="같은 이름 HWPX가 있으면 덮어쓰기 (기본: _run02.. 새 이름)")
    ap.add_argument("--no-json", action="store_true", help="결과 JSON을 쓰지 않음")
    ap.add_argument("--debug", action="store_true", help="JSON에 줄 단위 추출 정보 포함")
    ap.add_argument("--font", default="함초롬바탕", help="본문 글꼴 (기본: 함초롬바탕)")
    ap.add_argument("--size", type=float, default=10.0, help="본문 글자 크기 pt (기본: 10)")
    ap.add_argument("--title", default="", help="바탕쪽 제목, 예: \"[중간 대비] 2. 품격을 높이는 언어생활 ①\"")
    ap.add_argument("--academy", default="", help="바탕쪽 학원 이름(검은 칸 흰 글씨)")
    ap.add_argument("--logo", help="학원 로고 그림 파일(PNG/JPG). 지정하면 학원 이름 대신 사용")
    ap.add_argument("--frame", action="store_true", help="페이지 바깥 네모 테두리")
    args = ap.parse_args(argv)
    try:  # Windows 콘솔(cp949)에서 특수 문자 때문에 멈추지 않게
        sys.stdout.reconfigure(errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

    logo = Path(args.logo).read_bytes() if args.logo else None
    style = DocStyle(body_font=args.font, body_size=args.size, title=args.title, academy_name=args.academy,
                     logo=logo, frame=args.frame).validate()
    pdfs = _expand(args.inputs)
    if not pdfs:
        print("입력 PDF가 없습니다.", file=sys.stderr)
        return 2
    rows = []
    worst = 0
    for pdf in pdfs:
        t0 = time.time()
        try:
            res = convert(str(pdf), out_dir=args.out_dir, overwrite=args.overwrite,
                          write_json=not args.no_json, debug=args.debug, style=style)
        except Exception as e:  # 한 파일 실패가 일괄 실행을 멈추지 않게
            rows.append({"file": pdf.name, "status": "ERROR", "error": f"{type(e).__name__}: {e}"})
            worst = max(worst, 2)
            continue
        v = res["validation"]
        c = v["checks"]
        rows.append({
            "file": pdf.name, "status": v["status"], "seconds": round(time.time() - t0, 1),
            "questions": f"{c.get('question_count')} ({c.get('objective')}/{c.get('subjective')})",
            "boxes": f"{c.get('box_groups')}/{c.get('expected_boxes')}",
            "pictures": c.get("pictures"), "coverage": c.get("text_coverage"),
            "hwpx": res["hwpx"], "root_causes": v["root_causes"][:3], "warnings": v["warnings"][:5],
        })
        worst = max(worst, {"PASS": 0, "WARN": 0, "FAIL": 1}.get(v["status"], 1))
    print(json.dumps(rows if len(rows) > 1 else rows[0], ensure_ascii=False, indent=2))
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
