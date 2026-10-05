"""PDF 한 개 변환 (CLI와 향후 웹 서버가 공통으로 쓰는 진입점)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import pymupdf as fitz

from . import VERSION
from .extract import extract
from .hwpx_writer import HwpxWriter
from .ir import build_document
from .ir_json import document_to_json
from .validate import validate


def _free_path(path: Path, overwrite: bool) -> Path:
    if overwrite or not path.exists():
        return path
    n = 2
    while True:
        cand = path.with_name(f"{path.stem}_run{n:02d}{path.suffix}")
        if not cand.exists():
            return cand
        n += 1


def _preview_png(ex) -> Optional[bytes]:
    try:
        page = ex.doc[0]
        zoom = 724 / max(1.0, page.rect.width)
        return page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False).tobytes("png")
    except Exception:
        return None


def convert(pdf_path: str, out_dir: Optional[str] = None, overwrite: bool = False,
            write_json: bool = True, debug: bool = False, hwpx_path: Optional[str] = None) -> dict:
    pdf = Path(pdf_path)
    if not pdf.exists():
        raise FileNotFoundError(pdf_path)
    target_dir = Path(out_dir) if out_dir else pdf.parent
    target_dir.mkdir(parents=True, exist_ok=True)
    out = Path(hwpx_path) if hwpx_path else _free_path(target_dir / f"{pdf.stem}.hwpx", overwrite)

    ex = extract(str(pdf))
    doc = build_document(ex)
    writer = HwpxWriter(doc, preview_png=_preview_png(ex))
    write_stats = writer.write(str(out))
    report = validate(ex, doc, str(out))
    result = {
        "version": VERSION,
        "source_file": pdf.name,
        "hwpx": str(out.resolve()),
        "extraction": ex.stats,
        "ir_stats": doc.stats,
        "writer": write_stats,
        "validation": report,
        "document": document_to_json(doc),
    }
    if debug:
        result["debug_lines"] = [
            {"page": ln.page, "col": ln.col, "box": ln.box, "x0": round(ln.x0, 1), "x1": round(ln.x1, 1),
             "y0": round(ln.y0, 1), "ts": ln.trailing_space, "text": ln.text}
            for pm in ex.pages for ln in pm.lines]
    if write_json:
        jp = out.with_name(out.stem + "_result.json")
        jp.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        result["json"] = str(jp.resolve())
    ex.doc.close()
    return result
