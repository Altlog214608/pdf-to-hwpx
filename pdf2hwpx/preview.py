"""웹 화면용 미리보기 정보: 1쪽 그림, 제목 후보, 지문/문제 샘플, 텍스트 레이어 진단."""
from __future__ import annotations

import re
from typing import Optional

import pymupdf as fitz

from .extract import extract
from .ir import build_document
from .model import AuxBlock, Para, Passage, Question


def text_layer_status(pdf_path: str) -> dict:
    """글자 정보가 있는 PDF인지 판별(스캔본/글자 깨짐 안내용)."""
    doc = fitz.open(pdf_path)
    n = doc.page_count
    chars = 0
    hangul = 0
    bad = 0
    for page in doc:
        t = page.get_text()
        chars += len(t.strip())
        hangul += len(re.findall(r"[가-힣]", t))
        bad += t.count("�") + len(re.findall(r"[-]", t))
    doc.close()
    per_page = chars / max(1, n)
    if per_page < 40:
        status = "scanned"  # 글자 정보가 거의 없음 = 이미지(스캔) PDF
    elif hangul < 0.2 * chars or bad > 0.05 * chars:
        status = "garbled"  # 글자는 있으나 한글이 깨져 있음
    else:
        status = "ok"
    return {"status": status, "pages": n, "chars_per_page": round(per_page)}


def _title_candidates(header_texts: list) -> list[str]:
    """1쪽 머리 영역 글자 중 제목 후보: 한글이 있고, 큰 글씨·긴 글 순."""
    best: dict[str, float] = {}
    for page, txt, size, y0 in header_texts:
        if page != 1:
            continue
        t = re.sub(r"\s+", " ", txt).strip()
        hangul = len(re.findall(r"[가-힣]", t))
        if len(t) < 4 or hangul < max(2, 0.3 * len(re.sub(r"\s", "", t))):
            continue  # 'I410-141-…' 같은 코드, 쪽 번호 제외
        best[t] = max(best.get(t, 0.0), size)
    ranked = sorted(best.items(), key=lambda kv: (-round(kv[1]), -len(kv[0])))
    return [t for t, _ in ranked][:6]


def _para_json(p: Para) -> dict:
    if p.kind != "text":
        return {"kind": p.kind}
    return {"kind": "text", "align": p.align, "role": p.role,
            "runs": [{"t": r.text, "u": r.underline, "b": r.bold} for r in p.runs]}


def sample_json(doc, max_passage_paras: int = 7) -> dict:
    """미리보기에 쓸 앞부분: 첫 지문 일부 + 첫 문제(보기 포함)."""
    passage: Optional[Passage] = next((x for x in doc.items if isinstance(x, Passage)), None)
    question: Optional[Question] = next((x for x in doc.items if isinstance(x, Question)), None)
    out: dict = {}
    if passage:
        paras = [p for p in passage.paras if p.kind != "image"][:max_passage_paras]
        out["passage"] = {"guide": passage.guide.text if passage.guide else "", "boxed": passage.boxed,
                          "paras": [_para_json(p) for p in paras],
                          "more": len(passage.paras) > len(paras)}
    if question:
        blocks = []
        for b in question.blocks[:1]:
            if isinstance(b, AuxBlock):
                blocks.append({"title": b.title, "paras": [_para_json(p) for p in b.paras[:3] if p.kind == "text"]})
        out["question"] = {"stem": _para_json(question.stem), "blocks": blocks,
                           "choices": [_para_json(c.para) for c in question.choices]}
    return out


def analyze(pdf_path: str, page_png_width: int = 900) -> dict:
    tl = text_layer_status(pdf_path)
    info: dict = {"text_layer": tl}
    doc = fitz.open(pdf_path)
    page = doc[0]
    zoom = page_png_width / max(1.0, page.rect.width)
    info["page1_png"] = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False).tobytes("png")
    doc.close()
    if tl["status"] == "scanned":
        return info
    ex = extract(pdf_path)
    d = build_document(ex)
    info["title_candidates"] = _title_candidates(ex.header_texts)
    info["sample"] = sample_json(d)
    info["stats"] = {"questions": len(d.questions), "passages": len(d.passages), "answers": len(d.answers),
                     "pages": tl["pages"]}
    ex.doc.close()
    return info
