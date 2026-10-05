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

from .model import AuxBlock, Document, ImageEl, Para, Passage, Question, Run

PT_TO_HWP = 110  # PDF pt -> HWPUNIT (원본 9.1pt 글자 ≈ 출력 10pt 글자 비율)
COL_WIDTH = 26362  # A4, 여백 2268, 단 간격 2268 기준 단 폭(HWPUNIT)
IMG_MAX_IN_BOX = COL_WIDTH - 3000
IMG_MAX_FREE = COL_WIDTH - 600

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
        n = len(self.para_xml)
        h = re.sub(r'<hh:paraProperties itemCnt="\d+"', f'<hh:paraProperties itemCnt="{n}"', h)
        h = re.sub(r'secCnt="\d+"', f'secCnt="{sec_cnt}"', h)
        return h


def _indent_hwp(pt: float, lo: int = -3000, hi: int = 3000) -> int:
    v = int(round(pt * PT_TO_HWP / 10.0)) * 10
    return max(lo, min(hi, v))


class HwpxWriter:
    def __init__(self, doc: Document, preview_png: Optional[bytes] = None):
        self.doc = doc
        self.styles = Styles(_tpl("header.xml"))
        self.images: list[tuple[str, bytes]] = []
        self.preview_png = preview_png
        self._rng = random.Random(20260)
        self.stats = {"aux_boxes": 0, "passage_boxes": 0, "spacers": 0, "pictures": 0, "paragraphs": 0}

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
                out.append(self._p(S.derive(base, align="CENTER", **ov), self._pic(p.image, IMG_MAX_IN_BOX)))
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
                out.append(self._p(S.derive(base, align="CENTER", intent=0, **ov), self._pic(p.image, IMG_MAX_IN_BOX)))
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
        hang = 1400 if digits == 1 else 1950
        stem_pp = S.derive(PP["stem_first"] if first_after_passage else PP["stem"], intent=-hang)
        out = [self._p(stem_pp, self._runs_xml(q.stem.runs, True))]
        n_blocks = len(q.blocks)
        for i, b in enumerate(q.blocks):
            last = i == n_blocks - 1 and not q.choices
            if isinstance(b, AuxBlock):
                out.extend(self._aux(b, last))
            elif b.kind == "image":
                out.append(self._p(S.derive(PP["choice"], align="CENTER", left=0, intent=0), self._pic(b.image, IMG_MAX_FREE)))
            elif b.kind == "text":
                out.append(self._p(S.derive(PP["choice"], left=0, intent=0), self._runs_xml(b.runs)))
        for i, c in enumerate(q.choices):
            base = PP["choice_last"] if i == len(q.choices) - 1 else PP["choice"]
            out.append(self._p(S.derive(base, left=1100, intent=-1430), self._runs_xml(c.para.runs)))
        for p in q.after:
            out.append(self._p(PP["plain"], self._runs_xml(p.runs)))
        return out

    def _answers(self) -> list[str]:
        S = self.styles
        out = [self._p(PP["ans_heading"], self._runs_xml([Run("[정답 및 해설]", bold=True)]))]
        for a in self.doc.answers:
            out.append(self._p(PP["ans_head"], self._runs_xml(a.head.runs)))
            for p in a.paras:
                if p.kind != "text":
                    continue
                out.append(self._p(S.derive(PP["ans_expl"], left=0, intent=_indent_hwp(p.indent_pt)), self._runs_xml(p.runs)))
        return out

    # ---------------------------------------------------------- build ----
    def section_xml(self, paras: list[str]) -> str:
        open_tag = _tpl("section_open.xml")
        secpr = _tpl("secpr.xml")
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
            elif isinstance(it, Para):
                if it.kind == "image":
                    body.append(self._p(PP["plain"], self._pic(it.image, IMG_MAX_FREE)))
                elif it.kind == "text":
                    body.append(self._p(PP["plain"], self._runs_xml(it.runs)))
        sections = [self.section_xml(body)]
        if self.doc.answers:
            sections.append(self.section_xml(self._answers()))
        return sections

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
        header = self.styles.render_header(len(sections))
        manifest_items = ['<opf:item id="header" href="Contents/header.xml" media-type="application/xml"/>']
        spine = ['<opf:itemref idref="header" linear="yes"/>']
        for i in range(len(sections)):
            manifest_items.append(f'<opf:item id="section{i}" href="Contents/section{i}.xml" media-type="application/xml"/>')
            spine.append(f'<opf:itemref idref="section{i}" linear="yes"/>')
        for name, _ in self.images:
            manifest_items.append(f'<opf:item id="{name}" href="BinData/{name}.png" media-type="image/png" isEmbeded="1"/>')
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
        return dict(self.stats, sections=len(sections), new_para_styles=len(self.styles.new_paras))
