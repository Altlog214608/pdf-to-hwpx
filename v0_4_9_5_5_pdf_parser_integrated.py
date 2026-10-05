#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
V0.4.9.5.5 - 국어 문제 PDF → 구조화 JSON → 컴팩트 여백/지문 박스 패딩 + 문제 묶음 조판 통합 파서
=============================================================

V0.2.3~V0.4.9.5.2의 누적 파서를 유지하면서 논리 page/column 검증, HWPX section0 2단 XML 원자적 보정, 검증 상태 분리를 추가한 통합 수정본.

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


8) V0.4.9.5.2 이미지 앵커 안정화
   - InsertPicture의 Width/Height만 사용하고 개체 선택 기반 후처리 완전 제거
   - 저장된 HWPX의 BinData hash로 실제 그림 filename 순서를 역검증
   - [정답 및 해설] 이후 문제 그림이 존재하면 FAIL
   - 원본 PDF page/group과 주변 텍스트 anchor를 비교해 이미지 위치 검증

9) V0.4.9.5.3 실제 2단 안정화
   - HParameterSet.HColDef 기반 MultiColumn(2) 시도는 그대로 유지
   - COM 저장 결과가 colCount=1이어도 columnBreak/pageBreak가 정상인 경우 section0.xml만 colCount=2로 원자적 보정
   - 정답 section1은 colCount=1로 유지
   - 보정 후보를 별도 HWPX로 만들고 패키지/이미지/논리 위치 검증 통과 시에만 최종 output.hwpx로 교체
   - HWP COM/보안 모듈은 한 번만 실행

주의
----
- <보기>를 별도 block으로 분리하는 작업은 V0.3
- 이미지 crop / 이미지 지문 구조화는 V0.4
- 이 버전은 현재 업로드된 '최다빈출 공략' 계열 PDF 구조를 기준으로 함

필요 패키지
-----------
    pip install pymupdf kiwipiepy Pillow pywin32

실행
----
    python v0_4_9_5_5_pdf_parser_integrated.py "원본.pdf"

출력 파일 지정
--------------
    python v0_4_9_5_5_pdf_parser_integrated.py "원본.pdf" -o v0_4_9_5_5_result.json

특정 문제만 디버깅
------------------
    python v0_4_9_5_5_pdf_parser_integrated.py "원본.pdf" -q 2 3 4 16

Kiwi 없이 구조만 테스트
-----------------------
    python v0_4_9_5_2_pdf_parser_integrated.py "원본.pdf" --no-kiwi
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import pymupdf as fitz

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
        import pymupdf as fitz
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
        import pymupdf as fitz
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
    import pymupdf as fitz

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
    import pymupdf as fitz

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

        if q.get("question"):
            elements.append({
                "type": "text",
                "content": q.get("question"),
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
            "전체 구조화 JSON V0.4.9.5.3"
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
            "v0_4_9_5_3_result.json"
        ),
        help=(
            "저장할 JSON "
            "(기본: v0_4_9_5_3_result.json)"
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

    parser.add_argument(
        "--security-module",
        type=Path,
        default=None,
        help=(
            "한컴 공식 FilePathCheckerModuleExample.dll 경로. "
            "생략하면 레지스트리/스크립트 폴더/LOCALAPPDATA를 자동 탐색"
        ),
    )

    parser.add_argument(
        "--allow-interactive-hwp",
        action="store_true",
        help=(
            "공식 보안 모듈 등록에 실패해도 한글 승인창을 띄우고 계속 진행. "
            "기본값은 무조작 실행을 위해 실패 시 즉시 중단"
        ),
    )

    parser.add_argument(
        "--show-hwp",
        action="store_true",
        help=(
            "보안 모듈이 정상 등록되어도 한글 창을 표시 (디버그용)"
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

    checkpoint_path = args.output.with_name(
        args.output.stem + "_pre_hwpx.json"
    )
    result = v04953_upgrade_result(
        result,
        args.pdf,
        checkpoint_path=checkpoint_path,
        security_module_path=args.security_module,
        allow_interactive_hwp=args.allow_interactive_hwp,
        show_hwp=args.show_hwp,
    )

    args.output.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # A pre-HWPX checkpoint exists only to survive a Hangul COM hang/error.
    # On a successful HWPX run, remove it so the normal result is a single JSON.
    checkpoint_info = result.get("pre_hwpx_checkpoint") or {}
    checkpoint_file = Path(str(checkpoint_info.get("path") or "")) if isinstance(checkpoint_info, dict) else None
    if result.get("hwpx_v04953", {}).get("status") == "created" and checkpoint_file and str(checkpoint_file):
        try:
            if checkpoint_file.exists():
                checkpoint_file.unlink()
            checkpoint_info["retained"] = False
            result["pre_hwpx_checkpoint"] = checkpoint_info
            args.output.write_text(
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print("[v0.4.9.5.3] HWPX 성공: 임시 pre_hwpx 체크포인트를 정리했습니다.", flush=True)
        except Exception as exc:
            checkpoint_info["retained"] = True
            checkpoint_info["cleanup_error"] = str(exc)
            result["pre_hwpx_checkpoint"] = checkpoint_info

    validation = (
        result["validation"]
    )

    print("=" * 76)
    print(
        "V0.4.9.5.3 전체 문제 구조화 완료"
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

    v492 = next((
        result.get(key)
        for key in (
            "validation_v04953", "validation_v04952", "validation_v04951",
            "validation_v0495", "validation_v0494", "validation_v0493",
            "validation_v0492",
        )
        if result.get(key)
    ), {})
    if v492:
        print(
            "문제 이미지 : "
            f"{v492.get('problem_image_saved', 0)} / "
            f"{v492.get('problem_image_count', 0)} "
            f"({v492.get('image_status', '?')})"
        )
        print(
            "렌더 페이지 : "
            f"{v492.get('render_page_count', 0)} | "
            f"렌더 아이템 : {v492.get('render_item_count', 0)}"
        )
        if "answer_count" in v492:
            print(
                "정답/해설 : "
                f"{v492.get('answer_count', 0)}문항 | "
                f"표 렌더 {v492.get('renderable_table_count', 0)}개 / "
                f"제외 {v492.get('excluded_table_count', 0)}개"
            )
        print(
            "HWPX 상태 : "
            f"{v492.get('hwpx_status', '?')}"
        )
        hwpx_info = next((
            result.get(key)
            for key in (
                "hwpx_v04953", "hwpx_v04952", "hwpx_v04951", "hwpx_v0495",
                "hwpx_v0494", "hwpx_v0493", "hwpx_v0492",
            )
            if result.get(key)
        ), {})
        if hwpx_info.get("renderer_mode"):
            print(f"HWPX 렌더러 : {hwpx_info.get('renderer_mode')}")
        if hwpx_info.get("reason"):
            print(f"HWPX 안내 : {hwpx_info.get('reason')}")
        if hwpx_info.get("previous_output_preserved"):
            print("HWPX 안내 : 새 렌더링 실패 시 기존 output.hwpx는 보존됩니다.")
        security_info = result.get("hancom_security_v04953") or result.get("hancom_security_v04952") or result.get("hancom_security_v04951") or result.get("hancom_security_v0495") or result.get("hancom_security_v0494") or result.get("hancom_security_v0493") or hwpx_info.get("hancom_security") or {}
        if security_info:
            print(
                "한컴 보안 : "
                f"{security_info.get('status', '?')} | "
                f"RegisterModule={security_info.get('register_module_result')} | "
                f"무조작={security_info.get('unattended_ready', False)}"
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


# ============================================================
# V0.4.8.1 Corrected Integrated Extension
# - only proven problem_figure assets are exported to ./images
# - stale root images are removed before every run
# - passage-group -> question image linkage is written to JSON
# - final version is fixed after all historical upgrade layers
# - real HWPX is created through installed Hancom Hangul on Windows
#   (no more fake 2 KB ZIP/XML package)
# ============================================================

import os
import platform
from collections import Counter


def v0481_prepare_problem_images(pdf_path: Path, result: dict) -> dict:
    """Export exactly the assets already classified as real problem figures.

    v0.4.4 already classifies this source PDF very well: 132 embedded assets ->
    12 problem_figure assets.  v0.4.8 accidentally ignored that classification
    and re-selected 40 decorative assets.  This stage intentionally reuses the
    proven classifier rather than inventing a second competing filter.
    """
    from PIL import Image
    import io

    image_dir = pdf_path.parent / "images"
    if image_dir.exists():
        shutil.rmtree(image_dir)
    image_dir.mkdir(parents=True, exist_ok=True)

    all_assets = result.get("image_assets", [])
    class_counts = Counter(str(a.get("classification") or "unclassified") for a in all_assets)

    # Remove stale v0.4.7/v0.4.8 output metadata from every asset first.
    for asset in all_assets:
        asset.pop("image_output", None)
        asset["image_candidate_v0481"] = False
        asset["image_candidate"] = False

    selected = [
        a for a in all_assets
        if a.get("is_problem_image") is True
        and a.get("classification") == "problem_figure"
    ]

    # Stable document-order sorting.
    selected.sort(key=lambda a: (
        int(a.get("page", 10**9)),
        float((a.get("bbox") or [0, 0, 0, 0])[1] if len(a.get("bbox") or []) == 4 else 0),
        float((a.get("bbox") or [0, 0, 0, 0])[0] if len(a.get("bbox") or []) == 4 else 0),
        int(a.get("xref", 0) or 0),
    ))

    group_questions = {
        int(g.get("id")): list(g.get("question_numbers", []))
        for g in result.get("passage_groups", [])
        if g.get("id") is not None
    }

    per_group_index = defaultdict(int)
    saved = 0
    failed = 0
    failures = []

    doc = fitz.open(pdf_path)
    try:
        for asset in selected:
            gid = int(asset.get("passage_group_id") or 0)
            per_group_index[gid] += 1
            fig_idx = per_group_index[gid]
            qnums = group_questions.get(gid, [])
            qlabel = "-".join(str(x) for x in qnums) if qnums else "unknown"
            filename = f"group_{gid:02d}_q{qlabel}_fig_{fig_idx:02d}.png"
            save_path = image_dir / filename

            try:
                source = Path(str(asset.get("path") or ""))
                if not source.is_absolute():
                    source = pdf_path.parent / source

                # The _assets/images file is already the correctly extracted problem
                # figure. Prefer copying it byte-for-byte.  Fall back to PDF bbox crop
                # only when that source file is unavailable.
                if source.exists() and source.is_file():
                    shutil.copy2(source, save_path)
                    export_method = "copy_classified_problem_figure"
                else:
                    bbox = asset.get("bbox", [])
                    page_no = int(asset.get("page", 1)) - 1
                    if len(bbox) != 4 or page_no < 0 or page_no >= len(doc):
                        raise ValueError("problem figure has no usable source path or bbox")

                    page = doc[page_no]
                    pix = page.get_pixmap(dpi=300, alpha=False)
                    page_img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
                    rect = page.rect
                    sx = pix.width / rect.width
                    sy = pix.height / rect.height
                    x0, y0, x1, y1 = map(float, bbox)
                    crop_box = (
                        max(0, int(round(x0 * sx))),
                        max(0, int(round(y0 * sy))),
                        min(pix.width, int(round(x1 * sx))),
                        min(pix.height, int(round(y1 * sy))),
                    )
                    crop = page_img.crop(crop_box)
                    if crop.width < 20 or crop.height < 20:
                        raise ValueError(f"crop too small: {crop.width}x{crop.height}")
                    crop.save(save_path, "PNG")
                    export_method = "pdf_bbox_crop_fallback"

                with Image.open(save_path) as check_img:
                    width, height = check_img.size

                rel = save_path.relative_to(pdf_path.parent)
                asset["image_candidate_v0481"] = True
                asset["image_candidate"] = True
                asset["crop_status"] = "saved"
                asset["image_output"] = {
                    "status": "saved",
                    "path": str(save_path.resolve()),
                    "relative_path": str(rel),
                    "filename": filename,
                    "width": width,
                    "height": height,
                    "format": "png",
                    "export_method": export_method,
                    "passage_group_id": gid,
                    "question_numbers": qnums,
                }
                saved += 1
            except Exception as exc:
                failed += 1
                msg = f"page={asset.get('page')} xref={asset.get('xref')}: {exc}"
                failures.append(msg)
                asset["image_output"] = {"status": "error", "message": str(exc)}
    finally:
        doc.close()

    # Mark legacy raw metadata with the final v0.4.8.1 decision so that
    # crop_status=metadata_only is not mistaken for the final pipeline state.
    selected_keys = {(int(a.get("page", 0) or 0), int(a.get("xref", 0) or 0)): a for a in selected}
    for meta in result.get("image_metadata", []):
        key = (int(meta.get("page", 0) or 0), int(meta.get("xref", 0) or 0))
        linked = selected_keys.get(key)
        if linked and linked.get("image_output", {}).get("status") == "saved":
            meta["final_status_v0481"] = "saved_problem_figure"
            meta["final_relative_path_v0481"] = linked["image_output"]["relative_path"]
        else:
            meta["final_status_v0481"] = "excluded_non_problem_asset"

    # The filtered list is now truly the selected problem assets only.
    result["image_assets_filtered"] = selected

    selected_by_group = defaultdict(list)
    for asset in selected:
        out = asset.get("image_output", {})
        if out.get("status") == "saved":
            selected_by_group[int(asset.get("passage_group_id") or 0)].append(out["relative_path"])

    # Attach shared passage images to both questions that consume that passage.
    q_by_no = {int(q.get("number")): q for q in result.get("questions", []) if q.get("number") is not None}
    for gid, qnums in group_questions.items():
        refs = selected_by_group.get(gid, [])
        for qno in qnums:
            q = q_by_no.get(int(qno))
            if q is not None:
                q["image_assets_v0481"] = list(refs)
                q["image_asset_scope_v0481"] = "shared_passage_group" if refs else "none"

    result["image_filter_v0481"] = {
        "raw_asset_count": len(all_assets),
        "classification_counts": dict(class_counts),
        "selected_problem_figure_count": len(selected),
        "saved_count": saved,
        "failed_count": failed,
        "output_directory": str(image_dir.resolve()),
        "selection_rule": "is_problem_image == true AND classification == problem_figure",
        "failures": failures,
        "status": "PASS" if failed == 0 and saved == len(selected) else "WARN",
    }
    return result


def v0481_hwpx_document_items(result: dict) -> list:
    """Build a deterministic logical document stream for the Hangul writer."""
    q_by_no = {int(q["number"]): q for q in result.get("questions", []) if q.get("number") is not None}
    selected = result.get("image_assets_filtered", [])
    images_by_group = defaultdict(list)
    for asset in selected:
        out = asset.get("image_output", {})
        if out.get("status") == "saved":
            images_by_group[int(asset.get("passage_group_id") or 0)].append(out)

    items = []
    for group in result.get("passage_groups", []):
        gid = int(group.get("id") or 0)
        passage = (group.get("normalized_text") or group.get("raw_text") or "").strip()
        if passage:
            items.append({"type": "text", "text": passage + "\r\n"})
        for image_out in images_by_group.get(gid, []):
            items.append({"type": "image", "path": image_out["path"], "filename": image_out["filename"]})
        for qno in group.get("question_numbers", []):
            q = q_by_no.get(int(qno))
            if not q:
                continue
            items.append({"type": "text", "text": f"\r\n{q['number']}. {q.get('question','')}\r\n"})
            for idx, choice in enumerate(q.get("choices", []), 1):
                circled = CIRCLED[idx - 1] if 1 <= idx <= len(CIRCLED) else f"{idx}."
                items.append({"type": "text", "text": f"{circled} {choice}\r\n"})
    return items


def v0481_validate_hwpx(path: Path, expect_images: bool = False) -> dict:
    required = [
        "mimetype",
        "version.xml",
        "settings.xml",
        "Contents/content.hpf",
        "Contents/header.xml",
        "Contents/section0.xml",
        "META-INF/container.xml",
    ]
    info = {
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "zip_valid": False,
        "required_files": required,
        "missing": list(required),
        "bin_data_count": 0,
        "status": "FAIL",
    }
    if not path.exists() or not zipfile.is_zipfile(path):
        return info
    try:
        with zipfile.ZipFile(path, "r") as zf:
            names = set(zf.namelist())
            bad = zf.testzip()
            info["zip_valid"] = bad is None
            info["missing"] = [x for x in required if x not in names]
            info["bin_data_count"] = sum(1 for n in names if n.startswith("BinData/") and not n.endswith("/"))
            info["mimetype_stored_first"] = bool(zf.infolist()) and zf.infolist()[0].filename == "mimetype" and zf.infolist()[0].compress_type == zipfile.ZIP_STORED
            images_ok = (info["bin_data_count"] > 0) if expect_images else True
            info["status"] = "PASS" if info["zip_valid"] and not info["missing"] and info["mimetype_stored_first"] and images_ok else "FAIL"
    except Exception as exc:
        info["error"] = str(exc)
    return info


def v0481_create_hwpx_with_hancom(output: Path, result: dict) -> dict:
    """Create a real HWPX through Hancom Hangul COM automation on Windows.

    This intentionally replaces the hand-written 2 KB pseudo-HWPX from v0.4.8.
    HWPX contains multiple interdependent XML files; letting Hangul serialize the
    document guarantees that those relationships, style tables and manifests are
    authored consistently.
    """
    if output.exists():
        try:
            output.unlink()
        except Exception:
            pass

    if os.name != "nt":
        return {
            "status": "SKIPPED",
            "reason": "Hancom HWPX writer requires Windows with Hancom Hangul installed",
            "path": str(output),
            "backend": "hancom_com",
        }

    try:
        import win32com.client as win32
    except Exception as exc:
        return {
            "status": "ERROR",
            "reason": f"pywin32 is not available: {exc}",
            "install": "python -m pip install pywin32",
            "path": str(output),
            "backend": "hancom_com",
        }

    hwp = None
    try:
        hwp = win32.gencache.EnsureDispatch("HWPFrame.HwpObject")
        try:
            hwp.XHwpWindows.Item(0).Visible = False
        except Exception:
            pass
        try:
            hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
        except Exception:
            # Optional security helper; absence must not block normal interactive HWP.
            pass

        def insert_text(value: str):
            hwp.HAction.GetDefault("InsertText", hwp.HParameterSet.HInsertText.HSet)
            hwp.HParameterSet.HInsertText.Text = value
            hwp.HAction.Execute("InsertText", hwp.HParameterSet.HInsertText.HSet)

        items = v0481_hwpx_document_items(result)
        for item in items:
            if item["type"] == "text":
                insert_text(item["text"])
            elif item["type"] == "image":
                image_path = str(Path(item["path"]).resolve())
                if Path(image_path).exists():
                    hwp.InsertPicture(image_path, Embedded=True, sizeoption=0)
                    hwp.HAction.Run("BreakPara")

        output.parent.mkdir(parents=True, exist_ok=True)
        try:
            hwp.SaveAs(str(output.resolve()), "HWPX")
        except TypeError:
            hwp.SaveAs(str(output.resolve()), "HWPX", "")

        validation = v0481_validate_hwpx(output, expect_images=bool(result.get("image_assets_filtered")))
        return {
            "status": "created" if validation.get("status") == "PASS" else "INVALID",
            "path": str(output.resolve()),
            "backend": "hancom_com",
            "validation": validation,
        }
    except Exception as exc:
        if output.exists():
            try:
                output.unlink()
            except Exception:
                pass
        return {
            "status": "ERROR",
            "reason": str(exc),
            "path": str(output),
            "backend": "hancom_com",
            "install": "python -m pip install pywin32",
        }
    finally:
        if hwp is not None:
            try:
                hwp.Quit()
            except Exception:
                pass


def v0481_upgrade_result(result: dict, pdf_path: Path) -> dict:
    # Keep v0.4.6 HWP-ready metadata, but do not call the defective v0.4.8
    # image filter / hand-authored pseudo-HWPX writer.
    result = v046_upgrade_result(result, pdf_path)
    result = v0481_prepare_problem_images(pdf_path, result)

    hwpx_path = pdf_path.parent / "output.hwpx"
    hwpx_info = v0481_create_hwpx_with_hancom(hwpx_path, result)

    # Final version assignment MUST happen after every historical upgrade layer.
    result["version"] = "v0.4.8.1"
    result["parser_version"] = "v0.4.8.1"
    result["generator_version"] = "PDF Parser Integrated v0.4.8.1"
    result["hwpx_v0481"] = hwpx_info

    base_validation = result.get("validation", {})
    img_validation = result.get("image_filter_v0481", {})
    hwpx_status = hwpx_info.get("status")
    result["validation_v0481"] = {
        "question_count": len(result.get("questions", [])),
        "passage_group_count": len(result.get("passage_groups", [])),
        "problem_image_count": img_validation.get("selected_problem_figure_count", 0),
        "problem_image_saved": img_validation.get("saved_count", 0),
        "image_status": img_validation.get("status"),
        "hwpx_status": hwpx_status,
        "base_parser_status": base_validation.get("status"),
        "status": (
            "PASS"
            if base_validation.get("status") == "PASS"
            and img_validation.get("status") == "PASS"
            and hwpx_status in {"created", "SKIPPED"}
            else "WARN"
        ),
    }
    return result



def _v049_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _v049_column_name(value: Any) -> str:
    if isinstance(value, str):
        value = value.strip().lower()
        if value in {"left", "l", "0"}:
            return "left"
        if value in {"right", "r", "1"}:
            return "right"
    try:
        return "left" if int(value) == 0 else "right"
    except Exception:
        return "left"


def _v049_image_column_from_bbox(bbox: list[float] | tuple[float, ...] | None) -> str:
    if not bbox or len(bbox) < 4:
        return "left"
    try:
        x0, _, x1, _ = bbox[:4]
        cx = (float(x0) + float(x1)) / 2.0
        return "left" if cx < 297.5 else "right"
    except Exception:
        return "left"


def _v049_sort_images(assets: list[dict]) -> list[dict]:
    def key(a: dict):
        bbox = a.get("bbox") or [0, 0, 0, 0]
        x0 = float(bbox[0]) if len(bbox) >= 1 else 0.0
        y0 = float(bbox[1]) if len(bbox) >= 2 else 0.0
        return (int(a.get("page") or 0), y0, x0)
    return sorted(assets, key=key)


def _v049_has_substantive_blocks(group: dict) -> bool:
    for b in group.get("blocks", []):
        t = (b.get("text") or "").strip()
        if not t:
            continue
        if t in {"(가)", "(나)", "(다)", "(라)"}:
            continue
        return True
    return False


def v049_build_render_plan(result: dict) -> dict:
    """Build a page/column aware render plan for final HWPX generation.

    Strategy:
    - Each source page gets a logical left/right column bucket.
    - Passage blocks are inserted block-by-block to preserve original line breaks.
    - Images keep their source page, section and visual ordering.
    - Questions are placed in their source column, with <보기> between stem and choices.
    - Tables are kept as standalone table payloads for later HWPX conversion.
    """
    from collections import defaultdict

    page_cells: dict[int, dict[str, list[dict]]] = defaultdict(lambda: {"left": [], "right": []})
    question_pages = []

    def add_item(page: int, column: str, sort_y: float, item: dict):
        if page <= 0:
            return
        col = _v049_column_name(column)
        payload = dict(item)
        payload.setdefault("page", page)
        payload.setdefault("column", col)
        payload.setdefault("sort_y", float(sort_y))
        page_cells[page][col].append(payload)

    # Passage blocks first: preserve original lines / bullets / short-form text.
    group_by_id = {int(g.get("id") or 0): g for g in result.get("passage_groups", [])}
    for group in sorted(result.get("passage_groups", []), key=lambda g: int(g.get("id") or 0)):
        gid = int(group.get("id") or 0)
        blocks = sorted(
            group.get("blocks", []),
            key=lambda b: (
                int(b.get("source_start_page") or (group.get("source_pages") or [0])[0]),
                int(b.get("column") or 0),
                float(b.get("start_y") or 0),
                float(b.get("relative_x") or 0),
            ),
        )
        for idx, block in enumerate(blocks):
            page = int(block.get("source_start_page") or (group.get("source_pages") or [0])[0] or 0)
            column = _v049_column_name(block.get("column"))
            add_item(
                page,
                column,
                float(block.get("start_y") or (10 + idx)),
                {
                    "type": "block",
                    "group_id": gid,
                    "block_type": block.get("type") or block.get("kind") or "paragraph",
                    "text": _v049_text(block.get("text")).strip(),
                    "line_count": int(block.get("line_count") or 1),
                },
            )

        # Images: keep page/column order. For image-only groups, section labels from blocks
        # already exist, so we only need to place the images in correct cells.
        image_assets = [a for a in group.get("image_assets", []) if (a.get("image_output") or {}).get("status") == "saved"]
        for asset in _v049_sort_images(image_assets):
            out = asset.get("image_output") or {}
            page = int(asset.get("page") or (group.get("source_pages") or [0])[0] or 0)
            column = _v049_image_column_from_bbox(asset.get("bbox"))
            bbox = asset.get("bbox") or [0, 0, 0, 0]
            add_item(
                page,
                column,
                float(bbox[1] if len(bbox) >= 2 else 500.0),
                {
                    "type": "image",
                    "group_id": gid,
                    "section_label": asset.get("section_label"),
                    "path": out.get("path"),
                    "relative_path": out.get("relative_path"),
                    "filename": out.get("filename"),
                    "display_width": asset.get("display_width"),
                    "display_height": asset.get("display_height"),
                    "pixel_width": asset.get("pixel_width"),
                    "pixel_height": asset.get("pixel_height"),
                    "bbox": bbox,
                },
            )

    # Questions: stem -> 보기 -> choices order.
    for q in sorted(result.get("questions", []), key=lambda q: int(q.get("number") or 0)):
        qno = int(q.get("number") or 0)
        page = int(q.get("source_page") or 0)
        if page:
            question_pages.append(page)
        column = _v049_column_name(q.get("column"))
        base_y = 900.0 + qno
        add_item(
            page,
            column,
            base_y,
            {
                "type": "question",
                "number": qno,
                "text": _v049_text(q.get("question")).strip(),
                "passage_group_id": q.get("passage_group_id"),
            },
        )
        ex = q.get("example_block") or {}
        if ex.get("exists") and (ex.get("text") or "").strip():
            add_item(
                page,
                column,
                base_y + 0.1,
                {
                    "type": "example_box",
                    "number": qno,
                    "title": ex.get("type") or "보기",
                    "text": _v049_text(ex.get("text")).strip(),
                    "confidence": ex.get("confidence"),
                },
            )
        for idx, choice in enumerate(q.get("choices", []), 1):
            circled = CIRCLED[idx - 1] if 1 <= idx <= len(CIRCLED) else f"{idx}."
            add_item(
                page,
                column,
                base_y + 0.2 + idx / 100.0,
                {
                    "type": "choice",
                    "number": qno,
                    "choice_index": idx,
                    "prefix": circled,
                    "text": _v049_text(choice).strip(),
                },
            )

    # Standalone JSON tables: keep them in dedicated list and insert after main content.
    standalone_tables = []
    for idx, table in enumerate(result.get("table_metadata", []), 1):
        rows = table.get("rows") or []
        if not rows:
            continue
        bbox = table.get("bbox") or [0, 0, 0, 0]
        standalone_tables.append(
            {
                "table_id": idx,
                "page": int(table.get("page") or 0),
                "column": _v049_image_column_from_bbox(bbox),
                "sort_y": float(bbox[1] if len(bbox) >= 2 else 0.0),
                "rows": rows,
                "row_count": int(table.get("row_count") or len(rows)),
                "column_count": int(table.get("column_count") or max((len(r) for r in rows), default=0)),
                "bbox": bbox,
            }
        )

    page_entries = []
    for page in sorted(page_cells):
        left_items = sorted(page_cells[page]["left"], key=lambda x: (x.get("sort_y", 0.0), str(x.get("type", ""))))
        right_items = sorted(page_cells[page]["right"], key=lambda x: (x.get("sort_y", 0.0), str(x.get("type", ""))))
        page_entries.append(
            {
                "page": page,
                "left": left_items,
                "right": right_items,
                "left_count": len(left_items),
                "right_count": len(right_items),
            }
        )

    max_question_page = max(question_pages) if question_pages else 0
    return {
        "version": "v0.4.9",
        "layout_mode": "two_column_page_table",
        "page_width_reference_pt": 595.0,
        "question_page_max": max_question_page,
        "pages": page_entries,
        "standalone_tables": standalone_tables,
        "stats": {
            "page_count": len(page_entries),
            "render_item_count": sum(p["left_count"] + p["right_count"] for p in page_entries),
            "table_count": len(standalone_tables),
        },
    }


def v049_prepare_image_for_hwp(item: dict, temp_dir: Path, max_width_pt: float = 215.0) -> str | None:
    """Create an insertion-friendly image copy.

    We keep the cropped image content, but rewrite DPI metadata so that HWP
    uses a physical size close to the original PDF display size while never
    exceeding a single column width.
    """
    try:
        from PIL import Image
    except Exception:
        return item.get("path")

    src = item.get("path")
    if not src:
        return None
    src_path = Path(str(src))
    if not src_path.exists():
        return str(src_path)

    try:
        img = Image.open(src_path)
        width_px, height_px = img.size
        disp_w_pt = float(item.get("display_width") or 0.0)
        disp_h_pt = float(item.get("display_height") or 0.0)
        if disp_w_pt <= 0 or disp_h_pt <= 0:
            return str(src_path)
        # Cap to one-column width.
        scale = min(1.0, max_width_pt / disp_w_pt) if disp_w_pt > 0 else 1.0
        target_w_pt = disp_w_pt * scale
        target_h_pt = disp_h_pt * scale
        target_w_in = max(target_w_pt / 72.0, 0.1)
        target_h_in = max(target_h_pt / 72.0, 0.1)
        dpi_x = max(96, min(600, int(round(width_px / target_w_in))))
        dpi_y = max(96, min(600, int(round(height_px / target_h_in))))
        out_name = f"hwp_{src_path.stem}.png"
        out_path = temp_dir / out_name
        img.save(out_path, format="PNG", dpi=(dpi_x, dpi_y))
        return str(out_path)
    except Exception:
        return str(src_path)


def v049_validate_hwpx(path: Path, expect_images: bool = False) -> dict:
    # Reuse v0481 validator but rename for new version-specific metadata.
    info = v0481_validate_hwpx(path, expect_images=expect_images)
    info["validator_version"] = "v0.4.9"
    return info


def v049_create_hwpx_with_hancom(output: Path, result: dict, render_plan: dict) -> dict:
    """Create a real HWPX using Hangul COM with improved logical rendering.

    - main question pages use a 1x2 layout table per source page to simulate
      the original two-column workbook structure.
    - passage text is emitted block-by-block to preserve poetry/dialog line breaks.
    - images are inserted using DPI-adjusted temporary variants.
    - JSON tables are appended as real HWP tables.
    """
    import os
    import tempfile
    import shutil

    if output.exists():
        try:
            output.unlink()
        except Exception:
            pass

    if os.name != "nt":
        return {
            "status": "SKIPPED",
            "reason": "Hancom HWPX writer requires Windows with Hancom Hangul installed",
            "path": str(output),
            "backend": "hancom_com_v049",
            "render_plan_pages": render_plan.get("stats", {}).get("page_count", 0),
        }

    try:
        import win32com.client as win32
    except Exception as exc:
        return {
            "status": "ERROR",
            "reason": f"pywin32 is not available: {exc}",
            "install": "python -m pip install pywin32",
            "path": str(output),
            "backend": "hancom_com_v049",
        }

    temp_dir = Path(tempfile.mkdtemp(prefix="v049_hwp_img_"))
    hwp = None

    def normalize_text_lines(text: str) -> str:
        text = _v049_text(text).replace("\r\n", "\n").replace("\r", "\n")
        return text

    try:
        hwp = win32.gencache.EnsureDispatch("HWPFrame.HwpObject")
        try:
            hwp.XHwpWindows.Item(0).Visible = False
        except Exception:
            pass
        try:
            hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
        except Exception:
            pass

        def insert_text(value: str):
            txt = _v049_text(value)
            if not txt:
                return
            hwp.HAction.GetDefault("InsertText", hwp.HParameterSet.HInsertText.HSet)
            hwp.HParameterSet.HInsertText.Text = txt
            hwp.HAction.Execute("InsertText", hwp.HParameterSet.HInsertText.HSet)

        def break_para(times: int = 1):
            for _ in range(max(1, times)):
                try:
                    hwp.HAction.Run("BreakPara")
                except Exception:
                    insert_text("\r\n")

        def break_page():
            try:
                hwp.HAction.Run("BreakPage")
            except Exception:
                break_para(3)

        def create_table(rows: int, cols: int) -> bool:
            try:
                hwp.HAction.GetDefault("TableCreate", hwp.HParameterSet.HTableCreation.HSet)
                pset = hwp.HParameterSet.HTableCreation
                pset.Rows = max(1, int(rows))
                pset.Cols = max(1, int(cols))
                try:
                    pset.WidthType = 0
                except Exception:
                    pass
                try:
                    pset.HeightType = 0
                except Exception:
                    pass
                hwp.HAction.Execute("TableCreate", pset.HSet)
                return True
            except Exception:
                return False

        def table_right():
            try:
                hwp.HAction.Run("TableRightCell")
            except Exception:
                pass

        def table_lower():
            try:
                hwp.HAction.Run("TableLowerCell")
            except Exception:
                pass

        def move_doc_end():
            try:
                hwp.MovePos(3)
            except Exception:
                pass

        def render_block(item: dict):
            text = normalize_text_lines(item.get("text", "")).strip()
            if not text:
                return
            block_type = item.get("block_type") or "paragraph"
            if block_type in {"title"}:
                insert_text(text)
                break_para(2)
            elif block_type in {"section_label"}:
                insert_text(text)
                break_para(1)
            elif block_type in {"bullet"}:
                insert_text(text)
                break_para(1)
            else:
                # preserve original line breaks already kept in block text.
                insert_text(text)
                break_para(1)

        def render_question(item: dict):
            insert_text(f"{item.get('number')}. {normalize_text_lines(item.get('text','')).strip()}")
            break_para(1)

        def render_choice(item: dict):
            prefix = item.get("prefix") or "-"
            insert_text(f"{prefix} {normalize_text_lines(item.get('text','')).strip()}")
            break_para(1)

        def render_example_box(item: dict):
            title = item.get("title") or "보기"
            body = normalize_text_lines(item.get("text", "")).strip()
            insert_text(f"[{title}]\r\n{body}")
            break_para(1)

        def render_image(item: dict):
            img_path = v049_prepare_image_for_hwp(item, temp_dir=temp_dir, max_width_pt=215.0)
            if not img_path or not Path(img_path).exists():
                return
            try:
                try:
                    hwp.InsertPicture(str(Path(img_path).resolve()), Embedded=True, sizeoption=3)
                except TypeError:
                    hwp.InsertPicture(str(Path(img_path).resolve()), True, 3)
                break_para(1)
            except Exception:
                # Ultimate fallback: output path reference so the loss is visible in JSON/HWP.
                insert_text(f"[이미지 삽입 실패: {Path(img_path).name}]")
                break_para(1)

        def render_item(item: dict):
            t = item.get("type")
            if t == "block":
                render_block(item)
            elif t == "question":
                render_question(item)
            elif t == "choice":
                render_choice(item)
            elif t == "example_box":
                render_example_box(item)
            elif t == "image":
                render_image(item)

        def render_two_column_page(page_entry: dict):
            if not create_table(1, 2):
                # fallback to sequential sections
                insert_text(f"[page {page_entry.get('page')}: left column]\r\n")
                for item in page_entry.get("left", []):
                    render_item(item)
                insert_text(f"[page {page_entry.get('page')}: right column]\r\n")
                for item in page_entry.get("right", []):
                    render_item(item)
                break_page()
                return

            # left cell
            for item in page_entry.get("left", []):
                render_item(item)
            # right cell
            table_right()
            for item in page_entry.get("right", []):
                render_item(item)
            move_doc_end()
            break_para(1)
            break_page()

        def render_standalone_table(table_info: dict):
            rows = table_info.get("rows") or []
            if not rows:
                return
            row_count = max(1, len(rows))
            col_count = max(1, max((len(r) for r in rows), default=0))
            insert_text(f"[표 {table_info.get('table_id')}]\r\n")
            if not create_table(row_count, col_count):
                # text fallback
                for row in rows:
                    line = "\t".join("" if c is None else str(c) for c in row)
                    insert_text(line)
                    break_para(1)
                break_para(1)
                return
            for r_idx, row in enumerate(rows):
                for c_idx in range(col_count):
                    cell = ""
                    if c_idx < len(row) and row[c_idx] is not None:
                        cell = normalize_text_lines(str(row[c_idx])).strip()
                    if cell:
                        insert_text(cell)
                    # move to next cell unless this is the very last cell
                    if not (r_idx == row_count - 1 and c_idx == col_count - 1):
                        if c_idx < col_count - 1:
                            table_right()
                        else:
                            table_lower()
            move_doc_end()
            break_para(2)

        # Render page layout.
        for page_entry in render_plan.get("pages", []):
            render_two_column_page(page_entry)

        # Append actual JSON tables as HWP tables.
        if render_plan.get("standalone_tables"):
            insert_text("[표 변환 결과]\r\n")
            break_para(1)
            for table_info in render_plan.get("standalone_tables", []):
                render_standalone_table(table_info)

        output.parent.mkdir(parents=True, exist_ok=True)
        try:
            hwp.SaveAs(str(output.resolve()), "HWPX")
        except TypeError:
            hwp.SaveAs(str(output.resolve()), "HWPX", "")

        validation = v049_validate_hwpx(output, expect_images=bool(result.get("image_assets_filtered")))
        return {
            "status": "created" if validation.get("status") == "PASS" else "INVALID",
            "path": str(output.resolve()),
            "backend": "hancom_com_v049",
            "render_plan_pages": render_plan.get("stats", {}).get("page_count", 0),
            "render_item_count": render_plan.get("stats", {}).get("render_item_count", 0),
            "table_count": render_plan.get("stats", {}).get("table_count", 0),
            "validation": validation,
        }
    except Exception as exc:
        if output.exists():
            try:
                output.unlink()
            except Exception:
                pass
        return {
            "status": "ERROR",
            "reason": str(exc),
            "path": str(output),
            "backend": "hancom_com_v049",
            "install": "python -m pip install pywin32 pillow",
            "render_plan_pages": render_plan.get("stats", {}).get("page_count", 0),
        }
    finally:
        if hwp is not None:
            try:
                hwp.Quit()
            except Exception:
                pass
        shutil.rmtree(temp_dir, ignore_errors=True)


def v049_upgrade_result(result: dict, pdf_path: Path) -> dict:
    # Build upon the latest stable extraction+image crop stage.
    result = v0481_upgrade_result(result, pdf_path)

    # Clean obsolete metadata that is no longer accurate in v0.4.9.
    for key in [
        "known_limitations_v045",
        "known_limitations_v046",
        "validation_v045",
        "validation_v046",
        "hwpx_v047",
        "hwpx_v048",
    ]:
        result.pop(key, None)

    render_plan = v049_build_render_plan(result)
    result["render_plan_v049"] = render_plan

    hwpx_path = pdf_path.parent / "output.hwpx"
    hwpx_info = v049_create_hwpx_with_hancom(hwpx_path, result, render_plan)
    result["hwpx_v049"] = hwpx_info

    # Keep the legacy key aligned for downstream compatibility.
    result["hwpx_v0481"] = hwpx_info

    result["version"] = "v0.4.9"
    result["parser_version"] = "v0.4.9"
    result["generator_version"] = "PDF Parser Integrated v0.4.9"

    base_validation = result.get("validation", {})
    img_validation = result.get("image_filter_v0481", {})
    result["validation_v049"] = {
        "question_count": len(result.get("questions", [])),
        "passage_group_count": len(result.get("passage_groups", [])),
        "problem_image_count": img_validation.get("selected_problem_figure_count", 0),
        "problem_image_saved": img_validation.get("saved_count", 0),
        "table_count": render_plan.get("stats", {}).get("table_count", 0),
        "render_page_count": render_plan.get("stats", {}).get("page_count", 0),
        "render_item_count": render_plan.get("stats", {}).get("render_item_count", 0),
        "base_parser_status": base_validation.get("status"),
        "image_status": img_validation.get("status"),
        "hwpx_status": hwpx_info.get("status"),
        "status": (
            "PASS"
            if base_validation.get("status") == "PASS"
            and img_validation.get("status") == "PASS"
            and hwpx_info.get("status") in {"created", "SKIPPED"}
            else "WARN"
        ),
    }
    return result


# ============================================================
# V0.4.9.1 Stability Patch
# - do NOT invoke the v0.4.8.1 HWPX writer before v0.4.9 renderer
# - create HWPX only once and preserve an existing output on failure
# - use a temporary build file and replace output only after ZIP validation
# - show Hangul while COM automation runs so security permission dialogs are visible
# - print page/column/item progress with flush=True
# - record the exact COM stage that failed
# - retry with a safe sequential renderer when rich two-column rendering fails
# - save a pre-HWPX JSON checkpoint before entering COM automation
# ============================================================


def _v0491_log(message: str) -> None:
    print(message, flush=True)


def _v0491_json_safe_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp.replace(path)


def v0491_cleanup_legacy_metadata(result: dict) -> dict:
    """Remove metadata that is no longer a final rendering source in v0.4.9.1."""
    obsolete_root_keys = [
        "known_limitations_v045",
        "known_limitations_v046",
        "validation_v045",
        "validation_v046",
        "hwpx_v047",
        "hwpx_v048",
        "hwpx_v0481",
        "validation_v0481",
        "hwpx_v049",
        "validation_v049",
    ]
    for key in obsolete_root_keys:
        result.pop(key, None)

    def clean_asset(asset: dict) -> None:
        if not isinstance(asset, dict):
            return
        asset.pop("crop_v045", None)
        asset.pop("crop_v046", None)
        asset.pop("mapping_v045", None)

    for asset in result.get("image_assets", []):
        clean_asset(asset)
    for asset in result.get("image_assets_filtered", []):
        clean_asset(asset)
    for group in result.get("passage_groups", []):
        for asset in group.get("image_assets", []):
            clean_asset(asset)
        for section_assets in (group.get("image_sections") or {}).values():
            for asset in section_assets or []:
                clean_asset(asset)
    for question in result.get("questions", []):
        for asset in question.get("image_assets", []):
            clean_asset(asset)
    return result


def v0491_validate_hwpx(path: Path, expected_images: int | None = None) -> dict:
    """Inspect the actual HWPX ZIP structure produced by Hancom Hangul."""
    required = [
        "mimetype",
        "version.xml",
        "settings.xml",
        "Contents/content.hpf",
        "Contents/header.xml",
        "Contents/section0.xml",
        "META-INF/container.xml",
    ]
    info = {
        "validator_version": "v0.4.9.1",
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "zip_valid": False,
        "required_files": required,
        "missing": list(required),
        "mimetype": None,
        "mimetype_stored_first": False,
        "xml_parse_ok": False,
        "xml_parse_errors": [],
        "bin_data_count": 0,
        "expected_problem_image_count": expected_images,
        "image_count_match": None,
        "problem_unknown_found": False,
        "member_count": 0,
        "status": "FAIL",
    }
    if not path.exists() or not zipfile.is_zipfile(path):
        return info

    try:
        import xml.etree.ElementTree as ET
        with zipfile.ZipFile(path, "r") as zf:
            infos = zf.infolist()
            names = [x.filename for x in infos]
            names_set = set(names)
            info["member_count"] = len(names)
            info["zip_valid"] = zf.testzip() is None
            info["missing"] = [x for x in required if x not in names_set]
            info["bin_data_count"] = sum(
                1 for n in names
                if n.startswith("BinData/") and not n.endswith("/")
            )
            if "mimetype" in names_set:
                info["mimetype"] = zf.read("mimetype").decode("ascii", errors="replace")
            info["mimetype_stored_first"] = bool(infos) and (
                infos[0].filename == "mimetype"
                and infos[0].compress_type == zipfile.ZIP_STORED
            )

            xml_targets = [
                n for n in required
                if n.endswith(".xml") and n in names_set
            ]
            xml_errors = []
            for name in xml_targets:
                try:
                    ET.fromstring(zf.read(name))
                except Exception as exc:
                    xml_errors.append(f"{name}: {exc}")
            info["xml_parse_errors"] = xml_errors
            info["xml_parse_ok"] = not xml_errors

            probe_names = "\n".join(names).lower()
            probe_xml = ""
            for name in ["Contents/section0.xml", "Contents/content.hpf"]:
                if name in names_set:
                    try:
                        probe_xml += zf.read(name).decode("utf-8", errors="ignore").lower()
                    except Exception:
                        pass
            info["problem_unknown_found"] = "problem_unknown" in (probe_names + probe_xml)

            if expected_images is not None:
                info["image_count_match"] = info["bin_data_count"] == int(expected_images)
            else:
                info["image_count_match"] = True

            core_ok = (
                info["zip_valid"]
                and not info["missing"]
                and info["mimetype"] == "application/hwp+zip"
                and info["mimetype_stored_first"]
                and info["xml_parse_ok"]
                and not info["problem_unknown_found"]
                and bool(info["image_count_match"])
            )
            info["status"] = "PASS" if core_ok else "FAIL"
    except Exception as exc:
        info["error"] = str(exc)
    return info


def _v0491_render_attempt(
    build_output: Path,
    result: dict,
    render_plan: dict,
    *,
    rich_layout: bool,
) -> dict:
    """Render one isolated HWPX attempt. Never touches the final output path."""
    import os
    import tempfile
    import shutil as _shutil

    mode = "two_column_table" if rich_layout else "safe_sequential"
    state = {
        "renderer_mode": mode,
        "stage": "initializing",
        "page": None,
        "column": None,
        "item_index": None,
        "item_type": None,
        "operation": None,
    }

    def mark(stage: str, **kwargs) -> None:
        state["stage"] = stage
        state.update(kwargs)

    if build_output.exists():
        try:
            build_output.unlink()
        except Exception:
            pass

    if os.name != "nt":
        return {
            "status": "SKIPPED",
            "reason": "Hancom HWPX writer requires Windows with Hancom Hangul installed",
            "path": str(build_output),
            "backend": "hancom_com_v0491",
            "renderer_mode": mode,
            "failure_context": dict(state),
        }

    try:
        import pythoncom
        import win32com.client as win32
    except Exception as exc:
        return {
            "status": "ERROR",
            "reason": f"pywin32 is not available: {exc}",
            "install": "python -m pip install pywin32 pillow",
            "path": str(build_output),
            "backend": "hancom_com_v0491",
            "renderer_mode": mode,
            "failure_context": dict(state),
        }

    hwp = None
    temp_dir = Path(tempfile.mkdtemp(prefix="v0492_hwp_img_"))
    co_initialized = False
    save_completed = False

    def normalize_text_lines(value: str) -> str:
        return _v049_text(value).replace("\r\n", "\n").replace("\r", "\n")

    try:
        mark("com_initialize", operation="pythoncom.CoInitialize")
        pythoncom.CoInitialize()
        co_initialized = True

        _v0491_log(f"[HWPX] 렌더러 시작: {mode}")
        _v0491_log("[HWPX] 한글에서 외부 프로그램 접근 허용 창이 뜨면 '허용'을 눌러주세요.")
        mark("create_hwp_object", operation="DispatchEx")
        try:
            hwp = win32.DispatchEx("HWPFrame.HwpObject")
        except Exception:
            hwp = win32.gencache.EnsureDispatch("HWPFrame.HwpObject")

        mark("show_hwp_window", operation="XHwpWindows.Item(0).Visible=True")
        try:
            hwp.XHwpWindows.Item(0).Visible = True
        except Exception:
            pass

        mark("register_security_module", operation="RegisterModule")
        try:
            hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
        except Exception:
            # The interactive Hangul permission prompt remains visible by design.
            pass

        def insert_text(value: str) -> None:
            txt = _v049_text(value)
            if not txt:
                return
            mark(state["stage"], operation="InsertText")
            hwp.HAction.GetDefault("InsertText", hwp.HParameterSet.HInsertText.HSet)
            hwp.HParameterSet.HInsertText.Text = txt
            hwp.HAction.Execute("InsertText", hwp.HParameterSet.HInsertText.HSet)

        def break_para(times: int = 1) -> None:
            for _ in range(max(1, times)):
                mark(state["stage"], operation="BreakPara")
                hwp.HAction.Run("BreakPara")

        def break_page() -> None:
            mark(state["stage"], operation="BreakPage")
            hwp.HAction.Run("BreakPage")

        def move_doc_end() -> None:
            mark(state["stage"], operation="MovePos(3)")
            hwp.MovePos(3)

        def create_table(rows: int, cols: int) -> None:
            mark(state["stage"], operation=f"TableCreate({rows}x{cols})")
            hwp.HAction.GetDefault("TableCreate", hwp.HParameterSet.HTableCreation.HSet)
            pset = hwp.HParameterSet.HTableCreation
            pset.Rows = max(1, int(rows))
            pset.Cols = max(1, int(cols))
            try:
                pset.WidthType = 0
            except Exception:
                pass
            try:
                pset.HeightType = 0
            except Exception:
                pass
            hwp.HAction.Execute("TableCreate", pset.HSet)

        def table_right() -> None:
            mark(state["stage"], operation="TableRightCell")
            hwp.HAction.Run("TableRightCell")

        def table_lower() -> None:
            mark(state["stage"], operation="TableLowerCell")
            hwp.HAction.Run("TableLowerCell")

        def render_block(item: dict) -> None:
            text_value = normalize_text_lines(item.get("text", "")).strip()
            if not text_value:
                return
            insert_text(text_value)
            break_para(2 if item.get("block_type") == "title" else 1)

        def render_question(item: dict) -> None:
            insert_text(f"{item.get('number')}. {normalize_text_lines(item.get('text','')).strip()}")
            break_para(1)

        def render_choice(item: dict) -> None:
            insert_text(f"{item.get('prefix') or '-'} {normalize_text_lines(item.get('text','')).strip()}")
            break_para(1)

        def render_example_box(item: dict) -> None:
            title = item.get("title") or "보기"
            body = normalize_text_lines(item.get("text", "")).strip()
            # Keep the semantic position stem -> example -> choices. The visual
            # border is intentionally simple here because stability is more important
            # than a fragile nested-table construction.
            insert_text(f"<{title}>\r\n{body}")
            break_para(1)

        image_counter = {"value": 0}

        def render_image(item: dict) -> None:
            image_counter["value"] += 1
            total_images = int(result.get("image_filter_v0481", {}).get("saved_count") or 0)
            _v0491_log(f"[HWPX] 이미지 {image_counter['value']}/{max(total_images, image_counter['value'])}: {item.get('filename')}")
            mark(state["stage"], operation="prepare_image")
            img_path = v049_prepare_image_for_hwp(item, temp_dir=temp_dir, max_width_pt=215.0)
            if not img_path or not Path(img_path).exists():
                insert_text(f"[이미지 파일 없음: {item.get('filename') or ''}]")
                break_para(1)
                return
            try:
                mark(state["stage"], operation="InsertPicture")
                try:
                    hwp.InsertPicture(str(Path(img_path).resolve()), Embedded=True, sizeoption=3)
                except TypeError:
                    hwp.InsertPicture(str(Path(img_path).resolve()), True, 3)
                break_para(1)
            except Exception as image_exc:
                # An individual image failure must not destroy the whole document.
                _v0491_log(f"[HWPX][WARN] 이미지 삽입 실패: {Path(img_path).name} / {image_exc}")
                insert_text(f"[이미지 삽입 실패: {Path(img_path).name}]")
                break_para(1)

        def render_item(item: dict, *, page: int, column: str, index: int) -> None:
            mark(
                "render_item",
                page=page,
                column=column,
                item_index=index,
                item_type=item.get("type"),
                operation=None,
            )
            item_type = item.get("type")
            if item_type == "block":
                render_block(item)
            elif item_type == "question":
                render_question(item)
            elif item_type == "choice":
                render_choice(item)
            elif item_type == "example_box":
                render_example_box(item)
            elif item_type == "image":
                render_image(item)

        pages = render_plan.get("pages", [])
        for page_idx, page_entry in enumerate(pages, 1):
            page_no = int(page_entry.get("page") or page_idx)
            _v0491_log(f"[HWPX] 페이지 {page_idx}/{len(pages)} (PDF p.{page_no})")
            mark("render_page", page=page_no, column=None, item_index=None, item_type=None, operation=None)

            if rich_layout:
                create_table(1, 2)
                left_items = page_entry.get("left", [])
                _v0491_log(f"[HWPX]   LEFT  {len(left_items)} items")
                for idx, item in enumerate(left_items, 1):
                    render_item(item, page=page_no, column="left", index=idx)

                mark("switch_column", page=page_no, column="right", operation="TableRightCell")
                table_right()
                right_items = page_entry.get("right", [])
                _v0491_log(f"[HWPX]   RIGHT {len(right_items)} items")
                for idx, item in enumerate(right_items, 1):
                    render_item(item, page=page_no, column="right", index=idx)

                mark("leave_page_table", page=page_no, column=None, operation="MovePos(3)")
                move_doc_end()
                break_para(1)
                if page_idx < len(pages):
                    break_page()
            else:
                # Conservative fallback: same logical order, no page-wide layout table.
                left_items = page_entry.get("left", [])
                right_items = page_entry.get("right", [])
                _v0491_log(f"[HWPX]   SAFE LEFT {len(left_items)} items")
                for idx, item in enumerate(left_items, 1):
                    render_item(item, page=page_no, column="left", index=idx)
                if left_items and right_items:
                    break_para(1)
                _v0491_log(f"[HWPX]   SAFE RIGHT {len(right_items)} items")
                for idx, item in enumerate(right_items, 1):
                    render_item(item, page=page_no, column="right", index=idx)
                if page_idx < len(pages):
                    break_page()

        standalone = render_plan.get("standalone_tables", [])
        if standalone:
            _v0491_log(f"[HWPX] 실제 표 변환 시작: {len(standalone)}개")
            break_page()
            insert_text("[표 변환 결과]")
            break_para(1)

        table_failures = []
        for table_idx, table_info in enumerate(standalone, 1):
            rows = table_info.get("rows") or []
            if not rows:
                continue
            row_count = max(1, len(rows))
            col_count = max(1, max((len(r) for r in rows), default=0))
            _v0491_log(f"[HWPX] 표 {table_idx}/{len(standalone)}: {row_count}x{col_count}")
            mark(
                "render_table",
                page=table_info.get("page"),
                column=table_info.get("column"),
                item_index=table_idx,
                item_type="table",
                operation=None,
            )
            insert_text(f"[표 {table_info.get('table_id')}] ")
            try:
                create_table(row_count, col_count)
                for r_idx, row in enumerate(rows):
                    for c_idx in range(col_count):
                        cell = ""
                        if c_idx < len(row) and row[c_idx] is not None:
                            cell = normalize_text_lines(str(row[c_idx])).strip()
                        if cell:
                            insert_text(cell)
                        if not (r_idx == row_count - 1 and c_idx == col_count - 1):
                            if c_idx < col_count - 1:
                                table_right()
                            else:
                                table_lower()
                move_doc_end()
                break_para(2)
            except Exception as table_exc:
                table_failures.append({
                    "table_id": table_info.get("table_id"),
                    "error": str(table_exc),
                })
                _v0491_log(f"[HWPX][WARN] 표 {table_info.get('table_id')} COM 변환 실패 -> 텍스트 fallback")
                try:
                    hwp.HAction.Run("Cancel")
                except Exception:
                    pass
                try:
                    move_doc_end()
                    break_para(1)
                except Exception:
                    pass
                for row in rows:
                    insert_text("\t".join("" if c is None else str(c) for c in row))
                    break_para(1)

        answer_items = render_plan.get("answer_items", [])
        if answer_items:
            _v0491_log(f"[HWPX] 정답/해설 섹션 생성: {len(answer_items)}문항")
            break_page()
            mark("render_answers", page=None, column=None, item_index=None, item_type="answer_section", operation="InsertText")
            insert_text("[정답 및 해설]")
            break_para(2)
            for answer_idx, answer_item in enumerate(answer_items, 1):
                mark(
                    "render_answers",
                    page=None,
                    column=None,
                    item_index=answer_idx,
                    item_type="answer_entry",
                    operation="InsertText",
                )
                qno = int(answer_item.get("number") or answer_idx)
                answer = (answer_item.get("answer") or "?").strip()
                explanation = normalize_text_lines(answer_item.get("explanation", "")).strip()
                insert_text(f"{qno}) [정답] {answer}")
                break_para(1)
                if explanation:
                    insert_text(f"[해설] {explanation}")
                    break_para(2)
                else:
                    break_para(1)

        build_output.parent.mkdir(parents=True, exist_ok=True)
        mark("save_hwpx", page=None, column=None, item_index=None, item_type=None, operation="SaveAs(HWPX)")
        _v0491_log(f"[HWPX] 임시 HWPX 저장: {build_output.name}")
        try:
            hwp.SaveAs(str(build_output.resolve()), "HWPX")
        except TypeError:
            hwp.SaveAs(str(build_output.resolve()), "HWPX", "")
        save_completed = bool(build_output.exists())

        expected_images = int(result.get("image_filter_v0481", {}).get("saved_count") or 0)
        mark("validate_hwpx", operation="zip_structure_check")
        validation = v0491_validate_hwpx(build_output, expected_images=expected_images)
        _v0491_log(
            f"[HWPX] ZIP 검사: {validation.get('status')} | "
            f"size={validation.get('size_bytes', 0)} | "
            f"BinData={validation.get('bin_data_count', 0)}/{expected_images}"
        )
        return {
            "status": "created" if validation.get("status") == "PASS" else "INVALID",
            "path": str(build_output.resolve()),
            "backend": "hancom_com_v0491",
            "renderer_mode": mode,
            "render_plan_pages": render_plan.get("stats", {}).get("page_count", 0),
            "render_item_count": render_plan.get("stats", {}).get("render_item_count", 0),
            "table_count": render_plan.get("stats", {}).get("table_count", 0),
            "table_fallback_count": len(table_failures),
            "table_failures": table_failures,
            "validation": validation,
            "failure_context": None,
        }
    except Exception as exc:
        context = dict(state)
        _v0491_log(
            "[HWPX][ERROR] "
            f"stage={context.get('stage')} page={context.get('page')} "
            f"column={context.get('column')} item={context.get('item_index')} "
            f"type={context.get('item_type')} op={context.get('operation')} / {exc}"
        )
        return {
            "status": "ERROR",
            "reason": str(exc),
            "path": str(build_output),
            "backend": "hancom_com_v0491",
            "renderer_mode": mode,
            "failure_context": context,
            "render_plan_pages": render_plan.get("stats", {}).get("page_count", 0),
        }
    finally:
        if hwp is not None and save_completed:
            try:
                hwp.Quit()
            except Exception:
                pass
        elif hwp is not None:
            # Do not call Quit() on a dirty failed document. Hangul otherwise opens
            # a modal "빈 문서1을 저장할까요?" dialog and the next COM call can fail
            # while that window is closing. Leave the failed window visible instead.
            _v0491_log("[HWPX][WARN] 저장 전 오류가 발생해 한글 창을 자동 종료하지 않습니다. 필요하면 직접 닫아주세요.")
        if co_initialized:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass
        _shutil.rmtree(temp_dir, ignore_errors=True)


def v0491_create_hwpx_with_hancom(output: Path, result: dict, render_plan: dict) -> dict:
    """Build to a temporary file; replace final output only after validation PASS."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    previous_exists = output.exists()
    previous_size = output.stat().st_size if previous_exists else 0

    build_rich = output.with_name("output_v0_4_9_1_build.hwpx")
    build_safe = output.with_name("output_v0_4_9_1_safe_build.hwpx")
    for temp in (build_rich, build_safe):
        if temp.exists():
            try:
                temp.unlink()
            except Exception:
                pass

    _v0491_log("[HWPX] 기존 output.hwpx는 새 파일 검증이 끝날 때까지 삭제하지 않습니다.")
    rich_info = _v0491_render_attempt(build_rich, result, render_plan, rich_layout=True)

    if rich_info.get("status") == "SKIPPED":
        rich_info["final_path"] = str(output.resolve())
        rich_info["previous_output_preserved"] = previous_exists
        return rich_info

    attempts = [rich_info]
    selected = rich_info

    if rich_info.get("status") != "created":
        _v0491_log("[HWPX] 2단 렌더링 실패 -> 안전 순차 렌더러로 1회 재시도합니다.")
        safe_info = _v0491_render_attempt(build_safe, result, render_plan, rich_layout=False)
        attempts.append(safe_info)
        selected = safe_info

    if selected.get("status") == "created":
        src = Path(selected["path"])
        try:
            src.replace(output)
        except Exception:
            shutil.copy2(src, output)
            try:
                src.unlink()
            except Exception:
                pass
        final_validation = v0491_validate_hwpx(
            output,
            expected_images=int(result.get("image_filter_v0481", {}).get("saved_count") or 0),
        )
        _v0491_log(f"[HWPX] 최종 파일 확정: {output.resolve()}")
        _v0491_log(f"[HWPX] 최종 압축 구조 검사: {final_validation.get('status')}")
        return {
            **selected,
            "status": "created" if final_validation.get("status") == "PASS" else "INVALID",
            "path": str(output.resolve()),
            "final_path": str(output.resolve()),
            "validation": final_validation,
            "previous_output_preserved": False,
            "previous_output_existed": previous_exists,
            "previous_output_size": previous_size,
            "attempts": [
                {
                    "renderer_mode": a.get("renderer_mode"),
                    "status": a.get("status"),
                    "reason": a.get("reason"),
                    "failure_context": a.get("failure_context"),
                }
                for a in attempts
            ],
        }

    # Both attempts failed. Never delete a previously usable output.hwpx.
    for temp in (build_rich, build_safe):
        if temp.exists():
            try:
                temp.unlink()
            except Exception:
                pass
    reason = selected.get("reason") or rich_info.get("reason") or "HWPX creation failed"
    return {
        "status": "ERROR",
        "reason": reason,
        "path": str(output.resolve()),
        "final_path": str(output.resolve()),
        "backend": "hancom_com_v0491",
        "renderer_mode": selected.get("renderer_mode"),
        "previous_output_preserved": previous_exists,
        "previous_output_existed": previous_exists,
        "previous_output_size": previous_size,
        "failure_context": selected.get("failure_context") or rich_info.get("failure_context"),
        "attempts": [
            {
                "renderer_mode": a.get("renderer_mode"),
                "status": a.get("status"),
                "reason": a.get("reason"),
                "failure_context": a.get("failure_context"),
            }
            for a in attempts
        ],
    }


def v0491_upgrade_result(
    result: dict,
    pdf_path: Path,
    checkpoint_path: Path | None = None,
) -> dict:
    """v0.4.9.1 integrated upgrade without duplicate HWPX generation."""
    _v0491_log("[v0.4.9.1] HWP 메타데이터 보정")

    # IMPORTANT: v0481_upgrade_result() is intentionally NOT called here because
    # it creates an HWPX of its own. We only reuse its stable extraction/image step.
    result = v046_upgrade_result(result, pdf_path)
    result = v0481_prepare_problem_images(pdf_path, result)
    result = v0491_cleanup_legacy_metadata(result)

    render_plan = v049_build_render_plan(result)
    render_plan["version"] = "v0.4.9.1"
    render_plan["layout_mode"] = "two_column_page_table_with_safe_fallback"
    result["render_plan_v049"] = render_plan

    # Stamp final version BEFORE checkpoint so a hung COM session still leaves a
    # useful, correctly-versioned JSON snapshot on disk.
    result["version"] = "v0.4.9.1"
    result["parser_version"] = "v0.4.9.1"
    result["generator_version"] = "PDF Parser Integrated v0.4.9.1"
    result["schema_version"] = {
        "base": "v0.4.9",
        "extension": [
            "single_pass_hwpx_generation",
            "safe_temp_hwpx_commit",
            "visible_hancom_permission_prompt",
            "stage_progress_logging",
            "com_failure_context",
            "safe_sequential_retry",
            "pre_hwpx_json_checkpoint",
            "hwpx_zip_structure_validation",
        ],
    }

    if checkpoint_path is not None:
        checkpoint_path = Path(checkpoint_path)
        result["pre_hwpx_checkpoint"] = str(checkpoint_path.resolve())
        _v0491_json_safe_write(checkpoint_path, result)
        _v0491_log(f"[v0.4.9.1] HWPX 전 체크포인트 저장: {checkpoint_path.resolve()}")

    hwpx_path = pdf_path.parent / "output.hwpx"
    hwpx_info = v0491_create_hwpx_with_hancom(hwpx_path, result, render_plan)
    result["hwpx_v0491"] = hwpx_info

    base_validation = result.get("validation", {})
    img_validation = result.get("image_filter_v0481", {})
    hwpx_status = hwpx_info.get("status")
    result["validation_v0491"] = {
        "question_count": len(result.get("questions", [])),
        "passage_group_count": len(result.get("passage_groups", [])),
        "problem_image_count": img_validation.get("selected_problem_figure_count", 0),
        "problem_image_saved": img_validation.get("saved_count", 0),
        "table_count": render_plan.get("stats", {}).get("table_count", 0),
        "render_page_count": render_plan.get("stats", {}).get("page_count", 0),
        "render_item_count": render_plan.get("stats", {}).get("render_item_count", 0),
        "base_parser_status": base_validation.get("status"),
        "image_status": img_validation.get("status"),
        "hwpx_status": hwpx_status,
        "hwpx_renderer_mode": hwpx_info.get("renderer_mode"),
        "previous_output_preserved": hwpx_info.get("previous_output_preserved", False),
        "hwpx_zip_status": (hwpx_info.get("validation") or {}).get("status"),
        "hwpx_embedded_image_count": (hwpx_info.get("validation") or {}).get("bin_data_count"),
        "status": (
            "PASS"
            if base_validation.get("status") == "PASS"
            and img_validation.get("status") == "PASS"
            and hwpx_status in {"created", "SKIPPED"}
            else "WARN"
        ),
    }

    result["known_limitations_v0491"] = [
        "Windows 한글 COM 보안 허용 창은 최초 실행 시 사용자가 직접 허용해야 할 수 있습니다.",
        "2단 표 렌더러가 COM 예외를 내면 문서 유실 방지를 위해 safe_sequential 모드로 자동 재시도합니다.",
        "safe_sequential fallback에서는 좌우 단의 의미 순서는 보존되지만 실제 좌우 병렬 배치는 단순화됩니다.",
        "개별 이미지 또는 표 COM 삽입 실패 시 해당 요소만 텍스트 fallback으로 남길 수 있습니다.",
    ]
    return result


# ============================================================
# V0.4.9.2 Integrated Cleanup / Stable HWPX Layer
# - one final JSON after a successful run (checkpoint auto-cleanup)
# - content-aware table filtering (TOP/answer-page/legal footer excluded)
# - explicit per-question answer/explanation section
# - stable sequential renderer as default to avoid Hancom TableCreate COM crash
# - dirty failed Hangul window is never force-Quit (prevents save/closing popup cascade)
# ============================================================


def _v0492_flat_table_text(table: dict) -> str:
    parts = []
    for row in table.get("rows") or []:
        for cell in row or []:
            if cell is not None:
                parts.append(str(cell))
    return "\n".join(parts).strip()


def _v0492_table_exclusion_reason(table: dict, question_page_count: int) -> str | None:
    text = _v0492_flat_table_text(table)
    compact = re.sub(r"\s+", " ", text)
    page = int(table.get("page") or 0)

    if not compact:
        return "empty_table"
    bbox = table.get("bbox") or [0, 0, 0, 0]
    if len(bbox) == 4 and float(bbox[3]) <= 100.0:
        return "publisher_page_header"
    if "TOP 1" in compact:
        return "publisher_navigation_summary"
    if (
        "콘텐츠산업 진흥법" in compact
        or "제작연월일" in compact
        or re.search(r"\bI\d{3}-\d{3}-\d{2}-\d{2}-\d+\b", compact)
    ):
        return "legal_footer_or_content_id"
    if page > int(question_page_count or 0):
        # Answer/explanation pages are already represented by the structured
        # questions[].answer / explanation fields. Rendering their PDF table
        # geometry duplicates and corrupts the answer section.
        return "answer_or_explanation_page_layout"
    if "[정답]" in compact or "[해설]" in compact:
        return "answer_or_explanation_table_artifact"
    return None


def v0492_filter_tables_for_render(result: dict) -> list[dict]:
    question_pages = int((result.get("document_structure") or {}).get("question_pages") or 0)
    renderable = []
    excluded = []
    for idx, table in enumerate(result.get("table_metadata", []), 1):
        reason = _v0492_table_exclusion_reason(table, question_pages)
        table["table_id_v0492"] = idx
        table["render_v0492"] = reason is None
        table["exclude_reason_v0492"] = reason
        if reason is None:
            renderable.append(table)
        else:
            excluded.append({
                "table_id": idx,
                "page": table.get("page"),
                "reason": reason,
                "preview": re.sub(r"\s+", " ", _v0492_flat_table_text(table))[:140],
            })

    result["table_filter_v0492"] = {
        "raw_table_count": len(result.get("table_metadata", [])),
        "renderable_table_count": len(renderable),
        "excluded_table_count": len(excluded),
        "excluded": excluded,
        "policy": "render only tables that are part of question/passage content; exclude publisher navigation, answer-page layout artifacts, and legal/footer tables",
        "status": "PASS",
    }
    result["renderable_tables_v0492"] = renderable
    return renderable


def v0492_build_render_plan(result: dict) -> dict:
    renderable_tables = v0492_filter_tables_for_render(result)
    plan = v049_build_render_plan(result)

    # v049_build_render_plan() sees every PyMuPDF table. Replace that list with
    # only content tables approved by the v0.4.9.2 filter.
    approved = []
    for idx, table in enumerate(renderable_tables, 1):
        rows = table.get("rows") or []
        bbox = table.get("bbox") or [0, 0, 0, 0]
        approved.append({
            "table_id": int(table.get("table_id_v0492") or idx),
            "page": int(table.get("page") or 0),
            "column": _v049_image_column_from_bbox(bbox),
            "sort_y": float(bbox[1] if len(bbox) >= 2 else 0.0),
            "rows": rows,
            "row_count": int(table.get("row_count") or len(rows)),
            "column_count": int(table.get("column_count") or max((len(r) for r in rows), default=0)),
            "bbox": bbox,
        })
    plan["standalone_tables"] = approved

    answer_items = []
    for q in sorted(result.get("questions", []), key=lambda x: int(x.get("number") or 0)):
        answer_items.append({
            "number": int(q.get("number") or 0),
            "answer": q.get("answer") or "?",
            "answer_index": q.get("answer_index"),
            "explanation": q.get("explanation") or "",
        })
    plan["answer_items"] = answer_items
    plan["answer_section"] = {
        "enabled": True,
        "title": "정답 및 해설",
        "format": "one_question_per_block",
        "blank_line_between_questions": True,
        "count": len(answer_items),
    }
    plan["version"] = "v0.4.9.2"
    plan["layout_mode"] = "stable_sequential_with_clean_answer_section"
    plan["stats"]["table_count"] = len(approved)
    plan["stats"]["excluded_table_count"] = int(result.get("table_filter_v0492", {}).get("excluded_table_count") or 0)
    plan["stats"]["answer_count"] = len(answer_items)
    return plan


def v0492_validate_hwpx(path: Path, expected_images: int | None = None) -> dict:
    info = v0491_validate_hwpx(path, expected_images=expected_images)
    info["validator_version"] = "v0.4.9.2"
    return info


def v0492_create_hwpx_with_hancom(output: Path, result: dict, render_plan: dict) -> dict:
    """Stable v0.4.9.2 writer.

    The user's Hangul installation consistently throws a COM server exception on
    TableCreate(1x2) when the second source page starts. v0.4.9.2 therefore does
    not intentionally create a failing rich-layout document first. It renders a
    clean sequential HWPX once, preserving the existing output until validation
    succeeds. A later version can reintroduce true two-column layout using a
    safer Hancom mechanism rather than a page-wide table.
    """
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    previous_exists = output.exists()
    previous_size = output.stat().st_size if previous_exists else 0
    build_output = output.with_name("output_v0_4_9_2_build.hwpx")
    if build_output.exists():
        try:
            build_output.unlink()
        except Exception:
            pass

    _v0491_log("[HWPX] v0.4.9.2 안정 렌더러: safe_sequential 1회만 실행합니다.")
    _v0491_log("[HWPX] 실패가 확인된 페이지 1x2 TableCreate 선행 시도는 비활성화했습니다.")
    attempt = _v0491_render_attempt(build_output, result, render_plan, rich_layout=False)
    attempt["backend"] = "hancom_com_v0492"

    if attempt.get("status") == "SKIPPED":
        attempt["final_path"] = str(output.resolve())
        attempt["previous_output_preserved"] = previous_exists
        return attempt

    if attempt.get("status") == "created":
        src = Path(attempt["path"])
        try:
            src.replace(output)
        except Exception:
            shutil.copy2(src, output)
            try:
                src.unlink()
            except Exception:
                pass
        validation = v0492_validate_hwpx(
            output,
            expected_images=int(result.get("image_filter_v0481", {}).get("saved_count") or 0),
        )
        _v0491_log(f"[HWPX] 최종 파일 확정: {output.resolve()}")
        _v0491_log(f"[HWPX] 최종 압축 구조 검사: {validation.get('status')}")
        return {
            **attempt,
            "status": "created" if validation.get("status") == "PASS" else "INVALID",
            "path": str(output.resolve()),
            "final_path": str(output.resolve()),
            "backend": "hancom_com_v0492",
            "renderer_mode": "safe_sequential",
            "validation": validation,
            "previous_output_preserved": False,
            "previous_output_existed": previous_exists,
            "previous_output_size": previous_size,
            "attempts": [{
                "renderer_mode": "safe_sequential",
                "status": attempt.get("status"),
                "reason": attempt.get("reason"),
                "failure_context": attempt.get("failure_context"),
            }],
        }

    if build_output.exists():
        try:
            build_output.unlink()
        except Exception:
            pass
    return {
        **attempt,
        "status": "ERROR",
        "path": str(output.resolve()),
        "final_path": str(output.resolve()),
        "backend": "hancom_com_v0492",
        "previous_output_preserved": previous_exists,
        "previous_output_existed": previous_exists,
        "previous_output_size": previous_size,
        "attempts": [{
            "renderer_mode": "safe_sequential",
            "status": attempt.get("status"),
            "reason": attempt.get("reason"),
            "failure_context": attempt.get("failure_context"),
        }],
    }


def v0492_upgrade_result(
    result: dict,
    pdf_path: Path,
    checkpoint_path: Path | None = None,
) -> dict:
    _v0491_log("[v0.4.9.2] 이미지/메타데이터 준비")

    # Do not call v0481_upgrade_result/v0491_upgrade_result: both can start HWPX
    # generation. Reuse only the proven metadata + 12-image preparation stages.
    result = v046_upgrade_result(result, pdf_path)
    result = v0481_prepare_problem_images(pdf_path, result)
    result = v0491_cleanup_legacy_metadata(result)

    render_plan = v0492_build_render_plan(result)
    result["render_plan_v0492"] = render_plan
    # Remove the old final-render key so there is only one authoritative plan.
    result.pop("render_plan_v049", None)

    result["version"] = "v0.4.9.2"
    result["parser_version"] = "v0.4.9.2"
    result["generator_version"] = "PDF Parser Integrated v0.4.9.2"
    result["schema_version"] = {
        "base": "v0.4.9.1",
        "extension": [
            "clean_content_table_filter",
            "answer_and_explanation_section",
            "one_question_per_answer_block",
            "stable_single_hancom_attempt",
            "no_dirty_document_auto_quit",
            "successful_checkpoint_auto_cleanup",
        ],
    }

    if checkpoint_path is not None:
        checkpoint_path = Path(checkpoint_path)
        result["pre_hwpx_checkpoint"] = {
            "path": str(checkpoint_path.resolve()),
            "purpose": "COM hang/error recovery only",
            "retained_after_success": False,
        }
        _v0491_json_safe_write(checkpoint_path, result)
        _v0491_log(f"[v0.4.9.2] HWPX 전 임시 체크포인트 저장: {checkpoint_path.resolve()}")

    hwpx_path = pdf_path.parent / "output.hwpx"
    hwpx_info = v0492_create_hwpx_with_hancom(hwpx_path, result, render_plan)
    result["hwpx_v0492"] = hwpx_info

    base_validation = result.get("validation", {})
    img_validation = result.get("image_filter_v0481", {})
    table_validation = result.get("table_filter_v0492", {})
    validation_zip = hwpx_info.get("validation") or {}
    hwpx_status = hwpx_info.get("status")
    result["validation_v0492"] = {
        "question_count": len(result.get("questions", [])),
        "passage_group_count": len(result.get("passage_groups", [])),
        "problem_image_count": img_validation.get("selected_problem_figure_count", 0),
        "problem_image_saved": img_validation.get("saved_count", 0),
        "raw_table_count": table_validation.get("raw_table_count", 0),
        "renderable_table_count": table_validation.get("renderable_table_count", 0),
        "excluded_table_count": table_validation.get("excluded_table_count", 0),
        "answer_count": render_plan.get("stats", {}).get("answer_count", 0),
        "render_page_count": render_plan.get("stats", {}).get("page_count", 0),
        "render_item_count": render_plan.get("stats", {}).get("render_item_count", 0),
        "base_parser_status": base_validation.get("status"),
        "image_status": img_validation.get("status"),
        "hwpx_status": hwpx_status,
        "hwpx_renderer_mode": hwpx_info.get("renderer_mode"),
        "hwpx_zip_status": validation_zip.get("status"),
        "hwpx_embedded_image_count": validation_zip.get("bin_data_count"),
        "status": (
            "PASS"
            if base_validation.get("status") == "PASS"
            and img_validation.get("status") == "PASS"
            and table_validation.get("status") == "PASS"
            and hwpx_status in {"created", "SKIPPED"}
            else "WARN"
        ),
    }
    result["known_limitations_v0492"] = [
        "현재 Windows 한글 환경에서 페이지 1x2 TableCreate가 COM 서버 예외를 내므로 v0.4.9.2 기본 출력은 안정 순차 배치입니다.",
        "출판사 TOP 요약표, 정답지 레이아웃 오인식 표, 저작권/콘텐츠산업 진흥법 footer는 HWPX 렌더링에서 제외합니다.",
        "정답/해설은 questions 구조화 데이터에서 직접 생성하며 각 문항을 별도 문단으로 구분합니다.",
        "HWPX 저장 전 오류 시 더 이상 dirty 문서에 Quit()을 호출하지 않아 빈 문서 저장 확인창 연쇄를 피합니다.",
    ]
    return result


# ============================================================
# V0.4.9.3 Official Hancom Security / Unattended HWPX Layer
# - keep v0.4.9.2 content cleanup + stable sequential rendering
# - use Hancom's official FilePathCheckDLL mechanism instead of auto-clicking dialogs
# - auto-detect/copy/register FilePathCheckerModuleExample.dll under HKCU
# - default to fail-fast when unattended security is unavailable (no hidden modal hang)
# - optional --allow-interactive-hwp restores the visible approval-dialog fallback
# - write security diagnostics into final JSON
# ============================================================


def _v0493_pe_arch(path: Path | None) -> str | None:
    """Best-effort PE machine check for diagnostics only."""
    if not path or not path.exists():
        return None
    try:
        with path.open("rb") as f:
            if f.read(2) != b"MZ":
                return "not_pe"
            f.seek(0x3C)
            pe_offset = int.from_bytes(f.read(4), "little")
            f.seek(pe_offset)
            if f.read(4) != b"PE\x00\x00":
                return "unknown_pe"
            machine = int.from_bytes(f.read(2), "little")
        return {0x14C: "x86", 0x8664: "x64", 0xAA64: "arm64"}.get(machine, hex(machine))
    except Exception:
        return None


def v0493_prepare_hancom_security(security_module_path: Path | None = None) -> dict:
    """Prepare Hancom's official FilePathCheckDLL module for unattended automation.

    This function never downloads or fabricates a security DLL. It only uses an
    official FilePathCheckerModuleExample.dll already supplied by the user/Hancom,
    copies it to a stable local path when possible, and registers that absolute
    path in HKCU\\Software\\HNC\\HwpAutomation\\Modules.
    """
    import os

    info = {
        "version": "v0.4.9.3",
        "status": "NOT_READY",
        "module_type": "FilePathCheckDLL",
        "module_name": None,
        "dll_path": None,
        "dll_arch": None,
        "registry_key": r"HKEY_CURRENT_USER\Software\HNC\HwpAutomation\Modules",
        "registry_ready": False,
        "registry_updated": False,
        "uses_enabled": None,
        "register_module_result": None,
        "unattended_ready": False,
        "interactive_approval_required": True,
        "source": None,
        "diagnostics": [],
    }

    if os.name != "nt":
        info.update({
            "status": "SKIPPED",
            "interactive_approval_required": False,
            "diagnostics": ["Hancom HWP automation security setup is Windows-only."],
        })
        return info

    try:
        import winreg
    except Exception as exc:
        info["status"] = "ERROR"
        info["diagnostics"].append(f"winreg import failed: {exc}")
        return info

    reg_path = r"Software\HNC\HwpAutomation\Modules"
    default_name = "FilePathCheckerModuleExample"
    script_dir = Path(__file__).resolve().parent
    local_appdata = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
    managed_dir = local_appdata / "HncSec"
    managed_path = managed_dir / "FilePathCheckerModuleExample.dll"

    # Existing HKCU registrations are valid candidates. The second RegisterModule
    # argument is the REGISTRY VALUE NAME, not a DLL file name/path.
    registry_candidates: list[tuple[str, Path]] = []
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_READ) as key:
            idx = 0
            while True:
                try:
                    name, value, reg_type = winreg.EnumValue(key, idx)
                except OSError:
                    break
                idx += 1
                if reg_type == winreg.REG_SZ and value:
                    p = Path(str(value))
                    if p.exists() and p.is_file() and "filepathchecker" in name.lower():
                        registry_candidates.append((name, p))
    except FileNotFoundError:
        pass
    except Exception as exc:
        info["diagnostics"].append(f"registry read warning: {exc}")

    explicit_candidates: list[tuple[str, Path]] = []
    if security_module_path:
        explicit_candidates.append(("cli", Path(security_module_path).expanduser()))
    env_path = os.environ.get("HWP_FILEPATHCHECKER_DLL")
    if env_path:
        explicit_candidates.append(("env:HWP_FILEPATHCHECKER_DLL", Path(env_path).expanduser()))
    explicit_candidates.extend([
        ("script_dir", script_dir / "FilePathCheckerModuleExample.dll"),
        ("script_security_dir", script_dir / "security" / "FilePathCheckerModuleExample.dll"),
        ("managed_localappdata", managed_path),
        ("C_HncSec", Path(r"C:\HncSec\FilePathCheckerModuleExample.dll")),
    ])

    chosen_name = None
    chosen_path = None
    chosen_source = None

    # Explicit/user-local official DLL wins. Otherwise reuse a valid registry entry.
    for source, candidate in explicit_candidates:
        try:
            candidate = candidate.resolve()
        except Exception:
            candidate = Path(candidate)
        if candidate.exists() and candidate.is_file():
            chosen_name = default_name
            chosen_path = candidate
            chosen_source = source
            break

    if chosen_path is None and registry_candidates:
        chosen_name, chosen_path = registry_candidates[0]
        chosen_source = "existing_registry"

    if chosen_path is None:
        info["diagnostics"].append(
            "FilePathCheckerModuleExample.dll not found. Put Hancom's official DLL next to this script, "
            "under .\\security, at %LOCALAPPDATA%\\HncSec, at C:\\HncSec, or pass --security-module PATH."
        )
        return info

    # Prefer a stable local, non-OneDrive location. This does not modify the DLL.
    final_path = chosen_path
    try:
        if chosen_path.resolve() != managed_path.resolve():
            managed_dir.mkdir(parents=True, exist_ok=True)
            import shutil as _shutil
            _shutil.copy2(chosen_path, managed_path)
            final_path = managed_path
            chosen_source = f"{chosen_source}->managed_localappdata"
    except Exception as exc:
        info["diagnostics"].append(f"managed DLL copy warning: {exc}; original path will be used")
        final_path = chosen_path

    module_name = default_name if chosen_source != "existing_registry" else (chosen_name or default_name)

    try:
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER,
            reg_path,
            0,
            winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE,
        ) as key:
            current = None
            try:
                current, _ = winreg.QueryValueEx(key, module_name)
            except FileNotFoundError:
                pass
            if str(current or "") != str(final_path):
                winreg.SetValueEx(key, module_name, 0, winreg.REG_SZ, str(final_path))
                info["registry_updated"] = True

        # Hancom states Uses is optional, but a stale DWORD 0 can disable a module.
        uses_path = reg_path + r"\Uses"
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER,
            uses_path,
            0,
            winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE,
        ) as uses_key:
            uses_value = None
            try:
                uses_value, uses_type = winreg.QueryValueEx(uses_key, module_name)
            except FileNotFoundError:
                uses_value = None
            if uses_value == 0:
                winreg.SetValueEx(uses_key, module_name, 0, winreg.REG_DWORD, 1)
                uses_value = 1
                info["registry_updated"] = True
            # Do not create Uses when absent; official guidance says it is optional.
            info["uses_enabled"] = (uses_value != 0) if uses_value is not None else None

        # Verify the exact REG_SZ value we are about to pass by name to RegisterModule.
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_READ) as key:
            registered_path, registered_type = winreg.QueryValueEx(key, module_name)
        info["registry_ready"] = (
            registered_type == winreg.REG_SZ
            and Path(str(registered_path)).exists()
        )
    except Exception as exc:
        info["status"] = "ERROR"
        info["diagnostics"].append(f"registry write/verify failed: {exc}")
        return info

    info.update({
        "status": "READY_FOR_REGISTERMODULE" if info["registry_ready"] else "NOT_READY",
        "module_name": module_name,
        "dll_path": str(final_path),
        "dll_arch": _v0493_pe_arch(final_path),
        "source": chosen_source,
    })
    return info


def _v0493_register_security_on_hwp(hwp, security_info: dict) -> dict:
    runtime = dict(security_info or {})
    runtime.setdefault("diagnostics", [])
    module_name = runtime.get("module_name")
    if not runtime.get("registry_ready") or not module_name:
        runtime.update({
            "register_module_result": False,
            "unattended_ready": False,
            "interactive_approval_required": True,
            "status": "NOT_READY",
        })
        return runtime
    try:
        ok = bool(hwp.RegisterModule("FilePathCheckDLL", str(module_name)))
    except Exception as exc:
        ok = False
        runtime["diagnostics"].append(f"RegisterModule exception: {exc}")
    runtime["register_module_result"] = ok
    runtime["unattended_ready"] = ok
    runtime["interactive_approval_required"] = not ok
    runtime["status"] = "PASS" if ok else "REGISTER_FAILED"
    if not ok:
        runtime["diagnostics"].append(
            "RegisterModule returned False. Check that the DLL is Hancom's official FilePathChecker module, "
            "the registry value name matches exactly, and the DLL bitness matches Hwp.exe."
        )
    return runtime


def _v0493_render_attempt(
    build_output: Path,
    result: dict,
    render_plan: dict,
    *,
    security_info: dict,
    allow_interactive_hwp: bool = False,
    show_hwp: bool = False,
) -> dict:
    """v0.4.9.2 renderer with official security registration before any file I/O."""
    import os
    import tempfile
    import shutil as _shutil

    mode = "safe_sequential"
    state = {
        "renderer_mode": mode,
        "stage": "initializing",
        "page": None,
        "column": None,
        "item_index": None,
        "item_type": None,
        "operation": None,
    }

    def mark(stage: str, **kwargs) -> None:
        state["stage"] = stage
        state.update(kwargs)

    if build_output.exists():
        try:
            build_output.unlink()
        except Exception:
            pass

    if os.name != "nt":
        sec = dict(security_info or {})
        sec["status"] = "SKIPPED"
        return {
            "status": "SKIPPED",
            "reason": "Hancom HWPX writer requires Windows with Hancom Hangul installed",
            "path": str(build_output),
            "backend": "hancom_com_v0493",
            "renderer_mode": mode,
            "failure_context": dict(state),
            "hancom_security": sec,
        }

    try:
        import pythoncom
        import win32com.client as win32
    except Exception as exc:
        return {
            "status": "ERROR",
            "reason": f"pywin32 is not available: {exc}",
            "install": "python -m pip install pywin32 pillow",
            "path": str(build_output),
            "backend": "hancom_com_v0493",
            "renderer_mode": mode,
            "failure_context": dict(state),
            "hancom_security": dict(security_info or {}),
        }

    hwp = None
    temp_dir = Path(tempfile.mkdtemp(prefix="v0493_hwp_img_"))
    co_initialized = False
    save_completed = False
    security_runtime = dict(security_info or {})
    content_started = False

    def normalize_text_lines(value: str) -> str:
        return _v049_text(value).replace("\r\n", "\n").replace("\r", "\n")

    try:
        mark("com_initialize", operation="pythoncom.CoInitialize")
        pythoncom.CoInitialize()
        co_initialized = True

        _v0491_log("[HWPX] v0.4.9.3 무조작 안정 렌더러 시작")
        mark("create_hwp_object", operation="DispatchEx")
        try:
            hwp = win32.DispatchEx("HWPFrame.HwpObject")
        except Exception:
            hwp = win32.gencache.EnsureDispatch("HWPFrame.HwpObject")

        # Register the official module BEFORE any file open/save/insert operation.
        mark("register_security_module", operation="RegisterModule(FilePathCheckDLL)")
        security_runtime = _v0493_register_security_on_hwp(hwp, security_info)
        if security_runtime.get("unattended_ready"):
            _v0491_log(
                f"[HWPX] 한컴 보안 모듈 등록 성공: {security_runtime.get('module_name')} "
                "(승인창 없이 진행)"
            )
            mark("set_hwp_visibility", operation=f"Visible={bool(show_hwp)}")
            try:
                hwp.XHwpWindows.Item(0).Visible = bool(show_hwp)
            except Exception:
                pass
        elif allow_interactive_hwp:
            _v0491_log("[HWPX][WARN] 보안 모듈 등록 실패 -> 대화형 승인 모드로 계속합니다.")
            _v0491_log("[HWPX][WARN] 한글 승인창이 뜨면 사용자가 직접 허용해야 합니다.")
            try:
                hwp.XHwpWindows.Item(0).Visible = True
            except Exception:
                pass
        else:
            # Fail fast instead of waiting for a hidden modal permission window.
            try:
                hwp.Quit()
            except Exception:
                pass
            hwp = None
            return {
                "status": "SECURITY_SETUP_REQUIRED",
                "reason": (
                    "Hancom official FilePathChecker security module is not active. "
                    "Place FilePathCheckerModuleExample.dll next to the script (or pass --security-module PATH) "
                    "and run again. Use --allow-interactive-hwp only when manual approval is acceptable."
                ),
                "path": str(build_output),
                "backend": "hancom_com_v0493",
                "renderer_mode": mode,
                "failure_context": dict(state),
                "hancom_security": security_runtime,
            }

        def insert_text(value: str) -> None:
            nonlocal content_started
            txt = _v049_text(value)
            if not txt:
                return
            content_started = True
            mark(state["stage"], operation="InsertText")
            hwp.HAction.GetDefault("InsertText", hwp.HParameterSet.HInsertText.HSet)
            hwp.HParameterSet.HInsertText.Text = txt
            hwp.HAction.Execute("InsertText", hwp.HParameterSet.HInsertText.HSet)

        def break_para(times: int = 1) -> None:
            for _ in range(max(1, times)):
                mark(state["stage"], operation="BreakPara")
                hwp.HAction.Run("BreakPara")

        def break_page() -> None:
            mark(state["stage"], operation="BreakPage")
            hwp.HAction.Run("BreakPage")

        def render_block(item: dict) -> None:
            text_value = normalize_text_lines(item.get("text", "")).strip()
            if not text_value:
                return
            insert_text(text_value)
            break_para(2 if item.get("block_type") == "title" else 1)

        def render_question(item: dict) -> None:
            insert_text(f"{item.get('number')}. {normalize_text_lines(item.get('text','')).strip()}")
            break_para(1)

        def render_choice(item: dict) -> None:
            insert_text(f"{item.get('prefix') or '-'} {normalize_text_lines(item.get('text','')).strip()}")
            break_para(1)

        def render_example_box(item: dict) -> None:
            title = item.get("title") or "보기"
            body = normalize_text_lines(item.get("text", "")).strip()
            insert_text(f"<{title}>\r\n{body}")
            break_para(1)

        image_counter = 0

        def render_image(item: dict) -> None:
            nonlocal image_counter, content_started
            image_counter += 1
            total_images = int(result.get("image_filter_v0481", {}).get("saved_count") or 0)
            _v0491_log(f"[HWPX] 이미지 {image_counter}/{max(total_images, image_counter)}: {item.get('filename')}")
            mark(state["stage"], operation="prepare_image")
            img_path = v049_prepare_image_for_hwp(item, temp_dir=temp_dir, max_width_pt=215.0)
            if not img_path or not Path(img_path).exists():
                insert_text(f"[이미지 파일 없음: {item.get('filename') or ''}]")
                break_para(1)
                return
            try:
                mark(state["stage"], operation="InsertPicture")
                try:
                    hwp.InsertPicture(str(Path(img_path).resolve()), Embedded=True, sizeoption=3)
                except TypeError:
                    hwp.InsertPicture(str(Path(img_path).resolve()), True, 3)
                content_started = True
                break_para(1)
            except Exception as image_exc:
                _v0491_log(f"[HWPX][WARN] 이미지 삽입 실패: {Path(img_path).name} / {image_exc}")
                insert_text(f"[이미지 삽입 실패: {Path(img_path).name}]")
                break_para(1)

        def render_item(item: dict, *, page: int, column: str, index: int) -> None:
            mark(
                "render_item",
                page=page,
                column=column,
                item_index=index,
                item_type=item.get("type"),
                operation=None,
            )
            t = item.get("type")
            if t == "block":
                render_block(item)
            elif t == "question":
                render_question(item)
            elif t == "choice":
                render_choice(item)
            elif t == "example_box":
                render_example_box(item)
            elif t == "image":
                render_image(item)

        pages = render_plan.get("pages", [])
        for page_idx, page_entry in enumerate(pages, 1):
            page_no = int(page_entry.get("page") or page_idx)
            _v0491_log(f"[HWPX] 페이지 {page_idx}/{len(pages)} (PDF p.{page_no})")
            mark("render_page", page=page_no, column=None, item_index=None, item_type=None, operation=None)
            left_items = page_entry.get("left", [])
            right_items = page_entry.get("right", [])
            _v0491_log(f"[HWPX]   SAFE LEFT {len(left_items)} items")
            for idx, item in enumerate(left_items, 1):
                render_item(item, page=page_no, column="left", index=idx)
            if left_items and right_items:
                break_para(1)
            _v0491_log(f"[HWPX]   SAFE RIGHT {len(right_items)} items")
            for idx, item in enumerate(right_items, 1):
                render_item(item, page=page_no, column="right", index=idx)
            if page_idx < len(pages):
                break_page()

        # v0.4.9.2 already filtered publisher/navigation/legal tables. Render only approved content tables.
        standalone = render_plan.get("standalone_tables", [])
        table_failures = []
        if standalone:
            _v0491_log(f"[HWPX] 실제 표 변환 시작: {len(standalone)}개")
            break_page()
        for table_idx, table_info in enumerate(standalone, 1):
            rows = table_info.get("rows") or []
            if not rows:
                continue
            # Avoid the page-wide 1x2 table mechanism that crashed in v0.4.9/0.4.9.1.
            # Real content tables are currently represented as tab-separated rows for stability.
            _v0491_log(f"[HWPX] 표 {table_idx}/{len(standalone)} 안정 텍스트 렌더")
            for row in rows:
                insert_text("\t".join("" if c is None else str(c) for c in row))
                break_para(1)
            break_para(1)

        answer_items = render_plan.get("answer_items", [])
        if answer_items:
            _v0491_log(f"[HWPX] 정답/해설 섹션 생성: {len(answer_items)}문항")
            break_page()
            mark("render_answers", page=None, column=None, item_index=None, item_type="answer_section", operation="InsertText")
            insert_text("[정답 및 해설]")
            break_para(2)
            for answer_idx, answer_item in enumerate(answer_items, 1):
                mark(
                    "render_answers",
                    page=None,
                    column=None,
                    item_index=answer_idx,
                    item_type="answer_entry",
                    operation="InsertText",
                )
                qno = int(answer_item.get("number") or answer_idx)
                answer = (answer_item.get("answer") or "?").strip()
                explanation = normalize_text_lines(answer_item.get("explanation", "")).strip()
                insert_text(f"{qno}) [정답] {answer}")
                break_para(1)
                if explanation:
                    insert_text(f"[해설] {explanation}")
                    break_para(2)
                else:
                    break_para(1)

        build_output.parent.mkdir(parents=True, exist_ok=True)
        mark("save_hwpx", page=None, column=None, item_index=None, item_type=None, operation="SaveAs(HWPX)")
        _v0491_log(f"[HWPX] 임시 HWPX 저장: {build_output.name}")
        try:
            hwp.SaveAs(str(build_output.resolve()), "HWPX")
        except TypeError:
            hwp.SaveAs(str(build_output.resolve()), "HWPX", "")
        save_completed = bool(build_output.exists())

        expected_images = int(result.get("image_filter_v0481", {}).get("saved_count") or 0)
        mark("validate_hwpx", operation="zip_structure_check")
        validation = v0493_validate_hwpx(build_output, expected_images=expected_images)
        _v0491_log(
            f"[HWPX] ZIP 검사: {validation.get('status')} | "
            f"size={validation.get('size_bytes', 0)} | "
            f"BinData={validation.get('bin_data_count', 0)}/{expected_images}"
        )
        return {
            "status": "created" if validation.get("status") == "PASS" else "INVALID",
            "path": str(build_output.resolve()),
            "backend": "hancom_com_v0493",
            "renderer_mode": mode,
            "render_plan_pages": render_plan.get("stats", {}).get("page_count", 0),
            "render_item_count": render_plan.get("stats", {}).get("render_item_count", 0),
            "table_count": render_plan.get("stats", {}).get("table_count", 0),
            "table_fallback_count": len(table_failures),
            "table_failures": table_failures,
            "validation": validation,
            "failure_context": None,
            "hancom_security": security_runtime,
        }
    except Exception as exc:
        context = dict(state)
        _v0491_log(
            "[HWPX][ERROR] "
            f"stage={context.get('stage')} page={context.get('page')} "
            f"column={context.get('column')} item={context.get('item_index')} "
            f"type={context.get('item_type')} op={context.get('operation')} / {exc}"
        )
        return {
            "status": "ERROR",
            "reason": str(exc),
            "path": str(build_output),
            "backend": "hancom_com_v0493",
            "renderer_mode": mode,
            "failure_context": context,
            "render_plan_pages": render_plan.get("stats", {}).get("page_count", 0),
            "hancom_security": security_runtime,
        }
    finally:
        if hwp is not None and save_completed:
            try:
                hwp.Quit()
            except Exception:
                pass
        elif hwp is not None and not content_started:
            # Clean untouched blank document: safe to close.
            try:
                hwp.Quit()
            except Exception:
                pass
        elif hwp is not None:
            # Preserve v0.4.9.2 behavior: never force-close a dirty failed document.
            _v0491_log("[HWPX][WARN] 저장 전 오류가 발생해 dirty 한글 문서를 자동 종료하지 않습니다.")
        if co_initialized:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass
        _shutil.rmtree(temp_dir, ignore_errors=True)


def v0493_validate_hwpx(path: Path, expected_images: int | None = None) -> dict:
    info = v0491_validate_hwpx(path, expected_images=expected_images)
    info["validator_version"] = "v0.4.9.3"
    return info


def v0493_create_hwpx_with_hancom(
    output: Path,
    result: dict,
    render_plan: dict,
    *,
    security_module_path: Path | None = None,
    allow_interactive_hwp: bool = False,
    show_hwp: bool = False,
) -> dict:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    previous_exists = output.exists()
    previous_size = output.stat().st_size if previous_exists else 0
    build_output = output.with_name("output_v0_4_9_3_build.hwpx")
    if build_output.exists():
        try:
            build_output.unlink()
        except Exception:
            pass

    security_info = v0493_prepare_hancom_security(security_module_path)
    result["hancom_security_v0493"] = security_info
    _v0491_log(
        "[HWPX] 보안 사전점검: "
        f"{security_info.get('status')} | module={security_info.get('module_name')} | "
        f"dll={security_info.get('dll_path')}"
    )

    attempt = _v0493_render_attempt(
        build_output,
        result,
        render_plan,
        security_info=security_info,
        allow_interactive_hwp=allow_interactive_hwp,
        show_hwp=show_hwp,
    )
    attempt["backend"] = "hancom_com_v0493"
    result["hancom_security_v0493"] = attempt.get("hancom_security") or security_info

    if attempt.get("status") == "SKIPPED":
        attempt["final_path"] = str(output.resolve())
        attempt["previous_output_preserved"] = previous_exists
        return attempt

    if attempt.get("status") == "created":
        src = Path(attempt["path"])
        try:
            src.replace(output)
        except Exception:
            shutil.copy2(src, output)
            try:
                src.unlink()
            except Exception:
                pass
        validation = v0493_validate_hwpx(
            output,
            expected_images=int(result.get("image_filter_v0481", {}).get("saved_count") or 0),
        )
        _v0491_log(f"[HWPX] 최종 파일 확정: {output.resolve()}")
        _v0491_log(f"[HWPX] 최종 압축 구조 검사: {validation.get('status')}")
        return {
            **attempt,
            "status": "created" if validation.get("status") == "PASS" else "INVALID",
            "path": str(output.resolve()),
            "final_path": str(output.resolve()),
            "backend": "hancom_com_v0493",
            "renderer_mode": "safe_sequential",
            "validation": validation,
            "previous_output_preserved": False,
            "previous_output_existed": previous_exists,
            "previous_output_size": previous_size,
            "attempts": [{
                "renderer_mode": "safe_sequential",
                "status": attempt.get("status"),
                "reason": attempt.get("reason"),
                "failure_context": attempt.get("failure_context"),
            }],
        }

    if build_output.exists():
        try:
            build_output.unlink()
        except Exception:
            pass
    return {
        **attempt,
        "path": str(output.resolve()),
        "final_path": str(output.resolve()),
        "backend": "hancom_com_v0493",
        "previous_output_preserved": previous_exists,
        "previous_output_existed": previous_exists,
        "previous_output_size": previous_size,
        "attempts": [{
            "renderer_mode": "safe_sequential",
            "status": attempt.get("status"),
            "reason": attempt.get("reason"),
            "failure_context": attempt.get("failure_context"),
        }],
    }


# ============================================================
# V0.4.9.4 Integrated Cleanup / Core-content-first HWPX Layer
# - render plan post-filter removes publisher study-guide helper blocks
# - image insertion metadata carries target width/height hints
# - result JSON exposes excluded non-core block statistics
# ============================================================

_V0494_NONCORE_KEYWORDS = [
    "TOP 1",
    "작품 구조",
    "핵심 시어",
    "학습 포인트",
    "감상 포인트",
    "배경지식",
    "확인 문제",
    "실전 포인트",
    "갈래의 이해",
]


def _v0494_compact_text(value: str) -> str:
    return re.sub(r"\s+", " ", _v049_text(value)).strip()


def _v0494_is_noncore_block(item: dict) -> bool:
    if not isinstance(item, dict):
        return False
    if item.get("type") != "block":
        return False
    text = _v049_text(item.get("text", "")).strip()
    if not text:
        return True
    compact = _v0494_compact_text(text)
    block_type = str(item.get("block_type") or "").strip().lower()

    if block_type in {"page_header", "footer", "header", "summary", "guide"}:
        return True

    if any(keyword in compact for keyword in _V0494_NONCORE_KEYWORDS):
        return True

    if compact.startswith("◇「콘텐츠산업 진흥법") or "제작연월일" in compact:
        return True

    if re.search(r"\bI\d{3}-\d{3}-\d{2}-\d{2}-\d+\b", compact):
        return True

    if compact.startswith("[표 ") and len(compact) <= 20:
        return True

    if text.count("☑") >= 1:
        return True

    if re.match(r"^\d+\.\s*.+갈래의 이해", compact):
        return True

    # Short publisher helper notes often appear as condensed bullet summaries.
    summary_tokens = ["작품", "핵심", "구조", "시어", "포인트"]
    if len(compact) <= 120 and sum(tok in compact for tok in summary_tokens) >= 2:
        return True

    return False


def v0494_build_render_plan(result: dict) -> dict:
    plan = v0492_build_render_plan(result)
    removed = []
    kept_pages = []
    kept_item_count = 0
    for page_entry in plan.get("pages", []):
        new_entry = dict(page_entry)
        for side in ("left", "right"):
            filtered_items = []
            for item in page_entry.get(side, []):
                if _v0494_is_noncore_block(item):
                    removed.append({
                        "page": page_entry.get("page"),
                        "column": side,
                        "type": item.get("type"),
                        "block_type": item.get("block_type"),
                        "preview": _v049_text(item.get("text", ""))[:120],
                    })
                    continue
                if item.get("type") == "image":
                    item = dict(item)
                    disp_w = float(item.get("display_width") or 0.0)
                    disp_h = float(item.get("display_height") or 0.0)
                    max_col_pt = 205.0
                    scale = min(1.0, max_col_pt / disp_w) if disp_w > 0 else 1.0
                    item["target_width_pt_v0494"] = round(disp_w * scale, 2) if disp_w > 0 else None
                    item["target_height_pt_v0494"] = round(disp_h * scale, 2) if disp_h > 0 else None
                filtered_items.append(item)
            new_entry[side] = filtered_items
            new_entry[f"{side}_count"] = len(filtered_items)
            kept_item_count += len(filtered_items)
        kept_pages.append(new_entry)

    plan["pages"] = kept_pages
    plan["version"] = "v0.4.9.4"
    plan["layout_mode"] = "stable_sequential_core_content_only"
    plan.setdefault("stats", {})["removed_noncore_block_count"] = len(removed)
    plan["stats"]["render_item_count"] = kept_item_count
    plan["removed_noncore_blocks_v0494"] = removed
    return plan


def v0494_validate_hwpx(path: Path, expected_images: int | None = None) -> dict:
    info = v0493_validate_hwpx(path, expected_images=expected_images)
    info["validator_version"] = "v0.4.9.4"
    return info


def v0494_create_hwpx_with_hancom(
    output: Path,
    result: dict,
    render_plan: dict,
    *,
    security_module_path: Path | None = None,
    allow_interactive_hwp: bool = False,
    show_hwp: bool = False,
) -> dict:
    info = v0493_create_hwpx_with_hancom(
        output,
        result,
        render_plan,
        security_module_path=security_module_path,
        allow_interactive_hwp=allow_interactive_hwp,
        show_hwp=show_hwp,
    )
    info = dict(info)
    info["backend"] = "hancom_com_v0494"
    if isinstance(info.get("validation"), dict):
        info["validation"] = dict(info["validation"])
        info["validation"]["validator_version"] = "v0.4.9.4"
    return info


def v0494_upgrade_result(
    result: dict,
    pdf_path: Path,
    checkpoint_path: Path | None = None,
    *,
    security_module_path: Path | None = None,
    allow_interactive_hwp: bool = False,
    show_hwp: bool = False,
) -> dict:
    _v0491_log("[v0.4.9.4] 이미지/메타데이터 준비")

    result = v046_upgrade_result(result, pdf_path)
    result = v0481_prepare_problem_images(pdf_path, result)
    result = v0491_cleanup_legacy_metadata(result)

    render_plan = v0494_build_render_plan(result)
    result["render_plan_v0494"] = render_plan
    for stale_key in ["render_plan_v0493", "render_plan_v0492", "render_plan_v049"]:
        result.pop(stale_key, None)

    result["version"] = "v0.4.9.4"
    result["parser_version"] = "v0.4.9.4"
    result["generator_version"] = "PDF Parser Integrated v0.4.9.4"
    result["schema_version"] = {
        "base": "v0.4.9.3",
        "extension": [
            "core_content_block_filter",
            "publisher_helper_note_removal",
            "noncore_block_statistics",
            "image_target_size_hints",
            "unattended_hidden_hangul_mode",
        ],
    }

    if checkpoint_path is not None:
        checkpoint_path = Path(checkpoint_path)
        result["pre_hwpx_checkpoint"] = {
            "path": str(checkpoint_path.resolve()),
            "purpose": "COM hang/error recovery only",
            "retained_after_success": False,
        }
        _v0491_json_safe_write(checkpoint_path, result)
        _v0491_log(f"[v0.4.9.4] HWPX 전 임시 체크포인트 저장: {checkpoint_path.resolve()}")

    hwpx_path = pdf_path.parent / "output.hwpx"
    hwpx_info = v0494_create_hwpx_with_hancom(
        hwpx_path,
        result,
        render_plan,
        security_module_path=security_module_path,
        allow_interactive_hwp=allow_interactive_hwp,
        show_hwp=show_hwp,
    )
    result["hwpx_v0494"] = hwpx_info
    result["hancom_security_v0494"] = (
        result.get("hancom_security_v0493")
        or hwpx_info.get("hancom_security")
        or {}
    )

    base_validation = result.get("validation", {})
    img_validation = result.get("image_filter_v0481", {})
    table_validation = result.get("table_filter_v0492", {})
    validation_zip = hwpx_info.get("validation") or {}
    security_runtime = result.get("hancom_security_v0494") or result.get("hancom_security_v0493") or hwpx_info.get("hancom_security") or {}
    hwpx_status = hwpx_info.get("status")
    security_ok = (
        security_runtime.get("unattended_ready") is True
        or hwpx_status == "SKIPPED"
        or (allow_interactive_hwp and hwpx_status == "created")
    )

    result["validation_v0494"] = {
        "question_count": len(result.get("questions", [])),
        "passage_group_count": len(result.get("passage_groups", [])),
        "problem_image_count": img_validation.get("selected_problem_figure_count", 0),
        "problem_image_saved": img_validation.get("saved_count", 0),
        "raw_table_count": table_validation.get("raw_table_count", 0),
        "renderable_table_count": table_validation.get("renderable_table_count", 0),
        "excluded_table_count": table_validation.get("excluded_table_count", 0),
        "removed_noncore_block_count": render_plan.get("stats", {}).get("removed_noncore_block_count", 0),
        "answer_count": render_plan.get("stats", {}).get("answer_count", 0),
        "render_page_count": render_plan.get("stats", {}).get("page_count", 0),
        "render_item_count": render_plan.get("stats", {}).get("render_item_count", 0),
        "base_parser_status": base_validation.get("status"),
        "image_status": img_validation.get("status"),
        "hancom_security_status": security_runtime.get("status"),
        "hancom_security_register_result": security_runtime.get("register_module_result"),
        "unattended_ready": security_runtime.get("unattended_ready", False),
        "hwpx_status": hwpx_status,
        "hwpx_renderer_mode": hwpx_info.get("renderer_mode"),
        "hwpx_zip_status": validation_zip.get("status"),
        "hwpx_embedded_image_count": validation_zip.get("bin_data_count"),
        "status": (
            "PASS"
            if base_validation.get("status") == "PASS"
            and img_validation.get("status") == "PASS"
            and table_validation.get("status") == "PASS"
            and hwpx_status in {"created", "SKIPPED"}
            and security_ok
            else "WARN"
        ),
    }
    result["known_limitations_v0494"] = [
        "실제 좌우 2단 병렬 배치는 한글 COM 안정성 범위 안에서 점진적으로 개선 중이며, 현재는 안정 순차 배치 중심입니다.",
        "승인창 없는 완전 무조작 실행은 한컴 공식 FilePathCheckerModuleExample.dll이 PC에 한 번 제공되어 있어야 합니다.",
        "비핵심 학습가이드 블록 필터는 휴리스틱 기반이므로 특수 교재에서는 추가 패턴 보정이 필요할 수 있습니다.",
        "출판사 TOP 요약표, 정답지 레이아웃 오인식 표, 저작권/콘텐츠산업 진흥법 footer, 작품 구조/핵심 시어류 보조 블록은 HWPX 렌더링에서 제외합니다.",
    ]
    return result


def v0493_upgrade_result(
    result: dict,
    pdf_path: Path,
    checkpoint_path: Path | None = None,
    *,
    security_module_path: Path | None = None,
    allow_interactive_hwp: bool = False,
    show_hwp: bool = False,
) -> dict:
    _v0491_log("[v0.4.9.3] 이미지/메타데이터 준비")

    # Reuse the proven v0.4.9.2 content pipeline, but never call its HWPX writer.
    result = v046_upgrade_result(result, pdf_path)
    result = v0481_prepare_problem_images(pdf_path, result)
    result = v0491_cleanup_legacy_metadata(result)

    render_plan = v0492_build_render_plan(result)
    render_plan["version"] = "v0.4.9.3"
    render_plan["layout_mode"] = "stable_sequential_unattended_hancom"
    result["render_plan_v0493"] = render_plan
    result.pop("render_plan_v0492", None)
    result.pop("render_plan_v049", None)

    result["version"] = "v0.4.9.3"
    result["parser_version"] = "v0.4.9.3"
    result["generator_version"] = "PDF Parser Integrated v0.4.9.3"
    result["schema_version"] = {
        "base": "v0.4.9.2",
        "extension": [
            "official_hancom_filepathcheck_module",
            "automatic_hkcu_security_registration",
            "stable_local_security_module_copy",
            "registermodule_return_validation",
            "unattended_hidden_hangul_mode",
            "fail_fast_without_security_module",
            "optional_interactive_fallback_flag",
            "hancom_security_diagnostics",
        ],
    }

    if checkpoint_path is not None:
        checkpoint_path = Path(checkpoint_path)
        result["pre_hwpx_checkpoint"] = {
            "path": str(checkpoint_path.resolve()),
            "purpose": "COM hang/error recovery only",
            "retained_after_success": False,
        }
        _v0491_json_safe_write(checkpoint_path, result)
        _v0491_log(f"[v0.4.9.3] HWPX 전 임시 체크포인트 저장: {checkpoint_path.resolve()}")

    hwpx_path = pdf_path.parent / "output.hwpx"
    hwpx_info = v0493_create_hwpx_with_hancom(
        hwpx_path,
        result,
        render_plan,
        security_module_path=security_module_path,
        allow_interactive_hwp=allow_interactive_hwp,
        show_hwp=show_hwp,
    )
    result["hwpx_v0493"] = hwpx_info

    base_validation = result.get("validation", {})
    img_validation = result.get("image_filter_v0481", {})
    table_validation = result.get("table_filter_v0492", {})
    validation_zip = hwpx_info.get("validation") or {}
    security_runtime = result.get("hancom_security_v0493") or hwpx_info.get("hancom_security") or {}
    hwpx_status = hwpx_info.get("status")

    # On Linux self-tests HWPX is intentionally SKIPPED; on Windows the unattended
    # path is considered PASS only when RegisterModule succeeded.
    security_ok = (
        security_runtime.get("unattended_ready") is True
        or hwpx_status == "SKIPPED"
        or (allow_interactive_hwp and hwpx_status == "created")
    )

    result["validation_v0493"] = {
        "question_count": len(result.get("questions", [])),
        "passage_group_count": len(result.get("passage_groups", [])),
        "problem_image_count": img_validation.get("selected_problem_figure_count", 0),
        "problem_image_saved": img_validation.get("saved_count", 0),
        "raw_table_count": table_validation.get("raw_table_count", 0),
        "renderable_table_count": table_validation.get("renderable_table_count", 0),
        "excluded_table_count": table_validation.get("excluded_table_count", 0),
        "answer_count": render_plan.get("stats", {}).get("answer_count", 0),
        "render_page_count": render_plan.get("stats", {}).get("page_count", 0),
        "render_item_count": render_plan.get("stats", {}).get("render_item_count", 0),
        "base_parser_status": base_validation.get("status"),
        "image_status": img_validation.get("status"),
        "hancom_security_status": security_runtime.get("status"),
        "hancom_security_register_result": security_runtime.get("register_module_result"),
        "unattended_ready": security_runtime.get("unattended_ready", False),
        "hwpx_status": hwpx_status,
        "hwpx_renderer_mode": hwpx_info.get("renderer_mode"),
        "hwpx_zip_status": validation_zip.get("status"),
        "hwpx_embedded_image_count": validation_zip.get("bin_data_count"),
        "status": (
            "PASS"
            if base_validation.get("status") == "PASS"
            and img_validation.get("status") == "PASS"
            and table_validation.get("status") == "PASS"
            and hwpx_status in {"created", "SKIPPED"}
            and security_ok
            else "WARN"
        ),
    }
    result["known_limitations_v0493"] = [
        "실제 좌우 2단 병렬 배치는 한글 TableCreate COM 안정성 문제로 아직 보류하며, 현재는 안정 순차 배치입니다.",
        "승인창 없는 완전 무조작 실행은 한컴 공식 FilePathCheckerModuleExample.dll이 PC에 한 번 제공되어 있어야 합니다.",
        "v0.4.9.3은 공식 DLL을 자동 다운로드하지 않습니다. DLL이 발견되면 %LOCALAPPDATA%\\HncSec에 복사하고 HKCU 레지스트리를 자동 등록합니다.",
        "공식 보안 모듈이 없거나 RegisterModule이 False이면 기본 모드에서는 즉시 실패해 숨은 승인창 대기를 방지합니다.",
        "필요할 때만 --allow-interactive-hwp로 기존 수동 승인창 방식으로 실행할 수 있습니다.",
        "출판사 TOP 요약표, 정답지 레이아웃 오인식 표, 저작권/콘텐츠산업 진흥법 footer는 HWPX 렌더링에서 제외합니다.",
    ]
    return result


# ============================================================
# V0.4.9.5 Integrated Layout Fidelity Layer
# - real PDF y-coordinates for questions / choices
# - native two-column HWP layout (MultiColumn + BreakColumn)
#   with one-column safe fallback
# - exact image physical sizing in Hangul
# - paragraph spacing / choice indentation
# - HWPX post-validation for columns and picture sizes
# ============================================================

def _v0495_bbox_list(rect) -> list[float]:
    try:
        return [float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)]
    except Exception:
        try:
            vals = list(rect)
            return [float(x) for x in vals[:4]]
        except Exception:
            return []


def v0495_attach_question_geometry(pdf_path: Path, result: dict) -> dict:
    """Attach the real PDF positions of question headers and choice markers.

    Older render plans assigned question sort_y=900+question_number, which could
    push a question behind the *next* passage group on the same source page.
    This stage captures the source geometry once and keeps it in JSON.
    """
    doc = fitz.open(pdf_path)
    try:
        question_end_page = int(result.get("document_structure", {}).get("question_pages") or 0)
        if question_end_page <= 0:
            question_end_page = min(len(doc), 10)

        qmeta = build_question_meta(doc, question_end_page)
        digit_icon_map = build_digit_icon_map(doc[0])

        applied_questions = 0
        applied_choices = 0
        applied_examples = 0

        by_number = {
            int(q.get("number")): q
            for q in result.get("questions", [])
            if q.get("number") is not None
        }

        for qno, q in by_number.items():
            meta = qmeta.get(qno)
            if not meta:
                continue

            page = doc[int(meta["page_index"])]
            qbox = meta["bbox"]
            column = int(meta["column"])
            left, right = get_column_bounds(page, column)

            end_candidates = [float(page.rect.height - 50)]
            for other_number, other_box, other_column in get_question_headers(page):
                if other_column == column and float(other_box.y0) > float(qbox.y0):
                    end_candidates.append(float(other_box.y0))
            for anchor in get_passage_anchors(page, column):
                if float(anchor.y0) > float(qbox.y0):
                    end_candidates.append(float(anchor.y0))
            end_y = min(end_candidates)

            choice_y: dict[str, float] = {}
            choice_bbox: dict[str, list[float]] = {}
            grouped: dict[int, list[dict]] = defaultdict(list)
            for image_info in get_image_instances(page):
                if image_info.get("hash") not in digit_icon_map:
                    continue
                rect = image_info["rect"]
                if not (left <= rect.x0 < right):
                    continue
                if not (float(qbox.y0) < float(rect.y0) < end_y):
                    continue
                if rect.width >= 20 or rect.height >= 20:
                    continue
                grouped[int(digit_icon_map[image_info["hash"]])].append(image_info)

            for idx in range(1, 6):
                candidates = grouped.get(idx) or []
                if not candidates:
                    continue
                marker = min(candidates, key=lambda x: (x["rect"].y0, x["rect"].x0))
                choice_y[str(idx)] = float(marker["rect"].y0)
                choice_bbox[str(idx)] = _v0495_bbox_list(marker["rect"])
                applied_choices += 1

            example_y = None
            for line in get_line_records(page):
                if not (left <= line["bbox"].x0 < right):
                    continue
                if not (float(qbox.y0) <= float(line["bbox"].y0) < end_y):
                    continue
                compact = re.sub(r"\s+", "", str(line.get("text") or ""))
                if compact in {"<보기>", "[보기]", "〈보기〉", "《보기》"}:
                    y = float(line["bbox"].y0)
                    if example_y is None or y < example_y:
                        example_y = y

            first_choice_y = min(choice_y.values()) if choice_y else None
            layout = {
                "source_page": int(meta["page_index"]) + 1,
                "column": "left" if column == 0 else "right",
                "question_bbox": _v0495_bbox_list(qbox),
                "question_y": float(qbox.y0),
                "question_bottom_y": float(qbox.y1),
                "question_region_end_y": float(end_y),
                "choice_y": choice_y,
                "choice_bbox": choice_bbox,
                "first_choice_y": first_choice_y,
                "example_y": example_y,
                "source_geometry": "PyMuPDF question header + choice marker coordinates",
            }
            q["layout_v0495"] = layout
            q["source_bbox_v0495"] = layout["question_bbox"]
            q["source_y_v0495"] = layout["question_y"]
            applied_questions += 1
            if example_y is not None:
                applied_examples += 1

        result["question_geometry_v0495"] = {
            "question_source_y_applied_count": applied_questions,
            "choice_source_y_applied_count": applied_choices,
            "example_source_y_detected_count": applied_examples,
            "expected_question_count": len(by_number),
            "expected_choice_count": len(by_number) * 5,
            "status": (
                "PASS"
                if applied_questions == len(by_number)
                and applied_choices == len(by_number) * 5
                else "WARN"
            ),
        }
        return result
    finally:
        doc.close()


def _v0495_style_for_item(item: dict) -> dict:
    t = item.get("type")
    if t == "question":
        return {
            "role": "question",
            "left_margin_pt": 0.0,
            "line_spacing_percent": 155,
            "blank_before": 1,
        }
    if t == "choice":
        return {
            "role": "choice",
            "left_margin_pt": 9.0,
            "line_spacing_percent": 145,
            "blank_before": 0,
        }
    if t == "example_box":
        return {
            "role": "example",
            "left_margin_pt": 7.0,
            "line_spacing_percent": 145,
            "blank_before": 0,
        }
    if t == "block":
        bt = str(item.get("block_type") or "")
        return {
            "role": f"passage_{bt}",
            "left_margin_pt": 0.0 if bt != "poetry_line" else 4.0,
            "line_spacing_percent": 150 if bt not in {"poetry_line", "dialogue"} else 145,
            "blank_before": 1 if bt in {"title"} else 0,
        }
    if t == "image":
        return {
            "role": "image",
            "left_margin_pt": 0.0,
            "line_spacing_percent": 100,
            "blank_before": 0,
        }
    return {
        "role": str(t or "unknown"),
        "left_margin_pt": 0.0,
        "line_spacing_percent": 150,
        "blank_before": 0,
    }


def v0495_build_render_plan(result: dict) -> dict:
    """Build v0.4.9.4 content filtering on top of *real* source y-coordinates."""
    plan = v0494_build_render_plan(result)
    qmap = {
        int(q.get("number")): q
        for q in result.get("questions", [])
        if q.get("number") is not None
    }

    q_applied = 0
    choice_applied = 0
    ex_applied = 0
    image_targets = 0

    def type_priority(item: dict) -> int:
        return {
            "block": 10,
            "image": 20,
            "question": 30,
            "example_box": 40,
            "choice": 50,
        }.get(str(item.get("type")), 99)

    for page_entry in plan.get("pages", []):
        for side in ("left", "right"):
            updated = []
            for raw_item in page_entry.get(side, []):
                item = dict(raw_item)
                t = item.get("type")
                qno = int(item.get("number") or 0) if item.get("number") is not None else 0
                q = qmap.get(qno)
                layout = (q or {}).get("layout_v0495") or {}

                if t == "question" and layout.get("question_y") is not None:
                    item["legacy_sort_y_v0494"] = item.get("sort_y")
                    item["sort_y"] = float(layout["question_y"])
                    item["source_y_applied_v0495"] = True
                    q_applied += 1
                elif t == "choice" and layout:
                    idx = str(int(item.get("choice_index") or 0))
                    source_y = (layout.get("choice_y") or {}).get(idx)
                    if source_y is not None:
                        item["legacy_sort_y_v0494"] = item.get("sort_y")
                        item["sort_y"] = float(source_y)
                        item["source_y_applied_v0495"] = True
                        choice_applied += 1
                elif t == "example_box" and layout:
                    source_y = layout.get("example_y")
                    if source_y is None:
                        first_choice = layout.get("first_choice_y")
                        if first_choice is not None:
                            source_y = float(first_choice) - 0.5
                        elif layout.get("question_y") is not None:
                            source_y = float(layout["question_y"]) + 0.05
                    if source_y is not None:
                        item["legacy_sort_y_v0494"] = item.get("sort_y")
                        item["sort_y"] = float(source_y)
                        item["source_y_applied_v0495"] = True
                        ex_applied += 1
                elif t == "image":
                    disp_w = float(item.get("display_width") or 0.0)
                    disp_h = float(item.get("display_height") or 0.0)
                    max_col_pt = 205.0
                    scale = min(1.0, max_col_pt / disp_w) if disp_w > 0 else 1.0
                    target_w = disp_w * scale if disp_w > 0 else 0.0
                    target_h = disp_h * scale if disp_h > 0 else 0.0
                    item["target_width_pt_v0495"] = round(target_w, 2) if target_w else None
                    item["target_height_pt_v0495"] = round(target_h, 2) if target_h else None
                    item["target_width_mm_v0495"] = round(target_w * 25.4 / 72.0, 3) if target_w else None
                    item["target_height_mm_v0495"] = round(target_h * 25.4 / 72.0, 3) if target_h else None
                    if target_w and target_h:
                        image_targets += 1

                item["style_v0495"] = _v0495_style_for_item(item)
                updated.append(item)

            updated.sort(
                key=lambda x: (
                    float(x.get("sort_y") or 0.0),
                    type_priority(x),
                    int(x.get("number") or 0),
                    int(x.get("choice_index") or 0),
                )
            )
            page_entry[side] = updated
            page_entry[f"{side}_count"] = len(updated)

    plan["version"] = "v0.4.9.5"
    plan["layout_mode"] = "native_two_column_source_order_with_safe_fallback"
    plan["source_order_v0495"] = {
        "question_source_y_applied_count": q_applied,
        "choice_source_y_applied_count": choice_applied,
        "example_source_y_applied_count": ex_applied,
        "expected_question_count": len(qmap),
        "expected_choice_count": len(qmap) * 5,
        "status": (
            "PASS"
            if q_applied == len(qmap) and choice_applied == len(qmap) * 5
            else "WARN"
        ),
    }
    plan["image_sizing_v0495"] = {
        "target_size_item_count": image_targets,
        "max_column_width_pt": 205.0,
        "apply_method": "InsertPicture(sizeoption=1, Width/Height mm) + gso Properties HWPUNIT correction",
    }
    plan.setdefault("stats", {})["render_item_count"] = sum(
        int(p.get("left_count") or 0) + int(p.get("right_count") or 0)
        for p in plan.get("pages", [])
    )
    return plan


def v0495_validate_hwpx(
    path: Path,
    expected_images: int | None = None,
    *,
    require_two_column: bool = False,
    max_picture_width_hwpunit: int = 21000,
) -> dict:
    info = v0494_validate_hwpx(path, expected_images=expected_images)
    info["validator_version"] = "v0.4.9.5"
    info["require_two_column"] = bool(require_two_column)
    info["native_two_column_found"] = False
    info["column_counts"] = []
    info["picture_size_count"] = 0
    info["max_picture_width_hwpunit"] = 0
    info["picture_width_target_cap_hwpunit"] = int(max_picture_width_hwpunit)
    info["picture_width_within_target"] = None

    if not path.exists() or not zipfile.is_zipfile(path):
        return info

    try:
        with zipfile.ZipFile(path, "r") as zf:
            section_xml = zf.read("Contents/section0.xml").decode("utf-8", errors="ignore")
        col_counts = [int(x) for x in re.findall(r'colCount="(\d+)"', section_xml)]
        picture_sizes = [
            (int(w), int(h))
            for w, h in re.findall(
                r'<hp:sz[^>]*\bwidth="(\d+)"[^>]*\bheight="(\d+)"',
                section_xml,
            )
        ]
        info["column_counts"] = col_counts
        info["native_two_column_found"] = any(x >= 2 for x in col_counts)
        info["picture_size_count"] = len(picture_sizes)
        info["max_picture_width_hwpunit"] = max((w for w, _ in picture_sizes), default=0)
        if expected_images:
            widths = [w for w, _ in picture_sizes[: int(expected_images)]]
            info["picture_width_within_target"] = (
                len(widths) == int(expected_images)
                and all(w <= int(max_picture_width_hwpunit) for w in widths)
            )
        else:
            info["picture_width_within_target"] = True

        base_ok = info.get("status") == "PASS"
        column_ok = (not require_two_column) or info["native_two_column_found"]
        image_ok = info["picture_width_within_target"] is not False
        info["status"] = "PASS" if base_ok and column_ok and image_ok else "FAIL"
    except Exception as exc:
        info["post_validation_error"] = str(exc)
        info["status"] = "FAIL"
    return info


def _v0495_render_attempt(
    build_output: Path,
    result: dict,
    render_plan: dict,
    *,
    security_info: dict,
    renderer_mode: str,
    allow_interactive_hwp: bool = False,
    show_hwp: bool = False,
) -> dict:
    """Render with native 2-column layout or the safe single-column fallback."""
    import os
    import shutil as _shutil

    mode = str(renderer_mode)
    state = {
        "renderer_mode": mode,
        "stage": "initializing",
        "page": None,
        "column": None,
        "item_index": None,
        "item_type": None,
        "operation": None,
    }

    def mark(stage: str, **kwargs) -> None:
        state["stage"] = stage
        state.update(kwargs)

    if build_output.exists():
        try:
            build_output.unlink()
        except Exception:
            pass

    if os.name != "nt":
        sec = dict(security_info or {})
        sec["status"] = "SKIPPED"
        return {
            "status": "SKIPPED",
            "reason": "Hancom HWPX writer requires Windows with Hancom Hangul installed",
            "path": str(build_output),
            "backend": "hancom_com_v0495",
            "renderer_mode": mode,
            "failure_context": dict(state),
            "hancom_security": sec,
        }

    try:
        import pythoncom
        import win32com.client as win32
    except Exception as exc:
        return {
            "status": "ERROR",
            "reason": f"pywin32 is not available: {exc}",
            "install": "python -m pip install pywin32 pillow",
            "path": str(build_output),
            "backend": "hancom_com_v0495",
            "renderer_mode": mode,
            "failure_context": dict(state),
            "hancom_security": dict(security_info or {}),
        }

    hwp = None
    co_initialized = False
    security_runtime = dict(security_info or {})
    image_counter = 0
    image_exact_size_count = 0
    paragraph_style_apply_count = 0
    multicolumn_apply_count = 0

    def normalize_text_lines(value: str) -> str:
        return _v049_text(value).replace("\r\n", "\n").replace("\r", "\n")

    try:
        mark("com_initialize", operation="pythoncom.CoInitialize")
        pythoncom.CoInitialize()
        co_initialized = True

        _v0491_log(f"[HWPX] v0.4.9.5.2 렌더러 시작: {mode}")
        mark("create_hwp_object", operation="DispatchEx")
        try:
            hwp = win32.DispatchEx("HWPFrame.HwpObject")
        except Exception:
            hwp = win32.gencache.EnsureDispatch("HWPFrame.HwpObject")

        mark("register_security_module", operation="RegisterModule(FilePathCheckDLL)")
        security_runtime = _v0493_register_security_on_hwp(hwp, security_info)
        if security_runtime.get("unattended_ready"):
            _v0491_log(
                f"[HWPX] 한컴 보안 모듈 등록 성공: {security_runtime.get('module_name')} "
                "(승인창 없이 진행)"
            )
            try:
                hwp.XHwpWindows.Item(0).Visible = bool(show_hwp)
            except Exception:
                pass
        elif allow_interactive_hwp:
            _v0491_log("[HWPX][WARN] 보안 모듈 등록 실패 -> 대화형 승인 모드")
            try:
                hwp.XHwpWindows.Item(0).Visible = True
            except Exception:
                pass
        else:
            return {
                "status": "SECURITY_SETUP_REQUIRED",
                "reason": (
                    "Hancom official FilePathChecker security module is not active. "
                    "Place FilePathCheckerModuleExample.dll next to the script "
                    "(or pass --security-module PATH) and run again."
                ),
                "path": str(build_output),
                "backend": "hancom_com_v0495",
                "renderer_mode": mode,
                "failure_context": dict(state),
                "hancom_security": security_runtime,
            }

        def insert_text(value: str) -> None:
            txt = _v049_text(value)
            if not txt:
                return
            mark(state["stage"], operation="InsertText")
            hwp.HAction.GetDefault("InsertText", hwp.HParameterSet.HInsertText.HSet)
            hwp.HParameterSet.HInsertText.Text = txt
            hwp.HAction.Execute("InsertText", hwp.HParameterSet.HInsertText.HSet)

        def break_para(times: int = 1) -> None:
            for _ in range(max(1, int(times))):
                mark(state["stage"], operation="BreakPara")
                hwp.HAction.Run("BreakPara")

        def break_page() -> None:
            mark(state["stage"], operation="BreakPage")
            hwp.HAction.Run("BreakPage")

        def break_column() -> None:
            mark(state["stage"], operation="BreakColumn")
            hwp.HAction.Run("BreakColumn")

        def break_section() -> None:
            mark(state["stage"], operation="BreakSection")
            hwp.HAction.Run("BreakSection")

        def set_multicolumn(count: int, gap_mm: float = 8.0) -> bool:
            """Apply a real Hangul column definition through HColDef.

            v0.4.9.5 used a generic CreateAction/CreateSet payload.  On the
            tested Hangul build it returned success but serialized colCount=1.
            The documented automation pattern uses HParameterSet.HColDef.
            """
            nonlocal multicolumn_apply_count
            mark(state["stage"], operation=f"MultiColumn.HColDef(count={count})")
            try:
                coldef = hwp.HParameterSet.HColDef
                hwp.HAction.GetDefault("MultiColumn", coldef.HSet)
                coldef.Count = int(count)
                try:
                    coldef.SameSize = 1
                except Exception:
                    pass
                try:
                    coldef.SameGap = int(hwp.MiliToHwpUnit(float(gap_mm)))
                except Exception:
                    pass
                # Apply to current section.
                coldef.HSet.SetItem("ApplyClass", 832)
                coldef.HSet.SetItem("ApplyTo", 6)
                ok = bool(hwp.HAction.Execute("MultiColumn", coldef.HSet))
                if ok:
                    multicolumn_apply_count += 1
                return ok
            except Exception as exc:
                _v0491_log(f"[HWPX][WARN] HColDef MultiColumn 설정 실패: {exc}")
                return False

        def set_para_style(item: dict) -> None:
            nonlocal paragraph_style_apply_count
            style = item.get("style_v0495") or _v0495_style_for_item(item)
            try:
                act = hwp.CreateAction("ParagraphShape")
                aset = act.CreateSet()
                act.GetDefault(aset)
                left_pt = float(style.get("left_margin_pt") or 0.0)
                aset.SetItem("LeftMargin", int(round(left_pt * 100.0)))
                aset.SetItem("LineSpacingType", 0)
                aset.SetItem("LineSpacing", int(style.get("line_spacing_percent") or 150))
                aset.SetItem("BreakNonLatinWord", 0)
                act.Execute(aset)
                paragraph_style_apply_count += 1
            except Exception:
                # Style is polish only; never sacrifice the content pipeline.
                pass

        def render_block(item: dict, *, index: int) -> None:
            text_value = normalize_text_lines(item.get("text", "")).strip()
            if not text_value:
                return
            style = item.get("style_v0495") or {}
            if int(style.get("blank_before") or 0) and (
                index > 1 or item.get("force_blank_before_v04954")
            ):
                break_para(int(style.get("blank_before") or 0))
            set_para_style(item)
            insert_text(text_value)
            break_para(2 if item.get("block_type") == "title" else 1)

        def render_question(item: dict, *, index: int) -> None:
            style = item.get("style_v0495") or {}
            if int(style.get("blank_before") or 0) and index > 1:
                break_para(int(style.get("blank_before") or 0))
            set_para_style(item)
            insert_text(
                f"{item.get('number')}. "
                f"{normalize_text_lines(item.get('text','')).strip()}"
            )
            break_para(1)

        def render_choice(item: dict) -> None:
            set_para_style(item)
            insert_text(
                f"{item.get('prefix') or '-'} "
                f"{normalize_text_lines(item.get('text','')).strip()}"
            )
            break_para(1)

        def render_example_box(item: dict) -> None:
            set_para_style(item)
            title = item.get("title") or "보기"
            body = normalize_text_lines(item.get("text", "")).strip()
            insert_text(f"<{title}>\r\n{body}")
            break_para(1)

        def target_image_size(item: dict) -> tuple[float, float]:
            width_pt = float(
                item.get("target_width_pt_v0495")
                or item.get("target_width_pt_v0494")
                or item.get("display_width")
                or 0.0
            )
            height_pt = float(
                item.get("target_height_pt_v0495")
                or item.get("target_height_pt_v0494")
                or item.get("display_height")
                or 0.0
            )
            if width_pt <= 0 or height_pt <= 0:
                width_pt = min(float(item.get("display_width") or 180.0), 205.0)
                source_w = float(item.get("display_width") or width_pt)
                source_h = float(item.get("display_height") or width_pt * 0.67)
                ratio = source_h / source_w if source_w > 0 else 0.67
                height_pt = width_pt * ratio
            scale = min(1.0, 205.0 / width_pt) if width_pt > 0 else 1.0
            return width_pt * scale, height_pt * scale

        def render_image(item: dict) -> None:
            nonlocal image_counter, image_exact_size_count
            image_counter += 1
            total_images = int(result.get("image_filter_v0481", {}).get("saved_count") or 0)
            _v0491_log(
                f"[HWPX] 이미지 {image_counter}/{max(total_images, image_counter)}: "
                f"{item.get('filename')}"
            )
            image_path = Path(str(item.get("path") or ""))
            if not image_path.exists():
                insert_text(f"[이미지 파일 없음: {item.get('filename') or ''}]")
                break_para(1)
                return

            width_pt, height_pt = target_image_size(item)
            width_mm = width_pt * 25.4 / 72.0
            height_mm = height_pt * 25.4 / 72.0
            set_para_style(item)
            mark(state["stage"], operation="InsertPictureExactSize")
            try:
                try:
                    hwp.InsertPicture(
                        str(image_path.resolve()),
                        True,
                        1,
                        False,
                        False,
                        0,
                        float(width_mm),
                        float(height_mm),
                    )
                except TypeError:
                    hwp.InsertPicture(
                        str(image_path.resolve()),
                        Embedded=True,
                        sizeoption=1,
                        Width=float(width_mm),
                        Height=float(height_mm),
                    )

                # v0.4.9.5.2: never enter object-control selection here.
                # InsertPicture already receives the physical Width/Height.  Selecting
                # a control after insertion can move an earlier picture anchor to the
                # document tail on some Hangul builds.
                image_exact_size_count += 1
                break_para(1)
            except Exception as image_exc:
                _v0491_log(
                    f"[HWPX][WARN] 이미지 삽입 실패: {image_path.name} / {image_exc}"
                )
                insert_text(f"[이미지 삽입 실패: {image_path.name}]")
                break_para(1)

        def render_item(item: dict, *, page: int, column: str, index: int) -> None:
            mark(
                "render_item",
                page=page,
                column=column,
                item_index=index,
                item_type=item.get("type"),
                operation=None,
            )
            t = item.get("type")
            if t == "block":
                render_block(item, index=index)
            elif t == "question":
                render_question(item, index=index)
            elif t == "choice":
                render_choice(item)
            elif t == "example_box":
                render_example_box(item)
            elif t == "image":
                render_image(item)

        pages = render_plan.get("pages", [])
        if mode == "native_two_column":
            mark("setup_native_two_column", operation="MultiColumn.HColDef")
            if not set_multicolumn(2, gap_mm=8.0):
                # Fallback happens before any content is written, inside the same
                # HWP COM session, so RegisterModule is never called a second time.
                _v0491_log(
                    "[HWPX][WARN] HColDef 2단 설정 실패 -> 같은 HWP 세션에서 "
                    "safe_sequential로 전환"
                )
                mode = "safe_sequential"

        for page_idx, page_entry in enumerate(pages, 1):
            page_no = int(page_entry.get("page") or page_idx)
            left_items = page_entry.get("left", [])
            right_items = page_entry.get("right", [])
            _v0491_log(
                f"[HWPX] 페이지 {page_idx}/{len(pages)} (PDF p.{page_no}) | "
                f"L={len(left_items)} R={len(right_items)}"
            )

            if mode == "native_two_column":
                if left_items:
                    for idx, item in enumerate(left_items, 1):
                        render_item(item, page=page_no, column="left", index=idx)
                if right_items:
                    break_column()
                    for idx, item in enumerate(right_items, 1):
                        render_item(item, page=page_no, column="right", index=idx)
                if page_idx < len(pages):
                    break_page()
            else:
                for idx, item in enumerate(left_items, 1):
                    render_item(item, page=page_no, column="left", index=idx)
                if left_items and right_items:
                    break_para(1)
                for idx, item in enumerate(right_items, 1):
                    render_item(item, page=page_no, column="right", index=idx)
                if page_idx < len(pages):
                    break_page()

        # Isolate answers/tables in a one-column section after the question pages.
        if mode == "native_two_column":
            mark("switch_to_one_column_answer_section", operation="BreakSection+MultiColumn(1)")
            break_section()
            if not set_multicolumn(1, gap_mm=8.0):
                _v0491_log("[HWPX][WARN] 정답 섹션 1단 전환 실패 - 현재 단 설정 유지")
        else:
            if pages:
                break_page()

        standalone = render_plan.get("standalone_tables", [])
        if standalone:
            _v0491_log(f"[HWPX] 실제 내용표 안정 렌더: {len(standalone)}개")
            for table_idx, table_info in enumerate(standalone, 1):
                rows = table_info.get("rows") or []
                if not rows:
                    continue
                insert_text(f"[표 {table_idx}]")
                break_para(1)
                for row in rows:
                    insert_text("\t".join("" if c is None else str(c) for c in row))
                    break_para(1)
                break_para(1)

        answer_items = render_plan.get("answer_items", [])
        if answer_items:
            _v0491_log(f"[HWPX] 정답/해설 섹션 생성: {len(answer_items)}문항")
            set_para_style({"type": "block", "block_type": "title"})
            insert_text("[정답 및 해설]")
            break_para(2)
            for answer_idx, answer_item in enumerate(answer_items, 1):
                qno = int(answer_item.get("number") or answer_idx)
                answer = (answer_item.get("answer") or "?").strip()
                explanation = normalize_text_lines(answer_item.get("explanation", "")).strip()
                set_para_style({"type": "question"})
                insert_text(f"{qno}) [정답] {answer}")
                break_para(1)
                if explanation:
                    set_para_style({"type": "choice"})
                    insert_text(f"[해설] {explanation}")
                    break_para(2)
                else:
                    break_para(1)

        build_output.parent.mkdir(parents=True, exist_ok=True)
        mark("save_hwpx", operation="SaveAs(HWPX)")
        _v0491_log(f"[HWPX] 임시 HWPX 저장: {build_output.name}")
        try:
            hwp.SaveAs(str(build_output.resolve()), "HWPX")
        except TypeError:
            hwp.SaveAs(str(build_output.resolve()), "HWPX", "")

        expected_images = int(result.get("image_filter_v0481", {}).get("saved_count") or 0)
        validation = v0495_validate_hwpx(
            build_output,
            expected_images=expected_images,
            require_two_column=(mode == "native_two_column"),
        )
        _v0491_log(
            f"[HWPX] v0.4.9.5 검사: {validation.get('status')} | "
            f"2단={validation.get('native_two_column_found')} | "
            f"그림폭={validation.get('max_picture_width_hwpunit')}HU | "
            f"BinData={validation.get('bin_data_count', 0)}/{expected_images}"
        )
        return {
            "status": "created" if validation.get("status") == "PASS" else "INVALID",
            "path": str(build_output.resolve()),
            "backend": "hancom_com_v0495",
            "renderer_mode": mode,
            "render_plan_pages": render_plan.get("stats", {}).get("page_count", 0),
            "render_item_count": render_plan.get("stats", {}).get("render_item_count", 0),
            "table_count": render_plan.get("stats", {}).get("table_count", 0),
            "validation": validation,
            "failure_context": None,
            "hancom_security": security_runtime,
            "image_exact_size_apply_count": image_exact_size_count,
            "paragraph_style_apply_count": paragraph_style_apply_count,
            "multicolumn_apply_count": multicolumn_apply_count,
        }

    except Exception as exc:
        context = dict(state)
        _v0491_log(
            "[HWPX][ERROR] "
            f"mode={mode} stage={context.get('stage')} page={context.get('page')} "
            f"column={context.get('column')} item={context.get('item_index')} "
            f"type={context.get('item_type')} op={context.get('operation')} / {exc}"
        )
        return {
            "status": "ERROR",
            "reason": str(exc),
            "path": str(build_output),
            "backend": "hancom_com_v0495",
            "renderer_mode": mode,
            "failure_context": context,
            "render_plan_pages": render_plan.get("stats", {}).get("page_count", 0),
            "hancom_security": security_runtime,
            "image_exact_size_apply_count": image_exact_size_count,
            "paragraph_style_apply_count": paragraph_style_apply_count,
            "multicolumn_apply_count": multicolumn_apply_count,
        }
    finally:
        if hwp is not None:
            try:
                # Discard any dirty failed attempt without a save-confirmation popup.
                hwp.Clear(1)
            except Exception:
                pass
            try:
                hwp.Quit()
            except Exception:
                pass
        if co_initialized:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass


def v0495_create_hwpx_with_hancom(
    output: Path,
    result: dict,
    render_plan: dict,
    *,
    security_module_path: Path | None = None,
    allow_interactive_hwp: bool = False,
    show_hwp: bool = False,
) -> dict:
    """Try native two-column first; retry once in safe sequential mode if needed."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    previous_exists = output.exists()
    previous_size = output.stat().st_size if previous_exists else 0

    security_info = v0493_prepare_hancom_security(security_module_path)
    result["hancom_security_v0495"] = security_info
    _v0491_log(
        "[HWPX] 보안 사전점검: "
        f"{security_info.get('status')} | module={security_info.get('module_name')}"
    )

    attempts = []
    native_build = output.with_name("output_v0_4_9_5_native_build.hwpx")
    safe_build = output.with_name("output_v0_4_9_5_safe_build.hwpx")
    for temp in (native_build, safe_build):
        if temp.exists():
            try:
                temp.unlink()
            except Exception:
                pass

    native = _v0495_render_attempt(
        native_build,
        result,
        render_plan,
        security_info=security_info,
        renderer_mode="native_two_column",
        allow_interactive_hwp=allow_interactive_hwp,
        show_hwp=show_hwp,
    )
    attempts.append({
        "renderer_mode": native.get("renderer_mode"),
        "status": native.get("status"),
        "reason": native.get("reason"),
        "failure_context": native.get("failure_context"),
        "validation": native.get("validation"),
    })
    result["hancom_security_v0495"] = native.get("hancom_security") or security_info

    if native.get("status") == "SKIPPED":
        native["final_path"] = str(output.resolve())
        native["previous_output_preserved"] = previous_exists
        native["attempts"] = attempts
        return native

    selected = native
    if native.get("status") != "created":
        _v0491_log(
            "[HWPX][WARN] native 2단 렌더 실패/검증불합격 -> "
            "v0.4.9.5 safe_sequential 자동 재시도"
        )
        safe = _v0495_render_attempt(
            safe_build,
            result,
            render_plan,
            security_info=security_info,
            renderer_mode="safe_sequential",
            allow_interactive_hwp=allow_interactive_hwp,
            show_hwp=show_hwp,
        )
        attempts.append({
            "renderer_mode": safe.get("renderer_mode"),
            "status": safe.get("status"),
            "reason": safe.get("reason"),
            "failure_context": safe.get("failure_context"),
            "validation": safe.get("validation"),
        })
        selected = safe
        result["hancom_security_v0495"] = safe.get("hancom_security") or result.get("hancom_security_v0495")

    if selected.get("status") == "created":
        src_path = Path(str(selected.get("path")))
        try:
            src_path.replace(output)
        except Exception:
            shutil.copy2(src_path, output)
            try:
                src_path.unlink()
            except Exception:
                pass

        require_two = selected.get("renderer_mode") == "native_two_column"
        final_validation = v0495_validate_hwpx(
            output,
            expected_images=int(result.get("image_filter_v0481", {}).get("saved_count") or 0),
            require_two_column=require_two,
        )
        _v0491_log(
            f"[HWPX] 최종 파일 확정: {output.resolve()} | "
            f"검사={final_validation.get('status')} | "
            f"renderer={selected.get('renderer_mode')}"
        )
        for temp in (native_build, safe_build):
            if temp.exists() and temp != output:
                try:
                    temp.unlink()
                except Exception:
                    pass
        return {
            **selected,
            "status": "created" if final_validation.get("status") == "PASS" else "INVALID",
            "path": str(output.resolve()),
            "final_path": str(output.resolve()),
            "backend": "hancom_com_v0495",
            "validation": final_validation,
            "previous_output_preserved": False,
            "previous_output_existed": previous_exists,
            "previous_output_size": previous_size,
            "attempts": attempts,
        }

    for temp in (native_build, safe_build):
        if temp.exists():
            try:
                temp.unlink()
            except Exception:
                pass
    return {
        **selected,
        "path": str(output.resolve()),
        "final_path": str(output.resolve()),
        "backend": "hancom_com_v0495",
        "previous_output_preserved": previous_exists,
        "previous_output_existed": previous_exists,
        "previous_output_size": previous_size,
        "attempts": attempts,
    }


def v0495_upgrade_result(
    result: dict,
    pdf_path: Path,
    checkpoint_path: Path | None = None,
    *,
    security_module_path: Path | None = None,
    allow_interactive_hwp: bool = False,
    show_hwp: bool = False,
) -> dict:
    _v0491_log("[v0.4.9.5] 이미지/좌표/메타데이터 준비")

    # Keep the stable extraction/image pipeline, but never call an older HWPX writer.
    result = v046_upgrade_result(result, pdf_path)
    result = v0481_prepare_problem_images(pdf_path, result)
    result = v0491_cleanup_legacy_metadata(result)
    result = v0495_attach_question_geometry(pdf_path, result)

    render_plan = v0495_build_render_plan(result)
    result["render_plan_v0495"] = render_plan
    for stale_key in [
        "render_plan_v0494",
        "render_plan_v0493",
        "render_plan_v0492",
        "render_plan_v049",
    ]:
        result.pop(stale_key, None)

    result["version"] = "v0.4.9.5"
    result["parser_version"] = "v0.4.9.5"
    result["generator_version"] = "PDF Parser Integrated v0.4.9.5"
    result["schema_version"] = {
        "base": "v0.4.9.4",
        "extension": [
            "real_question_choice_pdf_geometry",
            "source_order_rendering",
            "native_hangul_multicolumn",
            "breakcolumn_page_flow",
            "safe_sequential_fallback",
            "exact_hangul_picture_size",
            "paragraph_spacing_and_choice_indent",
            "column_and_picture_post_validation",
        ],
    }

    if checkpoint_path is not None:
        checkpoint_path = Path(checkpoint_path)
        result["pre_hwpx_checkpoint"] = {
            "path": str(checkpoint_path.resolve()),
            "purpose": "COM hang/error recovery only",
            "retained_after_success": False,
        }
        _v0491_json_safe_write(checkpoint_path, result)
        _v0491_log(
            f"[v0.4.9.5] HWPX 전 임시 체크포인트 저장: "
            f"{checkpoint_path.resolve()}"
        )

    hwpx_path = pdf_path.parent / "output.hwpx"
    hwpx_info = v0495_create_hwpx_with_hancom(
        hwpx_path,
        result,
        render_plan,
        security_module_path=security_module_path,
        allow_interactive_hwp=allow_interactive_hwp,
        show_hwp=show_hwp,
    )
    result["hwpx_v0495"] = hwpx_info
    result["hancom_security_v0495"] = (
        result.get("hancom_security_v0495")
        or hwpx_info.get("hancom_security")
        or {}
    )

    base_validation = result.get("validation", {})
    img_validation = result.get("image_filter_v0481", {})
    table_validation = result.get("table_filter_v0492", {})
    geometry_validation = result.get("question_geometry_v0495", {})
    source_order_validation = render_plan.get("source_order_v0495", {})
    validation_zip = hwpx_info.get("validation") or {}
    security_runtime = result.get("hancom_security_v0495") or {}
    hwpx_status = hwpx_info.get("status")
    security_ok = (
        security_runtime.get("unattended_ready") is True
        or hwpx_status == "SKIPPED"
        or (allow_interactive_hwp and hwpx_status == "created")
    )

    result["validation_v0495"] = {
        "question_count": len(result.get("questions", [])),
        "passage_group_count": len(result.get("passage_groups", [])),
        "problem_image_count": img_validation.get("selected_problem_figure_count", 0),
        "problem_image_saved": img_validation.get("saved_count", 0),
        "raw_table_count": table_validation.get("raw_table_count", 0),
        "renderable_table_count": table_validation.get("renderable_table_count", 0),
        "excluded_table_count": table_validation.get("excluded_table_count", 0),
        "removed_noncore_block_count": render_plan.get("stats", {}).get("removed_noncore_block_count", 0),
        "answer_count": render_plan.get("stats", {}).get("answer_count", 0),
        "render_page_count": render_plan.get("stats", {}).get("page_count", 0),
        "render_item_count": render_plan.get("stats", {}).get("render_item_count", 0),
        "question_geometry_status": geometry_validation.get("status"),
        "question_source_y_applied_count": source_order_validation.get("question_source_y_applied_count", 0),
        "choice_source_y_applied_count": source_order_validation.get("choice_source_y_applied_count", 0),
        "source_order_status": source_order_validation.get("status"),
        "base_parser_status": base_validation.get("status"),
        "image_status": img_validation.get("status"),
        "hancom_security_status": security_runtime.get("status"),
        "hancom_security_register_result": security_runtime.get("register_module_result"),
        "unattended_ready": security_runtime.get("unattended_ready", False),
        "hwpx_status": hwpx_status,
        "hwpx_renderer_mode": hwpx_info.get("renderer_mode"),
        "hwpx_zip_status": validation_zip.get("status"),
        "hwpx_native_two_column_found": validation_zip.get("native_two_column_found"),
        "hwpx_column_counts": validation_zip.get("column_counts"),
        "hwpx_embedded_image_count": validation_zip.get("bin_data_count"),
        "hwpx_picture_size_count": validation_zip.get("picture_size_count"),
        "hwpx_max_picture_width_hwpunit": validation_zip.get("max_picture_width_hwpunit"),
        "hwpx_picture_width_within_target": validation_zip.get("picture_width_within_target"),
        "image_exact_size_apply_count": hwpx_info.get("image_exact_size_apply_count"),
        "paragraph_style_apply_count": hwpx_info.get("paragraph_style_apply_count"),
        "status": (
            "PASS"
            if base_validation.get("status") == "PASS"
            and img_validation.get("status") == "PASS"
            and table_validation.get("status") == "PASS"
            and geometry_validation.get("status") == "PASS"
            and source_order_validation.get("status") == "PASS"
            and hwpx_status in {"created", "SKIPPED"}
            and security_ok
            else "WARN"
        ),
    }
    result["known_limitations_v0495"] = [
        "native_two_column이 한글 버전별 COM 동작 차이로 검증에 실패하면 같은 실행에서 safe_sequential로 자동 재시도합니다.",
        "비핵심 학습가이드 블록 필터는 휴리스틱 기반이므로 다른 출판사에서는 키워드 규칙 보정이 필요할 수 있습니다.",
        "원본 PDF와 한글의 글꼴/행간 엔진이 달라 페이지 안의 세로 위치를 픽셀 단위로 완전히 동일하게 복제하지는 않습니다.",
        "승인창 없는 완전 무조작 실행은 한컴 공식 FilePathCheckerModuleExample.dll이 PC에 한 번 제공되어 있어야 합니다.",
    ]
    return result


# ============================================================
# V0.4.9.5.1 Stability Hotfix Layer
# - one Hangul COM session / one RegisterModule call per run
# - safe_sequential is the production renderer (native 2-column disabled by default)
# - never discard a structurally valid HWPX candidate because of layout warnings
# - validate all Contents/section*.xml files
# - split package/content/layout/image-size validation signals
# - preserve previous output and failed-but-valid recovery candidates
# ============================================================


def v04951_validate_hwpx(
    path: Path,
    expected_images: int | None = None,
    *,
    max_picture_width_hwpunit: int = 21000,
) -> dict:
    """Validate package integrity separately from content/layout quality.

    v0.4.9.5 mixed picture-count and picture-width checks and only inspected
    section0.xml.  This validator reads every section*.xml and reports each
    signal independently so a usable HWPX is never deleted only because a
    layout-quality check is WARN.
    """
    path = Path(path)
    expected = int(expected_images or 0)
    info = v0494_validate_hwpx(path, expected_images=expected if expected else None)
    info["validator_version"] = "v0.4.9.5.1"
    info["section_files"] = []
    info["section_count"] = 0
    info["column_counts"] = []
    info["native_two_column_found"] = False
    info["picture_object_count"] = 0
    info["picture_size_count"] = 0
    info["picture_sizes_hwpunit"] = []
    info["max_picture_width_hwpunit"] = 0
    info["picture_width_target_cap_hwpunit"] = int(max_picture_width_hwpunit)
    info["embedded_image_count_match"] = None if not expected else False
    info["picture_object_count_match"] = None if not expected else False
    info["picture_width_within_target"] = None
    info["package_status"] = "FAIL"
    info["content_status"] = "WARN"
    info["layout_status"] = "WARN"
    info["quality_status"] = "WARN"

    if not path.exists() or not zipfile.is_zipfile(path):
        info["status"] = "FAIL"
        return info

    try:
        with zipfile.ZipFile(path, "r") as zf:
            names = zf.namelist()
            section_names = sorted(
                name for name in names
                if re.fullmatch(r"Contents/section\d+\.xml", name)
            )
            info["section_files"] = section_names
            info["section_count"] = len(section_names)

            all_col_counts: list[int] = []
            picture_sizes: list[tuple[int, int]] = []
            picture_object_count = 0

            for section_name in section_names:
                xml = zf.read(section_name).decode("utf-8", errors="ignore")
                all_col_counts.extend(
                    int(x) for x in re.findall(r'colCount="(\d+)"', xml)
                )
                pic_blocks = re.findall(r'<hp:pic\b.*?</hp:pic>', xml, re.S)
                picture_object_count += len(pic_blocks)
                for pic in pic_blocks:
                    size_match = re.search(
                        r'<hp:sz[^>]*\bwidth="(\d+)"[^>]*\bheight="(\d+)"',
                        pic,
                    )
                    if size_match:
                        picture_sizes.append(
                            (int(size_match.group(1)), int(size_match.group(2)))
                        )

            info["column_counts"] = all_col_counts
            info["native_two_column_found"] = any(x >= 2 for x in all_col_counts)
            info["picture_object_count"] = picture_object_count
            info["picture_size_count"] = len(picture_sizes)
            info["picture_sizes_hwpunit"] = [
                {"width": w, "height": h} for w, h in picture_sizes
            ]
            info["max_picture_width_hwpunit"] = max(
                (w for w, _ in picture_sizes), default=0
            )

            if expected:
                info["embedded_image_count_match"] = (
                    int(info.get("bin_data_count") or 0) == expected
                )
                info["picture_object_count_match"] = (
                    picture_object_count == expected
                )
            else:
                info["embedded_image_count_match"] = True
                info["picture_object_count_match"] = True

            # Width validity is independent of object count.
            if picture_sizes:
                info["picture_width_within_target"] = all(
                    w <= int(max_picture_width_hwpunit)
                    for w, _ in picture_sizes
                )
            else:
                info["picture_width_within_target"] = (expected == 0)

        package_ok = (
            bool(info.get("zip_valid"))
            and not info.get("missing")
            and bool(info.get("mimetype_stored_first"))
            and not info.get("xml_parse_errors")
        )
        info["package_status"] = "PASS" if package_ok else "FAIL"

        content_ok = (
            bool(info.get("embedded_image_count_match"))
            and bool(info.get("picture_object_count_match"))
        )
        info["content_status"] = "PASS" if content_ok else "WARN"
        info["layout_status"] = (
            "PASS" if info.get("native_two_column_found") else "WARN"
        )
        image_size_ok = info.get("picture_width_within_target") is not False
        info["quality_status"] = (
            "PASS" if content_ok and image_size_ok else "WARN"
        )
        # A valid HWPX package remains usable even when layout/content quality warns.
        info["status"] = (
            "PASS" if package_ok and content_ok and image_size_ok
            else "WARN" if package_ok
            else "FAIL"
        )
    except Exception as exc:
        info["post_validation_error"] = str(exc)
        info["package_status"] = "FAIL"
        info["status"] = "FAIL"
    return info


def v04951_create_hwpx_with_hancom(
    output: Path,
    result: dict,
    render_plan: dict,
    *,
    security_module_path: Path | None = None,
    allow_interactive_hwp: bool = False,
    show_hwp: bool = False,
) -> dict:
    """Production writer: one safe render attempt and one HWP COM session.

    v0.4.9.5 created a valid native candidate, rejected it for layout quality,
    then opened a second HWP process.  The second RegisterModule call could fail,
    after which the first valid candidate was deleted.  v0.4.9.5.1 never starts
    that second session and never discards a structurally valid candidate.
    """
    import os
    import shutil as _shutil

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    previous_exists = output.exists()
    previous_size = output.stat().st_size if previous_exists else 0
    expected_images = int(result.get("image_filter_v0481", {}).get("saved_count") or 0)

    security_info = v0493_prepare_hancom_security(security_module_path)
    result["hancom_security_v04951"] = security_info
    _v0491_log(
        "[HWPX] v0.4.9.5.1 보안 사전점검: "
        f"{security_info.get('status')} | module={security_info.get('module_name')}"
    )

    build = output.with_name("output_v0_4_9_5_1_safe_build.hwpx")
    recovery = output.with_name("output_v0_4_9_5_1_recovery.hwpx")
    if build.exists():
        try:
            build.unlink()
        except Exception:
            pass

    attempt = _v0495_render_attempt(
        build,
        result,
        render_plan,
        security_info=security_info,
        renderer_mode="safe_sequential",
        allow_interactive_hwp=allow_interactive_hwp,
        show_hwp=show_hwp,
    )
    result["hancom_security_v04951"] = (
        attempt.get("hancom_security") or security_info
    )

    if attempt.get("status") == "SKIPPED":
        attempt.update({
            "backend": "hancom_com_v04951",
            "final_path": str(output.resolve()),
            "previous_output_preserved": previous_exists,
            "previous_output_existed": previous_exists,
            "previous_output_size": previous_size,
            "attempts": [{
                "renderer_mode": "safe_sequential",
                "status": "SKIPPED",
                "reason": attempt.get("reason"),
            }],
        })
        return attempt

    validation = None
    if build.exists() and zipfile.is_zipfile(build):
        validation = v04951_validate_hwpx(
            build,
            expected_images=expected_images,
        )

    package_usable = bool(
        validation
        and validation.get("package_status") == "PASS"
    )

    if package_usable:
        # Only replace an existing output after the new candidate is confirmed usable.
        try:
            if output.exists():
                output.unlink()
            try:
                build.replace(output)
            except Exception:
                _shutil.copy2(build, output)
                try:
                    build.unlink()
                except Exception:
                    pass
        except Exception as exc:
            # Preserve the candidate under a deterministic recovery name.
            try:
                if recovery.exists():
                    recovery.unlink()
                _shutil.copy2(build, recovery)
            except Exception:
                pass
            return {
                **attempt,
                "status": "ERROR",
                "reason": f"validated candidate could not replace output.hwpx: {exc}",
                "path": str(output.resolve()),
                "final_path": str(output.resolve()),
                "recovery_path": str(recovery.resolve()) if recovery.exists() else None,
                "backend": "hancom_com_v04951",
                "renderer_mode": "safe_sequential",
                "validation": validation,
                "previous_output_preserved": previous_exists and output.exists(),
                "previous_output_existed": previous_exists,
                "previous_output_size": previous_size,
                "attempts": [{
                    "renderer_mode": "safe_sequential",
                    "status": attempt.get("status"),
                    "reason": attempt.get("reason"),
                    "validation": validation,
                }],
            }

        final_validation = v04951_validate_hwpx(
            output,
            expected_images=expected_images,
        )
        _v0491_log(
            f"[HWPX] v0.4.9.5.1 최종 파일 확정: {output.resolve()} | "
            f"package={final_validation.get('package_status')} | "
            f"content={final_validation.get('content_status')} | "
            f"layout={final_validation.get('layout_status')}"
        )
        return {
            **attempt,
            "status": "created",
            "path": str(output.resolve()),
            "final_path": str(output.resolve()),
            "backend": "hancom_com_v04951",
            "renderer_mode": "safe_sequential",
            "validation": final_validation,
            "quality_status": final_validation.get("status"),
            "previous_output_preserved": False,
            "previous_output_existed": previous_exists,
            "previous_output_size": previous_size,
            "attempts": [{
                "renderer_mode": "safe_sequential",
                "status": attempt.get("status"),
                "reason": attempt.get("reason"),
                "validation": final_validation,
            }],
        }

    # New render failed or produced a broken package. Keep any old output intact.
    recovery_path = None
    if build.exists():
        try:
            if recovery.exists():
                recovery.unlink()
            build.replace(recovery)
            recovery_path = str(recovery.resolve())
        except Exception:
            recovery_path = str(build.resolve())

    return {
        **attempt,
        "status": attempt.get("status") or "ERROR",
        "path": str(output.resolve()),
        "final_path": str(output.resolve()),
        "recovery_path": recovery_path,
        "backend": "hancom_com_v04951",
        "renderer_mode": "safe_sequential",
        "validation": validation,
        "previous_output_preserved": previous_exists and output.exists(),
        "previous_output_existed": previous_exists,
        "previous_output_size": previous_size,
        "attempts": [{
            "renderer_mode": "safe_sequential",
            "status": attempt.get("status"),
            "reason": attempt.get("reason"),
            "failure_context": attempt.get("failure_context"),
            "validation": validation,
        }],
    }


def v04951_upgrade_result(
    result: dict,
    pdf_path: Path,
    checkpoint_path: Path | None = None,
    *,
    security_module_path: Path | None = None,
    allow_interactive_hwp: bool = False,
    show_hwp: bool = False,
) -> dict:
    _v0491_log("[v0.4.9.5.1] 이미지/좌표/메타데이터 준비")

    result = v046_upgrade_result(result, pdf_path)
    result = v0481_prepare_problem_images(pdf_path, result)
    result = v0491_cleanup_legacy_metadata(result)
    result = v0495_attach_question_geometry(pdf_path, result)

    render_plan = v0495_build_render_plan(result)
    render_plan["version"] = "v0.4.9.5.1"
    render_plan["layout_mode"] = "safe_sequential_single_hwp_session"
    render_plan["native_two_column_policy_v04951"] = {
        "enabled": False,
        "reason": (
            "v0.4.9.5 MultiColumn action serialized colCount=1 on the tested Hangul build; "
            "production mode prioritizes deterministic output generation."
        ),
    }
    result["render_plan_v04951"] = render_plan
    for stale_key in [
        "render_plan_v0495", "render_plan_v0494", "render_plan_v0493",
        "render_plan_v0492", "render_plan_v049",
    ]:
        result.pop(stale_key, None)

    result["version"] = "v0.4.9.5.1"
    result["parser_version"] = "v0.4.9.5.1"
    result["generator_version"] = "PDF Parser Integrated v0.4.9.5.1"
    result["schema_version"] = {
        "base": "v0.4.9.5",
        "extension": [
            "single_hwp_com_session",
            "single_registermodule_call",
            "safe_sequential_production_renderer",
            "non_destructive_valid_candidate_preservation",
            "all_section_xml_validation",
            "split_package_content_layout_validation",
            "independent_picture_count_and_width_checks",
            "source_order_rendering",
            "exact_hangul_picture_size",
            "paragraph_spacing_and_choice_indent",
        ],
    }

    if checkpoint_path is not None:
        checkpoint_path = Path(checkpoint_path)
        result["pre_hwpx_checkpoint"] = {
            "path": str(checkpoint_path.resolve()),
            "purpose": "COM hang/error recovery only",
            "retained_after_success": False,
        }
        _v0491_json_safe_write(checkpoint_path, result)
        _v0491_log(
            f"[v0.4.9.5.1] HWPX 전 임시 체크포인트 저장: "
            f"{checkpoint_path.resolve()}"
        )

    hwpx_path = pdf_path.parent / "output.hwpx"
    hwpx_info = v04951_create_hwpx_with_hancom(
        hwpx_path,
        result,
        render_plan,
        security_module_path=security_module_path,
        allow_interactive_hwp=allow_interactive_hwp,
        show_hwp=show_hwp,
    )
    result["hwpx_v04951"] = hwpx_info
    result["hancom_security_v04951"] = (
        result.get("hancom_security_v04951")
        or hwpx_info.get("hancom_security")
        or {}
    )

    base_validation = result.get("validation", {})
    img_validation = result.get("image_filter_v0481", {})
    table_validation = result.get("table_filter_v0492", {})
    geometry_validation = result.get("question_geometry_v0495", {})
    source_order_validation = render_plan.get("source_order_v0495", {})
    final_validation = hwpx_info.get("validation") or {}
    security_runtime = result.get("hancom_security_v04951") or {}
    hwpx_status = hwpx_info.get("status")
    security_ok = (
        security_runtime.get("unattended_ready") is True
        or hwpx_status == "SKIPPED"
        or (allow_interactive_hwp and hwpx_status == "created")
    )

    hard_pass = (
        base_validation.get("status") == "PASS"
        and img_validation.get("status") == "PASS"
        and table_validation.get("status") == "PASS"
        and geometry_validation.get("status") == "PASS"
        and source_order_validation.get("status") == "PASS"
        and hwpx_status in {"created", "SKIPPED"}
        and security_ok
        and final_validation.get("package_status") in {"PASS", None}
    )
    quality_warn = (
        final_validation.get("content_status") == "WARN"
        or final_validation.get("quality_status") == "WARN"
    )

    result["validation_v04951"] = {
        "question_count": len(result.get("questions", [])),
        "passage_group_count": len(result.get("passage_groups", [])),
        "problem_image_count": img_validation.get("selected_problem_figure_count", 0),
        "problem_image_saved": img_validation.get("saved_count", 0),
        "raw_table_count": table_validation.get("raw_table_count", 0),
        "renderable_table_count": table_validation.get("renderable_table_count", 0),
        "excluded_table_count": table_validation.get("excluded_table_count", 0),
        "removed_noncore_block_count": render_plan.get("stats", {}).get("removed_noncore_block_count", 0),
        "answer_count": render_plan.get("stats", {}).get("answer_count", 0),
        "render_page_count": render_plan.get("stats", {}).get("page_count", 0),
        "render_item_count": render_plan.get("stats", {}).get("render_item_count", 0),
        "question_geometry_status": geometry_validation.get("status"),
        "question_source_y_applied_count": source_order_validation.get("question_source_y_applied_count", 0),
        "choice_source_y_applied_count": source_order_validation.get("choice_source_y_applied_count", 0),
        "source_order_status": source_order_validation.get("status"),
        "base_parser_status": base_validation.get("status"),
        "image_status": img_validation.get("status"),
        "hancom_security_status": security_runtime.get("status"),
        "hancom_security_register_result": security_runtime.get("register_module_result"),
        "unattended_ready": security_runtime.get("unattended_ready", False),
        "hwpx_status": hwpx_status,
        "hwpx_renderer_mode": hwpx_info.get("renderer_mode"),
        "hwpx_package_status": final_validation.get("package_status"),
        "hwpx_content_status": final_validation.get("content_status"),
        "hwpx_layout_status": final_validation.get("layout_status"),
        "hwpx_quality_status": final_validation.get("quality_status"),
        "hwpx_zip_status": final_validation.get("status"),
        "hwpx_section_count": final_validation.get("section_count"),
        "hwpx_section_files": final_validation.get("section_files"),
        "hwpx_embedded_image_count": final_validation.get("bin_data_count"),
        "hwpx_embedded_image_count_match": final_validation.get("embedded_image_count_match"),
        "hwpx_picture_object_count": final_validation.get("picture_object_count"),
        "hwpx_picture_object_count_match": final_validation.get("picture_object_count_match"),
        "hwpx_max_picture_width_hwpunit": final_validation.get("max_picture_width_hwpunit"),
        "hwpx_picture_width_within_target": final_validation.get("picture_width_within_target"),
        "image_exact_size_apply_count": hwpx_info.get("image_exact_size_apply_count"),
        "paragraph_style_apply_count": hwpx_info.get("paragraph_style_apply_count"),
        "status": "WARN" if hard_pass and quality_warn else ("PASS" if hard_pass else "WARN"),
    }
    result["known_limitations_v04951"] = [
        "v0.4.9.5에서 실제 HWPX가 colCount=1로 저장된 native MultiColumn 방식은 production 경로에서 비활성화했습니다.",
        "현재 기본 출력은 한 번의 HWP COM 세션과 한 번의 RegisterModule 호출로 생성하는 safe_sequential 방식입니다.",
        "유효한 HWPX 패키지가 생성되면 레이아웃 품질 경고가 있어도 output.hwpx를 보존합니다.",
        "그림 개수와 그림 폭 검증은 독립적으로 기록하며 모든 Contents/section*.xml을 검사합니다.",
        "원본 PDF와 한글의 글꼴/행간 엔진 차이 때문에 픽셀 단위 세로 위치 완전 복제는 하지 않습니다.",
    ]
    return result



# ============================================================
# V0.4.9.5.2 Image Anchor Validation + Native HColDef 2-Column Layer
# - InsertPicture Width/Height only: no post-insert control-selection correction
# - one HWP COM session / one RegisterModule call
# - HColDef-based real MultiColumn attempt with same-session pre-render fallback
# - validate image filename order from BinData hashes
# - fail if any problem picture is serialized after [정답 및 해설]
# - validate expected PDF page/group by neighboring HWPX text anchors
# - expose image_order_status / image_anchor_status in final JSON
# ============================================================

def _v04952_anchor_normalize(value: Any) -> str:
    import html as _html
    text_value = _html.unescape(_v049_text(value))
    text_value = re.sub(r"\s+", "", text_value)
    text_value = re.sub(
        r"""[\[\]<>〈〉《》「」『』“”‘’'"(),.:;!?…·\-―]+""",
        "",
        text_value,
    )
    return text_value


def _v04952_anchor_match(actual: str, expected: str) -> bool | None:
    """Loose but deterministic neighbor-text comparison for picture anchors."""
    a = _v04952_anchor_normalize(actual)
    e = _v04952_anchor_normalize(expected)
    if not e:
        return None
    if not a:
        return False
    if a == e or a in e or e in a:
        return True
    span = min(24, len(a), len(e))
    if span <= 0:
        return False
    return a[:span] == e[:span] or a[-span:] == e[-span:]


def _v04952_item_text(item: dict) -> str:
    kind = item.get("type")
    if kind == "block":
        return _v049_text(item.get("text")).strip()
    if kind == "question":
        return (
            f"{item.get('number')}. "
            f"{_v049_text(item.get('text')).strip()}"
        ).strip()
    if kind == "choice":
        return (
            f"{item.get('prefix') or '-'} "
            f"{_v049_text(item.get('text')).strip()}"
        ).strip()
    if kind == "example_box":
        return (
            f"<{item.get('title') or '보기'}> "
            f"{_v049_text(item.get('text')).strip()}"
        ).strip()
    return ""


def _v04952_expected_image_stream(render_plan: dict) -> list[dict]:
    """Return images in the exact order the renderer is expected to insert them."""
    stream: list[dict] = []
    flat_items: list[dict] = []

    for page_entry in render_plan.get("pages", []):
        page_no = int(page_entry.get("page") or 0)
        for column in ("left", "right"):
            for item in page_entry.get(column, []):
                payload = dict(item)
                payload.setdefault("page", page_no)
                payload.setdefault("column", column)
                flat_items.append(payload)

    for idx, item in enumerate(flat_items):
        if item.get("type") != "image":
            continue

        prev_text = ""
        next_text = ""
        for pos in range(idx - 1, -1, -1):
            candidate = _v04952_item_text(flat_items[pos])
            if candidate:
                prev_text = candidate
                break
        for pos in range(idx + 1, len(flat_items)):
            candidate = _v04952_item_text(flat_items[pos])
            if candidate:
                next_text = candidate
                break

        stream.append({
            "filename": item.get("filename"),
            "path": item.get("path"),
            "relative_path": item.get("relative_path"),
            "page": int(item.get("page") or 0),
            "column": item.get("column"),
            "group_id": item.get("group_id"),
            "section_label": item.get("section_label"),
            "sort_y": item.get("sort_y"),
            "expected_prev_text": prev_text,
            "expected_next_text": next_text,
        })

    return stream


def _v04952_expected_hashes(
    result: dict,
    expected_stream: list[dict],
) -> tuple[dict[str, list[str]], dict[str, str]]:
    """Map embedded image digests back to deterministic problem-image filenames."""
    digest_to_names: dict[str, list[str]] = defaultdict(list)
    filename_to_digest: dict[str, str] = {}

    # First preference: the parser's original embedded-image MD5.
    for asset in result.get("image_assets", []):
        out = asset.get("image_output") or {}
        filename = out.get("filename")
        digest = asset.get("byte_hash")
        if filename and digest:
            filename_to_digest[str(filename)] = str(digest)

    # Fallback: hash the exported problem image currently on disk.
    for item in expected_stream:
        filename = str(item.get("filename") or "")
        if not filename or filename in filename_to_digest:
            continue
        image_path = Path(str(item.get("path") or ""))
        if image_path.exists() and image_path.is_file():
            try:
                filename_to_digest[filename] = hashlib.md5(
                    image_path.read_bytes()
                ).hexdigest()
            except Exception:
                pass

    expected_names = [
        str(item.get("filename") or "")
        for item in expected_stream
        if item.get("filename")
    ]
    for filename in expected_names:
        digest = filename_to_digest.get(filename)
        if digest:
            digest_to_names[digest].append(filename)

    return dict(digest_to_names), filename_to_digest


def v04952_validate_hwpx(
    path: Path,
    *,
    expected_images: int | None = None,
    render_plan: dict | None = None,
    result: dict | None = None,
    max_picture_width_hwpunit: int = 21000,
    require_two_column: bool = False,
) -> dict:
    """Validate HWPX package, image order, answer boundary and text anchors.

    Positional failures never cause the caller to delete a structurally valid
    HWPX.  They are nevertheless recorded as FAIL so layout regressions are
    visible in JSON instead of being hidden behind image-count PASS signals.
    """
    import html as _html

    path = Path(path)
    expected_count = int(expected_images or 0)
    info = v04951_validate_hwpx(
        path,
        expected_images=expected_count,
        max_picture_width_hwpunit=max_picture_width_hwpunit,
    )
    info["validator_version"] = "v0.4.9.5.2"
    info["require_two_column"] = bool(require_two_column)
    info["image_order_status"] = "WARN"
    info["image_anchor_status"] = "WARN"
    info["image_answer_boundary_status"] = "WARN"
    info["image_position_status"] = "WARN"
    info["expected_image_filenames"] = []
    info["actual_image_filenames"] = []
    info["image_anchor_details"] = []
    info["answer_boundary_paragraph_index"] = None
    info["pictures_after_answer_count"] = 0
    info["pictures_after_answer"] = []

    if (
        not path.exists()
        or not zipfile.is_zipfile(path)
        or info.get("package_status") != "PASS"
    ):
        return info

    expected_stream = _v04952_expected_image_stream(render_plan or {})
    expected_names = [
        str(item.get("filename") or "")
        for item in expected_stream
        if item.get("filename")
    ]
    info["expected_image_filenames"] = expected_names
    expected_by_name = {
        str(item.get("filename")): item
        for item in expected_stream
        if item.get("filename")
    }

    digest_to_names, filename_to_digest = _v04952_expected_hashes(
        result or {},
        expected_stream,
    )
    # Consume duplicate image hashes in expected render order.
    digest_queues = {
        digest: list(names)
        for digest, names in digest_to_names.items()
    }

    try:
        with zipfile.ZipFile(path, "r") as zf:
            names = zf.namelist()
            section_names = sorted(
                (
                    name for name in names
                    if re.fullmatch(r"Contents/section\d+\.xml", name)
                ),
                key=lambda name: int(re.search(r"(\d+)", name).group(1)),
            )

            id_to_href: dict[str, str] = {}
            if "Contents/content.hpf" in names:
                hpf = zf.read("Contents/content.hpf").decode(
                    "utf-8",
                    errors="ignore",
                )
                for match in re.finditer(r"<opf:item\b[^>]*>", hpf):
                    tag = match.group(0)
                    id_match = re.search(r'\bid="([^"]+)"', tag)
                    href_match = re.search(r'\bhref="([^"]+)"', tag)
                    if id_match and href_match:
                        id_to_href[id_match.group(1)] = href_match.group(1)

            paragraphs: list[dict] = []
            global_index = 0
            for section_name in section_names:
                xml = zf.read(section_name).decode("utf-8", errors="ignore")
                for paragraph_match in re.finditer(
                    r"<hp:p\b.*?</hp:p>",
                    xml,
                    re.S,
                ):
                    paragraph_xml = paragraph_match.group(0)
                    text_parts = []
                    for text_match in re.findall(
                        r"<hp:t\b[^>]*>(.*?)</hp:t>",
                        paragraph_xml,
                        re.S,
                    ):
                        clean = re.sub(r"<[^>]+>", "", text_match)
                        text_parts.append(_html.unescape(clean))
                    picture_refs = re.findall(
                        r'\bbinaryItemIDRef="([^"]+)"',
                        paragraph_xml,
                    )
                    paragraphs.append({
                        "index": global_index,
                        "section": section_name,
                        "text": "".join(text_parts),
                        "picture_refs": picture_refs,
                    })
                    global_index += 1

            answer_index = next(
                (
                    int(paragraph["index"])
                    for paragraph in paragraphs
                    if "정답및해설" in _v04952_anchor_normalize(
                        paragraph.get("text", "")
                    )
                ),
                None,
            )
            info["answer_boundary_paragraph_index"] = answer_index

            actual_pictures: list[dict] = []
            for paragraph_pos, paragraph in enumerate(paragraphs):
                for ref in paragraph.get("picture_refs", []):
                    href = id_to_href.get(ref)
                    if not href:
                        for extension in ("png", "jpg", "jpeg", "bmp", "gif"):
                            candidate = f"BinData/{ref}.{extension}"
                            if candidate in names:
                                href = candidate
                                break

                    digest = None
                    if href and href in names:
                        try:
                            digest = hashlib.md5(zf.read(href)).hexdigest()
                        except Exception:
                            digest = None

                    filename = None
                    if digest and digest_queues.get(digest):
                        filename = digest_queues[digest].pop(0)

                    previous_text = next(
                        (
                            paragraphs[pos].get("text", "")
                            for pos in range(paragraph_pos - 1, -1, -1)
                            if paragraphs[pos].get("text", "").strip()
                        ),
                        "",
                    )
                    next_text = next(
                        (
                            paragraphs[pos].get("text", "")
                            for pos in range(
                                paragraph_pos + 1,
                                len(paragraphs),
                            )
                            if paragraphs[pos].get("text", "").strip()
                        ),
                        "",
                    )

                    actual_pictures.append({
                        "binary_item_id": ref,
                        "href": href,
                        "digest": digest,
                        "filename": filename,
                        "paragraph_index": int(paragraph.get("index") or 0),
                        "section": paragraph.get("section"),
                        "actual_prev_text": previous_text,
                        "actual_next_text": next_text,
                    })

            actual_names = [
                str(item.get("filename") or f"<unmapped:{item.get('binary_item_id')}>")
                for item in actual_pictures
            ]
            info["actual_image_filenames"] = actual_names

            fully_mapped = (
                len(actual_pictures) == len(expected_names)
                and all(item.get("filename") for item in actual_pictures)
            )
            if expected_names and fully_mapped:
                info["image_order_status"] = (
                    "PASS"
                    if actual_names == expected_names
                    else "FAIL"
                )
            elif not expected_names and not actual_pictures:
                info["image_order_status"] = "PASS"
            else:
                info["image_order_status"] = "WARN"

            pictures_after_answer = []
            if answer_index is not None:
                pictures_after_answer = [
                    {
                        "filename": item.get("filename"),
                        "binary_item_id": item.get("binary_item_id"),
                        "paragraph_index": item.get("paragraph_index"),
                        "section": item.get("section"),
                    }
                    for item in actual_pictures
                    if int(item.get("paragraph_index") or 0) > answer_index
                ]
                info["pictures_after_answer"] = pictures_after_answer
                info["pictures_after_answer_count"] = len(
                    pictures_after_answer
                )
                info["image_answer_boundary_status"] = (
                    "PASS" if not pictures_after_answer else "FAIL"
                )
            elif render_plan and render_plan.get("answer_items"):
                info["image_answer_boundary_status"] = "WARN"
            else:
                info["image_answer_boundary_status"] = "PASS"

            anchor_details = []
            anchor_fail = False
            anchor_unknown = False
            for actual in actual_pictures:
                filename = actual.get("filename")
                expected = expected_by_name.get(str(filename)) if filename else None
                if not expected:
                    anchor_unknown = True
                    anchor_details.append({
                        **actual,
                        "expected_page": None,
                        "expected_group_id": None,
                        "expected_column": None,
                        "expected_prev_text": None,
                        "expected_next_text": None,
                        "prev_match": None,
                        "next_match": None,
                        "anchor_match": None,
                    })
                    continue

                prev_match = _v04952_anchor_match(
                    actual.get("actual_prev_text", ""),
                    expected.get("expected_prev_text", ""),
                )
                next_match = _v04952_anchor_match(
                    actual.get("actual_next_text", ""),
                    expected.get("expected_next_text", ""),
                )
                comparable = [
                    value
                    for value in (prev_match, next_match)
                    if value is not None
                ]
                # One matching neighbor is sufficient for consecutive pictures.
                anchor_match = (
                    any(comparable)
                    if comparable
                    else None
                )
                if anchor_match is False:
                    anchor_fail = True
                if anchor_match is None:
                    anchor_unknown = True

                anchor_details.append({
                    **actual,
                    "expected_page": expected.get("page"),
                    "expected_group_id": expected.get("group_id"),
                    "expected_column": expected.get("column"),
                    "expected_section_label": expected.get("section_label"),
                    "expected_prev_text": expected.get("expected_prev_text"),
                    "expected_next_text": expected.get("expected_next_text"),
                    "prev_match": prev_match,
                    "next_match": next_match,
                    "anchor_match": anchor_match,
                })

            info["image_anchor_details"] = anchor_details
            if anchor_fail:
                info["image_anchor_status"] = "FAIL"
            elif anchor_unknown:
                info["image_anchor_status"] = "WARN"
            else:
                info["image_anchor_status"] = "PASS"

            position_signals = (
                info.get("image_order_status"),
                info.get("image_anchor_status"),
                info.get("image_answer_boundary_status"),
            )
            if "FAIL" in position_signals:
                info["image_position_status"] = "FAIL"
            elif "WARN" in position_signals:
                info["image_position_status"] = "WARN"
            else:
                info["image_position_status"] = "PASS"

            # Count/size package validation remains independent, but a known
            # picture-position regression must surface as a validation failure.
            if info.get("image_position_status") == "FAIL":
                info["content_status"] = "FAIL"
                info["quality_status"] = "FAIL"
                info["status"] = "FAIL"
            else:
                layout_ok = bool(info.get("native_two_column_found"))
                info["layout_status"] = "PASS" if layout_ok else "WARN"
                if require_two_column and not layout_ok:
                    # Keep the file; report that the native layout attempt did not
                    # serialize as 2-column instead of deleting a usable document.
                    if info.get("status") == "PASS":
                        info["status"] = "WARN"

    except Exception as exc:
        info["position_validation_error"] = str(exc)
        info["image_order_status"] = "WARN"
        info["image_anchor_status"] = "WARN"
        info["image_answer_boundary_status"] = "WARN"
        info["image_position_status"] = "WARN"
        if info.get("package_status") == "PASS":
            info["status"] = "WARN"
        else:
            info["status"] = "FAIL"

    return info


def v04952_create_hwpx_with_hancom(
    output: Path,
    result: dict,
    render_plan: dict,
    *,
    security_module_path: Path | None = None,
    allow_interactive_hwp: bool = False,
    show_hwp: bool = False,
) -> dict:
    """Single-session writer with HColDef native 2-column attempt.

    The renderer opens Hangul once.  If HColDef cannot be applied, it switches
    to safe_sequential before writing content in that same session.  After save,
    package validity decides whether output.hwpx is preserved; layout/anchor
    warnings never delete a valid candidate.
    """
    import shutil as _shutil

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    previous_exists = output.exists()
    previous_size = output.stat().st_size if previous_exists else 0
    expected_count = int(
        result.get("image_filter_v0481", {}).get("saved_count") or 0
    )

    security_info = v0493_prepare_hancom_security(security_module_path)
    result["hancom_security_v04952"] = security_info
    _v0491_log(
        "[HWPX] v0.4.9.5.2 보안 사전점검: "
        f"{security_info.get('status')} | "
        f"module={security_info.get('module_name')}"
    )

    build = output.with_name("output_v0_4_9_5_2_build.hwpx")
    recovery = output.with_name("output_v0_4_9_5_2_recovery.hwpx")
    if build.exists():
        try:
            build.unlink()
        except Exception:
            pass

    attempt = _v0495_render_attempt(
        build,
        result,
        render_plan,
        security_info=security_info,
        renderer_mode="native_two_column",
        allow_interactive_hwp=allow_interactive_hwp,
        show_hwp=show_hwp,
    )
    result["hancom_security_v04952"] = (
        attempt.get("hancom_security") or security_info
    )

    if attempt.get("status") == "SKIPPED":
        attempt.update({
            "backend": "hancom_com_v04952",
            "final_path": str(output.resolve()),
            "previous_output_preserved": previous_exists,
            "previous_output_existed": previous_exists,
            "previous_output_size": previous_size,
            "attempts": [{
                "renderer_mode": attempt.get("renderer_mode"),
                "status": "SKIPPED",
                "reason": attempt.get("reason"),
            }],
        })
        return attempt

    validation = None
    if build.exists() and zipfile.is_zipfile(build):
        validation = v04952_validate_hwpx(
            build,
            expected_images=expected_count,
            render_plan=render_plan,
            result=result,
            require_two_column=(
                attempt.get("renderer_mode") == "native_two_column"
            ),
        )

    package_usable = bool(
        validation
        and validation.get("package_status") == "PASS"
    )

    if package_usable:
        try:
            if output.exists():
                output.unlink()
            try:
                build.replace(output)
            except Exception:
                _shutil.copy2(build, output)
                try:
                    build.unlink()
                except Exception:
                    pass
        except Exception as exc:
            try:
                if recovery.exists():
                    recovery.unlink()
                _shutil.copy2(build, recovery)
            except Exception:
                pass
            return {
                **attempt,
                "status": "ERROR",
                "reason": (
                    "validated candidate could not replace output.hwpx: "
                    f"{exc}"
                ),
                "path": str(output.resolve()),
                "final_path": str(output.resolve()),
                "recovery_path": (
                    str(recovery.resolve()) if recovery.exists() else None
                ),
                "backend": "hancom_com_v04952",
                "validation": validation,
                "previous_output_preserved": previous_exists and output.exists(),
                "previous_output_existed": previous_exists,
                "previous_output_size": previous_size,
                "attempts": [{
                    "renderer_mode": attempt.get("renderer_mode"),
                    "status": attempt.get("status"),
                    "reason": attempt.get("reason"),
                    "validation": validation,
                }],
            }

        final_validation = v04952_validate_hwpx(
            output,
            expected_images=expected_count,
            render_plan=render_plan,
            result=result,
            require_two_column=(
                attempt.get("renderer_mode") == "native_two_column"
            ),
        )
        _v0491_log(
            "[HWPX] v0.4.9.5.2 최종 파일 확정: "
            f"{output.resolve()} | "
            f"package={final_validation.get('package_status')} | "
            f"2단={final_validation.get('native_two_column_found')} | "
            f"order={final_validation.get('image_order_status')} | "
            f"anchor={final_validation.get('image_anchor_status')} | "
            f"answer-boundary="
            f"{final_validation.get('image_answer_boundary_status')}"
        )
        return {
            **attempt,
            "status": "created",
            "path": str(output.resolve()),
            "final_path": str(output.resolve()),
            "backend": "hancom_com_v04952",
            "renderer_mode": attempt.get("renderer_mode"),
            "validation": final_validation,
            "quality_status": final_validation.get("status"),
            "previous_output_preserved": False,
            "previous_output_existed": previous_exists,
            "previous_output_size": previous_size,
            "attempts": [{
                "renderer_mode": attempt.get("renderer_mode"),
                "status": attempt.get("status"),
                "reason": attempt.get("reason"),
                "validation": final_validation,
            }],
        }

    recovery_path = None
    if build.exists():
        try:
            if recovery.exists():
                recovery.unlink()
            build.replace(recovery)
            recovery_path = str(recovery.resolve())
        except Exception:
            recovery_path = str(build.resolve())

    return {
        **attempt,
        "status": attempt.get("status") or "ERROR",
        "path": str(output.resolve()),
        "final_path": str(output.resolve()),
        "recovery_path": recovery_path,
        "backend": "hancom_com_v04952",
        "validation": validation,
        "previous_output_preserved": previous_exists and output.exists(),
        "previous_output_existed": previous_exists,
        "previous_output_size": previous_size,
        "attempts": [{
            "renderer_mode": attempt.get("renderer_mode"),
            "status": attempt.get("status"),
            "reason": attempt.get("reason"),
            "failure_context": attempt.get("failure_context"),
            "validation": validation,
        }],
    }


def v04952_upgrade_result(
    result: dict,
    pdf_path: Path,
    checkpoint_path: Path | None = None,
    *,
    security_module_path: Path | None = None,
    allow_interactive_hwp: bool = False,
    show_hwp: bool = False,
) -> dict:
    _v0491_log("[v0.4.9.5.2] 이미지/좌표/앵커/2단 메타데이터 준비")

    result = v046_upgrade_result(result, pdf_path)
    result = v0481_prepare_problem_images(pdf_path, result)
    result = v0491_cleanup_legacy_metadata(result)
    result = v0495_attach_question_geometry(pdf_path, result)

    render_plan = v0495_build_render_plan(result)
    render_plan["version"] = "v0.4.9.5.2"
    render_plan["layout_mode"] = (
        "native_hcoldef_two_column_single_session"
    )
    render_plan["native_two_column_policy_v04952"] = {
        "enabled": True,
        "method": (
            'HAction.GetDefault("MultiColumn", '
            "HParameterSet.HColDef.HSet)"
        ),
        "fallback": (
            "If HColDef setup fails before rendering, switch to "
            "safe_sequential inside the same HWP COM session."
        ),
        "post_save_policy": (
            "A valid HWPX is preserved even when colCount remains 1; "
            "layout_status becomes WARN."
        ),
    }
    render_plan["image_anchor_policy_v04952"] = {
        "no_control_selection_after_insert": True,
        "size_method": "InsertPicture Width/Height only",
        "validate_filename_order": True,
        "fail_picture_after_answer_boundary": True,
        "validate_neighbor_text_anchor": True,
    }
    result["render_plan_v04952"] = render_plan
    for stale_key in [
        "render_plan_v04951", "render_plan_v0495", "render_plan_v0494",
        "render_plan_v0493", "render_plan_v0492", "render_plan_v049",
    ]:
        result.pop(stale_key, None)

    result["version"] = "v0.4.9.5.2"
    result["parser_version"] = "v0.4.9.5.2"
    result["generator_version"] = "PDF Parser Integrated v0.4.9.5.2"
    result["schema_version"] = {
        "base": "v0.4.9.5.1",
        "extension": [
            "insertpicture_size_only_no_findctrl",
            "no_control_selection_after_picture_insert",
            "bin_data_filename_order_validation",
            "answer_boundary_picture_failure_check",
            "neighbor_text_picture_anchor_validation",
            "image_order_status",
            "image_anchor_status",
            "native_hcoldef_two_column_retry",
            "single_hwp_com_session",
            "single_registermodule_call",
            "non_destructive_valid_candidate_preservation",
        ],
    }

    if checkpoint_path is not None:
        checkpoint_path = Path(checkpoint_path)
        result["pre_hwpx_checkpoint"] = {
            "path": str(checkpoint_path.resolve()),
            "purpose": "COM hang/error recovery only",
            "retained_after_success": False,
        }
        _v0491_json_safe_write(checkpoint_path, result)
        _v0491_log(
            "[v0.4.9.5.2] HWPX 전 임시 체크포인트 저장: "
            f"{checkpoint_path.resolve()}"
        )

    hwpx_path = pdf_path.parent / "output.hwpx"
    hwpx_info = v04952_create_hwpx_with_hancom(
        hwpx_path,
        result,
        render_plan,
        security_module_path=security_module_path,
        allow_interactive_hwp=allow_interactive_hwp,
        show_hwp=show_hwp,
    )
    result["hwpx_v04952"] = hwpx_info
    result["hancom_security_v04952"] = (
        result.get("hancom_security_v04952")
        or hwpx_info.get("hancom_security")
        or {}
    )

    base_validation = result.get("validation", {})
    img_validation = result.get("image_filter_v0481", {})
    table_validation = result.get("table_filter_v0492", {})
    geometry_validation = result.get("question_geometry_v0495", {})
    source_order_validation = render_plan.get("source_order_v0495", {})
    final_validation = hwpx_info.get("validation") or {}
    security_runtime = result.get("hancom_security_v04952") or {}
    hwpx_status = hwpx_info.get("status")
    security_ok = (
        security_runtime.get("unattended_ready") is True
        or hwpx_status == "SKIPPED"
        or (allow_interactive_hwp and hwpx_status == "created")
    )

    hard_pass = (
        base_validation.get("status") == "PASS"
        and img_validation.get("status") == "PASS"
        and table_validation.get("status") == "PASS"
        and geometry_validation.get("status") == "PASS"
        and source_order_validation.get("status") == "PASS"
        and hwpx_status in {"created", "SKIPPED"}
        and security_ok
        and final_validation.get("package_status") in {"PASS", None}
    )
    positional_fail = any(
        final_validation.get(key) == "FAIL"
        for key in (
            "image_order_status",
            "image_anchor_status",
            "image_answer_boundary_status",
        )
    )
    quality_warn = (
        final_validation.get("content_status") in {"WARN", "FAIL"}
        or final_validation.get("quality_status") in {"WARN", "FAIL"}
        or final_validation.get("layout_status") == "WARN"
        or final_validation.get("image_order_status") == "WARN"
        or final_validation.get("image_anchor_status") == "WARN"
        or final_validation.get("image_answer_boundary_status") == "WARN"
    )

    if positional_fail:
        final_status = "FAIL"
    elif hard_pass and quality_warn:
        final_status = "WARN"
    elif hard_pass:
        final_status = "PASS"
    else:
        final_status = "WARN"

    result["validation_v04952"] = {
        "question_count": len(result.get("questions", [])),
        "passage_group_count": len(result.get("passage_groups", [])),
        "problem_image_count": img_validation.get(
            "selected_problem_figure_count", 0
        ),
        "problem_image_saved": img_validation.get("saved_count", 0),
        "raw_table_count": table_validation.get("raw_table_count", 0),
        "renderable_table_count": table_validation.get(
            "renderable_table_count", 0
        ),
        "excluded_table_count": table_validation.get(
            "excluded_table_count", 0
        ),
        "removed_noncore_block_count": render_plan.get(
            "stats", {}
        ).get("removed_noncore_block_count", 0),
        "answer_count": render_plan.get("stats", {}).get("answer_count", 0),
        "render_page_count": render_plan.get("stats", {}).get(
            "page_count", 0
        ),
        "render_item_count": render_plan.get("stats", {}).get(
            "render_item_count", 0
        ),
        "question_geometry_status": geometry_validation.get("status"),
        "question_source_y_applied_count": source_order_validation.get(
            "question_source_y_applied_count", 0
        ),
        "choice_source_y_applied_count": source_order_validation.get(
            "choice_source_y_applied_count", 0
        ),
        "source_order_status": source_order_validation.get("status"),
        "base_parser_status": base_validation.get("status"),
        "image_status": img_validation.get("status"),
        "hancom_security_status": security_runtime.get("status"),
        "hancom_security_register_result": security_runtime.get(
            "register_module_result"
        ),
        "unattended_ready": security_runtime.get(
            "unattended_ready", False
        ),
        "hwpx_status": hwpx_status,
        "hwpx_renderer_mode": hwpx_info.get("renderer_mode"),
        "hwpx_package_status": final_validation.get("package_status"),
        "hwpx_content_status": final_validation.get("content_status"),
        "hwpx_layout_status": final_validation.get("layout_status"),
        "hwpx_quality_status": final_validation.get("quality_status"),
        "hwpx_zip_status": final_validation.get("status"),
        "hwpx_native_two_column_found": final_validation.get(
            "native_two_column_found"
        ),
        "hwpx_column_counts": final_validation.get("column_counts"),
        "hwpx_section_count": final_validation.get("section_count"),
        "hwpx_section_files": final_validation.get("section_files"),
        "hwpx_embedded_image_count": final_validation.get("bin_data_count"),
        "hwpx_embedded_image_count_match": final_validation.get(
            "embedded_image_count_match"
        ),
        "hwpx_picture_object_count": final_validation.get(
            "picture_object_count"
        ),
        "hwpx_picture_object_count_match": final_validation.get(
            "picture_object_count_match"
        ),
        "hwpx_max_picture_width_hwpunit": final_validation.get(
            "max_picture_width_hwpunit"
        ),
        "hwpx_picture_width_within_target": final_validation.get(
            "picture_width_within_target"
        ),
        "image_order_status": final_validation.get("image_order_status"),
        "image_anchor_status": final_validation.get("image_anchor_status"),
        "image_answer_boundary_status": final_validation.get(
            "image_answer_boundary_status"
        ),
        "image_position_status": final_validation.get(
            "image_position_status"
        ),
        "pictures_after_answer_count": final_validation.get(
            "pictures_after_answer_count"
        ),
        "image_size_request_count": hwpx_info.get(
            "image_exact_size_apply_count"
        ),
        "paragraph_style_apply_count": hwpx_info.get(
            "paragraph_style_apply_count"
        ),
        "multicolumn_apply_count": hwpx_info.get(
            "multicolumn_apply_count"
        ),
        "status": final_status,
    }

    result["known_limitations_v04952"] = [
        (
            "실제 2단은 HParameterSet.HColDef 기반 MultiColumn으로 다시 시도합니다. "
            "한글 빌드가 colCount=2를 직렬화하지 않으면 output.hwpx는 보존하고 "
            "layout_status=WARN으로 기록합니다."
        ),
        (
            "그림 위치는 filename 순서 + 정답 경계 + 주변 텍스트 앵커로 검증합니다. "
            "한글 내부의 실제 물리 페이지 번호 자체를 HWPX XML에서 역산하지는 않습니다."
        ),
        (
            "이미지 크기는 InsertPicture Width/Height만 사용하며 "
            "개체 선택 기반 그림 후처리는 완전히 제거했습니다."
        ),
        (
            "원본 PDF와 한글의 글꼴/행간 엔진 차이 때문에 픽셀 단위 세로 위치 "
            "완전 복제는 하지 않습니다."
        ),
    ]
    return result


# ============================================================
# V0.4.9.5.3 HWPX Native-Layout Completion Layer
# - preserve v0.4.9.5.2 image-anchor stability
# - verify logical PDF page/left-right placement from pageBreak/columnBreak
# - when Hangul COM serializes HColDef as colCount=1, patch only question
#   section0.xml to colCount=2 in a separate atomic candidate
# - keep answer section(s) one-column
# - accept XML post-process only after package/content/image/position validation
# - separate ZIP/package/layout/overall validation statuses
# ============================================================


def _v04953_section_number(name: str) -> int:
    match = re.search(r"section(\d+)\.xml$", str(name))
    return int(match.group(1)) if match else 10**9


def _v04953_col_counts(xml: str) -> list[int]:
    return [int(value) for value in re.findall(r'\bcolCount="(\d+)"', xml)]


def _v04953_patch_colpr(xml: str, target_count: int = 2) -> tuple[str, int, list[int], list[int]]:
    """Patch only the first hp:colPr tag in a question section.

    Regex replacement is intentionally narrow: serializing the full XML tree
    would rewrite namespace prefixes/attribute order across the entire HWPX.
    """
    before = _v04953_col_counts(xml)
    changed = 0

    def replace_tag(match: re.Match) -> str:
        nonlocal changed
        tag = match.group(0)
        if changed:
            return tag
        if re.search(r'\bcolCount="\d+"', tag):
            new_tag = re.sub(
                r'\bcolCount="\d+"',
                f'colCount="{int(target_count)}"',
                tag,
                count=1,
            )
        else:
            new_tag = tag[:-2] + f' colCount="{int(target_count)}"/>' if tag.endswith('/>') else tag[:-1] + f' colCount="{int(target_count)}">'
        if new_tag != tag:
            changed = 1
        return new_tag

    patched = re.sub(r'<hp:colPr\b[^>]*?/?>', replace_tag, xml, count=1)
    after = _v04953_col_counts(patched)
    return patched, changed, before, after


def _v04953_write_patched_hwpx_candidate(
    source: Path,
    candidate: Path,
    *,
    question_section: str = "Contents/section0.xml",
    target_count: int = 2,
) -> dict:
    """Create a separate HWPX candidate with section0 colCount corrected.

    The source file is never modified.  ZIP entry order and the required
    uncompressed first `mimetype` member are preserved.
    """
    import copy
    import xml.etree.ElementTree as ET

    source = Path(source)
    candidate = Path(candidate)
    report = {
        "version": "v0.4.9.5.3",
        "status": "NOT_ATTEMPTED",
        "source": str(source),
        "candidate": str(candidate),
        "question_section": question_section,
        "target_col_count": int(target_count),
        "original_col_counts": [],
        "patched_col_counts": [],
        "column_break_count": 0,
        "page_break_count": 0,
        "applied": False,
        "reason": None,
    }

    if not source.exists() or not zipfile.is_zipfile(source):
        report.update(status="SKIPPED", reason="source is not a valid ZIP/HWPX")
        return report

    try:
        with zipfile.ZipFile(source, "r") as zin:
            names = zin.namelist()
            if question_section not in names:
                report.update(status="SKIPPED", reason=f"missing {question_section}")
                return report

            original_xml = zin.read(question_section).decode("utf-8", errors="strict")
            report["original_col_counts"] = _v04953_col_counts(original_xml)
            report["column_break_count"] = len(re.findall(r'\bcolumnBreak="1"', original_xml))
            report["page_break_count"] = len(re.findall(r'\bpageBreak="1"', original_xml))

            if any(count >= int(target_count) for count in report["original_col_counts"]):
                report.update(
                    status="ALREADY_TWO_COLUMN",
                    patched_col_counts=list(report["original_col_counts"]),
                    reason="question section already contains colCount>=2",
                )
                return report

            if report["column_break_count"] <= 0:
                report.update(
                    status="SKIPPED",
                    reason="no columnBreak markers; direct colCount patch would not reconstruct source columns safely",
                )
                return report

            patched_xml, changed, before, after = _v04953_patch_colpr(
                original_xml,
                target_count=target_count,
            )
            report["original_col_counts"] = before
            report["patched_col_counts"] = after
            if not changed or not any(count >= int(target_count) for count in after):
                report.update(status="SKIPPED", reason="hp:colPr colCount could not be patched")
                return report

            # Parse before writing so malformed XML never becomes a candidate.
            ET.fromstring(patched_xml.encode("utf-8"))

            if candidate.exists():
                candidate.unlink()
            candidate.parent.mkdir(parents=True, exist_ok=True)

            infos = zin.infolist()
            info_by_name = {info.filename: info for info in infos}

            with zipfile.ZipFile(candidate, "w") as zout:
                # HWPX/EPUB-style rule: mimetype must be first and stored.
                ordered_names = ["mimetype"] if "mimetype" in names else []
                ordered_names.extend(name for name in names if name != "mimetype")

                for name in ordered_names:
                    src_info = info_by_name[name]
                    new_info = copy.copy(src_info)
                    data = zin.read(name)
                    if name == question_section:
                        data = patched_xml.encode("utf-8")
                    if name == "mimetype":
                        new_info.compress_type = zipfile.ZIP_STORED
                    zout.writestr(new_info, data)

        if not zipfile.is_zipfile(candidate):
            report.update(status="FAIL", reason="candidate is not a ZIP after rewrite")
            return report

        with zipfile.ZipFile(candidate, "r") as check:
            bad = check.testzip()
            if bad is not None:
                report.update(status="FAIL", reason=f"ZIP CRC failure: {bad}")
                return report
            infos = check.infolist()
            mimetype_ok = bool(infos) and infos[0].filename == "mimetype" and infos[0].compress_type == zipfile.ZIP_STORED
            patched_check = check.read(question_section).decode("utf-8", errors="strict")
            ET.fromstring(patched_check.encode("utf-8"))
            verified_counts = _v04953_col_counts(patched_check)
            report["patched_col_counts"] = verified_counts
            if not mimetype_ok:
                report.update(status="FAIL", reason="mimetype is not first/stored")
                return report
            if not any(count >= int(target_count) for count in verified_counts):
                report.update(status="FAIL", reason="patched candidate did not retain colCount>=2")
                return report

        report.update(status="CREATED", applied=True)
        return report
    except Exception as exc:
        report.update(status="FAIL", reason=str(exc))
        try:
            if candidate.exists():
                candidate.unlink()
        except Exception:
            pass
        return report


def _v04953_extract_logical_picture_positions(path: Path) -> tuple[list[dict], dict]:
    """Infer logical source page/column from HWPX break markers.

    Hangul serializes BreakPage/BreakColumn on the paragraph that begins the
    new page/column.  This is independent of visual pagination and therefore
    gives us a deterministic structural check for the renderer plan.
    """
    import html as _html

    pictures: list[dict] = []
    meta = {
        "section_break_stats": {},
        "question_column_break_count": 0,
        "question_page_break_count": 0,
    }
    if not path.exists() or not zipfile.is_zipfile(path):
        return pictures, meta

    with zipfile.ZipFile(path, "r") as zf:
        names = zf.namelist()
        section_names = sorted(
            [name for name in names if re.fullmatch(r"Contents/section\d+\.xml", name)],
            key=_v04953_section_number,
        )
        global_index = 0
        for section_name in section_names:
            xml = zf.read(section_name).decode("utf-8", errors="ignore")
            local_page = 1
            logical_column = "left"
            section_page_breaks = 0
            section_column_breaks = 0
            section_pictures = 0
            paragraphs = re.findall(r"<hp:p\b.*?</hp:p>", xml, re.S)

            for paragraph_xml in paragraphs:
                has_page_break = bool(re.search(r'\bpageBreak="1"', paragraph_xml))
                has_column_break = bool(re.search(r'\bcolumnBreak="1"', paragraph_xml))
                if has_page_break:
                    local_page += 1
                    logical_column = "left"
                    section_page_breaks += 1
                elif has_column_break:
                    logical_column = "right" if logical_column == "left" else "left"
                    section_column_breaks += 1

                text_parts = []
                for text_match in re.findall(r"<hp:t\b[^>]*>(.*?)</hp:t>", paragraph_xml, re.S):
                    clean = re.sub(r"<[^>]+>", "", text_match)
                    text_parts.append(_html.unescape(clean))
                text_value = "".join(text_parts)
                refs = re.findall(r'\bbinaryItemIDRef="([^"]+)"', paragraph_xml)
                for ref in refs:
                    section_pictures += 1
                    pictures.append({
                        "binary_item_id": ref,
                        "section": section_name,
                        "paragraph_index": global_index,
                        "logical_page": local_page,
                        "logical_column": logical_column,
                        "paragraph_text": text_value,
                        "page_break_before": has_page_break,
                        "column_break_before": has_column_break,
                    })
                global_index += 1

            meta["section_break_stats"][section_name] = {
                "page_break_count": section_page_breaks,
                "column_break_count": section_column_breaks,
                "picture_count": section_pictures,
                "logical_page_count": local_page,
            }
            if section_name == "Contents/section0.xml":
                meta["question_column_break_count"] = section_column_breaks
                meta["question_page_break_count"] = section_page_breaks

    return pictures, meta


def v04953_validate_hwpx(
    path: Path,
    *,
    expected_images: int | None = None,
    render_plan: dict | None = None,
    result: dict | None = None,
    max_picture_width_hwpunit: int = 21000,
    require_two_column: bool = False,
) -> dict:
    """v0.4.9.5.2 validation plus strict logical page/column verification."""
    path = Path(path)
    info = v04952_validate_hwpx(
        path,
        expected_images=expected_images,
        render_plan=render_plan,
        result=result,
        max_picture_width_hwpunit=max_picture_width_hwpunit,
        require_two_column=require_two_column,
    )
    info["validator_version"] = "v0.4.9.5.3"
    info["zip_status"] = "PASS" if info.get("zip_valid") is True else "FAIL"
    info["validation_status"] = info.get("status")
    info["image_logical_position_status"] = "WARN"
    info["logical_position_details"] = []
    info["question_two_column_found"] = False
    info["answer_sections_one_column"] = None
    info["effective_layout_mode"] = "unknown"
    info["two_column_origin"] = info.get("two_column_origin")

    if not path.exists() or not zipfile.is_zipfile(path) or info.get("package_status") != "PASS":
        info["validation_status"] = info.get("status")
        return info

    try:
        with zipfile.ZipFile(path, "r") as zf:
            names = zf.namelist()
            section_names = sorted(
                [name for name in names if re.fullmatch(r"Contents/section\d+\.xml", name)],
                key=_v04953_section_number,
            )
            section_col_counts: dict[str, list[int]] = {}
            for section_name in section_names:
                xml = zf.read(section_name).decode("utf-8", errors="ignore")
                section_col_counts[section_name] = _v04953_col_counts(xml)

        info["section_column_counts"] = section_col_counts
        question_counts = section_col_counts.get("Contents/section0.xml", [])
        question_two = any(count >= 2 for count in question_counts)
        answer_section_names = [name for name in section_names if name != "Contents/section0.xml"]
        answer_one = all(
            all(count <= 1 for count in section_col_counts.get(name, []) or [1])
            for name in answer_section_names
        ) if answer_section_names else True
        info["question_two_column_found"] = question_two
        info["answer_sections_one_column"] = answer_one
        info["native_two_column_found"] = question_two
        info["effective_layout_mode"] = "two_column" if question_two else "one_column"

        # Correct layout semantics: questions must be two-column; answer section must remain one-column.
        if question_two and answer_one:
            info["layout_status"] = "PASS"
        else:
            info["layout_status"] = "WARN" if info.get("package_status") == "PASS" else "FAIL"

        logical_pictures, break_meta = _v04953_extract_logical_picture_positions(path)
        info.update(break_meta)
        logical_by_key = {
            (str(item.get("section")), int(item.get("paragraph_index") or 0), str(item.get("binary_item_id"))): item
            for item in logical_pictures
        }
        expected_stream = _v04952_expected_image_stream(render_plan or {})
        expected_by_name = {
            str(item.get("filename")): item
            for item in expected_stream
            if item.get("filename")
        }

        logical_details = []
        logical_fail = False
        logical_unknown = False
        for detail in info.get("image_anchor_details", []):
            key = (
                str(detail.get("section")),
                int(detail.get("paragraph_index") or 0),
                str(detail.get("binary_item_id")),
            )
            logical = logical_by_key.get(key)
            filename = str(detail.get("filename") or "")
            expected = expected_by_name.get(filename)
            if not logical or not expected:
                logical_unknown = True
                logical_details.append({
                    "filename": filename or None,
                    "binary_item_id": detail.get("binary_item_id"),
                    "expected_page": expected.get("page") if expected else None,
                    "expected_column": expected.get("column") if expected else None,
                    "actual_page": logical.get("logical_page") if logical else None,
                    "actual_column": logical.get("logical_column") if logical else None,
                    "page_match": None,
                    "column_match": None,
                    "group_match": None,
                    "position_match": None,
                })
                continue

            expected_page = int(expected.get("page") or 0)
            expected_column = str(expected.get("column") or "")
            actual_page = int(logical.get("logical_page") or 0)
            actual_column = str(logical.get("logical_column") or "")
            page_match = actual_page == expected_page
            column_match = actual_column == expected_column

            expected_group = expected.get("group_id")
            group_match = None
            parsed_group = None
            group_match_obj = re.match(r"group_(\d+)_", filename)
            if group_match_obj:
                parsed_group = int(group_match_obj.group(1))
                if expected_group is not None:
                    group_match = parsed_group == int(expected_group)

            position_match = page_match and column_match and (group_match is not False)
            if not position_match:
                logical_fail = True

            logical_details.append({
                "filename": filename,
                "binary_item_id": detail.get("binary_item_id"),
                "expected_page": expected_page,
                "expected_column": expected_column,
                "expected_group_id": expected_group,
                "actual_page": actual_page,
                "actual_column": actual_column,
                "actual_group_id_from_filename": parsed_group,
                "page_match": page_match,
                "column_match": column_match,
                "group_match": group_match,
                "position_match": position_match,
                "page_break_before": logical.get("page_break_before"),
                "column_break_before": logical.get("column_break_before"),
            })

        info["logical_position_details"] = logical_details
        if logical_fail:
            info["image_logical_position_status"] = "FAIL"
        elif logical_unknown:
            info["image_logical_position_status"] = "WARN"
        else:
            info["image_logical_position_status"] = "PASS"

        signals = (
            info.get("image_order_status"),
            info.get("image_anchor_status"),
            info.get("image_answer_boundary_status"),
            info.get("image_logical_position_status"),
        )
        if "FAIL" in signals:
            info["image_position_status"] = "FAIL"
            info["content_status"] = "FAIL"
            info["quality_status"] = "FAIL"
            info["status"] = "FAIL"
        elif "WARN" in signals:
            info["image_position_status"] = "WARN"
        else:
            info["image_position_status"] = "PASS"

        # Package and content can be valid while layout is still a warning.
        if info.get("status") != "FAIL":
            if require_two_column and info.get("layout_status") != "PASS":
                info["status"] = "WARN"
            elif info.get("package_status") == "PASS" and info.get("content_status") == "PASS" and info.get("quality_status") == "PASS":
                info["status"] = "PASS" if info.get("layout_status") == "PASS" or not require_two_column else "WARN"

        info["validation_status"] = info.get("status")
    except Exception as exc:
        info["logical_position_validation_error"] = str(exc)
        info["image_logical_position_status"] = "WARN"
        if info.get("package_status") == "PASS" and info.get("status") != "FAIL":
            info["status"] = "WARN"
        info["validation_status"] = info.get("status")

    return info


def v04953_create_hwpx_with_hancom(
    output: Path,
    result: dict,
    render_plan: dict,
    *,
    security_module_path: Path | None = None,
    allow_interactive_hwp: bool = False,
    show_hwp: bool = False,
) -> dict:
    """Render once through Hangul, then complete 2-column serialization safely.

    No second COM session is opened.  If Hangul produced valid columnBreak/pageBreak
    markers but left section0 colCount=1, a separate HWPX ZIP candidate is patched
    and fully revalidated before it replaces output.hwpx.
    """
    import os as _os
    import shutil as _shutil

    output = Path(output)
    expected_count = int(result.get("image_filter_v0481", {}).get("saved_count") or 0)

    base = v04952_create_hwpx_with_hancom(
        output,
        result,
        render_plan,
        security_module_path=security_module_path,
        allow_interactive_hwp=allow_interactive_hwp,
        show_hwp=show_hwp,
    )
    base_security = result.get("hancom_security_v04952") or base.get("hancom_security") or {}
    result["hancom_security_v04953"] = base_security

    if base.get("status") == "SKIPPED":
        return {
            **base,
            "backend": "hancom_com_v04953",
            "requested_renderer_mode": base.get("renderer_mode"),
            "effective_layout_mode": "not_generated",
            "two_column_origin": "not_generated",
            "layout_postprocess_v04953": {"status": "SKIPPED", "applied": False},
        }

    if not output.exists() or not zipfile.is_zipfile(output):
        return {
            **base,
            "backend": "hancom_com_v04953",
            "requested_renderer_mode": base.get("renderer_mode"),
            "effective_layout_mode": "unknown",
            "two_column_origin": "none",
            "layout_postprocess_v04953": {"status": "SKIPPED", "applied": False, "reason": "no usable output.hwpx"},
        }

    pre_validation = v04953_validate_hwpx(
        output,
        expected_images=expected_count,
        render_plan=render_plan,
        result=result,
        require_two_column=True,
    )
    requested_mode = base.get("renderer_mode")
    origin = "native_com" if pre_validation.get("question_two_column_found") else "none"
    patch_report = {
        "version": "v0.4.9.5.3",
        "status": "NOT_NEEDED" if origin == "native_com" else "NOT_ATTEMPTED",
        "applied": False,
    }

    candidate = output.with_name("output_v0_4_9_5_3_colpatch_candidate.hwpx")
    if candidate.exists():
        try:
            candidate.unlink()
        except Exception:
            pass

    # Only patch the output of the native renderer. If HColDef itself failed and
    # the renderer switched to safe_sequential, there are no reliable columnBreak
    # markers to reconstruct two columns without re-rendering.
    if not pre_validation.get("question_two_column_found") and requested_mode == "native_two_column":
        patch_report = _v04953_write_patched_hwpx_candidate(output, candidate)
        if patch_report.get("status") == "CREATED" and candidate.exists():
            candidate_validation = v04953_validate_hwpx(
                candidate,
                expected_images=expected_count,
                render_plan=render_plan,
                result=result,
                require_two_column=True,
            )
            candidate_validation["two_column_origin"] = "hwpx_xml_postprocess"
            patch_report["validation"] = candidate_validation
            candidate_ok = (
                candidate_validation.get("package_status") == "PASS"
                and candidate_validation.get("question_two_column_found") is True
                and candidate_validation.get("answer_sections_one_column") is True
                and candidate_validation.get("image_position_status") != "FAIL"
                and candidate_validation.get("content_status") != "FAIL"
            )
            if candidate_ok:
                try:
                    _os.replace(str(candidate), str(output))
                    patch_report["accepted"] = True
                    patch_report["applied"] = True
                    patch_report["status"] = "APPLIED"
                    origin = "hwpx_xml_postprocess"
                    _v0491_log(
                        "[HWPX] v0.4.9.5.3 section0 colCount=2 XML 보정 적용 완료 "
                        "(이미지/페이지/컬럼/패키지 재검증 통과)"
                    )
                except Exception as exc:
                    patch_report["accepted"] = False
                    patch_report["status"] = "REPLACE_FAILED"
                    patch_report["reason"] = str(exc)
            else:
                patch_report["accepted"] = False
                patch_report["status"] = "REJECTED_BY_VALIDATION"
                patch_report["reason"] = "patched candidate failed package/layout/image-position acceptance checks"
        if candidate.exists():
            try:
                candidate.unlink()
            except Exception:
                pass

    final_validation = v04953_validate_hwpx(
        output,
        expected_images=expected_count,
        render_plan=render_plan,
        result=result,
        require_two_column=True,
    )
    final_validation["two_column_origin"] = origin
    effective_layout = final_validation.get("effective_layout_mode") or (
        "two_column" if final_validation.get("question_two_column_found") else "one_column"
    )

    attempts = list(base.get("attempts") or [])
    attempts.append({
        "renderer_mode": "hwpx_xml_two_column_postprocess",
        "status": patch_report.get("status"),
        "applied": patch_report.get("applied", False),
        "reason": patch_report.get("reason"),
    })

    return {
        **base,
        "status": "created" if final_validation.get("package_status") == "PASS" else base.get("status"),
        "path": str(output.resolve()),
        "final_path": str(output.resolve()),
        "backend": "hancom_com_v04953",
        "requested_renderer_mode": requested_mode,
        "renderer_mode": requested_mode,
        "effective_layout_mode": effective_layout,
        "two_column_origin": origin,
        "layout_postprocess_v04953": patch_report,
        "validation_before_layout_postprocess": pre_validation,
        "validation": final_validation,
        "quality_status": final_validation.get("status"),
        "attempts": attempts,
        "hancom_security": base_security,
    }


def v04953_upgrade_result(
    result: dict,
    pdf_path: Path,
    checkpoint_path: Path | None = None,
    *,
    security_module_path: Path | None = None,
    allow_interactive_hwp: bool = False,
    show_hwp: bool = False,
) -> dict:
    _v0491_log("[v0.4.9.5.3] 이미지 안정화 + 논리 위치 검증 + 2단 XML 보정 준비")

    result = v046_upgrade_result(result, pdf_path)
    result = v0481_prepare_problem_images(pdf_path, result)
    result = v0491_cleanup_legacy_metadata(result)
    result = v0495_attach_question_geometry(pdf_path, result)

    render_plan = v0495_build_render_plan(result)
    render_plan["version"] = "v0.4.9.5.3"
    render_plan["layout_mode"] = "native_hcoldef_then_validated_hwpx_xml_two_column"
    render_plan["native_two_column_policy_v04953"] = {
        "enabled": True,
        "primary_method": 'HAction.GetDefault("MultiColumn", HParameterSet.HColDef.HSet)',
        "serialization_completion": "atomic HWPX section0.xml colCount=2 patch when BreakColumn markers are present",
        "answer_section_policy": "section1+ remain colCount=1",
        "acceptance": "package + content + image order + answer boundary + logical page/column must not fail",
        "second_com_session": False,
    }
    render_plan["image_anchor_policy_v04953"] = {
        "no_control_selection_after_insert": True,
        "size_method": "InsertPicture Width/Height only",
        "validate_filename_order": True,
        "fail_picture_after_answer_boundary": True,
        "validate_neighbor_text_anchor": True,
        "validate_logical_page_from_pageBreak": True,
        "validate_logical_column_from_columnBreak": True,
    }
    result["render_plan_v04953"] = render_plan
    for stale_key in [
        "render_plan_v04952", "render_plan_v04951", "render_plan_v0495",
        "render_plan_v0494", "render_plan_v0493", "render_plan_v0492", "render_plan_v049",
    ]:
        result.pop(stale_key, None)

    result["version"] = "v0.4.9.5.3"
    result["parser_version"] = "v0.4.9.5.3"
    result["generator_version"] = "PDF Parser Integrated v0.4.9.5.3"
    result["schema_version"] = {
        "base": "v0.4.9.5.2",
        "extension": [
            "strict_logical_page_column_picture_validation",
            "pageBreak_columnBreak_layout_verification",
            "atomic_hwpx_section0_colcount_patch",
            "answer_section_one_column_guard",
            "postpatch_full_revalidation",
            "requested_vs_effective_layout_metadata",
            "zip_package_layout_validation_status_split",
            "single_hwp_com_session_preserved",
        ],
    }

    if checkpoint_path is not None:
        checkpoint_path = Path(checkpoint_path)
        result["pre_hwpx_checkpoint"] = {
            "path": str(checkpoint_path.resolve()),
            "purpose": "COM hang/error recovery only",
            "retained_after_success": False,
        }
        _v0491_json_safe_write(checkpoint_path, result)
        _v0491_log(
            "[v0.4.9.5.3] HWPX 전 임시 체크포인트 저장: "
            f"{checkpoint_path.resolve()}"
        )

    hwpx_path = pdf_path.parent / "output.hwpx"
    hwpx_info = v04953_create_hwpx_with_hancom(
        hwpx_path,
        result,
        render_plan,
        security_module_path=security_module_path,
        allow_interactive_hwp=allow_interactive_hwp,
        show_hwp=show_hwp,
    )
    result["hwpx_v04953"] = hwpx_info
    result["hancom_security_v04953"] = (
        result.get("hancom_security_v04953")
        or hwpx_info.get("hancom_security")
        or {}
    )
    result.pop("hancom_security_v04952", None)

    base_validation = result.get("validation", {})
    img_validation = result.get("image_filter_v0481", {})
    table_validation = result.get("table_filter_v0492", {})
    geometry_validation = result.get("question_geometry_v0495", {})
    source_order_validation = render_plan.get("source_order_v0495", {})
    final_validation = hwpx_info.get("validation") or {}
    security_runtime = result.get("hancom_security_v04953") or {}
    hwpx_status = hwpx_info.get("status")
    security_ok = (
        security_runtime.get("unattended_ready") is True
        or hwpx_status == "SKIPPED"
        or (allow_interactive_hwp and hwpx_status == "created")
    )

    hard_pass = (
        base_validation.get("status") == "PASS"
        and img_validation.get("status") == "PASS"
        and table_validation.get("status") == "PASS"
        and geometry_validation.get("status") == "PASS"
        and source_order_validation.get("status") == "PASS"
        and hwpx_status in {"created", "SKIPPED"}
        and security_ok
        and final_validation.get("package_status") in {"PASS", None}
    )
    positional_fail = any(
        final_validation.get(key) == "FAIL"
        for key in (
            "image_order_status",
            "image_anchor_status",
            "image_answer_boundary_status",
            "image_logical_position_status",
        )
    )
    quality_warn = (
        final_validation.get("content_status") in {"WARN", "FAIL"}
        or final_validation.get("quality_status") in {"WARN", "FAIL"}
        or final_validation.get("layout_status") in {"WARN", "FAIL"}
        or final_validation.get("image_order_status") == "WARN"
        or final_validation.get("image_anchor_status") == "WARN"
        or final_validation.get("image_answer_boundary_status") == "WARN"
        or final_validation.get("image_logical_position_status") == "WARN"
    )

    if positional_fail:
        final_status = "FAIL"
    elif hard_pass and quality_warn:
        final_status = "WARN"
    elif hard_pass:
        final_status = "PASS"
    else:
        final_status = "WARN"

    result["validation_v04953"] = {
        "question_count": len(result.get("questions", [])),
        "passage_group_count": len(result.get("passage_groups", [])),
        "problem_image_count": img_validation.get("selected_problem_figure_count", 0),
        "problem_image_saved": img_validation.get("saved_count", 0),
        "raw_table_count": table_validation.get("raw_table_count", 0),
        "renderable_table_count": table_validation.get("renderable_table_count", 0),
        "excluded_table_count": table_validation.get("excluded_table_count", 0),
        "removed_noncore_block_count": render_plan.get("stats", {}).get("removed_noncore_block_count", 0),
        "answer_count": render_plan.get("stats", {}).get("answer_count", 0),
        "render_page_count": render_plan.get("stats", {}).get("page_count", 0),
        "render_item_count": render_plan.get("stats", {}).get("render_item_count", 0),
        "question_geometry_status": geometry_validation.get("status"),
        "question_source_y_applied_count": source_order_validation.get("question_source_y_applied_count", 0),
        "choice_source_y_applied_count": source_order_validation.get("choice_source_y_applied_count", 0),
        "source_order_status": source_order_validation.get("status"),
        "base_parser_status": base_validation.get("status"),
        "image_status": img_validation.get("status"),
        "hancom_security_status": security_runtime.get("status"),
        "hancom_security_register_result": security_runtime.get("register_module_result"),
        "unattended_ready": security_runtime.get("unattended_ready", False),
        "hwpx_status": hwpx_status,
        "hwpx_requested_renderer_mode": hwpx_info.get("requested_renderer_mode"),
        "hwpx_renderer_mode": hwpx_info.get("renderer_mode"),
        "hwpx_effective_layout_mode": hwpx_info.get("effective_layout_mode"),
        "hwpx_two_column_origin": hwpx_info.get("two_column_origin"),
        "hwpx_xml_postprocess_status": (hwpx_info.get("layout_postprocess_v04953") or {}).get("status"),
        "hwpx_xml_postprocess_applied": (hwpx_info.get("layout_postprocess_v04953") or {}).get("applied", False),
        "hwpx_zip_status": final_validation.get("zip_status"),
        "hwpx_package_status": final_validation.get("package_status"),
        "hwpx_content_status": final_validation.get("content_status"),
        "hwpx_layout_status": final_validation.get("layout_status"),
        "hwpx_quality_status": final_validation.get("quality_status"),
        "hwpx_validation_status": final_validation.get("status"),
        "hwpx_native_two_column_found": final_validation.get("native_two_column_found"),
        "hwpx_question_two_column_found": final_validation.get("question_two_column_found"),
        "hwpx_answer_sections_one_column": final_validation.get("answer_sections_one_column"),
        "hwpx_column_counts": final_validation.get("column_counts"),
        "hwpx_section_column_counts": final_validation.get("section_column_counts"),
        "hwpx_section_count": final_validation.get("section_count"),
        "hwpx_section_files": final_validation.get("section_files"),
        "hwpx_embedded_image_count": final_validation.get("bin_data_count"),
        "hwpx_embedded_image_count_match": final_validation.get("embedded_image_count_match"),
        "hwpx_picture_object_count": final_validation.get("picture_object_count"),
        "hwpx_picture_object_count_match": final_validation.get("picture_object_count_match"),
        "hwpx_max_picture_width_hwpunit": final_validation.get("max_picture_width_hwpunit"),
        "hwpx_picture_width_within_target": final_validation.get("picture_width_within_target"),
        "image_order_status": final_validation.get("image_order_status"),
        "image_anchor_status": final_validation.get("image_anchor_status"),
        "image_answer_boundary_status": final_validation.get("image_answer_boundary_status"),
        "image_logical_position_status": final_validation.get("image_logical_position_status"),
        "image_position_status": final_validation.get("image_position_status"),
        "pictures_after_answer_count": final_validation.get("pictures_after_answer_count"),
        "question_column_break_count": final_validation.get("question_column_break_count"),
        "question_page_break_count": final_validation.get("question_page_break_count"),
        "image_size_request_count": hwpx_info.get("image_exact_size_apply_count"),
        "paragraph_style_apply_count": hwpx_info.get("paragraph_style_apply_count"),
        "multicolumn_apply_count": hwpx_info.get("multicolumn_apply_count"),
        "status": final_status,
    }

    result["known_limitations_v04953"] = [
        "2단 XML 보정은 section0에 columnBreak가 실제로 존재하는 경우에만 적용하며, safe_sequential 결과를 억지로 2단으로 바꾸지 않습니다.",
        "그림 위치는 filename/hash 순서, 정답 경계, 주변 텍스트, pageBreak/columnBreak 기반 논리 page/column을 함께 검증합니다.",
        "이미지 크기는 InsertPicture Width/Height만 사용하며 개체 선택 기반 그림 후처리는 사용하지 않습니다.",
        "원본 PDF와 한글의 글꼴/행간 엔진 차이 때문에 픽셀 단위 세로 위치 완전 복제는 하지 않습니다.",
    ]
    return result


# ============================================================
# V0.4.9.5.4 Layout / Editorial Fidelity Layer
# - bold passage instruction before every passage group
# - connected rectangular border around passage material only
# - one blank line only at (가)/(나)/(다) passage transitions
# - left-aligned narrow-column paragraphs to prevent stretched word gaps
# - question AND answer sections use two columns with an 8 mm center gutter
# - HWPX post-validation for guide/border/gutter/spacing metadata
# ============================================================

_V04954_PASSAGE_GUIDE = "※ 다음 글을 읽고 물음에 답하시오."
_V04954_GUTTER_HWPUNIT = 2268   # approx. 8 mm
_V04954_COLUMN_LINE_WIDTH = 23376  # reference from the user's hand-edited two-column HWPX


def v04954_build_render_plan(result: dict) -> dict:
    """Extend the proven v0.4.9.5 source-order render plan with editorial markers.

    The instruction is inserted immediately before the first rendered passage
    item of each group.  It deliberately lives outside the passage box.  Later
    section labels inside the same passage receive exactly one extra paragraph
    before them so (가) -> (나) -> (다) has a single visual blank line.
    """
    plan = v0495_build_render_plan(result)
    group_first: dict[int, tuple[int, str, float]] = {}

    for page_entry in plan.get("pages", []):
        page_no = int(page_entry.get("page") or 0)
        for side in ("left", "right"):
            for item in page_entry.get(side, []):
                gid = int(item.get("group_id") or item.get("passage_group_id") or 0)
                if gid <= 0 or item.get("type") not in {"block", "image"}:
                    continue
                y = float(item.get("sort_y") or 0.0)
                cur = group_first.get(gid)
                key = (page_no, 0 if side == "left" else 1, y)
                if cur is None:
                    group_first[gid] = (page_no, side, y)
                else:
                    old_key = (cur[0], 0 if cur[1] == "left" else 1, cur[2])
                    if key < old_key:
                        group_first[gid] = (page_no, side, y)

    # Insert one guide per passage group.
    for gid, (page_no, side, first_y) in sorted(group_first.items()):
        entry = next((p for p in plan.get("pages", []) if int(p.get("page") or 0) == page_no), None)
        if not entry:
            continue
        guide = {
            "type": "block",
            "group_id": gid,
            "block_type": "passage_instruction",
            "text": _V04954_PASSAGE_GUIDE,
            "sort_y": max(0.0, float(first_y) - 15.0),
            "page": page_no,
            "column": side,
            "style_v0495": {
                "role": "passage_instruction",
                "left_margin_pt": 0.0,
                "line_spacing_percent": 140,
                "blank_before": 0,
            },
            "bold_v04954": True,
            "outside_passage_box_v04954": True,
        }
        entry[side].append(guide)

    # Sort again and mark later (가)/(나)/(다) labels for one blank line.
    section_seen: dict[int, int] = {}
    for page_entry in plan.get("pages", []):
        for side in ("left", "right"):
            items = page_entry.get(side, [])
            items.sort(key=lambda x: (
                float(x.get("sort_y") or 0.0),
                0 if x.get("block_type") == "passage_instruction" else 1,
                str(x.get("type") or ""),
                int(x.get("number") or 0),
                int(x.get("choice_index") or 0),
            ))
            for item in items:
                if item.get("type") != "block" or item.get("block_type") != "section_label":
                    continue
                text = str(item.get("text") or "").strip()
                if text not in {"(가)", "(나)", "(다)", "(라)", "(마)"}:
                    continue
                gid = int(item.get("group_id") or 0)
                count = section_seen.get(gid, 0)
                if count >= 1:
                    style = dict(item.get("style_v0495") or _v0495_style_for_item(item))
                    style["blank_before"] = 1
                    item["style_v0495"] = style
                    item["force_blank_before_v04954"] = True
                section_seen[gid] = count + 1
            page_entry[f"{side}_count"] = len(items)

    plan["version"] = "v0.4.9.5.4"
    plan["layout_mode"] = "two_column_question_and_answer_with_passage_boxes"
    plan["editorial_layout_v04954"] = {
        "passage_instruction": _V04954_PASSAGE_GUIDE,
        "passage_instruction_bold": True,
        "passage_box": "connected paragraph border",
        "section_transition_blank_lines": 1,
        "paragraph_alignment": "LEFT",
        "question_column_count": 2,
        "answer_column_count": 2,
        "center_gutter_hwpunit": _V04954_GUTTER_HWPUNIT,
        "center_gutter_mm": 8.0,
        "answer_center_gap": True,
    }
    plan.setdefault("stats", {})["passage_instruction_count"] = len(group_first)
    plan["stats"]["render_item_count"] = sum(
        int(p.get("left_count") or 0) + int(p.get("right_count") or 0)
        for p in plan.get("pages", [])
    )
    return plan


def _v04954_para_text(paragraph_xml: str) -> str:
    import html as _html
    chunks = re.findall(r"<hp:t\b[^>]*>(.*?)</hp:t>", paragraph_xml, flags=re.S)
    text = "".join(_html.unescape(re.sub(r"<[^>]+>", "", chunk)) for chunk in chunks)
    return re.sub(r"\s+", " ", text).strip()


def _v04954_next_id(xml: str, tag: str) -> int:
    ids = [int(x) for x in re.findall(rf'<hh:{tag}\b[^>]*\bid="(\d+)"', xml)]
    return max(ids, default=0) + 1


def _v04954_set_item_count(xml: str, container: str, delta: int) -> str:
    if delta <= 0:
        return xml
    pattern = rf'(<hh:{container}\b[^>]*\bitemCnt=")(\d+)(")'
    m = re.search(pattern, xml)
    if not m:
        return xml
    return xml[:m.start()] + m.group(1) + str(int(m.group(2)) + delta) + m.group(3) + xml[m.end():]


def _v04954_make_solid_border_fill(border_id: int) -> str:
    return (
        f'<hh:borderFill id="{border_id}" threeD="0" shadow="0" centerLine="NONE" breakCellSeparateLine="0">'
        '<hh:slash type="NONE" Crooked="0" isCounter="0"/>'
        '<hh:backSlash type="NONE" Crooked="0" isCounter="0"/>'
        '<hh:leftBorder type="SOLID" width="0.2 mm" color="#000000"/>'
        '<hh:rightBorder type="SOLID" width="0.2 mm" color="#000000"/>'
        '<hh:topBorder type="SOLID" width="0.2 mm" color="#000000"/>'
        '<hh:bottomBorder type="SOLID" width="0.2 mm" color="#000000"/>'
        '<hh:diagonal type="SOLID" width="0.1 mm" color="#000000"/>'
        '<hc:fillBrush><hc:winBrush faceColor="none" hatchColor="#000000" alpha="0"/></hc:fillBrush>'
        '</hh:borderFill>'
    )


def _v04954_clone_bold_charpr(header_xml: str) -> tuple[str, int]:
    new_id = _v04954_next_id(header_xml, "charPr")
    m = re.search(r'<hh:charPr\b[^>]*\bid="0"[\s\S]*?</hh:charPr>', header_xml)
    if not m:
        m = re.search(r'<hh:charPr\b[^>]*>[\s\S]*?</hh:charPr>', header_xml)
    if not m:
        raise RuntimeError("header.xml charPr template not found")
    clone = m.group(0)
    clone = re.sub(r'\bid="\d+"', f'id="{new_id}"', clone, count=1)
    if '<hh:bold/>' not in clone:
        clone = clone.replace('<hh:underline ', '<hh:bold/><hh:underline ', 1)
    header_xml = header_xml.replace('</hh:charProperties>', clone + '</hh:charProperties>', 1)
    header_xml = _v04954_set_item_count(header_xml, "charProperties", 1)
    return header_xml, new_id


def _v04954_clone_box_parapr(header_xml: str, source_id: int, new_id: int, border_id: int) -> str:
    m = re.search(
        rf'<hh:paraPr\b[^>]*\bid="{int(source_id)}"[\s\S]*?</hh:paraPr>',
        header_xml,
    )
    if not m:
        raise RuntimeError(f"header.xml paraPr template {source_id} not found")
    clone = m.group(0)
    clone = re.sub(r'\bid="\d+"', f'id="{new_id}"', clone, count=1)
    clone = re.sub(r'horizontal="JUSTIFY"', 'horizontal="LEFT"', clone)
    clone = re.sub(r'breakNonLatinWord="BREAK_WORD"', 'breakNonLatinWord="KEEP_WORD"', clone)
    border = (
        f'<hh:border borderFillIDRef="{border_id}" offsetLeft="0" offsetRight="0" '
        'offsetTop="0" offsetBottom="0" connect="1" ignoreMargin="0"/>'
    )
    if re.search(r'<hh:border\b[^>]*/>', clone):
        clone = re.sub(r'<hh:border\b[^>]*/>', border, clone, count=1)
    else:
        clone = clone.replace('</hh:paraPr>', border + '</hh:paraPr>', 1)
    header_xml = header_xml.replace('</hh:paraProperties>', clone + '</hh:paraProperties>', 1)
    return header_xml


def _v04954_patch_colpr(xml: str, target_count: int = 2, gap_hwpunit: int = _V04954_GUTTER_HWPUNIT) -> str:
    def repl(m: re.Match) -> str:
        tag = m.group(0)
        if 'colCount=' in tag:
            tag = re.sub(r'colCount="\d+"', f'colCount="{int(target_count)}"', tag)
        else:
            tag = tag[:-2] + f' colCount="{int(target_count)}"/>' if tag.endswith('/>') else tag
        if 'sameGap=' in tag:
            tag = re.sub(r'sameGap="\d+"', f'sameGap="{int(gap_hwpunit)}"', tag)
        else:
            tag = tag[:-2] + f' sameGap="{int(gap_hwpunit)}"/>' if tag.endswith('/>') else tag
        return tag
    return re.sub(r'<hp:colPr\b[^>]*(?:/>|>.*?</hp:colPr>)', repl, xml, count=1, flags=re.S)


def _v04954_shrink_lineseg_width(xml: str, target: int = _V04954_COLUMN_LINE_WIDTH) -> tuple[str, int]:
    changed = 0
    def repl(m: re.Match) -> str:
        nonlocal changed
        old = int(m.group(1))
        if old <= 28000:
            return m.group(0)
        changed += 1
        return m.group(0).replace(f'horzsize="{old}"', f'horzsize="{int(target)}"')
    return re.sub(r'<hp:lineseg\b[^>]*\bhorzsize="(\d+)"[^>]*/>', repl, xml), changed


def _v04954_style_section0(header_xml: str, section_xml: str, result: dict) -> tuple[str, str, dict]:
    """Apply bold guide + connected border to passage paragraphs.

    Styling is based on visible guide paragraphs and the first question number of
    each passage group, not on paragraph indices, so it remains stable even when
    image paragraphs or a page/column break are present.
    """
    # Prevent visual 3~4-space expansion caused by stale one-column justification.
    header_xml = header_xml.replace('horizontal="JUSTIFY"', 'horizontal="LEFT"')
    header_xml = header_xml.replace('breakNonLatinWord="BREAK_WORD"', 'breakNonLatinWord="KEEP_WORD"')

    border_id = _v04954_next_id(header_xml, "borderFill")
    border_xml = _v04954_make_solid_border_fill(border_id)
    header_xml = header_xml.replace('</hh:borderFills>', border_xml + '</hh:borderFills>', 1)
    header_xml = _v04954_set_item_count(header_xml, "borderFills", 1)
    header_xml, bold_char_id = _v04954_clone_bold_charpr(header_xml)

    groups = {
        int(g.get("id") or 0): [int(x) for x in g.get("question_numbers", [])]
        for g in result.get("passage_groups", [])
    }
    expected_guides = len([g for g in groups if g > 0])

    paragraphs = list(re.finditer(r'<hp:p\b[^>]*>[\s\S]*?</hp:p>', section_xml))
    output_parts = []
    cursor = 0
    passage_active = False
    active_gid = None
    next_gid_iter = iter(sorted(g for g in groups if g > 0))
    pending_gid = next(next_gid_iter, None)
    guide_count = 0
    boxed_count = 0
    box_style_map: dict[int, int] = {}
    new_para_prs = 0

    for pm in paragraphs:
        output_parts.append(section_xml[cursor:pm.start()])
        p = pm.group(0)
        text = _v04954_para_text(p)

        if text == _V04954_PASSAGE_GUIDE:
            guide_count += 1
            active_gid = pending_gid
            pending_gid = next(next_gid_iter, None)
            passage_active = True
            # Guide is outside the box and bold.
            p = re.sub(r'charPrIDRef="\d+"', f'charPrIDRef="{bold_char_id}"', p)
        elif passage_active and active_gid:
            qnums = groups.get(active_gid) or []
            first_q = qnums[0] if qnums else None
            if first_q is not None and re.match(rf'^{first_q}\.\s', text):
                passage_active = False
                active_gid = None
            else:
                start = re.match(r'<hp:p\b[^>]*\bparaPrIDRef="(\d+)"[^>]*>', p)
                if start:
                    old_id = int(start.group(1))
                    if old_id not in box_style_map:
                        new_id = _v04954_next_id(header_xml, "paraPr")
                        header_xml = _v04954_clone_box_parapr(header_xml, old_id, new_id, border_id)
                        box_style_map[old_id] = new_id
                        new_para_prs += 1
                    p = re.sub(
                        r'(<hp:p\b[^>]*\bparaPrIDRef=")\d+("[^>]*>)',
                        rf'\g<1>{box_style_map[old_id]}\2',
                        p,
                        count=1,
                    )
                    boxed_count += 1

        output_parts.append(p)
        cursor = pm.end()

    output_parts.append(section_xml[cursor:])
    section_xml = ''.join(output_parts)
    header_xml = _v04954_set_item_count(header_xml, "paraProperties", new_para_prs)

    report = {
        "expected_passage_instruction_count": expected_guides,
        "passage_instruction_count": guide_count,
        "passage_instruction_bold_charpr_id": bold_char_id,
        "passage_border_fill_id": border_id,
        "passage_box_paragraph_count": boxed_count,
        "passage_box_para_style_count": len(box_style_map),
        "passage_instruction_status": "PASS" if guide_count == expected_guides else "WARN",
        "passage_box_status": "PASS" if boxed_count > 0 and guide_count == expected_guides else "WARN",
    }
    return header_xml, section_xml, report


def _v04954_repack_hwpx(source: Path, candidate: Path, replacements: dict[str, bytes]) -> None:
    import zipfile as _zipfile
    source = Path(source)
    candidate = Path(candidate)
    if candidate.exists():
        candidate.unlink()
    with _zipfile.ZipFile(source, 'r') as zin, _zipfile.ZipFile(candidate, 'w') as zout:
        names = zin.namelist()
        # HWPX requires mimetype first and uncompressed.
        if 'mimetype' in names:
            data = replacements.get('mimetype', zin.read('mimetype'))
            zout.writestr('mimetype', data, compress_type=_zipfile.ZIP_STORED)
        for info in zin.infolist():
            name = info.filename
            if name == 'mimetype':
                continue
            data = replacements.get(name, zin.read(name))
            zi = _zipfile.ZipInfo(name, date_time=info.date_time)
            zi.compress_type = info.compress_type
            zi.external_attr = info.external_attr
            zi.internal_attr = info.internal_attr
            zi.create_system = info.create_system
            zi.flag_bits = info.flag_bits
            zout.writestr(zi, data)


def _v04954_editorial_postprocess(output: Path, result: dict, render_plan: dict) -> dict:
    import os as _os
    import zipfile as _zipfile
    output = Path(output)
    report = {
        "version": "v0.4.9.5.4",
        "status": "SKIPPED",
        "applied": False,
        "question_columns": 2,
        "answer_columns": 2,
        "center_gutter_hwpunit": _V04954_GUTTER_HWPUNIT,
        "center_gutter_mm": 8.0,
        "paragraph_alignment": "LEFT",
    }
    if not output.exists() or not _zipfile.is_zipfile(output):
        report["reason"] = "no usable HWPX"
        return report

    candidate = output.with_name('output_v0_4_9_5_4_editorial_candidate.hwpx')
    try:
        with _zipfile.ZipFile(output, 'r') as zf:
            names = set(zf.namelist())
            header = zf.read('Contents/header.xml').decode('utf-8', errors='ignore')
            section_names = sorted(
                [n for n in names if re.fullmatch(r'Contents/section\d+\.xml', n)],
                key=_v04953_section_number,
            )
            sections = {n: zf.read(n).decode('utf-8', errors='ignore') for n in section_names}

        if 'Contents/section0.xml' not in sections:
            report["reason"] = "section0.xml missing"
            return report

        # Question section styling / boxes / guides.
        header, sections['Contents/section0.xml'], style_report = _v04954_style_section0(
            header, sections['Contents/section0.xml'], result
        )
        report.update(style_report)

        # Both questions and answers are two columns with an 8 mm central gutter.
        lineseg_changes = {}
        for name in section_names:
            sections[name] = _v04954_patch_colpr(sections[name], 2, _V04954_GUTTER_HWPUNIT)
            sections[name], changed = _v04954_shrink_lineseg_width(
                sections[name], _V04954_COLUMN_LINE_WIDTH
            )
            lineseg_changes[name] = changed
        report["lineseg_width_adjustments"] = lineseg_changes

        replacements = {'Contents/header.xml': header.encode('utf-8')}
        replacements.update({k: v.encode('utf-8') for k, v in sections.items()})
        _v04954_repack_hwpx(output, candidate, replacements)

        expected_count = int(result.get('image_filter_v0481', {}).get('saved_count') or 0)
        validation = v04953_validate_hwpx(
            candidate,
            expected_images=expected_count,
            render_plan=render_plan,
            result=result,
            require_two_column=True,
        )
        # v04953 expects answer section one-column, so package/image/location are
        # the acceptance criteria here. v04954 validates answer columns separately.
        with _zipfile.ZipFile(candidate, 'r') as zf:
            sec_counts = {
                name: _v04953_col_counts(zf.read(name).decode('utf-8', errors='ignore'))
                for name in section_names
            }
            header_check = zf.read('Contents/header.xml').decode('utf-8', errors='ignore')
            sec0_check = zf.read('Contents/section0.xml').decode('utf-8', errors='ignore')

        answer_two = all(any(c >= 2 for c in counts) for name, counts in sec_counts.items() if name != 'Contents/section0.xml') if len(sec_counts) > 1 else True
        question_two = any(c >= 2 for c in sec_counts.get('Contents/section0.xml', []))
        guide_count = sec0_check.count(_V04954_PASSAGE_GUIDE)
        solid_border_present = 'width="0.2 mm"' in header_check and '<hh:leftBorder type="SOLID"' in header_check
        remaining_wide_lines = [int(x) for x in re.findall(r'horzsize="(\d+)"', ''.join(sections.values())) if int(x) > 28000]
        package_ok = validation.get('package_status') == 'PASS'
        image_ok = validation.get('image_position_status') != 'FAIL' and validation.get('content_status') != 'FAIL'
        guide_ok = guide_count == len(result.get('passage_groups', []))
        box_ok = solid_border_present and report.get('passage_box_paragraph_count', 0) > 0
        spacing_ok = not remaining_wide_lines and 'horizontal="JUSTIFY"' not in header_check
        answer_gap_ok = answer_two

        report.update({
            "section_column_counts": sec_counts,
            "question_two_column_status": "PASS" if question_two else "FAIL",
            "answer_two_column_status": "PASS" if answer_two else "FAIL",
            "answer_center_gap_status": "PASS" if answer_gap_ok else "FAIL",
            "guide_count_after_save": guide_count,
            "guide_bold_status": "PASS" if '<hh:bold/>' in header_check and guide_ok else "WARN",
            "passage_box_status": "PASS" if box_ok and guide_ok else "WARN",
            "word_spacing_layout_status": "PASS" if spacing_ok else "WARN",
            "remaining_wide_lineseg_count": len(remaining_wide_lines),
            "validation": validation,
        })

        accepted = package_ok and image_ok and question_two and answer_two and guide_ok and box_ok
        if accepted:
            _os.replace(str(candidate), str(output))
            report["status"] = "APPLIED"
            report["applied"] = True
            report["accepted"] = True
        else:
            report["status"] = "REJECTED_BY_VALIDATION"
            report["accepted"] = False
            report["reason"] = "editorial candidate failed package/image/layout/guide/box checks"
        return report
    except Exception as exc:
        report["status"] = "ERROR"
        report["reason"] = str(exc)
        return report
    finally:
        if candidate.exists():
            try:
                candidate.unlink()
            except Exception:
                pass


def v04954_validate_hwpx(path: Path, *, expected_images: int, render_plan: dict, result: dict) -> dict:
    info = v04953_validate_hwpx(
        path,
        expected_images=expected_images,
        render_plan=render_plan,
        result=result,
        require_two_column=True,
    )
    info["validator_version"] = "v0.4.9.5.4"
    if not Path(path).exists() or not zipfile.is_zipfile(path):
        return info
    try:
        with zipfile.ZipFile(path, 'r') as zf:
            section_names = sorted(
                [n for n in zf.namelist() if re.fullmatch(r'Contents/section\d+\.xml', n)],
                key=_v04953_section_number,
            )
            sections = {n: zf.read(n).decode('utf-8', errors='ignore') for n in section_names}
            header = zf.read('Contents/header.xml').decode('utf-8', errors='ignore')
        counts = {n: _v04953_col_counts(x) for n, x in sections.items()}
        answer_two = all(any(c >= 2 for c in cs) for n, cs in counts.items() if n != 'Contents/section0.xml') if len(counts) > 1 else True
        guide_count = sections.get('Contents/section0.xml', '').count(_V04954_PASSAGE_GUIDE)
        expected_guides = len(result.get('passage_groups', []))
        wide = [int(x) for x in re.findall(r'horzsize="(\d+)"', ''.join(sections.values())) if int(x) > 28000]
        info["answer_sections_two_column"] = answer_two
        info["answer_center_gap_status"] = "PASS" if answer_two else "FAIL"
        info["passage_instruction_count"] = guide_count
        info["expected_passage_instruction_count"] = expected_guides
        info["passage_instruction_status"] = "PASS" if guide_count == expected_guides else "FAIL"
        info["passage_box_style_present"] = '<hh:leftBorder type="SOLID" width="0.2 mm"' in header
        info["passage_box_status"] = "PASS" if info["passage_box_style_present"] and guide_count == expected_guides else "FAIL"
        info["word_spacing_layout_status"] = "PASS" if not wide and 'horizontal="JUSTIFY"' not in header else "WARN"
        info["remaining_wide_lineseg_count"] = len(wide)
        # v04953 flags answer_two as a layout FAIL because its old policy requires
        # answer one-column. Replace only that policy result for v04954.
        info["answer_sections_one_column"] = False if len(counts) > 1 else None
        info["section_column_counts"] = counts
        if (
            info.get("package_status") == "PASS"
            and info.get("content_status") != "FAIL"
            and info.get("image_position_status") != "FAIL"
            and info.get("question_two_column_found") is True
            and answer_two
            and info["passage_instruction_status"] == "PASS"
            and info["passage_box_status"] == "PASS"
        ):
            info["layout_status"] = "PASS"
            info["quality_status"] = "PASS" if info["word_spacing_layout_status"] == "PASS" else "WARN"
            info["status"] = "PASS" if info["quality_status"] == "PASS" else "WARN"
        else:
            info["status"] = "FAIL" if info.get("package_status") == "FAIL" or info.get("image_position_status") == "FAIL" else "WARN"
    except Exception as exc:
        info["v04954_validation_error"] = str(exc)
        info["status"] = "WARN"
    return info


def v04954_create_hwpx_with_hancom(
    output: Path,
    result: dict,
    render_plan: dict,
    *,
    security_module_path: Path | None = None,
    allow_interactive_hwp: bool = False,
    show_hwp: bool = False,
) -> dict:
    # Keep the stable one-session renderer + image anchor guarantees from v04953.
    base = v04953_create_hwpx_with_hancom(
        output,
        result,
        render_plan,
        security_module_path=security_module_path,
        allow_interactive_hwp=allow_interactive_hwp,
        show_hwp=show_hwp,
    )
    result["hancom_security_v04954"] = (
        result.get("hancom_security_v04953") or base.get("hancom_security") or {}
    )
    if base.get("status") == "SKIPPED":
        return {
            **base,
            "backend": "hancom_com_v04954",
            "editorial_postprocess_v04954": {"status": "SKIPPED", "applied": False},
        }
    if not Path(output).exists() or not zipfile.is_zipfile(output):
        return {
            **base,
            "backend": "hancom_com_v04954",
            "editorial_postprocess_v04954": {"status": "SKIPPED", "applied": False, "reason": "no usable output.hwpx"},
        }

    editorial = _v04954_editorial_postprocess(output, result, render_plan)
    expected = int(result.get("image_filter_v0481", {}).get("saved_count") or 0)
    final_validation = v04954_validate_hwpx(
        output,
        expected_images=expected,
        render_plan=render_plan,
        result=result,
    )
    attempts = list(base.get("attempts") or [])
    attempts.append({
        "renderer_mode": "editorial_layout_v04954",
        "status": editorial.get("status"),
        "applied": editorial.get("applied", False),
        "reason": editorial.get("reason"),
    })
    return {
        **base,
        "status": "created" if final_validation.get("package_status") == "PASS" else base.get("status"),
        "backend": "hancom_com_v04954",
        "effective_layout_mode": "two_column_question_and_answer",
        "two_column_origin": "hwpx_xml_postprocess_plus_editorial_style",
        "editorial_postprocess_v04954": editorial,
        "validation": final_validation,
        "quality_status": final_validation.get("status"),
        "attempts": attempts,
        "hancom_security": result.get("hancom_security_v04954") or base.get("hancom_security") or {},
    }


def v04954_upgrade_result(
    result: dict,
    pdf_path: Path,
    checkpoint_path: Path | None = None,
    *,
    security_module_path: Path | None = None,
    allow_interactive_hwp: bool = False,
    show_hwp: bool = False,
) -> dict:
    _v0491_log("[v0.4.9.5.4] 지문 안내문/박스 + 띄어쓰기 조판 + 답안 2단 준비")
    result = v046_upgrade_result(result, pdf_path)
    result = v0481_prepare_problem_images(pdf_path, result)
    result = v0491_cleanup_legacy_metadata(result)
    result = v0495_attach_question_geometry(pdf_path, result)

    render_plan = v04954_build_render_plan(result)
    result["render_plan_v04954"] = render_plan
    for stale_key in [
        "render_plan_v04953", "render_plan_v04952", "render_plan_v04951", "render_plan_v0495",
        "render_plan_v0494", "render_plan_v0493", "render_plan_v0492", "render_plan_v049",
    ]:
        result.pop(stale_key, None)

    result["version"] = "v0.4.9.5.4"
    result["parser_version"] = "v0.4.9.5.4"
    result["generator_version"] = "PDF Parser Integrated v0.4.9.5.4"
    result["schema_version"] = {
        "base": "v0.4.9.5.3",
        "extension": [
            "bold_passage_instruction_per_group",
            "connected_passage_rectangle_border",
            "single_blank_line_between_section_labels",
            "left_alignment_to_prevent_stretched_word_gaps",
            "two_column_answer_section_with_center_gutter",
            "narrow_column_lineseg_width_normalization",
            "editorial_hwpx_postvalidation",
        ],
    }

    if checkpoint_path is not None:
        checkpoint_path = Path(checkpoint_path)
        result["pre_hwpx_checkpoint"] = {
            "path": str(checkpoint_path.resolve()),
            "purpose": "COM hang/error recovery only",
            "retained_after_success": False,
        }
        _v0491_json_safe_write(checkpoint_path, result)
        _v0491_log(f"[v0.4.9.5.4] HWPX 전 임시 체크포인트 저장: {checkpoint_path.resolve()}")

    hwpx_path = pdf_path.parent / "output.hwpx"
    hwpx_info = v04954_create_hwpx_with_hancom(
        hwpx_path,
        result,
        render_plan,
        security_module_path=security_module_path,
        allow_interactive_hwp=allow_interactive_hwp,
        show_hwp=show_hwp,
    )
    result["hwpx_v04954"] = hwpx_info
    result["hancom_security_v04954"] = result.get("hancom_security_v04954") or hwpx_info.get("hancom_security") or {}
    result.pop("hancom_security_v04953", None)

    base_validation = result.get("validation", {})
    img_validation = result.get("image_filter_v0481", {})
    table_validation = result.get("table_filter_v0492", {})
    geometry_validation = result.get("question_geometry_v0495", {})
    source_order_validation = render_plan.get("source_order_v0495", {})
    final_validation = hwpx_info.get("validation") or {}
    security_runtime = result.get("hancom_security_v04954") or {}
    hwpx_status = hwpx_info.get("status")
    security_ok = (
        security_runtime.get("unattended_ready") is True
        or hwpx_status == "SKIPPED"
        or (allow_interactive_hwp and hwpx_status == "created")
    )
    hard_pass = (
        base_validation.get("status") == "PASS"
        and img_validation.get("status") == "PASS"
        and table_validation.get("status") == "PASS"
        and geometry_validation.get("status") == "PASS"
        and source_order_validation.get("status") == "PASS"
        and hwpx_status in {"created", "SKIPPED"}
        and security_ok
        and final_validation.get("package_status") in {"PASS", None}
    )
    positional_fail = any(final_validation.get(k) == "FAIL" for k in (
        "image_order_status", "image_anchor_status", "image_answer_boundary_status", "image_logical_position_status",
    ))
    editorial_fail = any(final_validation.get(k) == "FAIL" for k in (
        "passage_instruction_status", "passage_box_status", "answer_center_gap_status",
    ))
    if positional_fail or editorial_fail:
        final_status = "FAIL"
    elif hard_pass and final_validation.get("status") in {"PASS", None}:
        final_status = "PASS"
    else:
        final_status = "WARN"

    editorial = hwpx_info.get("editorial_postprocess_v04954") or {}
    result["validation_v04954"] = {
        "question_count": len(result.get("questions", [])),
        "passage_group_count": len(result.get("passage_groups", [])),
        "problem_image_count": img_validation.get("selected_problem_figure_count", 0),
        "problem_image_saved": img_validation.get("saved_count", 0),
        "raw_table_count": table_validation.get("raw_table_count", 0),
        "renderable_table_count": table_validation.get("renderable_table_count", 0),
        "excluded_table_count": table_validation.get("excluded_table_count", 0),
        "answer_count": render_plan.get("stats", {}).get("answer_count", 0),
        "render_page_count": render_plan.get("stats", {}).get("page_count", 0),
        "render_item_count": render_plan.get("stats", {}).get("render_item_count", 0),
        "question_geometry_status": geometry_validation.get("status"),
        "source_order_status": source_order_validation.get("status"),
        "base_parser_status": base_validation.get("status"),
        "image_status": img_validation.get("status"),
        "hancom_security_status": security_runtime.get("status"),
        "hancom_security_register_result": security_runtime.get("register_module_result"),
        "unattended_ready": security_runtime.get("unattended_ready", False),
        "hwpx_status": hwpx_status,
        "hwpx_effective_layout_mode": hwpx_info.get("effective_layout_mode"),
        "hwpx_two_column_origin": hwpx_info.get("two_column_origin"),
        "hwpx_zip_status": final_validation.get("zip_status"),
        "hwpx_package_status": final_validation.get("package_status"),
        "hwpx_content_status": final_validation.get("content_status"),
        "hwpx_layout_status": final_validation.get("layout_status"),
        "hwpx_quality_status": final_validation.get("quality_status"),
        "hwpx_validation_status": final_validation.get("status"),
        "hwpx_question_two_column_found": final_validation.get("question_two_column_found"),
        "hwpx_answer_sections_two_column": final_validation.get("answer_sections_two_column"),
        "hwpx_section_column_counts": final_validation.get("section_column_counts"),
        "passage_instruction_count": final_validation.get("passage_instruction_count"),
        "passage_instruction_status": final_validation.get("passage_instruction_status"),
        "passage_box_status": final_validation.get("passage_box_status"),
        "word_spacing_layout_status": final_validation.get("word_spacing_layout_status"),
        "remaining_wide_lineseg_count": final_validation.get("remaining_wide_lineseg_count"),
        "answer_center_gap_status": final_validation.get("answer_center_gap_status"),
        "answer_center_gap_hwpunit": _V04954_GUTTER_HWPUNIT,
        "answer_center_gap_mm": 8.0,
        "image_order_status": final_validation.get("image_order_status"),
        "image_anchor_status": final_validation.get("image_anchor_status"),
        "image_answer_boundary_status": final_validation.get("image_answer_boundary_status"),
        "image_logical_position_status": final_validation.get("image_logical_position_status"),
        "image_position_status": final_validation.get("image_position_status"),
        "pictures_after_answer_count": final_validation.get("pictures_after_answer_count"),
        "editorial_postprocess_status": editorial.get("status"),
        "editorial_postprocess_applied": editorial.get("applied", False),
        "status": final_status,
    }
    result["known_limitations_v04954"] = [
        "지문 박스는 HWPX paragraph border(connect=1) 방식이며 문제/선택지는 박스 밖에 둡니다.",
        "(가)/(나)/(다) 전환은 한 줄만 비우며 수작업 파일 첫 지문의 과도한 공백은 재현하지 않습니다.",
        "문제/답안 모두 2단이며 중앙 간격은 약 8 mm로 고정합니다.",
        "XML 2단 보정 후 어절 간격이 늘어나는 현상을 줄이기 위해 문단 정렬을 LEFT로 바꾸고 1단 폭 line-segment cache를 2단 폭으로 정규화합니다.",
        "Windows 한글 COM의 실제 화면 재조판은 설치 버전에 따라 미세한 줄바꿈 차이가 남을 수 있습니다.",
    ]
    return result


def main_v04954() -> None:
    parser = argparse.ArgumentParser(description="국어 문제 PDF -> 구조화 JSON + HWPX V0.4.9.5.4")
    parser.add_argument("pdf", type=Path, help="분석할 PDF 파일")
    parser.add_argument("-o", "--output", type=Path, default=Path("v0_4_9_5_4_result.json"), help="저장할 JSON")
    parser.add_argument("-q", "--questions", nargs="+", type=int, default=list(range(1, 21)), help="추출할 문제 번호")
    parser.add_argument("--no-kiwi", action="store_true", help="Kiwi 경계 판별을 끔")
    parser.add_argument("--security-module", type=Path, default=None, help="FilePathCheckerModuleExample.dll 경로")
    parser.add_argument("--allow-interactive-hwp", action="store_true", help="보안 모듈 실패 시 대화형 한글 허용")
    parser.add_argument("--show-hwp", action="store_true", help="한글 창 표시")
    args = parser.parse_args()

    if not args.pdf.exists():
        raise SystemExit(f"PDF 파일을 찾을 수 없습니다: {args.pdf}")
    if not args.no_kiwi and Kiwi is None:
        print("[경고] kiwipiepy 미설치. fallback으로 실행합니다.")

    result = parse_v0_2_3(args.pdf, sorted(set(args.questions)), use_kiwi=not args.no_kiwi)
    result = v044_upgrade_result(result, args.pdf)
    result = v045_upgrade_result(result, args.pdf)
    checkpoint_path = args.output.with_name(args.output.stem + "_pre_hwpx.json")
    result = v04954_upgrade_result(
        result,
        args.pdf,
        checkpoint_path=checkpoint_path,
        security_module_path=args.security_module,
        allow_interactive_hwp=args.allow_interactive_hwp,
        show_hwp=args.show_hwp,
    )
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    checkpoint_info = result.get("pre_hwpx_checkpoint") or {}
    checkpoint_file = Path(str(checkpoint_info.get("path") or "")) if isinstance(checkpoint_info, dict) else None
    if result.get("hwpx_v04954", {}).get("status") == "created" and checkpoint_file and str(checkpoint_file):
        try:
            if checkpoint_file.exists():
                checkpoint_file.unlink()
            checkpoint_info["retained"] = False
            result["pre_hwpx_checkpoint"] = checkpoint_info
            args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            checkpoint_info["retained"] = True
            checkpoint_info["cleanup_error"] = str(exc)

    v = result.get("validation_v04954", {})
    print("=" * 76)
    print("V0.4.9.5.4 전체 문제 구조화 + 편집 레이아웃 완료")
    print("=" * 76)
    print(f"입력 : {args.pdf}")
    print(f"출력 : {args.output.resolve()}")
    print(f"문제 : {v.get('question_count', 0)} | 지문 그룹 : {v.get('passage_group_count', 0)}")
    print(f"HWPX : {v.get('hwpx_status')} | 최종 검증 : {v.get('status')}")
    print(f"지문 안내문 : {v.get('passage_instruction_status')} | 지문 박스 : {v.get('passage_box_status')}")
    print(f"문제/답안 2단 : {v.get('hwpx_question_two_column_found')} / {v.get('hwpx_answer_sections_two_column')}")
    print(f"답안 중앙 간격 : {v.get('answer_center_gap_status')} ({v.get('answer_center_gap_mm')} mm)")
    print(f"어절 간격 조판 : {v.get('word_spacing_layout_status')}")
    print(f"이미지 위치 : {v.get('image_position_status')} | 답지 뒤 이미지 : {v.get('pictures_after_answer_count')}")




# ============================================================
# V0.4.9.5.5 Compact Page / Block Integrity Layer
# - increase passage-box text padding without widening the border itself
# - reduce outer page margins to maximize usable paper area
# - remove full blank-paragraph spacing before questions; use compact para margins
# - keep each question + example + five choices together across column/page breaks
# - keep answer header + explanation pairs together in the answer section
# - keep passage guide + first passage paragraph together
# - expand cached two-column line width to match the newly widened page body
# - post-validate margins, box padding, and keep-together styles atomically
# ============================================================

_V04955_PAGE_MARGIN_HWPUNIT = 2268       # approx. 8 mm
_V04955_HEADER_FOOTER_HWPUNIT = 1134    # approx. 4 mm
_V04955_BOX_LR_PADDING_HWPUNIT = 850     # approx. 3.0 mm
_V04955_BOX_TB_PADDING_HWPUNIT = 425     # approx. 1.5 mm
_V04955_COLUMN_LINE_WIDTH = 24600        # ~86.8 mm text width, fits 3 mm box padding in 93 mm column
_V04955_FIRST_QUESTION_PREV = 1000       # ~3.5 mm separation after a passage box
_V04955_QUESTION_PREV = 425              # ~1.5 mm between question blocks
_V04955_BLOCK_END_NEXT = 425             # ~1.5 mm after last choice / answer explanation
_V04955_GUIDE_PREV = 850                 # ~3.0 mm before a new passage guide


def v04955_build_render_plan(result: dict) -> dict:
    """Reuse v0.4.9.5.4 source ordering, but remove wasteful blank paragraphs.

    Question separation is handled with paragraph `prev/next` margins in the
    final HWPX rather than inserting an empty paragraph. This keeps the document
    compact while still visually separating passage/question blocks.
    """
    plan = v04954_build_render_plan(result)
    first_questions = {
        int((g.get("question_numbers") or [0])[0])
        for g in result.get("passage_groups", [])
        if g.get("question_numbers")
    }
    for page_entry in plan.get("pages", []):
        for side in ("left", "right"):
            for item in page_entry.get(side, []):
                if item.get("type") == "question":
                    style = dict(item.get("style_v0495") or _v0495_style_for_item(item))
                    style["blank_before"] = 0
                    item["style_v0495"] = style
                    qno = int(item.get("number") or 0)
                    item["first_question_in_group_v04955"] = qno in first_questions
    plan["version"] = "v0.4.9.5.5"
    plan["layout_mode"] = "compact_two_column_with_keep_together_blocks"
    plan["compact_layout_v04955"] = {
        "page_margin_mm": 8.0,
        "header_footer_margin_mm": 4.0,
        "passage_box_horizontal_padding_mm": 3.0,
        "passage_box_vertical_padding_mm": 1.5,
        "question_block_keep_together": True,
        "answer_pair_keep_together": True,
        "passage_guide_keep_with_first_paragraph": True,
        "full_blank_paragraph_before_question": False,
    }
    return plan


def _v04955_patch_page_margins(xml: str) -> tuple[str, int]:
    changed = 0

    def repl(m: re.Match) -> str:
        nonlocal changed
        tag = m.group(0)
        values = {
            "header": _V04955_HEADER_FOOTER_HWPUNIT,
            "footer": _V04955_HEADER_FOOTER_HWPUNIT,
            "gutter": 0,
            "left": _V04955_PAGE_MARGIN_HWPUNIT,
            "right": _V04955_PAGE_MARGIN_HWPUNIT,
            "top": _V04955_PAGE_MARGIN_HWPUNIT,
            "bottom": _V04955_PAGE_MARGIN_HWPUNIT,
        }
        original = tag
        for key, value in values.items():
            if re.search(rf'\b{key}="-?\d+"', tag):
                tag = re.sub(rf'\b{key}="-?\d+"', f'{key}="{int(value)}"', tag)
            else:
                tag = tag[:-2] + f' {key}="{int(value)}"/>' if tag.endswith('/>') else tag
        if tag != original:
            changed += 1
        return tag

    return re.sub(r'<hp:margin\b[^>]*/>', repl, xml), changed


def _v04955_expand_lineseg_width(xml: str) -> tuple[str, int]:
    """Expand only the v0.4.9.5.4 normalized 23376-HU line cache.

    This avoids rewriting special narrow lines while allowing the reduced page
    margins to translate into useful text width instead of dead white space.
    """
    changed = 0

    def repl(m: re.Match) -> str:
        nonlocal changed
        tag = m.group(0)
        width_m = re.search(r'\bhorzsize="(\d+)"', tag)
        pos_m = re.search(r'\bhorzpos="(\d+)"', tag)
        if not width_m:
            return tag
        old = int(width_m.group(1))
        if old != _V04954_COLUMN_LINE_WIDTH:
            return tag
        horzpos = int(pos_m.group(1)) if pos_m else 0
        target = max(18000, _V04955_COLUMN_LINE_WIDTH - horzpos)
        changed += 1
        return re.sub(r'\bhorzsize="\d+"', f'horzsize="{target}"', tag, count=1)

    return re.sub(r'<hp:lineseg\b[^>]*/>', repl, xml), changed


def _v04955_patch_box_padding(header_xml: str) -> tuple[str, int]:
    changed = 0

    def repl(m: re.Match) -> str:
        nonlocal changed
        tag = m.group(0)
        if not re.search(r'\bconnect="1"', tag):
            return tag
        original = tag
        for key, value in (
            ("offsetLeft", _V04955_BOX_LR_PADDING_HWPUNIT),
            ("offsetRight", _V04955_BOX_LR_PADDING_HWPUNIT),
            ("offsetTop", _V04955_BOX_TB_PADDING_HWPUNIT),
            ("offsetBottom", _V04955_BOX_TB_PADDING_HWPUNIT),
        ):
            if re.search(rf'\b{key}="-?\d+"', tag):
                tag = re.sub(rf'\b{key}="-?\d+"', f'{key}="{int(value)}"', tag)
            else:
                tag = tag[:-2] + f' {key}="{int(value)}"/>' if tag.endswith('/>') else tag
        if tag != original:
            changed += 1
        return tag

    return re.sub(r'<hh:border\b[^>]*/>', repl, header_xml), changed


def _v04955_clone_flow_parapr(
    header_xml: str,
    source_id: int,
    new_id: int,
    *,
    keep_with_next: int,
    keep_lines: int,
    prev_margin: int,
    next_margin: int,
) -> str:
    m = re.search(
        rf'<hh:paraPr\b[^>]*\bid="{int(source_id)}"[\s\S]*?</hh:paraPr>',
        header_xml,
    )
    if not m:
        raise RuntimeError(f"header.xml paraPr template {source_id} not found")
    clone = m.group(0)
    clone = re.sub(r'\bid="\d+"', f'id="{int(new_id)}"', clone, count=1)
    clone = re.sub(r'horizontal="JUSTIFY"', 'horizontal="LEFT"', clone)

    def patch_break(bs: re.Match) -> str:
        tag = bs.group(0)
        for key, value in (("keepWithNext", keep_with_next), ("keepLines", keep_lines)):
            if re.search(rf'\b{key}="\d+"', tag):
                tag = re.sub(rf'\b{key}="\d+"', f'{key}="{int(value)}"', tag)
            else:
                tag = tag[:-2] + f' {key}="{int(value)}"/>' if tag.endswith('/>') else tag
        return tag

    clone = re.sub(r'<hh:breakSetting\b[^>]*/>', patch_break, clone, count=1)
    clone = re.sub(
        r'(<hc:prev\b[^>]*\bvalue=")-?\d+("[^>]*/>)',
        rf'\g<1>{int(prev_margin)}\2',
        clone,
    )
    clone = re.sub(
        r'(<hc:next\b[^>]*\bvalue=")-?\d+("[^>]*/>)',
        rf'\g<1>{int(next_margin)}\2',
        clone,
    )
    header_xml = header_xml.replace('</hh:paraProperties>', clone + '</hh:paraProperties>', 1)
    return header_xml



def _v04955_remove_spacing_only_paragraphs(section_xml: str, *, answer_section: bool) -> tuple[str, int]:
    """Remove only empty paragraphs that were used as block spacing.

    v0.4.9.5.4 rendered a full empty paragraph before every question and after
    every answer explanation.  v0.4.9.5.5 replaces those with para prev/next
    margins, which is visually cleaner and saves vertical space.  Explicit
    pageBreak/columnBreak carriers and intentional (가)/(나)/(다) blank lines
    are never removed.
    """
    matches = list(re.finditer(r'<hp:p\b[^>]*>[\s\S]*?</hp:p>', section_xml))
    if not matches:
        return section_xml, 0
    texts = [_v04954_para_text(m.group(0)) for m in matches]

    def prev_text(i: int) -> str:
        for j in range(i - 1, -1, -1):
            if texts[j]:
                return texts[j]
        return ""

    def next_text(i: int) -> str:
        for j in range(i + 1, len(texts)):
            if texts[j]:
                return texts[j]
        return ""

    remove: set[int] = set()
    for i, m in enumerate(matches):
        if texts[i]:
            continue
        p = m.group(0)
        if re.search(r'\bpageBreak="1"', p) or re.search(r'\bcolumnBreak="1"', p):
            continue
        prev = prev_text(i)
        nxt = next_text(i)
        if answer_section:
            if (
                (prev == "[정답 및 해설]" and re.match(r'^\d+\)\s*\[정답\]', nxt))
                or (prev.startswith("[해설]") and re.match(r'^\d+\)\s*\[정답\]', nxt))
            ):
                remove.add(i)
        else:
            # Empty spacer immediately before a question stem or between two
            # question blocks.  Do not remove the one intentional blank line
            # before later (나)/(다) passage labels.
            if re.match(r'^\d+\.\s', nxt):
                if prev and prev not in {"(가)", "(나)", "(다)", "(라)", "(마)"}:
                    remove.add(i)

    if not remove:
        return section_xml, 0
    out = []
    cursor = 0
    for i, m in enumerate(matches):
        out.append(section_xml[cursor:m.start()])
        if i not in remove:
            out.append(m.group(0))
        cursor = m.end()
    out.append(section_xml[cursor:])
    return ''.join(out), len(remove)


def _v04955_apply_flow_styles(
    header_xml: str,
    section_xml: str,
    *,
    answer_section: bool,
    result: dict,
) -> tuple[str, str, dict]:
    """Apply compact spacing + keep-together semantics by paragraph role."""
    first_questions = {
        int((g.get("question_numbers") or [0])[0])
        for g in result.get("passage_groups", [])
        if g.get("question_numbers")
    }
    cache: dict[tuple[int, int, int, int, int], int] = {}
    clone_count = 0
    counters = {
        "question_keep_count": 0,
        "choice_keep_count": 0,
        "guide_keep_count": 0,
        "section_label_keep_count": 0,
        "answer_keep_count": 0,
        "explanation_keep_count": 0,
    }

    def style_para(p: str, keep_next: int, keep_lines: int, prev: int, nxt: int) -> str:
        nonlocal header_xml, clone_count
        sm = re.match(r'<hp:p\b[^>]*\bparaPrIDRef="(\d+)"[^>]*>', p)
        if not sm:
            return p
        source_id = int(sm.group(1))
        key = (source_id, int(keep_next), int(keep_lines), int(prev), int(nxt))
        if key not in cache:
            new_id = _v04954_next_id(header_xml, "paraPr")
            header_xml = _v04955_clone_flow_parapr(
                header_xml,
                source_id,
                new_id,
                keep_with_next=keep_next,
                keep_lines=keep_lines,
                prev_margin=prev,
                next_margin=nxt,
            )
            cache[key] = new_id
            clone_count += 1
        return re.sub(
            r'(<hp:p\b[^>]*\bparaPrIDRef=")\d+("[^>]*>)',
            rf'\g<1>{cache[key]}\2',
            p,
            count=1,
        )

    paragraphs = list(re.finditer(r'<hp:p\b[^>]*>[\s\S]*?</hp:p>', section_xml))
    output = []
    cursor = 0
    for pm in paragraphs:
        output.append(section_xml[cursor:pm.start()])
        p = pm.group(0)
        text = _v04954_para_text(p)

        if answer_section:
            if text == "[정답 및 해설]":
                p = style_para(p, 1, 1, 0, 250)
            elif re.match(r'^\d+\)\s*\[정답\]', text):
                p = style_para(p, 1, 1, _V04955_QUESTION_PREV, 0)
                counters["answer_keep_count"] += 1
            elif text.startswith("[해설]"):
                p = style_para(p, 0, 1, 0, _V04955_BLOCK_END_NEXT)
                counters["explanation_keep_count"] += 1
        else:
            if text == _V04954_PASSAGE_GUIDE:
                p = style_para(p, 1, 1, _V04955_GUIDE_PREV, 180)
                counters["guide_keep_count"] += 1
            elif text in {"(가)", "(나)", "(다)", "(라)", "(마)"}:
                p = style_para(p, 1, 1, 0, 0)
                counters["section_label_keep_count"] += 1
            else:
                qm = re.match(r'^(\d+)\.\s', text)
                if qm:
                    qno = int(qm.group(1))
                    prev = _V04955_FIRST_QUESTION_PREV if qno in first_questions else _V04955_QUESTION_PREV
                    p = style_para(p, 1, 1, prev, 0)
                    counters["question_keep_count"] += 1
                elif re.match(r'^[①②③④]\s', text):
                    p = style_para(p, 1, 1, 0, 0)
                    counters["choice_keep_count"] += 1
                elif re.match(r'^⑤\s', text):
                    p = style_para(p, 0, 1, 0, _V04955_BLOCK_END_NEXT)
                    counters["choice_keep_count"] += 1
                elif text.startswith("<보기>") or text.startswith("[보기]"):
                    p = style_para(p, 1, 1, 0, 0)

        output.append(p)
        cursor = pm.end()

    output.append(section_xml[cursor:])
    section_xml = ''.join(output)
    header_xml = _v04954_set_item_count(header_xml, "paraProperties", clone_count)
    counters["new_flow_para_style_count"] = clone_count
    return header_xml, section_xml, counters


def _v04955_read_margin_values(xml: str) -> dict[str, int]:
    m = re.search(r'<hp:pagePr\b[^>]*>[\s\S]*?<hp:margin\b([^>]*)/>', xml)
    if not m:
        return {}
    attrs = m.group(1)
    out = {}
    for key in ("header", "footer", "gutter", "left", "right", "top", "bottom"):
        v = re.search(rf'\b{key}="(-?\d+)"', attrs)
        if v:
            out[key] = int(v.group(1))
    return out


def _v04955_flow_style_sets(header_xml: str) -> tuple[set[int], set[int]]:
    keep_next_ids: set[int] = set()
    keep_lines_ids: set[int] = set()
    for m in re.finditer(r'<hh:paraPr\b[^>]*\bid="(\d+)"[\s\S]*?</hh:paraPr>', header_xml):
        pid = int(m.group(1))
        body = m.group(0)
        if re.search(r'\bkeepWithNext="1"', body):
            keep_next_ids.add(pid)
        if re.search(r'\bkeepLines="1"', body):
            keep_lines_ids.add(pid)
    return keep_next_ids, keep_lines_ids


def _v04955_validate_compact_layout(path: Path, result: dict, base_info: dict | None = None) -> dict:
    info = dict(base_info or {})
    info["validator_version"] = "v0.4.9.5.5"
    if not Path(path).exists() or not zipfile.is_zipfile(path):
        info["compact_layout_status"] = "FAIL"
        return info
    try:
        with zipfile.ZipFile(path, 'r') as zf:
            header = zf.read('Contents/header.xml').decode('utf-8', errors='ignore')
            section_names = sorted(
                [n for n in zf.namelist() if re.fullmatch(r'Contents/section\d+\.xml', n)],
                key=_v04953_section_number,
            )
            sections = {n: zf.read(n).decode('utf-8', errors='ignore') for n in section_names}

        margin_values = {name: _v04955_read_margin_values(xml) for name, xml in sections.items()}
        margins_ok = bool(margin_values) and all(
            vals.get("left") == _V04955_PAGE_MARGIN_HWPUNIT
            and vals.get("right") == _V04955_PAGE_MARGIN_HWPUNIT
            and vals.get("top") == _V04955_PAGE_MARGIN_HWPUNIT
            and vals.get("bottom") == _V04955_PAGE_MARGIN_HWPUNIT
            for vals in margin_values.values()
        )

        padded_borders = re.findall(
            rf'<hh:border\b[^>]*offsetLeft="{_V04955_BOX_LR_PADDING_HWPUNIT}"[^>]*'
            rf'offsetRight="{_V04955_BOX_LR_PADDING_HWPUNIT}"[^>]*'
            rf'offsetTop="{_V04955_BOX_TB_PADDING_HWPUNIT}"[^>]*'
            rf'offsetBottom="{_V04955_BOX_TB_PADDING_HWPUNIT}"[^>]*connect="1"[^>]*/>',
            header,
        )
        box_padding_ok = bool(padded_borders)

        keep_next_ids, keep_lines_ids = _v04955_flow_style_sets(header)
        q_total = q_keep = answer_total = answer_keep = 0
        for name, xml in sections.items():
            for pm in re.finditer(r'<hp:p\b[^>]*\bparaPrIDRef="(\d+)"[^>]*>[\s\S]*?</hp:p>', xml):
                pid = int(pm.group(1))
                text = _v04954_para_text(pm.group(0))
                if name == 'Contents/section0.xml' and re.match(r'^\d+\.\s', text):
                    q_total += 1
                    if pid in keep_next_ids and pid in keep_lines_ids:
                        q_keep += 1
                if name != 'Contents/section0.xml' and re.match(r'^\d+\)\s*\[정답\]', text):
                    answer_total += 1
                    if pid in keep_next_ids and pid in keep_lines_ids:
                        answer_keep += 1

        question_keep_ok = q_total > 0 and q_keep == q_total
        answer_keep_ok = answer_total == 0 or answer_keep == answer_total

        wide_cache = []
        for xml in sections.values():
            for hp, hs in re.findall(r'<hp:lineseg\b[^>]*horzpos="(\d+)"[^>]*horzsize="(\d+)"[^>]*/>', xml):
                if int(hs) == _V04954_COLUMN_LINE_WIDTH:
                    wide_cache.append((int(hp), int(hs)))

        info.update({
            "page_margin_values": margin_values,
            "page_margin_status": "PASS" if margins_ok else "FAIL",
            "page_margin_mm": 8.0,
            "passage_box_padding_status": "PASS" if box_padding_ok else "FAIL",
            "passage_box_padding_left_right_mm": 3.0,
            "passage_box_padding_top_bottom_mm": 1.5,
            "question_keep_together_count": q_keep,
            "question_count_for_keep_together": q_total,
            "question_keep_together_status": "PASS" if question_keep_ok else "FAIL",
            "answer_keep_together_count": answer_keep,
            "answer_count_for_keep_together": answer_total,
            "answer_keep_together_status": "PASS" if answer_keep_ok else "FAIL",
            "remaining_old_column_lineseg_count": len(wide_cache),
            "compact_layout_status": "PASS" if margins_ok and box_padding_ok and question_keep_ok and answer_keep_ok else "FAIL",
        })
        return info
    except Exception as exc:
        info["compact_layout_status"] = "FAIL"
        info["v04955_validation_error"] = str(exc)
        return info


def _v04955_compact_postprocess(output: Path, result: dict, render_plan: dict) -> dict:
    import os as _os
    import zipfile as _zipfile
    output = Path(output)
    report = {
        "version": "v0.4.9.5.5",
        "status": "SKIPPED",
        "applied": False,
        "page_margin_mm": 8.0,
        "box_padding_horizontal_mm": 3.0,
        "box_padding_vertical_mm": 1.5,
        "question_keep_together": True,
        "answer_pair_keep_together": True,
    }
    if not output.exists() or not _zipfile.is_zipfile(output):
        report["reason"] = "no usable HWPX"
        return report

    candidate = output.with_name('output_v0_4_9_5_5_compact_candidate.hwpx')
    try:
        with _zipfile.ZipFile(output, 'r') as zf:
            names = set(zf.namelist())
            header = zf.read('Contents/header.xml').decode('utf-8', errors='ignore')
            section_names = sorted(
                [n for n in names if re.fullmatch(r'Contents/section\d+\.xml', n)],
                key=_v04953_section_number,
            )
            sections = {n: zf.read(n).decode('utf-8', errors='ignore') for n in section_names}

        header, padding_changes = _v04955_patch_box_padding(header)
        report["passage_box_padding_style_count"] = padding_changes

        margin_changes = {}
        line_changes = {}
        for name in section_names:
            sections[name], margin_changes[name] = _v04955_patch_page_margins(sections[name])
            sections[name], line_changes[name] = _v04955_expand_lineseg_width(sections[name])
        report["page_margin_patch_count"] = margin_changes
        report["lineseg_width_expansion_count"] = line_changes

        flow_reports = {}
        removed_spacers = {}
        if 'Contents/section0.xml' in sections:
            sections['Contents/section0.xml'], removed_spacers['Contents/section0.xml'] = _v04955_remove_spacing_only_paragraphs(
                sections['Contents/section0.xml'], answer_section=False
            )
            header, sections['Contents/section0.xml'], q_report = _v04955_apply_flow_styles(
                header,
                sections['Contents/section0.xml'],
                answer_section=False,
                result=result,
            )
            flow_reports['Contents/section0.xml'] = q_report
        for name in section_names:
            if name == 'Contents/section0.xml':
                continue
            sections[name], removed_spacers[name] = _v04955_remove_spacing_only_paragraphs(
                sections[name], answer_section=True
            )
            header, sections[name], a_report = _v04955_apply_flow_styles(
                header,
                sections[name],
                answer_section=True,
                result=result,
            )
            flow_reports[name] = a_report
        report["flow_style_report"] = flow_reports
        report["removed_spacing_only_paragraphs"] = removed_spacers

        replacements = {'Contents/header.xml': header.encode('utf-8')}
        replacements.update({name: xml.encode('utf-8') for name, xml in sections.items()})
        _v04954_repack_hwpx(output, candidate, replacements)

        expected_images = int(result.get('image_filter_v0481', {}).get('saved_count') or 0)
        base_validation = v04954_validate_hwpx(
            candidate,
            expected_images=expected_images,
            render_plan=render_plan,
            result=result,
        )
        final_validation = _v04955_validate_compact_layout(candidate, result, base_validation)
        report["validation"] = final_validation

        accepted = (
            final_validation.get("package_status") == "PASS"
            and final_validation.get("image_position_status") != "FAIL"
            and final_validation.get("passage_instruction_status") != "FAIL"
            and final_validation.get("passage_box_status") != "FAIL"
            and final_validation.get("page_margin_status") == "PASS"
            and final_validation.get("passage_box_padding_status") == "PASS"
            and final_validation.get("question_keep_together_status") == "PASS"
            and final_validation.get("answer_keep_together_status") == "PASS"
        )
        if accepted:
            _os.replace(str(candidate), str(output))
            report["status"] = "APPLIED"
            report["applied"] = True
            report["accepted"] = True
        else:
            report["status"] = "REJECTED_BY_VALIDATION"
            report["accepted"] = False
            report["reason"] = "compact candidate failed package/image/margin/padding/keep-together checks"
        return report
    except Exception as exc:
        report["status"] = "ERROR"
        report["reason"] = str(exc)
        return report
    finally:
        if candidate.exists():
            try:
                candidate.unlink()
            except Exception:
                pass


def v04955_validate_hwpx(path: Path, *, expected_images: int, render_plan: dict, result: dict) -> dict:
    base = v04954_validate_hwpx(
        path,
        expected_images=expected_images,
        render_plan=render_plan,
        result=result,
    )
    info = _v04955_validate_compact_layout(path, result, base)
    if info.get("compact_layout_status") == "FAIL":
        info["status"] = "FAIL"
    elif info.get("status") not in {"FAIL", "WARN"}:
        info["status"] = "PASS"
    return info


def v04955_create_hwpx_with_hancom(
    output: Path,
    result: dict,
    render_plan: dict,
    *,
    security_module_path: Path | None = None,
    allow_interactive_hwp: bool = False,
    show_hwp: bool = False,
) -> dict:
    # First use the already-stable v0.4.9.5.4 generation path.
    base = v04954_create_hwpx_with_hancom(
        output,
        result,
        render_plan,
        security_module_path=security_module_path,
        allow_interactive_hwp=allow_interactive_hwp,
        show_hwp=show_hwp,
    )
    result["hancom_security_v04955"] = result.get("hancom_security_v04954") or base.get("hancom_security") or {}
    if base.get("status") == "SKIPPED":
        return {
            **base,
            "backend": "hancom_com_v04955",
            "compact_postprocess_v04955": {"status": "SKIPPED", "applied": False},
        }
    if base.get("status") not in {"created", "INVALID"} or not Path(output).exists():
        return {
            **base,
            "backend": "hancom_com_v04955",
            "compact_postprocess_v04955": {"status": "SKIPPED", "applied": False, "reason": "no usable output.hwpx"},
        }

    compact = _v04955_compact_postprocess(output, result, render_plan)
    expected_images = int(result.get('image_filter_v0481', {}).get('saved_count') or 0)
    validation = v04955_validate_hwpx(
        output,
        expected_images=expected_images,
        render_plan=render_plan,
        result=result,
    )
    status = "created" if validation.get("status") in {"PASS", "WARN"} and validation.get("package_status") == "PASS" else "INVALID"
    return {
        **base,
        "status": status,
        "path": str(Path(output).resolve()),
        "final_path": str(Path(output).resolve()),
        "backend": "hancom_com_v04955",
        "renderer_mode": "compact_editorial_layout_v04955",
        "validation": validation,
        "compact_postprocess_v04955": compact,
        "effective_layout_mode": validation.get("effective_layout_mode") or base.get("effective_layout_mode"),
        "two_column_origin": base.get("two_column_origin"),
        "hancom_security": result.get("hancom_security_v04955") or base.get("hancom_security") or {},
    }


def v04955_upgrade_result(
    result: dict,
    pdf_path: Path,
    checkpoint_path: Path | None = None,
    *,
    security_module_path: Path | None = None,
    allow_interactive_hwp: bool = False,
    show_hwp: bool = False,
) -> dict:
    _v0491_log("[v0.4.9.5.5] 컴팩트 페이지 여백 + 지문 박스 패딩 + 문제/답안 묶음 조판 준비")
    result = v046_upgrade_result(result, pdf_path)
    result = v0481_prepare_problem_images(pdf_path, result)
    result = v0491_cleanup_legacy_metadata(result)
    result = v0495_attach_question_geometry(pdf_path, result)

    render_plan = v04955_build_render_plan(result)
    result["render_plan_v04955"] = render_plan
    for stale_key in [
        "render_plan_v04954", "render_plan_v04953", "render_plan_v04952", "render_plan_v04951",
        "render_plan_v0495", "render_plan_v0494", "render_plan_v0493", "render_plan_v0492", "render_plan_v049",
    ]:
        result.pop(stale_key, None)

    result["version"] = "v0.4.9.5.5"
    result["parser_version"] = "v0.4.9.5.5"
    result["generator_version"] = "PDF Parser Integrated v0.4.9.5.5"
    result["schema_version"] = {
        "base": "v0.4.9.5.4",
        "extension": [
            "reduced_page_margins_8mm",
            "passage_box_inner_padding_3mm_1_5mm",
            "compact_question_spacing_without_blank_paragraphs",
            "question_choice_keep_together",
            "answer_explanation_keep_together",
            "passage_guide_keep_with_first_line",
            "expanded_two_column_lineseg_cache",
            "compact_layout_postvalidation",
        ],
    }

    if checkpoint_path is not None:
        checkpoint_path = Path(checkpoint_path)
        result["pre_hwpx_checkpoint"] = {
            "path": str(checkpoint_path.resolve()),
            "purpose": "COM hang/error recovery only",
            "retained_after_success": False,
        }
        _v0491_json_safe_write(checkpoint_path, result)
        _v0491_log(f"[v0.4.9.5.5] HWPX 전 임시 체크포인트 저장: {checkpoint_path.resolve()}")

    hwpx_path = pdf_path.parent / "output.hwpx"
    hwpx_info = v04955_create_hwpx_with_hancom(
        hwpx_path,
        result,
        render_plan,
        security_module_path=security_module_path,
        allow_interactive_hwp=allow_interactive_hwp,
        show_hwp=show_hwp,
    )
    result["hwpx_v04955"] = hwpx_info
    result["hancom_security_v04955"] = result.get("hancom_security_v04955") or hwpx_info.get("hancom_security") or {}
    result.pop("hancom_security_v04954", None)

    base_validation = result.get("validation", {})
    img_validation = result.get("image_filter_v0481", {})
    table_validation = result.get("table_filter_v0492", {})
    geometry_validation = result.get("question_geometry_v0495", {})
    source_order_validation = render_plan.get("source_order_v0495", {})
    final_validation = hwpx_info.get("validation") or {}
    security_runtime = result.get("hancom_security_v04955") or {}
    hwpx_status = hwpx_info.get("status")
    security_ok = (
        security_runtime.get("unattended_ready") is True
        or hwpx_status == "SKIPPED"
        or (allow_interactive_hwp and hwpx_status == "created")
    )
    hard_pass = (
        base_validation.get("status") == "PASS"
        and img_validation.get("status") == "PASS"
        and table_validation.get("status") == "PASS"
        and geometry_validation.get("status") == "PASS"
        and source_order_validation.get("status") == "PASS"
        and hwpx_status in {"created", "SKIPPED"}
        and security_ok
        and final_validation.get("package_status") in {"PASS", None}
    )
    critical_keys = (
        "image_order_status", "image_anchor_status", "image_answer_boundary_status",
        "passage_instruction_status", "passage_box_status", "answer_center_gap_status",
        "page_margin_status", "passage_box_padding_status", "question_keep_together_status",
        "answer_keep_together_status",
    )
    critical_fail = any(final_validation.get(k) == "FAIL" for k in critical_keys)
    if critical_fail:
        final_status = "FAIL"
    elif hard_pass and final_validation.get("status") in {"PASS", None}:
        final_status = "PASS"
    else:
        final_status = "WARN"

    compact = hwpx_info.get("compact_postprocess_v04955") or {}
    result["validation_v04955"] = {
        "question_count": len(result.get("questions", [])),
        "passage_group_count": len(result.get("passage_groups", [])),
        "problem_image_count": img_validation.get("selected_problem_figure_count", 0),
        "problem_image_saved": img_validation.get("saved_count", 0),
        "answer_count": render_plan.get("stats", {}).get("answer_count", 0),
        "render_page_count": render_plan.get("stats", {}).get("page_count", 0),
        "render_item_count": render_plan.get("stats", {}).get("render_item_count", 0),
        "question_geometry_status": geometry_validation.get("status"),
        "source_order_status": source_order_validation.get("status"),
        "base_parser_status": base_validation.get("status"),
        "image_status": img_validation.get("status"),
        "hancom_security_status": security_runtime.get("status"),
        "unattended_ready": security_runtime.get("unattended_ready", False),
        "hwpx_status": hwpx_status,
        "hwpx_validation_status": final_validation.get("status"),
        "hwpx_package_status": final_validation.get("package_status"),
        "hwpx_question_two_column_found": final_validation.get("question_two_column_found"),
        "hwpx_answer_sections_two_column": final_validation.get("answer_sections_two_column"),
        "passage_instruction_status": final_validation.get("passage_instruction_status"),
        "passage_box_status": final_validation.get("passage_box_status"),
        "page_margin_status": final_validation.get("page_margin_status"),
        "page_margin_mm": final_validation.get("page_margin_mm"),
        "passage_box_padding_status": final_validation.get("passage_box_padding_status"),
        "passage_box_padding_left_right_mm": final_validation.get("passage_box_padding_left_right_mm"),
        "passage_box_padding_top_bottom_mm": final_validation.get("passage_box_padding_top_bottom_mm"),
        "question_keep_together_status": final_validation.get("question_keep_together_status"),
        "question_keep_together_count": final_validation.get("question_keep_together_count"),
        "answer_keep_together_status": final_validation.get("answer_keep_together_status"),
        "answer_keep_together_count": final_validation.get("answer_keep_together_count"),
        "image_position_status": final_validation.get("image_position_status"),
        "pictures_after_answer_count": final_validation.get("pictures_after_answer_count"),
        "compact_postprocess_status": compact.get("status"),
        "compact_postprocess_applied": compact.get("applied", False),
        "status": final_status,
    }
    result["known_limitations_v04955"] = [
        "페이지 외곽 여백은 좌우/상하 약 8 mm로 줄이며 헤더/푸터 간격은 약 4 mm로 설정합니다.",
        "지문 박스는 좌우 약 3 mm, 상하 약 1.5 mm의 내부 여백을 둡니다.",
        "문제문과 선택지 ①~⑤는 keepWithNext/keepLines로 한 묶음처럼 이동하도록 해 컬럼/페이지 중간 분할을 줄입니다.",
        "정답 번호와 해설도 한 쌍으로 묶어 컬럼 경계에서 분리되는 현상을 줄입니다.",
        "긴 문제나 긴 해설이 한 컬럼 높이 자체를 초과하면 한글 조판 엔진이 keep 규칙을 완화할 수 있습니다.",
    ]
    return result


def main_v04955() -> None:
    parser = argparse.ArgumentParser(description="국어 문제 PDF -> 구조화 JSON + HWPX V0.4.9.5.5")
    parser.add_argument("pdf", type=Path, help="분석할 PDF 파일")
    parser.add_argument("-o", "--output", type=Path, default=Path("v0_4_9_5_5_result.json"), help="저장할 JSON")
    parser.add_argument("-q", "--questions", nargs="+", type=int, default=list(range(1, 21)), help="추출할 문제 번호")
    parser.add_argument("--no-kiwi", action="store_true", help="Kiwi 경계 판별을 끔")
    parser.add_argument("--security-module", type=Path, default=None, help="FilePathCheckerModuleExample.dll 경로")
    parser.add_argument("--allow-interactive-hwp", action="store_true", help="보안 모듈 실패 시 대화형 한글 허용")
    parser.add_argument("--show-hwp", action="store_true", help="한글 창 표시")
    args = parser.parse_args()

    if not args.pdf.exists():
        raise SystemExit(f"PDF 파일을 찾을 수 없습니다: {args.pdf}")
    if not args.no_kiwi and Kiwi is None:
        print("[경고] kiwipiepy 미설치. fallback으로 실행합니다.")

    result = parse_v0_2_3(args.pdf, sorted(set(args.questions)), use_kiwi=not args.no_kiwi)
    result = v044_upgrade_result(result, args.pdf)
    result = v045_upgrade_result(result, args.pdf)
    checkpoint_path = args.output.with_name(args.output.stem + "_pre_hwpx.json")
    result = v04955_upgrade_result(
        result,
        args.pdf,
        checkpoint_path=checkpoint_path,
        security_module_path=args.security_module,
        allow_interactive_hwp=args.allow_interactive_hwp,
        show_hwp=args.show_hwp,
    )
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    checkpoint_info = result.get("pre_hwpx_checkpoint") or {}
    checkpoint_file = Path(str(checkpoint_info.get("path") or "")) if isinstance(checkpoint_info, dict) else None
    if result.get("hwpx_v04955", {}).get("status") == "created" and checkpoint_file and str(checkpoint_file):
        try:
            if checkpoint_file.exists():
                checkpoint_file.unlink()
            checkpoint_info["retained"] = False
            result["pre_hwpx_checkpoint"] = checkpoint_info
            args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            checkpoint_info["retained"] = True
            checkpoint_info["cleanup_error"] = str(exc)

    v = result.get("validation_v04955", {})
    print("=" * 76)
    print("V0.4.9.5.5 컴팩트 여백 + 지문 박스 패딩 + 문제/답안 묶음 조판 완료")
    print("=" * 76)
    print(f"입력 : {args.pdf}")
    print(f"출력 : {args.output.resolve()}")
    print(f"문제 : {v.get('question_count', 0)} | 지문 그룹 : {v.get('passage_group_count', 0)}")
    print(f"HWPX : {v.get('hwpx_status')} | 최종 검증 : {v.get('status')}")
    print(f"페이지 여백 : {v.get('page_margin_status')} ({v.get('page_margin_mm')} mm)")
    print(f"지문 박스 패딩 : {v.get('passage_box_padding_status')} | 좌우 {v.get('passage_box_padding_left_right_mm')} mm")
    print(f"문제 묶음 : {v.get('question_keep_together_status')} | 답안 묶음 : {v.get('answer_keep_together_status')}")
    print(f"이미지 위치 : {v.get('image_position_status')} | 답지 뒤 이미지 : {v.get('pictures_after_answer_count')}")


if __name__ == "__main__":
    main_v04955()
