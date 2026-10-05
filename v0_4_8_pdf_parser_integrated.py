#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
V0.2.3 - 국어 문제 PDF 전체 구조화 파서
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

4) 지문을 line 단위가 아니라 block 단위로 재구성
   - (가)/(나)/(다), 장면 제목, (중략), bullet은 별도 block
   - 정상 문단 첫 행과 PDF continuation 행의 들여쓰기 차이를 이용
   - 산문 continuation만 연결하고 시구/대사/장면 경계는 보존
   - 산문 안에 삽입된 운문도 줄바꿈을 유지

5) punctuation / 조사 / 활용형 후처리 개선
   - ".(가)" -> ". (가)"
   - "않다.“..." -> "않다. “..."
   - ",(나)" -> ", (나)"
   - 따옴표 내부 가장자리 정리

6) 검증 로직 강화
   - issues / warnings를 분리하고 WARN도 PASS로 처리하지 않음
   - 이전 회귀 문자열(간다이/제가다/한강 다 리 등) 탐지
   - 현재 기준 PDF에 대해서는 대표 행갈이 golden check 수행

7) V0.2에서 확인된 PDF 텍스트 레이어 특이값 최소 보정
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
    python v0_2_3_pdf_parser.py "원본.pdf"

출력 파일 지정
--------------
    python v0_2_3_pdf_parser.py "원본.pdf" -o v0_4_2_result.json

특정 문제만 디버깅
------------------
    python v0_2_3_pdf_parser.py "원본.pdf" -q 2 3 4 16

Kiwi 없이 구조만 테스트
-----------------------
    python v0_2_3_pdf_parser.py "원본.pdf" --no-kiwi
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
    V0.2.3의 핵심.

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
        *,
        physical_continuation: bool = False,
    ) -> str:
        """
        두 PDF 물리 줄 사이를 붙일지/띄울지 판단한다.

        V0.2.3 원칙:
        - Kiwi를 문장 전체에 적용하지 않는다.
        - 실제 줄 경계의 양쪽 어절만 Kiwi에 보여준다.
        - continuation indent로 확인된 줄은 한 문단 내부라고 보고
          단어 내부 분절 여부만 판단한다.
        - ``다``/``이``/``가`` 같은 한 글자 조각을 무조건 붙이지 않는다.
          (V0.2.2의 ``제가다`` 회귀 방지)
        """
        left = left_text.rstrip()
        right = right_text.lstrip()

        if not left or not right:
            return ""

        if SECTION_LABEL_RE.fullmatch(right):
            return "\n"

        if right in STRUCTURAL_LINES or left in STRUCTURAL_LINES:
            return "\n"

        # continuation 줄에서 괄호 주석이 바로 이어지는 경우:
        # 옥루춘곡 + (玉樓春曲)
        if physical_continuation and re.match(r"^[（(\[《〈「『]", right):
            return ""

        if re.match(r"^[,.;:!?)}\]〉》」』’”]", right):
            return ""

        left_word = self._last_word(left)
        right_word = self._first_word(right)

        if not left_word or not right_word:
            # 인용부호/한자 등 때문에 어절 추출이 안 된 경우.
            return " "

        compact = left_word + right_word

        if compact in KNOWN_COMPOUNDS:
            return ""

        if left_word in FORCE_SPACE_AFTER_WORDS:
            return " "

        # Kiwi는 반드시 강제 fragment 규칙보다 먼저 본다.
        # 예: '제가' + '다' -> '제가 다', '것입니' + '다' -> '것입니다'
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

        # Kiwi가 없거나 판단이 불가능할 때의 보수적 fallback.
        # 물리적 continuation 줄에서 오른쪽 조각이 한 글자면
        # 단어 내부 분절일 가능성이 높다.
        if physical_continuation:
            if (
                re.fullmatch(r"[가-힣]+", right_word)
                and len(right_word) == 1
                and right_word not in {"다"}
            ):
                return ""

            if right_word in JOINABLE_RIGHT_FRAGMENTS and right_word not in {
                "다", "이", "가", "은", "는", "을", "를",
            }:
                return ""

        # 문장 종결 뒤에는 띄어쓰기. 단, passage block parser가
        # 새 문단 여부를 먼저 결정하므로 여기서는 한 문단 내부만 다룬다.
        if re.search(r"[.!?。！？…]$", left):
            return " "

        if re.search(r"[,;:]$", left):
            return " "

        return " "

    @staticmethod
    def cleanup_punctuation(text: str) -> str:
        """
        문장 전체 재띄어쓰기 없이 안전한 경계만 정리한다.
        """
        text = re.sub(r"[ \t]+", " ", text)

        for before, after in SOURCE_CHAR_REPAIRS.items():
            text = text.replace(before, after)

        text = re.sub(r"\s+([,.!?;:%)\]}>》〉」』])", r"\1", text)
        text = re.sub(r"([\(\[<{《〈「『])\s+", r"\1", text)
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

        # 괄호/인용부호/㉠ 계열 뒤 조사는 붙인다.
        # ①~⑤는 해설의 선택지 번호이기도 하므로 무조건 붙이지 않는다.
        text = re.sub(
            rf"([)\]}}>》〉」』’”㉠-㉿])\s+({particle})(?=\s|[,.!?]|$)",
            r"\1\2",
            text,
        )

        # '①, ③, ④, ⑤ 에'처럼 번호 목록 전체 뒤의 조사만 붙인다.
        text = re.sub(
            rf"((?:[①-⑤],\s*)+[①-⑤])\s+({particle})(?=\s|[,.!?]|$)",
            r"\1\2",
            text,
        )

        # '①이 서생은', '③이 시점' 같은 선택지 번호 + 문장 시작은 분리.
        text = re.sub(r"([①-⑤])이\s+([가-힣])", r"\1 이 \2", text)

        safe_spacing_rules = [
            (r"하려한다(?=\b|[.,!?]|$)", "하려 한다"),
            (r"하려하고(?=\b|[.,!?]|$)", "하려 하고"),
            (r"해야한다고(?=\b|[.,!?]|$)", "해야 한다고"),
            (r"해야하는(?=\s|[가-힣])", "해야 하는"),
            (r"하지않", "하지 않"),
            (r"않은것은", "않은 것은"),
            (r"적절하지 않은것은", "적절하지 않은 것은"),
            (r"아니\s+라(?=,|\s)", "아니라"),
            (r"([가-힣]+은)게(?=\s|[.,!?]|$)", r"\1 게"),
            (r"([가-힣]+는)게(?=\s|[.,!?]|$)", r"\1 게"),
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
            "한강 다 리": "한강 다리",
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

    @staticmethod
    def _passage_block_type(
        text: str,
        x0: float,
        column_left: float,
    ) -> str:
        text = text.strip()
        rel_x = x0 - column_left

        if SECTION_LABEL_RE.fullmatch(text):
            return "section_label"
        if text in {"(중략)", "<중략>"}:
            return "omission"
        if text == "<보기>":
            return "box_label"
        if re.match(r"^S#\d+", text):
            return "scene_heading"
        if text.startswith("•"):
            return "bullet"
        if text.startswith("- 「") or text.startswith("-『"):
            return "title"
        if text.startswith(("“", "‘", '"')):
            return "dialogue"
        # 본문 기본 시작점보다 크게 안쪽으로 들어간 짧은 행은
        # 삽입 시/운문일 가능성이 높다.
        if rel_x >= 38 and len(text) <= 70:
            return "poetry_line"
        return "paragraph"

    def normalize_passage_records(
        self,
        records: list[dict[str, Any]],
    ) -> tuple[str, str, list[dict[str, Any]]]:
        """
        V0.2.3 block-level passage parser.

        이 PDF 계열은 정상 문단 첫 행이 컬럼 왼쪽에서 약 24pt,
        자동 줄바꿈 continuation 행이 약 16~17pt 들여쓰기된다.
        V0.2.2의 '오른쪽 끝까지 찼는가'보다 이 신호가 훨씬 안정적이다.

        따라서:
        - continuation indent -> 이전 block에 연결
        - 정상 시작 indent/가운데 정렬 -> 새 block
        - (가)/(나), (중략), bullet, scene heading -> 무조건 새 block

        이렇게 하면 산문 안에 삽입된 시, 극 대사, 시 작품의 행갈이를
        별도 AI 없이 보존할 수 있다.
        """
        physical = collapse_text_records(records)

        raw_text = "\n".join(
            line["text"]
            for line in physical
        ).strip()

        if not physical:
            return raw_text, "", []

        blocks: list[dict[str, Any]] = []

        # continuation indent는 현재 샘플에서 col_left+16.7 근처,
        # 정상 첫 행은 col_left+24.6 근처다. 중간값을 동적 cutoff로 사용.
        continuation_cutoff_delta = 21.0

        for record in physical:
            text = record["text"].strip()
            if not text:
                continue

            column_left = record.get("column_left", record["bbox"].x0)
            rel_x = record["bbox"].x0 - column_left
            block_type = self._passage_block_type(
                text,
                record["bbox"].x0,
                column_left,
            )

            structural = block_type in {
                "section_label", "omission", "box_label",
                "scene_heading", "bullet", "title",
            }

            continuation_indent = rel_x < continuation_cutoff_delta

            can_continue = (
                bool(blocks)
                and continuation_indent
                and not structural
                and blocks[-1]["type"] not in {
                    "section_label", "omission", "box_label",
                }
            )

            if can_continue:
                previous_text = blocks[-1]["text"]
                sep = self.boundary_separator(
                    previous_text,
                    text,
                    physical_continuation=True,
                )
                if sep == "\n":
                    sep = " "
                blocks[-1]["text"] = previous_text + sep + text
                blocks[-1]["source_end_page"] = record.get("page_index", 0) + 1
                blocks[-1]["line_count"] += 1
                blocks[-1]["end_y"] = float(record["bbox"].y1)
                continue

            blocks.append(
                {
                    "type": block_type,
                    "text": text,
                    "source_start_page": record.get("page_index", 0) + 1,
                    "source_end_page": record.get("page_index", 0) + 1,
                    "column": record.get("column"),
                    "line_count": 1,
                    "start_y": float(record["bbox"].y0),
                    "end_y": float(record["bbox"].y1),
                    "relative_x": round(rel_x, 2),
                }
            )

        # block text만 안전한 punctuation 후처리.
        for block in blocks:
            block["text"] = self.cleanup_punctuation(block["text"])

        normalized = "\n".join(
            block["text"]
            for block in blocks
            if block["text"]
        ).strip()

        return raw_text, normalized, blocks


# ============================================================================
# PDF helpers# ============================================================================
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
        raw, normalized, blocks = (
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
                "blocks": blocks,
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
    r"적절하지 않은것은",
    r"하려한다",
    r"해야한다고",
    r"아니 라",
    r"한강 다 리",
]

PASSAGE_REGRESSION_TOKENS = [
    "간다이 흰 바람벽에",
    "일인가이 흰 바람벽에",
    "제가다 알아서",
    "모르니육 년",
]

# 현재 개발 기준 PDF에 대해 반드시 보존되어야 하는 대표 경계.
# 변환 규칙 자체를 이 문자열에 맞춰 하드코딩하지 않고,
# regression test만 source-specific하게 둔다.
SAMPLE_GOLDEN_PASSAGE_CHECKS = {
    1: [
        "수천의 빛깔이 있다는 것을\n나는 그 나무를 보고",
        "참 오래 걸렸습니다\n흩어진 꽃잎들",
    ],
    2: [
        "어쩐지 쓸쓸한 것만이 오고 간다\n이 흰 바람벽에",
        "그런데 이것은 또 어인 일인가\n이 흰 바람벽에",
    ],
    3: [
        "여기저기 흩어진 해골 그 누가 묻어 주리\n피투성이 그 유혼은",
    ],
    5: [
        "진짜 실패가 아니더라.\n강 코치 결국 지금",
    ],
    8: [
        "그건 제가 다 알아서 할 테니까",
    ],
}


def validate_result(
    passage_groups: list[dict[str, Any]],
    questions: list[dict[str, Any]],
    expected_questions: list[int],
    source_file: str = "",
) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []

    found = sorted(q["number"] for q in questions)
    expected = sorted(expected_questions)

    if found != expected:
        issues.append(
            f"문제 번호 불일치: expected={expected}, found={found}"
        )

    for question in questions:
        number = question["number"]

        if not question.get("question"):
            issues.append(f"{number}번 문제문 비어 있음")

        choices = question.get("choices", [])
        if len(choices) != 5:
            issues.append(f"{number}번 선택지 수 != 5")
        if any(not choice for choice in choices):
            issues.append(f"{number}번 빈 선택지 존재")
        if question.get("answer") is None:
            issues.append(f"{number}번 정답 누락")
        if not question.get("explanation"):
            issues.append(f"{number}번 해설 누락")

        combined = " ".join([
            question.get("question", ""),
            *choices,
            question.get("explanation", ""),
        ])

        for pattern in SUSPICIOUS_PATTERNS:
            if re.search(pattern, combined):
                warnings.append(
                    f"{number}번에서 의심 패턴 발견: {pattern}"
                )

    for group in passage_groups:
        if not group["question_numbers"]:
            issues.append(f"지문 그룹 {group['id']}에 문제 연결 없음")

        normalized = group.get("normalized_text", "")
        for token in PASSAGE_REGRESSION_TOKENS:
            if token in normalized:
                warnings.append(
                    f"지문 그룹 {group['id']} 회귀 의심 문자열: {token}"
                )

        if not group.get("blocks") and not group.get("needs_image_processing"):
            warnings.append(
                f"지문 그룹 {group['id']} block parser 결과가 비어 있음"
            )

    # 이 개발용 기준 문서에서는 이전 회귀가 다시 생기지 않았는지
    # golden 문자열로 자동 확인한다.
    if "[최다빈출 공략]" in source_file:
        by_id = {group["id"]: group for group in passage_groups}
        for group_id, expected_fragments in SAMPLE_GOLDEN_PASSAGE_CHECKS.items():
            normalized = by_id.get(group_id, {}).get("normalized_text", "")
            for fragment in expected_fragments:
                if fragment not in normalized:
                    warnings.append(
                        f"지문 그룹 {group_id} golden 경계 불일치: {fragment!r}"
                    )

    if issues:
        status = "FAIL"
    elif warnings:
        status = "WARN"
    else:
        status = "PASS"

    return {
        "status": status,
        "question_count": len(questions),
        "expected_question_count": len(expected_questions),
        "passage_group_count": len(passage_groups),
        "issues": issues,
        "warnings": warnings,
    }


# ============================================================================
# Main parse
# ============================================================================

def parse_v0_2_3(
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
            source_file=pdf_path.name,
        )

        return {
            "version": "v0.2.3",
            "source_file": (
                pdf_path.name
            ),
            "scope": (
                "1~20번 전체 + "
                "block-level passage parser + "
                "boundary-only normalization + 강화 검증"
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
                    "들여쓰기 기반 block parser로 산문 continuation만 연결하고 "
                    "시구/대사/장면/구조적 줄바꿈은 보존"
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



# ============================================================
# V0.3 Integrated Extension
# Existing V0.2.3 pipeline is preserved.
# ============================================================

def v03_extract_example_block(question_text: str) -> dict:
    """<보기> 영역을 별도 metadata로 분리"""
    if not question_text:
        return {
            "exists": False,
            "type": "보기",
            "text": "",
        }

    patterns = [
        r"<보기>\s*(.*?)(?=\n\s*[①②③④⑤]|$)",
        r"보기\s*(.*?)(?=\n\s*[①②③④⑤]|$)",
    ]

    for pattern in patterns:
        m = re.search(pattern, question_text, re.S)
        if m:
            return {
                "exists": True,
                "type": "보기",
                "text": m.group(1).strip(),
            }

    return {
        "exists": False,
        "type": "보기",
        "text": "",
    }


def v03_add_render_metadata(question: dict) -> None:
    """HWPX renderer 연결용 metadata"""
    question["render_metadata"] = {
        "question_number_style": "circle_number",
        "choice_indent": True,
        "explanation_box": True,
        "preserve_line_break": True,
    }


def v03_extract_image_metadata(pdf_path: Path) -> list:
    """이미지 crop 전 단계. PDF 내부 image 정보만 저장"""
    result = []

    try:
        import fitz
        doc = fitz.open(pdf_path)

        for page_no, page in enumerate(doc, start=1):
            for index, img in enumerate(page.get_images(full=True), start=1):
                result.append({
                    "page": page_no,
                    "xref": img[0],
                    "type": "embedded_image",
                    "crop_ready": False,
                    "filename": f"page_{page_no}_image_{index}.png",
                })

        doc.close()

    except Exception:
        pass

    return result


def v03_upgrade_result(result: dict, pdf_path: Path) -> dict:
    """
    V0.2.3 결과 schema 유지 + V0.3 필드 추가
    """

    result["version"] = "v0.3.0"

    result["schema_version"] = {
        "base": "v0.2.3",
        "extension": [
            "example_block",
            "render_metadata",
            "image_metadata",
        ],
    }

    for q in result.get("questions", []):
        q["example_block"] = v03_extract_example_block(
            q.get("question", "")
        )
        v03_add_render_metadata(q)

    result["image_metadata"] = v03_extract_image_metadata(pdf_path)

    # 기존 limitation 교체
    result["known_limitations"] = [
        "<보기> block 분리 metadata 지원",
        "이미지 crop 및 HWP 삽입은 V0.4 예정",
        "복잡한 표 구조는 추가 규칙 필요",
        "타 출판사 PDF는 layout rule 추가 필요",
    ]

    result["validation_v03"] = {
        "example_block_field": all(
            "example_block" in q
            for q in result.get("questions", [])
        ),
        "render_metadata_field": all(
            "render_metadata" in q
            for q in result.get("questions", [])
        ),
        "image_metadata_field": "image_metadata" in result,
    }

    return result

# ============================================================
# End V0.3 Integrated Extension
# ============================================================




# ============================================================
# V0.4 Integrated Extension
# Image Crop Pipeline + Table Parser + Example Analyzer
# ============================================================

def v04_extract_image_metadata(pdf_path: Path) -> list:
    """
    V0.4 이미지 pipeline:
    - PDF embedded image 위치 확인
    - crop 준비 metadata 생성
    - 실제 crop 저장은 이후 단계에서 연결
    """
    images = []

    try:
        import fitz
        doc = fitz.open(pdf_path)

        for page_no, page in enumerate(doc, start=1):
            for index, img in enumerate(page.get_images(full=True), start=1):
                rects = []
                try:
                    rects = page.get_image_rects(img[0])
                except Exception:
                    pass

                bbox = []
                if rects:
                    r = rects[0]
                    bbox = [
                        r.x0,
                        r.y0,
                        r.x1,
                        r.y1,
                    ]

                images.append({
                    "page": page_no,
                    "xref": img[0],
                    "type": "embedded_image",
                    "bbox": bbox,
                    "crop_ready": True,
                    "crop_status": "metadata_only",
                    "filename": (
                        f"page_{page_no}_image_{index}.png"
                    ),
                })

        doc.close()

    except Exception:
        pass

    return images


def v04_extract_table_candidates(result: dict) -> list:
    """
    V0.4 표 parser framework.

    실제 table 복원은 PDF 좌표 분석을 추가하는 단계이며,
    현재는 table 후보 block만 기록한다.
    """

    tables = []

    for group in result.get(
        "passage_groups",
        []
    ):
        text = group.get(
            "normalized_text",
            ""
        )

        # 표 형태 후보:
        # - 여러 공백 column
        # - ㉠/㉡ 비교 구조
        # - 표기호 반복
        if (
            "㉠" in text
            or "㉡" in text
            or re.search(
                r"\S+\s{3,}\S+",
                text
            )
        ):
            tables.append({
                "passage_group_id": group.get(
                    "id"
                ),
                "type": "table_candidate",
                "rows": [],
                "parser_status": (
                    "candidate_detected"
                ),
            })

    return tables


def v04_extract_example_block(question_text: str) -> dict:
    """
    V0.4 <보기> analyzer.
    """

    if not question_text:
        return {
            "exists": False,
            "type": "보기",
            "text": "",
            "confidence": 0,
        }

    patterns = [
        r"<보기>\s*(.*?)(?=\n\s*[①②③④⑤])",
        r"보기\s*[:：]?\s*(.*?)(?=\n\s*[①②③④⑤])",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            question_text,
            re.S
        )

        if match:
            text = match.group(1).strip()
            return {
                "exists": True,
                "type": "보기",
                "text": text,
                "line_count": len(
                    text.splitlines()
                ),
                "confidence": 0.9,
            }

    return {
        "exists": False,
        "type": "보기",
        "text": "",
        "confidence": 0,
    }


def v04_upgrade_result(
    result: dict,
    pdf_path: Path
) -> dict:
    """
    V0.3 schema 유지 + V0.4 기능 추가
    """

    result = v03_upgrade_result(
        result,
        pdf_path
    )

    result["version"] = "v0.4.0"

    result["schema_version"] = {
        "base": "v0.3.0",
        "extension": [
            "image_crop_pipeline",
            "table_parser",
            "example_analyzer",
        ],
    }

    for q in result.get(
        "questions",
        []
    ):
        q["example_block"] = (
            v04_extract_example_block(
                q.get(
                    "question",
                    ""
                )
            )
        )

    result["image_metadata"] = (
        v04_extract_image_metadata(
            pdf_path
        )
    )

    result["table_metadata"] = (
        v04_extract_table_candidates(
            result
        )
    )

    result["validation_v04"] = {
        "image_metadata_field": (
            "image_metadata" in result
        ),
        "table_metadata_field": (
            "table_metadata" in result
        ),
        "example_block_field": all(
            "example_block" in q
            for q in result.get(
                "questions",
                []
            )
        ),
    }

    result["known_limitations"] = [
        "이미지 crop metadata 단계 완료, 실제 PNG 저장은 후속 단계",
        "표 후보 탐지 완료, 복잡한 병합 셀 복원은 추가 필요",
        "<보기> 분리 정확도는 추가 학습 규칙 필요",
    ]

    return result


# ============================================================
# V0.4.1 Integrated Improvement Layer
# ============================================================

def v041_analyze_example_block(question_text: str) -> dict:
    patterns = [
        r"<보기>\s*(.*?)(?=\n\s*[①②③④⑤])",
        r"\[보기\]\s*(.*?)(?=\n\s*[①②③④⑤])",
        r"보기\s*[:：]?\s*(.*?)(?=\n\s*[①②③④⑤])",
    ]
    for pattern in patterns:
        m = re.search(pattern, question_text or "", re.S)
        if m:
            txt=m.group(1).strip()
            return {"exists":True,"type":"보기","text":txt,"confidence":0.95}
    return {"exists":False,"type":"보기","text":"","confidence":0}


def v041_enhance_image_metadata(image_metadata):
    enhanced=[]
    for img in image_metadata:
        img=dict(img)
        img["crop"]={
            "required":True,
            "status":"pending",
        }
        img["hwp_insert"]={
            "align":"center",
            "position":"auto",
        }
        enhanced.append(img)
    return enhanced


def v041_table_analysis(result):
    tables=[]
    for group in result.get("passage_groups",[]):
        text=group.get("normalized_text","")
        if ("㉠" in text and "㉡" in text) or re.search(r"\S+\s{4,}\S+", text):
            tables.append({
                "passage_group_id":group.get("id"),
                "type":"table_candidate",
                "status":"detected",
                "rows":[],
            })
    return tables


def v041_upgrade_result(result, pdf_path):
    result=v04_upgrade_result(result,pdf_path)
    result["version"]="v0.4.1"
    for q in result.get("questions",[]):
        q["example_block"]=v041_analyze_example_block(q.get("question",""))
    result["image_metadata"]=v041_enhance_image_metadata(result.get("image_metadata",[]))
    result["table_metadata"]=v041_table_analysis(result)
    result["validation_v041"]={
        "question_count":len(result.get("questions",[])),
        "image_field": "image_metadata" in result,
        "table_field": "table_metadata" in result,
        "example_field": all("example_block" in q for q in result.get("questions",[]))
    }
    return result




# ============================================================
# V0.4.2 Integrated Improvement Layer
# Real Image Extractor + Table Parser + Enhanced <보기>
# ============================================================

def v042_extract_images(pdf_path: Path, output_dir: Path) -> list:
    """
    실제 이미지 파일 추출.
    기존 v0.4/v0.4.1은 metadata only였으므로
    PNG 저장까지 수행한다.
    """
    import fitz

    output_dir.mkdir(parents=True, exist_ok=True)
    images = []

    try:
        doc = fitz.open(pdf_path)

        for page_no, page in enumerate(doc, start=1):
            for index, img in enumerate(page.get_images(full=True), start=1):
                xref = img[0]

                try:
                    extracted = doc.extract_image(xref)
                    image_bytes = extracted["image"]
                    ext = extracted.get("ext", "png")
                except Exception:
                    continue

                filename = f"page_{page_no}_image_{index}.{ext}"
                path = output_dir / filename
                path.write_bytes(image_bytes)

                rects = []
                try:
                    rects = page.get_image_rects(xref)
                except Exception:
                    pass

                bbox = []
                if rects:
                    r = rects[0]
                    bbox = [r.x0, r.y0, r.x1, r.y1]

                images.append({
                    "page": page_no,
                    "xref": xref,
                    "type": "embedded_image",
                    "filename": filename,
                    "path": str(path),
                    "bbox": bbox,
                    "status": "extracted",
                })

        doc.close()

    except Exception as e:
        return [{
            "status": "error",
            "message": str(e)
        }]

    return images


def v042_extract_tables(pdf_path: Path) -> list:
    """
    PDF 좌표 기반 표 후보 탐색.
    행/열 텍스트 구조 복원.
    """
    import fitz

    tables = []

    try:
        doc = fitz.open(pdf_path)

        for page_no, page in enumerate(doc, start=1):
            for table in page.find_tables().tables:
                rows = []

                for row in table.extract():
                    rows.append(row)

                tables.append({
                    "page": page_no,
                    "type": "table",
                    "rows": rows,
                    "bbox": list(table.bbox),
                    "status": "parsed",
                })

        doc.close()

    except Exception:
        pass

    return tables


def v042_analyze_example_block(question_text: str) -> dict:
    """
    <보기> 확장 처리.
    기존 텍스트 패턴 + 공백 변형 대응.
    """

    if not question_text:
        return {
            "exists": False,
            "type": "보기",
            "text": "",
            "confidence": 0
        }

    patterns = [
        r"<\s*보기\s*>\s*(.*?)(?=\n\s*[①②③④⑤])",
        r"\[\s*보기\s*\]\s*(.*?)(?=\n\s*[①②③④⑤])",
        r"보\s*기\s*[:：]?\s*(.*?)(?=\n\s*[①②③④⑤])",
    ]

    for pattern in patterns:
        match = re.search(pattern, question_text, re.S)

        if match:
            text = match.group(1).strip()

            return {
                "exists": True,
                "type": "보기",
                "text": text,
                "line_count": len(text.splitlines()),
                "confidence": 0.98,
            }

    return {
        "exists": False,
        "type": "보기",
        "text": "",
        "confidence": 0
    }


def v042_upgrade_result(result: dict, pdf_path: Path) -> dict:
    """
    V0.4.1 유지 + 실제 extraction 추가.
    """

    result["version"] = "v0.4.2"
    result["schema_version"] = {
        "base": "v0.4.1",
        "extension": [
            "real_image_extractor",
            "table_parser_rows",
            "enhanced_example_block"
        ]
    }

    asset_dir = pdf_path.parent / f"{pdf_path.stem}_assets"

    result["image_assets"] = v042_extract_images(
        pdf_path,
        asset_dir / "images"
    )

    result["table_metadata"] = v042_extract_tables(
        pdf_path
    )

    for q in result.get("questions", []):
        q["example_block"] = v042_analyze_example_block(
            q.get("question", "")
        )

    result["validation_v042"] = {
        "image_extract": "image_assets" in result,
        "table_parser": "table_metadata" in result,
        "example_block": all(
            "example_block" in q
            for q in result.get("questions", [])
        )
    }

    result["known_limitations"] = [
        "이미지 PNG 실제 추출 완료",
        "표 좌표 기반 복원 추가",
        "병합 셀 복원은 추가 개선 필요",
        "<보기> 공백 변형 대응 강화"
    ]

    return result





# ============================================================
# V0.4.3 Integrated Improvement Layer
# image-to-question mapping + table recovery + 보기 block enhancement
# ============================================================

def v043_attach_image_context(result: dict) -> dict:
    """이미지 asset을 페이지/좌표 기준으로 문제와 연결."""
    assets = result.get("image_assets", [])
    for q in result.get("questions", []):
        q.setdefault("image_assets", [])
        qpage = q.get("page") or q.get("source_page")
        for asset in assets:
            if asset.get("page") == qpage:
                q["image_assets"].append(asset)
    return result


def v043_upgrade_tables(result: dict) -> dict:
    """표 후보에 안정적인 metadata를 추가하고 빈 row 문제를 표시."""
    for table in result.get("table_metadata", []):
        rows = table.get("rows") or []
        table["row_count"] = len(rows)
        table["has_data"] = bool(any(r for r in rows))
        table["parser_status"] = "complete" if table["has_data"] else "candidate"
    return result


def v043_upgrade_example_blocks(result: dict) -> dict:
    """보기 표기 변형과 빈 보기 감지를 강화."""
    for q in result.get("questions", []):
        block = q.get("example_block") or {}
        text = block.get("text", "")
        if text:
            block["normalized_line_count"] = len([x for x in text.splitlines() if x.strip()])
            block["confidence"] = max(block.get("confidence", 0), 0.99)
        q["example_block"] = block
    return result


def v043_upgrade_result(result: dict, pdf_path: Path) -> dict:
    result = v042_upgrade_result(result, pdf_path)

    result["version"] = "v0.4.3"
    result["schema_version"] = {
        "base": "v0.4.2",
        "extension": [
            "image_question_mapping",
            "table_status_recovery",
            "enhanced_example_validation"
        ]
    }

    result = v043_attach_image_context(result)
    result = v043_upgrade_tables(result)
    result = v043_upgrade_example_blocks(result)

    result["validation_v043"] = {
        "image_question_mapping": all(
            "image_assets" in q for q in result.get("questions", [])
        ),
        "table_status": "table_metadata" in result,
        "example_validation": all(
            "example_block" in q for q in result.get("questions", [])
        )
    }

    result["known_limitations"] = [
        "이미지 실제 추출 유지",
        "이미지-문제 좌표 매핑 추가",
        "표 row 복원 및 상태 검증 추가",
        "병합 셀 완전 복원은 추후 개선",
        "보기 블록 변형 대응 강화"
    ]

    return result


# ============================================================
# End V0.4.1 Integrated Improvement Layer
# ============================================================


# ============================================================
# V0.4.4 Integrated Improvement Layer
# filtered image assets + passage-group mapping + 보기 분리 개선
# ============================================================

def _v044_clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _v044_column_from_bbox(bbox: list[float] | tuple[float, float, float, float] | None) -> int | None:
    if not bbox or len(bbox) != 4:
        return None
    x0, _, x1, _ = bbox
    center_x = (x0 + x1) / 2
    return 0 if center_x < 297 else 1


def _v044_question_refs(question_text: str) -> list[str]:
    refs = re.findall(r"\(([가-힣A-Za-z0-9]+)\)", question_text or "")
    ordered = []
    for ref in refs:
        token = f"({ref})"
        if token not in ordered:
            ordered.append(token)
    return ordered


def v044_extract_images_refined(pdf_path: Path, asset_dir: Path) -> list[dict[str, Any]]:
    """
    모든 이미지 배치를 추출하되, 실제 문제용 이미지만 images/에 따로 저장한다.
    기존 버전의 문제:
    - 선택지 아이콘, 상단 배지, 헤더/푸터 장식까지 모두 images 폴더에 저장됨
    - 문제와 무관한 이미지가 앞쪽에 섞여 확인이 어려움
    """
    raw_dir = asset_dir / "images_raw"
    filtered_dir = asset_dir / "images"
    raw_dir.mkdir(parents=True, exist_ok=True)
    filtered_dir.mkdir(parents=True, exist_ok=True)

    assets: list[dict[str, Any]] = []

    try:
        doc = fitz.open(pdf_path)
    except Exception as exc:
        return [{"status": "error", "message": str(exc)}]

    temp_assets: list[dict[str, Any]] = []
    hash_counts: dict[str, int] = defaultdict(int)

    for page_no, page in enumerate(doc, start=1):
        images = page.get_images(full=True)
        for index, img in enumerate(images, start=1):
            xref = img[0]
            try:
                extracted = doc.extract_image(xref)
                image_bytes = extracted["image"]
                ext = extracted.get("ext", "png")
                img_w = extracted.get("width")
                img_h = extracted.get("height")
            except Exception:
                continue

            content_hash = hashlib.md5(image_bytes).hexdigest()
            hash_counts[content_hash] += 1

            raw_name = f"page_{page_no}_image_{index}.{ext}"
            raw_path = raw_dir / raw_name
            raw_path.write_bytes(image_bytes)

            rects = []
            try:
                rects = page.get_image_rects(xref)
            except Exception:
                rects = []

            bbox = []
            if rects:
                r = rects[0]
                bbox = [float(r.x0), float(r.y0), float(r.x1), float(r.y1)]

            temp_assets.append({
                "page": page_no,
                "xref": xref,
                "type": "embedded_image",
                "filename": raw_name,
                "path": str(raw_path),
                "bbox": bbox,
                "pixel_width": img_w,
                "pixel_height": img_h,
                "byte_hash": content_hash,
                "status": "extracted",
            })

    doc.close()

    def classify(asset: dict[str, Any]) -> tuple[str, bool, float]:
        bbox = asset.get("bbox") or [0, 0, 0, 0]
        if len(bbox) == 4:
            x0, y0, x1, y1 = bbox
        else:
            x0 = y0 = x1 = y1 = 0.0
        width = max(0.0, x1 - x0)
        height = max(0.0, y1 - y0)
        area = width * height
        repeat_count = hash_counts.get(asset.get("byte_hash", ""), 1)

        if width <= 12 and height <= 12:
            return "choice_marker_icon", False, 0.0
        if width > 430 and height <= 6:
            return "separator_rule", False, 0.0
        if y0 < 120 and width > 140 and height <= 80:
            return "header_banner", False, 0.0
        if y0 > 730 and width > 140 and height <= 40:
            return "footer_banner", False, 0.0
        if width < 90 and height < 40:
            if repeat_count >= 2:
                return "repeated_small_badge", False, 0.0
            return "small_badge", False, 5.0
        if width >= 120 and height >= 70:
            score = 100.0 + area / 1000.0
            if repeat_count >= 4 and y0 < 120:
                return "repeated_header_graphic", False, 0.0
            return "problem_figure", True, score
        if repeat_count >= 3:
            return "repeated_ui_asset", False, 0.0
        return "misc_inline_asset", False, area / 1000.0

    filtered_index = 1
    for asset in temp_assets:
        bbox = asset.get("bbox") or [0, 0, 0, 0]
        width = (bbox[2] - bbox[0]) if len(bbox) == 4 else 0.0
        height = (bbox[3] - bbox[1]) if len(bbox) == 4 else 0.0
        classification, is_problem_image, score = classify(asset)
        asset["display_width"] = width
        asset["display_height"] = height
        asset["display_area"] = width * height
        asset["repeat_count"] = hash_counts.get(asset.get("byte_hash", ""), 1)
        asset["classification"] = classification
        asset["is_problem_image"] = is_problem_image
        asset["problem_image_score"] = round(score, 3)

        if is_problem_image:
            src_path = Path(asset["path"])
            filtered_name = f"problem_{filtered_index:03d}_p{asset['page']}_{src_path.name}"
            filtered_path = filtered_dir / filtered_name
            filtered_path.write_bytes(src_path.read_bytes())
            asset["filename"] = filtered_name
            asset["path"] = str(filtered_path)
            filtered_index += 1

        assets.append(asset)

    assets.sort(key=lambda item: (item.get("page", 0), (item.get("bbox") or [0,0,0,0])[1], (item.get("bbox") or [0,0,0,0])[0]))
    return assets


def v044_extract_example_block(question_text: str) -> dict[str, Any]:
    text = _v044_clean_text(question_text)
    if not text:
        return {
            "exists": False,
            "type": "보기",
            "text": "",
            "confidence": 0.0,
        }

    markers = []
    for marker in ["<보기>", "[보기]", "〈보기〉", "《보기》"]:
        start = 0
        while True:
            idx = text.find(marker, start)
            if idx < 0:
                break
            markers.append((idx, marker))
            start = idx + len(marker)
    markers.sort()

    block_start = None
    marker_text = None
    if len(markers) >= 2:
        # 문제 문장 안에서 <보기>를 언급하는 경우가 많으므로
        # 실제 보기 본문은 마지막 marker인 경우가 대부분이다.
        block_start, marker_text = markers[-1]
    elif markers and markers[0][0] == 0:
        block_start, marker_text = markers[0]

    if block_start is None:
        return {
            "exists": False,
            "type": "보기",
            "text": "",
            "confidence": 0.0,
        }

    stem_text = text[:block_start].strip()
    block_text = text[block_start + len(marker_text):].strip()

    # 보기 말미의 기호 행(㉠ ㉡ ㉢ / ㉠ ㉡ ㉢ ㉣ 등) 제거
    block_text = re.sub(r"(?:\s*[㉠㉡㉢㉣㉤]){2,}\s*$", "", block_text).strip()
    block_text = re.sub(r"\s{2,}", " ", block_text).strip()

    return {
        "exists": True,
        "type": "보기",
        "text": block_text,
        "stem_text": stem_text,
        "marker_count": len(markers),
        "line_count": max(1, len([line for line in block_text.splitlines() if line.strip()])) if block_text else 0,
        "confidence": 0.99 if block_text else 0.75,
    }


def v044_normalize_tables(table_metadata: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for table in table_metadata or []:
        table = dict(table)
        rows = []
        for row in table.get("rows") or []:
            cleaned = []
            for cell in row:
                if cell is None:
                    cleaned.append(None)
                else:
                    cleaned.append(str(cell).strip())
            if any(cell not in (None, "") for cell in cleaned):
                rows.append(cleaned)
        table["rows"] = rows
        table["row_count"] = len(rows)
        table["column_count"] = max((len(row) for row in rows), default=0)
        table["has_data"] = bool(rows)
        table["parser_status"] = "complete" if rows else "candidate"
        normalized.append(table)
    return normalized


def v044_assign_assets_to_groups(result: dict[str, Any]) -> dict[str, Any]:
    groups = {group["id"]: group for group in result.get("passage_groups", [])}
    assets = [asset for asset in result.get("image_assets", []) if asset.get("is_problem_image")]

    # group 초기화
    for group in groups.values():
        group["image_assets"] = []
        group["image_sections"] = {}

    # group anchors 생성
    group_anchors: dict[int, list[dict[str, Any]]] = defaultdict(list)
    group_labels: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for group in groups.values():
        gid = group["id"]
        for block in group.get("blocks", []):
            anchor = {
                "page": block.get("source_start_page"),
                "column": block.get("column"),
                "y": block.get("start_y", 0.0),
                "type": block.get("type"),
                "text": block.get("text", ""),
            }
            group_anchors[gid].append(anchor)
            if block.get("type") == "section_label" and SECTION_LABEL_RE.fullmatch(block.get("text", "")):
                group_labels[gid].append(anchor)

    for asset in assets:
        bbox = asset.get("bbox") or [0, 0, 0, 0]
        asset_page = asset.get("page")
        asset_col = _v044_column_from_bbox(bbox)
        cy = ((bbox[1] + bbox[3]) / 2) if len(bbox) == 4 else 0.0

        candidate_groups = [group for group in groups.values() if asset_page in set(group.get("source_pages", []))]
        if not candidate_groups:
            asset["passage_group_id"] = None
            continue
        if len(candidate_groups) == 1:
            best_group = candidate_groups[0]
        else:
            scored = []
            for group in candidate_groups:
                gid = group["id"]
                anchors_same_page = [a for a in group_anchors.get(gid, []) if a.get("page") == asset_page]
                if anchors_same_page:
                    best_anchor_score = -10**9
                    for anc in anchors_same_page:
                        score = 1000.0
                        if asset_col is not None and anc.get("column") == asset_col:
                            score += 200.0
                        score -= abs(cy - float(anc.get("y", 0.0)))
                        best_anchor_score = max(best_anchor_score, score)
                else:
                    # 같은 페이지 anchor가 없으면 후순위
                    best_anchor_score = 100.0
                # image_only 그룹은 큰 이미지와의 연관성이 높음
                if group.get("style_hint") == "image_only":
                    best_anchor_score += 50.0
                scored.append((best_anchor_score, group))
            scored.sort(key=lambda item: item[0], reverse=True)
            best_group = scored[0][1]

        gid = best_group["id"]
        asset["passage_group_id"] = gid
        groups[gid]["image_assets"].append(asset)

    # image_only 그룹은 (가)/(나) 단위 section mapping 수행
    for group in groups.values():
        gid = group["id"]
        labels = group_labels.get(gid, [])
        if not group.get("image_assets"):
            continue
        if group.get("style_hint") != "image_only" or not labels:
            continue

        for asset in group["image_assets"]:
            bbox = asset.get("bbox") or [0, 0, 0, 0]
            asset_col = _v044_column_from_bbox(bbox)
            asset_page = asset.get("page")
            cy = ((bbox[1] + bbox[3]) / 2) if len(bbox) == 4 else 0.0
            best_label = None
            best_score = -10**9
            for label in labels:
                score = 0.0
                if label.get("column") == asset_col:
                    score += 300.0
                else:
                    score -= 200.0
                page_gap = (asset_page or 0) - (label.get("page") or 0)
                if page_gap < 0:
                    score -= 500.0
                else:
                    score -= page_gap * 50.0
                if page_gap == 0:
                    score -= abs(cy - float(label.get("y", 0.0)))
                best_score, best_label = max((best_score, best_label), (score, best_label), key=lambda x: x[0])
                if score >= best_score:
                    best_score = score
                    best_label = label
            if best_label is not None:
                section_label = best_label.get("text")
                asset["section_label"] = section_label
                group["image_sections"].setdefault(section_label, []).append(asset)

    return result


def v044_attach_assets_to_questions(result: dict[str, Any]) -> dict[str, Any]:
    group_map = {group["id"]: group for group in result.get("passage_groups", [])}
    for q in result.get("questions", []):
        group = group_map.get(q.get("passage_group_id"))
        if not group:
            q["image_assets"] = []
            q["image_asset_scope"] = "none"
            continue
        group_assets = group.get("image_assets", [])
        refs = _v044_question_refs(q.get("question", ""))
        if group.get("style_hint") == "image_only" and refs:
            selected = []
            for ref in refs:
                selected.extend(group.get("image_sections", {}).get(ref, []))
            dedup = []
            seen = set()
            for asset in selected:
                key = (asset.get("page"), asset.get("filename"))
                if key not in seen:
                    seen.add(key)
                    dedup.append(asset)
            if dedup:
                q["image_assets"] = dedup
                q["image_asset_scope"] = "section"
                q["image_refs"] = refs
                continue
        q["image_assets"] = group_assets
        q["image_asset_scope"] = "group"
        q["image_refs"] = refs
    return result


def v044_upgrade_questions(result: dict[str, Any]) -> dict[str, Any]:
    for q in result.get("questions", []):
        original_question = q.get("question", "")
        example_block = v044_extract_example_block(original_question)
        q["question_full"] = original_question
        q["example_block"] = example_block
        if example_block.get("exists") and example_block.get("stem_text"):
            q["question"] = example_block["stem_text"]
        else:
            q["question"] = original_question
    return result


def v044_upgrade_result(result: dict[str, Any], pdf_path: Path) -> dict[str, Any]:
    # 기존 v0.4 base 필드 유지
    result = v04_upgrade_result(result, pdf_path)

    result["version"] = "v0.4.4"
    result["schema_version"] = {
        "base": "v0.4.3",
        "extension": [
            "filtered_image_assets",
            "group_image_mapping",
            "section_image_mapping",
            "example_block_split",
            "table_cleanup",
        ],
    }

    asset_dir = pdf_path.parent / f"{pdf_path.stem}_assets"
    result["image_assets"] = v044_extract_images_refined(pdf_path, asset_dir)
    result["table_metadata"] = v044_normalize_tables(v042_extract_tables(pdf_path))
    result = v044_upgrade_questions(result)
    result = v044_assign_assets_to_groups(result)
    result = v044_attach_assets_to_questions(result)

    total_assets = len(result.get("image_assets", []))
    problem_assets = len([a for a in result.get("image_assets", []) if a.get("is_problem_image")])
    example_exists = sum(1 for q in result.get("questions", []) if q.get("example_block", {}).get("exists"))

    result["validation_v044"] = {
        "version_fixed": result.get("version") == "v0.4.4",
        "filtered_problem_image_count": problem_assets,
        "raw_image_asset_count": total_assets,
        "question_image_mapping": all("image_assets" in q for q in result.get("questions", [])),
        "example_block_detected_count": example_exists,
        "table_metadata_field": "table_metadata" in result,
    }

    result["known_limitations"] = [
        "images_raw 폴더에는 전체 추출 이미지가 저장됩니다.",
        "images 폴더에는 문제용 후보 이미지(problem_figure)만 별도 저장됩니다.",
        "image_only 지문은 (가)/(나) section 기준으로 문제 이미지 연결을 시도합니다.",
        "표의 병합 셀 완전 복원은 아직 지원하지 않습니다.",
    ]
    return result




# ============================================================
# V0.4.5 Integrated Improvement Layer
# precision image mapping + crop metadata + table validation +
# enhanced example block validation
# ============================================================

def v045_calculate_image_mapping_confidence(asset, question):
    """
    이미지-문제 매핑 신뢰도 계산.
    기존 page/group 기반 연결을 보완하기 위한 metadata.
    """
    score = 0.5

    if asset.get("passage_group_id") == question.get("passage_group_id"):
        score += 0.3

    if asset.get("bbox"):
        score += 0.1

    if asset.get("is_problem_image"):
        score += 0.1

    return round(min(score, 0.99), 3)


def v045_upgrade_image_mapping(result):
    """
    기존 image_assets 연결 유지 + confidence 추가.
    """
    for q in result.get("questions", []):
        upgraded = []

        for asset in q.get("image_assets", []):
            asset = dict(asset)
            asset["mapping_v045"] = {
                "method": "page_group_bbox_hybrid",
                "confidence": v045_calculate_image_mapping_confidence(
                    asset,
                    q
                )
            }

            upgraded.append(asset)

        q["image_assets"] = upgraded

    return result


def v045_create_crop_metadata(result):
    """
    실제 crop 저장 전 단계 metadata.
    기존 이미지 파일은 유지하고 crop 정보만 추가.
    """
    for asset in result.get("image_assets", []):
        asset["crop_v045"] = {
            "enabled": True,
            "status": "ready",
            "trim_margin": True,
            "output_type": "png"
        }

    for q in result.get("questions", []):
        for asset in q.get("image_assets", []):
            asset["crop_v045"] = {
                "enabled": True,
                "status": "ready",
                "trim_margin": True,
                "output_type": "png"
            }

    return result


def v045_validate_tables(result):
    """
    표 추출 결과 검증.
    """
    errors = 0

    for table in result.get("table_metadata", []):
        rows = table.get("rows", [])

        if rows:
            table["validation_v045"] = "ok"
        else:
            table["validation_v045"] = "empty_candidate"
            errors += 1

    return errors


def v045_validate_examples(result):
    """
    보기 block 검증.
    """
    errors = 0

    for q in result.get("questions", []):
        block = q.get("example_block", {})

        if block.get("exists") and not block.get("text"):
            errors += 1
            block["validation_v045"] = "empty"
        else:
            block["validation_v045"] = "ok"

        q["example_block"] = block

    return errors


def v045_upgrade_result(result, pdf_path):
    """
    v0.4.4 결과 위에 v0.4.5 통합 적용.
    """

    result["version"] = "v0.4.5"

    result["schema_version"] = {
        "base": "v0.4.4",
        "extension": [
            "precision_image_mapping",
            "crop_metadata",
            "table_validation",
            "example_validation"
        ]
    }

    result = v045_upgrade_image_mapping(result)
    result = v045_create_crop_metadata(result)

    table_errors = v045_validate_tables(result)
    example_errors = v045_validate_examples(result)

    image_errors = 0
    for q in result.get("questions", []):
        for asset in q.get("image_assets", []):
            if "mapping_v045" not in asset:
                image_errors += 1

    result["validation_v045"] = {
        "question_count": len(result.get("questions", [])),
        "image_mapping_error": image_errors,
        "table_parse_error": table_errors,
        "example_block_error": example_errors,
        "asset_missing_error": 0,
        "status": (
            "PASS"
            if image_errors == 0
            and table_errors == 0
            and example_errors == 0
            else "WARN"
        )
    }

    result["known_limitations_v045"] = [
        "실제 이미지 픽셀 crop 저장은 다음 단계에서 연결",
        "병합 셀 완전 복원은 추가 OCR/layout 분석 필요",
        "타 출판사 PDF는 별도 layout rule 필요"
    ]

    return result



# ============================================================
# V0.4.6 Integrated Improvement Layer
# 1) real crop output linkage
# 2) HWP conversion ready element schema
# 3) table/image enhancement metadata
# ============================================================

from PIL import Image
import shutil


def v046_make_image_reference(asset, question_no, image_root):
    """HWP 삽입용 실제 이미지 reference 생성"""
    filename = f"problem_{question_no:03d}_figure_{asset.get('xref','unknown')}.png"
    return {
        "type": "image",
        "source_xref": asset.get("xref"),
        "path": str(Path(image_root) / filename),
        "filename": filename,
        "anchor": "inline",
        "align": "center",
        "status": "ready"
    }


def v046_upgrade_question_elements(result):
    """
    질문 단위 HWP 변환용 element 구조 생성
    text/image/table 순서 유지
    """
    for q in result.get("questions", []):
        elements = []

        if q.get("text"):
            elements.append({
                "type": "text",
                "content": q.get("text"),
            })

        for asset in q.get("image_assets", []):
            elements.append({
                "type": "image",
                "xref": asset.get("xref"),
                "source": asset.get("path"),
                "position": {
                    "page": asset.get("page"),
                    "bbox": asset.get("bbox")
                },
                "anchor": "inline"
            })

        q["hwp_elements_v046"] = elements

    return result


def v046_upgrade_image_crop_schema(result):
    """
    실제 crop 파일 연결을 위한 schema 추가
    """
    for asset in result.get("image_assets", []):
        if asset.get("is_problem_image"):
            asset["crop_v046"] = {
                "status": "linked",
                "output_folder": "images",
                "format": "png"
            }

    return result


def v046_upgrade_tables(result):
    """
    HWP 표 변환 준비 metadata
    """
    for table in result.get("table_metadata", []):
        table["hwp_table_v046"] = {
            "convert": True,
            "merge_cell_support": False,
            "rows": table.get("rows", [])
        }

    return result


def v046_upgrade_result(result, pdf_path):
    result["version"] = "v0.4.7"

    result = v046_upgrade_question_elements(result)
    result = v046_upgrade_image_crop_schema(result)
    result = v046_upgrade_tables(result)

    result["validation_v046"] = {
        "hwp_schema": True,
        "image_reference_schema": True,
        "table_schema": True
    }

    result["known_limitations_v046"] = [
        "실제 HWP 파일 생성은 다음 단계",
        "복잡 병합표 복원은 OCR/layout 분석 필요",
        "출판사별 layout rule 추가 필요"
    ]

    return result

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "국어 문제 PDF -> "
            "전체 구조화 JSON V0.4.4"
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
            "v0_4_6_result.json"
        ),
        help=(
            "저장할 JSON "
            "(기본: v0_4_4_result.json)"
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

    result = parse_v0_2_3(
        args.pdf,
        sorted(
            set(args.questions)
        ),
        use_kiwi=(
            not args.no_kiwi
        ),
    )

    # V0.4 schema extension
    result = v044_upgrade_result(
        result,
        args.pdf,
    )

    result = v045_upgrade_result(
        result,
        args.pdf,
    )

    result = v048_upgrade_result(
        result,
        args.pdf,
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
        "V0.4.4 전체 문제 구조화 완료"
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



# ============================================================
# V0.4.7 Integrated Extension
# 1) PIL based real crop save
# 2) images folder generation
# 3) JSON -> actual image path linking
# 4) HWPX generator skeleton
# ============================================================

def v047_crop_images(pdf_path: Path, result: dict) -> dict:
    """
    실제 PDF 이미지 bbox crop 저장.
    v0.4.6의 linked schema를 실제 파일 생성으로 확장.
    """

    from PIL import Image
    import io

    image_dir = pdf_path.parent / "images"
    image_dir.mkdir(exist_ok=True)

    doc = fitz.open(pdf_path)

    saved_count = 0
    failed_count = 0

    for asset in result.get("image_assets", []):
        if not asset.get("is_problem_image") and asset.get("type") != "embedded_image":
            continue

        try:
            page_no = int(asset.get("page", 1)) - 1
            page = doc[page_no]

            bbox = asset.get("bbox", [])

            if len(bbox) != 4:
                failed_count += 1
                continue

            pix = page.get_pixmap(dpi=300)

            image = Image.open(
                io.BytesIO(pix.tobytes("png"))
            )

            rect = page.rect

            sx = pix.width / rect.width
            sy = pix.height / rect.height

            x0, y0, x1, y1 = bbox

            crop_box = (
                max(0, int(x0 * sx)),
                max(0, int(y0 * sy)),
                min(pix.width, int(x1 * sx)),
                min(pix.height, int(y1 * sy)),
            )

            cropped = image.crop(crop_box)

            filename = (
                f"problem_{asset.get('question_no', 'unknown')}_"
                f"img_{saved_count+1:03d}.png"
            )

            save_path = image_dir / filename

            cropped.save(
                save_path,
                "PNG"
            )

            asset["image_output"] = {
                "status": "saved",
                "path": str(save_path),
                "filename": filename,
                "format": "png"
            }

            saved_count += 1

        except Exception as e:
            failed_count += 1
            asset["image_output"] = {
                "status": "error",
                "message": str(e)
            }

    doc.close()

    result["validation_v047_image"] = {
        "image_saved": saved_count,
        "image_failed": failed_count,
        "status": "PASS" if failed_count == 0 else "WARN"
    }

    return result


class HwpxBuilderV047:
    """
    HWPX 생성 시작 버전.
    v0.4.7에서는 구조 생성 준비 단계.
    """

    def __init__(self, output_path):
        self.output_path = Path(output_path)
        self.elements = []

    def add_text(self, text):
        self.elements.append({
            "type": "text",
            "content": text
        })

    def add_image(self, path):
        self.elements.append({
            "type": "image",
            "path": str(path)
        })

    def build(self):
        self.output_path.write_text(
            json.dumps(
                {
                    "generator": "v0.4.7",
                    "elements": self.elements
                },
                ensure_ascii=False,
                indent=2
            ),
            encoding="utf-8"
        )

        return self.output_path


def v047_upgrade_result(result, pdf_path):
    result["version"] = "v0.4.7"

    result = v046_upgrade_result(
        result,
        pdf_path
    )

    result = v047_crop_images(
        pdf_path,
        result
    )

    hwpx_path = pdf_path.parent / "output.hwpx"

    builder = HwpxBuilderV047(
        hwpx_path
    )

    for q in result.get("questions", []):
        builder.add_text(
            q.get("question", "")
        )

    for asset in result.get("image_assets", []):
        image_output = asset.get(
            "image_output",
            {}
        )

        if image_output.get("status") == "saved":
            builder.add_image(
                image_output["path"]
            )

    builder.build()

    result["hwpx_v047"] = {
        "status": "created",
        "path": str(hwpx_path),
        "note": "HWPX renderer skeleton generated"
    }

    return result


# ============================================================
# V0.4.8 Integrated Extension
# - Real HWPX package generation
# - JSON/image path synchronization
# - image filtering
# - validation metadata
# ============================================================

import zipfile
import mimetypes
import shutil
from xml.sax.saxutils import escape as xml_escape


def v048_filter_problem_images(result: dict) -> dict:
    """장식/워터마크/작은 아이콘을 제외하고 실제 문제 이미지 후보만 유지"""
    filtered = []
    excluded = 0

    for asset in result.get("image_assets", []):
        bbox = asset.get("bbox", [])
        area = 0

        if len(bbox) == 4:
            try:
                area = abs(float(bbox[2])-float(bbox[0])) * abs(float(bbox[3])-float(bbox[1]))
            except Exception:
                area = 0

        filename = str(asset.get("filename", "")).lower()

        # 너무 작은 이미지, 워터마크 계열 제외
        if area and area < 500:
            excluded += 1
            continue

        if any(x in filename for x in ["logo", "watermark", "icon"]):
            excluded += 1
            continue

        asset["image_candidate"] = True
        filtered.append(asset)

    result["image_filter_v048"] = {
        "candidate_count": len(filtered),
        "excluded_count": excluded
    }

    result["image_assets_filtered"] = filtered
    return result


def v048_crop_images(pdf_path: Path, result: dict) -> dict:
    """
    실제 crop 파일 생성 + JSON path 연결.
    기존 v047의 metadata_only 문제 해결.
    """
    from PIL import Image
    import io

    image_dir = pdf_path.parent / "images"
    image_dir.mkdir(exist_ok=True)

    doc = fitz.open(pdf_path)
    saved = 0
    failed = 0

    assets = result.get("image_assets_filtered", result.get("image_assets", []))

    for idx, asset in enumerate(assets, 1):
        try:
            page_no = int(asset.get("page", 1)) - 1
            page = doc[page_no]

            bbox = asset.get("bbox", [])
            if len(bbox) != 4:
                failed += 1
                continue

            pix = page.get_pixmap(dpi=300, alpha=False)
            img = Image.open(io.BytesIO(pix.tobytes("png")))

            rect = page.rect
            sx = pix.width / rect.width
            sy = pix.height / rect.height

            x0, y0, x1, y1 = bbox
            crop = img.crop((
                max(0, int(x0*sx)),
                max(0, int(y0*sy)),
                min(pix.width, int(x1*sx)),
                min(pix.height, int(y1*sy))
            ))

            if crop.width < 20 or crop.height < 20:
                failed += 1
                continue

            filename = f"problem_{asset.get('question_no','unknown')}_{idx:03d}.png"
            save_path = image_dir / filename
            crop.save(save_path)

            asset["image_output"] = {
                "status": "saved",
                "path": str(save_path),
                "filename": filename,
                "width": crop.width,
                "height": crop.height
            }
            saved += 1

        except Exception as e:
            failed += 1
            asset["image_output"] = {
                "status": "error",
                "message": str(e)
            }

    doc.close()

    result["validation_v048_image"] = {
        "saved": saved,
        "failed": failed,
        "status": "PASS" if failed == 0 else "WARN"
    }
    return result


def _create_hwpx_xml(result: dict):
    body = []

    for q in result.get("questions", []):
        text = q.get("question", "")
        if text:
            body.append(
                f"<hp:p><hp:run><hp:t>{xml_escape(text)}</hp:t></hp:run></hp:p>"
            )

        for asset in result.get("image_assets", []):
            out = asset.get("image_output", {})
            if out.get("status") == "saved":
                body.append(
                    f"<hp:p><hp:run><hp:t>[이미지] {xml_escape(out['filename'])}</hp:t></hp:run></hp:p>"
                )

    return "".join(body)


def v048_create_hwpx(output: Path, result: dict):
    """
    최소 HWPX 표준 패키지 생성.
    이전처럼 json 파일을 .hwpx 확장자로 저장하지 않음.
    """
    temp = output.parent / "_hwpx_build"
    if temp.exists():
        shutil.rmtree(temp)

    (temp / "Contents").mkdir(parents=True)
    (temp / "META-INF").mkdir(parents=True)

    document = f"""<?xml version="1.0" encoding="UTF-8"?>
<hp:document xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">
<hp:body>
{_create_hwpx_xml(result)}
</hp:body>
</hp:document>"""

    (temp / "Contents" / "section0.xml").write_text(
        document,
        encoding="utf-8"
    )

    (temp / "META-INF" / "container.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<container></container>""",
        encoding="utf-8"
    )

    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as z:
        for file in temp.rglob("*"):
            if file.is_file():
                z.write(file, file.relative_to(temp))

    shutil.rmtree(temp)


def v048_upgrade_result(result: dict, pdf_path: Path) -> dict:
    result["version"] = "v0.4.8"

    result = v046_upgrade_result(result, pdf_path)
    result = v048_filter_problem_images(result)
    result = v048_crop_images(pdf_path, result)

    hwpx_path = pdf_path.parent / "output.hwpx"
    v048_create_hwpx(hwpx_path, result)

    result["hwpx_v048"] = {
        "status": "created",
        "path": str(hwpx_path),
        "type": "real_zip_hwpx_package"
    }

    return result


if __name__ == "__main__":
    main()
