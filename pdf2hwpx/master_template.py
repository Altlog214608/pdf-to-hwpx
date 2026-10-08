"""내 한글 파일(HWPX)의 바탕쪽을 가져와 변환 결과에 그대로 쓰기.

선생님이 한글에서 직접 만든 시험지 바탕쪽(학원 이름 칸, 제목 칸, 바깥 테두리, 산돌 등에서 내려받은 글꼴)을 그대로 쓰려고,
바탕쪽 XML과 그것이 쓰는 글자 모양·문단 모양·테두리/배경·탭·글꼴·그림만 뽑아 작은 묶음(JSON)으로 만든다.
본문(문제 내용)은 가져오지 않는다. 변환할 때는 묶음의 id를 결과 파일 header.xml의 새 id로 바꿔 끼우고,
제목 칸(바탕쪽에서 가장 긴 글자 문단)의 글자만 새 제목으로 바꾼다.
"""
from __future__ import annotations

import base64
import io
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from typing import Optional
from xml.sax.saxutils import escape

LANGS = {"hangul": "HANGUL", "latin": "LATIN", "hanja": "HANJA", "japanese": "JAPANESE", "other": "OTHER",
         "symbol": "SYMBOL", "user": "USER"}
NS_DECL = ('xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph" xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head" '
           'xmlns:hc="http://www.hancom.co.kr/hwpml/2011/core" xmlns:hp10="http://www.hancom.co.kr/hwpml/2016/paragraph" '
           'xmlns:hm="http://www.hancom.co.kr/hwpml/2011/master-page" xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
           'xmlns:ha="http://www.hancom.co.kr/hwpml/2011/app" xmlns:hhs="http://www.hancom.co.kr/hwpml/2011/history" '
           'xmlns:hpf="http://www.hancom.co.kr/schema/2011/hpf" xmlns:dc="http://purl.org/dc/elements/1.1/" '
           'xmlns:opf="http://www.idpf.org/2007/opf/" xmlns:ooxmlchart="http://www.hancom.co.kr/hwpml/2016/ooxmlchart" '
           'xmlns:hwpunitchar="http://www.hancom.co.kr/hwpml/2016/HwpUnitChar" xmlns:epub="http://www.idpf.org/2007/ops" '
           'xmlns:config="urn:oasis:names:tc:opendocument:xmlns:config:1.0"')
HP = "{http://www.hancom.co.kr/hwpml/2011/paragraph}"
MAX_PACKAGE = 400_000      # 묶음(JSON) 크기 상한
MAX_IMAGES = 2_000_000     # 바탕쪽 그림(로고 등) 합계 상한


class TemplateError(ValueError):
    """사용자에게 그대로 보여 줄 수 있는 설명을 담는다."""


def _block(xml: str, tag: str, ident: str) -> Optional[str]:
    """id 가 ident 인 hh:tag 요소 하나(빈 요소 <…/> 이든 <…>…</…> 이든)."""
    m = re.search(rf'<hh:{tag} id="{re.escape(ident)}"(?:\s[^>]*)?>', xml)
    if not m:
        return None
    if m.group(0).endswith("/>"):
        return m.group(0)
    end = xml.find(f"</hh:{tag}>", m.end())
    return xml[m.start():end + len(f"</hh:{tag}>")] if end >= 0 else None


def _parse_fragment(xml: str) -> ET.Element:
    return ET.fromstring(f"<root {NS_DECL}>{xml}</root>")


def _p_texts(inner: str) -> list[str]:
    """바탕쪽의 문단(hp:p)마다 그 문단에 바로 든 글자(표 안 문단은 따로)."""
    root = _parse_fragment(inner)
    out = []
    for p in root.iter(f"{HP}p"):
        out.append("".join("".join(t.itertext()) for r in p.findall(f"{HP}run") for t in r.findall(f"{HP}t")))
    return out


def _p_span(inner: str, index: int) -> Optional[tuple[int, int]]:
    """index 번째 hp:p 의 문자열 위치(안에 다른 문단이 없을 때만)."""
    starts = [m.start() for m in re.finditer(r"<hp:p[ >]", inner)]
    if not 0 <= index < len(starts):
        return None
    a = starts[index]
    b = inner.find("</hp:p>", a)
    if b < 0 or re.search(r"<hp:p[ >]", inner[a + 5:b]):
        return None
    return a, b + len("</hp:p>")


def extract_template(data: bytes) -> dict:
    """HWPX 바이트 -> 바탕쪽 묶음(dict, JSON으로 주고받음)."""
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
        names = z.namelist()
        header = z.read("Contents/header.xml").decode("utf-8")
    except Exception:
        raise TemplateError("한글(HWPX) 파일이 아닙니다. 한글에서 '다른 이름으로 저장 → HWPX'로 저장한 파일을 골라 주세요.")
    secs = sorted((n for n in names if re.fullmatch(r"Contents/section\d+\.xml", n)),
                  key=lambda n: int(re.search(r"\d+", n.rsplit("/", 1)[1]).group()))
    mp_id = secpr = None
    for s in secs:
        m = re.search(r"<hp:secPr\b.*?</hp:secPr>", z.read(s).decode("utf-8"), re.S)
        r = re.search(r'<hp:masterPage idRef="([^"]+)"', m.group(0)) if m else None
        if r:
            mp_id, secpr = r.group(1), m.group(0)
            break
    if mp_id is None:
        raise TemplateError("이 파일에는 바탕쪽이 없습니다. 한글에서 바탕쪽(쪽 → 바탕쪽)을 만든 시험지 파일을 골라 주세요.")
    mp_xml = None
    for n in names:
        if re.fullmatch(r"Contents/masterpage\d+\.xml", n):
            x = z.read(n).decode("utf-8")
            if re.search(rf'<masterPage\b[^>]*\bid="{re.escape(mp_id)}"', x):
                mp_xml = x
                break
    if mp_xml is None:
        raise TemplateError("바탕쪽 파일을 찾지 못했습니다.")
    root_tag = re.search(r"<masterPage\b[^>]*>", mp_xml).group(0)
    attrs = " ".join(f'{k}="{v}"' for k, v in re.findall(r'\b(type|pageNumber|pageDuplicate|pageFront)="([^"]*)"', root_tag))
    inner = mp_xml[mp_xml.index(">", mp_xml.index("<masterPage")) + 1: mp_xml.rindex("</masterPage>")]
    inner = re.sub(r"<hp:linesegarray>.*?</hp:linesegarray>", "", inner, flags=re.S)  # 줄 배치 캐시(한글이 다시 계산)

    # ---- 바탕쪽이 쓰는 모양들 ----
    chars = {i: _block(header, "charPr", i) for i in set(re.findall(r'charPrIDRef="(\d+)"', inner))}
    paras = {i: _block(header, "paraPr", i) for i in set(re.findall(r'paraPrIDRef="(\d+)"', inner))}
    chars = {k: v for k, v in chars.items() if v}
    paras = {k: v for k, v in paras.items() if v}
    tabs = {i: _block(header, "tabPr", i) for i in {re.search(r'tabPrIDRef="(\d+)"', x).group(1)
                                                     for x in paras.values() if 'tabPrIDRef="' in x} - {"0"}}
    tabs = {k: v for k, v in tabs.items() if v}
    bf_ids = set(re.findall(r'borderFillIDRef="(\d+)"', inner))
    for x in list(chars.values()) + list(paras.values()):
        bf_ids |= set(re.findall(r'borderFillIDRef="(\d+)"', x))
    fills = {k: v for k, v in ((i, _block(header, "borderFill", i)) for i in bf_ids) if v}
    fonts: dict[str, dict[str, str]] = {}
    for lang, tag in LANGS.items():
        face = re.search(rf'<hh:fontface lang="{tag}"[^>]*>(.*?)</hh:fontface>', header, re.S)
        used = {re.search(rf'{lang}="(\d+)"', re.search(r"<hh:fontRef [^>]*/>", x).group(0)).group(1)
                for x in chars.values() if re.search(r"<hh:fontRef [^>]*/>", x)}
        fonts[tag] = {}
        for fid in used:
            x = _block(face.group(1), "font", fid) if face else None
            if x:
                fonts[tag][fid] = x

    # ---- 그림(로고 등): PNG로 바꿔 담는다 ----
    hpf = z.read("Contents/content.hpf").decode("utf-8") if "Contents/content.hpf" in names else ""
    images = {}
    total = 0
    refs = set(re.findall(r'binaryItemIDRef="([^"]+)"', inner + "".join(fills.values())))
    for item in refs:
        m = re.search(rf'<opf:item id="{re.escape(item)}" href="([^"]+)"', hpf)
        if not m or m.group(1) not in names:
            continue
        raw = z.read(m.group(1))
        try:
            import pymupdf as fitz
            png = fitz.Pixmap(raw).tobytes("png")
        except Exception:
            raise TemplateError("바탕쪽의 그림을 읽지 못했습니다. PNG·JPG 그림으로 바꿔 넣고 다시 저장해 주세요.")
        total += len(png)
        images[item] = base64.b64encode(png).decode("ascii")
    if total > MAX_IMAGES:
        raise TemplateError("바탕쪽 그림이 너무 큽니다(합계 2MB까지).")

    # ---- 쪽 여백 ----
    margins = {}
    m = re.search(r"<hp:margin [^>]*/>", secpr or "")
    if m:
        margins = {k: int(v) for k, v in re.findall(r'\b(header|footer|left|right|top|bottom)="(\d+)"', m.group(0))}

    # ---- 제목 칸: 가장 긴 글자 문단, 학원 칸: 그 밖의 첫 글자 문단 ----
    texts = _p_texts(inner)
    cands = [(len(t.strip()), i) for i, t in enumerate(texts) if t.strip() and _p_span(inner, i)]
    title_index = max(cands)[1] if cands else -1
    others = [i for i, t in enumerate(texts) if t.strip() and i != title_index]

    def runs_of(index: int) -> list[dict]:
        span = _p_span(inner, index)
        if not span:
            return []
        out = []
        for cid, body in re.findall(r'<hp:run charPrIDRef="(\d+)"[^>]*>(.*?)</hp:run>', inner[span[0]:span[1]], re.S):
            t = "".join(re.findall(r"<hp:t>([^<]*)", body))
            if not t:
                continue
            cx = chars.get(cid, "")
            hz = re.search(r'height="(\d+)"', cx)
            col = re.search(r'textColor="(#[0-9A-Fa-f]{6})"', cx)
            fr = re.search(r'hangul="(\d+)"', re.search(r"<hh:fontRef [^>]*/>", cx).group(0)) if "<hh:fontRef" in cx else None
            face = re.search(r'face="([^"]*)"', fonts["HANGUL"].get(fr.group(1), "")) if fr else None
            out.append({"t": t, "size": int(hz.group(1)) / 100 if hz else 10.0, "color": col.group(1) if col else "#000000",
                        "font": face.group(1) if face else "", "bold": "<hh:bold/>" in cx})
        return out

    all_faces = []
    hang = re.search(r'<hh:fontface lang="HANGUL"[^>]*>(.*?)</hh:fontface>', header, re.S)
    if hang:
        all_faces = list(dict.fromkeys(re.findall(r'<hh:font id="\d+" face="([^"]+)"', hang.group(1))))
    pkg = {
        "v": 1, "attrs": attrs, "inner": inner, "charPr": chars, "paraPr": paras, "tabPr": tabs, "borderFill": fills,
        "fonts": fonts, "images": images, "margins": margins,
        "title_index": title_index, "title_text": texts[title_index].strip() if title_index >= 0 else "",
        "title_runs": runs_of(title_index) if title_index >= 0 else [],
        "academy_runs": runs_of(others[0]) if others else [],
        "font_names": all_faces,
    }
    check_template(pkg)
    return pkg


def check_template(pkg: dict) -> dict:
    """브라우저가 보내온 묶음을 쓰기 전에 모양을 확인한다(깨진 HWPX를 만들지 않게)."""
    if not isinstance(pkg, dict) or pkg.get("v") != 1 or not isinstance(pkg.get("inner"), str):
        raise TemplateError("바탕쪽 정보가 올바르지 않습니다. 한글 파일을 다시 골라 주세요.")
    if len(json.dumps(pkg, ensure_ascii=False)) > MAX_PACKAGE + MAX_IMAGES * 4 // 3:
        raise TemplateError("바탕쪽 정보가 너무 큽니다.")
    try:
        _parse_fragment(pkg["inner"])
        for key, tag in (("charPr", "charPr"), ("paraPr", "paraPr"), ("tabPr", "tabPr"), ("borderFill", "borderFill")):
            for k, x in (pkg.get(key) or {}).items():
                if not str(k).isdigit() or not re.match(rf'<hh:{tag} id="{k}"', x):
                    raise ValueError(key)
                _parse_fragment(x)
        for tag, fs in (pkg.get("fonts") or {}).items():
            if tag not in LANGS.values():
                raise ValueError(tag)
            for k, x in fs.items():
                if not str(k).isdigit() or not x.startswith("<hh:font "):
                    raise ValueError("font")
                _parse_fragment(x)
        for b64 in (pkg.get("images") or {}).values():
            if not base64.b64decode(b64, validate=True).startswith(b"\x89PNG"):
                raise ValueError("image")
        if not re.fullmatch(r'(\w+="[^"<>]*"\s?)*', pkg.get("attrs", "")):
            raise ValueError("attrs")
    except TemplateError:
        raise
    except Exception:
        raise TemplateError("바탕쪽 정보가 올바르지 않습니다. 한글 파일을 다시 골라 주세요.")
    return pkg


def apply_template(pkg: dict, styles, title: str, image_name) -> tuple[str, str, list[tuple[str, bytes]]]:
    """묶음을 결과 문서에 들인다. styles: hwpx_writer.Styles, image_name(): 새 그림 이름을 하나씩 내준다.
    돌려주는 값: (masterPage 속성, masterPage 안쪽 XML, [(그림 이름, PNG)])."""
    fmap: dict[str, dict[str, int]] = {}
    for tag, fs in pkg["fonts"].items():
        fmap[tag] = {k: styles.add_font(tag, x) for k, x in fs.items()}
    images = {old: (image_name(), base64.b64decode(b64)) for old, b64 in pkg["images"].items()}

    def sub_img(x: str) -> str:
        return re.sub(r'binaryItemIDRef="([^"]+)"',
                      lambda m: f'binaryItemIDRef="{images[m.group(1)][0]}"' if m.group(1) in images else m.group(0), x)
    bmap = {k: styles.add_raw("borderFill", sub_img(x)) for k, x in pkg["borderFill"].items()}

    def sub_bf(x: str) -> str:
        return re.sub(r'borderFillIDRef="(\d+)"', lambda m: f'borderFillIDRef="{bmap.get(m.group(1), 1)}"', x)
    tmap = {k: styles.add_raw("tabPr", x) for k, x in pkg["tabPr"].items()}
    cmap = {}
    for k, x in pkg["charPr"].items():
        def font_ref(m: re.Match) -> str:
            parts = []
            for lang, tag in LANGS.items():
                old = re.search(rf'{lang}="(\d+)"', m.group(0))
                parts.append(f'{lang}="{fmap.get(tag, {}).get(old.group(1), 0) if old else 0}"')
            return "<hh:fontRef " + " ".join(parts) + "/>"
        cmap[k] = styles.add_raw("charPr", re.sub(r"<hh:fontRef [^>]*/>", font_ref, sub_bf(x), count=1))
    pmap = {}
    for k, x in pkg["paraPr"].items():
        x = re.sub(r'tabPrIDRef="(\d+)"', lambda m: f'tabPrIDRef="{tmap.get(m.group(1), 0)}"', sub_bf(x))
        x = re.sub(r"<hh:heading [^>]*/>", '<hh:heading type="NONE" idRef="0" level="0"/>', x, count=1)  # 번호 모양은 가져오지 않음
        pmap[k] = styles.add_raw("paraPr", x)

    inner = pkg["inner"]
    span = _p_span(inner, pkg.get("title_index", -1))
    if span:  # 제목 칸: 첫 글자 조각에 새 제목, 나머지 글자는 비운다
        p = inner[span[0]:span[1]]
        k = [0]

        def put(m: re.Match) -> str:
            k[0] += 1
            return f"<hp:t>{escape(title)}</hp:t>" if k[0] == 1 else "<hp:t/>"
        p = re.sub(r"<hp:t>.*?</hp:t>|<hp:t/>", put, p, flags=re.S) if re.search(r"<hp:t>[^<]", p) else p
        inner = inner[:span[0]] + p + inner[span[1]:]
    inner = re.sub(r'charPrIDRef="(\d+)"', lambda m: f'charPrIDRef="{cmap.get(m.group(1), 0)}"', inner)
    inner = re.sub(r'paraPrIDRef="(\d+)"', lambda m: f'paraPrIDRef="{pmap.get(m.group(1), 0)}"', inner)
    inner = re.sub(r'styleIDRef="\d+"', 'styleIDRef="0"', inner)
    inner = sub_img(sub_bf(inner))
    return pkg["attrs"], inner, [v for v in images.values()]
