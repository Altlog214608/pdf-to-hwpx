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
from .model import (CIRCLED_DIGITS, AnswerEntry, AuxBlock, Box, Choice, Document, Glyph, ImageEl, Line, Para,
                    Passage, Question, Run)

GUIDE_RE = re.compile(r"^\s*(※|\[\s*\d+\s*[~∼～\-–]\s*\d+\s*\])")
ANSWER_HEAD_RE = re.compile(r"^\s*(\d{1,2})\s*\)\s*\[\s*정답\s*\]")
EXPL_RE = re.compile(r"^\s*\[\s*해설\s*\]")
LABEL_RE = re.compile(r"^\s*(\([가-힣A-Za-z]\)|\[[A-Z가-힣]\]|<[가-힣]\>)\s*$")
# 줄 머리에 오면 새 문단을 시작하는 표지 (원문자/목록/화자/섹션 라벨 등)
MARKER_RE = re.compile(
    r"^\s*(?:[①-⑳]|[㉠-㉻ⓐ-ⓩ](?=\s)|\([가-힣A-Za-z0-9]\)(?=\s|$)|[ㄱ-ㅎ]\s*\.|[A-Z]\s*\.|\d{1,2}\s*\.(?!\d)"
    r"|[-–—•·▪◦○●□■◇◆※]\s|[가-힣A-Za-z]{1,6}\s?:|S#|\[[^\]]{1,20}\])")

BodyBounds = Callable[[Line], tuple[float, float]]


# ------------------------------------------------------------- helpers ----

def _runs_from_glyphs(glyphs: list[Glyph], bold: bool = False) -> list[Run]:
    runs: list[Run] = []
    for g in glyphs:
        ul = g.underline
        if runs and runs[-1].underline == ul:
            runs[-1].text += g.c
        else:
            runs.append(Run(g.c, ul, bold))
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

    def _stanza_gap(self, a: Line, b: Line, pitch: float) -> bool:
        return (a.page, a.col) == (b.page, b.col) and b.y0 - a.y0 > 1.7 * pitch

    def _para_from_lines(self, lines: list[Line], bold: bool, base_left: float) -> Para:
        runs: list[Run] = []
        for i, ln in enumerate(lines):
            if i > 0:
                prev = lines[i - 1]
                if prev.trailing_space or not self.trailing_space_reliable:
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
        cx = (first.x0 + first.x1) / 2
        if len(lines) <= 2 and all(l.x1 >= right - tol for l in lines) and first.x0 > left + 0.3 * width:
            p.align = "RIGHT"
            p.indent_pt = 0.0
            if re.match(r"^\s*[-–—]", p.text):
                p.role = "credit"
        elif len(lines) == 1 and abs(cx - (left + right) / 2) < 0.06 * width and first.x0 > left + 0.15 * width \
                and first.x1 < right - 0.15 * width:
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
            self.image_only_lines.extend(x for x in box.all_items() if isinstance(x, Line) and x is not (box.items[0] if title else None))
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

    # 정답부 시작
    answer_idx = len(flow)
    for i, it in enumerate(flow):
        if isinstance(it, Line) and ANSWER_HEAD_RE.match(it.text) and ANSWER_HEAD_RE.match(it.text).group(1) == "1":
            answer_idx = i
            break

    # 문제 머리줄
    headers: list[int] = []
    header_numbers: list[int] = []
    skipped: list[int] = []
    expected = 1
    for i, it in enumerate(flow[:answer_idx]):
        if not isinstance(it, Line):
            continue
        if _is_question_header(it, expected, body):
            headers.append(i)
            header_numbers.append(expected)
            expected += 1
            continue
        # 복구: 번호 하나를 놓쳐도 이후 문제를 전부 잃지 않도록, 큰 글씨 번호가 1~2개 건너뛰어 나오면 따라간다
        for jump in (1, 2):
            if it.lead_size >= 1.15 * body and _is_question_header(it, expected + jump, body):
                skipped.extend(range(expected, expected + jump))
                headers.append(i)
                header_numbers.append(expected + jump)
                expected += jump + 1
                break

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
            q = _build_question(b, q_index[i], flow[i:j], current_passage)
            doc.items.append(q)
            if current_passage:
                current_passage.question_numbers.append(q.number)
            i = j
            continue
        # 문제/지문 밖의 내용도 버리지 않는다
        if isinstance(it, Box):
            doc.items.extend(b.paragraphs(it.all_items()))
        else:
            doc.items.extend(b.paragraphs([it]))
        doc.warnings.append(f"문제/지문에 속하지 않은 내용(p{it.page}): {getattr(it, 'text', '[그림/박스]')[:30]}")
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
            q.answer = re.sub(r"^\s*\d{1,2}\s*\)\s*\[\s*정답\s*\]\s*", "", head).strip()
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
        "aux_blocks": sum(1 for q in doc.questions for x in q.blocks if isinstance(x, AuxBlock)),
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


def _build_question(b: Builder, number: int, items: list, passage: Optional[Passage]) -> Question:
    header: Line = items[0]
    stem_lines = [header]
    blocks: list = []
    choice_lines: list[list[Line]] = []
    state = "stem"
    after: list[Para] = []
    for it in items[1:]:
        if isinstance(it, Box):
            state = "blocks"
            blocks.append(b.aux_from_box(it))
            continue
        if isinstance(it, ImageEl):
            state = "blocks" if state == "stem" else state
            blocks.append(Para(kind="image", image=it, align="CENTER"))
            continue
        for ln in _choice_split(it):
            t = ln.text.lstrip()
            if t[:1] in CIRCLED_DIGITS:
                choice_lines.append([ln])
                state = "choices"
            elif state == "choices" and choice_lines:
                prev = choice_lines[-1][-1]
                far = (prev.page, prev.col) == (ln.page, ln.col) and ln.y0 - prev.y0 > 2.5 * ln.size
                if len(choice_lines) >= 5 and (far or not b._is_full(prev)):
                    after.extend(b.paragraphs([ln]))
                else:
                    choice_lines[-1].append(ln)
            elif state == "stem":
                stem_lines.append(ln)
            else:
                blocks.extend(b.paragraphs([ln]))
    stem = b.single_para(stem_lines, bold=True)
    choices = []
    for cl in choice_lines:
        p = b.single_para(cl)
        label = p.text.lstrip()[:1]
        choices.append(Choice(label, p))
    q = Question(number=number, stem=stem, passage_id=passage.id if passage else None,
                 blocks=blocks, choices=choices, after=after, page=header.page)
    return q


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
        (cur_body if in_body else cur_head).append(ln)
    flush()
    return entries


def _iter_images(doc: Document):
    def from_paras(ps):
        for p in ps:
            if isinstance(p, Para) and p.kind == "image" and p.image is not None:
                yield p.image
    for it in doc.items:
        if isinstance(it, Passage):
            yield from from_paras(it.paras)
        elif isinstance(it, Question):
            for b in it.blocks:
                if isinstance(b, AuxBlock):
                    yield from from_paras(b.paras)
                else:
                    yield from from_paras([b])
        elif isinstance(it, Para):
            yield from from_paras([it])
