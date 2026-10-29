"""PDF -> 페이지 모델.

PDF를 한 번만 읽어서 다음을 만든다.
- 줄(Line): 글자 좌표 기반. 텍스트 레이어에 공백 글자가 없어도 글자 간격으로 띄어쓰기를 복원하고,
  줄 끝 공백 여부(trailing_space)를 보존한다.
- 원문자 아이콘(①~⑤ 이미지)은 사설 영역 문자로 줄 안에 끼워 넣는다 (나중에 숫자로 판별).
- 박스(Box): 문단 테두리가 줄 단위 선분으로 그려지므로 세로 선분을 이어 붙여 사각형을 복원한다.
- 밑줄: 글자 아래 가로 선분.
- 표(TableEl): 가로/세로 선분이 서로 맞물린 격자를 칸으로 복원(병합 칸, 칸 배경색, 칸 안 글자/그림).
- 묶음 괄호(Bracket): 지문 왼쪽의 [A] 표시와 그 옆 세로선(위/아래 짧은 가로선).
- 머리글/바닥글/배너/숨은 글자 제거, 2단 분리, 읽기 순서(페이지 -> 왼쪽 단 -> 오른쪽 단 -> 위에서 아래).
"""
from __future__ import annotations

import re
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Optional

import pymupdf as fitz

from . import ocr
from .model import BLANK_BOX, CIRCLED_DIGITS, Box, Bracket, Cell, FlowItem, Glyph, ICON_PUA_BASE, ImageEl, Line, PageInfo, TableEl

HIDDEN_TEXT_MAX_SIZE = 3.0  # 크기 3pt 미만 글자는 숨은 텍스트(예: "zb1)")
GAP_SPACE_RATIO = 0.25  # 글자 사이 간격이 글자 크기의 이 비율을 넘으면 공백으로 본다
RENDER_ZOOM = 2.5  # 그림 렌더링 배율 (약 180dpi)
RENDER_MAX_PX = 1800  # 그림 한 변 최대 픽셀


@dataclass
class _Frag:
    glyphs: list[Glyph]
    x0: float
    y0: float
    x1: float
    y1: float
    size: float

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2


@dataclass
class _Seg:
    x0: float
    y0: float
    x1: float
    y1: float
    width: float
    color: Optional[str] = None  # 선 색(검정이 아니면)

    @property
    def horizontal(self) -> bool:
        return abs(self.y1 - self.y0) < 1.0 and abs(self.x1 - self.x0) >= 3.0

    @property
    def vertical(self) -> bool:
        return abs(self.x1 - self.x0) < 1.0 and abs(self.y1 - self.y0) >= 3.0


@dataclass
class PageModel:
    info: PageInfo
    lines: list[Line] = field(default_factory=list)
    images: list[ImageEl] = field(default_factory=list)
    boxes: list[Box] = field(default_factory=list)
    flow: list[FlowItem] = field(default_factory=list)


@dataclass
class Extraction:
    path: str
    pages: list[PageModel]
    flow: list[FlowItem]
    icon_digests: dict[str, str]  # digest -> PUA char
    body_size: float
    doc: fitz.Document
    stats: dict = field(default_factory=dict)
    header_texts: list = field(default_factory=list)
    wide_ids: set = field(default_factory=set)  # 두 단 쪽 위/아래의 전폭 구간에 든 흐름 항목(id)
    faithful: bool = False  # 쪽 테두리가 있는 교재: 원문 쪽마다 새 쪽으로(PDF 한 쪽 = 한글 한 쪽)

    def render(self, page: int, rect: tuple[float, float, float, float], sharp: bool = False) -> bytes:
        """원문 영역을 그림으로. sharp: 쪽 폭 가까이 크게 들어가는 도식(구조도 등)은 더 높은 해상도(약 290dpi)."""
        p = self.doc[page - 1]
        clip = fitz.Rect(*rect) & p.rect
        zoom = min(4.0 if sharp else RENDER_ZOOM, (3200 if sharp else RENDER_MAX_PX) / max(1.0, clip.width, clip.height))
        pix = p.get_pixmap(clip=clip, matrix=fitz.Matrix(zoom, zoom), alpha=False)
        return pix.tobytes("png")

    def icon_samples(self, digest: str, limit: int = 3) -> list[list[int]]:
        """아이콘 판별용 16x16 회색조 샘플."""
        out = []
        for pm in self.pages:
            for ln in pm.lines:
                for g in ln.glyphs:
                    if g.icon == digest:
                        p = self.doc[pm.info.number - 1]
                        pix = p.get_pixmap(clip=fitz.Rect(g.x0, g.y0, g.x1, g.y1), colorspace=fitz.csGRAY,
                                           matrix=fitz.Matrix(16 / max(1.0, g.x1 - g.x0), 16 / max(1.0, g.y1 - g.y0)),
                                           alpha=False)
                        out.append(_resample(pix, 16))
                        if len(out) >= limit:
                            return out
        return out


def _resample(pix: fitz.Pixmap, n: int) -> list[int]:
    w, h = pix.width, pix.height
    data = pix.samples
    vals = []
    for j in range(n):
        for i in range(n):
            x = min(w - 1, int((i + 0.5) * w / n))
            y = min(h - 1, int((j + 0.5) * h / n))
            vals.append(data[y * pix.stride + x])
    return vals


# --------------------------------------------------------------------------

def _blank_image(doc: fitz.Document, xref: int) -> bool:
    """아무것도 칠하지 않는 그림: 투명도가 모두 0(빈 이미지 마스크)이거나 모든 점이 흰색."""
    try:
        pix = fitz.Pixmap(doc, xref)
    except Exception:  # 인라인 그림(xref 0) 등
        return False
    if pix.alpha:
        a = pix.samples[pix.n - 1::pix.n]
        if max(a, default=0) == 0:
            return True
    kind, smask = doc.xref_get_key(xref, "SMask")  # 투명도를 따로 둔 그림: 투명도가 모두 0이면 안 보인다
    if kind == "xref":
        try:
            if max(fitz.Pixmap(doc, int(smask.split()[0])).samples, default=0) == 0:
                return True
        except Exception:
            pass
    if pix.colorspace is None:
        return False
    if pix.n - pix.alpha != 1:
        pix = fitz.Pixmap(fitz.csGRAY, pix)
    color = pix.samples if not pix.alpha else bytes(pix.samples[k] for k in range(0, len(pix.samples), pix.n))
    return min(color, default=0) > 235


def _is_bold(font: str, flags: int, char_flags: int = 0) -> bool:
    """굵은 글꼴 이름(…Bold, 나눔스퀘어 B/EB 등)이거나, 글자를 칠하고 테두리까지 그린 가짜 굵게(한글이 내보내는 진하게).
    SemiBold·DemiBold는 본문용 굵기다(을유1945 SemiBold로 쓴 교재 본문 전체가 굵게 되면 글자가 넓어져 쪽이 넘친다)."""
    name = font.lower()
    if "semibold" in name or "demibold" in name:  # (글꼴 굵게 표시도 켜져 있다)
        return (char_flags & 48) == 48
    return ("bold" in name or bool(flags & 16) or bool(re.search(r"[a-z](?:EB|XB|B)$", font))
            or (char_flags & 48) == 48)


def _plain_strokes(strokes: dict) -> None:
    """칠하고 테두리까지 그린 글자는 보통 가짜 굵게지만, 한 글꼴의 거의 모든 글자를 그렇게 찍은 문서(한글이 바탕체
    선택지·보기를 늘 가는 테두리와 함께 내보낸 교재)에서는 그 글꼴의 보통 모양이다: 굵게로 보지 않는다
    (한 교재의 선택지 556개가 모두 굵게 들어갔다). 일부 글자만 그런 글꼴('주제'만 테두리)은 그대로 강조."""
    for total, stroked, glyphs in strokes.values():
        if total >= 50 and stroked >= 0.85 * total:
            for g in glyphs:
                g.bold = False


WHITE = "#FFFFFF"


def _color(c: int) -> Optional[str]:
    """글자 색. 검정(또는 거의 검정)은 None. 흰색은 일단 WHITE로 두고, 진한 바탕 상자·칸 안이 아니면 쪽을 다 읽은 뒤
    None으로(색 배경 위 글자: 한글에선 배경이 없어 보이지 않음)."""
    r, g, b = (c >> 16) & 255, (c >> 8) & 255, c & 255
    if max(r, g, b) < 40:
        return None
    if min(r, g, b) > 235:
        return WHITE
    return "#%02X%02X%02X" % (r, g, b)


def _dark(color: Optional[str]) -> bool:
    if not color:
        return False
    r, g, b = (int(color[k:k + 2], 16) for k in (1, 3, 5))
    return 0.299 * r + 0.587 * g + 0.114 * b < 110


# Wingdings 글꼴은 일반 글자 자리에 기호를 그린다(예: 'ü'가 체크 표시). 문제집에 자주 나오는 것만 같은 모양의 유니코드로.
WINGDINGS = {"ü": "✓", "û": "✗", "ý": "☒", "þ": "☑", "è": "→", "ç": "←", "é": "↑", "ê": "↓",
             "ð": "⇨", "ï": "⇦", "ñ": "⇧", "ò": "⇩", "l": "●", "n": "■", "u": "◆", "§": "▪", "o": "□", "¡": "○"}
# 한글 수식(HancomEQN 글꼴)은 글자를 사용자 영역(U+E000~)에 매긴다: 영문 대문자 E000~, 숫자 E033~, '/' E054
# (그대로 두면 한글에서 빈칸·엉뚱한 기호로 나온다: "L²"이 "'"로). 작게 올려 쓴 숫자는 위첨자로
HANCOM_EQN = {**{chr(0xE000 + k): chr(65 + k) for k in range(26)}, **{chr(0xE033 + k): str(k) for k in range(10)},
              chr(0xE054): "/"}
SUPERSCRIPT = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
MISMAPPED_SPACE = "$%#&@\ufffd"  # \ufffd: 글자 정보가 없는 글자


def _mismapped_space(c: str, width: float, size: float) -> bool:
    """글꼴의 공백 글자가 엉뚱한 기호로 매겨진 경우("전략적$ 공약", "전략적\ufffd공약"): 진짜 기호보다 폭이 훨씬 좁다."""
    return c in MISMAPPED_SPACE and width < 0.36 * size


def _page_fragments(page: fitz.Page, strokes: Optional[dict] = None) -> list[_Frag]:
    """strokes: 글꼴별 [전체 글자 수, 칠하고 테두리까지 그린 글자 수, 그래서 굵게 본 글자들]을 모은다(_plain_strokes)."""
    frags: list[_Frag] = []
    raw = page.get_text("rawdict", flags=fitz.TEXT_PRESERVE_WHITESPACE | fitz.TEXT_COLLECT_STYLES)
    for block in raw.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            glyphs: list[Glyph] = []
            sup: list[int] = []  # 수식 글자 자리
            for span in line.get("spans", []):
                size = float(span.get("size") or 0)
                if size < HIDDEN_TEXT_MAX_SIZE:
                    continue
                font, flags, cflags = span.get("font", ""), int(span.get("flags") or 0), int(span.get("char_flags") or 0)
                bold = _is_bold(font, flags, cflags)
                color = _color(int(span.get("color") or 0))
                wingdings = "wingdings" in font.lower()
                eqn = "hancomeqn" in font.lower()
                st = strokes.setdefault(font, [0, 0, []]) if strokes is not None else None
                stroked = (cflags & 48) == 48
                for ch in span.get("chars", []):
                    c = ch.get("c") or ""
                    if not c:
                        continue
                    if wingdings:
                        c = WINGDINGS.get(c, c)
                    if eqn:
                        c = HANCOM_EQN.get(c, c)
                        sup.append(len(glyphs))
                    x0, y0, x1, y1 = ch["bbox"]
                    if c == " " or _mismapped_space(c, x1 - x0, size):
                        c = " "
                    glyphs.append(Glyph(c, x0, y0, x1, y1, size, bold, color=color))
                    if st is not None and c != " ":
                        st[0] += 1
                        st[1] += stroked
                        if stroked and bold and not _is_bold(font, flags):
                            st[2].append(glyphs[-1])
            if not glyphs or all(g.is_space for g in glyphs):
                continue
            body = max(g.size for g in glyphs)
            for k in sup:  # 줄 글자보다 작은 수식 숫자는 위첨자(크기는 줄 글자대로)
                g = glyphs[k]
                if g.c.isdigit() and g.size < 0.8 * body:
                    g.c, g.size = g.c.translate(SUPERSCRIPT), body
            solid = [g for g in glyphs if not g.is_space]
            frags.append(_Frag(glyphs, min(g.x0 for g in solid), min(g.y0 for g in solid),
                               max(g.x1 for g in solid), max(g.y1 for g in solid),
                               statistics.median(g.size for g in solid)))
    return frags


# 출판사가 첫 쪽 등에 넣는 법정 고지문: "◇「콘텐츠산업 진흥법 시행령」제33조에 의한 표시 / 제작연월일 / …저작권법에 의하여…"
NOTICE_RE = re.compile(r"콘텐츠\s*산업\s*진흥법|제작\s*연월일|저작권법에\s*의(?:하여|해|한)")


def _table_lines(t) -> list:
    return [x for cl in t.cells for x in cl.items if isinstance(x, Line)]


def _notice_items(lines: list, imgs: list, boxes: list, tables: list, segs: Optional[list] = None) -> set[int]:
    """고지문 줄에서 시작해 위아래·옆으로 맞붙은 줄과 그림(© 마크)까지 넓힌 덩어리의 id.
    지문·표 안에 법 이름이 나오는 경우처럼 덩어리가 본문 박스나 표의 일부에만 걸치거나, 고지문이라기엔
    너무 길면 아무것도 빼지 않는다."""
    seeds = [ln for ln in lines if NOTICE_RE.search(ln.text)]
    if not seeds:
        return set()
    # 고지문이 표(© 칸 | 표시 | 경고)에 들어 있으면 그 표만: 표 밖으로 넓히면 바로 아래 문제 줄까지 붙는다
    for t in tables:
        tl = _table_lines(t)
        if tl and all(any(ln is x for x in tl) for ln in seeds) and len(tl) <= 15:
            ids = {id(x) for x in tl}
            ids |= {id(im) for im in imgs if t.x0 - 2 <= im.x0 and im.x1 <= t.x1 + 2 and t.y0 - 2 <= im.y0 and im.y1 <= t.y1 + 2}
            return ids

    def near(a, b) -> bool:
        h = max(4.0, min(a.y1 - a.y0, b.y1 - b.y0))
        xo = min(a.x1, b.x1) - max(a.x0, b.x0)  # 가로로 겹친 길이(음수면 떨어진 거리)
        yo = min(a.y1, b.y1) - max(a.y0, b.y0)
        if xo > 0 and -yo <= 0.9 * h:
            # 사이에 가로선(고지문 틀의 아래 변)이 있으면 바로 아래 문제 줄과는 이어지지 않는다
            lo, hi = sorted((a.y1, b.y1))[0], sorted((a.y0, b.y0))[1]
            if any(s.horizontal and lo - 1 <= s.y0 <= hi + 1 and s.x0 <= max(a.x0, b.x0) + 2
                   and s.x1 >= min(a.x1, b.x1) - 2 for s in segs or ()):
                return False
            return True
        return yo > 0.5 * h and -xo <= 20

    pool = list(lines) + list(imgs)
    group = list(seeds)
    ids = {id(x) for x in group}
    grown = True
    while grown:
        grown = False
        for x in pool:
            if id(x) not in ids and any(near(x, g) for g in group):
                ids.add(id(x))
                group.append(x)
                grown = True
    if sum(1 for x in group if isinstance(x, Line)) > 15:
        return set()
    for items in [b.items for b in boxes] + [_table_lines(t) for t in tables]:
        inside = sum(1 for x in items if id(x) in ids)
        if 0 < inside < len(items):
            return set()
    return ids


def _full_width_page(frags: list, segs: list, grids: list, imgs: list, W: float, top: float, bottom: float) -> bool:
    """가운데 단 구분선이 없는 쪽에서, 쪽 가운데를 가로지르는 글 조각·박스·표·그림이 내용 높이의 30% 이상을 차지하면
    두 단이 아니라 쪽 전체 폭을 쓰는 쪽(시대별 문학의 작품 개관·표·구조도 등)이다. 두 단 문제 쪽은 모두 구분선이 있고
    가운데를 가로지르는 것이 거의 없다(실제 PDF 34개에서 4% 이하).
    다만 큰 상자 하나가 쪽을 가로지를 뿐 그 안의 글은 좌우 두 칸으로 나뉜 쪽(해설서의 '핵심 개념' 상자)은 두 단으로 읽어야
    순서가 맞으므로, 가운데를 가로지르는 글 줄(전체 글자의 10% 이상)이나 표가 있어야 한다."""
    mid = W / 2
    n_all = sum(len(f.glyphs) for f in frags)
    n_cross = sum(len(f.glyphs) for f in frags if f.x0 < mid - 10 and f.x1 > mid + 10)
    table_cross = any(xs[0] < mid - 10 and xs[-1] > mid + 10 for xs, _, _ in grids)
    if not table_cross and n_cross < 0.1 * max(1, n_all):
        return False
    rects = [(f.x0, f.y0, f.x1, f.y1) for f in frags]
    rects += _detect_boxes(segs, top, bottom)
    rects += [(xs[0], ys[0], xs[-1], ys[-1]) for xs, ys, _ in grids]
    rects += [(x0, y0, x1, y1) for x0, y0, x1, y1, *_ in imgs if x1 - x0 < 0.95 * W and top < (y0 + y1) / 2 < bottom]
    rects = [r for r in rects if r[3] > top and r[1] < bottom]

    def covered(ivs: list[tuple[float, float]]) -> float:
        tot, cur = 0.0, None
        for a, b in sorted(ivs):
            if cur is None or a > cur[1]:
                tot += cur[1] - cur[0] if cur else 0.0
                cur = [a, b]
            else:
                cur[1] = max(cur[1], b)
        return tot + (cur[1] - cur[0] if cur else 0.0)

    content = covered([(max(top, r[1]), min(bottom, r[3])) for r in rects])
    if content < 0.15 * (bottom - top):  # 거의 빈 쪽
        return False
    cross = covered([(max(top, r[1]), min(bottom, r[3])) for r in rects if r[0] < mid - 10 and r[2] > mid + 10])
    return cross >= 0.3 * content


def _invisible(d: dict) -> bool:
    """선(stroke)이 없고 칠한 색이 흰색이거나 거의 투명한 그림 명령: 화면에 보이지 않는다."""
    if d.get("type") != "f":
        return False
    fill = d.get("fill")
    return not fill or min(float(v) for v in fill[:3]) > 0.97 or d.get("fill_opacity", 1.0) < 0.2


def _glyph_path(d: dict) -> bool:
    """글자를 윤곽선 도형으로 그린 것(글꼴을 넣지 않고 내보낸 발문 등): 진하게 칠한 글자 크기의 도형이고
    곡선이 있거나 선분이 많다. 동그라미(곡선 4개)·화살촉(선 3개)·네모는 여기에 들지 않는다."""
    fill = d.get("fill")
    if not fill or "f" not in (d.get("type") or "") or min(float(v) for v in fill[:3]) > 0.6:
        return False
    r = d["rect"]
    if not (3 <= r.height <= 30 and r.width <= 2 * max(r.height, 4)):
        return False
    ops = [it[0] for it in d.get("items", [])]
    return len(ops) >= 8 or (len(ops) >= 6 and "c" in ops)


def _outline_rows(drawings: list[dict]) -> list[list[float]]:
    """윤곽선 글자를 같은 높이에 글자 폭 정도 간격으로 이어진 것끼리 묶은 줄 [x0, y0, x1, y1, 글자 수]."""
    rects = sorted((fitz.Rect(d["rect"]) for d in drawings if _glyph_path(d)), key=lambda r: (r.x0, r.y0))
    rows: list[list[fitz.Rect]] = []
    for r in rects:
        for row in rows:
            last = row[-1]
            h = max(r.height, last.height)
            # 맨 앞 큰 문제 번호 뒤는 더 넓게 띄기도 한다("4.  <보기>는": 번호가 따로 떨어져 줄에서 빠졌다)
            gap = 2.5 * h if len(row) == 1 and last.height >= 1.15 * r.height else 1.5 * h
            if min(r.y1, last.y1) - max(r.y0, last.y0) >= 0.4 * min(r.height, last.height) and -2 <= r.x0 - last.x1 <= gap:
                row.append(r)
                break
        else:
            rows.append([r])
    return [[row[0].x0, min(r.y0 for r in row), row[-1].x1, max(r.y1 for r in row), len(row)] for row in rows]


LEAD_NUM = set("0123456789.。,·oOㅇlI|")  # 줄 맨 앞 번호를 OCR이 이렇게 읽기도 한다


def _align(chars: list, shapes: list, size: float) -> list[tuple]:
    """OCR 글자와 원문 글자 도형을 왼쪽부터 순서를 지키며 짝짓는다(편집 거리: 짝은 가운데 거리, 건너뛰기는 글자 크기의 80%).
    가운데가 글자 크기만큼 넘게 떨어진 짝은 짓지 않는다(OCR 상자는 단어를 나눈 것이라 반 글자쯤 어긋나기도 한다)."""
    n, m = len(chars), len(shapes)
    skip, far = 0.8 * size, 1.0 * size
    # (단어 첫 글자에 단어 전체 상자가 붙어 나오기도 한다: '설 438.8~474.1' -> 왼쪽 끝에서 반 글자)
    cx = [c.x0 + min(c.x1 - c.x0, size) / 2 for c in chars]
    sx = [(q.x0 + q.x1) / 2 for q in shapes]
    cost = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        cost[i][0] = i * skip
    for j in range(1, m + 1):
        cost[0][j] = j * skip
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d = abs(cx[i - 1] - sx[j - 1])
            cost[i][j] = min(cost[i - 1][j] + skip, cost[i][j - 1] + skip,
                             cost[i - 1][j - 1] + d if d <= far else float("inf"))
    pairs = []
    i, j = n, m
    while i and j:
        d = abs(cx[i - 1] - sx[j - 1])
        if d <= far and cost[i][j] == cost[i - 1][j - 1] + d:
            pairs.append((chars[i - 1], shapes[j - 1]))
            i, j = i - 1, j - 1
        elif cost[i][j] == cost[i - 1][j] + skip:
            i -= 1
        else:
            j -= 1
    return pairs[::-1]


def _ocr_rows(page: fitz.Page, rects: list, kept: list[_Frag], stats: Counter) -> list[Optional[_Frag]]:
    """윤곽선 글자 줄을 OCR로 읽어 글 조각으로(줄마다, 못 읽으면 None).
    - 줄 안의 진짜 글자(㉠·[A] 등)는 그대로 두고, 그 자리는 지우고 읽으며 거기 걸친 OCR 글자는 버린다.
    - 줄 맨 앞 번호(문제 번호·차례 번호)는 숫자와 마침표만 다시 읽는다("3."을 "。"로, "11."을 "1 ."로 읽는 것).
    - 글자 크기는 한글 글자 높이(글자 크기의 약 88%)로, 맨 앞 큰 번호는 숫자 높이(약 72%)로 따로 잰다.
    - 자간을 넓힌 줄도 단어 안 글자는 붙이고 단어 사이만 띄운다(줄 안 글자 간격의 분포로).
    - 굵기는 줄 안 진짜 글자를 따르고, 없으면 굵게(발문)."""
    inside = [[g for f in kept for g in f.glyphs if not g.is_space
               and r[0] <= (g.x0 + g.x1) / 2 <= r[2] and r[1] <= (g.y0 + g.y1) / 2 <= r[3]] for r in rects]
    rows = ocr.read_rows(page, rects, [[(g.x0, g.y0, g.x1, g.y1) for g in gs] for gs in inside])
    if rows is None:
        return [None] * len(rects)
    drawings = page.get_drawings()
    shapes = [fitz.Rect(d["rect"]) for d in drawings if _glyph_path(d)]
    marks = [fitz.Rect(d["rect"]) for d in drawings if d.get("fill") and "f" in (d.get("type") or "")
             and max(float(v) for v in d["fill"][:3]) < 0.4 and not _glyph_path(d)]
    owns =[sorted((q for q in shapes if r[0] <= (q.x0 + q.x1) / 2 <= r[2] and r[1] <= (q.y0 + q.y1) / 2 <= r[3]),
                   key=lambda q: q.x0) for r in rects]

    def missed(chars, own) -> int:  # 읽은 글자 상자가 덮지 못한 원문 글자 도형 수
        return sum(not any(ch.x0 - 1.0 <= (q.x0 + q.x1) / 2 <= ch.x1 + 1.0 for ch in chars) for q in own)
    # 원문 글자 도형을 여럿 놓친 줄은 그 줄만 한 글줄로 다시 읽어, 더 많이 덮으면 그것으로
    # ("1. 윗글에서 언급된 …"을 큰 "1." 때문에 여러 글줄로 쪼개 읽어 앞부분을 잃었다)
    for k, (chars, own, real) in enumerate(zip(rows, owns, inside)):
        if len(own) >= 4 and missed(chars, own) > max(2, 0.15 * len(own)):
            again = ocr.read_rows(page, [rects[k]], [[(g.x0, g.y0, g.x1, g.y1) for g in real]], line=True)
            if again and missed(again[0], own) < missed(chars, own):
                rows[k] = again[0]
                stats["ocr_line_retry"] += 1
    for k, (chars, real) in enumerate(zip(rows, inside)):
        # 진짜 글자 자리(지운 자리의 자국)의 OCR 글자, 그 바로 옆의 확신도 낮은 기호는 버린다
        def stray(ch) -> bool:
            for g in real:
                # 지운 자리와 바로 뒤 글자를 한 상자로 읽은 것("㉠과"의 '과'): 진짜 글자 밖으로 반 글자 넘게 나가면
                # 글자로 남기고 상자를 진짜 글자 뒤로 줄인다
                if ch.x0 < g.x1 and ch.x1 - max(ch.x0, g.x1) >= 0.5 * g.size and "가" <= ch.c <= "힣" and ch.x0 >= g.x0 - 0.1 * g.size:
                    ch.x0 = g.x1
            cx = (ch.x0 + ch.x1) / 2
            for g in real:
                if g.x0 - 0.1 * g.size <= cx <= g.x1 + 0.1 * g.size:
                    return True
                if ch.conf < 70 and not "가" <= ch.c <= "힣" and g.x0 - 0.8 * g.size <= cx <= g.x1 + 0.8 * g.size:
                    return True
                # 지운 자리에서 시작하는 숫자·영문(지운 ⓐ의 자국을 "3"으로)
                if ch.conf < 90 and ch.c.isascii() and ch.c.isalnum() and g.x0 <= ch.x0 < g.x1 + 0.2 * g.size:
                    return True
            return False
        rows[k] = [ch for ch in chars if not stray(ch)]
    # 맨 앞 번호, '[' 뒤 표시 글자는 그 글자들만 다시 읽는다
    redo: dict[tuple[int, str], tuple] = {}
    for k, chars in enumerate(rows):
        # 번호는 첫 진짜 글자 앞에서, 크게 띈 곳 앞에서 끝난다(지운 ⓐ 자리를 "3"으로 읽어 "5.3"을 번호로 다시 읽었다)
        stop = min((g.x0 for g in inside[k]), default=rects[k][2])
        n = 0
        while n < len(chars) and chars[n].c in LEAD_NUM and chars[n].x0 < stop \
                and (not n or chars[n].x0 - chars[n - 1].x1 < 0.6 * (rects[k][3] - rects[k][1])):
            n += 1
        if n and (n == len(chars) or chars[n].c not in LEAD_NUM or chars[n].x0 >= stop
                  or chars[n].x0 - chars[n - 1].x1 >= 0.6 * (rects[k][3] - rects[k][1])):
            redo[(k, "0123456789.")] = (rects[k][0], rects[k][1], chars[n - 1].x1 + 1.0, rects[k][3])
        elif not n and len(owns[k]) >= 4:
            # 맨 앞이 줄 글자보다 큰 도형(큰 문제 번호)이고 크게 띄었는데 숫자로 못 읽은 줄("4. <보기>는"의 "4. <"를
            # ":"로 읽어 문제로 잡히지 않았다): 번호 도형 자리를 숫자로 다시 읽는다
            own = owns[k]
            rest = sorted(q.height for q in own[1:])
            big = [q for q in own if q.height >= 1.15 * rest[int(0.75 * (len(rest) - 1))]]
            m = 0
            while m < len(own) and own[m] in big and (not m or own[m].x0 - own[m - 1].x1 < 0.5 * own[m].height):
                m += 1
            if 0 < m < len(own) and own[m].x0 - own[m - 1].x1 >= 0.8 * own[0].height:
                redo[(k, "0123456789.")] = (rects[k][0], rects[k][1], own[m].x0 - 1.0, rects[k][3])
        for n, ch in enumerate(chars):
            if ch.c == "[":
                h = ch.y1 - ch.y0
                close = next((c for c in chars[n + 1:n + 4] if c.c == "]"), None)
                redo[(k, "[]ABCDEFGH")] = (ch.x0 - 1.0, rects[k][1], close.x1 + 1.0 if close else ch.x0 + 1.7 * h, rects[k][3])
                break
    for allow in ("0123456789.", "[]ABCDEFGH"):
        keys = [key for key in redo if key[1] == allow]
        got = ocr.read_rows(page, [redo[key] for key in keys], [[] for _ in keys], allow=allow) or [[] for _ in keys]
        for (k, _), new in zip(keys, got):
            x0, _, x1, _ = redo[(k, allow)]
            text = "".join(ch.c for ch in new)
            old = [ch for ch in rows[k] if x0 - 0.5 <= (ch.x0 + ch.x1) / 2 <= x1
                   and (allow[0] == "[" or not "가" <= ch.c <= "힣")]  # 번호 영역은 바로 뒤 한글을 남긴다
            if allow[0] == "0" and new and new[0].c.isdigit():
                if "." not in text and any(ch.c in ".。,·" for ch in old):  # 마침표만 놓친 경우
                    d = new[-1]
                    new.append(ocr.OcrChar(".", d.x1, d.y0, d.x1 + 0.4 * (d.x1 - d.x0), d.y1, d.conf, d.word))
            elif not (allow[0] == "[" and re.fullmatch(r"\[[A-H]\]?", text)):
                continue
            rows[k] = sorted([ch for ch in rows[k] if ch not in old] + new, key=lambda ch: ch.x0)

    def row_size(chars, own) -> float:
        # 원문 글자 도형 높이로 잰다(OCR은 단어 끝 글자에 단어 상자 높이를 붙이기도 해서, 그런 글자가 많은 짧은 줄은
        # "적절한 것은?"이 22pt로 잡혔다). 받침 없는 글자·기호는 낮으므로 위에서 4분의 1 자리 높이로. 도형이 적으면 OCR 한글 높이로
        tall = sorted(q.height for q in own if q.height >= 0.6 * max(q.height for q in own)) if own else []
        if len(tall) >= 3:
            return tall[int(0.75 * (len(tall) - 1))] / 0.88
        hangul = [ch.y1 - ch.y0 for ch in chars if "가" <= ch.c <= "힣"]
        return statistics.median(hangul) / 0.88 if hangul else statistics.median(ch.y1 - ch.y0 for ch in chars) / 0.8
    # 한 쪽의 발문은 같은 크기: 줄마다 잰 크기가 쪽 가운데값과 12% 안이면 가운데값으로("은?"처럼 짧은 줄은 잰 값이 흔들린다)
    def few(own) -> bool:  # 크기를 잴 글자 도형이 셋도 안 되는 짧은 줄
        return sum(q.height >= 0.6 * max(o.height for o in own) for q in own) < 3 if own else True
    page_sizes = [row_size(chars, own) for chars, own in zip(rows, owns) if chars and not few(own)] \
        or [row_size(chars, own) for chars, own in zip(rows, owns) if chars]
    page_size = statistics.median(page_sizes) if page_sizes else 0.0
    out: list[Optional[_Frag]] = []
    for r, chars, real, own in zip(rects, rows, inside, owns):
        # 확신도 낮은 글자가 많은 줄(무늬·밑줄이 겹친 줄 등)은 잘못 읽은 것이 많아 그림으로 둔다
        if not chars or sum(ch.conf < ocr.LOW_CONF for ch in chars) > 0.25 * len(chars):
            out.append(None)
            continue
        size = row_size(chars, own)
        # 도형이 적은 짧은 줄("은?")은 OCR 상자로 재서 6pt처럼 크게 어긋나기도 한다: 쪽의 발문 크기로
        if abs(size - page_size) < 0.12 * page_size or (few(own) and page_size):
            size = page_size
        # 글자 위치는 원문 윤곽선 글자 도형에 맞춘다(글자 하나 = 도형 하나, OCR 상자는 단어를 나눈 것이라 부정확):
        # 띄어쓰기를 원문 간격 그대로 잴 수 있다
        pairs = {id(ch): q for ch, q in _align(chars, own, size)}
        snapped = len(pairs) >= 0.8 * len(chars)
        for k, ch in enumerate(chars):
            q = pairs.get(id(ch))
            if q is not None:
                ch.x0, ch.x1, ch.y0, ch.y1 = q.x0, q.x1, q.y0, q.y1
            elif k:  # 짝 없는 글자는 앞 글자 바로 뒤에: 순서가 바뀌지 않게
                w = min(ch.x1 - ch.x0, 0.6 * size)
                ch.x0 = max(ch.x0, chars[k - 1].x1 + 0.01)
                ch.x1 = ch.x0 + w
        # 글자 하나를 도형 여러 개로 그린 것('설'의 받침 ㄹ 등): 짝 없는 도형은 가로로 겹치는 글자 상자에 합친다
        # (안 합치면 글자 폭이 좁게 잡혀 '설 명'처럼 단어 안이 띄어진다)
        used = {id(q) for q in pairs.values()}
        snapped_chars = [ch for ch in chars if id(ch) in pairs]
        for q in own:
            if id(q) in used or q.width > 1.2 * size:
                continue
            best = max(snapped_chars, key=lambda ch: min(ch.x1, q.x1) - max(ch.x0, q.x0), default=None)
            if best is not None and min(best.x1, q.x1) - max(best.x0, q.x0) > 0.3 * q.width:
                best.x0, best.x1 = min(best.x0, q.x0), max(best.x1, q.x1)
        # 단어 안 글자 간격은 붙이고 단어 사이만 띄운다. 원문 도형에 맞춘 줄은 잉크 사이 간격이 단어 안(글자 높이의 0.2배
        # 이하)과 단어 사이(0.4배 이상)로 뚜렷이 나뉘어 글자 크기의 28%로, OCR 상자 그대로인 줄은 줄 안 보통 간격보다
        # 글자 크기의 20% 넘게(그리고 38% 넘게) 넓은 곳
        gaps = [b.x0 - a.x1 for a, b in zip(chars, chars[1:])]
        base = statistics.median(gaps) if gaps else 0.0
        # (글자를 옮기지 않고 앞 글자 상자 폭만 바꾼다: 줄 안의 진짜 글자와 순서가 섞이지 않게)
        for a, b, gap in zip(chars, chars[1:], gaps):
            limit = 0.28 * size if snapped else max(base + 0.2 * size, 0.38 * size)
            word = gap > limit and b.c not in "?.,!)’'”>:" and a.c not in "‘“(<"
            if not word and gap > 0:
                a.x1 = b.x0
            elif word and gap < 0.35 * size:
                a.x1 = max(a.x0 + 0.1, b.x0 - 0.35 * size)
        chars = ocr.fix_chars(chars)
        bold = statistics.mode(g.bold for g in real) if real else True
        glyphs = []
        for k, ch in enumerate(chars):
            sz = size
            if ch.c.isdigit() and all(c.c.isdigit() for c in chars[:k]):  # 맨 앞 번호
                sz = max(size, (ch.y1 - ch.y0) / 0.72)
            elif ch.c == "." and k and all(c.c.isdigit() for c in chars[:k]):  # 번호 뒤 마침표는 번호 크기로
                sz = glyphs[-1].size
            cy = (ch.y0 + ch.y1) / 2 if sz > size else (r[1] + r[3]) / 2
            g = Glyph(ch.c, ch.x0, cy - 0.6 * sz, ch.x1, cy + 0.6 * sz, sz, bold)
            if ch.conf < ocr.LOW_CONF:  # 수만 센다(음영을 넣으면 원문에 없는 형광펜처럼 보인다)
                stats["ocr_low_chars"] += 1
            glyphs.append(g)
        # 진짜 글자 둘 사이에 작게 칠한 가로 도형은 물결표("ⓐ~ⓔ", "㉠~㉤"의 '~'가 글자 도형보다 작아 빠졌다)
        reals = sorted(real, key=lambda g: g.x0)
        for a, b in zip(reals, reals[1:]):
            gc, gh = (a.y0 + a.y1) / 2, a.y1 - a.y0
            q = next((q for q in marks if a.x1 - 0.5 <= q.x0 and q.x1 <= b.x0 + 0.5 and q.width >= 1.5 * q.height
                      and q.height <= 0.35 * gh and q.width <= gh and abs((q.y0 + q.y1) / 2 - gc) <= 0.35 * gh), None)
            if q is not None and not any(a.x1 <= (g.x0 + g.x1) / 2 <= b.x0 for g in glyphs):
                glyphs.append(Glyph("~", q.x0, gc - 0.6 * size, q.x1, gc + 0.6 * size, size, bold))
                stats["ocr_tilde"] += 1
        glyphs.sort(key=lambda g: g.x0)
        stats["ocr_rows"] += 1
        out.append(_Frag(glyphs, glyphs[0].x0, min(g.y0 for g in glyphs), glyphs[-1].x1, max(g.y1 for g in glyphs), size))
    return out


def _merge_outline_rows(rows: list[list[float]], frags: list[_Frag]) -> list[tuple[float, float, float, float]]:
    """윤곽선 글자 줄을 그림으로 넣을 영역으로. 같은 높이의 줄 사이를 진짜 글자가 메우고 있으면(발문 중간의 "㉠∼㉤"만
    글자) 한 줄로 합친다. 글자 3개 이상인 줄과, 그 바로 아래에서 이어지는 짧은 줄(발문 둘째 줄 "은?")만 남긴다.
    같은 자리에 진짜 글자가 겹쳐 찍힌 줄(글자 위에 윤곽선을 한 번 더 그린 머리글)은 글자로 읽으므로 뺀다."""
    def covered(r) -> bool:
        w = sum(min(g.x1, r[2]) - max(g.x0, r[0]) for f in frags for g in f.glyphs
                if not g.is_space and r[0] - 1 <= (g.x0 + g.x1) / 2 <= r[2] + 1 and r[1] - 1 <= (g.y0 + g.y1) / 2 <= r[3] + 1)
        return w >= 0.5 * (r[2] - r[0])
    rows = [list(r) for r in rows if not covered(r)]
    merged = True
    while merged:
        merged = False
        for a in rows:
            for b in rows:
                if a is b or b[0] < a[2] - 2:
                    continue
                h = min(a[3] - a[1], b[3] - b[1])
                if min(a[3], b[3]) - max(a[1], b[1]) < 0.5 * h:
                    continue
                ivs = sorted((g.x0, g.x1) for f in frags for g in f.glyphs if not g.is_space
                             and a[2] - 2 <= g.x0 and g.x1 <= b[0] + 2 and max(a[1], b[1]) - 2 <= (g.y0 + g.y1) / 2 <= min(a[3], b[3]) + 2)
                # 진짜 글자가 이어 주면 간격은 큰 줄 높이로 잰다(맨 앞 큰 번호가 든 줄: "<보기>의 ㉮~㉰에"의 ㉮·㉰ 사이가
                # 작은 줄 높이로는 넘쳤다)
                gap = 1.5 * (max(a[3] - a[1], b[3] - b[1]) if ivs else h)
                # 맨 앞 큰 번호 하나뿐인 줄 뒤는 더 넓게 띄기도 한다("3.  ⓐ~ⓒ에")
                first = 2.5 * (a[3] - a[1]) if a[4] <= 2 and a[3] - a[1] >= 1.15 * (b[3] - b[1]) else gap
                cur = a[2]
                for x0, x1 in ivs:
                    if x0 - cur <= (first if cur == a[2] else gap):
                        cur = max(cur, x1)
                if b[0] - cur <= gap:
                    a[:] = [a[0], min(a[1], b[1]), b[2], max(a[3], b[3]), a[4] + b[4]]
                    rows.remove(b)
                    merged = True
                    break
            if merged:
                break
    rows.sort(key=lambda r: r[1])

    def lead(r) -> bool:
        # 진짜 글자 줄 맨 앞에 윤곽선으로만 그린 큰 번호("4. <보기>의 …"의 "4"): 바로 오른쪽에 같은 줄 진짜 글자가 있고
        # 왼쪽에는 없다(번호를 빼면 문제로 잡히지 않는다)
        h = r[3] - r[1]
        same = [g for f in frags for g in f.glyphs if not g.is_space and r[1] - 0.5 * h <= (g.y0 + g.y1) / 2 <= r[3] + 0.5 * h]
        return r[4] <= 2 and h >= 0.9 * max((g.size for g in same), default=h) \
            and any(0 <= g.x0 - r[2] <= 2.5 * h for g in same) and not any(r[0] - 1.5 * h <= g.x1 <= r[0] for g in same)
    keep: list[list[float]] = []
    for r in rows:
        h = r[3] - r[1]
        if r[4] >= 3 or any(0 <= r[1] - k[3] <= 1.8 * h and k[0] - 2 * h <= r[0] <= k[2] for k in keep) or lead(r):
            keep.append(r)
    out = []
    for x0, y0, x1, y1, _ in keep:
        h = y1 - y0
        out.append((x0 - 0.3 * h, y0 - 0.15 * h, x1 + 0.5 * h, y1 + 0.15 * h))
    return out


def _page_segments(page: fitz.Page, drawings: Optional[list[dict]] = None) -> tuple[list[_Seg], int]:
    segs: list[_Seg] = []
    others = []
    drawings = page.get_drawings() if drawings is None else drawings
    rows = [fitz.Rect(r[:4]) + (-1.0, -1.0, 1.0, 1.0) for r in _outline_rows(drawings)]
    for d in drawings:
        if _invisible(d):  # 선 없이 흰색으로만 칠한 사각형(한글이 문단 배경으로 내보냄)은 보이지 않으므로 테두리가 아니다
            continue
        if _glyph_path(d):  # 윤곽선 글자의 획은 테두리·도형이 아니다
            continue
        # 윤곽선 글자 줄 안에 든 도형도 글자의 일부다: 따로 그린 가로획(으·은·보의 'ㅡ'), 굵게 보이려고 같은 글자를
        # 선으로 한 번 더 그린 것(칠하지 않은 윤곽). 밑줄·테두리로 잡지 않는다
        if any(r.contains(d["rect"]) for r in rows):
            continue
        w = float(d.get("width") or 0.0)
        sc = d.get("color")
        scol = None if not sc or max(sc[:3]) < 0.16 else "#%02X%02X%02X" % tuple(round(float(v) * 255) for v in sc[:3])
        for it in d.get("items", []):
            op = it[0]
            if op == "l":
                p1, p2 = it[1], it[2]
                segs.append(_Seg(min(p1.x, p2.x), min(p1.y, p2.y), max(p1.x, p2.x), max(p1.y, p2.y), w, scol))
            elif op == "re":
                r = it[1]
                if r.width < 1.5 or r.height < 1.5:  # 얇은 사각형 = 선
                    segs.append(_Seg(r.x0, r.y0, r.x1, r.y1, w, scol))
                else:
                    for a, b in ((r.tl, r.tr), (r.bl, r.br), (r.tl, r.bl), (r.tr, r.br)):
                        segs.append(_Seg(min(a.x, b.x), min(a.y, b.y), max(a.x, b.x), max(a.y, b.y), w, scol))
                    others.append(r)
            elif op == "qu":
                q = it[1]
                r = q.rect
                for a, b in ((r.tl, r.tr), (r.bl, r.br), (r.tl, r.bl), (r.tr, r.br)):
                    segs.append(_Seg(min(a.x, b.x), min(a.y, b.y), max(a.x, b.x), max(a.y, b.y), w, scol))
            elif op == "c":
                pts = it[1:]
                xs = [p.x for p in pts]
                ys = [p.y for p in pts]
                others.append(fitz.Rect(min(xs), min(ys), max(xs), max(ys)))
    return segs + _join_dots(segs), others


def _join_dots(segs: list[_Seg]) -> list[_Seg]:
    """점선(1pt 안팎의 짧은 획을 같은 줄에 촘촘히 찍은 것)을 하나의 선으로 잇는다(지문 분석 쪽의 메모 칸 구분선)."""
    out: list[_Seg] = []
    for vertical in (True, False):
        groups: dict[float, list[_Seg]] = defaultdict(list)
        for s in segs:
            dx, dy = s.x1 - s.x0, s.y1 - s.y0
            if (dx < 1.0 and dy < 3.0) if vertical else (dy < 1.0 and dx < 3.0):
                groups[round((s.x0 if vertical else s.y0) * 2) / 2].append(s)
        for pos, dots in groups.items():
            dots.sort(key=lambda s: s.y0 if vertical else s.x0)
            run = [dots[0]]
            for d in dots[1:] + [None]:
                if d is not None and ((d.y0 - run[-1].y1) if vertical else (d.x0 - run[-1].x1)) <= 3.0:
                    run.append(d)
                    continue
                a, b = run[0], run[-1]
                if len(run) >= 5 and ((b.y1 - a.y0) if vertical else (b.x1 - a.x0)) >= 20:
                    out.append(_Seg(a.x0, a.y0, a.x0, b.y1, a.width, a.color) if vertical
                               else _Seg(a.x0, a.y0, b.x1, a.y0, a.width, a.color))
                run = [d] if d is not None else []
    return out


def _merge_runs(values: list[tuple[float, float, float]], tol: float = 3.0) -> list[tuple[float, float, float]]:
    """(pos, start, end) 목록을 같은 pos끼리 묶고 이어지는 구간을 합친다."""
    by_pos: dict[float, list[tuple[float, float]]] = defaultdict(list)
    keys: list[float] = []
    for pos, a, b in sorted(values):
        key = next((k for k in keys if abs(k - pos) <= 1.0), None)
        if key is None:
            keys.append(pos)
            key = pos
        by_pos[key].append((a, b))
    out = []
    for pos, ivs in by_pos.items():
        ivs.sort()
        cur_a, cur_b = ivs[0]
        for a, b in ivs[1:]:
            if a <= cur_b + tol:
                cur_b = max(cur_b, b)
            else:
                out.append((pos, cur_a, cur_b))
                cur_a, cur_b = a, b
        out.append((pos, cur_a, cur_b))
    return out


def _detect_boxes(segs: list[_Seg], top: float, bottom: float) -> list[tuple[float, float, float, float]]:
    verts = [(s.x0, s.y0, s.y1) for s in segs if s.vertical and s.y1 > top and s.y0 < bottom]
    runs = [r for r in _merge_runs(verts) if r[2] - r[1] >= 8]
    runs.sort()
    used = set()
    boxes = []
    for i, (lx, ly0, ly1) in enumerate(runs):
        if i in used:
            continue
        best = None
        for j, (rx, ry0, ry1) in enumerate(runs):
            if j == i or j in used or rx <= lx + 40:
                continue
            if abs(ry0 - ly0) <= 5 and abs(ry1 - ly1) <= 5:
                # 위아래 끝이 더 잘 맞는 짝 먼저(테두리 안에 조금 들어간 칠 사각형의 세로선과 엇갈려 짝짓지 않게),
                # 같으면 가까운 쪽
                key = (round((abs(ry0 - ly0) + abs(ry1 - ly1)) / 1.5), rx)
                if best is None or key < best_key:
                    best, best_key = j, key
        if best is not None:
            used.add(i)
            used.add(best)
            rx, ry0, ry1 = runs[best]
            boxes.append((lx, max(ly0, ry0), rx, min(ly1, ry1)))
    return boxes


def _content_boxes(rects: list, W: float, H: float, top: float, bottom: float) -> tuple[list, bool]:
    """쪽 테두리(내용 영역 위·아래 끝까지 닿는 쪽 크기 사각형)와 머리 띠 안의 칸(학원 이름 등)을 뺀 상자, 쪽 테두리가 있었는지.
    쪽 테두리를 상자로 보면 다음 쪽 테두리와 이어 붙어 단원 전체가 상자 하나가 된다."""
    frame = [r for r in rects if r[2] - r[0] >= 0.6 * W and r[3] - r[1] >= 0.6 * H and r[1] <= top + 2 and r[3] >= bottom - 2]
    return [r for r in rects if r not in frame and top < (r[1] + r[3]) / 2 < bottom], bool(frame)


def _linked_boxes(rects: list[tuple[float, float, float, float]], segs: list[_Seg],
                  colsep: Optional[float]) -> list[tuple[float, float, float, float]]:
    """상자 변이 아닌 가로·세로 선(화살표 몸통)이 상자와 상자를 잇는 묶음(상자 2개 이상)을 감싸는 사각형.
    선끼리 맞닿으면(갈라지는 화살표) 이어진 것으로 본다. 두 단 쪽에서는 단 구분선을 넘는 묶음은 만들지 않는다.
    다른 상자 안에 든 상자(이미 바깥 상자의 도형)는 보지 않는다."""
    top = [r for r in rects if not any(o is not r and o[0] - 1 <= r[0] and r[2] <= o[2] + 1 and o[1] - 1 <= r[1]
                                       and r[3] <= o[3] + 1 for o in rects)]
    if len(top) < 2:
        return []

    def on_edge(s: _Seg) -> bool:  # 상자 변과 같은 줄에 겹쳐 놓인 선(여러 칸에 걸친 표의 행·열 선 포함)
        for x0, y0, x1, y1 in rects:
            if s.horizontal and any(abs(s.y0 - y) < 1.5 for y in (y0, y1)) and s.x0 < x1 - 1 and s.x1 > x0 + 1:
                return True
            if s.vertical and any(abs(s.x0 - x) < 1.5 for x in (x0, x1)) and s.y0 < y1 - 1 and s.y1 > y0 + 1:
                return True
        return False

    def inside(px: float, py: float) -> bool:
        return any(r[0] + 2 < px < r[2] - 2 and r[1] + 2 < py < r[3] - 2 for r in top)

    # 잇는 선은 상자 사이 빈 곳을 지난다(상자 안의 밑줄·구분선은 아니다)
    links = [s for s in segs if (s.horizontal or s.vertical) and max(s.x1 - s.x0, s.y1 - s.y0) >= 8 and not on_edge(s)
             and not inside((s.x0 + s.x1) / 2, (s.y0 + s.y1) / 2) and not inside(s.x0, s.y0) and not inside(s.x1, s.y1)]
    n = len(top)

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def touches(s: _Seg, px: float, py: float, r) -> bool:
        """선 끝이 선 방향으로 상자 면에 닿는다(가로선은 왼쪽·오른쪽 면, 세로선은 위·아래 면).
        화살촉(따로 칠한 세모) 길이만큼 떨어져 있어도 된다."""
        # 선은 그 면에서 바깥으로 뻗는다(상자를 가로지르는 표의 행·열 선은 잇는 선이 아니다)
        if s.horizontal:
            return r[1] <= py <= r[3] and ((abs(px - r[0]) <= 8 and s.x1 <= r[0] + 8) or (abs(px - r[2]) <= 8 and s.x0 >= r[2] - 8))
        return r[0] <= px <= r[2] and ((abs(py - r[1]) <= 8 and s.y1 <= r[1] + 8) or (abs(py - r[3]) <= 8 and s.y0 >= r[3] - 8))

    def near_seg(px: float, py: float, s: _Seg) -> bool:
        return s.x0 - 3 <= px <= s.x1 + 3 and s.y0 - 3 <= py <= s.y1 + 3

    # 비스듬한 선은 양 끝이 서로 다른 두 상자의 변에 닿을 때만 잇는 선이다((가) 1문단 아래 변 -> 2문단 위 변).
    # 선은 좌표를 작은 값·큰 값으로 담아 두어 두 대각선 중 어느 쪽인지 모르므로 둘 다 본다
    def on_side(px: float, py: float, r) -> bool:
        return r[0] - 8 <= px <= r[2] + 8 and r[1] - 8 <= py <= r[3] + 8 \
            and not (r[0] + 3 < px < r[2] - 3 and r[1] + 3 < py < r[3] - 3)

    def diag_ends(s: _Seg) -> Optional[tuple[int, int]]:
        for a, b in (((s.x0, s.y0), (s.x1, s.y1)), ((s.x0, s.y1), (s.x1, s.y0))):
            i = next((i for i, r in enumerate(top) if on_side(*a, r)), None)
            j = next((j for j, r in enumerate(top) if on_side(*b, r)), None)
            if i is not None and j is not None and i != j:
                return i, j
        return None
    diags = [s for s in segs if not (s.horizontal or s.vertical) and max(s.x1 - s.x0, s.y1 - s.y0) >= 15
             and not inside((s.x0 + s.x1) / 2, (s.y0 + s.y1) / 2)]
    diags = [(s, ij) for s in diags if (ij := diag_ends(s)) is not None]
    links += [s for s, _ in diags]
    parent = list(range(n + len(links)))
    for k, (s, (i, j)) in enumerate(diags, start=len(links) - len(diags)):
        parent[find(n + k)] = find(i)
        parent[find(n + k)] = find(j)
    for k, s in enumerate(links[:len(links) - len(diags)]):
        ends = ((s.x0, s.y0), (s.x1, s.y1))
        for i, r in enumerate(top):
            if any(touches(s, px, py, r) for px, py in ends):
                parent[find(n + k)] = find(i)
        for m, o in enumerate(links[:k]):
            if any(near_seg(px, py, o) for px, py in ends) or any(near_seg(px, py, s) for px, py in ((o.x0, o.y0), (o.x1, o.y1))):
                parent[find(n + k)] = find(n + m)
    groups: dict[int, list[int]] = defaultdict(list)
    for k in range(n + len(links)):
        groups[find(k)].append(k)
    out = []
    for members in groups.values():
        bs = [top[k] for k in members if k < n]
        ls = [links[k - n] for k in members if k >= n]
        if len(bs) < 2 or not ls:
            continue
        x0 = min([r[0] for r in bs] + [s.x0 for s in ls]) - 2
        y0 = min([r[1] for r in bs] + [s.y0 for s in ls]) - 2
        x1 = max([r[2] for r in bs] + [s.x1 for s in ls]) + 2
        y1 = max([r[3] for r in bs] + [s.y1 for s in ls]) + 2
        # 묶음에 걸친 상자도 넣는다(잇는 선이 우연히 닫힌 네모를 이루면 그 '네모'가 상자로 잡히고, 거기에 붙은
        # 상자들은 그 네모의 변에 닿아 선으로 이어지지 않는다)
        grown = True
        while grown:
            grown = False
            for r in top:
                if r[0] < x1 - 2 and r[2] > x0 + 2 and r[1] < y1 - 2 and r[3] > y0 + 2 \
                        and r[2] - r[0] < x1 - x0 and r[3] - r[1] < y1 - y0 and not (x0 <= r[0] and r[2] <= x1 and y0 <= r[1] and r[3] <= y1):
                    x0, y0, x1, y1 = min(x0, r[0] - 2), min(y0, r[1] - 2), max(x1, r[2] + 2), max(y1, r[3] + 2)
                    grown = True
        out.append((x0, y0, x1, y1))
    # 서로 겹치는 묶음은 한 구조도다(4·5문단 -> 6문단을 잇는 선이 닫힌 네모를 이뤄 따로 묶이면 4·5문단이 두 번 나온다)
    merged = True
    while merged:
        merged = False
        for a in out:
            for b in out:
                if a is not b and a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]:
                    out.remove(b)
                    out[out.index(a)] = (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))
                    merged = True
                    break
            if merged:
                break
    if colsep is not None:
        out = [r for r in out if not r[0] < colsep - 10 < colsep + 10 < r[2]]
    return out


def _page_fills(page: fitz.Page) -> list[tuple[fitz.Rect, Optional[str]]]:
    """칠해진 사각형(표 칸 배경 등)을 그린 순서대로. 흰색은 None(앞서 칠한 색을 덮어 지움)."""
    out: list[tuple[fitz.Rect, Optional[str]]] = []
    for d in page.get_drawings():
        fill = d.get("fill")
        if not fill or d.get("fill_opacity", 1.0) < 0.2:
            continue
        r, g, b = (float(v) for v in fill[:3])
        color = None if min(r, g, b) > 0.97 else "#%02X%02X%02X" % (round(r * 255), round(g * 255), round(b * 255))
        items = d.get("items", [])
        rects = [fitz.Rect(it[1]) for it in items if it[0] == "re"]
        if not rects and items and all(it[0] == "l" for it in items) and len(items) <= 5:
            rects = [fitz.Rect(d["rect"])]  # 선 4개로 닫은 사각형 경로
        out.extend((rc, color) for rc in rects if rc.width > 3 and rc.height > 3)
    return out


def _cluster(values: list[float], tol: float = 2.0) -> list[float]:
    out: list[float] = []
    for v in sorted(values):
        if out and v - out[-1] <= tol:
            continue
        out.append(v)
    return out


def _frame_grid(xs: list[float], ys: list[float]) -> bool:
    """바깥 테두리와 그 안에 몇 pt 들여 그린 사각형이 만든 격자: 가장자리 칸이 모두 얇고(12pt 이하) 가운데 칸 하나만 크다."""
    if not (3 <= len(xs) <= 4 and 2 <= len(ys) <= 4):
        return False
    thin_x = xs[1] - xs[0] <= 12 and xs[-1] - xs[-2] <= 12 and len(xs) == 4
    thin_y = len(ys) == 2 or (len(ys) == 4 and ys[1] - ys[0] <= 12 and ys[-1] - ys[-2] <= 12)
    return thin_x and thin_y and xs[2] - xs[1] > 60


def _detect_tables(segs: list[_Seg], fills: list[tuple[fitz.Rect, Optional[str]]], top: float, bottom: float, W: float,
                   skip_vertical_x: Optional[float], wide: bool = False) -> list[tuple[list[float], list[float], list[Cell]]]:
    """가로/세로 선분이 서로 맞물려 격자를 이루면 표로 본다.
    박스(사각형 하나)는 가로 2 + 세로 2라서 표가 아니고, 칸이 2개 이상 생기는 격자만 표다.
    wide: 전폭 쪽이면 쪽 폭의 60%가 넘는 가로선도 표의 행 선으로 본다(두 단 쪽에서는 쪽 구분선)."""
    hs = [(s.y0, s.x0, s.x1) for s in segs if s.horizontal and (wide or s.x1 - s.x0 < 0.6 * W) and top - 1 <= s.y0 <= bottom + 1]
    vs = [(s.x0, s.y0, s.y1) for s in segs if s.vertical and top - 1 <= s.y0 and s.y1 <= bottom + 1
          and not (skip_vertical_x is not None and abs(s.x0 - skip_vertical_x) < 1.0)]
    H = [r for r in _merge_runs(hs, tol=1.5) if r[2] - r[1] >= 4]
    V = [r for r in _merge_runs(vs, tol=1.5) if r[2] - r[1] >= 4]
    n = len(H) + len(V)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i, (hy, hx0, hx1) in enumerate(H):
        for j, (vx, vy0, vy1) in enumerate(V):
            if hx0 - 2 <= vx <= hx1 + 2 and vy0 - 2 <= hy <= vy1 + 2:
                parent[find(i)] = find(len(H) + j)
    comps: dict[int, list[int]] = defaultdict(list)
    for k in range(n):
        comps[find(k)].append(k)
    tables = []
    for members in comps.values():
        hl = [H[k] for k in members if k < len(H)]
        vl = [V[k - len(H)] for k in members if k >= len(H)]
        if len(hl) < 2 or len(vl) < 2 or len(hl) + len(vl) < 5:
            continue
        x0 = min(min(h[1] for h in hl), min(v[0] for v in vl))
        x1 = max(max(h[2] for h in hl), max(v[0] for v in vl))
        y0 = min(min(v[1] for v in vl), min(h[0] for h in hl))
        y1 = max(max(v[2] for v in vl), max(h[0] for h in hl))
        xs = _cluster([x0, x1] + [v[0] for v in vl])
        ys = _cluster([y0, y1] + [h[0] for h in hl])
        # 세로 칸이 하나뿐인 격자는 표가 아니다(박스 안 밑줄/구분선이 박스 변에 닿은 경우)
        if len(xs) < 3 or len(ys) < 2:
            continue

        def vedge(x: float, ya: float, yb: float) -> bool:
            need = 0.6 * (yb - ya)
            return sum(max(0.0, min(v[2], yb) - max(v[1], ya)) for v in vl if abs(v[0] - x) <= 2.0) >= need

        def hedge(y: float, xa: float, xb: float) -> bool:
            need = 0.6 * (xb - xa)
            return sum(max(0.0, min(h[2], xb) - max(h[1], xa)) for h in hl if abs(h[0] - y) <= 2.0) >= need

        R, C = len(ys) - 1, len(xs) - 1
        owner = [[False] * C for _ in range(R)]
        cells: list[Cell] = []
        for r in range(R):
            for c in range(C):
                if owner[r][c]:
                    continue
                cs = 1
                while c + cs < C and not owner[r][c + cs] and not vedge(xs[c + cs], ys[r], ys[r + 1]):
                    cs += 1
                rs = 1
                while r + rs < R and not any(owner[r + rs][k] for k in range(c, c + cs)) \
                        and not any(hedge(ys[r + rs], xs[k], xs[k + 1]) for k in range(c, c + cs)):
                    rs += 1
                for rr in range(r, r + rs):
                    for cc in range(c, c + cs):
                        owner[rr][cc] = True
                cells.append(Cell(r, c, rs, cs, xs[c], ys[r], xs[c + cs], ys[r + rs]))
        # 어떤 칸도 시작하지 않는 행/열(칸 안의 짧은 선 때문에 생긴 경계)은 없앤다
        rstart = sorted({cl.row for cl in cells})
        cstart = sorted({cl.col for cl in cells})
        rmap = {r: k for k, r in enumerate(rstart)}
        cmap = {c: k for k, c in enumerate(cstart)}
        rstart.append(R)
        cstart.append(C)
        for cl in cells:
            end_r = min(r for r in rstart if r >= cl.row + cl.rowspan)
            end_c = min(c for c in cstart if c >= cl.col + cl.colspan)
            cl.row, cl.rowspan = rmap[cl.row], rstart.index(end_r) - rmap[cl.row]
            cl.col, cl.colspan = cmap[cl.col], cstart.index(end_c) - cmap[cl.col]
        ys = [ys[r] for r in rstart]
        xs = [xs[c] for c in cstart]
        if len(xs) < 3:
            continue
        # 모든 칸이 선으로 닫혀 있을 것(표 바깥 왼쪽/오른쪽 변은 없어도 됨). 화살표로 이은 도형 묶음은 여기서 걸러진다
        if not all(hedge(cl.y0, cl.x0, cl.x1) and hedge(cl.y1, cl.x0, cl.x1)
                   and (cl.x0 == xs[0] or vedge(cl.x0, cl.y0, cl.y1)) and (cl.x1 == xs[-1] or vedge(cl.x1, cl.y0, cl.y1))
                   for cl in cells):
            continue
        # 칸이 2개 이상, 너무 납작한 칸(이중선 등)이 없을 것
        if len(cells) < 2 or any(cl.x1 - cl.x0 < 6 or cl.y1 - cl.y0 < 6 for cl in cells):
            continue
        # 외곽선이 거의 없는 격자(밑줄/화살표 묶음)는 표가 아니다
        outer = (int(hedge(ys[0], xs[0], xs[-1])) + int(hedge(ys[-1], xs[0], xs[-1]))
                 + int(vedge(xs[0], ys[0], ys[-1])) + int(vedge(xs[-1], ys[0], ys[-1])))
        if outer < 2:
            continue
        tb = fitz.Rect(xs[0] - 3, ys[0] - 3, xs[-1] + 3, ys[-1] + 3)
        for cl in cells:
            area = (cl.x1 - cl.x0) * (cl.y1 - cl.y0)
            for rect, color in fills:  # 그린 순서대로: 나중에 칠한 색(흰색 포함)이 이긴다
                if not tb.contains(rect):
                    continue
                inter = rect & fitz.Rect(cl.x0, cl.y0, cl.x1, cl.y1)
                if not inter.is_empty and inter.width * inter.height >= 0.7 * area:
                    cl.fill = color
        tables.append((xs, ys, cells))
    return tables


def _detect_brackets(pno: int, lines: list[Line], segs: list[_Seg], start_id: int) -> list[Bracket]:
    """[A] 같은 표시 줄 바로 위/아래로 이어지는 세로선이 있고, 그 오른쪽에 글 줄이 있으면 묶음 괄호다."""
    out: list[Bracket] = []
    verts = [(s.x0, s.y0, s.y1) for s in segs if s.vertical]
    runs = _merge_runs(verts, tol=2.0)
    # 표시가 본문 줄에 바로 붙어 한 줄로 읽힌 경우("[A] 질 수도 있다…"): 표시 글자 뒤로 세로선이 지나가면 떼어 낸다
    for k in range(len(lines) - 1, -1, -1):
        ln = lines[k]
        m = re.match(r"\s*\[[A-Z가-힣]\]", ln.text)
        if ln.cell is not None or not m or not ln.text[m.end():].strip():
            continue
        lab, rest = ln.glyphs[:m.end()], [g for g in ln.glyphs[m.end():]]
        while rest and rest[0].is_space:
            rest.pop(0)
        lx0 = min(g.x0 for g in lab if not g.is_space)
        lx1 = max(g.x1 for g in lab if not g.is_space)
        if not any(lx0 - 3 <= r[0] <= lx1 + 3 and r[0] < rest[0].x0 and r[2] - r[1] >= 2 * ln.size
                   and (r[2] <= ln.y1 + ln.size or r[1] >= ln.y0 - ln.size) for r in runs):
            continue
        lines[k] = _slice_line(ln, rest)
        lines.insert(k, _slice_line(ln, [g for g in lab if not g.is_space]))
    for ln in lines:
        if ln.cell is not None or not re.fullmatch(r"\s*\[[A-Z가-힣]\]\s*", ln.text):
            continue
        cx = (ln.x0 + ln.x1) / 2
        cand = [r for r in runs if ln.x0 - 3 <= r[0] <= ln.x1 + 3]  # 표시 글자 폭 안을 지나는 세로선
        cand.sort(key=lambda r: abs(r[0] - cx))
        through = [r for r in cand if r[1] <= ln.y0 and r[2] >= ln.y1]
        above = [r for r in cand if r[2] <= ln.y1 and ln.y0 - r[2] <= 6 * ln.size]
        below = [r for r in cand if r[1] >= ln.y0 and r[1] - ln.y1 <= 6 * ln.size]
        if through:
            near = through[:1]
        elif above and below:  # 표시 글자 자리만 비운 위/아래 세로선
            near = [max(above, key=lambda r: r[2]), min(below, key=lambda r: r[1])]
        else:
            continue
        x = statistics.median(r[0] for r in near)
        y0 = min(r[1] for r in near)
        y1 = max(r[2] for r in near)
        if y1 - y0 < 2.5 * ln.size:
            continue
        # 괄호 끝의 짧은 가로선( [ 모양 ). 박스 변처럼 긴 선은 괄호가 아니다
        if not any(s.horizontal and abs(s.x0 - x) <= 2.0 and 2.0 <= s.x1 - s.x0 <= 20.0
                   and (abs(s.y0 - y0) <= 2.0 or abs(s.y0 - y1) <= 2.0) for s in segs):
            continue
        body = [o for o in lines if o is not ln and o.col == ln.col and o.cell is None and o.x0 > x
                and y0 - 0.3 * o.size <= (o.y0 + o.y1) / 2 <= y1 + 0.3 * o.size]
        if not body:
            continue
        b = Bracket(start_id + len(out), pno, ln.col, ln.text.strip(), x, y0, y1)
        ln.bracket_label = True
        ln.bracket = b.id
        for o in body:
            o.bracket = b.id
        out.append(b)
    return out


def _slice_line(ln: Line, glyphs: list[Glyph]) -> Line:
    solid = [g for g in glyphs if not g.is_space] or glyphs
    return Line(ln.page, ln.col, glyphs, min(g.x0 for g in solid), ln.y0, max(g.x1 for g in solid), ln.y1,
                ln.size, solid[0].size, ln.trailing_space if glyphs and glyphs[-1] is ln.glyphs[-1] else False,
                box=ln.box, cell=ln.cell)


def _group_lines(frags: list[_Frag]) -> list[list[_Frag]]:
    """같은 높이(세로로 반 이상 겹침)의 조각을 한 줄로 묶는다."""
    frags = sorted(frags, key=lambda f: (f.cy, f.x0))
    groups: list[list[_Frag]] = []
    for f in frags:
        target = None
        for g in reversed(groups[-4:]):
            # 줄의 첫 조각 높이와 비교한다(조각마다 넓히면 사이에 걸친 조각을 타고 위·아래 줄까지 한 줄이 된다)
            gy0, gy1 = g[0].y0, g[0].y1
            ov = min(gy1, f.y1) - max(gy0, f.y0)
            if ov >= 0.5 * min(f.y1 - f.y0, gy1 - gy0):
                target = g
                break
        if target is None:
            groups.append([f])
        else:
            target.append(f)
    return groups


def _norm_repeat(text: str) -> str:
    return re.sub(r"\d+", "#", re.sub(r"\s+", "", text))


def _repeat_key(f: "_Frag") -> tuple[str, int]:
    """머리글/바닥글 판별 키: 같은 글(숫자 무시)이 여러 페이지의 같은 높이에 반복되면 머리글로 본다."""
    return _norm_repeat("".join(g.c for g in f.glyphs)), int(round(f.y0 / 3.0))


def extract(pdf_path: str) -> Extraction:
    doc = fitz.open(pdf_path)
    raw_pages = []
    band_texts: Counter = Counter()
    strokes: dict = {}

    # ---- 1차: 페이지별 원자료 수집 ----
    for pno, page in enumerate(doc, start=1):
        W, H = page.rect.width, page.rect.height
        frags = _page_fragments(page, strokes)
        drawings = page.get_drawings()
        segs, others = _page_segments(page, drawings)
        outlines = _outline_rows(drawings)
        fills = _page_fills(page)
        infos = page.get_image_info(hashes=True, xrefs=True)
        seen = set()
        imgs = []
        for inf in infos:
            x0, y0, x1, y1 = inf["bbox"]
            digest = (inf.get("digest") or b"").hex()
            key = (digest, round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1))
            if key in seen or x1 - x0 < 1 or y1 - y0 < 1:
                continue
            seen.add(key)
            imgs.append((x0, y0, x1, y1, digest, int(inf.get("xref") or 0)))

        # 콘텐츠 영역: 위/아래 전폭 배너 이미지와 전폭 가로선 기준
        top, bottom = 0.0, H
        for x0, y0, x1, y1, *_ in imgs:
            if x1 - x0 >= 0.6 * W:
                if y1 <= 0.2 * H:
                    top = max(top, y1)
                elif y0 >= 0.8 * H:
                    bottom = min(bottom, y0)
        for s in segs:
            if s.horizontal and s.x1 - s.x0 >= 0.6 * W:
                if s.y0 <= 0.12 * H:
                    top = max(top, s.y0)
                elif s.y0 >= 0.88 * H:
                    bottom = min(bottom, s.y0)

        for f in frags:
            if f.y1 <= 0.12 * H or f.y0 >= 0.88 * H:
                band_texts[_repeat_key(f)] += 1
        raw_pages.append((pno, W, H, frags, segs, others, imgs, top, bottom, fills, outlines))
    _plain_strokes(strokes)

    repeat_min = max(2, int(0.4 * len(raw_pages)))
    # 문제 번호("3.")처럼 짧은 숫자 조각은 반복돼도 머리글이 아니다.
    repeated = {k for k, n in band_texts.items() if n >= repeat_min and len(re.sub(r"[#\W]", "", k[0])) >= 3
                and not k[0].startswith("※")}

    pages: list[PageModel] = []
    header_texts: list[tuple[int, str, float, float]] = []  # 머리글/배너 영역 글자(제목 후보용)
    icon_digests: dict[str, str] = {}
    all_sizes: list[float] = []
    stats = Counter()

    bracket_id = 0
    wide_ids: set[int] = set()
    pill_order: dict[str, int] = {}  # 알약 번호 그림 해시 -> 처음 나온 차례(1, 2, ...)
    pill_glyphs: list[tuple[Glyph, int]] = []
    for pno, W, H, frags, segs, others, imgs, top, bottom, fills, outlines in raw_pages:
        # ---- 단 분리선 ----
        content_h = max(1.0, bottom - top)
        split_x = W / 2
        best_len = 0.0
        for s in segs:
            if s.vertical and 0.35 * W <= s.x0 <= 0.65 * W:
                ln = min(s.y1, bottom) - max(s.y0, top)
                if ln >= 0.4 * content_h and ln > best_len:
                    best_len, split_x = ln, s.x0
        # 단 구분선이 그어진 세로 범위(위·아래로 전폭 지문/상자가 있으면 그 범위 밖)
        # (구분선 위에서 맞붙은 상자의 짧은 경계선은 빼고, 길게 이어진 구분선만)
        div = [s for s in segs if s.vertical and abs(s.x0 - split_x) < 1.0 and s.y1 - s.y0 >= 0.25 * content_h]
        div_y0 = min((s.y0 for s in div), default=top) if best_len else top
        div_y1 = max((s.y1 for s in div), default=bottom) if best_len else bottom

        # ---- 글자 조각 필터 ----
        kept: list[_Frag] = []
        for f in frags:
            txt = "".join(g.c for g in f.glyphs).strip()
            if f.cy <= top or f.cy >= bottom:
                stats["dropped_band_text"] += 1
                if txt:
                    header_texts.append((pno, txt, f.size, f.y0))
                continue
            if (f.y1 <= 0.12 * H or f.y0 >= 0.88 * H) and (_repeat_key(f) in repeated or re.fullmatch(r"-\s*\d+\s*-", txt)):
                stats["dropped_repeated_text"] += 1
                continue
            kept.append(f)

        # ---- 윤곽선 글자 줄: 글자 정보가 없으므로 줄 영역을 그림으로 넣는다. 사이에 낀 진짜 글자("㉠∼㉤")는 그림에 들어간다 ----
        outline_rects = _merge_outline_rows([r for r in outlines if top < (r[1] + r[3]) / 2 < bottom], kept)
        if outline_rects:
            # 글자로 읽을 수 있으면(OCR) 글 조각으로, 사이에 낀 진짜 글자는 그대로 두고 그 자리는 지우고 읽는다
            read = _ocr_rows(doc[pno - 1], outline_rects, kept, stats)
            kept += [f for f in read if f is not None]
            outline_rects = [r for r, f in zip(outline_rects, read) if f is None]
        if outline_rects:
            stats["outline_text_rows"] += len(outline_rects)
            for f in kept:
                f.glyphs = [g for g in f.glyphs if not any(
                    x0 <= (g.x0 + g.x1) / 2 <= x1 and y0 <= (g.y0 + g.y1) / 2 <= y1 for x0, y0, x1, y1 in outline_rects)]
            kept = [f for f in kept if any(not g.is_space for g in f.glyphs)]
            for f in kept:
                solid = [g for g in f.glyphs if not g.is_space]
                f.x0, f.y0, f.x1, f.y1 = min(g.x0 for g in solid), min(g.y0 for g in solid), max(g.x1 for g in solid), max(g.y1 for g in solid)

        # ---- 표: 격자를 칸으로 복원하고 칸 안의 글자는 칸별로 따로 줄을 만든다 ----
        colsep = split_x if best_len else None
        grids = _detect_tables(segs, fills, top, bottom, W, colsep)
        # 선으로 이은 상자 묶음(구조도) 안의 격자(위아래 상자 + 잇는 세로선)는 표가 아니다
        content_rects, framed = _content_boxes(_detect_boxes(segs, top, bottom), W, H, top, bottom)
        stats["page_frames"] += framed
        charted = _linked_boxes(content_rects, segs, colsep)

        def _not_charted(gs):
            return [g for g in gs if not any(c[0] <= g[0][0] and g[0][-1] <= c[2] and c[1] <= g[1][0] and g[1][-1] <= c[3]
                                             for c in charted)]
        grids = _not_charted(grids)
        # ---- 전폭 쪽: 가운데 단 구분선이 없고 글·박스·표·그림이 가운데를 가로지르는 쪽은 한 단으로 읽는다 ----
        single = False
        if not best_len:
            wide_grids = _not_charted(_detect_tables(segs, fills, top, bottom, W, None, wide=True))
            single = _full_width_page(kept, segs, wide_grids, imgs, W, top, bottom)
        if single:
            grids = wide_grids  # 큰 표 칸 안의 작은 표(구성 칸의 초장/중장/종장 상자)는 그 칸 안의 표로(아래)
            split_x = W + 1.0  # 모든 내용이 단 0
            stats["single_column_pages"] += 1
        tables: list[TableEl] = []
        for xs, ys, cells in grids:
            if _frame_grid(xs, ys):  # 테두리 안에 조금 들여 그린 칠 사각형(Tip 상자)은 표가 아니라 상자
                continue
            col = 0 if (xs[0] + xs[-1]) / 2 < split_x else 1
            t = TableEl(pno, col, xs, ys, cells)
            # 쪽 크기 한 행 표: 메모 칸 쪽(지문 분석 쪽: 점선 한쪽은 비워 둔 메모 칸, 다른 쪽에 글·그림)
            t.memo = single and len(ys) == 2 and len(xs) >= 3 and xs[-1] - xs[0] >= 0.6 * W and ys[-1] - ys[0] >= 0.6 * H
            tables.append(t)
        # 표 칸 안에 든 표: 바깥 표의 그 칸에 넣는다(글자는 가장 안쪽 칸으로)
        tables.sort(key=lambda t: (t.x1 - t.x0) * (t.y1 - t.y0))
        for k, t in enumerate(tables):
            for o in tables[k + 1:]:
                if o.x0 - 1 <= t.x0 and t.x1 <= o.x1 + 1 and o.y0 - 1 <= t.y0 and t.y1 <= o.y1 + 1:
                    cx, cy = (t.x0 + t.x1) / 2, (t.y0 + t.y1) / 2
                    host = next((cl for cl in o.cells if cl.x0 <= cx <= cl.x1 and cl.y0 <= cy <= cl.y1), None)
                    if host is not None:
                        t.nested, t.col = True, o.col
                        host.items.append(t)
                        stats["nested_tables"] += 1
                    break

        def _cell_at(x: float, y: float) -> Optional[Cell]:
            for t in tables:
                if t.x0 - 0.5 <= x <= t.x1 + 0.5 and t.y0 - 0.5 <= y <= t.y1 + 0.5:
                    for cl in t.cells:
                        if cl.x0 <= x <= cl.x1 and cl.y0 <= y <= cl.y1:
                            return cl
            return None

        cell_frags: dict[int, list[_Frag]] = defaultdict(list)
        blank_memo: list[TableEl] = []
        cell_obj: dict[int, Cell] = {}
        if tables:
            rest: list[_Frag] = []
            for f in kept:
                groups: list[tuple[Optional[Cell], list[Glyph]]] = []
                for g in f.glyphs:
                    cl = _cell_at((g.x0 + g.x1) / 2, (g.y0 + g.y1) / 2)
                    if groups and groups[-1][0] is cl:
                        groups[-1][1].append(g)
                    else:
                        groups.append((cl, [g]))
                for cl, gs in groups:
                    solid = [g for g in gs if not g.is_space] or gs
                    nf = _Frag(gs, min(g.x0 for g in solid), min(g.y0 for g in solid), max(g.x1 for g in solid),
                               max(g.y1 for g in solid), f.size) if len(groups) > 1 else f
                    if cl is None:
                        rest.append(nf)
                    else:
                        cell_frags[id(cl)].append(nf)
                        cell_obj[id(cl)] = cl
            kept = rest
            stats["tables"] += len(tables)
            # 모든 칸이 빈 메모 칸 쪽(글 없는 메모 쪽)은 다른 빈 쪽처럼 넣지 않는다
            blank_memo = [t for t in tables if t.memo and not any(id(cl) in cell_frags for cl in t.cells)
                          and not any(t.x0 <= (r[0] + r[2]) / 2 <= t.x1 and t.y0 <= (r[1] + r[3]) / 2 <= t.y1
                                      for r in [im[:4] for im in imgs] + outline_rects)]
            tables = [t for t in tables if t not in blank_memo]
            for t in tables:
                for cl in t.cells if t.memo else ():
                    cl.valign = "TOP"
            # 메모 칸 쪽은 테두리가 점선에서 둘로 나뉘어 쪽 테두리로 잡히지 않는다: 쪽 테두리가 있는 쪽으로 센다
            if not framed and (blank_memo or any(t.memo for t in tables)):
                stats["page_frames"] += 1

        # ---- 줄 안의 빈칸 네모: 글자가 없는 작은 사각형이 같은 높이의 글 줄 옆에 있으면 빈칸 표시로 넣는다 ----
        blank_rects = []
        for (bx0, by0, bx1, by1) in _detect_boxes(segs, top, bottom):
            if not (6 <= by1 - by0 <= 24) or any(t.x0 - 2 <= bx0 and bx1 <= t.x1 + 2 and t.y0 - 2 <= by0 and by1 <= t.y1 + 2
                                                 for t in tables):
                continue
            inside = any(not g.is_space and bx0 < (g.x0 + g.x1) / 2 < bx1 and by0 < (g.y0 + g.y1) / 2 < by1
                         for f in kept for g in f.glyphs)
            row = [f for f in kept if min(f.y1, by1) - max(f.y0, by0) >= 0.5 * min(f.y1 - f.y0, by1 - by0)
                   and (f.x1 <= bx0 + 1 or f.x0 >= bx1 - 1) and min(abs(f.x1 - bx0), abs(f.x0 - bx1)) < 4 * f.size]
            if inside or not row:
                continue
            size = row[0].size
            n = max(2, round((bx1 - bx0) / size))
            w = (bx1 - bx0) / n
            glyphs = [Glyph(BLANK_BOX, bx0 + k * w, by0, bx0 + (k + 1) * w, by1, size) for k in range(n)]
            for f in kept:  # 네모 자리를 채운 공백 글자는 뺀다
                f.glyphs = [g for g in f.glyphs if not (g.is_space and bx0 < (g.x0 + g.x1) / 2 < bx1
                                                        and by0 < (g.y0 + g.y1) / 2 < by1)]
            kept = [f for f in kept if f.glyphs]
            kept.append(_Frag(glyphs, bx0, by0, bx1, by1, size))
            blank_rects.append((bx0, by0, bx1, by1))
        stats["blank_boxes"] += len(blank_rects)

        # ---- 이미지 분류 ----
        content_imgs: list[ImageEl] = []
        for x0, y0, x1, y1, digest, xref in imgs:
            w, h = x1 - x0, y1 - y0
            if (y0 + y1) / 2 <= top or (y0 + y1) / 2 >= bottom or (x1 - x0 >= 0.6 * W and (y1 <= top + 1 or y0 >= bottom - 1)):
                stats["dropped_banner_image"] += 1
                continue
            pill = _pill_label(kept, x0, y0, x1, y1, split_x)
            if pill is not None:
                # 발문 앞 알약 모양 번호 그림("예제1"): 글자 자리표로 두고, 이름은 문서를 다 읽은 뒤 붙인다
                n = pill_order.setdefault(digest, len(pill_order) + 1)
                g = Glyph(PILL_MARK, x0, pill.y0, x1, pill.y1, pill.size, True, color=_pill_color(doc[pno - 1], (x0, y0, x1, y1)))
                pill_glyphs.append((g, n))
                kept.append(_Frag([g], x0, pill.y0, x1, pill.y1, pill.size))
                stats["pill_labels"] += 1
                continue
            if 4 <= w <= 16 and 4 <= h <= 16 and 0.75 <= w / h <= 1.33:
                # 보이지 않는 빈 그림(발문 띄어쓰기 자리에 놓인 흰 네모 등)은 원문자 아이콘이 아니다
                if _blank_image(doc, xref):
                    stats["dropped_decorative_image"] += 1
                    continue
                ch = icon_digests.setdefault(digest, chr(ICON_PUA_BASE + len(icon_digests)))
                kept.append(_Frag([Glyph(ch, x0, y0, x1, y1, h * 1.08, False, icon=digest)], x0, y0, x1, y1, h * 1.08))
                stats["icons"] += 1
                continue
            if w < 4 or h < 4 or (h < 26 and w / h > 4.5):
                stats["dropped_decorative_image"] += 1
                continue
            col = 0 if (x0 + x1) / 2 < split_x else 1
            content_imgs.append(ImageEl(pno, col, x0, y0, x1, y1, digest, xref))
        kept = _absorb_chart_labels(content_imgs, kept, stats)
        for x0, y0, x1, y1 in outline_rects:
            content_imgs.append(ImageEl(pno, 0 if (x0 + x1) / 2 < split_x else 1, x0, y0, x1, y1, OUTLINE_TEXT, 0))

        # 표 칸 안의 그림
        if tables:
            left = []
            for im in content_imgs:
                cl = _cell_at((im.x0 + im.x1) / 2, (im.y0 + im.y1) / 2)
                if cl is not None:
                    im.in_cell = True
                    cl.items.append(im)
                else:
                    left.append(im)
            content_imgs = left

        # ---- 단별 줄 만들기 ----
        lines: list[Line] = []
        for col in (0, 1):
            cf = [f for f in kept if (0 if (f.x0 + f.x1) / 2 < split_x else 1) == col]
            for g in _group_lines(cf):
                for sub in _split_far_fragments(g):
                    lines.append(_build_line(pno, col, sub))
        for t in tables:
            for cl in t.cells:
                for g in _group_lines(cell_frags.get(id(cl), [])):
                    ln = _build_line(pno, t.col, sorted(g, key=lambda f: f.x0))
                    ln.cell = (cl.x0, cl.x1)
                    cl.items.append(ln)
                    lines.append(ln)
                cl.items.sort(key=lambda it: (it.y0, it.x0))
                cls = [ln for ln in cl.items if isinstance(ln, Line)]
                long = [ln for ln in cls if len(ln.glyphs) >= 12]
                if t.memo and long:
                    # 메모 칸 표의 글 칸은 쪽 본문처럼 안쪽 여백이 넓다: 줄이 꽉 찼는지는 글의 좌우 끝으로 잰다
                    x1s = sorted(ln.x1 for ln in long)
                    for ln in cls:
                        ln.cell = (min(ln.x0 for ln in long), x1s[int(0.9 * (len(x1s) - 1))])

        # ---- [A] 묶음 괄호 (줄을 나눌 수 있으므로 박스 소속을 정하기 전에) ----
        brackets = _detect_brackets(pno, lines, segs, bracket_id)
        bracket_id += len(brackets) + 1
        stats["brackets"] += len(brackets)
        for ln in lines:
            all_sizes.extend(gl.size for gl in ln.glyphs if not gl.is_space and not gl.icon)

        # ---- 박스 ----
        # 가운데 단 구분선은 박스의 왼쪽/오른쪽 변이 아니다
        box_segs = [s for s in segs if not (s.vertical and best_len and abs(s.x0 - split_x) < 1.0
                                             and s.y1 - s.y0 >= 0.25 * content_h)]
        box_rects = _detect_boxes(box_segs, top, bottom)
        # 표의 외곽/칸은 박스가 아니다
        box_rects = [r for r in box_rects if not any(
            r[0] >= t.x0 - 4 and r[2] <= t.x1 + 4 and r[1] >= t.y0 - 4 and r[3] <= t.y1 + 4 for t in tables)
            and r not in blank_rects]
        box_rects = [r for r in _content_boxes(box_rects, W, H, top, bottom)[0] if not any(
            t.x0 - 4 <= r[0] and r[2] <= t.x1 + 4 and t.y0 - 4 <= r[1] and r[3] <= t.y1 + 4 for t in blank_memo)]
        # 선·화살표로 이어진 상자 묶음(지문 구조도): 묶음 전체를 감싸는 테두리 없는 상자를 두어 그 안의 도형으로 센다
        charts = _linked_boxes(box_rects, box_segs, split_x if best_len else None)
        stats["linked_box_charts"] += len(charts)
        box_rects += charts
        # 다른 박스 안에 들어 있는 사각형(도식의 칸 등)은 박스가 아니라 바깥 박스의 내부 도형으로 센다
        nested_in: dict[int, int] = {}
        for i, (x0, y0, x1, y1) in enumerate(box_rects):
            for j, (X0, Y0, X1, Y1) in enumerate(box_rects):
                if i != j and x0 >= X0 - 1 and x1 <= X1 + 1 and y0 >= Y0 - 1 and y1 <= Y1 + 1 \
                        and (x1 - x0) * (y1 - y0) < (X1 - X0) * (Y1 - Y0):
                    nested_in[i] = j
                    break
        # 바깥 테두리 안쪽에 조금 들여 그린 두 번째 테두리(연두 바탕 상자의 안쪽 틀)는 도형이 아니라 상자 모양이다
        def _inset(a, b) -> bool:
            return all(0 <= d <= 12 for d in (a[0] - b[0], a[1] - b[1], b[2] - a[2], b[3] - a[3]))
        inset = {i for i, j in nested_in.items() if _inset(box_rects[i], box_rects[j])}
        boxes: list[Box] = []
        for i, (x0, y0, x1, y1) in enumerate(box_rects):
            if i in nested_in:
                continue
            col = 0 if (x0 + x1) / 2 < split_x else 1
            boxes.append(Box(id=pno * 1000 + i, page=pno, col=col, x0=x0, y0=y0, x1=x1, y1=y1,
                             border=box_rects[i] not in charts))
        nested_rects = [box_rects[i] for i in nested_in if i not in inset]
        outer_rect = {b.id: (b.x0, b.y0, b.x1, b.y1) for b in boxes}  # 테두리 색은 바깥 틀에서 읽는다
        for i in inset:  # 안쪽 틀이 있으면 글 줄의 좌우 경계는 안쪽 틀(줄이 꽉 찼는지 판단)
            outer = next((b for b in boxes if b.id == pno * 1000 + nested_in[i]), None)
            if outer is not None:
                outer.x0, outer.x1 = max(outer.x0, box_rects[i][0]), min(outer.x1, box_rects[i][2])
        # 상자 바탕색·테두리 색
        for b in boxes:
            area = (b.x1 - b.x0) * (b.y1 - b.y0)
            for rect, color in fills:  # 나중에 칠한 것이 이긴다
                if b.x0 - 2 <= rect.x0 and rect.x1 <= b.x1 + 2 and b.y0 - 2 <= rect.y0 and rect.y1 <= b.y1 + 2 \
                        and rect.width * rect.height >= 0.7 * area:
                    b.fill = color
            ox0, oy0, ox1, oy1 = outer_rect.get(b.id, (b.x0, b.y0, b.x1, b.y1))
            edge = Counter(s.color for s in segs if s.color and (
                (s.vertical and min(abs(s.x0 - ox0), abs(s.x0 - ox1)) < 1.5 and s.y0 < oy1 and s.y1 > oy0)
                or (s.horizontal and min(abs(s.y0 - oy0), abs(s.y0 - oy1)) < 1.5 and s.x0 < ox1 and s.x1 > ox0)))
            if edge:
                b.border_color = edge.most_common(1)[0][0]
        # 선 없이 색만 칠한 넓은 영역(회색 지문 바탕 등)도 상자: 좌우로 맞붙은 조각은 하나로
        areas = []
        for rect, color in fills:
            if not color or rect.width < 80 or rect.height < 40 or rect.y1 <= top or rect.y0 >= bottom:
                continue
            if any(t.x0 - 3 <= rect.x0 and rect.x1 <= t.x1 + 3 and t.y0 - 3 <= rect.y0 and rect.y1 <= t.y1 + 3 for t in tables):
                continue
            if any(b.x0 - 14 <= rect.x0 and rect.x1 <= b.x1 + 14 and b.y0 - 14 <= rect.y0 and rect.y1 <= b.y1 + 14
                   for b in boxes):
                continue
            prev = areas[-1] if areas else None
            if prev and prev[4] == color and abs(prev[1] - rect.y0) < 2 and abs(prev[3] - rect.y1) < 2 \
                    and abs(prev[2] - rect.x0) < 3:
                areas[-1] = (prev[0], prev[1], rect.x1, prev[3], color)
            else:
                areas.append((rect.x0, rect.y0, rect.x1, rect.y1, color))
        for k, (x0, y0, x1, y1, color) in enumerate(areas):
            col = 0 if (x0 + x1) / 2 < split_x else 1
            boxes.append(Box(id=pno * 1000 + 500 + k, page=pno, col=col, x0=x0, y0=y0, x1=x1, y1=y1,
                             fill=color, border=False))
            stats["fill_boxes"] += 1
            # 색만 칠한 넓은 바탕 안의 테두리 상자(차례 쪽 그림 속 제목 칸)는 따로 상자가 아니라 바탕의 도형
            inside = [b for b in boxes if b.border and x0 - 1 <= b.x0 and b.x1 <= x1 + 1 and y0 - 1 <= b.y0 and b.y1 <= y1 + 1
                      and (b.x1 - b.x0) * (b.y1 - b.y0) < 0.25 * (x1 - x0) * (y1 - y0)]
            if inside:
                boxes = [b for b in boxes if b not in inside]
                nested_rects += [(b.x0, b.y0, b.x1, b.y1) for b in inside]

        def _box_of(cx: float, cy: float) -> Optional[Box]:
            best = None
            for b in boxes:
                if b.x0 - 2 <= cx <= b.x1 + 2 and b.y0 - 2 <= cy <= b.y1 + 2:
                    if best is None or (b.x1 - b.x0) * (b.y1 - b.y0) < (best.x1 - best.x0) * (best.y1 - best.y0):
                        best = b
            return best

        # ---- 밑줄 ----
        edge_h = [(y, x0, x1) for (x0, y0, x1, y1) in blank_rects for y in (y0, y1)]
        for b in boxes:
            edge_h.append((b.y0, b.x0, b.x1))
            edge_h.append((b.y1, b.x0, b.x1))
        underline_segs = []
        for s in segs:
            if not s.horizontal or s.x1 - s.x0 >= 0.6 * W:
                continue
            if any(t.x0 - 2 <= s.x0 and s.x1 <= t.x1 + 2 and any(abs(s.y0 - y) <= 1.5 for y in t.ys) for t in tables):
                continue
            if any(abs(s.y0 - ey) <= 1.5 and s.x0 <= ex0 + 3 and s.x1 >= ex1 - 3 for ey, ex0, ex1 in edge_h):
                continue
            if any(abs(s.y0 - ey) <= 1.5 and (s.x1 - s.x0) >= 0.8 * (ex1 - ex0) for ey, ex0, ex1 in edge_h):
                continue
            underline_segs.append(s)
        used_underlines = set()
        for ln in lines:
            for k, s in enumerate(underline_segs):
                if ln.y1 - 0.45 * ln.size <= s.y0 <= ln.y1 + 0.35 * ln.size and s.x1 > ln.x0 \
                        and s.x0 < ln.x1 + 4 * ln.size and k not in used_underlines:
                    hit = False
                    for gl in ln.glyphs:
                        cx = (gl.x0 + gl.x1) / 2
                        if not gl.is_space and s.x0 - 0.5 <= cx <= s.x1 + 0.5:
                            gl.underline = True
                            hit = True
                    if not hit:  # 빈칸 밑줄("㉠ : ______"): 글자 없이 공백 위에만 그은 선
                        blank = [gl for gl in ln.glyphs if gl.is_space and s.x0 - 0.5 <= (gl.x0 + gl.x1) / 2 <= s.x1 + 0.5]
                        if len(blank) >= 3:
                            for gl in blank:
                                gl.underline = True
                            hit = True
                        elif ln.x1 - 1 <= s.x0 and s.x0 - ln.x1 < 4 * ln.size and s.x1 - s.x0 > 2 * ln.size \
                                and ln.text.rstrip()[-1:] in (":", "：") and len(ln.text.strip()) <= 12:
                            # 줄 끝 공백은 줄을 만들 때 지워졌다: 선 길이만큼 밑줄 친 공백을 붙인다
                            w = 0.5 * ln.size
                            n = max(3, int(round((s.x1 - s.x0) / w)))
                            ln.glyphs.append(Glyph(" ", ln.x1, ln.y0, s.x0, ln.y1, ln.size))
                            ln.glyphs += [Glyph(" ", s.x0 + k * w, ln.y0, s.x0 + (k + 1) * w, ln.y1, ln.size, underline=True)
                                          for k in range(n)]
                            hit = True
                    if hit:
                        used_underlines.add(k)
            # 밑줄 친 두 글자 사이 공백도 밑줄
            gs = ln.glyphs
            for i in range(1, len(gs) - 1):
                if gs[i].is_space and gs[i - 1].underline and gs[i + 1].underline:
                    gs[i].underline = True

        # ---- 형광펜: 한 줄 높이로 색을 칠한 띠 위의 글자는 음영 ----
        for rect, color in fills:
            if color and rect.height < 18 and rect.width > 8 and not any(
                    t.x0 - 2 <= rect.x0 and rect.x1 <= t.x1 + 2 and t.y0 - 2 <= rect.y0 and rect.y1 <= t.y1 + 2 for t in tables):
                for ln in lines:
                    if ln.cell is None and ln.y0 < rect.y1 and ln.y1 > rect.y0:
                        for g in ln.glyphs:
                            if rect.x0 - 1 <= (g.x0 + g.x1) / 2 <= rect.x1 + 1 and rect.y0 - 2 <= (g.y0 + g.y1) / 2 <= rect.y1 + 2:
                                g.shade = color

        # ---- 박스 소속 + 내부 도형 수 ----
        def _box_of_line(ln: Line) -> Optional[Box]:
            """줄이 가로로 다 들어가는 가장 작은 박스. 가운데 점만 보면 발문 속 낱말 하나를 둘러싼 작은 네모
            (강조 표시)에 발문 줄 전체가 들어가 버린다."""
            cy = (ln.y0 + ln.y1) / 2
            best = None
            for b in boxes:
                if b.x0 - 4 <= ln.x0 and ln.x1 <= b.x1 + 4 and b.y0 - 2 <= cy <= b.y1 + 2:
                    if best is None or (b.x1 - b.x0) * (b.y1 - b.y0) < (best.x1 - best.x0) * (best.y1 - best.y0):
                        best = b
            return best

        for ln in lines:
            if ln.cell is not None:
                continue
            b = _box_of_line(ln)
            if b:
                ln.box = b.id
                b.items.append(ln)
        for t in tables:
            if t.nested:
                continue
            b = _box_of((t.x0 + t.x1) / 2, (t.y0 + t.y1) / 2)
            if b and (b.x1 - b.x0) * (b.y1 - b.y0) > (t.x1 - t.x0) * (t.y1 - t.y0) * 1.02:
                t.box = b.id
                b.items.append(t)
                for cl in t.cells:
                    for it in cl.items:
                        if isinstance(it, Line):
                            it.box = b.id
        for im in content_imgs:
            b = _box_of((im.x0 + im.x1) / 2, (im.y0 + im.y1) / 2)
            if b and im.x0 >= b.x0 - 3 and im.x1 <= b.x1 + 3:
                im.box = b.id
                b.items.append(im)
        # 낱말 몇 개만 둘러싼 낮은 네모(강조 표시)는 줄을 담지 못해 비어 있다: 박스가 아니다
        word_boxes = [b for b in boxes if not b.items and b.y1 - b.y0 < 18]
        # 색을 칠한 한 줄 높이 띠(정답 선지의 노란 형광펜)는 박스가 아니라 글자 음영
        for b in boxes:
            if b.fill and b.y1 - b.y0 < 18 and len(b.items) == 1 and isinstance(b.items[0], Line):
                b.items[0].box = None
                word_boxes.append(b)
        if word_boxes:
            stats["inline_word_boxes"] += len(word_boxes)
            boxes = [b for b in boxes if b not in word_boxes]
        # 박스 밖의 작은 그림(‘빈출’ 배지 등 편집 장식)은 내용이 아니다
        small = [im for im in content_imgs if im.box is None and im.height < 26 and im.width < 120 and im.digest != OUTLINE_TEXT]
        if small:
            stats["dropped_decorative_image"] += len(small)
            content_imgs = [im for im in content_imgs if im not in small]
        def _in_table(x0: float, y0: float, x1: float, y1: float) -> bool:
            return any(t.x0 - 2 <= x0 and x1 <= t.x1 + 2 and t.y0 - 2 <= y0 and y1 <= t.y1 + 2 for t in tables) or \
                any(bx0 - 2 <= x0 and x1 <= bx1 + 2 and by0 - 2 <= y0 and y1 <= by1 + 2 for bx0, by0, bx1, by1 in blank_rects)


        def _bracket_seg(s: _Seg) -> bool:
            return any(abs(s.x0 - bk.x) <= 2 and bk.y0 - 2 <= s.y0 and s.y1 <= bk.y1 + 2
                       or (s.horizontal and abs(s.x0 - bk.x) <= 2 and (abs(s.y0 - bk.y0) <= 2 or abs(s.y0 - bk.y1) <= 2))
                       for bk in brackets)

        frames = [box_rects[i] for i in inset]
        # 글자 높이의 작은 네모(낱말 하나를 둘러싼 테두리, 폭이 좁아 박스 찾기에서는 빠진다)
        vs_short = [s for s in segs if s.vertical and s.y1 - s.y0 < 16]
        small_rects = []
        for a in vs_short:
            for c in sorted(vs_short, key=lambda v: v.x0):
                if c.x0 > a.x0 + 3 and c.x0 - a.x0 < 120 and abs(c.y0 - a.y0) < 1 and abs(c.y1 - a.y1) < 1 and any(
                        h.horizontal and abs(h.y0 - a.y0) < 1 and h.x0 <= a.x0 + 1 and h.x1 >= c.x0 - 1 for h in segs):
                    r = (a.x0, a.y0, c.x0, a.y1)
                    if not any(q[0] < r[0] - 1 and r[2] <= q[2] + 1 for q in small_rects if abs(q[1] - r[1]) < 1):
                        small_rects = [q for q in small_rects if not (abs(q[1] - r[1]) < 1 and q[0] == r[0] and q[2] > r[2])]
                        small_rects.append(r)
                    break

        def _on_frame(s: _Seg) -> bool:  # 안쪽 틀(상자 모양)의 변
            return any(abs(s.x0 - fx) < 1.5 and s.y0 >= fy0 - 1.5 and s.y1 <= fy1 + 1.5
                       for fx0, fy0, fx1, fy1 in frames for fx in (fx0, fx1))

        for b in boxes:
            n = 0
            for s in segs:
                if s.vertical and b.x0 + 3 < s.x0 < b.x1 - 3 and b.y0 - 1 <= s.y0 and s.y1 <= b.y1 + 1 \
                        and not _in_table(s.x0, s.y0, s.x1, s.y1) and not _bracket_seg(s) and not _on_frame(s):
                    n += 1
            for r in others:
                if b.x0 + 2 < r.x0 and r.x1 < b.x1 - 2 and b.y0 + 2 < r.y0 and r.y1 < b.y1 - 2 \
                        and not _in_table(r.x0, r.y0, r.x1, r.y1) and not _inset((r.x0, r.y0, r.x1, r.y1), (b.x0, b.y0, b.x1, b.y1)):
                    n += 1
            inner = []
            for (x0, y0, x1, y1) in nested_rects:
                if b.x0 - 1 <= x0 and x1 <= b.x1 + 1 and b.y0 - 1 <= y0 and y1 <= b.y1 + 1:
                    n += 4
                    inner.append((x0, y0, x1, y1))
            # 낱말 네모: 줄의 일부 낱말만 둘러싼 낮은 사각형은 그 글자들의 글자 테두리
            for r in [q for q in small_rects if b.x0 <= q[0] and q[2] <= b.x1 and b.y0 <= q[1] and q[3] <= b.y1]:
                if r[3] - r[1] > 16:
                    continue
                for ln in b.items:
                    if isinstance(ln, Line) and ln.y0 < r[3] and ln.y1 > r[1] and (r[2] - r[0]) < 0.7 * (ln.x1 - ln.x0):
                        for g in ln.glyphs:
                            if r[0] - 1 <= (g.x0 + g.x1) / 2 <= r[2] + 1:
                                g.boxed = True
            # 닫는 괄호 "]": 세로선 위·아래 끝에서 왼쪽으로 짧은 가로선(시 풀이에서 장마다 구절과 요약을 가른다)
            for s in segs:
                if s.vertical and b.x0 + 3 < s.x0 < b.x1 - 3 and b.y0 <= s.y0 and s.y1 <= b.y1 and s.y1 - s.y0 >= 15:
                    ticks = [h for h in segs if h.horizontal and h.x1 - h.x0 < 30 and abs(h.x1 - s.x0) < 1.5
                             and min(abs(h.y0 - s.y0), abs(h.y0 - s.y1)) < 1.5]
                    if {round(h.y0) for h in ticks} >= {round(s.y0), round(s.y1)} or len({round(h.y0) for h in ticks}) >= 2:
                        if not any(abs(x - s.x0) < 1.5 and abs(y0 - s.y0) < 1.5 for x, y0, _ in b.brackets):
                            b.brackets.append((s.x0, s.y0, s.y1))
            b.brackets.sort(key=lambda t: t[1])
            # 낱말 띠: 박스 안 사각형이 줄 하나만 둘러싸면 그 줄의 띠 테두리(거의 겹친 사각형 두 개면 이중선)
            for r in inner:
                inside = [ln for ln in b.items if isinstance(ln, Line)
                          and r[0] - 1 <= (ln.x0 + ln.x1) / 2 <= r[2] + 1 and r[1] - 1 <= (ln.y0 + ln.y1) / 2 <= r[3] + 1]
                if len(inside) == 1 and r[3] - r[1] < 3 * inside[0].size and (r[2] - r[0]) >= 0.7 * (inside[0].x1 - inside[0].x0):
                    twin = any(q is not r and all(abs(u - v) < 3 for u, v in zip(q, r)) for q in inner)
                    inside[0].frame = "DOUBLE_SLIM" if twin else (inside[0].frame or "SOLID")
            inner += [(r.x0, r.y0, r.x1, r.y1) for r in others if b.x0 + 2 < r.x0 and r.x1 < b.x1 - 2
                      and b.y0 + 2 < r.y0 and r.y1 < b.y1 - 2]
            b.inner_drawings = n
            b.framed_lines = sum(1 for ln in b.items if isinstance(ln, Line) and any(
                x0 - 1 <= (ln.x0 + ln.x1) / 2 <= x1 + 1 and y0 - 1 <= (ln.y0 + ln.y1) / 2 <= y1 + 1 for x0, y0, x1, y1 in inner))
            b.items.sort(key=lambda it: (it.y0, it.x0))

        # ---- 흰 글자: 진한 바탕 상자·칸 안(검은 제목 띠)만 흰색, 나머지는 기본 색 ----
        dark_boxes = {b.id for b in boxes if _dark(b.fill)}
        dark_cells = {id(ln) for t in tables for cl in t.cells if _dark(cl.fill) for ln in cl.items if isinstance(ln, Line)}
        for ln in lines:
            if ln.box not in dark_boxes and id(ln) not in dark_cells:
                for g in ln.glyphs:
                    if g.color == WHITE:
                        g.color = None

        # ---- 출판사 저작권·콘텐츠 보호 고지문(© 마크 포함)은 문제 내용이 아니다 ----
        drop = _notice_items(lines, content_imgs, boxes, tables, segs)
        if drop:
            stats["dropped_notice_lines"] += sum(1 for ln in lines if id(ln) in drop)
            lines = [ln for ln in lines if id(ln) not in drop]
            content_imgs = [im for im in content_imgs if id(im) not in drop]
            boxes = [b for b in boxes if not (b.items and all(id(x) in drop for x in b.items))]
            tables = [t for t in tables if not _table_lines(t) or not all(id(x) in drop for x in _table_lines(t))]

        # ---- 단 경계 ----
        def _col_bounds(col: int) -> tuple[float, float]:
            # 표 칸 줄, 단을 넘어가는 줄(전폭 지문 등)은 단 폭을 재는 데 쓰지 않는다
            ls = [ln for ln in lines if ln.col == col and len(ln.glyphs) >= 12 and ln.cell is None
                  and (single or col == 1 or ln.x1 <= split_x + 10)]
            if not ls:
                return ((36.0, min(split_x, W) - 14) if col == 0 else (split_x + 14, W - 36))
            xs0 = sorted(ln.x0 for ln in ls)
            xs1 = sorted(ln.x1 for ln in ls)
            return xs0[0], xs1[int(0.9 * (len(xs1) - 1))]

        info = PageInfo(pno, W, H, split_x, top, bottom, _col_bounds(0), _col_bounds(1), single=single)

        # ---- 읽기 순서 ----
        flow: list[FlowItem] = []
        free: list = [b for b in boxes]
        free += [ln for ln in lines if ln.box is None and ln.cell is None]
        free += [im for im in content_imgs if im.box is None]
        free += [t for t in tables if t.box is None and not t.nested]
        # 두 단 쪽이라도 단 구분선 위/아래에 가운데를 가로지르는 지문·상자·표가 있으면 그 구간은 전폭:
        # 위 구간 → 왼쪽 단 → 오른쪽 단 → 아래 구간 순서로 읽는다(해설서의 회색 지문, 맨 아래 '핵심 개념' 상자)
        above, below = [], []

        def crosses(it) -> bool:
            return it.x0 < split_x - 10 and it.x1 > split_x + 10
        if not best_len and not single and any(crosses(it) for it in free):
            # 단 구분선 없는 두 단 쪽: 단 안 내용의 세로 범위 밖에 가로지르는 상자가 있으면 그 구간이 전폭
            inner = [it for it in free if not crosses(it)]
            div_y0 = min((it.y0 for it in inner), default=bottom)
            div_y1 = max((it.y1 for it in inner), default=bottom)
            # 한쪽 단에만 있고 다른 단 내용보다 아래이며 바로 아래 가로지르는 상자에 붙은 것(구조도 위 '지문 구조' 칸)은
            # 아래 전폭 구간: 두 단에 두면 한글이 단 높이를 맞추며 오른쪽 단 맨 위로 옮긴다
            ends = [max((it.y1 for it in inner if it.col == c), default=top) for c in (0, 1)]
            edge = min((it.y0 for it in free if crosses(it) and it.y0 >= min(ends) - 3), default=None)
            if edge is not None:
                for it in sorted((it for it in inner if it.y0 >= ends[1 - it.col] + 3 and it.y1 <= edge + 3),
                                 key=lambda it: -it.y1):
                    if edge - it.y1 > 30:
                        break
                    edge = div_y1 = it.y0
        if not single and (best_len or any(crosses(it) for it in free)):
            up = [it for it in free if it.y1 <= div_y0 + 3]
            down = [it for it in free if it.y0 >= div_y1 - 3]

            def spans(zone) -> bool:  # 가운데를 가로지르거나, 가운데 선에서 맞붙은 좌우 두 상자(반쪽씩 그린 회색 지문)
                if any(crosses(it) for it in zone):
                    return True
                return any(isinstance(a, Box) and isinstance(c, Box) and abs(a.x1 - c.x0) < 3 and abs(a.x1 - split_x) < 12
                           and min(a.y1, c.y1) - max(a.y0, c.y0) > 0.6 * min(a.y1 - a.y0, c.y1 - c.y0)
                           for a in zone for c in zone if a is not c)
            if spans(up):
                above = up
            if spans(down):
                below = down
            if above or below:
                stats["wide_zones"] += bool(above) + bool(below)
                zone = {id(it) for it in above + below}
                free = [it for it in free if id(it) not in zone]
                wide_ids.update(id(it) for it in above + below)
        flow.extend(sorted(above, key=lambda it: (it.y0, it.x0)))
        for col in (0, 1):
            items = [it for it in free if it.col == col]
            items.sort(key=lambda it: (it.y0, it.x0))
            flow.extend(items)
        flow.extend(sorted(below, key=lambda it: (it.y0, it.x0)))
        pm = PageModel(info, lines, content_imgs, boxes, flow)
        pages.append(pm)

    body_size = statistics.median(all_sizes) if all_sizes else 10.0

    # ---- 단/페이지를 넘어 이어지는 박스 합치기 ----
    flow: list[FlowItem] = []
    info_by_page = {pm.info.number: pm.info for pm in pages}
    for pm in pages:
        for it in pm.flow:
            prev = flow[-1] if flow else None
            if isinstance(it, Box) and isinstance(prev, Box):
                last = prev.parts[-1] if prev.parts else prev
                pinfo, cinfo = info_by_page[last.page], info_by_page[it.page]
                if (last.page, last.col) != (it.page, it.col) and pinfo.single == cinfo.single \
                        and last.y1 >= pinfo.content_bottom - 4 * body_size \
                        and it.y0 <= cinfo.content_top + 4 * body_size \
                        and not _starts_with_title(it):
                    prev.parts.append(it)
                    stats["box_continuations"] += 1
                    continue
            flow.append(it)

    if pill_glyphs:
        word = _pill_word(pages)
        for g, n in pill_glyphs:
            g.c = f"{word}{n} " if word else f"{n}. "

    for it in flow:
        if isinstance(it, ImageEl):
            it.png = None
    stats["pages"] = len(pages)
    stats["boxes"] = sum(1 for it in flow if isinstance(it, Box))
    ex = Extraction(pdf_path, pages, flow, icon_digests, body_size, doc, dict(stats), wide_ids=wide_ids,
                    faithful=len(pages) >= 2 and stats["page_frames"] >= 0.5 * len(pages))
    ex.header_texts = header_texts
    return ex


OUTLINE_TEXT = "outline-text"  # 윤곽선 글자 줄을 영역째 그린 그림(ImageEl.digest)
PILL_MARK = "\ue0ff"  # 알약 번호 그림 자리표(문서를 다 읽은 뒤 "예제1 " 같은 글자로 바뀐다)
PILL_WORD_RE = re.compile(r"\[\s*([가-힣]{1,4})\s?(\d{1,2})\s*\]")


def _absorb_chart_labels(imgs: list[ImageEl], kept: list[_Frag], stats: Counter) -> list[_Frag]:
    """그래프 그림 위에 글자로 찍은 라벨(A·B, 눈금 숫자, 세로로 쓴 축 이름 "원/소/의/함/량")은 그림과 한 덩어리로:
    글로 따로 빼면 그림 아래에 "100 원 A 소 …"로 흩어진다. 그림 안에 글자가 하나라도 찍혀 있는 그림만(라벨 붙은
    그래프) 그 안과 둘레(글자 크기의 1.5배 안, 넓혀 가며)의 짧은 글 조각을 그림 영역에 넣는다. 같은 높이에 긴 글이
    있는 조각(그림 옆 본문 줄)이나 원문자(선택지 번호)는 넣지 않는다."""
    def short(f: _Frag) -> bool:
        text = "".join(g.c for g in f.glyphs if not g.is_space)
        return 0 < len(text) <= 8 and not any(c in CIRCLED_DIGITS for c in text)

    def inside(f: _Frag, im) -> bool:
        return im.x0 <= (f.x0 + f.x1) / 2 <= im.x1 and im.y0 <= (f.y0 + f.y1) / 2 <= im.y1

    for im in imgs:
        if im.x1 - im.x0 < 40 or im.y1 - im.y0 < 40 or not any(short(f) and inside(f, im) for f in kept):
            continue
        taken: list[_Frag] = []
        grew = True
        while grew:
            grew = False
            for f in kept:
                if f in taken or not short(f):
                    continue
                m = 1.5 * f.size
                if not (im.x0 - m <= f.x1 and f.x0 <= im.x1 + m and im.y0 - m <= f.y1 and f.y0 <= im.y1 + m):
                    continue
                row = [o for o in kept if o is not f and min(o.y1, f.y1) - max(o.y0, f.y0) > 0.5 * min(o.y1 - o.y0, f.y1 - f.y0)]
                if any(not short(o) and (im.x0 - m <= o.x1 and o.x0 <= im.x1 + m) for o in row):
                    continue
                taken.append(f)
                im.x0, im.y0, im.x1, im.y1 = min(im.x0, f.x0), min(im.y0, f.y0), max(im.x1, f.x1), max(im.y1, f.y1)
                grew = True
        if taken:
            stats["chart_labels"] += len(taken)
            kept = [f for f in kept if f not in taken]
    return kept


def _pill_label(kept: list, x0: float, y0: float, x1: float, y1: float, split_x: float) -> Optional["_Frag"]:
    """줄 맨 앞의 납작한 작은 그림(높이 9~20pt, 가로 1.5~3.5배)이고 바로 오른쪽에 글이 이어지면 그 글 조각.
    글 앞에 이미 숫자 번호("3.")가 있으면 번호 그림이 아니다."""
    w, h = x1 - x0, y1 - y0
    if not (9 <= h <= 20 and 1.5 <= w / h <= 3.5):
        return None
    side = (x0 + x1) / 2 < split_x
    band = [f for f in kept if min(f.y1, y1) - max(f.y0, y0) > 0.5 * min(h, f.y1 - f.y0)
            and ((f.x0 + f.x1) / 2 < split_x) == side]
    right = sorted([f for f in band if -1 <= f.x0 - x1 <= 2 * h], key=lambda f: f.x0)
    if not right or any(f.x1 <= x0 + 1 for f in band):
        return None
    first = "".join(g.c for g in right[0].glyphs).lstrip()
    if not first or re.match(r"\d{1,3}\s*[.)]", first):
        return None
    return right[0]


def _pill_color(page, rect) -> Optional[str]:
    """알약 그림의 바탕색(가장 진한 유채색 화소)."""
    try:
        pix = page.get_pixmap(clip=fitz.Rect(*rect), dpi=72, alpha=False)
    except Exception:
        return None
    best, best_s = None, 0.25
    data, n = pix.samples, pix.n
    for i in range(0, len(data) - n + 1, n):
        r, g, b = data[i], data[i + 1], data[i + 2]
        mx, mn = max(r, g, b), min(r, g, b)
        sat = (mx - mn) / mx if mx else 0.0
        if sat > best_s and mx > 60:
            best, best_s = (r, g, b), sat
    return "#%02X%02X%02X" % best if best else None


def _pill_word(pages: list) -> str:
    """알약 번호의 이름: 본문에서 "[예제1]"처럼 대괄호로 가리킨 낱말 중 가장 많은 것(없으면 번호만)."""
    cnt: Counter = Counter()
    for pm in pages:
        for ln in pm.lines:
            for m in PILL_WORD_RE.finditer(ln.text):
                cnt[m.group(1)] += 1
    return cnt.most_common(1)[0][0] if cnt else ""


TITLE_RE = re.compile(r"^\s*[<〈＜《]\s*[^<>〈〉＜＞]{1,14}\s*[>〉＞》]\s*$")


def _starts_with_title(box: Box) -> bool:
    for it in box.items:
        if isinstance(it, Line):
            return bool(TITLE_RE.match(it.text))
        return False
    return False


def _split_far_fragments(frags: list[_Frag]) -> list[list[_Frag]]:
    """같은 높이라도 멀리 떨어진 조각(시 옆의 [A] 표시 등)은 별도 줄로 둔다.
    단, 원문자로 시작하는 조각(한 줄에 선택지 여러 개)은 같은 줄로 두고 IR에서 나눈다."""
    frags = sorted(frags, key=lambda f: f.x0)
    out = [[frags[0]]]
    head = next((g for g in frags[0].glyphs if not g.is_space), None)
    choice_row = head is not None and (head.icon is not None or head.c in "①②③④⑤⑥⑦⑧⑨⑩")
    for f in frags[1:]:
        prev = out[-1][-1]
        first = next((g for g in f.glyphs if not g.is_space), None)
        starts_marker = first is not None and (first.icon is not None or first.c in "①②③④⑤⑥⑦⑧⑨⑩")
        side_label = any(re.fullmatch(r"\s*\[[A-Z가-힣]\]\s*", "".join(g.c for g in x.glyphs)) for x in (f, prev))
        # 앞 조각들 중 가장 오른쪽 끝과 잰다: 문장부호만 따로 찍은 조각(". ")이 긴 조각 안쪽에 겹쳐 있으면
        # 바로 앞 조각 끝과 재면 뒤 조각까지 거리가 멀어 보인다
        gap = f.x0 - max(x.x1 for x in out[-1])
        if (side_label and gap > 0.8 * f.size) or (gap > 3.0 * max(f.size, prev.size) and not starts_marker
                                                     and not choice_row):
            out.append([f])
        else:
            out[-1].append(f)
    # 짧은 조각이 한 줄에 띄엄띄엄 있으면(표 모양 선택지의 머리 ㉠ ㉡ ㉢ 등) 한 줄로 둔다.
    # 2개뿐이면 더 짧은 조각(기호 수준)만, 출전(- 작가)이나 [A] 표시는 제외
    texts = ["".join(g.c for x in grp for g in x.glyphs).strip() for grp in out]
    limit = 12 if len(out) >= 3 else 6
    if len(out) >= 2 and all(len(t) <= limit for t in texts) and not any(t.startswith(("-", "–", "—")) for t in texts) \
            and not any(re.fullmatch(r"\s*\[[A-Z가-힣]\]\s*", "".join(g.c for g in x.glyphs)) for grp in out for x in grp):
        return [[x for grp in out for x in grp]]
    return out


def _build_line(pno: int, col: int, frags: list[_Frag]) -> Line:
    frags = sorted(frags, key=lambda f: f.x0)
    glyphs: list[Glyph] = []
    for f in frags:
        for g in f.glyphs:
            # 겹쳐 찍힌 중복 글자(가짜 굵게) 제거
            if glyphs and not g.is_space and glyphs[-1].c == g.c and abs(glyphs[-1].x0 - g.x0) < 0.3 * g.size:
                continue
            glyphs.append(g)
    glyphs.sort(key=lambda g: (g.x0 if not g.is_space else g.x0 - 0.001))
    out: list[Glyph] = []
    prev_solid: Optional[Glyph] = None
    for g in glyphs:
        if g.is_space:
            if out and not out[-1].is_space:
                out.append(Glyph(" ", g.x0, g.y0, g.x1, g.y1, g.size))
            continue
        if prev_solid is not None and out and out[-1].is_space and g.c not in "①②③④⑤⑥⑦⑧⑨⑩" and not g.icon:
            gap = g.x0 - prev_solid.x1
            if gap > 3.0 * g.size:  # 원문 공백 글자가 넓은 간격을 차지하면(표 모양 줄) 전각 공백을 덧붙인다
                sp = out.pop()
                for _ in range(min(4, max(1, round(gap / g.size) - 2))):
                    out.append(Glyph("\u2003", prev_solid.x1, g.y0, prev_solid.x1, g.y1, g.size))
                out.append(sp)
        if prev_solid is not None and out and not out[-1].is_space:
            gap = g.x0 - prev_solid.x1
            size_jump = max(g.size, prev_solid.size) > 1.2 * min(g.size, prev_solid.size) and not (g.icon or prev_solid.icon)
            if gap > GAP_SPACE_RATIO * max(g.size, prev_solid.size) * (1.0 if not (g.icon or prev_solid.icon) else 0.9) \
                    or (size_jump and gap > 0.8):
                # 표 모양으로 띄엄띄엄 놓인 칸(선택지 ① 수리함   좋은 사람 …)은 공백 여러 개로 간격을 살린다
                wide = gap > 3.0 * g.size and g.c not in "①②③④⑤⑥⑦⑧⑨⑩" and not g.icon
                for _ in range(min(4, max(1, round(gap / g.size) - 2)) if wide else 0):  # 전각 공백(U+2003)은 합쳐지지 않는다
                    out.append(Glyph("\u2003", prev_solid.x1, g.y0, prev_solid.x1, g.y1, g.size))
                out.append(Glyph(" ", prev_solid.x1, g.y0, g.x0, g.y1, g.size))
        out.append(g)
        prev_solid = g
    trailing = bool(out) and out[-1].is_space
    while out and out[-1].is_space:
        out.pop()
    while out and out[0].is_space:
        out.pop(0)
    solid = [g for g in out if not g.is_space]
    sizes = [g.size for g in solid if not g.icon] or [g.size for g in solid] or [10.0]
    lead = next((g.size for g in solid if not g.icon), frags[0].size)  # 첫 글자 크기(문제 번호 판별용)
    return Line(pno, col, out, min(g.x0 for g in solid), min(g.y0 for g in solid), max(g.x1 for g in solid),
                max(g.y1 for g in solid), statistics.median(sizes), lead, trailing)
