#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
V0.2 - 국어 문제 PDF 전체 구조화 파서
=====================================

목표
----
- 문제 1~20번 전체 추출
- 2단 편집 PDF의 좌/우 컬럼 순서 처리
- 페이지를 넘어가는 지문/해설 연결
- 문제 ↔ 지문 그룹 자동 연결
- ①~⑤ 선택지 자동 추출
- 정답/해설 자동 매칭
- PDF Fragment Repair
- Kiwi 한국어 띄어쓰기 보정
- punctuation / 괄호 / 인용부호 경계 후처리
- 실행 후 자동 검증 리포트 생성

현재 V0.2는 첨부한 '최다빈출 공략' 계열 PDF 구조를 기준으로 작성했습니다.

필요 패키지
-----------
    pip install pymupdf kiwipiepy

실행
----
    python v0_2_pdf_parser.py "원본.pdf"

출력 파일 지정
--------------
    python v0_2_pdf_parser.py "원본.pdf" -o v0_2_result.json

특정 문제만 디버깅
------------------
    python v0_2_pdf_parser.py "원본.pdf" -q 13 14 15 16

Kiwi 없이 구조만 테스트
-----------------------
    python v0_2_pdf_parser.py "원본.pdf" --no-kiwi
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF

try:
    from kiwipiepy import Kiwi
except ImportError:
    Kiwi = None


CIRCLED = "①②③④⑤"

# Kiwi가 국어/문학 문맥에서 간혹 잘못 띄울 수 있는 용어.
DOMAIN_TERMS = [
    "영탄적",
    "색채어",
    "관조적",
]

SAFE_LINE_SUFFIX_FRAGMENTS = {
    "다", "서", "며", "고", "는", "은", "을", "를",
    "이", "가", "의", "로", "와", "과", "도", "만",
    "께", "게", "듯", "때", "지", "면", "니", "요",
    "데", "라", "나",
}

SECTION_LABEL_RE = re.compile(r"^\([가-힣A-Za-z0-9]+\)$")
QUESTION_HEADER_RE = re.compile(r"^(\d+)\.$")
ANSWER_HEADER_RE = re.compile(r"^(\d+)\)\s*\[정답\]$")


class TextNormalizer:
    def __init__(self, use_kiwi: bool = True) -> None:
        self.kiwi = None

        if use_kiwi and Kiwi is not None:
            self.kiwi = Kiwi()

            for term in DOMAIN_TERMS:
                try:
                    self.kiwi.add_user_word(term, "NNG", 0)
                except Exception:
                    # Kiwi 버전에 따라 사용자 단어 API 동작이 다를 수 있으므로
                    # 아래의 후처리 규칙이 한 번 더 보호한다.
                    pass

    @property
    def engine_name(self) -> str:
        if self.kiwi is not None:
            return (
                "PDF fragment repair + "
                "kiwipiepy.Kiwi.space + "
                "punctuation/domain post rules"
            )

        return (
            "PDF fragment repair + "
            "rule-based fallback + punctuation post rules"
        )

    @staticmethod
    def repair_prose_linewraps(text: str) -> str:
        """
        문제문/선택지/해설의 물리적 PDF 행갈이를 제거한다.

        예:
            흐
            름에
        ->  흐름에

        각 원본 라인 안에 존재하는 정상 공백은 보존하고,
        라인과 라인 사이만 공백 없이 이어 붙인다.
        실제 띄어쓰기는 이후 Kiwi가 복원한다.
        """
        if not text:
            return ""

        lines: list[str] = []

        for line in text.splitlines():
            line = re.sub(r"[ \t]+", " ", line.strip())

            if line:
                lines.append(line)

        return "".join(lines)

    @staticmethod
    def _repair_domain_terms(text: str) -> str:
        for term in DOMAIN_TERMS:
            # "영탄적" -> 영\s*탄\s*적
            pattern = r"\s*".join(re.escape(ch) for ch in term)
            text = re.sub(pattern, term, text)

        return text

    @staticmethod
    def _post_spacing_rules(text: str) -> str:
        """
        형태소 분석 후에도 간혹 붙는 활용형을 보완한다.
        """
        text = re.sub(r"하려\s*하고", "하려 하고", text)
        text = re.sub(r"하려\s*한다", "하려 한다", text)
        text = re.sub(r"하지\s*않", "하지 않", text)
        text = re.sub(r"않은\s*것", "않은 것", text)

        return text

    @staticmethod
    def _cleanup_punctuation(text: str) -> str:
        """
        V0.1.1에서 남았던 경계 공백 문제를 처리한다.

        예:
            있다.(나)에서       -> 있다. (나)에서
            강조하며,(나)에는   -> 강조하며, (나)에는
            결국‘그늘에서’      -> 결국 ‘그늘에서’
        """
        text = re.sub(r"[ \t]+", " ", text)

        # 문장부호 앞 공백 제거
        text = re.sub(r"\s+([,.!?;:%)\]}>])", r"\1", text)

        # 여는 괄호 바로 뒤의 불필요한 공백 제거
        text = re.sub(r"([(\[<{])\s+", r"\1", text)

        # 따옴표 내부 가장자리 공백 제거
        text = re.sub(r"([‘“])\s+", r"\1", text)
        text = re.sub(r"\s+([’”])", r"\1", text)

        # 마침표/물음표/느낌표 뒤 새 문장이 붙은 경우
        text = re.sub(
            r"([.!?])([가-힣A-Za-z])",
            r"\1 \2",
            text,
        )

        # 문장부호 뒤 (가), (나) 등의 구분자가 붙은 경우
        text = re.sub(
            r"([.!?,;:])(\([가-힣A-Za-z0-9]+\))",
            r"\1 \2",
            text,
        )

        # "결국‘그늘에서’" 같은 PDF 경계 오류
        # 닫는 따옴표 뒤 조사("‘자연’은")는 건드리지 않는다.
        text = re.sub(
            r"([가-힣A-Za-z0-9])([‘“])",
            r"\1 \2",
            text,
        )

        return text.strip()

    @staticmethod
    def _fallback_spacing(text: str) -> str:
        """
        Kiwi 미설치 시 최소 fallback.
        실제 사용에서는 kiwipiepy 설치를 권장한다.
        """
        replacements = {
            "사용 하고": "사용하고",
            "있 다.": "있다.",
            "있 다": "있다",
            "대 상": "대상",
            "화 자": "화자",
            "공 통점": "공통점",
            "성찰 을": "성찰을",
            "없으므 로": "없으므로",
            "감정과 는": "감정과는",
            "거리 를": "거리를",
            "태도 에": "태도에",
            "짐) 를": "짐)를",
            "않은것": "않은 것",
        }

        for before, after in replacements.items():
            text = text.replace(before, after)

        return text

    def normalize_prose(self, text: str) -> str:
        text = self.repair_prose_linewraps(text)

        if not text:
            return ""

        if self.kiwi is not None:
            try:
                text = self.kiwi.space(text)
            except Exception:
                text = self._fallback_spacing(text)
        else:
            text = self._fallback_spacing(text)

        text = self._repair_domain_terms(text)
        text = self._post_spacing_rules(text)
        text = self._cleanup_punctuation(text)

        return text

    @staticmethod
    def _should_join_passage_lines(left: str, right: str) -> bool:
        """
        문학 지문은 원래의 행갈이가 중요할 수 있으므로
        명백히 잘린 단어만 제한적으로 복원한다.
        """
        left = left.rstrip()
        right = right.lstrip()

        if not left or not right:
            return False

        if (
            SECTION_LABEL_RE.fullmatch(left)
            or SECTION_LABEL_RE.fullmatch(right)
        ):
            return False

        if left in {
            "<보기>",
            "※ 다음 글을 읽고 물음에 답하시오.",
            "※ 다음 글을 읽고, 물음에 답하시오.",
        }:
            return False

        if right in {"<보기>", "(중략)", "<중략>"}:
            return False

        if re.search(r"[.!?。！？…」』”’)]$", left):
            return False

        # 시의 반복 행 보호
        if left == right:
            return False

        # "것입니" + "다", "그늘에" + "서"
        if right in SAFE_LINE_SUFFIX_FRAGMENTS:
            return True

        if (
            len(right) <= 2
            and re.fullmatch(r"[가-힣]+", right)
        ):
            endings = (
                "다", "서", "고", "며", "는", "은", "을", "를",
                "로", "와", "과", "도", "만", "면", "니", "요",
            )

            if right.endswith(endings):
                return True

        return False

    def normalize_passage(self, text: str) -> str:
        """
        V0.2에서도 지문은 보수적으로 정규화한다.
        시/고전/극 대본 등 원문 자체의 줄바꿈을 과도하게
        변경하지 않기 위해 전체 Kiwi spacing은 적용하지 않는다.
        """
        raw_lines = [
            line.rstrip()
            for line in text.splitlines()
            if line.strip()
        ]

        if not raw_lines:
            return ""

        result: list[str] = []
        i = 0

        while i < len(raw_lines):
            current = raw_lines[i].strip()

            while i + 1 < len(raw_lines):
                nxt = raw_lines[i + 1].strip()

                if not self._should_join_passage_lines(
                    current,
                    nxt,
                ):
                    break

                current += nxt
                i += 1

            result.append(current)
            i += 1

        return "\n".join(result).strip()


# ---------------------------------------------------------------------------
# PDF 기본 유틸
# ---------------------------------------------------------------------------

def get_line_records(
    page: fitz.Page,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    for block in page.get_text("dict")["blocks"]:
        if block["type"] != 0:
            continue

        for line in block["lines"]:
            text = "".join(
                span["text"]
                for span in line["spans"]
            ).strip()

            if text:
                records.append(
                    {
                        "text": text,
                        "bbox": fitz.Rect(line["bbox"]),
                    }
                )

    return records


def get_image_instances(
    page: fitz.Page,
) -> list[dict[str, Any]]:
    """
    PDF 내부 이미지와 위치를 반환한다.
    동일 이미지/좌표가 PDF 내부 참조 때문에 중복되는 경우 제거한다.
    """
    result: list[dict[str, Any]] = []
    seen_xrefs: set[int] = set()
    seen_positions: set[tuple[Any, ...]] = set()

    for info in page.get_images(full=True):
        xref = info[0]

        if xref in seen_xrefs:
            continue

        seen_xrefs.add(xref)

        try:
            image_bytes = page.parent.extract_image(xref)["image"]
        except Exception:
            pix = fitz.Pixmap(page.parent, xref)
            image_bytes = pix.tobytes("png")

        image_hash = hashlib.md5(
            image_bytes
        ).hexdigest()

        for rect in page.get_image_rects(xref):
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
    return 0 if x < page.rect.width / 2 else 1


def get_column_bounds(
    page: fitz.Page,
    column: int,
) -> tuple[float, float]:
    """
    이 PDF의 2단 레이아웃을 좌/우 컬럼으로 분리한다.
    """
    middle = page.rect.width / 2

    if column == 0:
        return 45.0, middle - 6.0

    return middle + 6.0, page.rect.width - 45.0


def is_page_noise(
    text: str,
    bbox: fitz.Rect,
) -> bool:
    """
    페이지 공통 헤더/푸터/저작권 안내 등
    문제/지문/해설 데이터가 아닌 영역 제거.
    """
    text = text.strip()

    if text.startswith("[최다빈출 공략]"):
        return True

    if text == "비상(강호영)":
        return True

    if re.fullmatch(r"I\d[\d-]+", text):
        return True

    if re.fullmatch(r"-\s*\d+\s*-", text):
        return True

    # 정답/해설 페이지 하단 법적 고지
    if text.startswith("◇「콘텐츠산업 진흥법"):
        return True

    if text.startswith("1) 제작연월일"):
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


def get_ordered_regions(
    document: fitz.Document,
    page_indices: range | list[int],
) -> list[dict[str, Any]]:
    """
    2단 PDF를 사람이 읽는 순서로 정렬한다.

        page 1 left
        page 1 right
        page 2 left
        page 2 right
        ...

    페이지/컬럼을 넘어가는 지문과 해설을 연결하기 위한 핵심 로직.
    """
    regions: list[dict[str, Any]] = []

    for page_index in page_indices:
        page = document[page_index]
        all_lines = get_line_records(page)

        for column in (0, 1):
            left, right = get_column_bounds(
                page,
                column,
            )

            lines = [
                line
                for line in all_lines
                if (
                    left
                    <= line["bbox"].x0
                    < right
                )
                and not is_page_noise(
                    line["text"],
                    line["bbox"],
                )
            ]

            lines.sort(
                key=lambda line: (
                    line["bbox"].y0,
                    line["bbox"].x0,
                )
            )

            regions.append(
                {
                    "page_index": page_index,
                    "column": column,
                    "lines": lines,
                }
            )

    return regions


def find_answer_start_page(
    document: fitz.Document,
) -> int:
    """
    '1) [정답]'이 처음 나타나는 페이지를 자동 탐색한다.
    반환값은 0-based page index.
    """
    for page_index, page in enumerate(document):
        for line in get_line_records(page):
            if re.fullmatch(
                r"1\)\s*\[정답\]",
                line["text"],
            ):
                return page_index

    raise RuntimeError(
        "정답/해설 시작 페이지를 찾지 못했습니다."
    )


# ---------------------------------------------------------------------------
# ①~⑤ 아이콘 매핑
# ---------------------------------------------------------------------------

def get_question_headers(
    page: fitz.Page,
) -> list[tuple[int, fitz.Rect, int]]:
    result: list[tuple[int, fitz.Rect, int]] = []

    for line in get_line_records(page):
        match = QUESTION_HEADER_RE.fullmatch(
            line["text"]
        )

        if match:
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
    first_question_page: fitz.Page,
) -> dict[str, int]:
    """
    1번 문제의 ①~⑤ 작은 이미지의 MD5를 기준으로
    문서 전체의 선택지/정답 번호를 판별한다.
    """
    headers = get_question_headers(
        first_question_page
    )

    first = next(
        item
        for item in headers
        if item[0] == 1
    )

    _, question_box, column = first

    end_candidates = [
        bbox.y0
        for number, bbox, col in headers
        if (
            col == column
            and bbox.y0 > question_box.y0
        )
    ]

    end_y = min(
        end_candidates
        or [first_question_page.rect.height - 50]
    )

    left, right = get_column_bounds(
        first_question_page,
        column,
    )

    icons = [
        image
        for image in get_image_instances(
            first_question_page
        )
        if (
            question_box.y0
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
            "1번 문제에서 ①~⑤ 아이콘 5개를 찾지 못했습니다."
        )

    icons = icons[:5]

    return {
        image["hash"]: index + 1
        for index, image in enumerate(icons)
    }


# ---------------------------------------------------------------------------
# 지문 그룹 추출
# ---------------------------------------------------------------------------

def parse_passage_groups(
    document: fitz.Document,
    question_end_page: int,
    normalizer: TextNormalizer,
) -> list[dict[str, Any]]:
    """
    '※ 다음 글을 읽고...'를 새로운 지문 그룹의 시작으로 보고,
    뒤에 등장하는 문제 번호를 해당 지문 그룹에 연결한다.

    2단/페이지 넘김도 get_ordered_regions()의 읽기 순서를 이용해 처리.
    """
    groups: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    collecting_passage = False

    regions = get_ordered_regions(
        document,
        list(range(question_end_page)),
    )

    for region in regions:
        page_number = region["page_index"] + 1

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
                    "source_pages": {page_number},
                    "raw_lines": [],
                }

                collecting_passage = True
                continue

            question_match = (
                QUESTION_HEADER_RE.fullmatch(text)
            )

            if question_match:
                if current is not None:
                    number = int(
                        question_match.group(1)
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

                    current["source_pages"].add(
                        page_number
                    )

                collecting_passage = False
                continue

            if (
                current is not None
                and collecting_passage
            ):
                current["raw_lines"].append(text)
                current["source_pages"].add(
                    page_number
                )

    if current is not None:
        groups.append(current)

    output: list[dict[str, Any]] = []

    for group in groups:
        raw_text = "\n".join(
            group["raw_lines"]
        ).strip()

        output.append(
            {
                "id": group["id"],
                "question_numbers": (
                    group["question_numbers"]
                ),
                "source_pages": sorted(
                    group["source_pages"]
                ),
                "raw_text": raw_text,
                "normalized_text": (
                    normalizer.normalize_passage(
                        raw_text
                    )
                ),
            }
        )

    return output


# ---------------------------------------------------------------------------
# 문제 추출
# ---------------------------------------------------------------------------

def build_question_meta(
    document: fitz.Document,
    question_end_page: int,
) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}

    for page_index in range(
        question_end_page
    ):
        page = document[page_index]

        for (
            number,
            bbox,
            column,
        ) in get_question_headers(page):
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
    anchors: list[fitz.Rect] = []

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
            anchors.append(
                line["bbox"]
            )

    return anchors


def extract_question_block(
    document: fitz.Document,
    question_number: int,
    question_meta: dict[int, dict[str, Any]],
    digit_icon_map: dict[str, int],
) -> dict[str, Any]:
    meta = question_meta[question_number]
    page = document[meta["page_index"]]
    question_box = meta["bbox"]
    column = meta["column"]

    left, right = get_column_bounds(
        page,
        column,
    )

    # 현재 문제의 끝:
    # 같은 컬럼의 다음 문제 / 다음 새 지문 / 페이지 하단 중 가장 빠른 곳.
    end_candidates: list[float] = [
        page.rect.height - 50
    ]

    for (
        other_number,
        other_box,
        other_column,
    ) in get_question_headers(page):
        if (
            other_column == column
            and other_box.y0
            > question_box.y0
        ):
            end_candidates.append(
                other_box.y0
            )

    for anchor in get_passage_anchors(
        page,
        column,
    ):
        if anchor.y0 > question_box.y0:
            end_candidates.append(
                anchor.y0
            )

    end_y = min(end_candidates)

    page_lines = [
        line
        for line in get_line_records(page)
        if (
            left
            <= line["bbox"].x0
            < right
        )
        and (
            question_box.y0 - 1
            <= line["bbox"].y0
            < end_y
        )
        and not is_page_noise(
            line["text"],
            line["bbox"],
        )
    ]

    # ①~⑤ 이미지 찾기
    candidates_by_number: dict[
        int,
        list[dict[str, Any]],
    ] = defaultdict(list)

    for image in get_image_instances(page):
        rect = image["rect"]

        if image["hash"] not in digit_icon_map:
            continue

        if not (
            left <= rect.x0 < right
        ):
            continue

        if not (
            question_box.y0
            < rect.y0
            < end_y
        ):
            continue

        if (
            rect.width >= 20
            or rect.height >= 20
        ):
            continue

        choice_number = digit_icon_map[
            image["hash"]
        ]

        candidates_by_number[
            choice_number
        ].append(image)

    markers: dict[
        int,
        dict[str, Any],
    ] = {}

    for choice_number in range(1, 6):
        candidates = candidates_by_number.get(
            choice_number,
            [],
        )

        if not candidates:
            raise RuntimeError(
                f"{question_number}번 문제에서 "
                f"{CIRCLED[choice_number - 1]} "
                "선택지 아이콘을 찾지 못했습니다."
            )

        # 현재 문제 영역에서 가장 먼저 등장하는 동일 번호 아이콘 선택
        markers[choice_number] = min(
            candidates,
            key=lambda image: (
                image["rect"].y0,
                image["rect"].x0,
            ),
        )

    first_choice_y = min(
        marker["rect"].y0
        for marker in markers.values()
    )

    # 문제문 + <보기> 등 선택지 이전의 모든 구조
    stem_lines = [
        line
        for line in page_lines
        if line["bbox"].y0
        < first_choice_y - 3
        and line["text"]
        != f"{question_number}."
        and not line["text"].startswith(
            f"zb{question_number}"
        )
    ]

    stem_lines.sort(
        key=lambda line: (
            line["bbox"].y0,
            line["bbox"].x0,
        )
    )

    stem_text = "\n".join(
        line["text"]
        for line in stem_lines
    )

    # 선택지 추출
    choices: list[str] = []

    for choice_number in range(1, 6):
        current_rect = markers[
            choice_number
        ]["rect"]

        next_marker = markers.get(
            choice_number + 1
        )

        y_start = current_rect.y0 - 4
        y_end = end_y
        x_start = current_rect.x1 + 1
        x_end = right

        if next_marker is not None:
            next_rect = next_marker["rect"]

            # ① ②
            # ③ ④
            # ⑤
            # 형태의 2열 선택지 대응
            if (
                abs(
                    next_rect.y0
                    - current_rect.y0
                )
                <= 5
                and next_rect.x0
                > current_rect.x0
            ):
                x_end = next_rect.x0 - 1

                lower_markers = [
                    markers[index]["rect"].y0
                    for index in range(
                        choice_number + 1,
                        6,
                    )
                    if (
                        markers[index]["rect"].y0
                        > current_rect.y0 + 5
                    )
                ]

                if lower_markers:
                    y_end = min(
                        lower_markers
                    ) - 3

            elif (
                next_rect.y0
                > current_rect.y0
            ):
                y_end = (
                    next_rect.y0 - 3
                )

        choice_lines = [
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

        choice_lines.sort(
            key=lambda line: (
                line["bbox"].y0,
                line["bbox"].x0,
            )
        )

        choices.append(
            "\n".join(
                line["text"]
                for line in choice_lines
            )
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
        "raw_question": stem_text,
        "raw_choices": choices,
    }


# ---------------------------------------------------------------------------
# 정답 / 해설 추출
# ---------------------------------------------------------------------------

def extract_answer_digits(
    document: fitz.Document,
    answer_start_page: int,
    digit_icon_map: dict[str, int],
) -> dict[int, int]:
    result: dict[int, int] = {}

    for page_index in range(
        answer_start_page,
        len(document),
    ):
        page = document[page_index]
        lines = get_line_records(page)
        images = get_image_instances(page)

        for line in lines:
            match = ANSWER_HEADER_RE.fullmatch(
                line["text"]
            )

            if not match:
                continue

            question_number = int(
                match.group(1)
            )
            answer_box = line["bbox"]

            candidates = []

            for image in images:
                if (
                    image["hash"]
                    not in digit_icon_map
                ):
                    continue

                rect = image["rect"]

                same_line = (
                    abs(
                        rect.y0
                        - answer_box.y0
                    )
                    <= 6
                )

                right_of_label = (
                    answer_box.x1 - 3
                    <= rect.x0
                    <= answer_box.x1 + 35
                )

                small_icon = (
                    rect.width < 20
                    and rect.height < 20
                )

                if (
                    same_line
                    and right_of_label
                    and small_icon
                ):
                    candidates.append(image)

            if candidates:
                selected = min(
                    candidates,
                    key=lambda image: abs(
                        image["rect"].x0
                        - answer_box.x1
                    ),
                )

                result[question_number] = (
                    digit_icon_map[
                        selected["hash"]
                    ]
                )

    return result


def extract_explanations(
    document: fitz.Document,
    answer_start_page: int,
) -> dict[int, str]:
    """
    정답/해설 영역 역시 2단 문서이므로
    page-left -> page-right 순으로 읽는다.

    이 방식으로 아래와 같은 경우도 연결된다.
    - 왼쪽 컬럼 하단에서 시작해서 오른쪽 컬럼 상단으로 넘어가는 해설
    - 다음 페이지까지 이어지는 해설
    """
    result_lines: dict[
        int,
        list[str],
    ] = {}

    current_question: int | None = None

    regions = get_ordered_regions(
        document,
        list(
            range(
                answer_start_page,
                len(document),
            )
        ),
    )

    for region in regions:
        for line in region["lines"]:
            text = line["text"]

            answer_match = (
                ANSWER_HEADER_RE.fullmatch(
                    text
                )
            )

            if answer_match:
                current_question = int(
                    answer_match.group(1)
                )

                result_lines[
                    current_question
                ] = []

                continue

            if current_question is None:
                continue

            if text.startswith("[해설]"):
                text = text[
                    len("[해설]"):
                ].lstrip()

            if text:
                result_lines[
                    current_question
                ].append(text)

    return {
        number: "\n".join(lines).strip()
        for number, lines
        in result_lines.items()
    }


# ---------------------------------------------------------------------------
# 검증
# ---------------------------------------------------------------------------

def validate_result(
    passage_groups: list[dict[str, Any]],
    questions: list[dict[str, Any]],
    expected_questions: list[int],
) -> dict[str, Any]:
    issues: list[str] = []

    found_numbers = sorted(
        question["number"]
        for question in questions
    )

    expected_sorted = sorted(
        expected_questions
    )

    if found_numbers != expected_sorted:
        issues.append(
            "문제 번호가 기대값과 일치하지 않습니다. "
            f"expected={expected_sorted}, "
            f"found={found_numbers}"
        )

    for question in questions:
        number = question["number"]

        if not question["question"]:
            issues.append(
                f"{number}번 문제문이 비어 있습니다."
            )

        if len(question["choices"]) != 5:
            issues.append(
                f"{number}번 선택지가 5개가 아닙니다."
            )

        for index, choice in enumerate(
            question["choices"],
            start=1,
        ):
            if not choice:
                issues.append(
                    f"{number}번 {CIRCLED[index - 1]} "
                    "선택지가 비어 있습니다."
                )

        if question["answer"] is None:
            issues.append(
                f"{number}번 정답을 찾지 못했습니다."
            )

        if not question["explanation"]:
            issues.append(
                f"{number}번 해설을 찾지 못했습니다."
            )

        if question[
            "passage_group_id"
        ] is None:
            issues.append(
                f"{number}번 지문 그룹 연결 실패."
            )

    groups_without_questions = [
        group["id"]
        for group in passage_groups
        if not group["question_numbers"]
    ]

    if groups_without_questions:
        issues.append(
            "문제가 연결되지 않은 지문 그룹: "
            f"{groups_without_questions}"
        )

    return {
        "status": (
            "PASS"
            if not issues
            else "WARN"
        ),
        "question_count": len(questions),
        "expected_question_count": len(
            expected_questions
        ),
        "passage_group_count": len(
            passage_groups
        ),
        "issues": issues,
    }


# ---------------------------------------------------------------------------
# 메인 파서
# ---------------------------------------------------------------------------

def parse_v0_2(
    pdf_path: Path,
    question_numbers: list[int],
    use_kiwi: bool = True,
) -> dict[str, Any]:
    document = fitz.open(pdf_path)
    normalizer = TextNormalizer(
        use_kiwi=use_kiwi
    )

    try:
        answer_start_page = (
            find_answer_start_page(document)
        )

        # 정답 페이지 이전이 문제지 영역
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

        question_to_group: dict[
            int,
            int,
        ] = {}

        for group in passage_groups:
            for number in group[
                "question_numbers"
            ]:
                question_to_group[
                    number
                ] = group["id"]

        question_meta = build_question_meta(
            document,
            question_end_page,
        )

        answers = extract_answer_digits(
            document,
            answer_start_page,
            digit_icon_map,
        )

        explanations = (
            extract_explanations(
                document,
                answer_start_page,
            )
        )

        questions: list[
            dict[str, Any]
        ] = []

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
                            "문제 번호를 PDF 본문에서 "
                            "찾지 못했습니다."
                        ),
                    }
                )
                continue

            raw = extract_question_block(
                document,
                number,
                question_meta,
                digit_icon_map,
            )

            answer_index = answers.get(
                number
            )

            raw_explanation = (
                explanations.get(number)
            )

            questions.append(
                {
                    "number": number,
                    "source_page": raw[
                        "source_page"
                    ],
                    "column": raw["column"],
                    "passage_group_id": (
                        question_to_group.get(
                            number
                        )
                    ),
                    "question": (
                        normalizer.normalize_prose(
                            raw["raw_question"]
                        )
                    ),
                    "choices": [
                        normalizer.normalize_prose(
                            choice
                        )
                        for choice
                        in raw["raw_choices"]
                    ],
                    "answer": (
                        CIRCLED[
                            answer_index - 1
                        ]
                        if (
                            answer_index
                            is not None
                        )
                        else None
                    ),
                    "answer_index": (
                        answer_index
                    ),
                    "explanation": (
                        normalizer.normalize_prose(
                            raw_explanation
                        )
                        if raw_explanation
                        else None
                    ),
                }
            )

        validation = validate_result(
            passage_groups,
            questions,
            question_numbers,
        )

        return {
            "version": "v0.2",
            "source_file": pdf_path.name,
            "scope": (
                "1~20번 전체 문제 + "
                "2단/페이지 넘김 처리 + "
                "punctuation 후처리"
            ),
            "normalization": {
                "engine": (
                    normalizer.engine_name
                ),
                "question_policy": (
                    "PDF 물리 행갈이를 먼저 복원한 뒤 "
                    "Kiwi로 문제문/선택지/해설 띄어쓰기 보정"
                ),
                "punctuation_policy": (
                    "문장부호 뒤 (가)/(나), "
                    "인용부호 경계 등 PDF 결합 오류 후처리"
                ),
                "passage_policy": (
                    "문학 원문의 행갈이는 최대한 보존하고 "
                    "명백한 단어 분절만 연결"
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
                    "V0.2는 20문제 전체의 텍스트 구조화를 "
                    "목표로 하며 이미지 자체의 crop/저장은 아직 하지 않음"
                ),
                (
                    "<보기>는 현재 문제문 내부 텍스트로 보존하며 "
                    "별도 block 타입 분리는 V0.3에서 진행"
                ),
                (
                    "표/이미지 중심 지문은 텍스트가 적게 추출될 수 있으며 "
                    "V0.3~V0.4에서 별도 구조화 예정"
                ),
                (
                    "시/고전/방언의 원문 표현 보호를 위해 "
                    "지문 전체에는 공격적인 Kiwi 띄어쓰기 교정을 적용하지 않음"
                ),
                (
                    "다른 출판사/사이트 PDF는 컬럼/문항 마커 규칙을 "
                    "추가해야 할 수 있음"
                ),
            ],
        }

    finally:
        document.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "국어 문제 PDF -> "
            "전체 1~20번 구조화 JSON V0.2"
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
            "v0_2_result.json"
        ),
        help=(
            "저장할 JSON 파일명 "
            "(기본: v0_2_result.json)"
        ),
    )

    parser.add_argument(
        "-q",
        "--questions",
        nargs="+",
        type=int,
        default=list(range(1, 21)),
        help=(
            "추출할 문제 번호 "
            "(기본: 1~20 전체)"
        ),
    )

    parser.add_argument(
        "--no-kiwi",
        action="store_true",
        help=(
            "Kiwi 띄어쓰기 보정을 끄고 "
            "구조 추출 위주로 테스트"
        ),
    )

    args = parser.parse_args()

    if not args.pdf.exists():
        raise SystemExit(
            f"PDF 파일을 찾을 수 없습니다: "
            f"{args.pdf}"
        )

    invalid_numbers = [
        number
        for number in args.questions
        if number < 1
    ]

    if invalid_numbers:
        raise SystemExit(
            "문제 번호는 1 이상이어야 합니다."
        )

    if (
        not args.no_kiwi
        and Kiwi is None
    ):
        print(
            "[경고] kiwipiepy가 설치되어 있지 않습니다."
        )
        print(
            "       fallback으로 실행하지만 "
            "텍스트 품질은 Kiwi 사용 시 더 좋습니다."
        )
        print(
            "       설치: pip install kiwipiepy"
        )
        print()

    result = parse_v0_2(
        args.pdf,
        sorted(
            set(args.questions)
        ),
        use_kiwi=not args.no_kiwi,
    )

    args.output.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    validation = result["validation"]

    print("=" * 72)
    print(
        "V0.2 전체 문제 구조화 완료"
    )
    print("=" * 72)
    print(f"입력 : {args.pdf}")
    print(
        f"출력 : {args.output.resolve()}"
    )
    print(
        f"Normalizer : "
        f"{result['normalization']['engine']}"
    )
    print()
    print(
        f"문제 수     : "
        f"{validation['question_count']} / "
        f"{validation['expected_question_count']}"
    )
    print(
        f"지문 그룹   : "
        f"{validation['passage_group_count']}"
    )
    print(
        f"검증 상태   : "
        f"{validation['status']}"
    )

    if validation["issues"]:
        print()
        print("[검증 경고]")

        for issue in validation["issues"]:
            print(f"- {issue}")

    else:
        print()
        print(
            "문제문 / 선택지 5개 / 정답 / "
            "해설 / 지문 그룹 연결이 모두 확인되었습니다."
        )

    print()
    print("[문제 요약]")

    for question in result["questions"]:
        number = question["number"]
        answer = question.get(
            "answer"
        ) or "?"

        print(
            f"{number:>2}번 | "
            f"지문 그룹 {question.get('passage_group_id')} | "
            f"정답 {answer} | "
            f"{question.get('question', '')[:55]}"
        )


if __name__ == "__main__":
    main()
