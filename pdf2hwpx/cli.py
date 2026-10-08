"""명령줄 실행: python v0_5_pdf_to_hwpx.py "파일.pdf" [더 많은 파일/폴더 ...]"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from . import VERSION
from .convert import convert, convert_many
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
    ap.add_argument("--academy", default="", help="바탕쪽 학원 이름(검은 칸 흰 글씨), 예: 김한춘")
    ap.add_argument("--academy-sub", default="", help="학원 이름 뒤 작은 글씨, 예: 국어전문학원")
    ap.add_argument("--academy-size", type=float, default=14.0, help="학원 이름 글자 크기 pt (기본: 14)")
    ap.add_argument("--academy-sub-size", type=float, default=11.0, help="뒷부분 글자 크기 pt (기본: 11)")
    ap.add_argument("--title-size", type=float, default=14.0, help="제목 글자 크기 pt (기본: 14)")
    ap.add_argument("--logo", help="학원 로고 그림 파일(PNG/JPG). 지정하면 학원 이름 대신 사용")
    ap.add_argument("--frame", action="store_true", help="페이지 바깥 네모 테두리")
    ap.add_argument("--template", metavar="시험지.hwpx", help="이 한글 파일의 바탕쪽(학원 칸·제목 칸·테두리·글꼴)을 그대로 쓰기")
    ap.add_argument("--title-color", default="#000000", help="제목 글자 색, 예: #555555")
    ap.add_argument("--endnotes", action="store_true", help="정답·해설을 각 문제에 연결된 미주로 넣기")
    ap.add_argument("--no-auto-number", action="store_true", help="문제 번호를 한글 문단 번호 대신 글자로 넣기")
    ap.add_argument("--merge", metavar="통합본.hwpx", help="입력 PDF를 순서대로 이어 한 파일로(문제·정답 번호를 이어서 매김)")
    args = ap.parse_args(argv)
    try:  # Windows 콘솔(cp949)에서 특수 문자 때문에 멈추지 않게
        sys.stdout.reconfigure(errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

    logo = Path(args.logo).read_bytes() if args.logo else None
    template = None
    if args.template:
        from .master_template import TemplateError, extract_template
        try:
            template = extract_template(Path(args.template).read_bytes())
        except TemplateError as e:
            print(f"바탕쪽을 가져오지 못했습니다: {e}", file=sys.stderr)
            return 2
    style = DocStyle(body_font=args.font, body_size=args.size, title=args.title, academy_name=args.academy,
                     academy_sub=args.academy_sub, academy_size=args.academy_size,
                     academy_sub_size=args.academy_sub_size, title_size=args.title_size, logo=logo, template=template, frame=args.frame, title_color=args.title_color,
                     answers_as_endnotes=args.endnotes, auto_number=not args.no_auto_number).validate()
    pdfs = _expand(args.inputs)
    if not pdfs:
        print("입력 PDF가 없습니다.", file=sys.stderr)
        return 2
    if args.merge:
        res = convert_many([str(p) for p in pdfs], args.merge, style=style)
        v = res["validation"]
        print(json.dumps({"files": res["source_files"], "status": v["status"], "hwpx": res["hwpx"],
                          "questions": v["checks"].get("question_count"), "answers": v["checks"].get("answer_count"),
                          "root_causes": v["root_causes"][:3], "warnings": v["warnings"][:5]}, ensure_ascii=False, indent=2))
        return {"PASS": 0, "WARN": 0}.get(v["status"], 1)
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
