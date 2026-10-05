"""IR -> HWPX (한글 COM 없이 순수 XML 생성).

- 스타일은 한글에서 실제로 열어 검증된 v5.23 결과물의 header.xml을 템플릿으로 쓴다.
  검증된 문단 모양(지문 박스 25, <보기> 제목 51/53, 본문 58, 마지막 줄 57, 빈 문단 62, 선택지 41/42 …)을
  그대로 재사용하고, 들여쓰기/정렬 변형만 복제해서 새 id로 추가한다.
- 문단 테두리는 같은 borderFill + connect=1인 문단끼리 하나의 박스로 이어지므로
  박스와 박스 사이, 박스와 선택지 사이에는 항상 테두리 없는 빈 문단을 넣는다(v5.22 교훈).
- 결과는 매번 새로 생성(후처리 패치 없음)하므로 단계별 거부/롤백 문제가 없다.
"""
from __future__ import annotations

import io
import random
import re
import zipfile
from importlib import resources
from typing import Optional
from xml.sax.saxutils import escape

from .masterpage import MARGINS_WITH_MASTER, PAPER_W, Logo, MasterIds, build_masterpage
from .model import AuxBlock, Document, ImageEl, Para, Passage, Question, Run
from .style import DocStyle

PT_TO_HWP = 110  # PDF pt -> HWPUNIT (원본 9.1pt 글자 ≈ 출력 10pt 글자 비율)
DEFAULT_MARGINS = {"header": 1134, "footer": 1134, "left": 2268, "right": 2268, "top": 2268, "bottom": 2268}
COL_GAP = 2268

# 템플릿 문단 모양 id
PP = {
    "guide": 27, "passage": 25, "passage_label": 33, "passage_credit": 56,
    "stem_first": 38, "stem": 43,
    "aux_title": 51, "aux_mid": 58, "aux_last": 57,
    "spacer": 62, "choice": 41, "choice_last": 42,
    "ans_heading": 35, "ans_head": 36, "ans_expl": 37, "plain": 21,
}
# 템플릿 글자 모양 id
CP = {"body": 0, "body_ul": 8, "guide": 7, "bold": 9, "bold_ul": 10}


def _tpl(name: str) -> str:
    return resources.files("pdf2hwpx").joinpath("template", name).read_text(encoding="utf-8")


class Styles:
    def __init__(self, header_xml: str):
        self.header = header_xml
        self.para_xml: dict[int, str] = {}
        for m in re.finditer(r'<hh:paraPr id="(\d+)".*?</hh:paraPr>', header_xml, re.S):
            self.para_xml[int(m.group(1))] = m.group(0)
        self.next_para = max(self.para_xml) + 1
        self.new_paras: list[str] = []
        self.cache: dict[tuple, int] = {}
        self.char_xml: dict[int, str] = {int(m.group(1)): m.group(0) for m in
                                         re.finditer(r'<hh:charPr id="(\d+)".*?</hh:charPr>', header_xml, re.S)}
        self.new_chars: list[str] = []
        self.bf_ids = [int(x) for x in re.findall(r'<hh:borderFill id="(\d+)"', header_xml)]
        self.new_bfs: list[str] = []

    # ---- 글꼴/글자 크기 (템플릿: 글꼴 0 = 제목용 돋움, 1 = 본문용 바탕) ----
    def set_fonts(self, body_font: str, title_font: str) -> None:
        def repl(m: re.Match) -> str:
            fid = m.group(1)
            face = body_font if fid == "1" else title_font if fid == "0" else None
            if face is None:
                return m.group(0)
            return re.sub(r'face="[^"]*"', f'face="{escape(face, {chr(34): "&quot;"})}"', m.group(0), count=1)
        self.header = re.sub(r'<hh:font id="(\d+)" face="[^"]*"', repl, self.header)

    def set_char_height(self, char_ids: list[int], height: int) -> None:
        for cid in char_ids:
            old = self.char_xml[cid]
            new = re.sub(r' height="\d+"', f' height="{height}"', old, count=1)
            self.header = self.header.replace(old, new)
            self.char_xml[cid] = new

    def add_char(self, base: int, height: int, color: str = "#000000", bold: bool = True,
                 font_id: int = 0) -> int:
        x = self.char_xml[base]
        cid = max(self.char_xml) + 1
        x = re.sub(r'<hh:charPr id="\d+"', f'<hh:charPr id="{cid}"', x, count=1)
        x = re.sub(r' height="\d+"', f' height="{height}"', x, count=1)
        x = re.sub(r'textColor="#[0-9A-Fa-f]{6}"', f'textColor="{color}"', x, count=1)
        x = re.sub(r'<hh:fontRef [^>]*/>', '<hh:fontRef ' + " ".join(
            f'{k}="{font_id}"' for k in ("hangul", "latin", "hanja", "japanese", "other", "symbol", "user")) + '/>', x, count=1)
        x = re.sub(r'<hh:underline type="\w+"', '<hh:underline type="NONE"', x, count=1)
        x = x.replace("<hh:bold/>", "")
        if bold:
            x = x.replace("</hh:charPr>", "<hh:bold/></hh:charPr>")
        self.char_xml[cid] = x
        self.new_chars.append(x)
        return cid

    def add_border_fill(self, width: str = "0.12 mm", fill: Optional[str] = None) -> int:
        bid = max(self.bf_ids) + 1
        self.bf_ids.append(bid)
        sides = "".join(f'<hh:{s}Border type="SOLID" width="{width}" color="#000000"/>' for s in ("left", "right", "top", "bottom"))
        brush = (f'<hc:fillBrush><hc:winBrush faceColor="{fill}" hatchColor="#999999" alpha="0"/></hc:fillBrush>'
                 if fill else "")
        self.new_bfs.append(
            f'<hh:borderFill id="{bid}" threeD="0" shadow="0" centerLine="NONE" breakCellSeparateLine="0">'
            '<hh:slash type="NONE" Crooked="0" isCounter="0"/><hh:backSlash type="NONE" Crooked="0" isCounter="0"/>'
            f'{sides}<hh:diagonal type="SOLID" width="0.1 mm" color="#000000"/>{brush}</hh:borderFill>')
        return bid

    def derive(self, base: int, **ov) -> int:
        """템플릿 문단 모양 base를 복제하고 일부 속성만 바꾼 새 id를 돌려준다."""
        if not ov:
            return base
        key = (base, tuple(sorted(ov.items())))
        if key in self.cache:
            return self.cache[key]
        x = self.para_xml[base]
        pid = self.next_para
        self.next_para += 1
        x = re.sub(r'<hh:paraPr id="\d+"', f'<hh:paraPr id="{pid}"', x, count=1)
        if "align" in ov:
            x = re.sub(r'horizontal="\w+"', f'horizontal="{ov["align"]}"', x, count=1)
        for k in ("intent", "left", "right", "prev", "next"):
            if k in ov:
                x = re.sub(rf'<hc:{k} value="-?\d+"', f'<hc:{k} value="{int(ov[k])}"', x)
        if "keep_next" in ov:
            x = re.sub(r'keepWithNext="\d"', f'keepWithNext="{int(ov["keep_next"])}"', x, count=1)
        if "border" in ov:
            bf, ol, orr, ot, ob, conn = ov["border"]
            x = re.sub(r'<hh:border [^>]*/>',
                       f'<hh:border borderFillIDRef="{bf}" offsetLeft="{ol}" offsetRight="{orr}" offsetTop="{ot}" '
                       f'offsetBottom="{ob}" connect="{conn}" ignoreMargin="0"/>', x, count=1)
        if "offset_top" in ov:
            x = re.sub(r'offsetTop="\d+"', f'offsetTop="{int(ov["offset_top"])}"', x, count=1)
        if "offset_bottom" in ov:
            x = re.sub(r'offsetBottom="\d+"', f'offsetBottom="{int(ov["offset_bottom"])}"', x, count=1)
        self.para_xml[pid] = x
        self.new_paras.append(x)
        self.cache[key] = pid
        return pid

    def render_header(self, sec_cnt: int) -> str:
        h = self.header
        if self.new_paras:
            h = h.replace("</hh:paraProperties>", "".join(self.new_paras) + "</hh:paraProperties>")
        if self.new_chars:
            h = h.replace("</hh:charProperties>", "".join(self.new_chars) + "</hh:charProperties>")
        if self.new_bfs:
            h = h.replace("</hh:borderFills>", "".join(self.new_bfs) + "</hh:borderFills>")
        n = len(self.para_xml)
        h = re.sub(r'<hh:paraProperties itemCnt="\d+"', f'<hh:paraProperties itemCnt="{n}"', h)
        h = re.sub(r'<hh:charProperties itemCnt="\d+"', f'<hh:charProperties itemCnt="{len(self.char_xml)}"', h)
        h = re.sub(r'<hh:borderFills itemCnt="\d+"', f'<hh:borderFills itemCnt="{len(self.bf_ids)}"', h)
        h = re.sub(r'secCnt="\d+"', f'secCnt="{sec_cnt}"', h)
        return h


def _indent_hwp(pt: float, lo: int = -3000, hi: int = 3000) -> int:
    v = int(round(pt * PT_TO_HWP / 10.0)) * 10
    return max(lo, min(hi, v))


class HwpxWriter:
    def __init__(self, doc: Document, preview_png: Optional[bytes] = None, style: Optional[DocStyle] = None):
        self.doc = doc
        self.style = (style or DocStyle()).validate()
        self.styles = Styles(_tpl("header.xml"))
        self.images: list[tuple[str, bytes]] = []
        self.preview_png = preview_png
        self._rng = random.Random(20260)
        self.stats = {"aux_boxes": 0, "passage_boxes": 0, "spacers": 0, "pictures": 0, "paragraphs": 0}
        st = self.style
        # 글꼴/크기: 본문 글자 모양(0, 7, 8, 9, 10)은 모두 글꼴 1을 쓴다
        self.styles.set_fonts(st.body_font, st.title_font)
        self.scale = st.body_size / 10.0
        self.styles.set_char_height([CP["body"], CP["body_ul"], CP["guide"], CP["bold"], CP["bold_ul"]],
                                    int(round(st.body_size * 100)))
        self.margins = dict(MARGINS_WITH_MASTER if st.uses_masterpage else DEFAULT_MARGINS)
        col_w = (PAPER_W - self.margins["left"] - self.margins["right"] - COL_GAP) // 2
        self.img_max_in_box = col_w - 3000
        self.img_max_free = col_w - 600
        self.master_ids: Optional[MasterIds] = None
        self.logo: Optional[Logo] = None
        if st.uses_masterpage:
            S = self.styles
            self.master_ids = MasterIds(
                frame_bf=S.add_border_fill(), black_bf=S.add_border_fill(fill="#000000"),
                title_cp=S.add_char(CP["bold"], int(st.title_size * 100), font_id=0),
                academy_cp=S.add_char(CP["bold"], int(st.title_size * 100), color="#FFFFFF", font_id=0),
                center_pp=S.derive(0, align="CENTER"), plain_pp=0, plain_cp=0)
            if st.logo:
                self.logo = self._add_logo(st.logo)

    def _add_logo(self, data: bytes) -> Optional[Logo]:
        try:
            import pymupdf as fitz
            pix = fitz.Pixmap(data)
            png = pix.tobytes("png")
        except Exception:
            return None
        name = f"image{len(self.images) + 1}"
        self.images.append((name, png))
        return Logo(name, pix.width, pix.height)

    def _hang(self, v: int) -> int:
        return int(round(v * self.scale / 10.0)) * 10

    # ------------------------------------------------------------ xml ----
    def _runs_xml(self, runs: list[Run], base_bold: bool = False) -> str:
        out = []
        for r in runs:
            bold = r.bold or base_bold
            if bold:
                cp = CP["bold_ul"] if r.underline else CP["bold"]
            else:
                cp = CP["body_ul"] if r.underline else CP["body"]
            out.append(f'<hp:run charPrIDRef="{cp}"><hp:t>{escape(r.text)}</hp:t></hp:run>')
        return "".join(out) or '<hp:run charPrIDRef="0"><hp:t></hp:t></hp:run>'

    def _p(self, pp: int, inner: str) -> str:
        self.stats["paragraphs"] += 1
        return (f'<hp:p id="0" paraPrIDRef="{pp}" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
                f'{inner}</hp:p>')

    def _empty(self, pp: int) -> str:
        return self._p(pp, '<hp:run charPrIDRef="0"><hp:t></hp:t></hp:run>')

    def _pic(self, img: ImageEl, max_w: int) -> str:
        if img.png is None:
            raise ValueError("image has no PNG data")
        idx = len(self.images) + 1
        name = f"image{idx}"
        self.images.append((name, img.png))
        self.stats["pictures"] += 1
        w = int(img.width * PT_TO_HWP)
        h = int(img.height * PT_TO_HWP)
        if w > max_w:
            h = int(h * max_w / w)
            w = max_w
        w, h = max(w, 200), max(h, 200)
        pid = self._rng.randint(10 ** 9, 2 * 10 ** 9)
        inst = self._rng.randint(10 ** 8, 9 * 10 ** 8)
        return (
            f'<hp:run charPrIDRef="0"><hp:pic id="{pid}" zOrder="{idx}" numberingType="PICTURE" textWrap="TOP_AND_BOTTOM" '
            f'textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" href="" groupLevel="0" instid="{inst}" reverse="0">'
            f'<hp:offset x="0" y="0"/><hp:orgSz width="{w}" height="{h}"/><hp:curSz width="0" height="0"/>'
            f'<hp:flip horizontal="0" vertical="0"/><hp:rotationInfo angle="0" centerX="{w // 2}" centerY="{h // 2}" rotateimage="1"/>'
            f'<hp:renderingInfo><hc:transMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'
            f'<hc:scaMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/><hc:rotMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'
            f'</hp:renderingInfo><hc:img binaryItemIDRef="{name}" bright="0" contrast="0" effect="REAL_PIC" alpha="0"/>'
            f'<hp:imgRect><hc:pt0 x="0" y="0"/><hc:pt1 x="{w}" y="0"/><hc:pt2 x="{w}" y="{h}"/><hc:pt3 x="0" y="{h}"/></hp:imgRect>'
            f'<hp:imgClip left="0" right="0" top="0" bottom="0"/><hp:inMargin left="0" right="0" top="0" bottom="0"/>'
            f'<hp:imgDim dimwidth="0" dimheight="0"/><hp:effects/>'
            f'<hp:sz width="{w}" widthRelTo="ABSOLUTE" height="{h}" heightRelTo="ABSOLUTE" protect="0"/>'
            f'<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" '
            f'horzRelTo="COLUMN" vertAlign="TOP" horzAlign="LEFT" vertOffset="0" horzOffset="0"/>'
            f'<hp:outMargin left="0" right="0" top="0" bottom="0"/><hp:shapeComment>그림입니다.</hp:shapeComment>'
            f'</hp:pic><hp:t/></hp:run>')

    # --------------------------------------------------------- blocks ----
    def _passage(self, ps: Passage) -> list[str]:
        S = self.styles
        out = [self._p(PP["guide"], self._runs_xml(ps.guide.runs, True))] if ps.guide else []
        if ps.boxed:
            self.stats["passage_boxes"] += 1
        for p in ps.paras:
            if ps.boxed:
                base = PP["passage"]
                ov: dict = {}
            else:
                base = PP["passage"]
                ov = {"border": (2, 0, 0, 0, 0, 0)}
            if p.kind == "blank":
                out.append(self._empty(S.derive(base, **ov)))
                continue
            if p.kind == "image":
                out.append(self._p(S.derive(base, align="CENTER", **ov), self._pic(p.image, self.img_max_in_box)))
                continue
            if p.role == "label" and ps.boxed:
                pp = PP["passage_label"]
            elif p.align == "RIGHT":
                pp = S.derive(PP["passage_credit"], **ov) if ov else PP["passage_credit"]
            elif p.align == "CENTER":
                pp = S.derive(base, align="CENTER", **ov)
            elif p.indent_pt:
                pp = S.derive(base, intent=_indent_hwp(p.indent_pt), **ov)
            else:
                pp = S.derive(base, **ov)
            out.append(self._p(pp, self._runs_xml(p.runs)))
        return out

    def _aux(self, blk: AuxBlock, last_in_question: bool) -> list[str]:
        S = self.styles
        out = []
        self.stats["aux_boxes"] += 1
        if blk.title:
            out.append(self._p(PP["aux_title"], self._runs_xml([Run(blk.title)])))
        body = [p for p in blk.paras]
        while body and body[-1].kind == "blank":
            body.pop()
        if not body:
            body = [Para(kind="blank")]
        for i, p in enumerate(body):
            last = i == len(body) - 1
            base = PP["aux_last"] if last else PP["aux_mid"]
            ov: dict = {}
            if i == 0 and not blk.title:
                ov.update(prev=280, offset_top=120)
            if p.kind == "image":
                out.append(self._p(S.derive(base, align="CENTER", intent=0, **ov), self._pic(p.image, self.img_max_in_box)))
                continue
            if p.kind == "blank":
                out.append(self._empty(S.derive(base, **ov)))
                continue
            if p.align in ("RIGHT", "CENTER"):
                ov["align"] = p.align
            elif p.indent_pt:
                ov["intent"] = _indent_hwp(p.indent_pt)
            out.append(self._p(S.derive(base, **ov), self._runs_xml(p.runs)))
        # 박스 아래 테두리가 다음 줄을 침범하지 않도록 실제 빈 문단(테두리 없음)
        out.append(self._empty(S.derive(PP["spacer"], keep_next=0) if last_in_question else PP["spacer"]))
        self.stats["spacers"] += 1
        return out

    def _question(self, q: Question, first_after_passage: bool) -> list[str]:
        S = self.styles
        digits = len(str(q.number))
        hang = self._hang(1400 if digits == 1 else 1950)
        stem_pp = S.derive(PP["stem_first"] if first_after_passage else PP["stem"], intent=-hang)
        out = [self._p(stem_pp, self._runs_xml(q.stem.runs, True))]
        n_blocks = len(q.blocks)
        for i, b in enumerate(q.blocks):
            out.extend(self._block(b, i == n_blocks - 1 and not q.choices and not q.after))
        for i, c in enumerate(q.choices):
            base = PP["choice_last"] if i == len(q.choices) - 1 else PP["choice"]
            if c.extra:  # 출전 줄이 뒤따르면 선택지 문단은 다음 줄과 붙어 있게
                base = PP["choice"]
            out.append(self._p(S.derive(base, left=1100, intent=-self._hang(1430)), self._runs_xml(c.para.runs)))
            for k, x in enumerate(c.extra):
                last_extra = i == len(q.choices) - 1 and k == len(c.extra) - 1
                xb = PP["choice_last"] if last_extra else PP["choice"]
                out.append(self._p(S.derive(xb, align="RIGHT", left=1100, intent=0), self._runs_xml(x.runs)))
        for i, b in enumerate(q.after):
            out.extend(self._block(b, i == len(q.after) - 1))
        return out

    def _block(self, b, last: bool) -> list[str]:
        """문제 안의 보조박스/그림/일반 문단 (선택지 앞이든 뒤든 같은 규칙)."""
        S = self.styles
        if isinstance(b, AuxBlock):
            return self._aux(b, last)
        if b.kind == "image":
            return [self._p(S.derive(PP["choice"], align="CENTER", left=0, intent=0), self._pic(b.image, self.img_max_free))]
        if b.kind == "text":
            ov = {"align": b.align} if b.align in ("RIGHT", "CENTER") else {"intent": _indent_hwp(b.indent_pt)}
            return [self._p(S.derive(PP["choice"], left=0, **ov), self._runs_xml(b.runs))]
        return []

    def _answers(self) -> list[str]:
        S = self.styles
        out = [self._p(PP["ans_heading"], self._runs_xml([Run("[정답 및 해설]", bold=True)]))]
        for a in self.doc.answers:
            out.append(self._p(PP["ans_head"], self._runs_xml(a.head.runs)))
            for p in a.paras:
                if p.kind != "text":
                    continue
                out.append(self._p(S.derive(PP["ans_expl"], left=0, intent=_indent_hwp(p.indent_pt)),
                                   self._runs_xml(p.runs, base_bold=p.role == "heading")))
        return out

    # ---------------------------------------------------------- build ----
    def section_xml(self, paras: list[str], master_id: Optional[str] = None) -> str:
        open_tag = _tpl("section_open.xml")
        secpr = _tpl("secpr.xml")
        m = self.margins
        secpr = re.sub(r'<hp:margin header="\d+" footer="\d+" gutter="0" left="\d+" right="\d+" top="\d+" bottom="\d+"/>',
                       f'<hp:margin header="{m["header"]}" footer="{m["footer"]}" gutter="0" left="{m["left"]}" '
                       f'right="{m["right"]}" top="{m["top"]}" bottom="{m["bottom"]}"/>', secpr, count=1)
        if master_id:
            secpr = secpr.replace('masterPageCnt="0"', 'masterPageCnt="1"')
            secpr = secpr.replace("</hp:secPr>", f'<hp:masterPage idRef="{master_id}"/></hp:secPr>')
        if not paras:
            paras = [self._empty(0)]
        first = paras[0]
        m = re.match(r'(<hp:p [^>]*>)', first)
        head = m.group(1)
        sec_run = f'<hp:run charPrIDRef="0">{secpr}</hp:run>'
        paras = [head + sec_run + first[len(head):]] + paras[1:]
        return open_tag + "".join(paras) + "</hs:sec>"

    def build_sections(self) -> list[str]:
        body: list[str] = []
        prev_passage = False
        for it in self.doc.items:
            if isinstance(it, Passage):
                body.extend(self._passage(it))
                prev_passage = True
            elif isinstance(it, Question):
                body.extend(self._question(it, prev_passage))
                prev_passage = False
            elif isinstance(it, AuxBlock):
                body.extend(self._aux(it, True))
                prev_passage = False
            elif isinstance(it, Para):
                if it.kind == "image":
                    body.append(self._p(PP["plain"], self._pic(it.image, self.img_max_free)))
                elif it.kind == "text":
                    body.append(self._p(PP["plain"], self._runs_xml(it.runs)))
        mp = self.master_ids is not None
        sections = [self.section_xml(body, "masterpage0" if mp else None)]
        if self.doc.answers:
            sections.append(self.section_xml(self._answers(), "masterpage1" if mp else None))
        return sections

    def masterpages(self, n_sections: int) -> list[tuple[str, str]]:
        if self.master_ids is None:
            return []
        return [(f"masterpage{i}", build_masterpage(f"masterpage{i}", self.style, self.master_ids, self.margins, self.logo))
                for i in range(n_sections)]

    def preview_text(self) -> str:
        lines = []
        for it in self.doc.items:
            if isinstance(it, Passage):
                lines.append(it.guide.text if it.guide else "")
                lines.extend(p.text for p in it.paras if p.kind == "text")
            elif isinstance(it, Question):
                lines.append(it.stem.text)
                lines.extend(c.para.text for c in it.choices)
            if sum(len(x) for x in lines) > 1800:
                break
        return "\r\n".join(lines)[:2000]

    def write(self, path: str) -> dict:
        sections = self.build_sections()
        masters = self.masterpages(len(sections))
        header = self.styles.render_header(len(sections))
        manifest_items = ['<opf:item id="header" href="Contents/header.xml" media-type="application/xml"/>']
        spine = ['<opf:itemref idref="header" linear="yes"/>']
        for i in range(len(sections)):
            manifest_items.append(f'<opf:item id="section{i}" href="Contents/section{i}.xml" media-type="application/xml"/>')
            spine.append(f'<opf:itemref idref="section{i}" linear="yes"/>')
        for name, _ in self.images:
            manifest_items.append(f'<opf:item id="{name}" href="BinData/{name}.png" media-type="image/png" isEmbeded="1"/>')
        for mid, _ in masters:
            manifest_items.append(f'<opf:item id="{mid}" href="Contents/{mid}.xml" media-type="application/xml"/>')
        manifest_items.append('<opf:item id="settings" href="settings.xml" media-type="application/xml"/>')
        ns = re.search(r"<hh:head (xmlns[^>]*?) version=", header).group(1)
        content_hpf = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
            f'<opf:package {ns} version="" unique-identifier="" id="">'
            '<opf:metadata><opf:title/><opf:language>ko</opf:language>'
            '<opf:meta name="creator" content="text">pdf2hwpx 0.5</opf:meta></opf:metadata>'
            f'<opf:manifest>{"".join(manifest_items)}</opf:manifest><opf:spine>{"".join(spine)}</opf:spine></opf:package>')
        settings = ('<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><ha:HWPApplicationSetting '
                    'xmlns:ha="http://www.hancom.co.kr/hwpml/2011/app" '
                    'xmlns:config="urn:oasis:names:tc:opendocument:xmlns:config:1.0">'
                    '<ha:CaretPosition listIDRef="0" paraIDRef="0" pos="0"/></ha:HWPApplicationSetting>')
        rdf_parts = ['<rdf:Description rdf:about=""><ns0:hasPart xmlns:ns0="http://www.hancom.co.kr/hwpml/2016/meta/pkg#" '
                     'rdf:resource="Contents/header.xml"/></rdf:Description><rdf:Description rdf:about="Contents/header.xml">'
                     '<rdf:type rdf:resource="http://www.hancom.co.kr/hwpml/2016/meta/pkg#HeaderFile"/></rdf:Description>']
        for i in range(len(sections)):
            rdf_parts.append(
                f'<rdf:Description rdf:about=""><ns0:hasPart xmlns:ns0="http://www.hancom.co.kr/hwpml/2016/meta/pkg#" '
                f'rdf:resource="Contents/section{i}.xml"/></rdf:Description><rdf:Description rdf:about="Contents/section{i}.xml">'
                f'<rdf:type rdf:resource="http://www.hancom.co.kr/hwpml/2016/meta/pkg#SectionFile"/></rdf:Description>')
        rdf = ('<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
               + "".join(rdf_parts) +
               '<rdf:Description rdf:about=""><rdf:type rdf:resource="http://www.hancom.co.kr/hwpml/2016/meta/pkg#Document"/>'
               '</rdf:Description></rdf:RDF>')

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr(zipfile.ZipInfo("mimetype"), "application/hwp+zip", compress_type=zipfile.ZIP_STORED)
            z.writestr("version.xml", _tpl("version.xml"), compress_type=zipfile.ZIP_STORED)
            z.writestr("Contents/header.xml", header, compress_type=zipfile.ZIP_DEFLATED)
            for name, data in self.images:
                z.writestr(f"BinData/{name}.png", data, compress_type=zipfile.ZIP_STORED)
            for mid, mx in masters:
                z.writestr(f"Contents/{mid}.xml", mx, compress_type=zipfile.ZIP_DEFLATED)
            for i, s in enumerate(sections):
                z.writestr(f"Contents/section{i}.xml", s, compress_type=zipfile.ZIP_DEFLATED)
            z.writestr("settings.xml", settings, compress_type=zipfile.ZIP_DEFLATED)
            z.writestr("Preview/PrvText.txt", self.preview_text(), compress_type=zipfile.ZIP_DEFLATED)
            if self.preview_png:
                z.writestr("Preview/PrvImage.png", self.preview_png, compress_type=zipfile.ZIP_STORED)
            z.writestr("META-INF/container.xml", _tpl("meta_container.xml"), compress_type=zipfile.ZIP_DEFLATED)
            z.writestr("Contents/content.hpf", content_hpf, compress_type=zipfile.ZIP_DEFLATED)
            z.writestr("META-INF/manifest.xml", _tpl("meta_manifest.xml"), compress_type=zipfile.ZIP_DEFLATED)
            z.writestr("META-INF/container.rdf", rdf, compress_type=zipfile.ZIP_DEFLATED)
        with open(path, "wb") as f:
            f.write(buf.getvalue())
        return dict(self.stats, sections=len(sections), new_para_styles=len(self.styles.new_paras),
                    masterpages=len(masters), style=self.style.summary())
