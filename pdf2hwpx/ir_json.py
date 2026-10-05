"""IR -> 사람이 읽을 수 있는 JSON (회귀 비교/골든 테스트용)."""
from __future__ import annotations

from .model import AuxBlock, Document, Para, Passage, Question


def _para(p: Para) -> dict:
    d: dict = {"kind": p.kind}
    if p.kind == "text":
        d["text"] = p.text
        if any(r.underline for r in p.runs):
            d["underlined"] = [r.text for r in p.runs if r.underline]
        if any(r.bold for r in p.runs) and not all(r.bold for r in p.runs):
            d["bold"] = [r.text.strip() for r in p.runs if r.bold and r.text.strip()]
        if p.align != "LEFT":
            d["align"] = p.align
        if p.indent_pt:
            d["indent_pt"] = p.indent_pt
        if p.role:
            d["role"] = p.role
    elif p.kind == "table" and p.table is not None:
        t = p.table
        d["table"] = {"rows": len(t.ys) - 1, "cols": len(t.xs) - 1,
                      "cells": [{"r": c.row, "c": c.col, "rs": c.rowspan, "cs": c.colspan, "fill": c.fill,
                                 "paras": [_para(x) for x in c.paras]} for c in t.cells]}
    elif p.kind == "bracket":
        d["label"] = p.label
        d["paras"] = [_para(x) for x in p.children]
    elif p.kind == "image" and p.image is not None:
        im = p.image
        d["image"] = {"page": im.page, "bbox": [round(im.x0, 1), round(im.y0, 1), round(im.x1, 1), round(im.y1, 1)]}
    return d


def _block(b) -> dict:
    if isinstance(b, AuxBlock):
        return {"type": "aux", "title": b.title, "kind": b.kind, "diagram": b.diagram is not None,
                "paras": [_para(p) for p in b.paras]}
    return _para(b)


def document_to_json(doc: Document) -> dict:
    items = []
    for it in doc.items:
        if isinstance(it, Passage):
            items.append({"type": "passage", "id": it.id, "boxed": it.boxed, "questions": it.question_numbers,
                          "guide": it.guide.text if it.guide else "", "paras": [_para(p) for p in it.paras]})
        elif isinstance(it, Question):
            blocks = [_block(b) for b in it.blocks]
            items.append({"type": "question", "number": it.number, "qtype": it.qtype, "passage": it.passage_id,
                          "stem": it.stem.text, "blocks": blocks,
                          "choices": [c.para.text for c in it.choices],
                          "choice_credits": {c.label: [x.text for x in c.extra] for c in it.choices if c.extra}, "answer": it.answer,
                          "explanation": [p.text for p in it.explanation if p.kind == "text"],
                          "after": [_block(b) for b in it.after],
                          **({"grid": {"header": ["".join(r.text for r in h) for h in it.grid.header],
                                       "rows": [[lab] + ["".join(r.text for r in c) for c in cells]
                                                for lab, cells in it.grid.rows]}} if it.grid else {})})
        elif isinstance(it, AuxBlock):
            items.append({"type": "loose_box", **_block(it)})
        elif isinstance(it, Para):
            items.append({"type": "loose", **_para(it)})
    return {"items": items, "warnings": doc.warnings, "loose_items": doc.loose_notes}
