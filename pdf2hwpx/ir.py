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

import re
import statistics
from collections import Counter, defaultdict
from typing import Callable, Optional, Union

from .extract import Extraction, TITLE_RE
from .model import (CIRCLED_DIGITS, AnswerEntry, AuxBlock, Box, Choice, ChoiceGrid, Document, Glyph, ImageEl, Line,
                    Para, Passage, Question, Run, TableEl)

GUIDE_RE = re.compile(r"^\s*(※|\[\s*\d+\s*[~∼～\-–]\s*\d+\s*\])")
ANSWER_HEAD_RE = re.compile(r"^\s*(\d{1,2})\s*\)\s*\[?\s*정답\s*\]?")  # "1) [정답] ④" / "1) 정답 ④"
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

def _runs_from_glyphs(glyphs: list[Glyph], bold: bool = False) -> list[Run]:
    """글자 -> 런. 원문의 밑줄과 굵게(지문 속 강조 시어 등)를 보존한다."""
    runs: list[Run] = []
    for g in glyphs:
        ul = g.underline
        b = bold or g.bold
        if g.is_space and runs:  # 공백은 앞 런의 모양을 따라가 런이 잘게 쪼개지지 않게
            ul, b = runs[-1].underline and ul, runs[-1].bold
        if runs and runs[-1].underline == ul and runs[-1].bold == b:
            runs[-1].text += g.c
        else:
            runs.append(Run(g.c, ul, b))
    return runs


def _append_runs(dst: list[Run], src: list[Run]) -> None:
    for r in src:
        if dst and dst[-1].underline == r.underline and dst[-1].bold == r.bold:
            dst[-1].text += r.text
        else:
            dst.append(Run(r.text, r.underline, r.bold))


def _clean_runs(runs: list[Run]) -> list[Run]:
    out: list[Run] = []
    for r in runs:
        t = re.sub(r"[ \t]{2,}", " ", r.text)
        if t:
            _append_runs(out, [Run(t, r.underline, r.bold)])
    if out:
        out[0].text = out[0].text.lstrip()
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
                paras.append(Para(kind="image", image=e, align="CENTER"))
                continue
            if isinstance(e, TableEl):
                flush()
                paras.append(Para(kind="table", table=self.table(e), align="CENTER"))
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
            if same_area:
                dy = e.y0 - prev.y0
                if dy > 1.3 * pitch:
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
            if LABEL_RE.match(e.text) or LABEL_RE.match(prev.text):
                brk = True
            if len(cur) >= 2 and self.rx(e) > self.rx(cur[1]) + 0.4 * e.size:
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
            if lines and all(abs((ln.x0 - cl.x0) - (cl.x1 - ln.x1)) <= max(4.0, 0.12 * w) for ln in lines):
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
                if prev.trailing_space or not self.trailing_space_reliable or self._emphasis_boundary(prev, ln):
                    _append_runs(runs, [Run(" ", False, bold)])
            _append_runs(runs, _runs_from_glyphs(ln.glyphs, bold))
        p = Para(runs=_clean_runs(runs))
        left, right = self.bounds(lines[0])
        width = max(1.0, right - left)
        first = lines[0]
        tol = max(1.2 * first.size, 6.0)
        r0 = self.rx(first)
        if len(lines) >= 2:
            p.indent_pt = round(r0 - self.rx(lines[1]), 1)
        else:
            p.indent_pt = round(r0 - base_left, 1) if r0 - base_left > 0.4 * first.size else 0.0
        if len(lines) <= 2 and all(l.x1 >= right - tol for l in lines) and first.x0 > left + 0.3 * width:
            p.align = "RIGHT"
            p.indent_pt = 0.0
            if re.match(r"^\s*[-–—]", p.text):
                p.role = "credit"
        elif len(lines) == 1 and abs((first.x0 - left) - (right - first.x1)) < 0.04 * width \
                and first.x0 > left + 0.15 * width:  # 좌우 여백이 같을 때만 가운데 정렬
            p.align = "CENTER"
            p.indent_pt = 0.0
        if LABEL_RE.match(p.text):
            p.role = "label"
        return p

    def single_para(self, lines: list[Line], bold: bool = False) -> Para:
        """문제 발문/선택지처럼 한 문단으로 묶이는 줄들."""
        p = self._para_from_lines(lines, bold, self.rx(lines[0]))
        p.align = "LEFT"
        p.indent_pt = round(self.rx(lines[0]) - self.rx(lines[1]), 1) if len(lines) >= 2 else 0.0
        p.role = ""
        return p

    # ---- aux box ----
    def aux_from_box(self, box: Box) -> AuxBlock:
        items = box.all_items()
        title = ""
        if items and isinstance(items[0], Line) and TITLE_RE.match(items[0].text):
            title = re.sub(r"\s+", " ", items[0].text.strip())
            title = re.sub(r"^[<〈＜《]\s*", "<", title)
            title = re.sub(r"\s*[>〉＞》]$", ">", title)
            items = items[1:]
        kind = "조건" if "조건" in title else ("보기" if "보기" in title or not title else "기타")
        blk = AuxBlock(title=title, kind=kind)
        drawings = box.inner_drawings + sum(p.inner_drawings for p in box.parts)
        if drawings >= 4:
            # 화살표/칸 등 도형이 그려진 박스: 텍스트로 풀면 순서가 깨지므로 영역을 그림으로 보존
            parts = [box] + box.parts
            imgs = []
            for part in parts:
                y0 = part.y0
                if part is box and title:
                    first = box.items[0]
                    y0 = first.y1 + 1
                img = ImageEl(part.page, part.col, part.x0 + 1, y0, part.x1 - 1, part.y1 - 1, "diagram", 0)
                img.png = self.ex.render(part.page, (img.x0, img.y0, img.x1, img.y1))
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

def _is_question_header(ln: Line, expected: int, body: float) -> bool:
    m = re.match(r"^\s*(\d{1,3})\s*\.\s*(?=\S)", ln.text)
    if not m or ln.box is not None:
        return False
    n = int(m.group(1))
    if n != expected:
        return False
    big = ln.lead_size >= 1.15 * body
    bold = any(g.bold for g in ln.glyphs[:3])
    return big or bold


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
        if isinstance(it, Line):
            m = re.match(r"^\s*(\d{1,3})\s*\.\s*(?=\S)", it.text)
            if m and _is_question_header(it, int(m.group(1)), body):
                starts.append(int(m.group(1)))
                break
    best = None
    for st in dict.fromkeys(starts):  # 순서 유지, 중복 제거
        found = find_headers(st)
        if best is None or len(found[0]) > len(best[0]):
            best = found
    headers, header_numbers, skipped = best

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
    doc = Document(source=ex.path, warnings=b.warnings, image_only_lines=b.image_only_lines)
    if unresolved:
        doc.warnings.append(f"판별하지 못한 원문자 아이콘 {unresolved}개를 ○로 표시함")

    header_set = set(headers)
    i = 0
    current_passage: Optional[Passage] = None
    passage_id = 0
    q_index = dict(zip(headers, header_numbers))
    if skipped:
        doc.warnings.append(f"문제 머리를 찾지 못한 번호: {skipped}")
    while i < answer_idx:
        it = flow[i]
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
        if isinstance(it, Box):
            doc.items.append(b.aux_from_box(it))
        else:
            doc.items.extend(b.paragraphs([it]))
        doc.loose_notes.append(f"p{it.page}: {getattr(it, 'text', '[그림/박스]')[:30]}")
        i += 1

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
        if q.choices and len(q.choices) not in (4, 5):
            doc.warnings.append(f"{q.number}번 선택지 수 {len(q.choices)}개")
    return doc


def _choice_split(ln: Line) -> list[Line]:
    """한 줄에 선택지가 여러 개(① ㄱ, ㄴ   ② ㄷ, ㄹ)면 나눈다."""
    gs = ln.glyphs
    cuts = [0]
    for i in range(1, len(gs)):
        g = gs[i]
        if g.c in CIRCLED_DIGITS and gs[i - 1].is_space and i >= 2 and g.x0 - gs[i - 2].x1 >= 1.5 * g.size:
            cuts.append(i)
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
            if state == "choices" and len(choice_lines) >= 5:
                state = "after"  # 선택지가 끝난 뒤의 박스/그림은 선택지 앞으로 끌어오지 않는다
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
    choices = []
    for k, cl in enumerate(choice_lines):
        p = b.single_para(cl)
        extra = b.paragraphs(credit_lines[k]) if k in credit_lines else []
        for x in extra:
            x.align, x.role, x.indent_pt = "RIGHT", "credit", 0.0
        choices.append(Choice(p.text.lstrip()[:1], p, extra))
    return Question(number=number, stem=stem, passage_id=passage.id if passage else None,
                    blocks=blocks, choices=choices, after=after, page=header.page, grid=grid)


def _is_credit_line(b: Builder, ln: Line) -> bool:
    """'- 작가, <작품>'처럼 오른쪽에 붙은 출전 줄."""
    left, right = b.bounds(ln)
    return bool(re.match(r"^\s*[-–—]\s", ln.text)) and ln.x1 >= right - max(1.2 * ln.size, 6.0) \
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
            elif p.kind == "bracket":
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
