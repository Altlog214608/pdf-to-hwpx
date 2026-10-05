#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
V0.2.2 - 국어 문제 PDF 전체 구조화 파서
=======================================

V0.2의 구조 추출은 유지하면서 텍스트 품질을 수정한 버전.

핵심 변경
---------
1) Kiwi 전체 문장 재띄어쓰기 제거
   - PDF 한 줄 안의 원래 띄어쓰기는 최대한 그대로 보존
   - "줄 끝 ↔ 다음 줄 시작" 경계에서만 Kiwi를 사용해
     붙일지/띄울지 판단

2) 해설의 PDF 시각 순서 복원
   - 같은 y좌표에 나뉜 텍스트 조각과 ①~⑤ 이미지 아이콘을
     x좌표 순서로 다시 합침
   - 예: "...보여준다." + ② + "(가)의 화자..." 순서 보존

3) 해설 안의 ①~⑤ 이미지 복원
   - 문제 선택지에서 학습한 이미지 hash를 그대로 활용

4) 지문 정규화 개선
   - 단순히 "시/산문 전체"를 한 방식으로 처리하지 않음
   - PDF 줄이 오른쪽 끝까지 찬 경우를 "물리적 자동 줄바꿈"으로 판단
   - 자동 줄바꿈만 연결하고, 짧은 시구/대사/구조선은 줄바꿈 보존
   - 페이지/2단 컬럼을 넘어가는 문장도 연결 가능

5) punctuation 후처리 개선
   - ".(가)" -> ". (가)"
   - "않다.“..." -> "않다. “..."
   - ",(나)" -> ", (나)"
   - 따옴표 내부 가장자리 정리

6) V0.2에서 확인된 PDF 텍스트 레이어 특이값 최소 보정
   - paired HWPX 원본과 비교해 확인된 "雪上加상" -> "雪上加霜"

주의
----
- <보기>를 별도 block으로 분리하는 작업은 V0.3
- 이미지 crop / 이미지 지문 구조화는 V0.4
- 이 버전은 현재 업로드된 '최다빈출 공략' 계열 PDF 구조를 기준으로 함

필요 패키지
-----------
    pip install pymupdf kiwipiepy

실행
----
    python v0_2_2_pdf_parser.py "원본.pdf"

출력 파일 지정
--------------
    python v0_2_2_pdf_parser.py "원본.pdf" -o v0_2_2_result.json

특정 문제만 디버깅
------------------
    python v0_2_2_pdf_parser.py "원본.pdf" -q 2 3 4 16

Kiwi 없이 구조만 테스트
-----------------------
    python v0_2_2_pdf_parser.py "원본.pdf" --no-kiwi
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import fitz

try:
    from kiwipiepy import Kiwi
except ImportError:
    Kiwi = None


CIRCLED = "①②③④⑤"

QUESTION_HEADER_RE = re.compile(r"^(\d+)\.$")
ANSWER_HEADER_RE = re.compile(r"^(\d+)\)\s*\[정답\](?:\s*[①-⑤])?$")
SECTION_LABEL_RE = re.compile(r"^\([가-힣A-Za-z0-9]+\)$")

# V0.2 결과와 paired HWPX를 비교해서 확인된 PDF text-layer artifact.
# 일반 문법 교정이 아니라, 해당 소스에서 실제 글자가 잘못 추출되는 케이스만 보정.
SOURCE_CHAR_REPAIRS = {
    "雪上加상": "雪上加霜",
}

# 경계 판별 fallback / 안전장치용.
# Kiwi 전체 문장을 다시 띄우지 않기 때문에 정상 문자열을 과도하게 바꾸지 않는다.
KNOWN_COMPOUNDS = {
    "짝새",
    "희비극적",
    "윗글",
    "1인칭",
    "반지하",
    "한자성어",
    "제작팀",
    "연주곡",
    "손글씨",
    "손수레",
    "색채어",
    "영탄적",
    "관조적",
    "외부인",
    "내면세계",
    "저항의지",
}

STRUCTURAL_LINES = {
    "<보기>",
    "(중략)",
    "<중략>",
}

JOINABLE_RIGHT_FRAGMENTS = {
    "다", "서", "며", "고", "는", "은", "을", "를",
    "이", "가", "의", "로", "와", "과", "도", "만",
    "에", "어", "여", "게", "면", "니", "지", "요",
    "에게", "에서", "으로", "부터", "까지", "처럼", "보다",
    "이라", "이라는", "라고", "라는",
}

FORCE_SPACE_AFTER_WORDS = {
    "어찌",
    "모르니",
}


# ============================================================================
# Text Normalizer
# ============================================================================

class BoundaryTextNormalizer:
    """
    V0.2.2의 핵심.

    V0.2처럼 문장 전체를 Kiwi.space()에 넣지 않는다.
    PDF에서 물리적으로 갈라진 두 줄의 '경계'만 검사한다.
    """

    def __init__(self, use_kiwi: bool = True) -> None:
        self.kiwi = None

        if use_kiwi and Kiwi is not None:
            self.kiwi = Kiwi()

            for word in KNOWN_COMPOUNDS:
                if re.fullmatch(r"[가-힣]+", word):
                    try:
                        self.kiwi.add_user_word(word, "NNG", 0)
                    except Exception:
                        pass

    @property
    def engine_name(self) -> str:
        if self.kiwi is not None:
            return "boundary-only Kiwi + layout-aware line repair + punctuation rules"
        return "boundary heuristic fallback + layout-aware line repair + punctuation rules"

    @staticmethod
    def _first_word(text: str) -> str:
        match = re.match(r"([가-힣A-Za-z0-9]+)", text.strip())
        return match.group(1) if match else ""

    @staticmethod
    def _last_word(text: str) -> str:
        match = re.search(r"([가-힣A-Za-z0-9]+)$", text.strip())
        return match.group(1) if match else ""

    @staticmethod
    def _space_at_character_boundary(
        spaced: str,
        left_char_count: int,
    ) -> bool | None:
        """
        Kiwi 결과에서 '왼쪽 조각 끝' 지점에 공백이 생겼는지 판단.
        """
        nonspace_count = 0

        for ch in spaced:
            if ch.isspace():
                if nonspace_count == left_char_count:
                    return True
                continue

            nonspace_count += 1

            if nonspace_count > left_char_count:
                return False

        return None

    def boundary_separator(
        self,
        left_text: str,
        right_text: str,
    ) -> str:
        """
        두 물리 줄 사이를 "" 로 붙일지 " " 로 띄울지 판단한다.

        V0.2.2 원칙:
        - 정상 띄어쓰기는 건드리지 않는다.
        - PDF 줄 경계만 판단한다.
        - 명백한 조사/어미 조각은 앞 단어에 붙인다.
        - 완결된 어절 뒤 새 단어는 띄어쓴다.
        """
        left = left_text.rstrip()
        right = right_text.lstrip()

        if not left or not right:
            return ""

        if SECTION_LABEL_RE.fullmatch(right):
            return "\n"

        if right in STRUCTURAL_LINES or left in STRUCTURAL_LINES:
            return "\n"

        if re.search(r"[.!?。！？…]$", left):
            return " "

        if re.search(r"[,;:]$", left):
            return " "

        if re.match(r"^[,.;:!?)}\]〉》」』’”]", right):
            return ""

        left_word = self._last_word(left)
        right_word = self._first_word(right)

        if not left_word or not right_word:
            return " "

        compact = left_word + right_word

        if compact in KNOWN_COMPOUNDS:
            return ""

        if right_word in JOINABLE_RIGHT_FRAGMENTS:
            return ""

        if left_word in FORCE_SPACE_AFTER_WORDS:
            return " "

        if re.search(r"(?:다|요|죠|네|니|까|며|고|면|지만|는데)$", left_word):
            return " "

        if self.kiwi is not None:
            try:
                spaced = self.kiwi.space(compact)

                if spaced.replace(" ", "") == compact.replace(" ", ""):
                    wants_space = self._space_at_character_boundary(
                        spaced,
                        len(left_word),
                    )

                    if wants_space is True:
                        return " "
                    if wants_space is False:
                        return ""
            except Exception:
                pass

        if (
            re.fullmatch(r"[가-힣]+", left_word)
            and re.fullmatch(r"[가-힣]+", right_word)
        ):
            if len(left_word) <= 1 or len(right_word) <= 1:
                return ""

        return " "

    @staticmethod
    def cleanup_punctuation(text: str) -> str:
        """문장부호, 조사 경계, 안전한 활용형만 후처리한다."""
        text = re.sub(r"[ \t]+", " ", text)

        for before, after in SOURCE_CHAR_REPAIRS.items():
            text = text.replace(before, after)

        text = re.sub(r"\s+([,.!?;:%)\]}>》〉」』])", r"\1", text)
        text = re.sub(r"([(\[<{《〈「『])\s+", r"\1", text)
        text = re.sub(r"([‘“])\s+", r"\1", text)
        text = re.sub(r"\s+([’”])", r"\1", text)

        text = re.sub(
            r"([.!?,;:])(\([가-힣A-Za-z0-9]+\))",
            r"\1 \2",
            text,
        )
        text = re.sub(r"([.!?,;:])([‘“])", r"\1 \2", text)
        text = re.sub(r"([가-힣A-Za-z0-9])([‘“])", r"\1 \2", text)

        particle = (
            r"은|는|이|가|을|를|에|의|도|로|으로|와|과|만|부터|까지|"
            r"처럼|보다|에게|에서|이라|이라는|라고|라는"
        )
        text = re.sub(
            rf"([)\]}}>》〉」』’”①-⑤㉠-㉿])\s+({particle})(?=\s|[,.!?]|$)",
            r"\1\2",
            text,
        )

        text = re.sub(r"([①-⑤㉠-㉿])\s+(에|은|는|이|가|을|를|의|도)", r"\1\2", text)
        text = re.sub(r"([’”])\s+(\([㉠-㉿]\))", r"\1\2", text)

        safe_spacing_rules = [
            (r"하려한다(?=\b|[.,!?]|$)", "하려 한다"),
            (r"하려하고(?=\b|[.,!?]|$)", "하려 하고"),
            (r"해야한다고(?=\b|[.,!?]|$)", "해야 한다고"),
            (r"해야하는(?=\s|[가-힣])", "해야 하는"),
            (r"하지않", "하지 않"),
            (r"않은것은", "않은 것은"),
            (r"적절하지 않은것은", "적절하지 않은 것은"),
        ]

        for pattern, replacement in safe_spacing_rules:
            text = re.sub(pattern, replacement, text)

        fixed_compounds = {
            "짝 새": "짝새",
            "희 비극적": "희비극적",
            "윗 글": "윗글",
            "1 인칭": "1인칭",
            "반 지하": "반지하",
            "한자 성어": "한자성어",
            "제작 팀": "제작팀",
            "연주 곡": "연주곡",
            "손 글씨": "손글씨",
            "손 수레": "손수레",
            "색 채어": "색채어",
            "영 탄적": "영탄적",
            "관 조적": "관조적",
        }

        for before, after in fixed_compounds.items():
            text = text.replace(before, after)

        return text.strip()

    @staticmethod
    def classify_passage_style(text: str) -> str:
        stripped_lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip()
        ]

        content = [
            line
            for line in stripped_lines
            if not SECTION_LABEL_RE.fullmatch(line)
        ]

        if not content:
            return "image_only"

        if any(
            re.match(r"^S#\d+", line)
            for line in content
        ):
            return "drama"

        short_lines = sum(
            1
            for line in content
            if len(line) <= 24
        )

        ratio = short_lines / max(len(content), 1)

        if ratio >= 0.65:
            return "poetry_or_short_form"

        if ratio >= 0.30:
            return "mixed"

        return "prose"

    def join_all_prose_lines(
        self,
        lines: list[str],
    ) -> str:
        """
        문제문/선택지/해설용.
        모든 물리 줄은 한 문단으로 만들되,
        줄 경계에서만 붙임/띄움을 판단한다.
        """
        lines = [
            line.strip()
            for line in lines
            if line and line.strip()
        ]

        if not lines:
            return ""

        result = lines[0]

        for nxt in lines[1:]:
            sep = self.boundary_separator(
                result,
                nxt,
            )

            if sep == "\n":
                # 문제문 안 <보기> 등을 V0.2 호환 형태로 유지.
                sep = " "

            result += sep + nxt

        return self.cleanup_punctuation(result)

    def normalize_passage_records(
        self,
        records: list[dict[str, Any]],
    ) -> tuple[str, str]:
        """
        지문 전용 정규화.

        V0.2.2에서는 두 조건 중 하나면 다음 줄과 연결한다.
        1) 현재 줄이 컬럼 폭의 상당 부분을 차지해 PDF 자동 줄바꿈으로 보이는 경우
        2) Kiwi/규칙상 줄 경계가 명백한 '단어 내부 분절'인 경우
        """
        physical = collapse_text_records(records)

        raw_text = "\n".join(
            line["text"]
            for line in physical
        ).strip()

        if not physical:
            return raw_text, ""

        result_parts: list[str] = [physical[0]["text"].strip()]
        previous = physical[0]

        for current in physical[1:]:
            current_text = current["text"].strip()
            previous_text = previous["text"].strip()

            structural = (
                SECTION_LABEL_RE.fullmatch(current_text)
                or current_text in STRUCTURAL_LINES
                or SECTION_LABEL_RE.fullmatch(previous_text)
                or previous_text in STRUCTURAL_LINES
            )

            right_margin = previous.get(
                "column_right",
                previous["bbox"].x1,
            )
            usable_width = max(
                right_margin - previous["bbox"].x0,
                1.0,
            )
            fill_ratio = previous["bbox"].width / usable_width

            likely_wrapped = (
                previous["bbox"].x1 >= right_margin - 22
                or fill_ratio >= 0.76
            )

            boundary = self.boundary_separator(
                previous_text,
                current_text,
            )
            definite_word_fragment = boundary == ""

            if structural:
                sep = "\n"
            elif definite_word_fragment:
                sep = ""
            elif likely_wrapped:
                sep = " " if boundary == "\n" else boundary
            else:
                sep = "\n"

            result_parts.append(sep + current_text)
            previous = current

        normalized = "".join(result_parts)
        normalized = "\n".join(
            self.cleanup_punctuation(line)
            for line in normalized.splitlines()
        ).strip()

        return raw_text, normalized


# ============================================================================
# PDF helpers
# ============================================================================

def get_line_records(
    page: fitz.Page,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    for block in page.get_text("dict")["blocks"]:
        if block["type"] != 0:
            continue

        for line in block["lines"]:
            text = "".join(
                span["text"]
                for span in line["spans"]
            ).strip()

            if not text:
                continue

            result.append(
                {
                    "text": text,
                    "bbox": fitz.Rect(
                        line["bbox"]
                    ),
                }
            )

    return result


def get_image_instances(
    page: fitz.Page,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen_xrefs: set[int] = set()
    seen_positions: set[tuple[Any, ...]] = set()

    for info in page.get_images(full=True):
        xref = info[0]

        if xref in seen_xrefs:
            continue

        seen_xrefs.add(xref)

        try:
            image_bytes = (
                page.parent
                .extract_image(xref)["image"]
            )
        except Exception:
            pix = fitz.Pixmap(
                page.parent,
                xref,
            )
            image_bytes = pix.tobytes("png")

        image_hash = hashlib.md5(
            image_bytes
        ).hexdigest()

        for rect in page.get_image_rects(
            xref
        ):
            key = (
                image_hash,
                round(rect.x0, 2),
                round(rect.y0, 2),
                round(rect.x1, 2),
                round(rect.y1, 2),
            )

            if key in seen_positions:
                continue

            seen_positions.add(key)

            result.append(
                {
                    "xref": xref,
                    "hash": image_hash,
                    "rect": rect,
                    "pixel_width": info[2],
                    "pixel_height": info[3],
                }
            )

    return result


def get_column(
    page: fitz.Page,
    x: float,
) -> int:
    return (
        0
        if x < page.rect.width / 2
        else 1
    )


def get_column_bounds(
    page: fitz.Page,
    column: int,
) -> tuple[float, float]:
    middle = page.rect.width / 2

    if column == 0:
        return 45.0, middle - 6.0

    return (
        middle + 6.0,
        page.rect.width - 45.0,
    )


def is_page_noise(
    text: str,
) -> bool:
    text = text.strip()

    if text.startswith(
        "[최다빈출 공략]"
    ):
        return True

    if text == "비상(강호영)":
        return True

    if re.fullmatch(
        r"I\d[\d-]+",
        text,
    ):
        return True

    if re.fullmatch(
        r"-\s*\d+\s*-",
        text,
    ):
        return True

    if text.startswith(
        "◇「콘텐츠산업 진흥법"
    ):
        return True

    if text.startswith(
        "1) 제작연월일"
    ):
        return True

    if text.startswith(
        "3) 이 콘텐츠는 「콘텐츠산업 진흥법」에 따라 최초 제작"
    ):
        return True

    if text == "일부터 5년간 보호됩니다.":
        return True

    if text.startswith(
        "부 또는 일부를 무단으로 복제하거나 전송하는 것은"
    ):
        return True

    if text.startswith(
        "의한 법적 책임을 질 수 있습니다."
    ):
        return True

    return False


def collapse_text_records(
    records: list[dict[str, Any]],
    y_tolerance: float = 2.0,
) -> list[dict[str, Any]]:
    """
    동일한 물리 baseline에 PDF가 여러 line object를 만든 경우
    x좌표 순서로 다시 한 줄로 합친다.

    텍스트-only 용.
    해설의 inline ①~⑤는 visual line builder에서 별도 처리.
    """
    if not records:
        return []

    ordered = sorted(
        records,
        key=lambda item: (
            item.get("page_index", 0),
            item.get("column", 0),
            item["bbox"].y0,
            item["bbox"].x0,
        ),
    )

    groups: list[list[dict[str, Any]]] = []

    for record in ordered:
        if not groups:
            groups.append([record])
            continue

        last_group = groups[-1]
        ref = last_group[0]

        same_region = (
            record.get("page_index")
            == ref.get("page_index")
            and record.get("column")
            == ref.get("column")
        )

        same_y = (
            abs(
                record["bbox"].y0
                - ref["bbox"].y0
            )
            <= y_tolerance
        )

        if same_region and same_y:
            last_group.append(record)
        else:
            groups.append([record])

    output: list[dict[str, Any]] = []

    for group in groups:
        group.sort(
            key=lambda item:
            item["bbox"].x0
        )

        text = " ".join(
            item["text"].strip()
            for item in group
            if item["text"].strip()
        )

        x0 = min(
            item["bbox"].x0
            for item in group
        )
        y0 = min(
            item["bbox"].y0
            for item in group
        )
        x1 = max(
            item["bbox"].x1
            for item in group
        )
        y1 = max(
            item["bbox"].y1
            for item in group
        )

        first = group[0]

        output.append(
            {
                "text": text,
                "bbox": fitz.Rect(
                    x0, y0, x1, y1
                ),
                "page_index": (
                    first.get(
                        "page_index"
                    )
                ),
                "column": (
                    first.get("column")
                ),
                "column_left": (
                    first.get(
                        "column_left"
                    )
                ),
                "column_right": (
                    first.get(
                        "column_right"
                    )
                ),
            }
        )

    return output


def find_answer_start_page(
    document: fitz.Document,
) -> int:
    for page_index, page in enumerate(
        document
    ):
        for line in get_line_records(
            page
        ):
            if re.fullmatch(
                r"1\)\s*\[정답\]",
                line["text"],
            ):
                return page_index

    raise RuntimeError(
        "정답/해설 시작 페이지를 찾지 못했습니다."
    )


def get_ordered_regions(
    document: fitz.Document,
    page_indices: list[int] | range,
) -> list[dict[str, Any]]:
    regions: list[dict[str, Any]] = []

    for page_index in page_indices:
        page = document[page_index]
        all_lines = get_line_records(
            page
        )

        for column in (0, 1):
            left, right = get_column_bounds(
                page,
                column,
            )

            lines = []

            for line in all_lines:
                if not (
                    left
                    <= line["bbox"].x0
                    < right
                ):
                    continue

                if is_page_noise(
                    line["text"]
                ):
                    continue

                item = dict(line)
                item.update(
                    {
                        "page_index": page_index,
                        "column": column,
                        "column_left": left,
                        "column_right": right,
                    }
                )

                lines.append(item)

            lines.sort(
                key=lambda item: (
                    item["bbox"].y0,
                    item["bbox"].x0,
                )
            )

            regions.append(
                {
                    "page_index": page_index,
                    "column": column,
                    "column_left": left,
                    "column_right": right,
                    "lines": lines,
                }
            )

    return regions


# ============================================================================
# Digit icon mapping / visual-line reconstruction
# ============================================================================

def get_question_headers(
    page: fitz.Page,
) -> list[tuple[int, fitz.Rect, int]]:
    result = []

    for line in get_line_records(page):
        match = QUESTION_HEADER_RE.fullmatch(
            line["text"]
        )

        if not match:
            continue

        result.append(
            (
                int(match.group(1)),
                line["bbox"],
                get_column(
                    page,
                    line["bbox"].x0,
                ),
            )
        )

    return result


def build_digit_icon_map(
    first_page: fitz.Page,
) -> dict[str, int]:
    """
    1번 문제의 ①~⑤ 아이콘을 hash -> 숫자로 매핑.
    """
    headers = get_question_headers(
        first_page
    )

    first = next(
        item
        for item in headers
        if item[0] == 1
    )

    _, qbox, column = first
    left, right = get_column_bounds(
        first_page,
        column,
    )

    next_ys = [
        bbox.y0
        for number, bbox, col
        in headers
        if (
            col == column
            and bbox.y0 > qbox.y0
        )
    ]

    end_y = min(
        next_ys
        or [
            first_page.rect.height - 50
        ]
    )

    icons = [
        image
        for image in get_image_instances(
            first_page
        )
        if (
            qbox.y0
            < image["rect"].y0
            < end_y
        )
        and (
            left
            <= image["rect"].x0
            < right
        )
        and image["rect"].width < 20
        and image["rect"].height < 20
    ]

    icons.sort(
        key=lambda image: (
            image["rect"].y0,
            image["rect"].x0,
        )
    )

    if len(icons) < 5:
        raise RuntimeError(
            "1번 문제에서 ①~⑤ 아이콘을 찾지 못했습니다."
        )

    return {
        icon["hash"]: index + 1
        for index, icon
        in enumerate(icons[:5])
    }


def build_visual_lines(
    page: fitz.Page,
    column: int,
    digit_icon_map: dict[str, int],
    y_tolerance: float = 3.2,
) -> list[dict[str, Any]]:
    """
    텍스트 조각 + inline ①~⑤ 이미지까지 한 물리 라인으로 복원.

    예:
        [text "...보여준다."]
        [image ②]
        [text "(가)의 화자는..."]

    -> "...보여준다. ② (가)의 화자는..."
    """
    left, right = get_column_bounds(
        page,
        column,
    )

    items: list[dict[str, Any]] = []

    for line in get_line_records(page):
        if not (
            left
            <= line["bbox"].x0
            < right
        ):
            continue

        if is_page_noise(
            line["text"]
        ):
            continue

        items.append(
            {
                "kind": "text",
                "text": line["text"],
                "bbox": line["bbox"],
            }
        )

    for image in get_image_instances(page):
        if image["hash"] not in digit_icon_map:
            continue

        rect = image["rect"]

        if not (
            left <= rect.x0 < right
        ):
            continue

        if (
            rect.width >= 20
            or rect.height >= 20
        ):
            continue

        index = digit_icon_map[
            image["hash"]
        ]

        items.append(
            {
                "kind": "icon",
                "text": CIRCLED[
                    index - 1
                ],
                "bbox": rect,
            }
        )

    items.sort(
        key=lambda item: (
            item["bbox"].y0,
            item["bbox"].x0,
        )
    )

    groups: list[list[dict[str, Any]]] = []

    for item in items:
        if not groups:
            groups.append([item])
            continue

        ref = groups[-1][0]

        if (
            abs(
                item["bbox"].y0
                - ref["bbox"].y0
            )
            <= y_tolerance
        ):
            groups[-1].append(item)
        else:
            groups.append([item])

    output = []

    for group in groups:
        group.sort(
            key=lambda item:
            item["bbox"].x0
        )

        parts: list[str] = []

        for item in group:
            token = item["text"].strip()

            if not token:
                continue

            if item["kind"] == "icon":
                parts.append(
                    f" {token} "
                )
            else:
                parts.append(token)

        text = "".join(parts)
        text = re.sub(
            r"[ \t]+",
            " ",
            text,
        ).strip()

        x0 = min(
            item["bbox"].x0
            for item in group
        )
        y0 = min(
            item["bbox"].y0
            for item in group
        )
        x1 = max(
            item["bbox"].x1
            for item in group
        )
        y1 = max(
            item["bbox"].y1
            for item in group
        )

        output.append(
            {
                "text": text,
                "bbox": fitz.Rect(
                    x0, y0, x1, y1
                ),
                "page_index": page.number,
                "column": column,
                "column_left": left,
                "column_right": right,
            }
        )

    return output


# ============================================================================
# Passage groups
# ============================================================================

def parse_passage_groups(
    document: fitz.Document,
    question_end_page: int,
    normalizer: BoundaryTextNormalizer,
) -> list[dict[str, Any]]:
    groups = []
    current = None
    collecting = False

    for region in get_ordered_regions(
        document,
        list(
            range(question_end_page)
        ),
    ):
        page_number = (
            region["page_index"] + 1
        )

        for line in region["lines"]:
            text = line["text"]

            if text.startswith(
                "※ 다음 글을 읽고"
            ):
                if current is not None:
                    groups.append(current)

                current = {
                    "id": len(groups) + 1,
                    "question_numbers": [],
                    "source_pages": set(),
                    "records": [],
                }

                current[
                    "source_pages"
                ].add(page_number)

                collecting = True
                continue

            qmatch = (
                QUESTION_HEADER_RE
                .fullmatch(text)
            )

            if qmatch:
                if current is not None:
                    number = int(
                        qmatch.group(1)
                    )

                    if (
                        number
                        not in current[
                            "question_numbers"
                        ]
                    ):
                        current[
                            "question_numbers"
                        ].append(number)

                    current[
                        "source_pages"
                    ].add(page_number)

                collecting = False
                continue

            if (
                current is not None
                and collecting
            ):
                current["records"].append(
                    line
                )

                current[
                    "source_pages"
                ].add(page_number)

    if current is not None:
        groups.append(current)

    output = []

    for group in groups:
        raw, normalized = (
            normalizer
            .normalize_passage_records(
                group["records"]
            )
        )

        style = (
            normalizer
            .classify_passage_style(
                normalized
            )
        )

        text_without_labels = re.sub(
            r"(?m)^\([가-힣A-Za-z0-9]+\)\s*$",
            "",
            normalized,
        ).strip()

        output.append(
            {
                "id": group["id"],
                "question_numbers": (
                    group[
                        "question_numbers"
                    ]
                ),
                "source_pages": sorted(
                    group["source_pages"]
                ),
                "style_hint": style,
                "needs_image_processing": (
                    not bool(
                        text_without_labels
                    )
                ),
                "raw_text": raw,
                "normalized_text": (
                    normalized
                ),
            }
        )

    return output


# ============================================================================
# Question extraction
# ============================================================================

def build_question_meta(
    document: fitz.Document,
    question_end_page: int,
) -> dict[int, dict[str, Any]]:
    result = {}

    for page_index in range(
        question_end_page
    ):
        page = document[page_index]

        for (
            number,
            bbox,
            column,
        ) in get_question_headers(
            page
        ):
            result[number] = {
                "page_index": page_index,
                "bbox": bbox,
                "column": column,
            }

    return result


def get_passage_anchors(
    page: fitz.Page,
    column: int,
) -> list[fitz.Rect]:
    result = []

    for line in get_line_records(page):
        if (
            line["text"].startswith(
                "※ 다음 글을 읽고"
            )
            and get_column(
                page,
                line["bbox"].x0,
            )
            == column
        ):
            result.append(
                line["bbox"]
            )

    return result


def extract_question_block(
    document: fitz.Document,
    question_number: int,
    question_meta: dict[int, dict[str, Any]],
    digit_icon_map: dict[str, int],
) -> dict[str, Any]:
    meta = question_meta[
        question_number
    ]

    page = document[
        meta["page_index"]
    ]

    qbox = meta["bbox"]
    column = meta["column"]

    left, right = get_column_bounds(
        page,
        column,
    )

    end_candidates = [
        page.rect.height - 50
    ]

    for (
        other_number,
        other_box,
        other_column,
    ) in get_question_headers(page):
        if (
            other_column == column
            and other_box.y0 > qbox.y0
        ):
            end_candidates.append(
                other_box.y0
            )

    for anchor in get_passage_anchors(
        page,
        column,
    ):
        if anchor.y0 > qbox.y0:
            end_candidates.append(
                anchor.y0
            )

    end_y = min(end_candidates)

    page_lines = []

    for line in get_line_records(page):
        if not (
            left
            <= line["bbox"].x0
            < right
        ):
            continue

        if not (
            qbox.y0 - 1
            <= line["bbox"].y0
            < end_y
        ):
            continue

        if is_page_noise(
            line["text"]
        ):
            continue

        item = dict(line)
        item.update(
            {
                "page_index": (
                    meta["page_index"]
                ),
                "column": column,
                "column_left": left,
                "column_right": right,
            }
        )
        page_lines.append(item)

    # ①~⑤ marker
    by_choice = defaultdict(list)

    for image in get_image_instances(page):
        if (
            image["hash"]
            not in digit_icon_map
        ):
            continue

        rect = image["rect"]

        if not (
            left <= rect.x0 < right
        ):
            continue

        if not (
            qbox.y0
            < rect.y0
            < end_y
        ):
            continue

        if (
            rect.width >= 20
            or rect.height >= 20
        ):
            continue

        number = digit_icon_map[
            image["hash"]
        ]

        by_choice[number].append(
            image
        )

    markers = {}

    for choice in range(1, 6):
        candidates = (
            by_choice.get(
                choice,
                [],
            )
        )

        if not candidates:
            raise RuntimeError(
                f"{question_number}번 "
                f"{CIRCLED[choice - 1]} "
                "선택지 아이콘을 찾지 못했습니다."
            )

        markers[choice] = min(
            candidates,
            key=lambda item: (
                item["rect"].y0,
                item["rect"].x0,
            ),
        )

    first_choice_y = min(
        item["rect"].y0
        for item
        in markers.values()
    )

    stem_records = [
        line
        for line in page_lines
        if (
            line["bbox"].y0
            < first_choice_y - 3
        )
        and line["text"]
        != f"{question_number}."
        and not line[
            "text"
        ].startswith(
            f"zb{question_number}"
        )
    ]

    stem_records.sort(
        key=lambda item: (
            item["bbox"].y0,
            item["bbox"].x0,
        )
    )

    stem_physical = (
        collapse_text_records(
            stem_records
        )
    )

    raw_question_lines = [
        item["text"]
        for item in stem_physical
    ]

    raw_choices = []

    for choice in range(1, 6):
        current = markers[
            choice
        ]["rect"]

        nxt = markers.get(
            choice + 1
        )

        y_start = current.y0 - 4
        y_end = end_y
        x_start = current.x1 + 1
        x_end = right

        if nxt is not None:
            next_rect = nxt["rect"]

            # 같은 행 2열 선택지
            if (
                abs(
                    next_rect.y0
                    - current.y0
                )
                <= 5
                and next_rect.x0
                > current.x0
            ):
                x_end = (
                    next_rect.x0 - 1
                )

                lower = [
                    markers[i]["rect"].y0
                    for i
                    in range(
                        choice + 1,
                        6,
                    )
                    if (
                        markers[i][
                            "rect"
                        ].y0
                        > current.y0 + 5
                    )
                ]

                if lower:
                    y_end = (
                        min(lower) - 3
                    )

            elif (
                next_rect.y0
                > current.y0
            ):
                y_end = (
                    next_rect.y0 - 3
                )

        choice_records = [
            line
            for line in page_lines
            if (
                y_start
                <= line["bbox"].y0
                < y_end
            )
            and (
                x_start
                <= line["bbox"].x0
                < x_end
            )
        ]

        choice_physical = (
            collapse_text_records(
                choice_records
            )
        )

        raw_choices.append(
            [
                item["text"]
                for item
                in choice_physical
            ]
        )

    return {
        "number": question_number,
        "source_page": (
            meta["page_index"] + 1
        ),
        "column": (
            "left"
            if column == 0
            else "right"
        ),
        "raw_question_lines": (
            raw_question_lines
        ),
        "raw_choice_lines": (
            raw_choices
        ),
    }


# ============================================================================
# Answers / explanations
# ============================================================================

def extract_answers_and_explanations(
    document: fitz.Document,
    answer_start_page: int,
    digit_icon_map: dict[str, int],
    normalizer: BoundaryTextNormalizer,
) -> tuple[
    dict[int, int],
    dict[int, str],
]:
    """
    정답과 해설을 동일한 visual-line stream에서 읽는다.

    이 방식으로:
    - 정답 번호 아이콘
    - 해설 내부 ①②③④⑤
    - 같은 baseline에서 이미지 때문에 갈라진 텍스트
    를 한 번에 복원한다.
    """
    answers: dict[int, int] = {}
    explanation_lines: dict[
        int,
        list[str],
    ] = {}

    current_question: int | None = None

    for page_index in range(
        answer_start_page,
        len(document),
    ):
        page = document[page_index]

        for column in (0, 1):
            visual_lines = (
                build_visual_lines(
                    page,
                    column,
                    digit_icon_map,
                )
            )

            for line in visual_lines:
                text = line["text"].strip()

                header_match = re.match(
                    r"^(\d+)\)\s*\[정답\]\s*([①-⑤])?",
                    text,
                )

                if header_match:
                    current_question = int(
                        header_match.group(1)
                    )

                    answer_symbol = (
                        header_match.group(2)
                    )

                    if answer_symbol:
                        answers[
                            current_question
                        ] = (
                            CIRCLED.index(
                                answer_symbol
                            )
                            + 1
                        )

                    explanation_lines[
                        current_question
                    ] = []

                    # 같은 visual line에 [해설]까지 붙는 변형 대응
                    remain = text[
                        header_match.end():
                    ].strip()

                    if remain.startswith(
                        "[해설]"
                    ):
                        remain = remain[
                            len("[해설]"):
                        ].strip()

                    if remain:
                        explanation_lines[
                            current_question
                        ].append(remain)

                    continue

                if current_question is None:
                    continue

                if text.startswith(
                    "[해설]"
                ):
                    text = text[
                        len("[해설]"):
                    ].strip()

                if text:
                    explanation_lines[
                        current_question
                    ].append(text)

    explanations = {}

    for number, lines in (
        explanation_lines.items()
    ):
        explanations[number] = (
            normalizer
            .join_all_prose_lines(
                lines
            )
        )

    return answers, explanations


# ============================================================================
# Validation
# ============================================================================

SUSPICIOUS_PATTERNS = [
    r",,,",
    r"\b1 인칭\b",
    r"\b윗 글\b",
    r"\b짝 새\b",
    r"\b희 비극적\b",
    r"\b한자 성어\b",
    r"\b제작 팀\b",
    r"\b연주 곡\b",
    r"\b손 글씨\b",
    r"\b손 수레\b",
    r"떠보기 단보다는",
    r"\b순히 위로",
    r"적절하지 않은것은",
    r"하려한다",
    r"해야한다고",
    r"\) [는이가을를에의도]\b",
    r"[①-⑤] 에\b",
]


def validate_result(
    passage_groups: list[dict[str, Any]],
    questions: list[dict[str, Any]],
    expected_questions: list[int],
) -> dict[str, Any]:
    issues = []
    warnings = []

    found = sorted(
        q["number"]
        for q in questions
    )

    expected = sorted(
        expected_questions
    )

    if found != expected:
        issues.append(
            f"문제 번호 불일치: "
            f"expected={expected}, found={found}"
        )

    for question in questions:
        number = question["number"]

        if not question.get(
            "question"
        ):
            issues.append(
                f"{number}번 문제문 비어 있음"
            )

        choices = question.get(
            "choices",
            [],
        )

        if len(choices) != 5:
            issues.append(
                f"{number}번 선택지 수 != 5"
            )

        if any(
            not choice
            for choice in choices
        ):
            issues.append(
                f"{number}번 빈 선택지 존재"
            )

        if question.get(
            "answer"
        ) is None:
            issues.append(
                f"{number}번 정답 누락"
            )

        if not question.get(
            "explanation"
        ):
            issues.append(
                f"{number}번 해설 누락"
            )

        combined = " ".join(
            [
                question.get(
                    "question",
                    "",
                ),
                *choices,
                question.get(
                    "explanation",
                    "",
                ),
            ]
        )

        for pattern in (
            SUSPICIOUS_PATTERNS
        ):
            if re.search(
                pattern,
                combined,
            ):
                warnings.append(
                    f"{number}번에서 "
                    f"의심 패턴 발견: {pattern}"
                )

    for group in passage_groups:
        if not group[
            "question_numbers"
        ]:
            issues.append(
                f"지문 그룹 {group['id']}에 문제 연결 없음"
            )

    return {
        "status": (
            "PASS"
            if not issues
            else "WARN"
        ),
        "question_count": len(
            questions
        ),
        "expected_question_count": (
            len(expected_questions)
        ),
        "passage_group_count": len(
            passage_groups
        ),
        "issues": issues,
        "warnings": warnings,
    }


# ============================================================================
# Main parse
# ============================================================================

def parse_v0_2_2(
    pdf_path: Path,
    question_numbers: list[int],
    use_kiwi: bool = True,
) -> dict[str, Any]:
    document = fitz.open(
        pdf_path
    )

    normalizer = (
        BoundaryTextNormalizer(
            use_kiwi=use_kiwi
        )
    )

    try:
        answer_start_page = (
            find_answer_start_page(
                document
            )
        )

        question_end_page = (
            answer_start_page
        )

        digit_icon_map = (
            build_digit_icon_map(
                document[0]
            )
        )

        passage_groups = (
            parse_passage_groups(
                document,
                question_end_page,
                normalizer,
            )
        )

        question_to_group = {}

        for group in passage_groups:
            for number in group[
                "question_numbers"
            ]:
                question_to_group[
                    number
                ] = group["id"]

        question_meta = (
            build_question_meta(
                document,
                question_end_page,
            )
        )

        (
            answers,
            explanations,
        ) = (
            extract_answers_and_explanations(
                document,
                answer_start_page,
                digit_icon_map,
                normalizer,
            )
        )

        questions = []

        for number in question_numbers:
            if number not in question_meta:
                questions.append(
                    {
                        "number": number,
                        "question": "",
                        "choices": [],
                        "answer": None,
                        "answer_index": None,
                        "explanation": None,
                        "passage_group_id": (
                            question_to_group.get(
                                number
                            )
                        ),
                        "error": (
                            "문제 번호를 "
                            "PDF에서 찾지 못했습니다."
                        ),
                    }
                )
                continue

            raw = (
                extract_question_block(
                    document,
                    number,
                    question_meta,
                    digit_icon_map,
                )
            )

            answer_index = (
                answers.get(number)
            )

            question_text = (
                normalizer
                .join_all_prose_lines(
                    raw[
                        "raw_question_lines"
                    ]
                )
            )

            choices = [
                normalizer
                .join_all_prose_lines(
                    lines
                )
                for lines
                in raw[
                    "raw_choice_lines"
                ]
            ]

            questions.append(
                {
                    "number": number,
                    "source_page": raw[
                        "source_page"
                    ],
                    "column": raw[
                        "column"
                    ],
                    "passage_group_id": (
                        question_to_group.get(
                            number
                        )
                    ),
                    "question": (
                        question_text
                    ),
                    "choices": choices,
                    "answer": (
                        CIRCLED[
                            answer_index - 1
                        ]
                        if answer_index
                        is not None
                        else None
                    ),
                    "answer_index": (
                        answer_index
                    ),
                    "explanation": (
                        explanations.get(
                            number
                        )
                    ),
                }
            )

        validation = validate_result(
            passage_groups,
            questions,
            question_numbers,
        )

        return {
            "version": "v0.2.1",
            "source_file": (
                pdf_path.name
            ),
            "scope": (
                "1~20번 전체 + "
                "boundary-only normalization v2 + "
                "잔여 띄어쓰기/산문 분절 보정"
            ),
            "normalization": {
                "engine": (
                    normalizer
                    .engine_name
                ),
                "policy": (
                    "문장 전체를 재띄어쓰기하지 않고 "
                    "PDF 물리 줄 경계에서만 붙임/띄움 판단"
                ),
                "explanation_policy": (
                    "텍스트와 ①~⑤ 이미지 아이콘을 "
                    "좌표 순으로 한 baseline에 재조립"
                ),
                "passage_policy": (
                    "오른쪽 마진까지 찬 물리 줄바꿈만 연결하고 "
                    "시구/대사/구조적 줄바꿈은 최대한 보존"
                ),
            },
            "document_structure": {
                "question_pages": (
                    answer_start_page
                ),
                "answer_pages": (
                    len(document)
                    - answer_start_page
                ),
                "passage_groups": (
                    len(passage_groups)
                ),
            },
            "passage_groups": (
                passage_groups
            ),
            "questions": questions,
            "validation": validation,
            "known_limitations": [
                (
                    "<보기>는 아직 문제문 안에 포함되며 "
                    "별도 block 분리는 V0.3에서 진행"
                ),
                (
                    "이미지 자체의 crop/저장은 V0.4에서 진행"
                ),
                (
                    "image_only 지문 그룹은 needs_image_processing=true로 표시"
                ),
                (
                    "다른 출판사/사이트 PDF는 "
                    "컬럼/문항 마커 규칙 추가가 필요할 수 있음"
                ),
            ],
        }

    finally:
        document.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "국어 문제 PDF -> "
            "전체 구조화 JSON V0.2.2"
        )
    )

    parser.add_argument(
        "pdf",
        type=Path,
        help="분석할 PDF 파일",
    )

    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path(
            "v0_2_2_result.json"
        ),
        help=(
            "저장할 JSON "
            "(기본: v0_2_2_result.json)"
        ),
    )

    parser.add_argument(
        "-q",
        "--questions",
        nargs="+",
        type=int,
        default=list(
            range(1, 21)
        ),
        help=(
            "추출할 문제 번호 "
            "(기본: 1~20)"
        ),
    )

    parser.add_argument(
        "--no-kiwi",
        action="store_true",
        help=(
            "Kiwi 경계 판별을 끄고 "
            "fallback만 사용"
        ),
    )

    args = parser.parse_args()

    if not args.pdf.exists():
        raise SystemExit(
            "PDF 파일을 찾을 수 없습니다: "
            f"{args.pdf}"
        )

    if (
        not args.no_kiwi
        and Kiwi is None
    ):
        print(
            "[경고] kiwipiepy 미설치. "
            "fallback으로 실행합니다."
        )
        print(
            "권장 설치: "
            "pip install kiwipiepy"
        )
        print()

    result = parse_v0_2_2(
        args.pdf,
        sorted(
            set(args.questions)
        ),
        use_kiwi=(
            not args.no_kiwi
        ),
    )

    args.output.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    validation = (
        result["validation"]
    )

    print("=" * 76)
    print(
        "V0.2.2 전체 문제 구조화 완료"
    )
    print("=" * 76)
    print(f"입력 : {args.pdf}")
    print(
        f"출력 : "
        f"{args.output.resolve()}"
    )
    print(
        "Normalizer : "
        f"{result['normalization']['engine']}"
    )
    print()
    print(
        "문제 수   : "
        f"{validation['question_count']} / "
        f"{validation['expected_question_count']}"
    )
    print(
        "지문 그룹 : "
        f"{validation['passage_group_count']}"
    )
    print(
        "검증 상태 : "
        f"{validation['status']}"
    )

    if validation["issues"]:
        print()
        print("[ERROR / 구조 문제]")

        for issue in validation[
            "issues"
        ]:
            print(f"- {issue}")

    if validation["warnings"]:
        print()
        print("[텍스트 품질 경고]")

        for warning in validation[
            "warnings"
        ]:
            print(f"- {warning}")

    if (
        not validation["issues"]
        and not validation["warnings"]
    ):
        print()
        print(
            "구조 및 주요 텍스트 품질 검사를 통과했습니다."
        )

    print()
    print("[문제 요약]")

    for question in result[
        "questions"
    ]:
        number = question[
            "number"
        ]
        answer = (
            question.get(
                "answer"
            )
            or "?"
        )

        print(
            f"{number:>2}번 | "
            f"그룹 "
            f"{question.get('passage_group_id')} | "
            f"정답 {answer} | "
            f"{question.get('question', '')[:55]}"
        )


if __name__ == "__main__":
    main()
