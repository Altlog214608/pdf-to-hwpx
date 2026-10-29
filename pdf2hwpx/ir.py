"""페이지 모델 -> IR(지문/문제/보조박스/선택지/정답).

핵심 원칙
- 문단 나눔은 글자 수가 아니라 줄의 위치(기하)로 판단한다.
  산문 줄은 단/박스 오른쪽 끝까지 차고(양쪽 정렬), 시 행·목록·문단 끝 줄은 짧다.
- 줄을 이을 때 텍스트 레이어의 줄 끝 공백 유무로 띄어쓰기를 정한다(재띄어쓰기 휴리스틱 없음).
- 연 구분(행간의 약 2배 간격)은 빈 문단으로 보존한다.
- 박스 안의 그림은 그 박스에, 도형이 그려진 박스는 영역 이미지로 보존한다.
- 문제 번호는 "기대 번호 + 큰 글씨 + 박스 밖" 조건으로만 인정한다(보기 안의 1. 2. 오인 방지).
"""
from __future__ import annotations

import dataclasses
import re
import statistics
from collections import Counter, defaultdict
from typing import Callable, Optional, Union

from .extract import Extraction, TITLE_RE
from .model import (CIRCLED_DIGITS, AnswerEntry, AuxBlock, Box, Cell, Choice, ChoiceGrid, Document, Glyph, ImageEl, Line,
                    Para, Passage, Question, Run, TableEl, WRITE_RE)

GUIDE_RE = re.compile(r"^\s*(※|\[\s*\d+\s*[~∼～\-–]\s*\d+\s*\])")
ANSWER_HEAD_RE = re.compile(r"^\s*(\d{1,3})\s*\)\s*\[?\s*정답\s*\]?")  # "1) [정답] ④" / "1) 정답 ④"
EXPL_RE = re.compile(r"^\s*\[\s*해설\s*\]")
LABEL_RE = re.compile(r"^\s*(\([가-힣A-Za-z]\)|\[[A-Z가-힣]\]|<[가-힣]\>)\s*$")
# 줄 머리에 오면 새 문단을 시작하는 표지 (원문자/목록/화자/섹션 라벨 등)
MARKER_RE = re.compile(
    r"^\s*(?:[①-⑳]|[㉠-㉻ⓐ-ⓩ](?=\s)|\([가-힣A-Za-z0-9]\)(?=\s|$)|[ㄱ-ㅎ]\s*\.|[A-Z]\s*\.|\d{1,2}\s*\.(?!\d)"
    r"|[-–—•·▪◦○●□■◇◆※]\s|[가-힣A-Za-z]{1,6}\s?:|S#|\[[^\]]{1,20}\])")

BodyBounds = Callable[[Line], tuple[float, float]]


class _BracketGroup:
    def __init__(self, bid: int, label: str, lines: list):
        self.id, self.label, self.lines = bid, label, lines


# ------------------------------------------------------------- helpers ----

def _same_look(a: Run, b: Run) -> bool:
    return a.underline == b.underline and a.bold == b.bold and a.color == b.color and a.size == b.size \
        and a.shade == b.shade and a.boxed == b.boxed


def _runs_from_glyphs(glyphs: list[Glyph], bold: bool = False) -> list[Run]:
    """글자 -> 런. 원문의 밑줄과 굵게(지문 속 강조 시어 등), 글자 색과 크기(0.5pt 단위)를 보존한다."""
    runs: list[Run] = []
    for g in glyphs:
        r = Run(g.c, g.underline, bold or g.bold, g.color, round(g.size * 2) / 2 if not g.icon else 0.0, shade=g.shade,
                boxed=g.boxed)
        if g.is_space and runs:  # 공백은 앞 런의 모양을 따라가 런이 잘게 쪼개지지 않게
            p = runs[-1]
            r = Run(g.c, r.underline, p.bold, p.color, p.size, shade=p.shade if g.shade else None,
                    boxed=p.boxed and g.boxed)
        if runs and _same_look(runs[-1], r):
            runs[-1].text += g.c
        else:
            runs.append(r)
    return runs


_NARROW = {" ": 0.26, ".": 0.25, ",": 0.25, "‘": 0.25, "’": 0.25, "'": 0.22, "·": 0.25, "(": 0.346, ")": 0.346,
           "[": 0.36, "]": 0.36, ":": 0.286, ";": 0.286, "-": 0.31, "!": 0.33, "?": 0.47, '"': 0.41, "“": 0.41, "”": 0.41}


def _natural_em(c: str) -> float:
    """함초롬 계열 글꼴의 글자 폭(em) 어림값: 한글·한자·전각은 1, 숫자·로마자 약 0.56, 문장 부호는 좁게."""
    if len(c) != 1:  # 글자 여러 개를 담은 자리(알약 번호 "예제1 ")
        return sum(_natural_em(x) for x in c)
    if c in _NARROW:
        return _NARROW[c]
    o = ord(c)
    if 0x1100 <= o <= 0x11FF or 0x2E80 <= o <= 0x9FFF or 0xAC00 <= o <= 0xD7A3 or 0xE000 <= o <= 0xFAFF \
            or 0xFF00 <= o <= 0xFF60:
        return 1.0
    if c.isascii():
        return 0.56
    return 0.8


def _hangul_spacing(lines: list[Line]) -> int:
    """원문 자간(%): 줄 폭(첫 글자 ~ 마지막 글자)과 같은 글자를 자간 0으로 늘어놓은 폭의 차이를 글자 수로 나눈 값.
    원문이 장평·자간을 좁혀 찍었으면 같은 글꼴로도 줄이 길어져 넘어가므로 그만큼 좁힌다.
    양쪽 정렬로 벌어진 줄은 크게 나오므로 줄들 중 가장 좁은 값, 좁힐 때만(-2% 이하) 쓴다."""
    vals = []
    for seg in [sg for ln in lines for sg in _segments(ln)]:  # 넓게 띄운 간격은 따로(간격이 자간으로 잡히지 않게)
        gs = [g for g in seg if g.c != "\u2003" and not g.icon]
        while gs and gs[-1].is_space:
            gs.pop()
        if len(gs) < 8 or not gs[0].size:
            continue
        size = statistics.median(g.size for g in gs)
        if any(abs(g.size - size) > 0.15 * size for g in gs):
            continue
        if any(b.x0 - a.x0 < 0.5 * size for a, b in zip(gs, gs[1:]) if _natural_em(a.c) >= 1.0):
            continue  # 글자가 겹쳐 찍힌 줄(두 줄이 포개짐 등)은 재지 않는다
        actual = gs[-1].x0 - gs[0].x0 + _natural_em(gs[-1].c) * size
        natural = sum(_natural_em(g.c) for g in gs) * size
        vals.append((actual - natural) / (len(gs) * size))
    if not vals:
        return 0
    v = round(min(vals) * 100)
    return max(-20, v) if v <= -2 else 0


def _same_row(prev: Line, ln: Line) -> bool:
    """ln 이 prev 와 같은 줄 오른쪽에 떨어져 놓인 조각인가."""
    return (ln.page, ln.col) == (prev.page, prev.col) and abs(ln.y0 - prev.y0) < 0.4 * prev.size and ln.x0 > prev.x1


def _row_starts(lines: list[Line]) -> list[Line]:
    return [ln for i, ln in enumerate(lines) if i == 0 or not _same_row(lines[i - 1], ln)]


def _append_runs(dst: list[Run], src: list[Run]) -> None:
    for r in src:
        if dst and _same_look(dst[-1], r):
            dst[-1].text += r.text
        else:
            dst.append(Run(r.text, r.underline, r.bold, r.color, r.size, shade=r.shade, boxed=r.boxed))


def _clean_runs(runs: list[Run]) -> list[Run]:
    out: list[Run] = []
    for r in runs:
        blank = r.underline and not r.text.strip()  # 빈칸 밑줄은 공백 길이 그대로
        t = r.text if blank else re.sub(r"[ \t]{2,}", " ", r.text)
        if t:
            _append_runs(out, [Run(t, r.underline, r.bold, r.color, r.size, shade=r.shade, boxed=r.boxed)])
    if out:
        out[0].text = out[0].text.lstrip()
        if not (out[-1].underline and not out[-1].text.strip()):
            out[-1].text = out[-1].text.rstrip()
    return [r for r in out if r.text]


def _sub_line(ln: Line, glyphs: list[Glyph]) -> Line:
    while glyphs and glyphs[-1].is_space:
        glyphs = glyphs[:-1]
    while glyphs and glyphs[0].is_space:
        glyphs = glyphs[1:]
    solid = [g for g in glyphs if not g.is_space]
    return Line(ln.page, ln.col, glyphs, min(g.x0 for g in solid), min(g.y0 for g in solid),
                max(g.x1 for g in solid), max(g.y1 for g in solid), ln.size, ln.size, ln.trailing_space, ln.box)


class Builder:
    def __init__(self, ex: Extraction):
        self.ex = ex
        self.size = ex.body_size
        self.info = {pm.info.number: pm.info for pm in ex.pages}
        self.box_by_id: dict[int, Box] = {}
        for it in ex.flow:
            if isinstance(it, Box):
                self.box_by_id[it.id] = it
                for p in it.parts:
                    self.box_by_id[p.id] = p
        self.warnings: list[str] = []
        self.image_only_lines: list[Line] = []
        self.source_fixes: dict[int, str] = {}  # 원문 대조용으로 글자를 고친 줄(id -> 고친 글)
        self.dropped: list[str] = []  # 문제와 관계없어 버린 것(정답 표지/저작권 안내 등)
        full = [ln for pm in ex.pages for ln in pm.lines if self._is_full(ln)]
        ts = sum(1 for ln in full if ln.trailing_space)
        # 텍스트 레이어에 줄 끝 공백 정보가 거의 없는 PDF면 줄 이음 시 공백을 넣는다(대체 규칙).
        self.trailing_space_reliable = bool(full) and ts / len(full) >= 0.05
        if full and not self.trailing_space_reliable:
            self.warnings.append("텍스트 레이어에 줄 끝 공백 정보가 없어 줄 이음 시 공백을 넣는 대체 규칙을 사용함")

    # ---- geometry ----
    def col_bounds(self, ln: Union[Line, ImageEl]) -> tuple[float, float]:
        inf = self.info[ln.page]
        return inf.col_left if ln.col == 0 else inf.col_right

    def bounds(self, ln: Line) -> tuple[float, float]:
        if ln.cell is not None:
            return ln.cell
        if ln.box is not None and ln.box in self.box_by_id:
            b = self.box_by_id[ln.box]
            return b.x0, b.x1
        return self.col_bounds(ln)

    def rx(self, ln: Line) -> float:
        """단/박스 왼쪽 경계 기준 상대 x (단을 넘어가는 문단 비교용)."""
        return ln.x0 - self.bounds(ln)[0]

    def _is_full(self, ln: Line, right: Optional[float] = None) -> bool:
        if right is None:
            right = self.bounds(ln)[1]
        return ln.x1 >= right - max(1.2 * ln.size, 6.0)

    # ---- paragraphs ----
    def paragraphs(self, entries: list[Union[Line, ImageEl]], bold: bool = False,
                   stanza: bool = True) -> list[Para]:
        """줄 목록 -> 문단 목록. 산문은 잇고, 시 행/목록은 나누고, 연 구분은 빈 문단으로."""
        entries = self._group_brackets(entries)
        lines = [e for e in entries if isinstance(e, Line)]
        diffs = []
        for a, b in zip(lines, lines[1:]):
            if (a.page, a.col) == (b.page, b.col) and 0 < b.y0 - a.y0 < 3.5 * a.size:
                diffs.append(b.y0 - a.y0)
        pitch = statistics.median(diffs) if diffs else 1.5 * self.size
        xs = Counter(round(self.rx(l)) for l in lines)
        base_left = xs.most_common(1)[0][0] if xs else 0

        paras: list[Para] = []
        cur: list[Line] = []
        prev_line: Optional[Line] = None

        def flush():
            nonlocal cur
            if cur:
                paras.append(self._para_from_lines(cur, bold, base_left))
            cur = []

        for e in entries:
            if isinstance(e, ImageEl):
                flush()
                paras.append(Para(kind="image", image=e, align="CENTER", src=(e.page, e.y0, e.y1, e.page)))
                continue
            if isinstance(e, TableEl):
                flush()
                prev_t = paras[-1] if paras and paras[-1].kind in ("table", "tablerow") else None
                last_t = (prev_t.children[-1] if prev_t and prev_t.kind == "tablerow" else prev_t).table if prev_t else None
                if last_t is not None and e.y0 < last_t.y1 - 2 and e.y1 > last_t.y0 + 2 and e.x0 >= last_t.x1 - 2:
                    # 같은 높이에 나란히 놓인 표(초장 | 중장 | 종장)는 한 줄에 나란히
                    if prev_t.kind == "table":
                        paras[-1] = prev_t = Para(kind="tablerow", children=[prev_t], align="CENTER")
                    prev_t.children.append(Para(kind="table", table=self.table(e), align="CENTER"))
                    continue
                paras.append(Para(kind="table", table=self.table(e), align="CENTER", src=(e.page, e.y0, e.y1, e.page)))
                continue
            if isinstance(e, _BracketGroup):
                flush()
                first = e.lines[0]
                if paras and paras[-1].kind == "text" and stanza and prev_line is not None and self._stanza_gap(prev_line, first, pitch):
                    paras.append(Para(kind="blank"))
                paras.append(Para(kind="bracket", label=e.label, children=self.paragraphs(e.lines, bold, stanza)))
                prev_line = e.lines[-1]
                continue
            if not cur:
                if paras and paras[-1].kind == "text" and stanza and prev_line is not None and self._stanza_gap(prev_line, e, pitch):
                    paras.append(Para(kind="blank"))
                cur = [e]
                prev_line = e
                continue
            prev = cur[-1]
            brk = False
            blank = False
            same_area = (prev.page, prev.col) == (e.page, e.col)
            # 번호 붙은 줄("2. 윗글을 …")의 내어 쓴 다음 줄("은?"): 줄 간격이 본문보다 넓은 발문도 한 문단으로
            hang = same_area and re.match(r"\s*\d{1,2}\s?\.\s", cur[0].text) is not None and self._is_full(prev) \
                and 0.8 * e.size <= self.rx(e) - self.rx(cur[0]) <= 3 * e.size and 0 < e.y0 - prev.y0 <= 3 * e.size \
                and (len(cur) == 1 or abs(self.rx(e) - self.rx(cur[1])) < 0.4 * e.size)
            if _same_row(prev, e) and re.fullmatch(r"\(.{0,6}\)", e.text.strip()):
                # 같은 줄 오른쪽 끝에 떨어져 놓인 "( ✕ )" 같은 표시: 그 줄 문단 끝에 붙인다
                cur.append(e)
                prev_line = e
                continue
            if same_area:
                dy = e.y0 - prev.y0
                if dy > 1.3 * pitch and not hang:
                    brk = True
                    blank = stanza and dy > 1.7 * pitch
            elif stanza and self._cross_area_blank(prev, e, pitch):
                brk = True
                blank = True
            if not self._is_full(prev):
                brk = True
            first = cur[0]
            if MARKER_RE.match(e.text) and self.rx(e) <= self.rx(first) + 0.4 * e.size:
                brk = True
            if MARKER_RE.match(e.text.lstrip(" ✓✔√")) and prev.text.rstrip().endswith(("?", "？")):  # 발문 다음 선택지(정답 표시 ✓ 포함)
                brk = True
            if LABEL_RE.match(e.text) or LABEL_RE.match(prev.text):
                brk = True
            if e.frame != prev.frame:  # 띠 테두리 줄(낱말 띠)은 따로 한 문단
                brk = True
            if abs(e.size - prev.size) > 0.15 * max(e.size, prev.size) and not hang:  # 글자 크기가 바뀌면(본문 -> 작은 해설) 새 문단
                brk = True
            # (단이 바뀌면 단 왼쪽 경계가 몇 pt 다를 수 있어 여유를 더 둔다)
            if len(cur) >= 2 and self.rx(e) > self.rx(cur[1]) + (0.4 if same_area else 1.0) * e.size:
                brk = True  # 새 문단의 첫 줄 들여쓰기
            if brk:
                flush()
                if blank:
                    paras.append(Para(kind="blank"))
                cur = [e]
            else:
                cur.append(e)
            prev_line = e
        flush()
        return paras

    @staticmethod
    def _group_brackets(entries: list) -> list:
        """[A] 묶음 괄호 안의 줄들을 하나의 묶음으로 바꾸고, 괄호 옆 [A] 표시 줄은 묶음의 이름으로 쓴다."""
        if not any(isinstance(e, Line) and e.bracket is not None for e in entries):
            return entries
        labels = {e.bracket: e.text.strip() for e in entries if isinstance(e, Line) and e.bracket_label}
        out: list = []
        for e in entries:
            if isinstance(e, Line) and e.bracket_label:
                continue
            if isinstance(e, Line) and e.bracket is not None and e.bracket in labels:
                if out and isinstance(out[-1], _BracketGroup) and out[-1].id == e.bracket:
                    out[-1].lines.append(e)
                else:
                    out.append(_BracketGroup(e.bracket, labels[e.bracket], [e]))
                continue
            out.append(e)
        return out

    def table(self, t: TableEl) -> TableEl:
        """표 칸마다 문단을 만든다(칸 안은 시 연 구분 없이)."""
        for cl in t.cells:
            cl.paras = self.paragraphs(cl.items, stanza=False) if cl.items else []
            lines = [x for x in cl.items if isinstance(x, Line)]
            w = cl.x1 - cl.x0
            # 칸 안 모든 줄의 좌우 여백이 비슷하면 가운데 정렬 칸(표 칸은 대부분 이렇다)
            if t.lines and lines and all(abs((ln.x0 - cl.x0) - (cl.x1 - ln.x1)) <= max(4.0, 0.12 * w) for ln in lines):
                for p in cl.paras:
                    if p.kind == "text":
                        p.align, p.indent_pt = "CENTER", 0.0
            else:
                for p in cl.paras:
                    if p.kind == "text" and p.align == "CENTER":
                        p.align = "LEFT"
        return t

    @staticmethod
    def _emphasis_boundary(prev: Line, cur: Line) -> bool:
        """발문의 굵은 밑줄 강조어(않은/아닌 …)가 줄 끝에서 끝나면 단어 경계다.
        한글 PDF는 이때 줄 끝 공백을 텍스트 레이어에 남기지 않는다."""
        a = next((g for g in reversed(prev.glyphs) if not g.is_space), None)
        b = next((g for g in cur.glyphs if not g.is_space), None)
        return bool(a and b and a.underline and a.bold and not b.underline)

    def _stanza_gap(self, a: Line, b: Line, pitch: float) -> bool:
        return (a.page, a.col) == (b.page, b.col) and b.y0 - a.y0 > 1.7 * pitch

    def _cross_area_blank(self, a: Line, b: Line, pitch: float) -> bool:
        """단/페이지가 바뀌는 곳의 연 구분: 박스 안에서 앞 단 마지막 줄 아래에
        한 줄 이상 빈자리가 남았으면(빈 줄이 거기 있었던 것) 빈 문단으로 본다."""
        if (a.page, a.col) == (b.page, b.col) or a.box is None or a.box not in self.box_by_id:
            return False
        part = self.box_by_id[a.box]
        return part.y1 - a.y1 > 1.25 * pitch

    def _para_from_lines(self, lines: list[Line], bold: bool, base_left: float) -> Para:
        runs: list[Run] = []
        for i, ln in enumerate(lines):
            if i > 0:
                prev = lines[i - 1]
                if _same_row(prev, ln):  # 같은 줄에 떨어진 조각
                    last = runs[-1] if runs else None
                    _append_runs(runs, [Run(" ", False, bold, last.color if last else None, last.size if last else 0.0)])
                elif prev.trailing_space or not self.trailing_space_reliable or self._emphasis_boundary(prev, ln):
                    last = runs[-1] if runs else None
                    _append_runs(runs, [Run(" ", False, bold, last.color if last else None, last.size if last else 0.0)])
            _append_runs(runs, _runs_from_glyphs(ln.glyphs, bold))
        p = Para(runs=_clean_runs(runs), frame=lines[0].frame, spacing=_hangul_spacing(lines))
        whole = lines
        lines = _row_starts(lines)  # 같은 줄 오른쪽에 붙인 조각("( ✕ )")은 들여쓰기·정렬 판단에서 뺀다
        left, right = self.bounds(lines[0])
        width = max(1.0, right - left)
        first = lines[0]
        tol = max(1.2 * first.size, 6.0)
        r0 = self.rx(first)
        if len(lines) >= 2:
            p.indent_pt = round(r0 - self.rx(lines[1]), 1)
        else:
            p.indent_pt = round(r0 - base_left, 1) if r0 - base_left > 0.4 * first.size else 0.0
        if len(lines) <= 2 and all(l.x1 >= right - tol for l in lines) and first.x0 > left + 0.3 * width \
                and len(whole) == len(lines):
            p.align = "RIGHT"
            p.indent_pt = 0.0
            if re.match(r"^\s*[-–—]", p.text):
                p.role = "credit"
        elif len(whole) == 1 and abs((first.x0 - left) - (right - first.x1)) < 0.04 * width \
                and first.x0 > left + 0.15 * width:  # 좌우 여백이 같을 때만 가운데 정렬
            p.align = "CENTER"
            p.indent_pt = 0.0
        if LABEL_RE.match(p.text):
            p.role = "label"
        size = statistics.median(l.size for l in whole)
        pitches = [b.y0 - a.y0 for a, b in zip(lines, lines[1:]) if (a.page, a.col) == (b.page, b.col) and b.y0 > a.y0]
        if pitches:
            # 한글은 줄 간격 %를 그 줄에서 가장 큰 글자에 곱한다: 첫 줄의 큰 문제 번호("3.") 기준으로 재야 원문 간격이 된다
            big = max((g.size for g in lines[0].glyphs if not g.is_space and not g.icon), default=size)
            p.line_pct = round(statistics.median(pitches) / max(size, big) * 100)
            # 큰 번호보다 좁은 간격(원문은 번호가 줄 위로 튀어나온 것)은 본문 크기로 잰다: 95%로 두면 둘째 줄이 첫 줄에 겹쳤다
            if p.line_pct < 105:
                p.line_pct = round(statistics.median(pitches) / size * 100)
        last = lines[-1]
        p.src = (lines[0].page, lines[0].y0, last.y0 + (p.line_pct or DEFAULT_LINE_PCT) / 100 * size, last.page)
        return p

    def faithful_box(self, box: Box) -> Optional[Para]:
        """원문 위치를 따르는 교재의 전폭 쪽: 선으로 이은 상자 묶음(구조도)과 색을 칠한 짧은 제목 칸(검은 제목 띠,
        노란 '핵심 정리' 칸)은 원문 모양 그대로 그림으로(한글 문단 테두리로는 폭·여백이 원문과 달라진다)."""
        if not self.ex.faithful:
            return None
        lines = [x for x in box.items if isinstance(x, Line)]
        chart = not box.border and not box.fill and box.inner_drawings >= 4  # (안에 겹테두리 칸이 따로 잡혀도)
        # 칠한 제목 칸: 두 줄 제목 띠("‘포틀래치 관습’과 / ‘레비스트로스 구조주의’")까지
        label = box.fill and not box.parts and 1 <= len(lines) <= 3 and len("".join(l.text for l in lines).strip()) <= 20 * len(lines) \
            and box.y1 - box.y0 < 25 * len(lines) + 10 and len(lines) == len(box.items)
        if not (chart or label):
            return None
        pad = 1.5
        img = ImageEl(box.page, box.col, box.x0 - pad, box.y0 - pad, box.x1 + pad, box.y1 + pad, "faithful", 0)
        img.png = self.ex.render(box.page, (img.x0, img.y0, img.x1, img.y1), sharp=True)
        self.image_only_lines.extend(lines)
        info = self.ex.pages[box.page - 1].info
        left, right = info.col_left
        centered = abs((box.x0 + box.x1) / 2 - info.width / 2) < 0.04 * info.width  # 쪽 가운데(검은 제목 띠)
        return Para(kind="image", image=img, align="CENTER" if centered else "LEFT",
                    left_pt=0.0 if centered else max(0.0, box.x0 - left), src=(box.page, box.y0, box.y1, box.page))

    def single_para(self, lines: list[Line], bold: bool = False) -> Para:
        """문제 발문/선택지처럼 한 문단으로 묶이는 줄들."""
        p = self._para_from_lines(lines, bold, self.rx(lines[0]))
        p.align = "LEFT"
        rows = _row_starts(lines)
        p.indent_pt = round(self.rx(rows[0]) - self.rx(rows[1]), 1) if len(rows) >= 2 else 0.0
        p.role = ""
        return p

    # ---- aux box ----
    def aux_from_box(self, box: Box, wide: bool = False) -> AuxBlock:
        items = box.all_items()
        title = ""
        if items and isinstance(items[0], Line) and TITLE_RE.match(items[0].text):
            title = re.sub(r"\s+", " ", items[0].text.strip())
            title = re.sub(r"^[<〈＜《]\s*", "<", title)
            title = re.sub(r"\s*[>〉＞》]$", ">", title)
            items = items[1:]
        kind = "조건" if "조건" in title else ("보기" if "보기" in title or not title else "기타")
        blk = AuxBlock(title=title, kind=kind, fill=box.fill, border_color=box.border_color, border=box.border)
        drawings = box.inner_drawings + sum(p.inner_drawings for p in box.parts)
        diagram = drawings >= 4
        n_imgs = sum(1 for x in items if isinstance(x, ImageEl))
        if wide and n_imgs >= 2:  # 여러 조각 그림으로 된 구조도: 조각마다 넣으면 이음매가 어긋나니 상자째 한 장으로
            diagram = True
        if diagram and wide:
            # 전폭 쪽의 큰 글 상자(시대 특징 설명 + 낱말 띠 하나)는 글로 둔다. 도형이 줄 수의 두 배를 넘거나
            # 줄의 30% 이상이 작은 칸 안에 든 것(화살표 풀이·구조도)만 그림으로
            n = sum(1 for x in items if isinstance(x, Line))
            framed = box.framed_lines + sum(p.framed_lines for p in box.parts)
            diagram = drawings >= 2 * n or framed >= max(2, 0.3 * n)
        if wide and len(box.brackets) >= 2 and not box.parts:
            laid = self._bracket_layout(box, blk, items)
            if laid is not None:
                return laid
        if not diagram and wide and not box.parts:
            # 전폭 상자 안이 좌우 두 칸(왼쪽 설명+표 | 오른쪽 설명+표)이면 선 없는 두 칸 표로 나란히
            cx = (box.x0 + box.x1) / 2
            left = [x for x in items if x.x1 <= cx + 6]
            right = [x for x in items if x.x0 >= cx - 6]
            if left and right and len(left) + len(right) == len(items):
                cells = [Cell(0, 0, 1, 1, box.x0, box.y0, cx, box.y1, items=left),
                         Cell(0, 1, 1, 1, cx, box.y0, box.x1, box.y1, items=right)]
                t = TableEl(box.page, 0, [box.x0, cx, box.x1], [box.y0, box.y1], cells, lines=False)
                blk.paras = [Para(kind="table", table=self.table(t), align="CENTER")]
                return blk
        if diagram:
            # 화살표/칸 등 도형이 그려진 박스: 텍스트로 풀면 순서가 깨지므로 영역을 그림으로 보존
            parts = [box] + box.parts
            imgs = []
            for part in parts:
                y0 = part.y0
                if part is box and title:
                    first = box.items[0]
                    y0 = first.y1 + 1
                img = ImageEl(part.page, part.col, part.x0 + 1, y0, part.x1 - 1, part.y1 - 1, "diagram", 0)
                img.png = self.ex.render(part.page, (img.x0, img.y0, img.x1, img.y1), sharp=wide)
                imgs.append(img)
            title_line = box.items[0] if title else None
            for x in box.all_items():
                if isinstance(x, Line) and x is not title_line:
                    self.image_only_lines.append(x)
                elif isinstance(x, TableEl):
                    self.image_only_lines.extend(ln for cl in x.cells for ln in cl.items if isinstance(ln, Line))
            blk.diagram = imgs[0]
            blk.paras = [Para(kind="image", image=im, align="CENTER") for im in imgs]
            return blk
        blk.paras = self.paragraphs(items)
        return blk

    def _bracket_layout(self, box: Box, blk: AuxBlock, items: list) -> Optional[AuxBlock]:
        """시 풀이(구절 위아래로 파란 풀이, 오른쪽 "]" 괄호 뒤에 장마다 요약): 괄호마다 한 행인 세 칸 표
        [구절과 풀이 | 괄호(위·오른쪽·아래 변) | 요약]. 괄호 사이 빈 간격은 선 없는 빈 행.
        왼쪽 칸은 줄마다 한 문단(원문 위치만큼 왼쪽 여백, 줄 안의 넓은 간격은 전각 공백으로)이고,
        글자 크기는 상자 안 본문(검은 구절) 크기 대비로 맞춘다(작은 풀이 글자가 원문 비율대로 작게)."""
        lines = [x for x in items if isinstance(x, Line)]
        if len(lines) != len(items):
            return None
        bx = statistics.median(x for x, _, _ in box.brackets)
        tick = 13.0  # 괄호 위·아래 짧은 가로선 길이(pt)
        split = []  # 괄호를 가로지르는 줄(같은 높이의 풀이와 요약이 한 줄로 묶인 것)은 괄호에서 나눈다
        for ln in lines:
            gs = ln.glyphs
            if ln.x0 < bx - tick < bx < ln.x1 and any(g.x0 >= bx for g in gs if not g.is_space):
                a = [g for g in gs if g.x0 < bx]
                b = [g for g in gs if g.x0 >= bx]
                split += [_sub_line(ln, a), _sub_line(ln, b)] if any(not g.is_space for g in a) else [ln]
            else:
                split.append(ln)
        lines = [ln for ln in split if ln.glyphs]
        groups = [(y0, y1) for _, y0, y1 in box.brackets]
        head = [ln for ln in lines if (ln.y0 + ln.y1) / 2 < groups[0][0] - 2]
        rows: list[list[Line]] = [[] for _ in groups]
        for ln in lines:
            if ln in head:
                continue
            cy = (ln.y0 + ln.y1) / 2
            k = min(range(len(groups)), key=lambda i: 0 if groups[i][0] - 2 <= cy <= groups[i][1] + 2
                    else min(abs(cy - groups[i][0]), abs(cy - groups[i][1])))
            rows[k].append(ln)
        # 상자 안 본문 크기: 검은(색 없는) 글자 중 가장 많은 크기
        sizes = Counter(round(g.size, 1) for ln in lines for g in ln.glyphs
                                    if not g.is_space and not g.color)
        main = sizes.most_common(1)[0][0] if sizes else 0.0
        x0, x1 = box.x0 + 4, box.x1 - 4
        tx = max(x0 + 20, bx - tick)
        tops = [min([g0] + [ln.y0 for ln in rl]) for (g0, _), rl in zip(groups, rows)]
        bots = [max([g1] + [ln.y1 for ln in rl]) for (_, g1), rl in zip(groups, rows)]
        ys = [tops[0]]
        for k in range(len(groups)):
            ys.append(bots[k])
            if k + 1 < len(groups):
                ys.append(max(bots[k] + 1, tops[k + 1]))
        cells = []
        for k, rl in enumerate(rows):
            r = 2 * k
            if k:  # 괄호 사이 빈 행
                cells.append(Cell(r - 1, 0, 1, 3, x0, ys[r - 1], x1, ys[r]))
            left = sorted([ln for ln in rl if ln.x0 < bx], key=lambda ln: (ln.y0, ln.x0))
            right = sorted([ln for ln in rl if ln.x0 >= bx], key=lambda ln: (ln.y0, ln.x0))
            lc = Cell(r, 0, 1, 1, x0, ys[r], tx, ys[r + 1])
            mc = Cell(r, 1, 1, 1, tx, ys[r], bx, ys[r + 1], sides=("top", "right", "bottom"))
            rc = Cell(r, 2, 1, 1, bx, ys[r], x1, ys[r + 1], valign="CENTER")
            for ln in left:
                p = self._spaced_para(ln)
                p.align, p.indent_pt, p.left_pt = "LEFT", 0.0, round(max(0.0, ln.x0 - x0), 1)
                lc.paras.append(p)
            rc.paras = [self.single_para(right)] if right else []  # 요약은 한 문단(둘째 줄 내어쓰기)
            for p in rc.paras:
                if not -60 <= p.indent_pt <= 0:  # 오른쪽 끝에 붙은 "(근경)" 같은 줄은 내어쓰기가 아니다
                    p.indent_pt = 0.0
            cells += [lc, mc, rc]
        t = TableEl(box.page, 0, [x0, tx, bx, x1], ys, cells, lines=False, text_pt=main)
        paras = []
        for ln in sorted(head, key=lambda ln: (ln.y0, ln.x0)):
            p = self.single_para([ln])
            cx = (ln.x0 + ln.x1) / 2
            p.align = "RIGHT" if ln.x1 > box.x1 - 30 and ln.x0 > (box.x0 + box.x1) / 2 else (
                "CENTER" if abs(cx - (box.x0 + box.x1) / 2) < 30 else "LEFT")
            p.indent_pt = 0.0
            paras.append(p)
        paras.append(Para(kind="table", table=t, align="CENTER"))
        if main and self.ex.body_size:  # 표 안 글자 크기 비율은 본문(검은 구절) 기준: 전체 rel 계산 때 size/main 이 되게
            for cl in cells:
                for p in cl.paras:
                    for run in p.runs:
                        if run.size:
                            run.size = round(run.size * self.ex.body_size / main, 2)
        blk.paras = paras
        self.stats_bracket_layouts = getattr(self, "stats_bracket_layouts", 0) + 1
        return blk

    def _spaced_para(self, ln: Line) -> Para:
        """한 줄 문단. 줄 안의 넓은 간격(풀이 두 개를 한 줄에 띄어 놓은 것)은 원래 폭만큼 전각 공백으로 띄운다."""
        segs = _segments(ln)
        p = self.single_para([ln])
        if len(segs) < 2:
            return p
        runs: list[Run] = []
        prev_x1 = None
        for seg in segs:
            solid = [g for g in seg if not g.is_space]
            if prev_x1 is not None and runs:
                n = max(1, round((solid[0].x0 - prev_x1) / max(1.0, solid[0].size)) - 1)
                runs.append(dataclasses.replace(runs[-1], text="\u2003" * n + " ", underline=False, boxed=False))
            runs.extend(_seg_runs([g for g in seg if g.c != "\u2003"]))
            prev_x1 = solid[-1].x1
        p.runs = [r for r in runs if r.text]
        return p

    def passage_paras(self, items: list) -> tuple[list[Para], bool]:
        entries: list[Union[Line, ImageEl]] = []
        boxed = False
        for it in items:
            if isinstance(it, Box):
                boxed = True
                entries.extend(it.all_items())
            else:
                entries.append(it)
        return self.paragraphs(entries), boxed


# ------------------------------------------------------------ icons -------

def _label_icons(ex: Extraction, headers: list[int], answer_idx: int) -> dict[str, str]:
    """선택지 줄머리 아이콘의 등장 순서(1~5)로 아이콘 이미지별 숫자를 투표로 정한다."""
    flow = ex.flow
    votes: dict[str, Counter] = defaultdict(Counter)
    bounds = headers + [answer_idx]
    for a, b in zip(bounds, bounds[1:]):
        seq: list[str] = []
        for it in flow[a:b]:
            if not isinstance(it, Line):
                continue
            gs = it.glyphs
            for i, g in enumerate(gs):
                if g.icon and (i == 0 or (gs[i - 1].is_space and g.x0 - gs[i - 2].x1 >= 1.5 * g.size if i >= 2 else False)):
                    seq.append(g.icon)
        for k, d in enumerate(seq[:10]):
            votes[d][k] += 1
    if not headers:
        # 문제 머리를 못 찾은 자료(예제 번호가 그림인 해설서 등): 같은 단·같은 x에서 줄머리 아이콘이 겹치지 않고
        # 이어지는 묶음을 선택지 한 벌로 보고 그 순서로 투표한다
        runs: list[list[str]] = []
        key = None
        for it in flow[:answer_idx]:
            if not isinstance(it, Line) or not it.glyphs or not it.glyphs[0].icon:
                continue
            g = it.glyphs[0]
            k = (it.page, it.col, round(g.x0 / 3))
            if runs and k == key and g.icon not in runs[-1]:
                runs[-1].append(g.icon)
            else:
                runs.append([g.icon])
                key = k
        for seq in runs:
            if len(seq) >= 3:
                for k, d in enumerate(seq[:10]):
                    votes[d][k] += 1
    labels: dict[str, str] = {}
    for d, cnt in votes.items():
        k, _ = cnt.most_common(1)[0]
        labels[d] = CIRCLED_DIGITS[k]
    # 투표에 안 걸린 아이콘: 이미 판별된 아이콘과 픽셀 비교
    unknown = [d for d in ex.icon_digests if d not in labels]
    if unknown and labels:
        ref = {d: ex.icon_samples(d, 1) for d in labels}
        for d in unknown:
            s = ex.icon_samples(d, 1)
            if not s:
                continue
            best, best_d = None, None
            for ld, rs in ref.items():
                if not rs:
                    continue
                mse = sum((x - y) ** 2 for x, y in zip(s[0], rs[0])) / len(s[0])
                if best is None or mse < best:
                    best, best_d = mse, ld
            if best_d is not None and best is not None and best < 2500:
                labels[d] = labels[best_d]
    return labels


# ------------------------------------------------------------- build ------

QNUM_RE = re.compile(r"^\s*(\d{1,3})\s*\.\s*(?=\S)")  # "1. 위 작품의…"
QNUM_BARE_RE = re.compile(r"^\s*(\d{1,3})\s+(?=\S)")  # "1  위 작품의…" (마침표 없이 큰 숫자만)


def _question_number(ln: Line, body: float) -> Optional[int]:
    """문제 머리줄 모양이면 그 번호. 박스 안 줄, 큰 글씨도 굵은 글씨도 아닌 번호는 문제 머리가 아니다."""
    if ln.box is not None:
        return None
    if m := QNUM_RE.match(ln.text):
        big = ln.lead_size >= 1.15 * body
        bold = any(g.bold for g in ln.glyphs[:3])
        return int(m.group(1)) if big or bold else None
    if m := QNUM_BARE_RE.match(ln.text):
        # 마침표가 없으면 본문 속 숫자와 헷갈리기 쉬우므로, 번호 글자가 본문과 바로 뒤 글자보다 확실히 클 때만
        solid = [g for g in ln.glyphs if not g.is_space]
        k = len(m.group(1))
        if len(solid) > k and ln.lead_size >= 1.15 * body and min(g.size for g in solid[:k]) >= 1.15 * solid[k].size:
            return int(m.group(1))
    return None


def _is_question_header(ln: Line, expected: int, body: float) -> bool:
    return _question_number(ln, body) == expected


DEFAULT_LINE_PCT = 155  # 본문 문단(plain)의 한글 줄 간격(%)


def _source_gaps(items: list, body: float) -> None:
    """원문 위치를 따르는 교재: 같은 쪽에서 앞 문단 다음 줄이 원래 올 자리보다 아래에서 시작하는 문단은 그 차이를
    문단 앞 간격(Para.gap, 본문 글자 크기 단위)으로.
    두 단 쪽에서 앞 문단보다 한참 위에서 시작하는 문단은 원문 오른쪽 단의 첫 문단: 한글에서도 단을 나눈다."""
    prev = None
    for it in items:
        src = getattr(it, "src", None)
        if src is None:
            prev = None
            continue
        if prev is not None and prev[3] == src[0] and src[1] > prev[2]:
            it.gap = round((src[1] - prev[2]) / body, 2)
            if not getattr(it, "wide", False):
                # 두 단 쪽의 문제 사이 큰 빈칸은 3줄까지만: 한글에서 지문이 원문보다 한두 줄 길어지면 그 빈칸이 그대로
                # 더해져 단이 넘친다(문제가 단 맨 위에서 시작하는 것은 단 나눔이 지킨다)
                it.gap = min(it.gap, 3.0)
        elif prev is not None and prev[3] == src[0] and src[1] < prev[2] - 3 * body and not getattr(it, "wide", False):
            it.col_break = True
        prev = src


def build_document(ex: Extraction) -> Document:
    flow = ex.flow
    body = ex.body_size

    # 정답부 시작: 정답 머리줄('13) [정답]') 중 가장 작은 번호가 처음 나오는 곳.
    # 문제집 일부(단원 중간)를 잘라 온 PDF는 1번이 아니라 13번 등에서 시작한다.
    ans_heads = [(i, int(m.group(1))) for i, it in enumerate(flow)
                 if isinstance(it, Line) and (m := ANSWER_HEAD_RE.match(it.text))]
    answer_idx = len(flow)
    first_answer_no = None
    if ans_heads:
        first_answer_no = min(n for _, n in ans_heads)
        answer_idx = next(i for i, n in ans_heads if n == first_answer_no)

    def find_headers(start: int) -> tuple[list[int], list[int], list[int]]:
        """start 번부터 차례로 문제 머리줄을 찾는다. (줄 위치, 번호, 건너뛴 번호)"""
        headers: list[int] = []
        numbers: list[int] = []
        skipped: list[int] = []
        expected = start
        for i, it in enumerate(flow[:answer_idx]):
            if not isinstance(it, Line):
                continue
            if _is_question_header(it, expected, body):
                headers.append(i)
                numbers.append(expected)
                expected += 1
                continue
            # 복구: 번호 하나를 놓쳐도 이후 문제를 전부 잃지 않도록, 큰 글씨 번호가 1~2개 건너뛰어 나오면 따라간다
            for jump in (1, 2):
                if it.lead_size >= 1.15 * body and _is_question_header(it, expected + jump, body):
                    skipped.extend(range(expected, expected + jump))
                    headers.append(i)
                    numbers.append(expected + jump)
                    expected += jump + 1
                    break
        return headers, numbers, skipped

    # 첫 문제 번호 후보: 정답부의 첫 번호, 1, 그리고 문제 머리 모양(큰 글씨/굵게, 박스 밖)인 첫 줄의 번호
    starts: list[int] = ([first_answer_no] if first_answer_no else []) + [1]
    for it in flow[:answer_idx]:
        if isinstance(it, Line) and (n := _question_number(it, body)) is not None:
            starts.append(n)
            break
    best = None
    for st in dict.fromkeys(starts):  # 순서 유지, 중복 제거
        found = find_headers(st)
        if best is None or len(found[0]) > len(best[0]):
            best = found
    headers, header_numbers, skipped = best
    restarted = False
    if ex.faithful:
        # 원문 쪽을 따르는 교재(학원 자체 교재)는 단원마다 번호가 1번부터 다시 시작하기도 한다: 이어지는 번호로 찾은 문제가
        # 문제 머리 모양 줄의 절반이 안 되면 일부만 문제로 묶지 않고(구조가 섞인다) 원문 번호 그대로 둔다
        heads = sum(1 for it in flow[:answer_idx] if isinstance(it, Line) and _question_number(it, body) is not None)
        if heads and len(headers) < 0.5 * heads:
            headers, header_numbers, skipped, restarted = [], [], [], True

    # 원문자 아이콘 판별 후 치환
    labels = _label_icons(ex, headers, answer_idx)
    unresolved = 0
    for pm in ex.pages:
        for ln in pm.lines:
            for g in ln.glyphs:
                if g.icon:
                    if g.icon in labels:
                        g.c = labels[g.icon]
                    else:
                        g.c = "○"
                        unresolved += 1

    b = Builder(ex)
    doc = Document(source=ex.path, warnings=b.warnings, image_only_lines=b.image_only_lines,
                   source_fixes=b.source_fixes)
    if unresolved:
        doc.warnings.append(f"판별하지 못한 원문자 아이콘 {unresolved}개를 ○로 표시함")
    if restarted:
        doc.warnings.append("문제 번호가 단원마다 다시 시작하는 교재 — 자동 번호 대신 원문 번호를 그대로 넣었습니다")
    if ex.stats.get("ocr_rows"):
        low = ex.stats.get("ocr_low_chars", 0)
        doc.warnings.append(f"글꼴 없이 그려진 글자 {ex.stats['ocr_rows']}줄을 OCR로 읽었습니다"
                            + (f" — 확신이 낮은 글자 {low}개(발문을 원문과 한 번 대조해 주세요)" if low else ""))

    header_set = set(headers)
    single_pages = {pm.info.number for pm in ex.pages if pm.info.single}
    doc.faithful = ex.faithful

    def same_page(j: int) -> bool:  # 원문 쪽마다 새 쪽인 교재는 쪽을 넘어 문단을 잇지 않는다
        return not ex.faithful or flow[j].page == flow[j - 1].page
    i = 0
    current_passage: Optional[Passage] = None
    passage_id = 0
    q_index = dict(zip(headers, header_numbers))
    if skipped:
        doc.warnings.append(f"문제 머리를 찾지 못한 번호: {skipped}")
    marks: dict[int, int] = {}  # 문서 항목 위치 -> 그 항목을 만든 흐름 위치(원문 쪽의 첫 내용인지 보려고)
    while i < answer_idx:
        it = flow[i]
        marks[len(doc.items)] = i
        if isinstance(it, Line) and GUIDE_RE.match(it.text) and it.box is None and i not in header_set:
            j = i + 1
            while j < answer_idx and j not in header_set and not (isinstance(flow[j], Line) and GUIDE_RE.match(flow[j].text) and flow[j].box is None):
                j += 1
            passage_id += 1
            paras, boxed = b.passage_paras(flow[i + 1:j])
            guide = Para(runs=_clean_runs(_runs_from_glyphs(it.glyphs, True)))
            current_passage = Passage(passage_id, guide, paras, boxed)
            doc.items.append(current_passage)
            i = j
            continue
        if i in header_set:
            j = i + 1
            while j < answer_idx and j not in header_set and not (isinstance(flow[j], Line) and GUIDE_RE.match(flow[j].text) and flow[j].box is None):
                j += 1
            q = _build_question(b, q_index[i], flow[i:j], current_passage, last=j >= answer_idx)
            doc.items.append(q)
            if current_passage:
                current_passage.question_numbers.append(q.number)
            i = j
            continue
        # 문제/지문 밖의 내용도 버리지 않는다
        if it.page in single_pages or id(it) in ex.wide_ids:
            # 전폭 쪽(작품 개관·표·구조도): 한 단으로 읽었으므로 이어지는 줄은 문단으로 잇고, 출력은 새 쪽에 한 단으로
            j = i + 1
            if not isinstance(it, Box):
                while j < answer_idx and j not in header_set and (flow[j].page in single_pages or id(flow[j]) in ex.wide_ids) and same_page(j) \
                        and not isinstance(flow[j], Box) and not (isinstance(flow[j], Line) and GUIDE_RE.match(flow[j].text)):
                    j += 1
            nb = flow[i + 1] if i + 1 < answer_idx else None
            if isinstance(it, Box) and isinstance(nb, Box) and not it.parts and not nb.parts and abs(it.x1 - nb.x0) < 3 \
                    and min(it.y1, nb.y1) - max(it.y0, nb.y0) > 0.6 * min(it.y1 - it.y0, nb.y1 - nb.y0):
                # 가운데에서 맞붙은 좌우 두 상자((가) | (나) 회색 지문): 두 칸 표 하나로 나란히
                cells = [Cell(0, k, 1, 1, x.x0, min(it.y0, nb.y0), x.x1, max(it.y1, nb.y1), fill=x.fill, items=x.all_items())
                         for k, x in enumerate((it, nb))]
                t = TableEl(it.page, 0, [it.x0, it.x1, nb.x1], [cells[0].y0, cells[0].y1], cells)
                out = [Para(kind="table", table=b.table(t), align="CENTER")]
                j = i + 2
            else:
                fb = b.faithful_box(it) if isinstance(it, Box) else None
                out = [fb] if fb else [b.aux_from_box(it, wide=True)] if isinstance(it, Box) else b.paragraphs(flow[i:j])
            for x in out:
                x.wide = True
            doc.items.extend(out)
            doc.loose_notes.extend(f"p{x.page}: {getattr(x, 'text', '[그림/박스]')[:30]}" for x in flow[i:j])
            i = j
            continue
        if isinstance(it, Box):
            doc.items.append(b.aux_from_box(it))
            j = i + 1
        else:
            # 이어지는 줄은 한꺼번에 문단으로(줄마다 끊으면 선택지가 "달래기 / 위해"처럼 원문 줄 끝에서 잘린다)
            j = i + 1
            while j < answer_idx and j not in header_set and isinstance(flow[j], Line) \
                    and not (GUIDE_RE.match(flow[j].text) and flow[j].box is None) \
                    and not (flow[j].page in single_pages or id(flow[j]) in ex.wide_ids) and same_page(j):
                j += 1
            doc.items.extend(b.paragraphs(flow[i:j]))
        doc.loose_notes.extend(f"p{x.page}: {getattr(x, 'text', '[그림/박스]')[:30]}" for x in flow[i:j])
        i = j

    for k, fi in marks.items():
        if k < len(doc.items) and (fi == 0 or flow[fi - 1].page != flow[fi].page):
            doc.items[k].top = True
    if ex.faithful:
        # 빈 문단(연 구분)은 빼고 원문 간격으로 띄운다(빈 문단이 있으면 간격을 잴 앞 문단을 잃는다)
        items = []
        for it in doc.items:
            if isinstance(it, Para) and it.kind == "blank":
                continue
            items.append(it)
        for k, it in enumerate(doc.items):  # 쪽 첫 내용 표시는 다음 항목으로 옮긴다
            if it.top and isinstance(it, Para) and it.kind == "blank" and k + 1 < len(doc.items):
                doc.items[k + 1].top = True
        doc.items = items
        _source_gaps(doc.items, b.size)
        for it in doc.items:
            if isinstance(it, Para) and it.kind == "table" and it.table is not None and it.table.memo:
                for cl in it.table.cells:
                    _source_gaps(cl.paras, b.size)

    # 정답/해설
    ans_lines: list[Line] = []
    for it in flow[answer_idx:]:
        if isinstance(it, Box):
            ans_lines.extend(x for x in it.all_items() if isinstance(x, Line))
        elif isinstance(it, Line):
            ans_lines.append(it)
    doc.answers = _build_answers(b, ans_lines)
    by_no = {q.number: q for q in doc.questions}
    for a in doc.answers:
        q = by_no.get(a.number)
        if q:
            head = a.head.text
            q.answer = ANSWER_HEAD_RE.sub("", head, count=1).strip()
            q.explanation = a.paras

    _underline_negatives([q.stem for q in doc.questions]
                         + [it for it in doc.items if isinstance(it, Para) and STEM_RE.match(it.text) and "?" in it.text])

    for r in _iter_runs(doc):  # 원문 본문 크기 대비 글자 크기(문제 밖 내용의 작은 설명 글 등)
        r.rel = round(r.size / body, 2) if r.size and body else 1.0

    # 그림 렌더링 (박스 안/지문/문제 그림)
    for img in _iter_images(doc):
        if img.png is None:
            img.png = ex.render(img.page, (img.x0, img.y0, img.x1, img.y1))

    doc.stats = {
        "question_count": len(doc.questions),
        "objective": sum(1 for q in doc.questions if q.qtype == "objective"),
        "subjective": sum(1 for q in doc.questions if q.qtype == "subjective"),
        "passages": len(doc.passages),
        "aux_blocks": sum(1 for q in doc.questions for x in q.blocks + q.after if isinstance(x, AuxBlock)),
        "loose_items": len(doc.loose_notes),
        "dropped_items": b.dropped,
        "answers": len(doc.answers),
        "icon_labels": {d[:8]: l for d, l in labels.items()},
        "expected_questions_found": headers and len(headers) == len(doc.answers),
    }
    nq, na = len(doc.questions), len(doc.answers)
    if na and nq != na:
        doc.warnings.append(f"문제 수({nq})와 정답 수({na})가 다름")
    for q in doc.questions:
        if q.choices and [c.label for c in q.choices] != list(CIRCLED_DIGITS[:len(q.choices)]):
            doc.warnings.append(f"{q.number}번 선택지 순서 이상: {''.join(c.label for c in q.choices)}")
        if q.choices and len(q.choices) not in (4, 5) and not q.written_parts:
            doc.warnings.append(f"{q.number}번 선택지 수 {len(q.choices)}개")
    return doc


def _choice_split(ln: Line) -> list[Line]:
    """한 줄에 선택지가 여러 개(① ㄱ, ㄴ   ② ㄷ, ㄹ)면 나눈다.
    - 앞 글자와 글자 크기의 1.5배 이상 떨어진 원문자, 또는
    - 바로 다음 번호(①→②)이면서 그 간격이 글자 크기의 0.6배 이상이고 그 줄의 다른 띄어쓰기보다 1.6배 이상 넓은 원문자
      (두 열 선택지 사이가 좁은 문제집: "① ㉠ : 혈혈단신(孑孑單身)  ② ㉡ : 전전반측"). 선택지 글 속에서 번호를 가리키는
      "② 와" 같은 경우는 보통 띄어쓰기라 나누지 않는다."""
    gs = ln.glyphs
    nonsp = [i for i, g in enumerate(gs) if not g.is_space]
    pairs = [(a, b) for a, b in zip(nonsp, nonsp[1:]) if b - a > 1]
    gaps = {b: gs[b].x0 - gs[a].x1 for a, b in pairs}  # 공백 뒤 글자 -> 앞 글자와 간격
    # 보통 띄어쓰기 폭: 원문자 앞뒤 간격(번호와 글 사이는 문제집마다 넓게 띄우기도 한다)은 빼고 잰다
    plain = max((gaps[b] for a, b in pairs if gs[a].c not in CIRCLED_DIGITS and gs[b].c not in CIRCLED_DIGITS),
                default=0.0)
    nxt = CIRCLED_DIGITS.index(gs[nonsp[0]].c) + 1 if nonsp and gs[nonsp[0]].c in CIRCLED_DIGITS else None
    cuts = [0]
    for i in sorted(gaps):
        g = gs[i]
        if g.c not in CIRCLED_DIGITS:
            continue
        gap = gaps[i]
        in_seq = nxt is not None and nxt < len(CIRCLED_DIGITS) and g.c == CIRCLED_DIGITS[nxt]
        if gap >= 1.5 * g.size or (in_seq and gap >= 0.6 * g.size and gap >= 1.6 * plain):
            cuts.append(i)
            nxt = CIRCLED_DIGITS.index(g.c) + 1
    if len(cuts) == 1:
        return [ln]
    cuts.append(len(gs))
    return [_sub_line(ln, gs[a:b]) for a, b in zip(cuts, cuts[1:]) if any(not g.is_space for g in gs[a:b])]


def _segments(ln: Line) -> list[list[Glyph]]:
    """넓은 간격(글자 크기의 1.2배 이상, 보통 띄어쓰기의 서너 배)으로 나뉜 조각들."""
    segs: list[list[Glyph]] = [[]]
    prev: Optional[Glyph] = None
    for g in ln.glyphs:
        if g.c == "\u2003":
            continue
        if not g.is_space and prev is not None and g.x0 - prev.x1 > 1.2 * ln.size and segs[-1]:
            segs.append([])
        segs[-1].append(g)
        if not g.is_space:
            prev = g
    return [s for s in segs if any(not g.is_space for g in s)]


def _seg_runs(glyphs: list[Glyph]) -> list[Run]:
    return _clean_runs(_runs_from_glyphs(glyphs))


def _choice_grid(b: "Builder", choice_lines: list[list[Line]], head: Optional[Line]) -> Optional[ChoiceGrid]:
    """모든 선택지가 한 줄이고, 넓은 간격으로 나뉜 열 수와 열 위치가 같으면 표 모양 선택지다."""
    if len(choice_lines) < 4 or any(len(cl) != 1 for cl in choice_lines):
        return None
    rows = []
    for (ln,) in choice_lines:
        segs = _segments(ln)
        if not segs:
            return None
        first = [g for g in segs[0] if not g.is_space]
        if not first or first[0].c not in CIRCLED_DIGITS:
            return None
        rest = segs[0][segs[0].index(first[0]) + 1:]
        data = ([rest] if any(not g.is_space for g in rest) else []) + segs[1:]
        rows.append((ln, first[0], data))
    k = len(rows[0][2])
    if k < 2 or any(len(d) != k for _, _, d in rows):
        return None

    def x0(ln: Line, seg: list[Glyph]) -> float:  # 줄마다 자기 단 왼쪽 기준(선택지가 다음 단으로 넘어가도 같은 열)
        return next(g.x0 for g in seg if not g.is_space) - b.bounds(ln)[0]
    cols = [statistics.median(x0(ln, d[j]) for ln, _, d in rows) for j in range(k)]
    size = rows[0][0].size
    if any(abs(x0(ln, d[j]) - cols[j]) > 1.5 * size for ln, _, d in rows for j in range(k)):
        return None
    header: list[list[Run]] = [[] for _ in range(k)]
    if head is not None:
        for seg in _segments(head):
            hx = x0(head, seg)
            j = min(range(k), key=lambda c: abs(cols[c] - hx))
            if header[j]:
                header = [[] for _ in range(k)]
                break
            header[j] = _seg_runs(seg)
    lft, rgt = b.bounds(rows[0][0])
    return ChoiceGrid(label_x=rows[0][1].x0 - lft, cols_x=cols, width=rgt - lft, header=header,
                      rows=[(lab.c, [_seg_runs(seg) for seg in d]) for _, lab, d in rows])


def _item_lines(it) -> list[Line]:
    if isinstance(it, Line):
        return [it]
    if isinstance(it, Box):
        return [x for y in it.all_items() for x in _item_lines(y)]
    if isinstance(it, TableEl):
        return [x for cl in it.cells for y in cl.items for x in _item_lines(y)]
    return []


def _build_question(b: Builder, number: int, items: list, passage: Optional[Passage],
                    last: bool = False) -> Question:
    """원문 순서를 지킨다: 발문 -> (보조박스/그림/기타 문단) -> 선택지 -> (선택지 뒤에 나온 내용).
    last: 정답부 바로 앞 문제. 선택지가 끝난 뒤 다음 쪽에 나오는 것(정답 표지, 저작권 안내, QR 등)은 버린다."""
    header: Line = items[0]
    stem_lines = [header]
    head_line: Optional[Line] = None  # 표 모양 선택지의 머리(㉠ ㉡ ㉢)
    blocks: list = []
    after: list = []
    choice_lines: list[list[Line]] = []
    credit_lines: dict[int, list[Line]] = {}  # 선택지 아래 오른쪽 정렬 출전 줄
    pending: list = []  # 박스/그림 사이의 일반 줄 (한꺼번에 문단으로 묶는다)
    state = "stem"

    def target() -> list:
        return after if state == "after" else blocks

    def flush():
        if pending:
            target().extend(b.paragraphs(list(pending)))
            pending.clear()

    for it in items[1:]:
        if last and len(choice_lines) >= 5 and it.page > max(ln.page for cl in choice_lines for ln in cl):
            b.image_only_lines.extend(_item_lines(it))  # 원문 대조에서도 뺀다
            b.dropped.append(f"p{it.page}: {getattr(it, 'text', '[그림/박스/표]')[:30]}")
            continue
        if isinstance(it, (Box, ImageEl, TableEl)):
            if state == "choices" and (len(choice_lines) >= 5
                                       or all(any(WRITE_RE.search(ln.text) for ln in cl) for cl in choice_lines)):
                state = "after"  # 선택지(또는 '…쓰시오' 하위 물음)가 끝난 뒤의 박스/그림은 선택지 앞으로 끌어오지 않는다
            flush()
            if state in ("stem", "choices"):
                state = "blocks" if state == "stem" else state
            dst = after if state == "after" else blocks
            if isinstance(it, Box):
                dst.append(b.aux_from_box(it))
            elif isinstance(it, TableEl):
                dst.append(Para(kind="table", table=b.table(it), align="CENTER"))
            else:
                dst.append(Para(kind="image", image=it, align="CENTER"))
            continue
        for ln in _choice_split(it):
            t = ln.text.lstrip()
            if t[:1] in CIRCLED_DIGITS and state != "after":
                if not choice_lines and pending and isinstance(pending[-1], Line) and len(_segments(pending[-1])) >= 2 \
                        and len(pending[-1].text.strip()) <= 40:
                    head_line = pending.pop()
                flush()
                choice_lines.append([ln])
                state = "choices"
            elif state == "choices" and choice_lines and _is_credit_line(b, ln):
                credit_lines.setdefault(len(choice_lines) - 1, []).append(ln)
            elif state == "choices" and choice_lines:
                prev = choice_lines[-1][-1]
                far = (prev.page, prev.col) != (ln.page, ln.col) or ln.y0 - prev.y0 > 2.5 * ln.size
                if len(choice_lines) >= 5 and (far or not b._is_full(prev)):
                    state = "after"
                    pending.append(ln)
                else:
                    choice_lines[-1].append(ln)
            elif state == "stem" and re.match(r"^\s*\(\d{1,2}\)\s", t):
                state = "blocks"  # 서술형 발문의 (1) (2) 하위 물음은 줄을 바꿔 둔다
                pending.append(ln)
            elif state == "stem":
                stem_lines.append(ln)
            else:
                pending.append(ln)
    flush()
    grid = _choice_grid(b, choice_lines, head_line)
    if head_line is not None and (grid is None or not any(grid.header)):
        blocks.extend(b.paragraphs([head_line]))
    stem = b.single_para(stem_lines, bold=True)
    if not QNUM_RE.match(stem.text) and QNUM_BARE_RE.match(stem.text):
        # 마침표 없이 숫자만 있던 번호("1  위 작품의…")는 다른 양식과 같게 "1. 위 작품의…"로
        r = next(r for r in stem.runs if r.text.strip())
        r.text = re.sub(r"^(\s*\d{1,3})", r"\1.", r.text, count=1)
        b.source_fixes[id(header)] = re.sub(r"^(\s*\d{1,3})", r"\1.", header.text, count=1)
    choices = []
    for k, cl in enumerate(choice_lines):
        # "① …쓰시오. / (a) : / (b) :"처럼 앞 줄이 일찍 끝나고 표지로 시작하는 줄은 선택지 글에 잇지 않고 따로 둔다
        cut = next((m for m in range(1, len(cl)) if MARKER_RE.match(cl[m].text)
                    and (not b._is_full(cl[m - 1]) or WRITE_RE.search(cl[m - 1].text))), len(cl))
        p = b.single_para(cl[:cut])
        subs = [b.single_para([ln]) for ln in cl[cut:]]
        for x in subs:
            x.align, x.role, x.indent_pt = "LEFT", "subline", 0.0
        extra = b.paragraphs(credit_lines[k]) if k in credit_lines else []
        for x in extra:
            x.align, x.role, x.indent_pt = "RIGHT", "credit", 0.0
        choices.append(Choice(p.text.lstrip()[:1], p, subs + extra))
    return Question(number=number, stem=stem, passage_id=passage.id if passage else None,
                    blocks=blocks, choices=choices, after=after, page=header.page, grid=grid)


def _is_credit_line(b: Builder, ln: Line) -> bool:
    """'- 작가, <작품>'(또는 '-작가, 「작품」')처럼 오른쪽에 붙은 출전 줄."""
    left, right = b.bounds(ln)
    return bool(re.match(r"^\s*[-–—]\s*[^\s\d\-–—]", ln.text)) and ln.x1 >= right - max(1.2 * ln.size, 6.0) \
        and ln.x0 > left + 0.3 * (right - left)


def _build_answers(b: Builder, lines: list[Line]) -> list[AnswerEntry]:
    entries: list[AnswerEntry] = []
    cur_head: list[Line] = []
    cur_body: list[Line] = []
    cur_no = None

    def flush():
        if cur_no is None:
            return
        head = b.single_para(cur_head)
        paras = b.paragraphs(cur_body, stanza=False) if cur_body else []
        for p in paras:
            p.align = "LEFT"
            # '오답 point', '1등급 공략 Tip' 같은 짧은 소제목
            t = p.text.strip()
            if p.kind == "text" and 0 < len(t) <= 16 and not re.search(r"[.?!다]$", t) and not MARKER_RE.match(t):
                p.role = "heading"
        entries.append(AnswerEntry(cur_no, head, paras))

    in_body = False
    for ln in lines:
        m = ANSWER_HEAD_RE.match(ln.text)
        if m:
            flush()
            cur_no = int(m.group(1))
            cur_head, cur_body = [ln], []
            in_body = False
            continue
        if cur_no is None:
            continue
        if EXPL_RE.match(ln.text):
            in_body = True
        elif not in_body and not b._is_full(cur_head[-1]):
            # "1) 정답 ②"처럼 정답 줄이 짧게 끝나면 다음 줄부터 해설(소제목 '오답 point' 등)
            in_body = True
        (cur_body if in_body else cur_head).append(ln)
    flush()
    return entries


STEM_RE = re.compile(r"\s*\d{1,2}\s?\.\s")
# 발문의 부정어·'먼'("적절하지 않은 것은?", "가장 먼 것은?"). OCR이 "않 은"으로 띄어 읽기도 한다
NEGATIVE_RE = re.compile(r"(않\s?[은는]|(?<![가-힣])(?:아\s?닌|없\s?는|먼))(?=\s?것)")


def _underline_negatives(stems: list[Para]) -> None:
    """발문 부정어 밑줄을 문서 안에서 고르게: 어느 발문이라도 부정어에 밑줄을 그었으면(원문이 그 관례를 쓰면) 밑줄이
    빠진 발문의 부정어에도 긋는다(같은 교재 안에서도 지문마다 빠진 곳이 있다). 관례를 안 쓰는 문서는 그대로 둔다."""
    def matches(p: Para):
        return list(NEGATIVE_RE.finditer(p.text))

    def underlined(p: Para, m) -> bool:
        pos = 0
        for r in p.runs:
            if r.underline and pos < m.end() and m.start() < pos + len(r.text):
                return True
            pos += len(r.text)
        return False
    if not any(underlined(p, m) for p in stems for m in matches(p)):
        return
    for p in stems:
        ms = matches(p)
        if not ms:
            continue
        chars = [(c, r) for r in p.runs for c in r.text]
        out: list[Run] = []
        k = 0
        for m in ms + [None]:
            end = m.start() if m else len(chars)
            for c, r in chars[k:end]:
                _append_runs(out, [dataclasses.replace(r, text=c)])
            if m is None:
                break
            word = m.group(0).replace(" ", "")  # OCR이 띄운 "않 은"은 붙인다
            r0 = next((r for c, r in chars[m.start():m.end()] if not c.isspace()), chars[m.start()][1])
            if word[0] == "않" and m.start() and "가" <= chars[m.start() - 1][0] <= "힣":  # OCR이 붙인 "적절하지않은"
                _append_runs(out, [dataclasses.replace(r0, text=" ", underline=False)])
            _append_runs(out, [dataclasses.replace(r0, text=word, underline=True)])
            k = m.end()
        p.runs = out


def _iter_runs(doc: Document):
    """문서의 모든 글자 런(지문·문제·박스·표 칸·정답 포함)."""
    def from_paras(ps):
        for p in ps:
            if isinstance(p, AuxBlock):
                yield from from_paras(p.paras)
            elif isinstance(p, Para):
                yield from p.runs
                if p.table is not None:
                    for cl in p.table.cells:
                        yield from from_paras(cl.paras)
                yield from from_paras(p.children)
    for it in doc.items:
        if isinstance(it, Passage):
            yield from from_paras(([it.guide] if it.guide else []) + it.paras)
        elif isinstance(it, Question):
            yield from from_paras([it.stem] + it.blocks + it.after + [c.para for c in it.choices]
                                  + [x for c in it.choices for x in c.extra])
        else:
            yield from from_paras([it])
    for a in doc.answers:
        yield from from_paras([a.head] + a.paras)


def _iter_images(doc: Document):
    def from_paras(ps):
        for p in ps:
            if not isinstance(p, Para):
                continue
            if p.kind == "image" and p.image is not None:
                yield p.image
            elif p.kind == "table" and p.table is not None:
                for cl in p.table.cells:
                    yield from from_paras(cl.paras)
            elif p.kind in ("bracket", "tablerow"):
                yield from from_paras(p.children)
    for it in doc.items:
        if isinstance(it, Passage):
            yield from from_paras(it.paras)
        elif isinstance(it, Question):
            for b in it.blocks + it.after:
                if isinstance(b, AuxBlock):
                    yield from from_paras(b.paras)
                else:
                    yield from from_paras([b])
        elif isinstance(it, AuxBlock):
            yield from from_paras(it.paras)
        elif isinstance(it, Para):
            yield from from_paras([it])
