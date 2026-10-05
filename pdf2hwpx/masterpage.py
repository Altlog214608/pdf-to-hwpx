"""바탕쪽(masterpage) 생성: 학원 이름/로고, 제목, 페이지 바깥 테두리.

사용자가 한글에서 직접 만든 시험지와 같은 방식이다. 바탕쪽에 '글 뒤로' 배치한 표 하나가 페이지를 덮는다.
  ┌──────────┬──────────────────────────────┐  ← 1행: [검은 칸: 로고 또는 학원 이름][제목]
  ├──────────┴──────────────────────────────┤
  │                                         │  ← 2행: 본문을 둘러싸는 큰 칸(바깥 테두리)
  └─────────────────────────────────────────┘
바탕쪽은 모든 페이지에 반복되고, 본문을 편집해도 움직이지 않는다.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional
from xml.sax.saxutils import escape

from .style import DocStyle

# 한글에서 만든 원본 시험지(A4)의 수치(HWPUNIT, 1mm ≈ 283.5)
PAPER_W, PAPER_H = 59528, 84186
TABLE_W, TABLE_H = 54599, 75791
HEAD_H = 2782
MARGINS_WITH_MASTER = {"header": 4251, "footer": 4251, "left": 4251, "right": 4251, "top": 4251, "bottom": 2834}

NS = ('xmlns:ha="http://www.hancom.co.kr/hwpml/2011/app" xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph" '
      'xmlns:hp10="http://www.hancom.co.kr/hwpml/2016/paragraph" xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
      'xmlns:hc="http://www.hancom.co.kr/hwpml/2011/core" xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head" '
      'xmlns:hhs="http://www.hancom.co.kr/hwpml/2011/history" xmlns:hm="http://www.hancom.co.kr/hwpml/2011/master-page" '
      'xmlns:hpf="http://www.hancom.co.kr/schema/2011/hpf" xmlns:dc="http://purl.org/dc/elements/1.1/" '
      'xmlns:opf="http://www.idpf.org/2007/opf/" xmlns:ooxmlchart="http://www.hancom.co.kr/hwpml/2016/ooxmlchart" '
      'xmlns:hwpunitchar="http://www.hancom.co.kr/hwpml/2016/HwpUnitChar" xmlns:epub="http://www.idpf.org/2007/ops" '
      'xmlns:config="urn:oasis:names:tc:opendocument:xmlns:config:1.0"')


@dataclass
class MasterIds:
    frame_bf: int      # 테두리만 있는 칸
    black_bf: int      # 검은 바탕 칸
    title_cp: int      # 제목 글자
    academy_cp: int    # 흰 학원 이름 글자
    center_pp: int     # 가운데 정렬 문단
    plain_pp: int = 0
    plain_cp: int = 0


@dataclass
class Logo:
    item_id: str
    px_w: int
    px_h: int


def text_width(margins: dict) -> int:
    return PAPER_W - margins["left"] - margins["right"]


def _p(pp: int, inner: str) -> str:
    return (f'<hp:p id="2147483648" paraPrIDRef="{pp}" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
            f'{inner}</hp:p>')


def _cell(col: int, row: int, w: int, h: int, bf: int, paras: str, colspan: int = 1) -> str:
    return (f'<hp:tc name="" header="0" hasMargin="0" protect="0" editable="0" dirty="0" borderFillIDRef="{bf}">'
            f'<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="CENTER" linkListIDRef="0" '
            f'linkListNextIDRef="0" textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">{paras}</hp:subList>'
            f'<hp:cellAddr colAddr="{col}" rowAddr="{row}"/><hp:cellSpan colSpan="{colspan}" rowSpan="1"/>'
            f'<hp:cellSz width="{w}" height="{h}"/><hp:cellMargin left="141" right="141" top="141" bottom="141"/></hp:tc>')


def _logo_pic(logo: Logo, max_w: int, max_h: int, rng: random.Random) -> str:
    h = max_h
    w = int(h * logo.px_w / max(1, logo.px_h))
    if w > max_w:
        w = max_w
        h = int(w * logo.px_h / max(1, logo.px_w))
    pid, inst = rng.randint(10 ** 9, 2 * 10 ** 9), rng.randint(10 ** 8, 9 * 10 ** 8)
    return (f'<hp:pic id="{pid}" zOrder="1" numberingType="PICTURE" textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" '
            f'lock="0" dropcapstyle="None" href="" groupLevel="0" instid="{inst}" reverse="0"><hp:offset x="0" y="0"/>'
            f'<hp:orgSz width="{w}" height="{h}"/><hp:curSz width="0" height="0"/><hp:flip horizontal="0" vertical="0"/>'
            f'<hp:rotationInfo angle="0" centerX="{w // 2}" centerY="{h // 2}" rotateimage="1"/><hp:renderingInfo>'
            f'<hc:transMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/><hc:scaMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'
            f'<hc:rotMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/></hp:renderingInfo>'
            f'<hc:img binaryItemIDRef="{logo.item_id}" bright="0" contrast="0" effect="REAL_PIC" alpha="0"/>'
            f'<hp:imgRect><hc:pt0 x="0" y="0"/><hc:pt1 x="{w}" y="0"/><hc:pt2 x="{w}" y="{h}"/><hc:pt3 x="0" y="{h}"/></hp:imgRect>'
            f'<hp:imgClip left="0" right="0" top="0" bottom="0"/><hp:inMargin left="0" right="0" top="0" bottom="0"/>'
            f'<hp:imgDim dimwidth="0" dimheight="0"/><hp:effects/>'
            f'<hp:sz width="{w}" widthRelTo="ABSOLUTE" height="{h}" heightRelTo="ABSOLUTE" protect="0"/>'
            f'<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" holdAnchorAndSO="0" '
            f'vertRelTo="PARA" horzRelTo="COLUMN" vertAlign="TOP" horzAlign="LEFT" vertOffset="0" horzOffset="0"/>'
            f'<hp:outMargin left="0" right="0" top="0" bottom="0"/><hp:shapeComment>학원 로고</hp:shapeComment></hp:pic>')


def academy_cell_width(style: DocStyle, logo: Optional[Logo]) -> int:
    if logo:
        w = int((HEAD_H - 600) * logo.px_w / max(1, logo.px_h)) + 900
    else:
        w = int(len(style.academy_name) * style.title_size * 100 * 0.98) + 1600
    return max(6000, min(20000, w))


def build_masterpage(page_id: str, style: DocStyle, ids: MasterIds, margins: dict,
                     logo: Optional[Logo], seed: int = 7) -> str:
    rng = random.Random(seed)
    has_academy = bool(logo or style.academy_name)
    has_title = bool(style.title)
    head = has_academy or has_title
    rows = []
    row_idx = 0
    if head:
        cells = []
        col = 0
        aw = academy_cell_width(style, logo) if has_academy else 0
        if has_academy:
            if logo:
                inner = _p(ids.center_pp, f'<hp:run charPrIDRef="{ids.academy_cp}">'
                                          f'{_logo_pic(logo, aw - 600, HEAD_H - 600, rng)}<hp:t/></hp:run>')
            else:
                inner = _p(ids.center_pp, f'<hp:run charPrIDRef="{ids.academy_cp}"><hp:t>{escape(style.academy_name)}</hp:t></hp:run>')
            cells.append(_cell(col, 0, aw if has_title else TABLE_W, HEAD_H, ids.black_bf, inner))
            col += 1
        if has_title:
            inner = _p(ids.center_pp, f'<hp:run charPrIDRef="{ids.title_cp}"><hp:t>{escape(style.title)}</hp:t></hp:run>')
            cells.append(_cell(col, 0, TABLE_W - aw, HEAD_H, ids.frame_bf, inner))
            col += 1
        rows.append((cells, col))
        row_idx = 1
    ncols = rows[0][1] if rows else 1
    if style.frame:
        body_h = TABLE_H - (HEAD_H if head else 0)
        rows.append(([_cell(0, row_idx, TABLE_W, body_h, ids.frame_bf,
                            _p(ids.plain_pp, f'<hp:run charPrIDRef="{ids.plain_cp}"/>'), colspan=ncols)], ncols))
    total_h = (HEAD_H if head else 0) + (TABLE_H - (HEAD_H if head else 0) if style.frame else 0)
    if style.frame:
        pos = ('vertRelTo="PAPER" horzRelTo="COLUMN" vertAlign="CENTER" horzAlign="CENTER" vertOffset="0" horzOffset="0"')
    else:  # 테두리 없이 머리 칸만: 테두리가 있을 때와 같은 높이에 둔다
        top = (PAPER_H - TABLE_H) // 2
        pos = (f'vertRelTo="PAPER" horzRelTo="COLUMN" vertAlign="TOP" horzAlign="CENTER" vertOffset="{top}" horzOffset="0"')
    tr = "".join(f'<hp:tr>{"".join(cells)}</hp:tr>' for cells, _ in rows)
    tid = rng.randint(10 ** 9, 2 * 10 ** 9)
    tbl = (f'<hp:tbl id="{tid}" zOrder="0" numberingType="TABLE" textWrap="BEHIND_TEXT" textFlow="BOTH_SIDES" lock="0" '
           f'dropcapstyle="None" pageBreak="CELL" repeatHeader="1" rowCnt="{len(rows)}" colCnt="{ncols}" cellSpacing="0" '
           f'borderFillIDRef="{ids.frame_bf}" noAdjust="0">'
           f'<hp:sz width="{TABLE_W}" widthRelTo="ABSOLUTE" height="{total_h}" heightRelTo="ABSOLUTE" protect="0"/>'
           f'<hp:pos treatAsChar="0" affectLSpacing="0" flowWithText="1" allowOverlap="0" holdAnchorAndSO="0" {pos}/>'
           f'<hp:outMargin left="283" right="283" top="283" bottom="283"/><hp:inMargin left="141" right="141" top="141" bottom="141"/>'
           f'{tr}</hp:tbl>')
    anchor = _p(ids.plain_pp, f'<hp:run charPrIDRef="{ids.plain_cp}">{tbl}<hp:t/></hp:run>')
    tw = text_width(margins)
    th = PAPER_H - margins["top"] - margins["bottom"] - margins["header"] - margins["footer"]
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
            f'<masterPage {NS} id="{page_id}" type="BOTH" pageNumber="0" pageDuplicate="0" pageFront="0">'
            f'<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="TOP" linkListIDRef="0" '
            f'linkListNextIDRef="0" textWidth="{tw}" textHeight="{th}" hasTextRef="0" hasNumRef="0">'
            f'{anchor}'
            '</hp:subList></masterPage>')
