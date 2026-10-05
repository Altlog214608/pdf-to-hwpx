"""PDF -> 페이지 모델.

PDF를 한 번만 읽어서 다음을 만든다.
- 줄(Line): 글자 좌표 기반. 텍스트 레이어에 공백 글자가 없어도 글자 간격으로 띄어쓰기를 복원하고,
  줄 끝 공백 여부(trailing_space)를 보존한다.
- 원문자 아이콘(①~⑤ 이미지)은 사설 영역 문자로 줄 안에 끼워 넣는다 (나중에 숫자로 판별).
- 박스(Box): 문단 테두리가 줄 단위 선분으로 그려지므로 세로 선분을 이어 붙여 사각형을 복원한다.
- 밑줄: 글자 아래 가로 선분.
- 머리글/바닥글/배너/숨은 글자 제거, 2단 분리, 읽기 순서(페이지 -> 왼쪽 단 -> 오른쪽 단 -> 위에서 아래).
"""
from __future__ import annotations

import re
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Optional

import pymupdf as fitz

from .model import Box, FlowItem, Glyph, ICON_PUA_BASE, ImageEl, Line, PageInfo

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

def _is_bold(font: str, flags: int) -> bool:
    return "bold" in font.lower() or bool(flags & 16)


def _page_fragments(page: fitz.Page) -> list[_Frag]:
    frags: list[_Frag] = []
    raw = page.get_text("rawdict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
    for block in raw.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            glyphs: list[Glyph] = []
            for span in line.get("spans", []):
                size = float(span.get("size") or 0)
                if size < HIDDEN_TEXT_MAX_SIZE:
                    continue
                bold = _is_bold(span.get("font", ""), int(span.get("flags") or 0))
                for ch in span.get("chars", []):
                    c = ch.get("c") or ""
                    if not c:
                        continue
                    x0, y0, x1, y1 = ch["bbox"]
                    if c == " ":
                        c = " "
                    glyphs.append(Glyph(c, x0, y0, x1, y1, size, bold))
            if not glyphs or all(g.is_space for g in glyphs):
                continue
            solid = [g for g in glyphs if not g.is_space]
            frags.append(_Frag(glyphs, min(g.x0 for g in solid), min(g.y0 for g in solid),
                               max(g.x1 for g in solid), max(g.y1 for g in solid),
                               statistics.median(g.size for g in solid)))
    return frags


def _page_segments(page: fitz.Page) -> tuple[list[_Seg], int]:
    segs: list[_Seg] = []
    others = []
    for d in page.get_drawings():
        w = float(d.get("width") or 0.0)
        for it in d.get("items", []):
            op = it[0]
            if op == "l":
                p1, p2 = it[1], it[2]
                segs.append(_Seg(min(p1.x, p2.x), min(p1.y, p2.y), max(p1.x, p2.x), max(p1.y, p2.y), w))
            elif op == "re":
                r = it[1]
                if r.width < 1.5 or r.height < 1.5:  # 얇은 사각형 = 선
                    segs.append(_Seg(r.x0, r.y0, r.x1, r.y1, w))
                else:
                    for a, b in ((r.tl, r.tr), (r.bl, r.br), (r.tl, r.bl), (r.tr, r.br)):
                        segs.append(_Seg(min(a.x, b.x), min(a.y, b.y), max(a.x, b.x), max(a.y, b.y), w))
                    others.append(r)
            elif op == "qu":
                q = it[1]
                r = q.rect
                for a, b in ((r.tl, r.tr), (r.bl, r.br), (r.tl, r.bl), (r.tr, r.br)):
                    segs.append(_Seg(min(a.x, b.x), min(a.y, b.y), max(a.x, b.x), max(a.y, b.y), w))
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
        raw_pages.append((pno, W, H, frags, segs, others, imgs, top, bottom))

    repeat_min = max(2, int(0.4 * len(raw_pages)))
    # 문제 번호("3.")처럼 짧은 숫자 조각은 반복돼도 머리글이 아니다.
    repeated = {k for k, n in band_texts.items() if n >= repeat_min and len(re.sub(r"[#\W]", "", k[0])) >= 3
                and not k[0].startswith("※")}

    pages: list[PageModel] = []
    icon_digests: dict[str, str] = {}
    all_sizes: list[float] = []
    stats = Counter()

    for pno, W, H, frags, segs, others, imgs, top, bottom in raw_pages:
        # ---- 단 분리선 ----
        content_h = max(1.0, bottom - top)
        split_x = W / 2
        best_len = 0.0
        for s in segs:
            if s.vertical and 0.35 * W <= s.x0 <= 0.65 * W:
                ln = min(s.y1, bottom) - max(s.y0, top)
                if ln >= 0.4 * content_h and ln > best_len:
                    best_len, split_x = ln, s.x0

        # ---- 글자 조각 필터 ----
        kept: list[_Frag] = []
        for f in frags:
            txt = "".join(g.c for g in f.glyphs).strip()
            if f.cy <= top or f.cy >= bottom:
                stats["dropped_band_text"] += 1
                continue
            if (f.y1 <= 0.12 * H or f.y0 >= 0.88 * H) and (_repeat_key(f) in repeated or re.fullmatch(r"-\s*\d+\s*-", txt)):
                stats["dropped_repeated_text"] += 1
                continue
            kept.append(f)

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

        # ---- 단별 줄 만들기 ----
        lines: list[Line] = []
        for col in (0, 1):
            cf = [f for f in kept if (0 if (f.x0 + f.x1) / 2 < split_x else 1) == col]
            cf.sort(key=lambda f: (f.cy, f.x0))
            groups: list[list[_Frag]] = []
            for f in cf:
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
            for g in groups:
                for sub in _split_far_fragments(g):
                    lines.append(_build_line(pno, col, sub))
        for ln in lines:
            all_sizes.extend(gl.size for gl in ln.glyphs if not gl.is_space and not gl.icon)

        # ---- 박스 ----
        box_rects = _detect_boxes(segs, top, bottom)
        # 다른 박스 안에 들어 있는 사각형(도식의 칸 등)은 박스가 아니라 바깥 박스의 내부 도형으로 센다
        nested_in: dict[int, int] = {}
        for i, (x0, y0, x1, y1) in enumerate(box_rects):
            for j, (X0, Y0, X1, Y1) in enumerate(box_rects):
                if i != j and x0 >= X0 - 1 and x1 <= X1 + 1 and y0 >= Y0 - 1 and y1 <= Y1 + 1 \
                        and (x1 - x0) * (y1 - y0) < (X1 - X0) * (Y1 - Y0):
                    nested_in[i] = j
                    break
        boxes: list[Box] = []
        for i, (x0, y0, x1, y1) in enumerate(box_rects):
            if i in nested_in:
                continue
            col = 0 if (x0 + x1) / 2 < split_x else 1
            boxes.append(Box(id=pno * 1000 + i, page=pno, col=col, x0=x0, y0=y0, x1=x1, y1=y1))
        nested_rects = [box_rects[i] for i in nested_in]

        def _box_of(cx: float, cy: float) -> Optional[Box]:
            best = None
            for b in boxes:
                if b.x0 - 2 <= cx <= b.x1 + 2 and b.y0 - 2 <= cy <= b.y1 + 2:
                    if best is None or (b.x1 - b.x0) * (b.y1 - b.y0) < (best.x1 - best.x0) * (best.y1 - best.y0):
                        best = b
            return best

        # ---- 밑줄 ----
        edge_h = []
        for b in boxes:
            edge_h.append((b.y0, b.x0, b.x1))
            edge_h.append((b.y1, b.x0, b.x1))
        underline_segs = []
        for s in segs:
            if not s.horizontal or s.x1 - s.x0 >= 0.6 * W:
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

        # ---- 박스 소속 + 내부 도형 수 ----
        for ln in lines:
            b = _box_of((ln.x0 + ln.x1) / 2, (ln.y0 + ln.y1) / 2)
            if b:
                ln.box = b.id
                b.items.append(ln)
        for im in content_imgs:
            b = _box_of((im.x0 + im.x1) / 2, (im.y0 + im.y1) / 2)
            if b and im.x0 >= b.x0 - 3 and im.x1 <= b.x1 + 3:
                im.box = b.id
                b.items.append(im)
        for b in boxes:
            n = 0
            for k, s in enumerate(underline_segs):
                if k in used_underlines:
                    continue
                if b.x0 + 2 < s.x0 and s.x1 < b.x1 - 2 and b.y0 + 2 < s.y0 < b.y1 - 2:
                    n += 1
            for s in segs:
                if s.vertical and b.x0 + 3 < s.x0 < b.x1 - 3 and b.y0 - 1 <= s.y0 and s.y1 <= b.y1 + 1:
                    n += 1
            for r in others:
                if b.x0 + 2 < r.x0 and r.x1 < b.x1 - 2 and b.y0 + 2 < r.y0 and r.y1 < b.y1 - 2:
                    n += 1
            for (x0, y0, x1, y1) in nested_rects:
                if b.x0 - 1 <= x0 and x1 <= b.x1 + 1 and b.y0 - 1 <= y0 and y1 <= b.y1 + 1:
                    n += 4
            b.inner_drawings = n
            b.items.sort(key=lambda it: (it.y0, it.x0))

        # ---- 단 경계 ----
        def _col_bounds(col: int) -> tuple[float, float]:
            ls = [ln for ln in lines if ln.col == col and len(ln.glyphs) >= 12]
            if not ls:
                return ((36.0, split_x - 14) if col == 0 else (split_x + 14, W - 36))
            xs0 = sorted(ln.x0 for ln in ls)
            xs1 = sorted(ln.x1 for ln in ls)
            return xs0[0], xs1[int(0.9 * (len(xs1) - 1))]

        info = PageInfo(pno, W, H, split_x, top, bottom, _col_bounds(0), _col_bounds(1))

        # ---- 읽기 순서 ----
        flow: list[FlowItem] = []
        for col in (0, 1):
            items: list = [b for b in boxes if b.col == col]
            items += [ln for ln in lines if ln.col == col and ln.box is None]
            items += [im for im in content_imgs if im.col == col and im.box is None]
            items.sort(key=lambda it: (it.y0, it.x0))
            flow.extend(items)
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
                if (last.page, last.col) != (it.page, it.col) \
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
    return Extraction(pdf_path, pages, flow, icon_digests, body_size, doc, dict(stats))


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
    for f in frags[1:]:
        prev = out[-1][-1]
        first = next((g for g in f.glyphs if not g.is_space), None)
        starts_marker = first is not None and (first.icon is not None or first.c in "①②③④⑤⑥⑦⑧⑨⑩")
        if f.x0 - prev.x1 > 3.0 * max(f.size, prev.size) and not starts_marker:
            out.append([f])
        else:
            out[-1].append(f)
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
        if prev_solid is not None and out and not out[-1].is_space:
            gap = g.x0 - prev_solid.x1
            size_jump = max(g.size, prev_solid.size) > 1.2 * min(g.size, prev_solid.size) and not (g.icon or prev_solid.icon)
            if gap > GAP_SPACE_RATIO * max(g.size, prev_solid.size) * (1.0 if not (g.icon or prev_solid.icon) else 0.9) \
                    or (size_jump and gap > 0.8):
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
