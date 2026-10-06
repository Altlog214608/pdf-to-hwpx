"""여러 PDF의 IR을 한 문서(통합본)로 잇는다.

뒤 파일의 문제 번호를 앞 파일의 마지막 번호 다음부터 다시 매기고, 번호가 글자로 들어 있는 곳
(발문 앞 `1.`, 지문 안내 `[1~3]`, 정답 머리 `1) [정답]`)도 같이 고친다. 미주 정답은 번호를 한글이 매기므로
문제 번호만 맞으면 따라온다.
"""
from __future__ import annotations

import re
from pathlib import Path

from .model import Document, Para, Passage, Question, Run

STEM_NO_RE = re.compile(r"^(\s*)(\d{1,3})(\s*\.)")
ANSWER_NO_RE = re.compile(r"^(\s*)(\d{1,3})(\s*\))")
RANGE_RE = re.compile(r"(\[\s*)(\d{1,3})(\s*[~∼～\-–]\s*)(\d{1,3})(\s*\])")


def _replace_span(runs: list[Run], start: int, end: int, new: str) -> None:
    """runs를 이은 글자에서 [start, end)를 new로 바꾼다. 글자 모양은 시작 글자가 든 조각을 따른다."""
    pos = 0
    placed = False
    for r in runs:
        a, b = pos, pos + len(r.text)
        pos = b
        lo, hi = max(a, start), min(b, end)
        if lo >= hi:
            continue
        if not placed:
            r.text = r.text[:lo - a] + new + r.text[hi - a:]
            placed = True
        else:
            r.text = r.text[:lo - a] + r.text[hi - a:]


def _renumber(runs: list[Run], pat: re.Pattern, fn) -> None:
    text = "".join(r.text for r in runs)
    edits = []
    for m in pat.finditer(text):
        for g in range(1, (m.lastindex or 0) + 1):
            s = m.group(g)
            if s.isdigit():
                edits.append((m.start(g), m.end(g), str(fn(int(s)))))
        if pat is not RANGE_RE:
            break
    for a, b, new in reversed(edits):  # 뒤에서부터 바꿔야 앞 위치가 그대로다
        _replace_span(runs, a, b, new)


def _shift_para(p: Para, pat: re.Pattern, off: int) -> None:
    if p is not None and p.kind == "text":
        _renumber(p.runs, pat, lambda n: n + off)


def merge_documents(docs: list[Document], names: list[str] | None = None) -> Document:
    if len(docs) == 1:
        return docs[0]
    names = names or [Path(d.source).name for d in docs]
    out = Document(source=docs[0].source)
    off = 0
    pid_off = 0
    for d, name in zip(docs, names):
        last = 0
        max_pid = 0
        for it in d.items:
            if isinstance(it, Question):
                it.number += off
                last = max(last, it.number)
                _shift_para(it.stem, STEM_NO_RE, off)
                if it.passage_id is not None:
                    it.passage_id += pid_off
            elif isinstance(it, Passage):
                max_pid = max(max_pid, it.id)
                it.id += pid_off
                it.question_numbers = [n + off for n in it.question_numbers]
                _shift_para(it.guide, RANGE_RE, off)
            out.items.append(it)
        for a in d.answers:
            a.number += off
            last = max(last, a.number)
            _shift_para(a.head, ANSWER_NO_RE, off)
            out.answers.append(a)
        out.warnings.extend(f"{name}: {w}" for w in d.warnings)
        out.image_only_lines.extend(d.image_only_lines)
        out.loose_notes.extend(f"{name} {x}" for x in d.loose_notes)
        for k, v in d.stats.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                out.stats[k] = out.stats.get(k, 0) + v
        off = max(off, last)
        pid_off += max_pid
    out.stats["merged_files"] = len(docs)
    return out
