"""생성된 HWPX 검증.

이전 버전처럼 "XML 속성이 있다"만 보지 않고 다음을 직접 잰다.
- 패키지/XML 무결성, 스타일 참조 무결성(깨진 속성값 포함)
- 원문 대비 텍스트 커버리지(글자 n-gram)와 누락 줄 목록
- 박스 개수(IR 기대값 vs HWPX 테두리 묶음), 보조박스 뒤 빈 문단, 문제 번호 순서, 선택지 수
- 실패 시 근본 원인을 앞에서부터 한 줄씩(root_causes)
"""
from __future__ import annotations

import re
import zipfile
import xml.etree.ElementTree as ET

from .extract import Extraction
from .model import AuxBlock, Box, Document, Line

NS = {
    "hp": "http://www.hancom.co.kr/hwpml/2011/paragraph",
    "hh": "http://www.hancom.co.kr/hwpml/2011/head",
    "hs": "http://www.hancom.co.kr/hwpml/2011/section",
    "opf": "http://www.idpf.org/2007/opf/",
}
NGRAM = 6


def _compact(s: str) -> str:
    return re.sub(r"\s+", "", s)


def _shingles(s: str, n: int = NGRAM) -> set[str]:
    return {s[i:i + n] for i in range(max(0, len(s) - n + 1))}


def read_hwpx(path: str) -> dict:
    """HWPX를 읽어 문단 목록과 스타일 정보를 돌려준다(검증/테스트 공용)."""
    out: dict = {"errors": [], "paragraphs": [], "pictures": 0}
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        infos = z.infolist()
        if not infos or infos[0].filename != "mimetype" or infos[0].compress_type != zipfile.ZIP_STORED:
            out["errors"].append("mimetype이 첫 항목(무압축)이 아님")
        xml_parts = {}
        for n in names:
            if n.endswith((".xml", ".hpf", ".rdf")):
                data = z.read(n)
                try:
                    xml_parts[n] = ET.fromstring(data)
                except ET.ParseError as e:
                    out["errors"].append(f"XML 파싱 실패: {n}: {e}")
        hpf = xml_parts.get("Contents/content.hpf")
        sections = []
        if hpf is not None:
            for item in hpf.iter(f"{{{NS['opf']}}}item"):
                href = item.get("href")
                if href not in names:
                    out["errors"].append(f"manifest 항목 누락: {href}")
                if re.match(r"Contents/section\d+\.xml", href or ""):
                    sections.append(href)
        head = xml_parts.get("Contents/header.xml")
        para_props, char_ids, bf_solid = {}, set(), {}
        if head is not None:
            for bf in head.iter(f"{{{NS['hh']}}}borderFill"):
                lb = bf.find("hh:leftBorder", NS)
                bf_solid[bf.get("id")] = lb is not None and lb.get("type") not in (None, "NONE")
            for pp in head.iter(f"{{{NS['hh']}}}paraPr"):
                b = pp.find("hh:border", NS)
                al = pp.find("hh:align", NS)
                ls = pp.find(".//hh:lineSpacing", NS)
                if ls is not None and not re.fullmatch(r"[A-Z_]+", ls.get("type") or ""):
                    out["errors"].append(f"paraPr {pp.get('id')} lineSpacing type 값 손상: {ls.get('type')!r}")
                para_props[pp.get("id")] = {
                    "bf": b.get("borderFillIDRef") if b is not None else None,
                    "connect": b.get("connect") if b is not None else "0",
                    "align": al.get("horizontal") if al is not None else None,
                }
            for cp in head.iter(f"{{{NS['hh']}}}charPr"):
                char_ids.add(cp.get("id"))
            for tag, ids in (("paraProperties", para_props), ("charProperties", char_ids)):
                el = head.find(f".//hh:{tag}", NS)
                if el is not None and int(el.get("itemCnt", "-1")) != len(ids):
                    out["errors"].append(f"{tag} itemCnt 불일치 ({el.get('itemCnt')} != {len(ids)})")
        for sec in sorted(sections):
            root = xml_parts.get(sec)
            if root is None:
                continue
            for p in root.findall("hp:p", NS):
                pid = p.get("paraPrIDRef")
                if pid not in para_props:
                    out["errors"].append(f"{sec}: 없는 paraPr {pid}")
                for r in p.iter(f"{{{NS['hp']}}}run"):
                    if r.get("charPrIDRef") not in char_ids:
                        out["errors"].append(f"{sec}: 없는 charPr {r.get('charPrIDRef')}")
                text = "".join(t.text or "" for t in p.iter(f"{{{NS['hp']}}}t"))
                pics = len(list(p.iter(f"{{{NS['hp']}}}pic")))
                out["pictures"] += pics
                prop = para_props.get(pid, {})
                boxed = bool(bf_solid.get(prop.get("bf"))) and prop.get("connect") == "1"
                out["paragraphs"].append({"section": sec, "pp": pid, "text": text, "pics": pics,
                                          "boxed": boxed, "bf": prop.get("bf"), "align": prop.get("align")})
        out["bindata"] = len([n for n in names if n.startswith("BinData/")])
    return out


def _source_lines(ex: Extraction) -> list[Line]:
    lines: list[Line] = []
    for it in ex.flow:
        if isinstance(it, Line):
            lines.append(it)
        elif isinstance(it, Box):
            lines.extend(x for x in it.all_items() if isinstance(x, Line))
    return lines


def validate(ex: Extraction, doc: Document, hwpx_path: str) -> dict:
    hx = read_hwpx(hwpx_path)
    causes: list[str] = []
    warns: list[str] = list(doc.warnings)
    checks: dict = {}

    checks["package_status"] = "FAIL" if hx["errors"] else "PASS"
    if hx["errors"]:
        causes.append("패키지/XML: " + hx["errors"][0])

    paras = hx["paragraphs"]

    # ---- 텍스트 커버리지 ----
    skip = {id(l) for l in doc.image_only_lines}
    src_lines = [l for l in _source_lines(ex) if id(l) not in skip]
    out_text = _compact("".join(p["text"] for p in paras))
    out_sh = _shingles(out_text)
    # 줄 단위 n-gram: 읽기 순서가 바뀌거나 그림으로 대체된 줄이 있어도 경계 n-gram이 왜곡되지 않게
    src_sh: set[str] = set()
    for l in src_lines:
        src_sh |= _shingles(_compact(l.text))
    coverage = len(src_sh & out_sh) / max(1, len(src_sh))
    precision = len(src_sh & out_sh) / max(1, len(out_sh))
    missing = []
    for l in src_lines:
        c = _compact(l.text)
        sh = _shingles(c)
        if len(c) >= NGRAM and sh and len(sh & out_sh) / len(sh) < 0.5:
            missing.append(f"p{l.page}: {l.text[:40]}")
    checks["text_coverage"] = round(coverage, 4)
    checks["text_precision"] = round(precision, 4)
    checks["missing_source_lines"] = missing[:30]
    if coverage < 0.97:
        checks["text_coverage_status"] = "FAIL"
        causes.append(f"원문 텍스트 커버리지 {coverage:.1%} (누락 줄 예: {missing[:1]})")
    elif coverage < 0.995 or missing:
        checks["text_coverage_status"] = "WARN"
        warns.append(f"원문 텍스트 커버리지 {coverage:.2%}, 누락 의심 줄 {len(missing)}개")
    else:
        checks["text_coverage_status"] = "PASS"

    # ---- 문제 번호/선택지 ----
    qs = doc.questions
    checks["question_count"] = len(qs)
    checks["objective"] = sum(1 for q in qs if q.qtype == "objective")
    checks["subjective"] = len(qs) - checks["objective"]
    seq_ok = [q.number for q in qs] == list(range(1, len(qs) + 1))
    sec0 = [p for p in paras if p["section"].endswith("section0.xml")]
    k = 0
    for p in sec0:
        if k < len(qs) and re.match(rf"^\s*{qs[k].number}\s*\.", p["text"]):
            k += 1
    checks["question_order_status"] = "PASS" if seq_ok and k == len(qs) and qs else "FAIL"
    if checks["question_order_status"] == "FAIL":
        causes.append(f"문제 번호 순서/누락 (IR {len(qs)}개, HWPX에서 순서대로 찾은 수 {k})")
    bad_choices = [q.number for q in qs if q.choices and len(q.choices) != 5]
    checks["choice_count_status"] = "PASS" if not bad_choices else "WARN"
    if bad_choices:
        warns.append(f"선택지가 5개가 아닌 문제: {bad_choices}")
    if doc.answers and len(doc.answers) != len(qs):
        causes.append(f"정답 수({len(doc.answers)}) != 문제 수({len(qs)})")
    # 원문에 정답 머리줄이 있는데 정답부로 인식하지 못한 경우(정답·해설이 마지막 문제에 붙어 버림)
    from .ir import ANSWER_HEAD_RE
    src_heads = sum(1 for l in src_lines if ANSWER_HEAD_RE.match(l.text))
    checks["answer_heads_in_source"] = src_heads
    if src_heads and len(doc.answers) < src_heads:
        causes.append(f"정답·해설 인식 실패: 원문 정답 머리줄 {src_heads}개 중 {len(doc.answers)}개만 인식")
    checks["answer_count"] = len(doc.answers)
    checks["loose_items"] = doc.loose_notes[:20]  # 문제/지문 밖 내용(단원 제목 박스 등) — 경고 아님

    # ---- 박스 ----
    expected_aux = sum(1 for q in qs for b in q.blocks + q.after if isinstance(b, AuxBlock)) \
        + sum(1 for it in doc.items if isinstance(it, AuxBlock))
    expected_passage = sum(1 for p in doc.passages if p.boxed and p.paras)
    groups = []
    cur = None
    for i, p in enumerate(sec0):
        if p["boxed"]:
            if cur is None:
                cur = [i, i]
            else:
                cur[1] = i
        elif cur is not None:
            groups.append(tuple(cur))
            cur = None
    if cur is not None:
        groups.append(tuple(cur))
    checks["box_groups"] = len(groups)
    checks["expected_boxes"] = expected_aux + expected_passage
    checks["box_count_status"] = "PASS" if len(groups) == expected_aux + expected_passage else "FAIL"
    if checks["box_count_status"] == "FAIL":
        causes.append(f"테두리 박스 수 {len(groups)} != 기대 {expected_aux + expected_passage} (지문 {expected_passage} + 보조 {expected_aux})")
    # 지문 박스(안내문 ※ 바로 뒤) 외의 보조박스 뒤에는 테두리 없는 빈 문단이 와야 한다
    no_spacer = 0
    for a, b in groups:
        prev = sec0[a - 1]["text"] if a > 0 else ""
        if re.match(r"^\s*(※|\[\s*\d+\s*[~∼～\-–]\s*\d+\s*\])", prev):
            continue
        nxt = sec0[b + 1] if b + 1 < len(sec0) else None
        if nxt is not None and (nxt["text"].strip() or nxt["pics"]):
            no_spacer += 1
    checks["box_spacer_missing"] = no_spacer
    checks["aux_spacer_status"] = "PASS" if no_spacer == 0 else "FAIL"
    if no_spacer:
        causes.append(f"박스 바로 뒤에 빈 문단이 없는 곳 {no_spacer}개 (테두리가 다음 줄 침범 위험)")

    # ---- 그림 ----
    checks["pictures"] = hx["pictures"]
    checks["bindata"] = hx["bindata"]
    if hx["pictures"] != hx["bindata"]:
        causes.append(f"그림 개체 수 {hx['pictures']} != BinData {hx['bindata']}")

    status = "FAIL" if causes else ("WARN" if warns else "PASS")
    return {"status": status, "root_causes": causes, "warnings": warns, "checks": checks}
