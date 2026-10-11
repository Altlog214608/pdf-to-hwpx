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

from .model import BLANK_BOX, Box, Bracket, Cell, FlowItem, Glyph, ICON_PUA_BASE, ImageEl, Line, PageInfo, TableEl

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

    def render(self, page: int, rect: tuple[float, float, float, float]) -> bytes:
        p = self.doc[page - 1]
        clip = fitz.Rect(*rect) & p.rect
        zoom = min(RENDER_ZOOM, RENDER_MAX_PX / max(1.0, clip.width, clip.height))
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

def _is_bold(font: str, flags: int, char_flags: int = 0) -> bool:
    """굵은 글꼴 이름(…Bold, 나눔스퀘어 B/EB 등)이거나, 글자를 칠하고 테두리까지 그린 가짜 굵게(한글이 내보내는 진하게)."""
    return ("bold" in font.lower() or bool(flags & 16) or bool(re.search(r"[a-z](?:EB|XB|B)$", font))
            or (char_flags & 48) == 48)


def _color(c: int) -> Optional[str]:
    """글자 색. 검정(또는 거의 검정)과 흰색(색 배경 위 글자: 한글에선 배경이 없어 보이지 않음)은 None."""
    r, g, b = (c >> 16) & 255, (c >> 8) & 255, c & 255
    if max(r, g, b) < 40 or min(r, g, b) > 235:
        return None
    return "#%02X%02X%02X" % (r, g, b)


# Wingdings 글꼴은 일반 글자 자리에 기호를 그린다(예: 'ü'가 체크 표시). 문제집에 자주 나오는 것만 같은 모양의 유니코드로.
WINGDINGS = {"ü": "✓", "û": "✗", "ý": "☒", "þ": "☑", "è": "→", "ç": "←", "é": "↑", "ê": "↓",
             "ð": "⇨", "ï": "⇦", "ñ": "⇧", "ò": "⇩", "l": "●", "n": "■", "u": "◆", "§": "▪", "o": "□", "¡": "○"}


def _page_fragments(page: fitz.Page) -> list[_Frag]:
    frags: list[_Frag] = []
    raw = page.get_text("rawdict", flags=fitz.TEXT_PRESERVE_WHITESPACE | fitz.TEXT_COLLECT_STYLES)
    for block in raw.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            glyphs: list[Glyph] = []
            for span in line.get("spans", []):
                size = float(span.get("size") or 0)
                if size < HIDDEN_TEXT_MAX_SIZE:
                    continue
                bold = _is_bold(span.get("font", ""), int(span.get("flags") or 0), int(span.get("char_flags") or 0))
                color = _color(int(span.get("color") or 0))
                wingdings = "wingdings" in span.get("font", "").lower()
                for ch in span.get("chars", []):
                    c = ch.get("c") or ""
                    if not c:
                        continue
                    if wingdings:
                        c = WINGDINGS.get(c, c)
                    x0, y0, x1, y1 = ch["bbox"]
                    if c == " ":
                        c = " "
                    glyphs.append(Glyph(c, x0, y0, x1, y1, size, bold, color=color))
            if not glyphs or all(g.is_space for g in glyphs):
                continue
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


def _page_segments(page: fitz.Page) -> tuple[list[_Seg], int]:
    segs: list[_Seg] = []
    others = []
    for d in page.get_drawings():
        if _invisible(d):  # 선 없이 흰색으로만 칠한 사각형(한글이 문단 배경으로 내보냄)은 보이지 않으므로 테두리가 아니다
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
    return segs, others


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
                if best is None or rx < runs[best][0]:
                    best = j
        if best is not None:
            used.add(i)
            used.add(best)
            rx, ry0, ry1 = runs[best]
            boxes.append((lx, max(ly0, ry0), rx, min(ly1, ry1)))
    return boxes


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
            gy0 = min(x.y0 for x in g)
            gy1 = max(x.y1 for x in g)
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

    # ---- 1차: 페이지별 원자료 수집 ----
    for pno, page in enumerate(doc, start=1):
        W, H = page.rect.width, page.rect.height
        frags = _page_fragments(page)
        segs, others = _page_segments(page)
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
        raw_pages.append((pno, W, H, frags, segs, others, imgs, top, bottom, fills))

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
    for pno, W, H, frags, segs, others, imgs, top, bottom, fills in raw_pages:
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
        div_y0 = min((s.y0 for s in segs if s.vertical and abs(s.x0 - split_x) < 1.0), default=top) if best_len else top
        div_y1 = max((s.y1 for s in segs if s.vertical and abs(s.x0 - split_x) < 1.0), default=bottom) if best_len else bottom

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

        # ---- 표: 격자를 칸으로 복원하고 칸 안의 글자는 칸별로 따로 줄을 만든다 ----
        colsep = split_x if best_len else None
        grids = _detect_tables(segs, fills, top, bottom, W, colsep)
        # ---- 전폭 쪽: 가운데 단 구분선이 없고 글·박스·표·그림이 가운데를 가로지르는 쪽은 한 단으로 읽는다 ----
        single = False
        if not best_len:
            wide_grids = _detect_tables(segs, fills, top, bottom, W, None, wide=True)
            single = _full_width_page(kept, segs, wide_grids, imgs, W, top, bottom)
        if single:
            grids = wide_grids  # 큰 표 칸 안의 작은 표(구성 칸의 초장/중장/종장 상자)는 그 칸 안의 표로(아래)
            split_x = W + 1.0  # 모든 내용이 단 0
            stats["single_column_pages"] += 1
        tables: list[TableEl] = []
        for xs, ys, cells in grids:
            col = 0 if (xs[0] + xs[-1]) / 2 < split_x else 1
            tables.append(TableEl(pno, col, xs, ys, cells))
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
            if 4 <= w <= 16 and 4 <= h <= 16 and 0.75 <= w / h <= 1.33:
                ch = icon_digests.setdefault(digest, chr(ICON_PUA_BASE + len(icon_digests)))
                kept.append(_Frag([Glyph(ch, x0, y0, x1, y1, h * 1.08, False, icon=digest)], x0, y0, x1, y1, h * 1.08))
                stats["icons"] += 1
                continue
            if w < 4 or h < 4 or (h < 26 and w / h > 4.5):
                stats["dropped_decorative_image"] += 1
                continue
            col = 0 if (x0 + x1) / 2 < split_x else 1
            content_imgs.append(ImageEl(pno, col, x0, y0, x1, y1, digest, xref))

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
            boxes.append(Box(id=pno * 1000 + i, page=pno, col=col, x0=x0, y0=y0, x1=x1, y1=y1))
        nested_rects = [box_rects[i] for i in nested_in if i not in inset]
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
            edge = Counter(s.color for s in segs if s.color and (
                (s.vertical and min(abs(s.x0 - b.x0), abs(s.x0 - b.x1)) < 1.5 and s.y0 < b.y1 and s.y1 > b.y0)
                or (s.horizontal and min(abs(s.y0 - b.y0), abs(s.y0 - b.y1)) < 1.5 and s.x0 < b.x1 and s.x1 > b.x0)))
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
                if ln.y1 - 0.45 * ln.size <= s.y0 <= ln.y1 + 0.35 * ln.size and s.x1 > ln.x0 and s.x0 < ln.x1:
                    hit = False
                    for gl in ln.glyphs:
                        cx = (gl.x0 + gl.x1) / 2
                        if not gl.is_space and s.x0 - 0.5 <= cx <= s.x1 + 0.5:
                            gl.underline = True
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
        small = [im for im in content_imgs if im.box is None and im.height < 26 and im.width < 120]
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
            # 낱말 띠: 박스 안 사각형이 줄 하나만 둘러싸면 그 줄의 띠 테두리(거의 겹친 사각형 두 개면 이중선)
            for r in inner:
                inside = [ln for ln in b.items if isinstance(ln, Line)
                          and r[0] - 1 <= (ln.x0 + ln.x1) / 2 <= r[2] + 1 and r[1] - 1 <= (ln.y0 + ln.y1) / 2 <= r[3] + 1]
                if len(inside) == 1 and r[3] - r[1] < 3 * inside[0].size:
                    twin = any(q is not r and all(abs(u - v) < 3 for u, v in zip(q, r)) for q in inner)
                    inside[0].frame = "DOUBLE_SLIM" if twin else (inside[0].frame or "SOLID")
            inner += [(r.x0, r.y0, r.x1, r.y1) for r in others if b.x0 + 2 < r.x0 and r.x1 < b.x1 - 2
                      and b.y0 + 2 < r.y0 and r.y1 < b.y1 - 2]
            b.inner_drawings = n
            b.framed_lines = sum(1 for ln in b.items if isinstance(ln, Line) and any(
                x0 - 1 <= (ln.x0 + ln.x1) / 2 <= x1 + 1 and y0 - 1 <= (ln.y0 + ln.y1) / 2 <= y1 + 1 for x0, y0, x1, y1 in inner))
            b.items.sort(key=lambda it: (it.y0, it.x0))

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
        if not single and (best_len or any(crosses(it) for it in free)):
            up = [it for it in free if it.y1 <= div_y0 + 3]
            down = [it for it in free if it.y0 >= div_y1 - 3]
            if any(crosses(it) for it in up):
                above = up
            if any(crosses(it) for it in down):
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

    for it in flow:
        if isinstance(it, ImageEl):
            it.png = None
    stats["pages"] = len(pages)
    stats["boxes"] = sum(1 for it in flow if isinstance(it, Box))
    ex = Extraction(pdf_path, pages, flow, icon_digests, body_size, doc, dict(stats), wide_ids=wide_ids)
    ex.header_texts = header_texts
    return ex


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
        gap = f.x0 - prev.x1
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
