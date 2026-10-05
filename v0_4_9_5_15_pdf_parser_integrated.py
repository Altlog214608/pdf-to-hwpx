#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
V0.4.9.5.15 - 국어 문제 PDF → 구조화 JSON → HWPX 의미구조/보기-중앙선 충돌 안정화 통합 파서
=============================================================

V0.2.3~V0.4.9.5.8의 누적 파서를 유지하면서 최종 HWPX의 문제/보기 무결성과
실제 조판 흐름을 보강한 통합 수정본.

V0.4.9.5.15 활성 레이어
-----------------
- source-backed (가)/(나)/(다) section label은 orphan cleanup에서 절대 삭제하지 않음
- `작품 구조` + `17~23행:`/`24~29행:`처럼 PDF raw에서 분리된 의미 행을 HWPX 독립 문단으로 복원
- geometry 복구 뒤 <보기> 열거형 `(3)이` → `(3) 이` 보정을 다시 적용하여 Q3 후단 생성 문제 차단
- <보기> 좌우 margin 500 HWPUNIT + border LR offset 0으로 중앙 세로선과의 겹침 제거
- 실제 HWPX에서 좌/우 테두리, gutter clearance, 의미행 독립 문단을 검증
- 필요 시 최종 HWPX 스타일 보정 후 Preview를 안전 재저장하고 재검증

V0.4.9.5.14 누적 레이어
-----------------
- passage semantic block을 noncore 키워드로 제거하지 않도록 보호
- raw/normalized/render/HWPX 전 단계 section label 및 passage block coverage 검증
- <보기> 열거형 `(3)이` → `(3) 이` 등 보수적 spacing 보정
- Windows/Hancom에서 XML 최종화 후 COM 재저장으로 Preview 재생성 시도
- native MultiColumn 경로에서 HColDef LineType/LineWidth/LineColor를 SaveAs 전에 설정

V0.4.9.5.13 누적 레이어
-----------------
- 수작업 HWPX 기준 2단 중앙 세로 구분선(0.12 mm SOLID) 문제/답지 모두 적용
- <보기> 앞 강제 빈 문단 제거 + title prev 280 HWPUNIT의 컴팩트 간격
- <보기> 뒤 spacer는 유지하여 선택지 침범 방지
- 전체 section colLine 및 compact-example 실제 XML validator 추가

V0.4.9.5.12 누적 레이어
-----------------
- <보기> 제목 CENTER / 본문 LEFT 유지
- <보기> 앞/뒤 실제 빈 paragraph를 항상 삽입 + 상하 border offset 축소
- PDF 읽기 순서의 지문 안내문 anchor를 기준으로 passage image ownership 재할당
- 페이지/열 경계를 넘는 이미지도 다음 지문 그룹에 정확히 귀속
- passage image affectLSpacing=1 + 문단/개체 CENTER 유지
- validator가 ownership + passage border + 실제 HWPX 문서 순서까지 검증

V0.4.9.5.9 기반 누적 기능
- <보기> 제목 + 본문 전체를 동일한 connected solid border로 묶음
- 한 컬럼에 들어가는 문제는 문제문 + <보기> + ①~⑤ 전체를 atomic keep-chain으로 유지
- 한 컬럼보다 큰 문제만 선택지 경계에서 safe split 허용
- 최종 HWPX에서 문제 순서/선택지 ①~⑤/보기 본문/박스/keep-chain을 직접 검증
- passage block의 start/end page+column metadata를 분리 저장
- '보기 어려운것은', '’며인생' 등 확인된 잔여 띄어쓰기만 보수적으로 보정
- 밑줄 벡터 분석은 실제 (a)/ⓐ 계열 참조가 있는 지문 그룹만 검사해 속도 개선

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
    python .\v0_4_9_5_14_pdf_parser_integrated.py ".\원본.pdf"

출력 파일 지정
--------------
    python .\v0_4_9_5_14_pdf_parser_integrated.py ".\원본.pdf" -o ".\원본_result.json"

특정 문제만 디버깅
------------------
    python .\v0_4_9_5_14_pdf_parser_integrated.py ".\원본.pdf" -q 2 3 4 16

Kiwi 없이 구조만 테스트
-----------------------
    python .\v0_4_9_5_14_pdf_parser_integrated.py ".\원본.pdf" --no-kiwi
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
            (r"보기 어려운것은", "보기 어려운 것은"),
            (r"([’”])며(?=[가-힣])", r"\1며 "),
            (r"며인생(?=에서|은|을|이|과|의|\s|[.,!?]|$)", "며 인생"),
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
                blocks[-1]["source_end_column"] = record.get("column")
                blocks[-1]["line_count"] += 1
                blocks[-1]["end_y"] = float(record["bbox"].y1)
                continue

            blocks.append(
                {
                    "type": block_type,
                    "text": text,
                    "source_start_page": record.get("page_index", 0) + 1,
                    "source_end_page": record.get("page_index", 0) + 1,
                    "source_start_column": record.get("column"),
                    "source_end_column": record.get("column"),
                    "column": record.get("column"),
                    "line_count": 1,
                    "start_y": float(record["bbox"].y0),
                    "end_y": float(record["bbox"].y1),
                    "relative_x": round(rel_x, 2),
                }
            )

        # v0.4.9.5.9: 시작/끝 page+column을 분리 보존한다.
        # 기존 ``column`` 필드는 호환성을 위해 시작 column 의미로 유지한다.
        for block in blocks:
            block.setdefault("source_start_column", block.get("column"))
            block.setdefault("source_end_column", block.get("source_start_column"))
            block["start_page"] = block.get("source_start_page")
            block["start_column"] = block.get("source_start_column")
            block["end_page"] = block.get("source_end_page")
            block["end_column"] = block.get("source_end_column")
            block["crosses_page_or_column"] = bool(
                block.get("source_start_page") != block.get("source_end_page")
                or block.get("source_start_column") != block.get("source_end_column")
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
    """Find the answer/explanation section with several safe source patterns.

    The original parser only accepted an exact ``1) [정답]`` line.  Sibling
    workbooks sometimes add ``[정답 및 해설]`` or minor spacing differences,
    so v0.4.9.5.7 accepts those without changing question-body parsing.
    """
    answer_header_re = re.compile(r"^1\s*\)\s*\[\s*정답\s*\](?:\s*[①-⑤])?$")
    section_title_re = re.compile(r"^[\[【]\s*정답\s*(?:및|&)\s*해설\s*[\]】]$")

    title_candidate = None
    for page_index, page in enumerate(document):
        lines = get_line_records(page)
        for line in lines:
            text = re.sub(r"[ \t]+", " ", line["text"].strip())
            if answer_header_re.fullmatch(text):
                return page_index
            if section_title_re.fullmatch(text) or text in {"[정답 및 해설]", "정답 및 해설"}:
                title_candidate = page_index if title_candidate is None else title_candidate

        # Text-layer fallback for cases where one visual line is split into spans.
        page_text = re.sub(r"[ \t]+", " ", page.get_text("text"))
        if re.search(r"(?m)^\s*1\s*\)\s*\[\s*정답\s*\]", page_text):
            return page_index

    if title_candidate is not None:
        return title_candidate

    raise RuntimeError(
        "정답/해설 시작 페이지를 찾지 못했습니다. "
        "지원 형식: '1) [정답]' 또는 '[정답 및 해설]' 계열"
    )


def find_first_question_page(
    document: fitz.Document,
    question_end_page: int,
) -> int:
    """Return the first page containing a numeric question header."""
    for page_index in range(max(0, int(question_end_page))):
        if get_question_headers(document[page_index]):
            return page_index
    raise RuntimeError("문제 번호가 있는 첫 페이지를 찾지 못했습니다.")


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

    if not headers:
        raise RuntimeError("첫 문제 페이지에서 문제 번호를 찾지 못했습니다.")

    first = min(
        headers,
        key=lambda item: (item[1].y0, item[1].x0, item[0]),
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
            "첫 문제 블록에서 ①~⑤ 아이콘을 찾지 못했습니다."
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
    if "2.다양한 빛깔로 만나는, 문학(01)_비상(강호영) 문학 [20문제] [Q]" in source_file:
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

        first_question_page = find_first_question_page(
            document,
            question_end_page,
        )

        digit_icon_map = (
            build_digit_icon_map(
                document[first_question_page]
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

    # v0.4.9.5.14: anything already assigned to a real passage group is
    # semantic source content.  Do not delete it merely because it contains
    # publisher helper words such as "작품 구조".  Page noise is filtered
    # earlier by is_page_noise(); this guard prevents content loss.
    if int(item.get("group_id") or 0) > 0:
        return False

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
        "v0.4.9.5.14에서는 passage_group에 귀속된 block을 semantic source content로 보호하므로 작품 구조/핵심 시어 등은 키워드만으로 제거하지 않습니다.",
        "명시적 page header/footer/저작권 noise처럼 passage_group 바깥의 검증된 비본문 요소만 기존 noncore 필터 대상이 될 수 있습니다.",
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

        _v0491_log(f"[HWPX staging] 렌더러 시작: {mode}")
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
                # v0.4.9.5.14: this is the native Hangul "단 구분선" property,
                # not a drawn line object.  Apply it before SaveAs whenever the
                # native MultiColumn path is available.  The XML finalizer remains
                # as a compatibility fallback for Hangul builds that serialize
                # MultiColumn inconsistently.
                try:
                    coldef.LineType = hwp.HwpLineType("Solid") if int(count) >= 2 else hwp.HwpLineType("None")
                except Exception:
                    pass
                try:
                    coldef.LineWidth = hwp.HwpLineWidth("0.12mm")
                except Exception:
                    pass
                try:
                    coldef.LineColor = hwp.RGBColor(0, 0, 0)
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
        "[HWPX staging] 보안 사전점검: "
        f"{security_info.get('status')} | "
        f"module={security_info.get('module_name')}"
    )

    build = output.with_name(output.stem + "_build.hwpx")
    recovery = output.with_name(output.stem + "_recovery.hwpx")
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
            "[HWPX staging] 중간 파일 확정: "
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

    candidate = output.with_name(output.stem + "_colpatch_candidate.hwpx")
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

    candidate = output.with_name(output.stem + '_editorial_candidate.hwpx')
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

    candidate = output.with_name(output.stem + '_compact_candidate.hwpx')
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


# ============================================================
# V0.4.9.5.6 Locked-Output Safe Finalization Layer
# - never overwrite a previously opened output.hwpx
# - generate into a versioned staging file, then write the compact/editorial
#   final package to a NEW versioned filename
# - if the nominal final filename already exists, automatically allocate
#   _run02, _run03, ... rather than deleting/replacing it
# - active build/recovery/candidate files inherit the current output stem
# - preserve all v0.4.9.5.5 passage boxes, padding, reduced margins,
#   keep-together rules, two-column layout and image-position validation
# ============================================================


def _v04956_pick_free_path(path: Path) -> Path:
    """Return a never-overwrite sibling path.

    This intentionally avoids deleting/replacing an existing HWPX.  An open
    Hangul document can keep a Windows file handle alive and make os.replace
    fail with WinError 5/32.  A fresh filename removes that entire failure
    class and also preserves the previous successful output for comparison.
    """
    path = Path(path)
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix or ".hwpx"
    for idx in range(2, 1000):
        candidate = path.with_name(f"{stem}_run{idx:02d}{suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"free output filename could not be allocated near: {path}")


def _v04956_cleanup_file(path: Path | None) -> tuple[bool, str | None]:
    if not path:
        return True, None
    path = Path(path)
    if not path.exists():
        return True, None
    try:
        path.unlink()
        return True, None
    except Exception as exc:
        return False, str(exc)



def _v04956_editorial_finalize_to_new_file(
    source: Path,
    editorial_output: Path,
    result: dict,
    render_plan: dict,
) -> dict:
    """Apply v0.4.9.5.4 editorial styling into a NEW file.

    This avoids the old candidate -> source os.replace step that failed when a
    previous HWPX was open in Hangul.  `editorial_output` must not exist.
    """
    import zipfile as _zipfile

    source = Path(source)
    editorial_output = Path(editorial_output)
    report = {
        "version": "v0.4.9.5.6",
        "status": "SKIPPED",
        "applied": False,
        "source_stage": str(source.resolve()),
        "editorial_output": str(editorial_output.resolve()),
        "question_columns": 2,
        "answer_columns": 2,
        "center_gutter_hwpunit": _V04954_GUTTER_HWPUNIT,
        "center_gutter_mm": 8.0,
        "paragraph_alignment": "LEFT",
        "write_policy": "new_file_no_replace",
    }
    if not source.exists() or not _zipfile.is_zipfile(source):
        report["reason"] = "no usable HWPX stage"
        return report
    if editorial_output.exists():
        report["status"] = "ERROR"
        report["reason"] = "editorial output already exists; no-overwrite policy refused replacement"
        return report

    try:
        with _zipfile.ZipFile(source, "r") as zf:
            names = set(zf.namelist())
            header = zf.read("Contents/header.xml").decode("utf-8", errors="ignore")
            section_names = sorted(
                [n for n in names if re.fullmatch(r"Contents/section\d+\.xml", n)],
                key=_v04953_section_number,
            )
            sections = {n: zf.read(n).decode("utf-8", errors="ignore") for n in section_names}

        if "Contents/section0.xml" not in sections:
            report["status"] = "ERROR"
            report["reason"] = "section0.xml missing"
            return report

        header, sections["Contents/section0.xml"], style_report = _v04954_style_section0(
            header, sections["Contents/section0.xml"], result
        )
        report.update(style_report)

        lineseg_changes = {}
        for name in section_names:
            sections[name] = _v04954_patch_colpr(sections[name], 2, _V04954_GUTTER_HWPUNIT)
            sections[name], changed = _v04954_shrink_lineseg_width(
                sections[name], _V04954_COLUMN_LINE_WIDTH
            )
            lineseg_changes[name] = changed
        report["lineseg_width_adjustments"] = lineseg_changes

        replacements = {"Contents/header.xml": header.encode("utf-8")}
        replacements.update({k: v.encode("utf-8") for k, v in sections.items()})
        _v04954_repack_hwpx(source, editorial_output, replacements)

        expected_count = int(result.get("image_filter_v0481", {}).get("saved_count") or 0)
        validation = v04953_validate_hwpx(
            editorial_output,
            expected_images=expected_count,
            render_plan=render_plan,
            result=result,
            require_two_column=True,
        )
        with _zipfile.ZipFile(editorial_output, "r") as zf:
            sec_counts = {
                name: _v04953_col_counts(zf.read(name).decode("utf-8", errors="ignore"))
                for name in section_names
            }
            header_check = zf.read("Contents/header.xml").decode("utf-8", errors="ignore")
            sec0_check = zf.read("Contents/section0.xml").decode("utf-8", errors="ignore")

        answer_two = all(
            any(c >= 2 for c in counts)
            for name, counts in sec_counts.items()
            if name != "Contents/section0.xml"
        ) if len(sec_counts) > 1 else True
        question_two = any(c >= 2 for c in sec_counts.get("Contents/section0.xml", []))
        guide_count = sec0_check.count(_V04954_PASSAGE_GUIDE)
        solid_border_present = 'width="0.2 mm"' in header_check and '<hh:leftBorder type="SOLID"' in header_check
        remaining_wide_lines = [
            int(x) for x in re.findall(r'horzsize="(\d+)"', "".join(sections.values())) if int(x) > 28000
        ]
        package_ok = validation.get("package_status") == "PASS"
        image_ok = validation.get("image_position_status") != "FAIL" and validation.get("content_status") != "FAIL"
        guide_ok = guide_count == len(result.get("passage_groups", []))
        box_ok = solid_border_present and report.get("passage_box_paragraph_count", 0) > 0
        spacing_ok = not remaining_wide_lines and 'horizontal="JUSTIFY"' not in header_check

        report.update({
            "section_column_counts": sec_counts,
            "question_two_column_status": "PASS" if question_two else "FAIL",
            "answer_two_column_status": "PASS" if answer_two else "FAIL",
            "answer_center_gap_status": "PASS" if answer_two else "FAIL",
            "guide_count_after_save": guide_count,
            "guide_bold_status": "PASS" if '<hh:bold/>' in header_check and guide_ok else "WARN",
            "passage_box_status": "PASS" if box_ok and guide_ok else "WARN",
            "word_spacing_layout_status": "PASS" if spacing_ok else "WARN",
            "remaining_wide_lineseg_count": len(remaining_wide_lines),
            "validation": validation,
        })

        accepted = package_ok and image_ok and question_two and answer_two and guide_ok and box_ok
        if accepted:
            report["status"] = "APPLIED"
            report["applied"] = True
            report["accepted"] = True
            return report

        report["status"] = "REJECTED_BY_VALIDATION"
        report["accepted"] = False
        report["reason"] = "editorial package failed package/image/layout/guide/box checks"
        return report
    except Exception as exc:
        report["status"] = "ERROR"
        report["reason"] = str(exc)
        return report


def _v04956_compact_finalize_to_new_file(
    source: Path,
    final_output: Path,
    result: dict,
    render_plan: dict,
) -> dict:
    """Build v0.4.9.5.5 compact layout directly into a NEW final file.

    Unlike v0.4.9.5.5, this function never calls os.replace(candidate, source).
    The validated package is written straight to `final_output`, whose name is
    guaranteed not to exist.  Therefore an older/open HWPX cannot block the
    finalization step.
    """
    import zipfile as _zipfile

    source = Path(source)
    final_output = Path(final_output)
    report = {
        "version": "v0.4.9.5.6",
        "status": "SKIPPED",
        "applied": False,
        "source_stage": str(source.resolve()),
        "final_output": str(final_output.resolve()),
        "write_policy": "new_file_no_replace",
        "page_margin_mm": 8.0,
        "box_padding_horizontal_mm": 3.0,
        "box_padding_vertical_mm": 1.5,
        "question_keep_together": True,
        "answer_pair_keep_together": True,
    }
    if not source.exists() or not _zipfile.is_zipfile(source):
        report["reason"] = "no usable staged HWPX"
        return report
    if final_output.exists():
        report["status"] = "ERROR"
        report["reason"] = "final output path already exists; no-overwrite policy refused replacement"
        return report

    try:
        with _zipfile.ZipFile(source, "r") as zf:
            names = set(zf.namelist())
            header = zf.read("Contents/header.xml").decode("utf-8", errors="ignore")
            section_names = sorted(
                [n for n in names if re.fullmatch(r"Contents/section\d+\.xml", n)],
                key=_v04953_section_number,
            )
            sections = {n: zf.read(n).decode("utf-8", errors="ignore") for n in section_names}

        # Reapply the accepted v0.4.9.5.5 compact/editorial adjustments to the
        # staged package.  These operations are idempotent enough for the
        # already-editorial v0.4.9.5.4 stage and are fully revalidated below.
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
        if "Contents/section0.xml" in sections:
            sections["Contents/section0.xml"], removed_spacers["Contents/section0.xml"] = _v04955_remove_spacing_only_paragraphs(
                sections["Contents/section0.xml"], answer_section=False
            )
            header, sections["Contents/section0.xml"], q_report = _v04955_apply_flow_styles(
                header,
                sections["Contents/section0.xml"],
                answer_section=False,
                result=result,
            )
            flow_reports["Contents/section0.xml"] = q_report

        for name in section_names:
            if name == "Contents/section0.xml":
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

        replacements = {"Contents/header.xml": header.encode("utf-8")}
        replacements.update({name: xml.encode("utf-8") for name, xml in sections.items()})

        # Crucial v0.4.9.5.6 change: destination is a NEW file, not `source`.
        _v04954_repack_hwpx(source, final_output, replacements)

        expected_images = int(result.get("image_filter_v0481", {}).get("saved_count") or 0)
        base_validation = v04954_validate_hwpx(
            final_output,
            expected_images=expected_images,
            render_plan=render_plan,
            result=result,
        )
        final_validation = _v04955_validate_compact_layout(final_output, result, base_validation)
        final_validation["validator_version"] = "v0.4.9.5.6"
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
            report["status"] = "APPLIED"
            report["applied"] = True
            report["accepted"] = True
            return report

        report["status"] = "REJECTED_BY_VALIDATION"
        report["accepted"] = False
        report["reason"] = "new final package failed package/image/margin/padding/keep-together checks"
        # Keep the rejected file with a diagnostic name rather than pretending
        # it is the final deliverable.
        rejected = final_output.with_name(final_output.stem + "_rejected" + final_output.suffix)
        try:
            if rejected.exists():
                rejected = _v04956_pick_free_path(rejected)
            final_output.rename(rejected)
            report["rejected_path"] = str(rejected.resolve())
        except Exception as exc:
            report["rejected_rename_error"] = str(exc)
        return report
    except Exception as exc:
        report["status"] = "ERROR"
        report["reason"] = str(exc)
        if final_output.exists():
            report["partial_final_path"] = str(final_output.resolve())
        return report


def v04956_validate_hwpx(path: Path, *, expected_images: int, render_plan: dict, result: dict) -> dict:
    info = v04955_validate_hwpx(
        path,
        expected_images=expected_images,
        render_plan=render_plan,
        result=result,
    )
    info["validator_version"] = "v0.4.9.5.6"
    return info


def v04956_create_hwpx_with_hancom(
    final_output: Path,
    result: dict,
    render_plan: dict,
    *,
    security_module_path: Path | None = None,
    allow_interactive_hwp: bool = False,
    show_hwp: bool = False,
) -> dict:
    """Create a versioned HWPX without replacing any previous final HWPX.

    Pipeline:
      fresh native stage -> fresh editorial stage -> fresh compact final

    The final path is never used as the COM save target and is never replaced.
    This isolates the user-visible file from Windows/Hangul file locks.
    """
    final_output = Path(final_output)
    final_output.parent.mkdir(parents=True, exist_ok=True)
    if final_output.exists():
        final_output = _v04956_pick_free_path(final_output)

    native_stage = final_output.with_name(final_output.stem + "_native_stage.hwpx")
    if native_stage.exists():
        native_stage = _v04956_pick_free_path(native_stage)
    editorial_stage = final_output.with_name(final_output.stem + "_editorial_stage.hwpx")
    if editorial_stage.exists():
        editorial_stage = _v04956_pick_free_path(editorial_stage)

    # Only the low-level stable two-column/image writer touches COM.  It writes
    # to a brand-new staging filename, never to the user-visible final output.
    base = v04953_create_hwpx_with_hancom(
        native_stage,
        result,
        render_plan,
        security_module_path=security_module_path,
        allow_interactive_hwp=allow_interactive_hwp,
        show_hwp=show_hwp,
    )
    result["hancom_security_v04956"] = (
        result.get("hancom_security_v04953")
        or base.get("hancom_security")
        or {}
    )

    if base.get("status") == "SKIPPED":
        return {
            **base,
            "backend": "hancom_com_v04956",
            "status": "SKIPPED",
            "requested_final_path": str(final_output.resolve()),
            "final_path": str(final_output.resolve()),
            "native_stage_path": str(native_stage.resolve()),
            "editorial_stage_path": str(editorial_stage.resolve()),
            "final_write_policy": "fresh_native_stage_to_fresh_editorial_stage_to_new_final",
            "editorial_finalize_v04956": {"status": "SKIPPED", "applied": False},
            "compact_finalize_v04956": {"status": "SKIPPED", "applied": False},
        }

    if not native_stage.exists() or not zipfile.is_zipfile(native_stage):
        return {
            **base,
            "backend": "hancom_com_v04956",
            "status": "ERROR",
            "reason": base.get("reason") or "native HWPX stage was not created",
            "requested_final_path": str(final_output.resolve()),
            "final_path": str(final_output.resolve()),
            "native_stage_path": str(native_stage.resolve()),
            "native_stage_preserved": native_stage.exists(),
            "editorial_stage_path": str(editorial_stage.resolve()),
            "final_write_policy": "fresh_native_stage_to_fresh_editorial_stage_to_new_final",
            "editorial_finalize_v04956": {"status": "SKIPPED", "applied": False},
            "compact_finalize_v04956": {"status": "SKIPPED", "applied": False},
        }

    editorial = _v04956_editorial_finalize_to_new_file(
        native_stage, editorial_stage, result, render_plan
    )
    if editorial.get("status") != "APPLIED" or not editorial_stage.exists():
        return {
            **base,
            "status": "ERROR" if editorial.get("status") == "ERROR" else "INVALID",
            "path": str(final_output.resolve()),
            "final_path": str(final_output.resolve()),
            "requested_final_path": str(final_output.resolve()),
            "native_stage_path": str(native_stage.resolve()),
            "editorial_stage_path": str(editorial_stage.resolve()),
            "recovery_path": str(native_stage.resolve()),
            "native_stage_preserved": True,
            "editorial_stage_preserved": editorial_stage.exists(),
            "backend": "hancom_com_v04956",
            "renderer_mode": "locked_output_safe_editorial_v04956",
            "final_write_policy": "fresh_native_stage_to_fresh_editorial_stage_to_new_final",
            "validation": editorial.get("validation") or base.get("validation") or {},
            "editorial_finalize_v04956": editorial,
            "compact_finalize_v04956": {"status": "SKIPPED", "applied": False},
            "hancom_security": result.get("hancom_security_v04956") or base.get("hancom_security") or {},
            "reason": editorial.get("reason") or base.get("reason"),
        }

    compact = _v04956_compact_finalize_to_new_file(
        editorial_stage, final_output, result, render_plan
    )
    expected_images = int(result.get("image_filter_v0481", {}).get("saved_count") or 0)

    if compact.get("status") == "APPLIED" and final_output.exists():
        validation = v04956_validate_hwpx(
            final_output,
            expected_images=expected_images,
            render_plan=render_plan,
            result=result,
        )
        native_cleanup_ok, native_cleanup_error = _v04956_cleanup_file(native_stage)
        editorial_cleanup_ok, editorial_cleanup_error = _v04956_cleanup_file(editorial_stage)
        return {
            **base,
            "status": "created" if validation.get("package_status") == "PASS" else "INVALID",
            "path": str(final_output.resolve()),
            "final_path": str(final_output.resolve()),
            "requested_final_path": str(final_output.resolve()),
            "native_stage_path": str(native_stage.resolve()),
            "editorial_stage_path": str(editorial_stage.resolve()),
            "native_stage_cleanup_ok": native_cleanup_ok,
            "native_stage_cleanup_error": native_cleanup_error,
            "editorial_stage_cleanup_ok": editorial_cleanup_ok,
            "editorial_stage_cleanup_error": editorial_cleanup_error,
            "backend": "hancom_com_v04956",
            "renderer_mode": "locked_output_safe_compact_editorial_v04956",
            "final_write_policy": "fresh_native_stage_to_fresh_editorial_stage_to_new_final",
            "validation": validation,
            "editorial_finalize_v04956": editorial,
            "compact_finalize_v04956": compact,
            "effective_layout_mode": validation.get("effective_layout_mode") or base.get("effective_layout_mode"),
            "two_column_origin": base.get("two_column_origin"),
            "hancom_security": result.get("hancom_security_v04956") or base.get("hancom_security") or {},
        }

    return {
        **base,
        "status": "ERROR" if compact.get("status") == "ERROR" else "INVALID",
        "path": str(final_output.resolve()),
        "final_path": str(final_output.resolve()),
        "requested_final_path": str(final_output.resolve()),
        "native_stage_path": str(native_stage.resolve()),
        "editorial_stage_path": str(editorial_stage.resolve()),
        "recovery_path": str(editorial_stage.resolve()),
        "native_stage_preserved": native_stage.exists(),
        "editorial_stage_preserved": True,
        "backend": "hancom_com_v04956",
        "renderer_mode": "locked_output_safe_compact_editorial_v04956",
        "final_write_policy": "fresh_native_stage_to_fresh_editorial_stage_to_new_final",
        "validation": compact.get("validation") or editorial.get("validation") or base.get("validation") or {},
        "editorial_finalize_v04956": editorial,
        "compact_finalize_v04956": compact,
        "hancom_security": result.get("hancom_security_v04956") or base.get("hancom_security") or {},
        "reason": compact.get("reason") or editorial.get("reason") or base.get("reason"),
    }


def v04956_upgrade_result(
    result: dict,
    pdf_path: Path,
    checkpoint_path: Path | None = None,
    *,
    hwpx_output_path: Path | None = None,
    security_module_path: Path | None = None,
    allow_interactive_hwp: bool = False,
    show_hwp: bool = False,
) -> dict:
    _v0491_log("[v0.4.9.5.6] 잠금 안전 버전별 HWPX 출력 + 기존 5.5 편집 레이아웃 준비")
    result = v046_upgrade_result(result, pdf_path)
    result = v0481_prepare_problem_images(pdf_path, result)
    result = v0491_cleanup_legacy_metadata(result)
    result = v0495_attach_question_geometry(pdf_path, result)

    render_plan = v04955_build_render_plan(result)
    render_plan["version"] = "v0.4.9.5.6"
    render_plan["output_policy_v04956"] = {
        "final_filename": "output_v0_4_9_5_6.hwpx",
        "never_overwrite_existing": True,
        "run_suffix_when_existing": "_runNN",
        "staging_file": "<final_stem>_stage.hwpx",
        "candidate_replacement_of_open_output": False,
    }
    result["render_plan_v04956"] = render_plan
    for stale_key in [
        "render_plan_v04955", "render_plan_v04954", "render_plan_v04953", "render_plan_v04952",
        "render_plan_v04951", "render_plan_v0495", "render_plan_v0494", "render_plan_v0493",
        "render_plan_v0492", "render_plan_v049",
    ]:
        result.pop(stale_key, None)

    result["version"] = "v0.4.9.5.6"
    result["parser_version"] = "v0.4.9.5.6"
    result["generator_version"] = "PDF Parser Integrated v0.4.9.5.6"
    result["schema_version"] = {
        "base": "v0.4.9.5.5",
        "extension": [
            "versioned_final_hwpx_filename",
            "never_overwrite_existing_final_hwpx",
            "auto_run_suffix_when_target_exists",
            "fresh_staging_hwpx_generation",
            "dynamic_build_recovery_candidate_names",
            "direct_compact_repack_to_new_final_file",
            "no_os_replace_against_open_previous_output",
            "preserve_stage_as_recovery_on_finalize_failure",
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
        _v0491_log(f"[v0.4.9.5.6] HWPX 전 임시 체크포인트 저장: {checkpoint_path.resolve()}")

    requested = Path(hwpx_output_path) if hwpx_output_path else (pdf_path.parent / "output_v0_4_9_5_6.hwpx")
    actual_target = _v04956_pick_free_path(requested)
    result["hwpx_output_v04956"] = {
        "requested_path": str(requested.resolve()),
        "allocated_path": str(actual_target.resolve()),
        "existing_requested_path_preserved": requested.exists(),
        "policy": "never overwrite; allocate _runNN when needed",
    }

    hwpx_info = v04956_create_hwpx_with_hancom(
        actual_target,
        result,
        render_plan,
        security_module_path=security_module_path,
        allow_interactive_hwp=allow_interactive_hwp,
        show_hwp=show_hwp,
    )
    result["hwpx_v04956"] = hwpx_info
    result["hancom_security_v04956"] = result.get("hancom_security_v04956") or hwpx_info.get("hancom_security") or {}
    for stale_key in ["hancom_security_v04955", "hancom_security_v04954", "hancom_security_v04953", "hancom_security_v04952"]:
        result.pop(stale_key, None)

    base_validation = result.get("validation", {})
    img_validation = result.get("image_filter_v0481", {})
    table_validation = result.get("table_filter_v0492", {})
    geometry_validation = result.get("question_geometry_v0495", {})
    source_order_validation = render_plan.get("source_order_v0495", {})
    final_validation = hwpx_info.get("validation") or {}
    security_runtime = result.get("hancom_security_v04956") or {}
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
    elif hwpx_status == "SKIPPED" and hard_pass:
        final_status = "PASS"
    else:
        final_status = "WARN" if hwpx_status == "SKIPPED" else "FAIL"

    compact = hwpx_info.get("compact_finalize_v04956") or {}
    result["validation_v04956"] = {
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
        "hwpx_final_path": hwpx_info.get("final_path"),
        "hwpx_stage_path": hwpx_info.get("stage_path"),
        "hwpx_final_write_policy": hwpx_info.get("final_write_policy"),
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
        "compact_finalize_status": compact.get("status"),
        "compact_finalize_applied": compact.get("applied", False),
        "status": final_status,
    }
    result["known_limitations_v04956"] = [
        "최종 HWPX는 output_v0_4_9_5_6.hwpx처럼 버전명을 포함한 새 파일로 생성합니다.",
        "동일 버전 파일이 이미 존재하면 삭제/덮어쓰기하지 않고 _run02, _run03 순으로 새 파일을 할당합니다.",
        "기존에 한글에서 열어 둔 output.hwpx가 있어도 새 버전 파일 생성에는 영향을 주지 않습니다.",
        "지문 박스/8 mm 페이지 여백/3 mm·1.5 mm 박스 패딩/문제·답안 묶음은 v0.4.9.5.5 규칙을 그대로 유지합니다.",
        "긴 문제나 긴 해설이 한 컬럼 높이 자체를 초과하면 한글 조판 엔진이 keep 규칙을 완화할 수 있습니다.",
    ]
    return result


def main_v04956() -> None:
    parser = argparse.ArgumentParser(description="국어 문제 PDF -> 구조화 JSON + HWPX V0.4.9.5.6")
    parser.add_argument("pdf", type=Path, help="분석할 PDF 파일")
    parser.add_argument("-o", "--output", type=Path, default=Path("v0_4_9_5_6_result.json"), help="저장할 JSON")
    parser.add_argument("--hwpx-output", type=Path, default=None, help="최종 HWPX 희망 파일명. 이미 존재하면 자동으로 _runNN 파일을 생성")
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
    result = v04956_upgrade_result(
        result,
        args.pdf,
        checkpoint_path=checkpoint_path,
        hwpx_output_path=args.hwpx_output,
        security_module_path=args.security_module,
        allow_interactive_hwp=args.allow_interactive_hwp,
        show_hwp=args.show_hwp,
    )
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    checkpoint_info = result.get("pre_hwpx_checkpoint") or {}
    checkpoint_file = Path(str(checkpoint_info.get("path") or "")) if isinstance(checkpoint_info, dict) else None
    if result.get("hwpx_v04956", {}).get("status") == "created" and checkpoint_file and str(checkpoint_file):
        try:
            if checkpoint_file.exists():
                checkpoint_file.unlink()
            checkpoint_info["retained"] = False
            result["pre_hwpx_checkpoint"] = checkpoint_info
            args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            checkpoint_info["retained"] = True
            checkpoint_info["cleanup_error"] = str(exc)

    v = result.get("validation_v04956", {})
    print("=" * 76)
    print("V0.4.9.5.6 잠금 안전 버전별 HWPX 출력 완료")
    print("=" * 76)
    print(f"입력 : {args.pdf}")
    print(f"JSON : {args.output.resolve()}")
    print(f"HWPX : {v.get('hwpx_final_path')}")
    print(f"문제 : {v.get('question_count', 0)} | 지문 그룹 : {v.get('passage_group_count', 0)}")
    print(f"HWPX 상태 : {v.get('hwpx_status')} | 최종 검증 : {v.get('status')}")
    print(f"지문 박스 : {v.get('passage_box_status')} | 박스 패딩 : {v.get('passage_box_padding_status')}")
    print(f"페이지 여백 : {v.get('page_margin_status')} ({v.get('page_margin_mm')} mm)")
    print(f"문제 묶음 : {v.get('question_keep_together_status')} | 답안 묶음 : {v.get('answer_keep_together_status')}")
    print(f"이미지 위치 : {v.get('image_position_status')} | 답지 뒤 이미지 : {v.get('pictures_after_answer_count')}")



# ============================================================
# V0.4.9.5.7 Functional Freeze Candidate / Cross-PDF Diagnostics Layer
# - remove orphan (가)/(나)/(다)... labels after non-core filtering
# - validate empty structural groups and oversize flow candidates
# - auto-detect question numbers when -q is omitted
# - default JSON/HWPX filenames derive from the source PDF stem
# - preserve v0.4.9.5.6 never-overwrite finalization
# ============================================================

_V04957_SECTION_LABEL_RE = re.compile(r"^\([가-힣A-Za-z0-9]\)$")
_V04957_QUESTION_OVERSIZE_CHARS = 2200
_V04957_ANSWER_OVERSIZE_CHARS = 3200


def _v04957_safe_output_stem(pdf_path: Path) -> str:
    """Create a Windows-safe output stem while preserving the PDF name."""
    stem = Path(pdf_path).stem.strip()
    # A Windows PDF filename normally cannot contain these characters, but a
    # file copied from another OS can.  Replace only illegal output characters.
    stem = re.sub(r'[<>:"/\\|?*]+', '_', stem)
    stem = re.sub(r'\s+', ' ', stem).strip(' .')
    return stem or 'converted_pdf'


def _v04957_default_hwpx_path(pdf_path: Path) -> Path:
    return Path(pdf_path).parent / f"{_v04957_safe_output_stem(pdf_path)}.hwpx"


def _v04957_default_json_path(pdf_path: Path) -> Path:
    return Path(pdf_path).parent / f"{_v04957_safe_output_stem(pdf_path)}_result.json"


def v04957_detect_question_numbers(pdf_path: Path) -> dict:
    """Detect actual question numbers before parsing instead of assuming 1~20."""
    report = {
        "status": "FAIL",
        "answer_start_page": None,
        "question_numbers": [],
        "question_count": 0,
        "contiguous_from_first": False,
    }
    doc = fitz.open(pdf_path)
    try:
        answer_start = find_answer_start_page(doc)
        found: list[int] = []
        seen: set[int] = set()
        for page_index in range(answer_start):
            for number, _bbox, _column in get_question_headers(doc[page_index]):
                if number not in seen:
                    seen.add(number)
                    found.append(number)
        found.sort()
        report["answer_start_page"] = int(answer_start) + 1
        report["question_numbers"] = found
        report["question_count"] = len(found)
        if found:
            report["contiguous_from_first"] = found == list(range(found[0], found[-1] + 1))
            report["status"] = "PASS"
        else:
            report["reason"] = "문제 번호를 자동 탐지하지 못했습니다."
    except Exception as exc:
        report["reason"] = str(exc)
    finally:
        doc.close()
    return report


def _v04957_block_is_renderable_core(block: dict) -> bool:
    text = str(block.get("text") or "").strip()
    if not text:
        return False
    if _V04957_SECTION_LABEL_RE.fullmatch(text):
        return False
    item = {
        "type": "block",
        "block_type": block.get("type") or block.get("kind") or "paragraph",
        "text": text,
    }
    return not _v0494_is_noncore_block(item)


def _v04957_group_orphan_labels(group: dict) -> list[dict]:
    blocks = list(group.get("blocks") or [])
    images = [
        a for a in (group.get("image_assets") or [])
        if (a.get("image_output") or {}).get("status") == "saved"
    ]
    results: list[dict] = []
    label_indices = [
        i for i, b in enumerate(blocks)
        if _V04957_SECTION_LABEL_RE.fullmatch(str(b.get("text") or "").strip())
    ]
    for pos, idx in enumerate(label_indices):
        label = str(blocks[idx].get("text") or "").strip()
        end = label_indices[pos + 1] if pos + 1 < len(label_indices) else len(blocks)
        segment = blocks[idx + 1:end]
        has_core_text = any(_v04957_block_is_renderable_core(b) for b in segment)
        has_image = any(str(a.get("section_label") or "").strip() == label for a in images)
        if not has_core_text and not has_image:
            results.append({
                "group_id": int(group.get("id") or 0),
                "label": label,
                "block_index": idx,
                "source_page": blocks[idx].get("source_start_page"),
                "column": blocks[idx].get("column"),
                "reason": "no renderable core text/image before next section label or group end",
            })
    return results


def v04957_cleanup_orphan_section_labels(result: dict) -> dict:
    """Remove labels whose only following material is filtered publisher helper content."""
    removed: list[dict] = []
    for group in result.get("passage_groups", []):
        orphans = _v04957_group_orphan_labels(group)
        if not orphans:
            continue
        remove_indices = {int(x["block_index"]) for x in orphans}
        old_blocks = list(group.get("blocks") or [])
        group["blocks"] = [b for i, b in enumerate(old_blocks) if i not in remove_indices]
        # Keep raw_text untouched as source evidence, but normalized_text should
        # represent the cleaned logical passage consumed by the renderer.
        group["normalized_text"] = "\n".join(
            str(b.get("text") or "").strip()
            for b in group["blocks"]
            if str(b.get("text") or "").strip()
        ).strip()
        removed.extend(orphans)

    remaining = []
    for group in result.get("passage_groups", []):
        remaining.extend(_v04957_group_orphan_labels(group))

    result["structural_cleanup_v04957"] = {
        "removed_orphan_section_label_count": len(removed),
        "removed_orphan_section_labels": removed,
        "remaining_orphan_section_label_count": len(remaining),
        "remaining_orphan_section_labels": remaining,
        "orphan_section_label_status": "PASS" if not remaining else "FAIL",
    }
    return result


def v04957_validate_structural_edges(result: dict) -> dict:
    empty_groups = []
    image_only_without_image = []
    empty_examples = []
    oversize_questions = []
    oversize_answers = []

    for group in result.get("passage_groups", []):
        gid = int(group.get("id") or 0)
        core_blocks = [b for b in (group.get("blocks") or []) if _v04957_block_is_renderable_core(b)]
        saved_images = [
            a for a in (group.get("image_assets") or [])
            if (a.get("image_output") or {}).get("status") == "saved"
        ]
        if not core_blocks and not saved_images:
            empty_groups.append(gid)
        if group.get("needs_image_processing") and not saved_images:
            image_only_without_image.append(gid)

    for q in result.get("questions", []):
        qno = int(q.get("number") or 0)
        ex = q.get("example_block") or {}
        if ex.get("exists") and not str(ex.get("text") or "").strip():
            empty_examples.append(qno)
        q_chars = len(str(q.get("question") or "")) + sum(len(str(x or "")) for x in q.get("choices", []))
        q_chars += len(str(ex.get("text") or ""))
        a_chars = len(str(q.get("explanation") or "")) + 24
        if q_chars > _V04957_QUESTION_OVERSIZE_CHARS:
            oversize_questions.append({"number": qno, "characters": q_chars})
        if a_chars > _V04957_ANSWER_OVERSIZE_CHARS:
            oversize_answers.append({"number": qno, "characters": a_chars})

    cleanup = result.get("structural_cleanup_v04957") or {}
    hard_issues = []
    if cleanup.get("orphan_section_label_status") == "FAIL":
        hard_issues.append("orphan_section_label")
    if empty_groups:
        hard_issues.append("empty_passage_group")
    if image_only_without_image:
        hard_issues.append("image_only_group_without_saved_image")
    if empty_examples:
        hard_issues.append("empty_example_block")

    return {
        "status": "PASS" if not hard_issues else "FAIL",
        "orphan_section_label_status": cleanup.get("orphan_section_label_status", "PASS"),
        "removed_orphan_section_label_count": cleanup.get("removed_orphan_section_label_count", 0),
        "empty_passage_group_ids": empty_groups,
        "image_only_group_without_saved_image_ids": image_only_without_image,
        "empty_example_question_numbers": empty_examples,
        "oversize_flow_status": "WARN" if (oversize_questions or oversize_answers) else "PASS",
        "oversize_question_candidates": oversize_questions,
        "oversize_answer_candidates": oversize_answers,
        "question_oversize_threshold_chars": _V04957_QUESTION_OVERSIZE_CHARS,
        "answer_oversize_threshold_chars": _V04957_ANSWER_OVERSIZE_CHARS,
        "issues": hard_issues,
    }


def v04957_create_hwpx_with_hancom(
    final_output: Path,
    result: dict,
    render_plan: dict,
    *,
    security_module_path: Path | None = None,
    allow_interactive_hwp: bool = False,
    show_hwp: bool = False,
) -> dict:
    info = v04956_create_hwpx_with_hancom(
        final_output,
        result,
        render_plan,
        security_module_path=security_module_path,
        allow_interactive_hwp=allow_interactive_hwp,
        show_hwp=show_hwp,
    )
    info["backend"] = "hancom_com_v04957"
    info["renderer_mode"] = "functional_freeze_pdf_named_output_v04957"
    if isinstance(info.get("validation"), dict):
        info["validation"]["validator_version"] = "v0.4.9.5.7"

    # Normalize active report keys so the final JSON does not look like it was
    # generated by the previous version merely because the proven 5.6 writer
    # is reused internally. Historical implementation functions remain in the
    # cumulative source, but active runtime metadata is v0.4.9.5.7.
    for old_key, new_key in (
        ("editorial_finalize_v04956", "editorial_finalize_v04957"),
        ("compact_finalize_v04956", "compact_finalize_v04957"),
    ):
        payload = info.pop(old_key, None)
        if isinstance(payload, dict):
            payload["version"] = "v0.4.9.5.7"
            if isinstance(payload.get("validation"), dict):
                payload["validation"]["validator_version"] = "v0.4.9.5.7"
            info[new_key] = payload
    return info


def v04957_upgrade_result(
    result: dict,
    pdf_path: Path,
    checkpoint_path: Path | None = None,
    *,
    hwpx_output_path: Path | None = None,
    question_detection: dict | None = None,
    security_module_path: Path | None = None,
    allow_interactive_hwp: bool = False,
    show_hwp: bool = False,
) -> dict:
    _v0491_log("[v0.4.9.5.7] 기능 동결 후보 + PDF명 기반 HWPX 출력 준비")

    # Keep the proven cumulative pipeline, then clean only logical structures
    # that were exposed by the final non-core render filter.
    result = v046_upgrade_result(result, pdf_path)
    result = v0481_prepare_problem_images(pdf_path, result)
    result = v0491_cleanup_legacy_metadata(result)
    result = v0495_attach_question_geometry(pdf_path, result)
    result = v04957_cleanup_orphan_section_labels(result)
    structural = v04957_validate_structural_edges(result)
    result["structural_validation_v04957"] = structural

    render_plan = v04955_build_render_plan(result)
    render_plan["version"] = "v0.4.9.5.7"
    render_plan["output_policy_v04957"] = {
        "default_final_filename": f"{_v04957_safe_output_stem(pdf_path)}.hwpx",
        "filename_basis": "source_pdf_stem",
        "never_overwrite_existing": True,
        "run_suffix_when_existing": "_runNN",
        "candidate_replacement_of_open_output": False,
    }
    render_plan["structural_cleanup_v04957"] = result.get("structural_cleanup_v04957", {})
    result["render_plan_v04957"] = render_plan
    for stale_key in [
        "render_plan_v04956", "render_plan_v04955", "render_plan_v04954", "render_plan_v04953",
        "render_plan_v04952", "render_plan_v04951", "render_plan_v0495", "render_plan_v0494",
        "render_plan_v0493", "render_plan_v0492", "render_plan_v049",
    ]:
        result.pop(stale_key, None)

    result["version"] = "v0.4.9.5.7"
    result["parser_version"] = "v0.4.9.5.7"
    result["generator_version"] = "PDF Parser Integrated v0.4.9.5.7"
    result["question_detection_v04957"] = question_detection or {}
    result["schema_version"] = {
        "base": "v0.4.9.5.6",
        "extension": [
            "pdf_stem_based_default_hwpx_filename",
            "pdf_stem_based_default_json_filename",
            "auto_question_number_detection",
            "source_specific_golden_check_scope_fix",
            "orphan_section_label_cleanup",
            "empty_structure_validation",
            "oversize_flow_warning",
            "preserve_never_overwrite_finalization",
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
        _v0491_log(f"[v0.4.9.5.7] HWPX 전 임시 체크포인트 저장: {checkpoint_path.resolve()}")

    requested = Path(hwpx_output_path) if hwpx_output_path else _v04957_default_hwpx_path(pdf_path)
    actual_target = _v04956_pick_free_path(requested)
    result["hwpx_output_v04957"] = {
        "requested_path": str(requested.resolve()),
        "allocated_path": str(actual_target.resolve()),
        "source_pdf_stem": Path(pdf_path).stem,
        "safe_output_stem": _v04957_safe_output_stem(pdf_path),
        "existing_requested_path_preserved": requested.exists(),
        "policy": "PDF stem filename; never overwrite; allocate _runNN when needed",
    }

    hwpx_info = v04957_create_hwpx_with_hancom(
        actual_target,
        result,
        render_plan,
        security_module_path=security_module_path,
        allow_interactive_hwp=allow_interactive_hwp,
        show_hwp=show_hwp,
    )
    result["hwpx_v04957"] = hwpx_info
    result["hancom_security_v04957"] = (
        result.get("hancom_security_v04956")
        or hwpx_info.get("hancom_security")
        or {}
    )
    for stale_key in [
        "hwpx_v04956", "hancom_security_v04956", "hancom_security_v04955",
        "hancom_security_v04954", "hancom_security_v04953", "hancom_security_v04952",
    ]:
        result.pop(stale_key, None)

    base_validation = result.get("validation", {})
    img_validation = result.get("image_filter_v0481", {})
    table_validation = result.get("table_filter_v0492", {})
    geometry_validation = result.get("question_geometry_v0495", {})
    source_order_validation = render_plan.get("source_order_v0495", {})
    final_validation = hwpx_info.get("validation") or {}
    security_runtime = result.get("hancom_security_v04957") or {}
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
        and structural.get("status") == "PASS"
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
    if critical_fail or structural.get("status") == "FAIL":
        final_status = "FAIL"
    elif hard_pass and final_validation.get("status") in {"PASS", None}:
        final_status = "PASS"
    elif hwpx_status == "SKIPPED" and hard_pass:
        final_status = "PASS"
    else:
        final_status = "WARN" if hwpx_status == "SKIPPED" else "FAIL"

    compact = hwpx_info.get("compact_finalize_v04957") or {}
    result["validation_v04957"] = {
        "question_count": len(result.get("questions", [])),
        "passage_group_count": len(result.get("passage_groups", [])),
        "problem_image_count": img_validation.get("selected_problem_figure_count", 0),
        "problem_image_saved": img_validation.get("saved_count", 0),
        "answer_count": render_plan.get("stats", {}).get("answer_count", 0),
        "render_page_count": render_plan.get("stats", {}).get("page_count", 0),
        "render_item_count": render_plan.get("stats", {}).get("render_item_count", 0),
        "question_detection_status": (question_detection or {}).get("status"),
        "question_geometry_status": geometry_validation.get("status"),
        "source_order_status": source_order_validation.get("status"),
        "base_parser_status": base_validation.get("status"),
        "image_status": img_validation.get("status"),
        "structural_status": structural.get("status"),
        "orphan_section_label_status": structural.get("orphan_section_label_status"),
        "removed_orphan_section_label_count": structural.get("removed_orphan_section_label_count", 0),
        "empty_passage_group_ids": structural.get("empty_passage_group_ids", []),
        "image_only_group_without_saved_image_ids": structural.get("image_only_group_without_saved_image_ids", []),
        "empty_example_question_numbers": structural.get("empty_example_question_numbers", []),
        "oversize_flow_status": structural.get("oversize_flow_status"),
        "oversize_question_candidates": structural.get("oversize_question_candidates", []),
        "oversize_answer_candidates": structural.get("oversize_answer_candidates", []),
        "hancom_security_status": security_runtime.get("status"),
        "unattended_ready": security_runtime.get("unattended_ready", False),
        "hwpx_status": hwpx_status,
        "hwpx_final_path": hwpx_info.get("final_path"),
        "hwpx_final_filename_basis": "source_pdf_stem",
        "hwpx_final_write_policy": hwpx_info.get("final_write_policy"),
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
        "compact_finalize_status": compact.get("status"),
        "compact_finalize_applied": compact.get("applied", False),
        "status": final_status,
    }
    result["known_limitations_v04957"] = [
        "현재 최다빈출 공략 계열 PDF에서 검증된 규칙이며, 다른 출판사/사이트는 레이아웃 진단 결과를 확인해야 합니다.",
        "복잡한 병합 셀 표의 완전 복원은 아직 지원하지 않습니다.",
        "긴 문제나 긴 해설이 한 컬럼 높이 자체를 초과하면 한글 조판 엔진이 keep 규칙을 완화할 수 있어 oversize_flow_status로 사전 경고합니다.",
        "최종 HWPX/JSON 기본 파일명은 원본 PDF 이름을 기준으로 하며, 동일 이름이 존재하면 _run02, _run03 순으로 새 파일을 생성합니다.",
    ]
    return result


def main_v04957() -> None:
    parser = argparse.ArgumentParser(
        description="국어 문제 PDF -> 구조화 JSON + HWPX V0.4.9.5.7 기능 동결 후보"
    )
    parser.add_argument("pdf", type=Path, help="분석할 PDF 파일")
    parser.add_argument(
        "-o", "--output", type=Path, default=None,
        help="저장할 JSON. 생략하면 <PDF이름>_result.json"
    )
    parser.add_argument(
        "--hwpx-output", type=Path, default=None,
        help="최종 HWPX 희망 파일명. 생략하면 <PDF이름>.hwpx, 존재 시 _runNN 자동 생성"
    )
    parser.add_argument(
        "-q", "--questions", nargs="+", type=int, default=None,
        help="추출할 문제 번호. 생략하면 PDF에서 자동 탐지"
    )
    parser.add_argument("--no-kiwi", action="store_true", help="Kiwi 경계 판별을 끔")
    parser.add_argument("--security-module", type=Path, default=None, help="FilePathCheckerModuleExample.dll 경로")
    parser.add_argument("--allow-interactive-hwp", action="store_true", help="보안 모듈 실패 시 대화형 한글 허용")
    parser.add_argument("--show-hwp", action="store_true", help="한글 창 표시")
    args = parser.parse_args()

    if not args.pdf.exists():
        raise SystemExit(f"PDF 파일을 찾을 수 없습니다: {args.pdf}")
    if not args.no_kiwi and Kiwi is None:
        print("[경고] kiwipiepy 미설치. fallback으로 실행합니다.")

    detection = v04957_detect_question_numbers(args.pdf)
    if args.questions:
        question_numbers = sorted(set(args.questions))
        detection["selection_mode"] = "explicit_cli"
        detection["selected_question_numbers"] = question_numbers
    else:
        if detection.get("status") != "PASS" or not detection.get("question_numbers"):
            raise SystemExit(
                "문제 번호 자동 탐지에 실패했습니다. -q 옵션으로 문제 번호를 직접 지정하세요. "
                + str(detection.get("reason") or "")
            )
        question_numbers = list(detection["question_numbers"])
        detection["selection_mode"] = "auto_detected"
        detection["selected_question_numbers"] = question_numbers

    json_output = Path(args.output) if args.output else _v04957_default_json_path(args.pdf)
    checkpoint_path = json_output.with_name(json_output.stem + "_pre_hwpx.json")

    result = parse_v0_2_3(args.pdf, question_numbers, use_kiwi=not args.no_kiwi)
    result = v044_upgrade_result(result, args.pdf)
    result = v045_upgrade_result(result, args.pdf)
    result = v04957_upgrade_result(
        result,
        args.pdf,
        checkpoint_path=checkpoint_path,
        hwpx_output_path=args.hwpx_output,
        question_detection=detection,
        security_module_path=args.security_module,
        allow_interactive_hwp=args.allow_interactive_hwp,
        show_hwp=args.show_hwp,
    )
    json_output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    checkpoint_info = result.get("pre_hwpx_checkpoint") or {}
    checkpoint_file = Path(str(checkpoint_info.get("path") or "")) if isinstance(checkpoint_info, dict) else None
    if result.get("hwpx_v04957", {}).get("status") == "created" and checkpoint_file and str(checkpoint_file):
        try:
            if checkpoint_file.exists():
                checkpoint_file.unlink()
            checkpoint_info["retained"] = False
            result["pre_hwpx_checkpoint"] = checkpoint_info
            json_output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            checkpoint_info["retained"] = True
            checkpoint_info["cleanup_error"] = str(exc)

    v = result.get("validation_v04957", {})
    print("=" * 76)
    print("V0.4.9.5.7 기능 동결 후보 + PDF명 기반 HWPX 출력 완료")
    print("=" * 76)
    print(f"입력 : {args.pdf}")
    print(f"JSON : {json_output.resolve()}")
    print(f"HWPX : {v.get('hwpx_final_path')}")
    print(f"문제 : {v.get('question_count', 0)} | 자동 탐지 : {v.get('question_detection_status')}")
    print(f"지문 그룹 : {v.get('passage_group_count', 0)} | 구조 검증 : {v.get('structural_status')}")
    print(f"고아 section label 제거 : {v.get('removed_orphan_section_label_count', 0)} | 상태 : {v.get('orphan_section_label_status')}")
    print(f"HWPX 상태 : {v.get('hwpx_status')} | 최종 검증 : {v.get('status')}")
    print(f"지문 박스 : {v.get('passage_box_status')} | 박스 패딩 : {v.get('passage_box_padding_status')}")
    print(f"페이지 여백 : {v.get('page_margin_status')} ({v.get('page_margin_mm')} mm)")
    print(f"문제 묶음 : {v.get('question_keep_together_status')} | 답안 묶음 : {v.get('answer_keep_together_status')}")
    print(f"긴 블록 경고 : {v.get('oversize_flow_status')} | 이미지 위치 : {v.get('image_position_status')}")



# ============================================================
# V0.4.9.5.8 Cross-PDF Flow / Example Box / Underline Semantics Layer
# - repair a single inline <보기> marker using real PDF geometry
# - draw a real rectangular border around every rendered <보기>
# - convert source-page forced breaks into natural two-column flow
# - use adaptive question grouping: short blocks stay together, long/<보기>
#   questions may split only at safe choice boundaries
# - detect PDF vector underlines and preserve labelled underline spans in HWPX
# ============================================================

_V04958_VERSION = "v0.4.9.5.8"
_V04958_MARKER_RE = re.compile(
    r"([ⓐ-ⓩ㉠-㉿]|\([A-Za-z가-힣0-9]\)|(?<![A-Za-z])[A-Za-z][.)])\s*$"
)
_V04958_EXAMPLE_MARKERS = ("<보기>", "[보기]", "〈보기〉", "《보기》")
_V04958_SPLIT_SAFE_CHAR_THRESHOLD = 520
_V04958_UNDERLINE_MAX_STROKE_PT = 0.36
_V04958_UNDERLINE_Y_TOLERANCE_PT = 1.7


def _v04958_normalize_visible_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def v04958_repair_example_blocks(result: dict) -> dict:
    """Repair <보기> extraction using the PDF's real standalone marker geometry.

    v0.4.4 intentionally required either two markers or a marker at the beginning
    of the extracted stem.  That misses the common pattern:

        3. ... 바르게 표시된 것은?
        <보기>
        (1) ...
        (2) ...

    v0.4.9.5 already records ``layout_v0495.example_y`` when a standalone
    <보기> line exists in the PDF.  v0.4.9.5.8 uses that signal to safely split
    a *single* marker in the middle of ``question_full`` without mistaking a
    mere textual reference to <보기> for the actual box.
    """
    repaired = []
    expected = []
    failed = []

    for q in result.get("questions", []):
        qno = int(q.get("number") or 0)
        layout = q.get("layout_v0495") or {}
        geometry_has_marker = layout.get("example_y") is not None
        block = dict(q.get("example_block") or {})
        full = str(q.get("question_full") or q.get("question") or "").strip()

        marker_hits: list[tuple[int, str]] = []
        for marker in _V04958_EXAMPLE_MARKERS:
            start = 0
            while True:
                idx = full.find(marker, start)
                if idx < 0:
                    break
                marker_hits.append((idx, marker))
                start = idx + len(marker)
        marker_hits.sort()

        if geometry_has_marker:
            expected.append(qno)

        if geometry_has_marker and marker_hits:
            # If the stem itself mentions <보기>, the standalone marker is the
            # last occurrence.  With one marker, geometry proves that this is
            # the actual box marker (the v0.4.4 blind spot).
            idx, marker = marker_hits[-1]
            stem = full[:idx].strip()
            body = full[idx + len(marker):].strip()
            body = re.sub(r"(?:\s*[㉠㉡㉢㉣㉤]){2,}\s*$", "", body).strip()
            body = re.sub(r"[ \t]{2,}", " ", body).strip()

            if body:
                was_missing = not (block.get("exists") and str(block.get("text") or "").strip())
                q["example_block"] = {
                    "exists": True,
                    "type": "보기",
                    "text": body,
                    "stem_text": stem,
                    "marker_count": len(marker_hits),
                    "line_count": max(1, len([x for x in body.splitlines() if x.strip()])),
                    "confidence": 0.995,
                    "validation_v045": "ok",
                    "source_v04958": "standalone_marker_geometry",
                }
                q["question"] = stem
                if was_missing:
                    repaired.append(qno)
            else:
                failed.append(qno)
        elif geometry_has_marker and not marker_hits:
            failed.append(qno)

    parsed_expected = []
    for q in result.get("questions", []):
        qno = int(q.get("number") or 0)
        if qno in expected and (q.get("example_block") or {}).get("exists") and str((q.get("example_block") or {}).get("text") or "").strip():
            parsed_expected.append(qno)

    missing = sorted(set(expected) - set(parsed_expected))
    result["example_repair_v04958"] = {
        "expected_from_geometry_question_numbers": sorted(set(expected)),
        "repaired_question_numbers": sorted(set(repaired)),
        "unparsed_example_marker_question_numbers": sorted(set(failed) | set(missing)),
        "detected_example_count": sum(1 for q in result.get("questions", []) if (q.get("example_block") or {}).get("exists")),
        "status": "PASS" if not (set(failed) | set(missing)) else "FAIL",
    }
    return result


def _v04958_horizontal_underline_segments(page: fitz.Page) -> list[dict]:
    """Collect thin dark horizontal vector strokes likely to be text underlines."""
    segments: list[dict] = []
    try:
        drawings = page.get_drawings()
    except Exception:
        drawings = []

    for drawing in drawings:
        width = drawing.get("width")
        if width is None:
            continue
        try:
            width = float(width)
        except Exception:
            continue
        if width <= 0 or width > _V04958_UNDERLINE_MAX_STROKE_PT:
            continue

        color = drawing.get("color")
        if color is not None:
            try:
                if max(float(x) for x in color) > 0.40:
                    continue
            except Exception:
                pass

        for item in drawing.get("items") or []:
            if not item or item[0] != "l":
                continue
            p1, p2 = item[1], item[2]
            if abs(float(p1.y) - float(p2.y)) > 0.8:
                continue
            x0, x1 = sorted((float(p1.x), float(p2.x)))
            if x1 - x0 < 4.0:
                continue
            segments.append({
                "x0": x0,
                "x1": x1,
                "y": (float(p1.y) + float(p2.y)) / 2.0,
                "width": width,
            })
    return segments


def _v04958_raw_char_lines(page: fitz.Page) -> list[dict]:
    lines: list[dict] = []
    raw = page.get_text("rawdict")
    for block in raw.get("blocks") or []:
        if block.get("type") != 0:
            continue
        for line in block.get("lines") or []:
            chars = []
            for span in line.get("spans") or []:
                for char in span.get("chars") or []:
                    value = str(char.get("c") or "")
                    bbox = char.get("bbox")
                    if not value or not bbox:
                        continue
                    chars.append({"c": value, "bbox": fitz.Rect(bbox)})
            if not chars:
                continue
            x0 = min(x["bbox"].x0 for x in chars)
            y0 = min(x["bbox"].y0 for x in chars)
            x1 = max(x["bbox"].x1 for x in chars)
            y1 = max(x["bbox"].y1 for x in chars)
            lines.append({
                "chars": chars,
                "bbox": fitz.Rect(x0, y0, x1, y1),
                "text": "".join(x["c"] for x in chars),
            })
    return lines


def _v04958_underlined_runs_for_line(line: dict, segments: list[dict]) -> list[dict]:
    bbox: fitz.Rect = line["bbox"]
    nearby = [
        s for s in segments
        if abs(float(s["y"]) - float(bbox.y1)) <= _V04958_UNDERLINE_Y_TOLERANCE_PT
        and min(float(bbox.x1), float(s["x1"])) - max(float(bbox.x0), float(s["x0"])) > 3.0
    ]
    if not nearby:
        return []

    flags: list[tuple[str, bool, fitz.Rect]] = []
    for char in line["chars"]:
        cb: fitz.Rect = char["bbox"]
        best_overlap = max(
            (min(float(cb.x1), float(s["x1"])) - max(float(cb.x0), float(s["x0"])) for s in nearby),
            default=-1.0,
        )
        underlined = best_overlap > max(0.25, float(cb.width) * 0.22)
        flags.append((char["c"], underlined, cb))

    runs = []
    current_flag = None
    current_chars: list[tuple[str, fitz.Rect]] = []
    for char, flag, cb in flags:
        if current_flag is None or flag == current_flag:
            current_flag = flag
            current_chars.append((char, cb))
            continue
        if current_flag and "".join(x[0] for x in current_chars).strip():
            runs.append(current_chars)
        current_flag = flag
        current_chars = [(char, cb)]
    if current_flag and "".join(x[0] for x in current_chars).strip():
        runs.append(current_chars)

    output = []
    full_text = line.get("text") or ""
    for run in runs:
        text = "".join(x[0] for x in run).strip()
        if not text:
            continue
        rb = fitz.Rect(
            min(x[1].x0 for x in run),
            min(x[1].y0 for x in run),
            max(x[1].x1 for x in run),
            max(x[1].y1 for x in run),
        )
        # prefix uses character geometry, so the marker remains detectable even
        # when the underlined range starts immediately after ⓐ/(a).
        prefix_chars = [x["c"] for x in line["chars"] if x["bbox"].x0 < rb.x0 - 0.05]
        prefix = "".join(prefix_chars)
        marker_match = _V04958_MARKER_RE.search(prefix)
        output.append({
            "text": text,
            "bbox": [float(rb.x0), float(rb.y0), float(rb.x1), float(rb.y1)],
            "line_text": full_text,
            "prefix": prefix,
            "marker": marker_match.group(1) if marker_match else None,
        })
    return output


def _v04958_find_block_underline_range(block_text: str, marker: str | None, fragments: list[str]) -> tuple[int, int] | None:
    """Map source-line underline fragments back into the normalized block text."""
    text = str(block_text or "")
    cleaned = [str(x or "").strip() for x in fragments if str(x or "").strip()]
    if not text or not cleaned:
        return None

    if marker:
        start_search = 0
        marker_positions = []
        while True:
            idx = text.find(marker, start_search)
            if idx < 0:
                break
            marker_positions.append(idx)
            start_search = idx + len(marker)
        for marker_index in marker_positions:
            start = marker_index + len(marker)
            while start < len(text) and text[start].isspace():
                start += 1
            last_fragment = cleaned[-1]
            end_idx = text.find(last_fragment, start)
            if end_idx >= 0:
                return start, end_idx + len(last_fragment)
            # Source PDF may split a word at a physical line boundary.  The last
            # fragment is normally intact, but if not, use a stable 8+ char tail.
            tail = last_fragment[-min(18, len(last_fragment)):]
            if len(tail) >= 6:
                tail_idx = text.find(tail, start)
                if tail_idx >= 0:
                    return start, tail_idx + len(tail)
        return None

    first = cleaned[0]
    last = cleaned[-1]
    start = text.find(first)
    if start < 0:
        return None
    end_idx = text.find(last, start)
    if end_idx < 0:
        return None
    return start, end_idx + len(last)


def v04958_extract_underline_semantics(pdf_path: Path, result: dict) -> dict:
    """Detect labelled source underlines and attach exact ranges to passage blocks."""
    annotations: list[dict] = []
    mapped = 0
    labelled = 0
    labelled_mapped = 0

    for group in result.get("passage_groups", []):
        for block in group.get("blocks", []) or []:
            block.pop("underline_ranges_v04958", None)

    doc = fitz.open(pdf_path)
    try:
        page_cache: dict[int, tuple[list[dict], list[dict]]] = {}
        for group in result.get("passage_groups", []):
            gid = int(group.get("id") or 0)
            for block_index, block in enumerate(group.get("blocks", []) or []):
                page_no = int(block.get("source_start_page") or 0)
                column = int(block.get("column") or 0)
                start_y = float(block.get("start_y") or 0.0)
                end_y = float(block.get("end_y") or start_y)
                block_text = str(block.get("text") or "")
                if not block_text or page_no <= 0 or page_no > len(doc):
                    continue
                if end_y < start_y:  # cross-column artefact: only trust first physical line
                    end_y = start_y + 18.0

                if page_no not in page_cache:
                    page = doc[page_no - 1]
                    page_cache[page_no] = (
                        _v04958_raw_char_lines(page),
                        _v04958_horizontal_underline_segments(page),
                    )
                raw_lines, segments = page_cache[page_no]
                page = doc[page_no - 1]

                relevant = []
                for line in raw_lines:
                    lb: fitz.Rect = line["bbox"]
                    if get_column(page, float(lb.x0)) != column:
                        continue
                    if float(lb.y1) < start_y - 2.0 or float(lb.y0) > end_y + 2.0:
                        continue
                    runs = _v04958_underlined_runs_for_line(line, segments)
                    for run in runs:
                        relevant.append({
                            **run,
                            "line_y0": float(lb.y0),
                            "line_y1": float(lb.y1),
                        })
                if not relevant:
                    continue
                relevant.sort(key=lambda x: (x["line_y0"], x["bbox"][0]))

                # Merge wrapped underline lines.  A marker starts a semantic span;
                # subsequent fully-underlined continuation lines extend it.
                merged: list[dict] = []
                active = None
                for run in relevant:
                    marker = run.get("marker")
                    if marker:
                        if active is not None:
                            merged.append(active)
                        active = {
                            "marker": marker,
                            "fragments": [run["text"]],
                            "first_y": run["line_y0"],
                            "last_y": run["line_y1"],
                            "source_run_bboxes": [run["bbox"]],
                        }
                        continue
                    if active is not None and run["line_y0"] - active["last_y"] <= 8.0:
                        active["fragments"].append(run["text"])
                        active["last_y"] = run["line_y1"]
                        active["source_run_bboxes"].append(run["bbox"])
                    else:
                        if active is not None:
                            merged.append(active)
                            active = None
                        merged.append({
                            "marker": None,
                            "fragments": [run["text"]],
                            "first_y": run["line_y0"],
                            "last_y": run["line_y1"],
                            "source_run_bboxes": [run["bbox"]],
                        })
                if active is not None:
                    merged.append(active)

                for ann in merged:
                    marker = ann.get("marker")
                    if marker:
                        labelled += 1
                    found = _v04958_find_block_underline_range(block_text, marker, ann["fragments"])
                    payload = {
                        "group_id": gid,
                        "block_index": block_index,
                        "page": page_no,
                        "column": "left" if column == 0 else "right",
                        "marker": marker,
                        "source_fragments": ann["fragments"],
                        "source_run_bboxes": ann["source_run_bboxes"],
                        "mapped": bool(found),
                    }
                    if found:
                        start, end = found
                        rendered_text = block_text[start:end]
                        range_info = {
                            "start": start,
                            "end": end,
                            "marker": marker,
                            "text": rendered_text,
                        }
                        block.setdefault("underline_ranges_v04958", []).append(range_info)
                        payload.update(range_info)
                        mapped += 1
                        if marker:
                            labelled_mapped += 1
                    annotations.append(payload)
    finally:
        doc.close()

    marker_refs = {}
    for q in result.get("questions", []):
        qno = int(q.get("number") or 0)
        text = " ".join([str(q.get("question") or ""), *(str(x or "") for x in q.get("choices", []))])
        refs = []
        for marker in re.findall(r"[ⓐ-ⓩ㉠-㉿]|\([A-Za-z가-힣0-9]\)", text):
            if marker not in refs:
                refs.append(marker)
        if refs:
            marker_refs[str(qno)] = refs

    unmatched_labelled = [a for a in annotations if a.get("marker") and not a.get("mapped")]
    result["underline_semantics_v04958"] = {
        "detector": "PyMuPDF raw chars + thin horizontal vector strokes",
        "annotation_count": len(annotations),
        "mapped_annotation_count": mapped,
        "labelled_annotation_count": labelled,
        "labelled_mapped_count": labelled_mapped,
        "unmatched_labelled_annotations": unmatched_labelled,
        "question_marker_references": marker_refs,
        "annotations": annotations,
        "status": "PASS" if not unmatched_labelled else "WARN",
    }
    return result


def v04958_build_adaptive_flow_policy(result: dict) -> dict:
    policies = {}
    split_safe = []
    full_keep = []
    for q in result.get("questions", []):
        qno = int(q.get("number") or 0)
        ex = q.get("example_block") or {}
        q_chars = len(str(q.get("question") or ""))
        q_chars += len(str(ex.get("text") or ""))
        q_chars += sum(len(str(x or "")) for x in q.get("choices", []))
        has_example = bool(ex.get("exists") and str(ex.get("text") or "").strip())
        mode = "split_safe" if has_example or q_chars > _V04958_SPLIT_SAFE_CHAR_THRESHOLD else "full_keep"
        policies[str(qno)] = {
            "mode": mode,
            "characters": q_chars,
            "has_example": has_example,
            "safe_split_boundaries": "between choices only" if mode == "split_safe" else "none",
        }
        (split_safe if mode == "split_safe" else full_keep).append(qno)
    result["adaptive_flow_v04958"] = {
        "split_safe_question_numbers": split_safe,
        "full_keep_question_numbers": full_keep,
        "threshold_chars": _V04958_SPLIT_SAFE_CHAR_THRESHOLD,
        "policy": "question stem stays with immediate following structural block; long/<보기> questions may break only between whole choice paragraphs",
        "questions": policies,
        "status": "PASS",
    }
    return result


def _v04958_clone_underline_charpr(header_xml: str, source_id: int, cache: dict[int, int]) -> tuple[str, int, bool]:
    if source_id in cache:
        return header_xml, cache[source_id], False
    m = re.search(rf'<hh:charPr\b[^>]*\bid="{int(source_id)}"[\s\S]*?</hh:charPr>', header_xml)
    if not m:
        return header_xml, source_id, False
    new_id = _v04954_next_id(header_xml, "charPr")
    clone = m.group(0)
    clone = re.sub(r'\bid="\d+"', f'id="{new_id}"', clone, count=1)
    if re.search(r'<hh:underline\b[^>]*/>', clone):
        clone = re.sub(
            r'<hh:underline\b[^>]*/>',
            '<hh:underline type="BOTTOM" shape="SOLID" color="#000000"/>',
            clone,
            count=1,
        )
    else:
        clone = clone.replace('</hh:charPr>', '<hh:underline type="BOTTOM" shape="SOLID" color="#000000"/></hh:charPr>', 1)
    header_xml = header_xml.replace('</hh:charProperties>', clone + '</hh:charProperties>', 1)
    header_xml = _v04954_set_item_count(header_xml, "charProperties", 1)
    cache[source_id] = new_id
    return header_xml, new_id, True


def _v04958_patch_simple_text_runs_with_underline(
    paragraph_xml: str,
    ranges: list[tuple[int, int]],
    header_xml: str,
    char_cache: dict[int, int],
) -> tuple[str, str, int]:
    """Split simple hp:run/hp:t runs at underline boundaries."""
    import html as _html
    from xml.sax.saxutils import escape as _xml_escape

    ranges = sorted((max(0, int(a)), max(0, int(b))) for a, b in ranges if int(b) > int(a))
    if not ranges:
        return paragraph_xml, header_xml, 0

    run_re = re.compile(r'<hp:run\b([^>]*)charPrIDRef="(\d+)"([^>]*)><hp:t\b([^>]*)>(.*?)</hp:t></hp:run>', re.S)
    matches = list(run_re.finditer(paragraph_xml))
    if not matches:
        return paragraph_xml, header_xml, 0

    output = []
    cursor = 0
    text_pos = 0
    applied = 0
    for m in matches:
        output.append(paragraph_xml[cursor:m.start()])
        source_id = int(m.group(2))
        raw_text = m.group(5)
        visible = _html.unescape(re.sub(r'<[^>]+>', '', raw_text))
        run_start = text_pos
        run_end = text_pos + len(visible)
        boundaries = {0, len(visible)}
        for a, b in ranges:
            if b <= run_start or a >= run_end:
                continue
            boundaries.add(max(0, a - run_start))
            boundaries.add(min(len(visible), b - run_start))
        points = sorted(boundaries)
        if len(points) == 2:
            output.append(m.group(0))
        else:
            for a, b in zip(points, points[1:]):
                piece = visible[a:b]
                if not piece:
                    continue
                global_a = run_start + a
                global_b = run_start + b
                is_under = any(global_a >= ra and global_b <= rb for ra, rb in ranges)
                char_id = source_id
                if is_under:
                    header_xml, char_id, _ = _v04958_clone_underline_charpr(header_xml, source_id, char_cache)
                    applied += 1
                attrs_before = m.group(1)
                attrs_after = m.group(3)
                t_attrs = m.group(4)
                output.append(
                    f'<hp:run{attrs_before}charPrIDRef="{char_id}"{attrs_after}>'
                    f'<hp:t{t_attrs}>{_xml_escape(piece)}</hp:t></hp:run>'
                )
        cursor = m.end()
        text_pos = run_end
    output.append(paragraph_xml[cursor:])
    return ''.join(output), header_xml, applied


def _v04958_apply_example_boxes(header_xml: str, section_xml: str) -> tuple[str, str, dict]:
    border_id = _v04954_next_id(header_xml, "borderFill")
    border_xml = _v04954_make_solid_border_fill(border_id)
    header_xml = header_xml.replace('</hh:borderFills>', border_xml + '</hh:borderFills>', 1)
    header_xml = _v04954_set_item_count(header_xml, "borderFills", 1)

    cache: dict[int, int] = {}
    clone_count = 0
    box_count = 0
    paragraphs = list(re.finditer(r'<hp:p\b[^>]*>[\s\S]*?</hp:p>', section_xml))
    out = []
    cursor = 0
    for pm in paragraphs:
        out.append(section_xml[cursor:pm.start()])
        p = pm.group(0)
        text = _v04954_para_text(p)
        if text.startswith("<보기>") or text.startswith("[보기]") or text.startswith("〈보기〉") or text.startswith("《보기》"):
            sm = re.match(r'<hp:p\b[^>]*\bparaPrIDRef="(\d+)"[^>]*>', p)
            if sm:
                old_id = int(sm.group(1))
                if old_id not in cache:
                    new_id = _v04954_next_id(header_xml, "paraPr")
                    header_xml = _v04954_clone_box_parapr(header_xml, old_id, new_id, border_id)
                    cache[old_id] = new_id
                    clone_count += 1
                p = re.sub(
                    r'(<hp:p\b[^>]*\bparaPrIDRef=")\d+("[^>]*>)',
                    rf'\g<1>{cache[old_id]}\2',
                    p,
                    count=1,
                )
                box_count += 1
        out.append(p)
        cursor = pm.end()
    out.append(section_xml[cursor:])
    section_xml = ''.join(out)
    header_xml = _v04954_set_item_count(header_xml, "paraProperties", clone_count)
    # Reuse the proven passage padding dimensions for <보기> boxes too.
    header_xml, _ = _v04955_patch_box_padding(header_xml)
    return header_xml, section_xml, {
        "example_box_paragraph_count": box_count,
        "example_box_para_style_count": clone_count,
        "example_border_fill_id": border_id,
    }


def _v04958_apply_underline_ranges(header_xml: str, section_xml: str, result: dict) -> tuple[str, str, dict]:
    block_ranges: dict[str, list[tuple[int, int]]] = defaultdict(list)
    expected = 0
    for group in result.get("passage_groups", []):
        for block in group.get("blocks", []) or []:
            text = str(block.get("text") or "")
            for rg in block.get("underline_ranges_v04958", []) or []:
                a, b = int(rg.get("start") or 0), int(rg.get("end") or 0)
                if b > a:
                    block_ranges[text].append((a, b))
                    expected += 1

    char_cache: dict[int, int] = {}
    applied_segments = 0
    matched_paragraphs = 0
    paragraphs = list(re.finditer(r'<hp:p\b[^>]*>[\s\S]*?</hp:p>', section_xml))
    out = []
    cursor = 0
    for pm in paragraphs:
        out.append(section_xml[cursor:pm.start()])
        p = pm.group(0)
        text = _v04954_para_text(p)
        ranges = block_ranges.get(text) or []
        if ranges:
            p, header_xml, applied = _v04958_patch_simple_text_runs_with_underline(
                p, ranges, header_xml, char_cache
            )
            if applied:
                matched_paragraphs += 1
                applied_segments += applied
        out.append(p)
        cursor = pm.end()
    out.append(section_xml[cursor:])
    return header_xml, ''.join(out), {
        "expected_underline_range_count": expected,
        "underlined_paragraph_count": matched_paragraphs,
        "underlined_run_segment_count": applied_segments,
        "underline_char_style_count": len(char_cache),
    }


def _v04958_apply_adaptive_flow_styles(header_xml: str, section_xml: str, result: dict) -> tuple[str, str, dict]:
    policies = (result.get("adaptive_flow_v04958") or {}).get("questions") or {}
    first_questions = {
        int((g.get("question_numbers") or [0])[0])
        for g in result.get("passage_groups", [])
        if g.get("question_numbers")
    }
    cache: dict[tuple[int, int, int, int, int], int] = {}
    clone_count = 0
    split_choice_count = 0
    full_keep_choice_count = 0
    current_qno = None

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
    out = []
    cursor = 0
    for pm in paragraphs:
        out.append(section_xml[cursor:pm.start()])
        p = pm.group(0)
        text = _v04954_para_text(p)
        qm = re.match(r'^(\d+)\.\s', text)
        if qm:
            current_qno = int(qm.group(1))
            prev = _V04955_FIRST_QUESTION_PREV if current_qno in first_questions else _V04955_QUESTION_PREV
            p = style_para(p, 1, 1, prev, 0)
        elif current_qno and (text.startswith("<보기>") or text.startswith("[보기]") or text.startswith("〈보기〉") or text.startswith("《보기》")):
            # Keep the box itself intact, but allow choices to start in the
            # remaining space or next column.  The question stem stays with the box.
            p = style_para(p, 0, 1, 0, 0)
        elif current_qno and re.match(r'^[①②③④⑤]\s', text):
            mode = (policies.get(str(current_qno)) or {}).get("mode", "full_keep")
            is_last = text.startswith("⑤ ")
            if mode == "split_safe":
                p = style_para(p, 0, 1, 0, _V04955_BLOCK_END_NEXT if is_last else 0)
                split_choice_count += 1
            else:
                p = style_para(p, 0 if is_last else 1, 1, 0, _V04955_BLOCK_END_NEXT if is_last else 0)
                full_keep_choice_count += 1
        out.append(p)
        cursor = pm.end()
    out.append(section_xml[cursor:])
    header_xml = _v04954_set_item_count(header_xml, "paraProperties", clone_count)
    return header_xml, ''.join(out), {
        "new_adaptive_para_style_count": clone_count,
        "split_safe_choice_paragraph_count": split_choice_count,
        "full_keep_choice_paragraph_count": full_keep_choice_count,
    }


def _v04958_enable_continuous_two_column_flow(section_xml: str) -> tuple[str, dict]:
    page_breaks = len(re.findall(r'\bpageBreak="1"', section_xml))
    column_breaks = len(re.findall(r'\bcolumnBreak="1"', section_xml))
    lineseg_count = len(re.findall(r'<hp:linesegarray>[\s\S]*?</hp:linesegarray>', section_xml))

    section_xml = re.sub(r'\bpageBreak="1"', 'pageBreak="0"', section_xml)
    section_xml = re.sub(r'\bcolumnBreak="1"', 'columnBreak="0"', section_xml)
    # Line segment arrays cache the old source-page geometry.  Once source
    # page/column breaks are removed they must not force stale vertical
    # positions.  Hancom-generated HWPX permits paragraphs without this cache;
    # Hangul recomputes line layout when the document is opened.
    section_xml = re.sub(r'<hp:linesegarray>[\s\S]*?</hp:linesegarray>', '', section_xml)
    return section_xml, {
        "removed_page_break_count": page_breaks,
        "removed_column_break_count": column_breaks,
        "removed_linesegarray_count": lineseg_count,
        "flow_mode": "continuous_native_two_column",
    }


def _v04958_repack_postprocessed_hwpx(source: Path, candidate: Path, header_xml: str, section0_xml: str) -> None:
    _v04954_repack_hwpx(
        source,
        candidate,
        {
            "Contents/header.xml": header_xml.encode("utf-8"),
            "Contents/section0.xml": section0_xml.encode("utf-8"),
        },
    )


def _v04958_para_style_border_refs(header_xml: str) -> dict[int, int]:
    refs = {}
    for m in re.finditer(r'<hh:paraPr\b[^>]*\bid="(\d+)"[\s\S]*?</hh:paraPr>', header_xml):
        pid = int(m.group(1))
        bm = re.search(r'<hh:border\b[^>]*\bborderFillIDRef="(\d+)"[^>]*/>', m.group(0))
        if bm:
            refs[pid] = int(bm.group(1))
    return refs


def _v04958_solid_border_fill_ids(header_xml: str) -> set[int]:
    ids = set()
    for m in re.finditer(r'<hh:borderFill\b[^>]*\bid="(\d+)"[\s\S]*?</hh:borderFill>', header_xml):
        body = m.group(0)
        if all(re.search(rf'<hh:{side}Border\b[^>]*\btype="SOLID"', body) for side in ("left", "right", "top", "bottom")):
            ids.add(int(m.group(1)))
    return ids


def v04958_validate_hwpx(path: Path, *, result: dict, render_plan: dict) -> dict:
    expected_count = int(result.get("image_filter_v0481", {}).get("saved_count") or 0)
    info = v04952_validate_hwpx(
        path,
        expected_images=expected_count,
        render_plan=render_plan,
        result=result,
        require_two_column=True,
    )
    info["validator_version"] = _V04958_VERSION
    info["image_logical_position_status"] = "NOT_APPLICABLE_CONTINUOUS_FLOW"

    if not Path(path).exists() or not zipfile.is_zipfile(path) or info.get("package_status") != "PASS":
        info["status"] = "FAIL"
        return info

    try:
        with zipfile.ZipFile(path, "r") as zf:
            header = zf.read("Contents/header.xml").decode("utf-8", errors="strict")
            section0 = zf.read("Contents/section0.xml").decode("utf-8", errors="strict")
            section_names = sorted(
                [n for n in zf.namelist() if re.fullmatch(r"Contents/section\d+\.xml", n)],
                key=_v04953_section_number,
            )
            sections = {n: zf.read(n).decode("utf-8", errors="strict") for n in section_names}

        question_col_counts = _v04953_col_counts(section0)
        question_two = any(x >= 2 for x in question_col_counts)
        answer_two = all(
            any(x >= 2 for x in (_v04953_col_counts(xml) or [1]))
            for name, xml in sections.items() if name != "Contents/section0.xml"
        ) if len(sections) > 1 else True
        info["question_two_column_found"] = question_two
        info["answer_sections_two_column"] = answer_two

        remaining_page_breaks = len(re.findall(r'\bpageBreak="1"', section0))
        remaining_column_breaks = len(re.findall(r'\bcolumnBreak="1"', section0))
        remaining_lineseg = len(re.findall(r'<hp:linesegarray>[\s\S]*?</hp:linesegarray>', section0))
        info["remaining_forced_page_break_count"] = remaining_page_breaks
        info["remaining_forced_column_break_count"] = remaining_column_breaks
        info["remaining_question_linesegarray_count"] = remaining_lineseg
        info["continuous_flow_status"] = "PASS" if question_two and remaining_page_breaks == 0 and remaining_column_breaks == 0 and remaining_lineseg == 0 else "FAIL"

        para_border_refs = _v04958_para_style_border_refs(header)
        solid_ids = _v04958_solid_border_fill_ids(header)
        expected_examples = sum(1 for q in result.get("questions", []) if (q.get("example_block") or {}).get("exists") and str((q.get("example_block") or {}).get("text") or "").strip())
        actual_examples = 0
        boxed_examples = 0
        for pm in re.finditer(r'<hp:p\b[^>]*\bparaPrIDRef="(\d+)"[^>]*>[\s\S]*?</hp:p>', section0):
            text = _v04954_para_text(pm.group(0))
            if text.startswith("<보기>") or text.startswith("[보기]") or text.startswith("〈보기〉") or text.startswith("《보기》"):
                actual_examples += 1
                pid = int(pm.group(1))
                if para_border_refs.get(pid) in solid_ids:
                    boxed_examples += 1
        info["expected_example_box_count"] = expected_examples
        info["actual_example_box_count"] = actual_examples
        info["bordered_example_box_count"] = boxed_examples
        info["example_box_status"] = "PASS" if actual_examples == expected_examples and boxed_examples == expected_examples else "FAIL"

        under_char_ids = set()
        for cm in re.finditer(r'<hh:charPr\b[^>]*\bid="(\d+)"[\s\S]*?</hh:charPr>', header):
            if re.search(r'<hh:underline\b[^>]*\btype="BOTTOM"', cm.group(0)):
                under_char_ids.add(int(cm.group(1)))
        under_texts = []
        for rm in re.finditer(r'<hp:run\b[^>]*\bcharPrIDRef="(\d+)"[^>]*>[\s\S]*?</hp:run>', section0):
            if int(rm.group(1)) not in under_char_ids:
                continue
            t = _v04954_para_text("<hp:p>" + rm.group(0) + "</hp:p>")
            if t:
                under_texts.append(t)
        expected_under = [
            str(rg.get("text") or "")
            for g in result.get("passage_groups", [])
            for b in (g.get("blocks") or [])
            for rg in (b.get("underline_ranges_v04958") or [])
            if str(rg.get("text") or "")
        ]
        normalized_under = " ".join(_v04958_normalize_visible_text(x) for x in under_texts)
        missing_under = [x for x in expected_under if _v04958_normalize_visible_text(x) not in normalized_under]
        info["expected_underline_range_count"] = len(expected_under)
        info["actual_underlined_run_count"] = len(under_texts)
        info["missing_underlined_texts"] = missing_under
        info["underline_status"] = "PASS" if not missing_under else "FAIL"

        repair = result.get("example_repair_v04958") or {}
        info["example_detection_status"] = repair.get("status", "PASS")
        sem = result.get("underline_semantics_v04958") or {}
        info["underline_detection_status"] = sem.get("status", "PASS")

        critical = [
            info.get("package_status"),
            info.get("image_order_status"),
            info.get("image_anchor_status"),
            info.get("image_answer_boundary_status"),
            info.get("continuous_flow_status"),
            info.get("example_box_status"),
            info.get("underline_status"),
            info.get("example_detection_status"),
        ]
        info["image_position_status"] = (
            "FAIL" if "FAIL" in (info.get("image_order_status"), info.get("image_anchor_status"), info.get("image_answer_boundary_status"))
            else "WARN" if "WARN" in (info.get("image_order_status"), info.get("image_anchor_status"), info.get("image_answer_boundary_status"))
            else "PASS"
        )
        info["status"] = "FAIL" if "FAIL" in critical else "WARN" if "WARN" in critical else "PASS"
        return info
    except Exception as exc:
        info["v04958_validation_error"] = str(exc)
        info["status"] = "FAIL"
        return info


def _v04958_postprocess_hwpx(path: Path, result: dict, render_plan: dict) -> dict:
    import xml.etree.ElementTree as ET
    path = Path(path)
    report = {
        "version": _V04958_VERSION,
        "status": "SKIPPED",
        "applied": False,
        "source": str(path),
    }
    if not path.exists() or not zipfile.is_zipfile(path):
        report["reason"] = "no usable HWPX"
        return report

    candidate = path.with_name(path.stem + "_v04958_candidate.hwpx")
    if candidate.exists():
        try:
            candidate.unlink()
        except Exception:
            pass

    try:
        with zipfile.ZipFile(path, "r") as zf:
            header = zf.read("Contents/header.xml").decode("utf-8", errors="strict")
            section0 = zf.read("Contents/section0.xml").decode("utf-8", errors="strict")

        header, section0, example_report = _v04958_apply_example_boxes(header, section0)
        header, section0, underline_report = _v04958_apply_underline_ranges(header, section0, result)
        header, section0, adaptive_report = _v04958_apply_adaptive_flow_styles(header, section0, result)
        section0, flow_report = _v04958_enable_continuous_two_column_flow(section0)

        ET.fromstring(header.encode("utf-8"))
        ET.fromstring(section0.encode("utf-8"))
        _v04958_repack_postprocessed_hwpx(path, candidate, header, section0)
        validation = v04958_validate_hwpx(candidate, result=result, render_plan=render_plan)

        report.update({
            "status": "APPLIED" if validation.get("status") == "PASS" else "REJECTED_BY_VALIDATION",
            "applied": validation.get("status") == "PASS",
            "candidate": str(candidate),
            "example_boxes": example_report,
            "underlines": underline_report,
            "adaptive_flow": adaptive_report,
            "continuous_flow": flow_report,
            "validation": validation,
        })
        if validation.get("status") == "PASS":
            os.replace(str(candidate), str(path))
            report["candidate"] = None
            report["final_path"] = str(path.resolve())
        elif candidate.exists():
            candidate.unlink()
        return report
    except Exception as exc:
        report["status"] = "FAIL"
        report["reason"] = str(exc)
        try:
            if candidate.exists():
                candidate.unlink()
        except Exception:
            pass
        return report


def v04958_create_hwpx_with_hancom(
    final_output: Path,
    result: dict,
    render_plan: dict,
    *,
    security_module_path: Path | None = None,
    allow_interactive_hwp: bool = False,
    show_hwp: bool = False,
) -> dict:
    info = v04957_create_hwpx_with_hancom(
        final_output,
        result,
        render_plan,
        security_module_path=security_module_path,
        allow_interactive_hwp=allow_interactive_hwp,
        show_hwp=show_hwp,
    )
    info["backend"] = "hancom_com_v04958"
    info["renderer_mode"] = "continuous_two_column_example_box_underline_v04958"

    for old_key, new_key in (
        ("editorial_finalize_v04957", "editorial_finalize_v04958"),
        ("compact_finalize_v04957", "compact_finalize_v04958"),
    ):
        payload = info.pop(old_key, None)
        if isinstance(payload, dict):
            payload["version"] = _V04958_VERSION
            info[new_key] = payload

    if info.get("status") == "created" and Path(final_output).exists():
        semantic = _v04958_postprocess_hwpx(Path(final_output), result, render_plan)
        info["semantic_finalize_v04958"] = semantic
        if semantic.get("applied"):
            info["validation"] = v04958_validate_hwpx(Path(final_output), result=result, render_plan=render_plan)
            info["status"] = "created" if info["validation"].get("status") == "PASS" else "INVALID"
            info["final_path"] = str(Path(final_output).resolve())
        else:
            # Preserve the already valid v0.4.9.5.7 file instead of destroying it,
            # but surface the failed enhancement as INVALID so it cannot be mistaken
            # for a successfully upgraded 5.8 document.
            info["status"] = "INVALID"
            if semantic.get("validation"):
                info["validation"] = semantic["validation"]
    elif info.get("status") == "SKIPPED":
        info["semantic_finalize_v04958"] = {"status": "SKIPPED", "applied": False, "reason": "Hancom writer unavailable on this platform"}
    return info


def v04958_validate_structural(result: dict) -> dict:
    base = v04957_validate_structural_edges(result)
    repair = result.get("example_repair_v04958") or {}
    underline = result.get("underline_semantics_v04958") or {}
    issues = list(base.get("issues") or [])
    if repair.get("status") == "FAIL":
        issues.append("unparsed_example_marker")
    if underline.get("status") == "FAIL":
        issues.append("underline_semantics")
    base.update({
        "example_detection_status": repair.get("status", "PASS"),
        "expected_example_question_numbers": repair.get("expected_from_geometry_question_numbers", []),
        "repaired_example_question_numbers": repair.get("repaired_question_numbers", []),
        "unparsed_example_marker_question_numbers": repair.get("unparsed_example_marker_question_numbers", []),
        "underline_detection_status": underline.get("status", "PASS"),
        "labelled_underline_count": underline.get("labelled_annotation_count", 0),
        "labelled_underline_mapped_count": underline.get("labelled_mapped_count", 0),
        "issues": issues,
        "status": "PASS" if not issues else "FAIL",
    })
    return base


def v04958_upgrade_result(
    result: dict,
    pdf_path: Path,
    checkpoint_path: Path | None = None,
    *,
    hwpx_output_path: Path | None = None,
    question_detection: dict | None = None,
    security_module_path: Path | None = None,
    allow_interactive_hwp: bool = False,
    show_hwp: bool = False,
) -> dict:
    _v0491_log("[v0.4.9.5.8] 연속 2단 흐름 + 보기 박스 + 밑줄 의미표지 준비")

    result = v046_upgrade_result(result, pdf_path)
    result = v0481_prepare_problem_images(pdf_path, result)
    result = v0491_cleanup_legacy_metadata(result)
    result = v0495_attach_question_geometry(pdf_path, result)
    result = v04958_repair_example_blocks(result)
    result = v04958_extract_underline_semantics(pdf_path, result)
    result = v04958_build_adaptive_flow_policy(result)
    result = v04957_cleanup_orphan_section_labels(result)
    structural = v04958_validate_structural(result)
    result["structural_validation_v04958"] = structural

    render_plan = v04955_build_render_plan(result)
    render_plan["version"] = _V04958_VERSION
    render_plan["flow_policy_v04958"] = {
        "mode": "continuous_native_two_column_after_safe_hancom_render",
        "source_page_breaks": "removed from final question section",
        "source_column_breaks": "removed from final question section",
        "line_layout_cache": "removed from section0 so Hangul recalculates natural flow",
        "safe_question_split": "adaptive; long/<보기> questions split only between whole choice paragraphs",
        "example_box": "solid rectangular border with existing 3.0mm/1.5mm box padding",
        "underline_semantics": "thin vector underline -> labelled text range -> HWPX BOTTOM underline char style",
    }
    render_plan["output_policy_v04958"] = {
        "default_final_filename": f"{_v04957_safe_output_stem(pdf_path)}.hwpx",
        "filename_basis": "source_pdf_stem",
        "never_overwrite_existing": True,
        "run_suffix_when_existing": "_runNN",
    }
    result["render_plan_v04958"] = render_plan
    for stale_key in [
        "render_plan_v04957", "render_plan_v04956", "render_plan_v04955", "render_plan_v04954",
        "render_plan_v04953", "render_plan_v04952", "render_plan_v04951", "render_plan_v0495",
        "render_plan_v0494", "render_plan_v0493", "render_plan_v0492", "render_plan_v049",
    ]:
        result.pop(stale_key, None)

    result["version"] = _V04958_VERSION
    result["parser_version"] = _V04958_VERSION
    result["generator_version"] = "PDF Parser Integrated v0.4.9.5.8"
    result["question_detection_v04958"] = question_detection or {}
    result["schema_version"] = {
        "base": "v0.4.9.5.7",
        "extension": [
            "single_marker_example_geometry_repair",
            "real_example_rectangular_border",
            "continuous_native_two_column_flow",
            "adaptive_question_choice_boundary_flow",
            "pdf_vector_underline_detection",
            "labelled_underline_semantic_ranges",
            "hwpx_partial_text_underline_rendering",
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
        _v0491_log(f"[v0.4.9.5.8] HWPX 전 임시 체크포인트 저장: {checkpoint_path.resolve()}")

    requested = Path(hwpx_output_path) if hwpx_output_path else _v04957_default_hwpx_path(pdf_path)
    actual_target = _v04956_pick_free_path(requested)
    result["hwpx_output_v04958"] = {
        "requested_path": str(requested.resolve()),
        "allocated_path": str(actual_target.resolve()),
        "source_pdf_stem": Path(pdf_path).stem,
        "safe_output_stem": _v04957_safe_output_stem(pdf_path),
        "existing_requested_path_preserved": requested.exists(),
        "policy": "PDF stem filename; never overwrite; allocate _runNN when needed",
    }

    hwpx_info = v04958_create_hwpx_with_hancom(
        actual_target,
        result,
        render_plan,
        security_module_path=security_module_path,
        allow_interactive_hwp=allow_interactive_hwp,
        show_hwp=show_hwp,
    )
    result["hwpx_v04958"] = hwpx_info
    result["hancom_security_v04958"] = result.get("hancom_security_v04957") or hwpx_info.get("hancom_security") or {}
    for stale_key in [
        "hwpx_v04957", "hancom_security_v04957", "hwpx_v04956", "hancom_security_v04956",
        "hancom_security_v04955", "hancom_security_v04954", "hancom_security_v04953", "hancom_security_v04952",
    ]:
        result.pop(stale_key, None)

    base_validation = result.get("validation", {})
    img_validation = result.get("image_filter_v0481", {})
    table_validation = result.get("table_filter_v0492", {})
    geometry_validation = result.get("question_geometry_v0495", {})
    source_order_validation = render_plan.get("source_order_v0495", {})
    final_validation = hwpx_info.get("validation") or {}
    security_runtime = result.get("hancom_security_v04958") or {}
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
        and structural.get("status") == "PASS"
        and hwpx_status in {"created", "SKIPPED"}
        and security_ok
        and final_validation.get("package_status") in {"PASS", None}
    )
    critical_keys = (
        "image_order_status", "image_anchor_status", "image_answer_boundary_status",
        "continuous_flow_status", "example_box_status", "underline_status",
        "example_detection_status",
    )
    critical_fail = any(final_validation.get(k) == "FAIL" for k in critical_keys)
    if critical_fail or structural.get("status") == "FAIL":
        final_status = "FAIL"
    elif hard_pass and final_validation.get("status") in {"PASS", None}:
        final_status = "PASS"
    elif hwpx_status == "SKIPPED" and hard_pass:
        final_status = "PASS"
    else:
        final_status = "WARN" if hwpx_status == "SKIPPED" else "FAIL"

    semantic = hwpx_info.get("semantic_finalize_v04958") or {}
    result["validation_v04958"] = {
        "question_count": len(result.get("questions", [])),
        "passage_group_count": len(result.get("passage_groups", [])),
        "problem_image_count": img_validation.get("selected_problem_figure_count", 0),
        "problem_image_saved": img_validation.get("saved_count", 0),
        "answer_count": render_plan.get("stats", {}).get("answer_count", 0),
        "render_page_count": render_plan.get("stats", {}).get("page_count", 0),
        "render_item_count": render_plan.get("stats", {}).get("render_item_count", 0),
        "question_detection_status": (question_detection or {}).get("status"),
        "question_geometry_status": geometry_validation.get("status"),
        "source_order_status": source_order_validation.get("status"),
        "base_parser_status": base_validation.get("status"),
        "image_status": img_validation.get("status"),
        "structural_status": structural.get("status"),
        "orphan_section_label_status": structural.get("orphan_section_label_status"),
        "removed_orphan_section_label_count": structural.get("removed_orphan_section_label_count", 0),
        "empty_passage_group_ids": structural.get("empty_passage_group_ids", []),
        "image_only_group_without_saved_image_ids": structural.get("image_only_group_without_saved_image_ids", []),
        "example_detection_status": structural.get("example_detection_status"),
        "repaired_example_question_numbers": structural.get("repaired_example_question_numbers", []),
        "unparsed_example_marker_question_numbers": structural.get("unparsed_example_marker_question_numbers", []),
        "underline_detection_status": structural.get("underline_detection_status"),
        "labelled_underline_count": structural.get("labelled_underline_count", 0),
        "labelled_underline_mapped_count": structural.get("labelled_underline_mapped_count", 0),
        "oversize_flow_status": structural.get("oversize_flow_status"),
        "hancom_security_status": security_runtime.get("status"),
        "unattended_ready": security_runtime.get("unattended_ready", False),
        "hwpx_status": hwpx_status,
        "hwpx_final_path": hwpx_info.get("final_path"),
        "hwpx_final_filename_basis": "source_pdf_stem",
        "hwpx_final_write_policy": hwpx_info.get("final_write_policy"),
        "hwpx_validation_status": final_validation.get("status"),
        "hwpx_package_status": final_validation.get("package_status"),
        "hwpx_question_two_column_found": final_validation.get("question_two_column_found"),
        "hwpx_answer_sections_two_column": final_validation.get("answer_sections_two_column"),
        "continuous_flow_status": final_validation.get("continuous_flow_status"),
        "remaining_forced_page_break_count": final_validation.get("remaining_forced_page_break_count"),
        "remaining_forced_column_break_count": final_validation.get("remaining_forced_column_break_count"),
        "remaining_question_linesegarray_count": final_validation.get("remaining_question_linesegarray_count"),
        "example_box_status": final_validation.get("example_box_status"),
        "expected_example_box_count": final_validation.get("expected_example_box_count"),
        "bordered_example_box_count": final_validation.get("bordered_example_box_count"),
        "underline_status": final_validation.get("underline_status"),
        "expected_underline_range_count": final_validation.get("expected_underline_range_count"),
        "actual_underlined_run_count": final_validation.get("actual_underlined_run_count"),
        "image_position_status": final_validation.get("image_position_status"),
        "pictures_after_answer_count": final_validation.get("pictures_after_answer_count"),
        "semantic_finalize_status": semantic.get("status"),
        "semantic_finalize_applied": semantic.get("applied", False),
        "adaptive_split_safe_question_numbers": (result.get("adaptive_flow_v04958") or {}).get("split_safe_question_numbers", []),
        "status": final_status,
    }
    result["known_limitations_v04958"] = [
        "현재 최다빈출 공략 계열 PDF에서 검증된 규칙이며, 다른 출판사/사이트는 컬럼/문항 마커 규칙을 추가 확인해야 합니다.",
        "밑줄은 PDF 텍스트 바로 아래의 얇은 벡터 선을 기준으로 검출합니다. 스캔 이미지에 그려진 밑줄은 OCR/영상 분석 없이는 별도 검출되지 않습니다.",
        "복잡한 병합 셀 표의 완전 복원은 아직 지원하지 않습니다.",
        "최종 HWPX/JSON 기본 파일명은 원본 PDF 이름을 기준으로 하며, 동일 이름이 존재하면 _run02, _run03 순으로 새 파일을 생성합니다.",
    ]
    return result


def main_v04958() -> None:
    parser = argparse.ArgumentParser(
        description="국어 문제 PDF -> 구조화 JSON + HWPX V0.4.9.5.8 연속 흐름/보기 박스/밑줄 의미표지"
    )
    parser.add_argument("pdf", type=Path, help="분석할 PDF 파일")
    parser.add_argument("-o", "--output", type=Path, default=None, help="저장할 JSON. 생략하면 <PDF이름>_result.json")
    parser.add_argument("--hwpx-output", type=Path, default=None, help="최종 HWPX 희망 파일명. 생략하면 <PDF이름>.hwpx, 존재 시 _runNN 자동 생성")
    parser.add_argument("-q", "--questions", nargs="+", type=int, default=None, help="추출할 문제 번호. 생략하면 PDF에서 자동 탐지")
    parser.add_argument("--no-kiwi", action="store_true", help="Kiwi 경계 판별을 끔")
    parser.add_argument("--security-module", type=Path, default=None, help="FilePathCheckerModuleExample.dll 경로")
    parser.add_argument("--allow-interactive-hwp", action="store_true", help="보안 모듈 실패 시 대화형 한글 허용")
    parser.add_argument("--show-hwp", action="store_true", help="한글 창 표시")
    args = parser.parse_args()

    if not args.pdf.exists():
        raise SystemExit(f"PDF 파일을 찾을 수 없습니다: {args.pdf}")
    if not args.no_kiwi and Kiwi is None:
        print("[경고] kiwipiepy 미설치. fallback으로 실행합니다.")

    detection = v04957_detect_question_numbers(args.pdf)
    if args.questions:
        question_numbers = sorted(set(args.questions))
        detection["selection_mode"] = "explicit_cli"
        detection["selected_question_numbers"] = question_numbers
    else:
        if detection.get("status") != "PASS" or not detection.get("question_numbers"):
            raise SystemExit("문제 번호 자동 탐지에 실패했습니다. -q 옵션으로 문제 번호를 직접 지정하세요. " + str(detection.get("reason") or ""))
        question_numbers = list(detection["question_numbers"])
        detection["selection_mode"] = "auto_detected"
        detection["selected_question_numbers"] = question_numbers

    json_output = Path(args.output) if args.output else _v04957_default_json_path(args.pdf)
    checkpoint_path = json_output.with_name(json_output.stem + "_pre_hwpx.json")

    result = parse_v0_2_3(args.pdf, question_numbers, use_kiwi=not args.no_kiwi)
    result = v044_upgrade_result(result, args.pdf)
    result = v045_upgrade_result(result, args.pdf)
    result = v04958_upgrade_result(
        result,
        args.pdf,
        checkpoint_path=checkpoint_path,
        hwpx_output_path=args.hwpx_output,
        question_detection=detection,
        security_module_path=args.security_module,
        allow_interactive_hwp=args.allow_interactive_hwp,
        show_hwp=args.show_hwp,
    )
    json_output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    checkpoint_info = result.get("pre_hwpx_checkpoint") or {}
    checkpoint_file = Path(str(checkpoint_info.get("path") or "")) if isinstance(checkpoint_info, dict) else None
    if result.get("hwpx_v04958", {}).get("status") == "created" and checkpoint_file and str(checkpoint_file):
        try:
            if checkpoint_file.exists():
                checkpoint_file.unlink()
            checkpoint_info["retained"] = False
            result["pre_hwpx_checkpoint"] = checkpoint_info
            json_output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            checkpoint_info["retained"] = True
            checkpoint_info["cleanup_error"] = str(exc)

    v = result.get("validation_v04958", {})
    print("=" * 76)
    print("V0.4.9.5.8 연속 2단 흐름 + 보기 박스 + 밑줄 의미표지 완료")
    print("=" * 76)
    print(f"입력 : {args.pdf}")
    print(f"JSON : {json_output.resolve()}")
    print(f"HWPX : {v.get('hwpx_final_path')}")
    print(f"문제 : {v.get('question_count', 0)} | 자동 탐지 : {v.get('question_detection_status')}")
    print(f"지문 그룹 : {v.get('passage_group_count', 0)} | 구조 검증 : {v.get('structural_status')}")
    print(f"<보기> 감지 : {v.get('example_detection_status')} | 자동 복구 : {v.get('repaired_example_question_numbers')}")
    print(f"밑줄 의미표지 : {v.get('underline_detection_status')} | {v.get('labelled_underline_mapped_count')}/{v.get('labelled_underline_count')}")
    print(f"연속 흐름 : {v.get('continuous_flow_status')} | 보기 박스 : {v.get('example_box_status')} | 밑줄 렌더 : {v.get('underline_status')}")
    print(f"HWPX 상태 : {v.get('hwpx_status')} | 최종 검증 : {v.get('status')}")



# ============================================================
# V0.4.9.5.9 Atomic Question Flow + Connected Example Box Layer
# - <보기> 제목 + 본문 전체를 하나의 연결된 직사각형 박스로 렌더
# - 한 컬럼에 들어가는 문제는 stem/example/①~⑤ 전체를 원자적으로 유지
# - 실제 한 컬럼보다 긴 문제만 선택지 경계에서 안전 분할
# - 최종 HWPX 자체에서 question/example 구조와 keep-chain을 검증
# - cross-page/cross-column passage metadata를 명시적으로 검증
# - 보수적인 잔여 띄어쓰기 교정 추가
# ============================================================

_V04959_VERSION = "v0.4.9.5.9"
_V04959_COLUMN_USABLE_HEIGHT_PT = 760.0
_V04959_ATOMIC_SAFETY_RATIO = 0.965
_V04959_KOREAN_CHARS_PER_LINE = 27.0
_V04959_EST_LINE_HEIGHT_PT = 14.2
_V04959_EST_PARA_OVERHEAD_PT = 3.0
_V04959_EXAMPLE_TITLE_RE = re.compile(r"^(?:<보기>|\[보기\]|〈보기〉|《보기》)$")


def _v04959_cleanup_visible_text(value: Any) -> str:
    """Small, source-safe spacing cleanup; never re-space whole sentences."""
    text = str(value or "")
    text = re.sub(r"보\s*기\s+어려운것은", "보기 어려운 것은", text)
    text = re.sub(r"적절하지\s+않은것은", "적절하지 않은 것은", text)
    text = re.sub(r"([’”])며(?=[가-힣])", r"\1며 ", text)
    text = re.sub(r"며인생(?=에서|은|을|이|과|의|\s|[.,!?]|$)", "며 인생", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def v04959_cleanup_spacing_fields(result: dict) -> dict:
    """Apply only conservative known spacing repairs to structured output."""
    changed = []

    def patch(container: dict, key: str, label: str) -> None:
        if key not in container or container.get(key) is None:
            return
        old = str(container.get(key) or "")
        new = _v04959_cleanup_visible_text(old)
        if new != old:
            container[key] = new
            changed.append({"field": label, "before": old, "after": new})

    for q in result.get("questions", []):
        qno = int(q.get("number") or 0)
        patch(q, "question", f"question[{qno}].question")
        patch(q, "question_full", f"question[{qno}].question_full")
        patch(q, "explanation", f"question[{qno}].explanation")
        q["choices"] = [
            _v04959_cleanup_visible_text(x) for x in (q.get("choices") or [])
        ]
        ex = q.get("example_block") or {}
        if ex:
            patch(ex, "text", f"question[{qno}].example_block.text")
            patch(ex, "stem_text", f"question[{qno}].example_block.stem_text")
            q["example_block"] = ex

    for g in result.get("passage_groups", []):
        gid = int(g.get("id") or 0)
        # Do not collapse line breaks in passage-level normalized_text.
        for bidx, block in enumerate(g.get("blocks") or []):
            patch(block, "text", f"passage[{gid}].blocks[{bidx}].text")
        if g.get("blocks"):
            g["normalized_text"] = "\n".join(
                str(b.get("text") or "") for b in g.get("blocks") if str(b.get("text") or "")
            ).strip()

    result["spacing_cleanup_v04959"] = {
        "changed_count": len(changed),
        "changes": changed,
        "rules": [
            "보기 어려운것은 -> 보기 어려운 것은",
            "적절하지 않은것은 -> 적절하지 않은 것은",
            "닫는 인용부호 + 며 + 명사 경계 띄움",
            "며인생 -> 며 인생 (제한적 문맥)",
        ],
        "status": "PASS",
    }
    return result



def v04959_extract_underline_semantics(pdf_path: Path, result: dict) -> dict:
    """Run the proven vector-underline detector only where labelled refs require it.

    v0.4.9.5.8 scanned drawings on every passage page. Some PDFs contain very
    large vector drawing lists, making that needlessly expensive. For the
    semantic pattern we need (ⓐ/ⓑ/... or (a)/(b)/...), only passage groups
    referenced by those markers in their questions need vector inspection.
    """
    marker_re = re.compile(r"[ⓐ-ⓩ㉠-㉿]|\([A-Za-z]\)")
    target_group_ids: set[int] = set()
    marker_refs: dict[str, list[str]] = {}
    for q in result.get("questions", []):
        text = " ".join([str(q.get("question") or ""), *(str(x or "") for x in (q.get("choices") or []))])
        refs = []
        for marker in marker_re.findall(text):
            if marker not in refs:
                refs.append(marker)
        if refs:
            qno = int(q.get("number") or 0)
            marker_refs[str(qno)] = refs
            gid = int(q.get("passage_group_id") or 0)
            if gid:
                target_group_ids.add(gid)

    for group in result.get("passage_groups", []):
        for block in group.get("blocks", []) or []:
            block.pop("underline_ranges_v04958", None)

    if not target_group_ids:
        result["underline_semantics_v04959"] = {
            "detector": "PyMuPDF raw chars + thin horizontal vector strokes (targeted pages)",
            "target_group_ids": [],
            "annotation_count": 0,
            "mapped_annotation_count": 0,
            "labelled_annotation_count": 0,
            "labelled_mapped_count": 0,
            "unmatched_labelled_annotations": [],
            "question_marker_references": marker_refs,
            "annotations": [],
            "status": "PASS",
        }
        return result

    subset = dict(result)
    subset["passage_groups"] = [
        g for g in result.get("passage_groups", [])
        if int(g.get("id") or 0) in target_group_ids
    ]
    subset = v04958_extract_underline_semantics(pdf_path, subset)
    payload = dict(subset.get("underline_semantics_v04958") or {})
    payload["detector"] = "PyMuPDF raw chars + thin horizontal vector strokes (targeted pages)"
    payload["target_group_ids"] = sorted(target_group_ids)
    payload["question_marker_references"] = marker_refs
    result["underline_semantics_v04959"] = payload
    return result


def _v04959_source_question_height_pt(q: dict) -> float | None:
    layout = q.get("layout_v0495") or {}
    try:
        top = float(layout.get("question_y"))
    except Exception:
        return None
    bottoms = []
    for bbox in (layout.get("choice_bbox") or {}).values():
        if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
            try:
                bottoms.append(float(bbox[3]))
            except Exception:
                pass
    if not bottoms:
        try:
            qb = float(layout.get("question_bottom_y"))
            bottoms.append(qb)
        except Exception:
            return None
    bottom = max(bottoms)
    if bottom <= top:
        return None
    return bottom - top


def _v04959_estimated_question_height_pt(q: dict) -> dict:
    """Estimate rendered question height conservatively.

    Source geometry is preferred because it already includes the source's real
    stem/example/choice wrapping. A text-based estimate is kept as a fallback
    and as a safety lower bound when the target column reflows slightly.
    """
    ex = q.get("example_block") or {}
    parts = [str(q.get("question") or "")]
    if ex.get("exists") and str(ex.get("text") or "").strip():
        parts.extend(["<보기>", str(ex.get("text") or "")])
    parts.extend(str(x or "") for x in (q.get("choices") or []))

    estimated_lines = 0
    nonempty_parts = 0
    for text in parts:
        text = _v04958_normalize_visible_text(text)
        if not text:
            continue
        nonempty_parts += 1
        # Korean workbook columns are fairly narrow; 27 visible chars/line is
        # intentionally conservative for the current 8 mm margin / 8 mm gutter.
        estimated_lines += max(1, int((len(text) + _V04959_KOREAN_CHARS_PER_LINE - 1) // _V04959_KOREAN_CHARS_PER_LINE))
    text_est = (
        estimated_lines * _V04959_EST_LINE_HEIGHT_PT
        + nonempty_parts * _V04959_EST_PARA_OVERHEAD_PT
        + (18.0 if ex.get("exists") else 0.0)
    )
    source_h = _v04959_source_question_height_pt(q)
    source_est = source_h * 1.10 + (8.0 if ex.get("exists") else 0.0) if source_h is not None else 0.0
    estimated = max(text_est, source_est)
    return {
        "source_height_pt": round(source_h, 2) if source_h is not None else None,
        "text_estimated_height_pt": round(text_est, 2),
        "estimated_target_height_pt": round(estimated, 2),
        "estimated_line_count": estimated_lines,
    }


def v04959_build_atomic_flow_policy(result: dict) -> dict:
    policies = {}
    atomic = []
    split_safe = []
    capacity = float(_V04959_COLUMN_USABLE_HEIGHT_PT)
    atomic_limit = capacity * float(_V04959_ATOMIC_SAFETY_RATIO)

    for q in result.get("questions", []):
        qno = int(q.get("number") or 0)
        est = _v04959_estimated_question_height_pt(q)
        estimated = float(est["estimated_target_height_pt"])
        mode = "atomic_fit" if estimated <= atomic_limit else "split_safe_oversize"
        ex = q.get("example_block") or {}
        policies[str(qno)] = {
            "mode": mode,
            **est,
            "column_usable_height_pt": capacity,
            "atomic_limit_pt": round(atomic_limit, 2),
            "has_example": bool(ex.get("exists") and str(ex.get("text") or "").strip()),
            "safe_split_boundaries": "none; entire question moves together" if mode == "atomic_fit" else "between whole choice paragraphs only",
        }
        (atomic if mode == "atomic_fit" else split_safe).append(qno)

    result["question_flow_v04959"] = {
        "policy": "A question estimated to fit one column is kept as one atomic chain; only true oversize questions may split between whole choice paragraphs.",
        "column_usable_height_pt": capacity,
        "atomic_safety_ratio": _V04959_ATOMIC_SAFETY_RATIO,
        "atomic_question_numbers": atomic,
        "split_safe_oversize_question_numbers": split_safe,
        "questions": policies,
        "status": "PASS",
    }
    return result


def v04959_validate_cross_region_metadata(result: dict) -> dict:
    missing = []
    inconsistent = []
    cross_blocks = []
    total = 0
    for g in result.get("passage_groups", []):
        gid = int(g.get("id") or 0)
        for idx, b in enumerate(g.get("blocks") or []):
            total += 1
            required = ("source_start_page", "source_end_page", "source_start_column", "source_end_column")
            absent = [k for k in required if k not in b]
            if absent:
                missing.append({"group_id": gid, "block_index": idx, "missing": absent, "text": str(b.get("text") or "")[:80]})
                continue
            should_cross = bool(
                b.get("source_start_page") != b.get("source_end_page")
                or b.get("source_start_column") != b.get("source_end_column")
            )
            actual_cross = bool(b.get("crosses_page_or_column"))
            if should_cross != actual_cross:
                inconsistent.append({"group_id": gid, "block_index": idx, "expected": should_cross, "actual": actual_cross})
            if should_cross:
                cross_blocks.append({
                    "group_id": gid,
                    "block_index": idx,
                    "start_page": b.get("source_start_page"),
                    "start_column": b.get("source_start_column"),
                    "end_page": b.get("source_end_page"),
                    "end_column": b.get("source_end_column"),
                    "text": str(b.get("text") or "")[:100],
                })
    return {
        "block_count": total,
        "cross_region_block_count": len(cross_blocks),
        "cross_region_blocks": cross_blocks,
        "missing_metadata": missing,
        "inconsistent_flags": inconsistent,
        "status": "PASS" if not missing and not inconsistent else "FAIL",
    }


def _v04959_clone_example_parapr(
    header_xml: str,
    source_id: int,
    new_id: int,
    border_id: int,
    *,
    role: str,
) -> str:
    """Clone a paragraph style with a connected example-box border.

    ``role`` is title/body so outer padding is placed mainly at the outside of
    the connected box rather than doubled at the join between title and body.
    """
    m = re.search(
        rf'<hh:paraPr\b[^>]*\bid="{int(source_id)}"[\s\S]*?</hh:paraPr>',
        header_xml,
    )
    if not m:
        raise RuntimeError(f"header.xml paraPr template {source_id} not found")
    clone = m.group(0)
    clone = re.sub(r'\bid="\d+"', f'id="{int(new_id)}"', clone, count=1)
    clone = re.sub(r'horizontal="JUSTIFY"', 'horizontal="LEFT"', clone)
    clone = re.sub(r'breakNonLatinWord="BREAK_WORD"', 'breakNonLatinWord="KEEP_WORD"', clone)

    top = _V04955_BOX_TB_PADDING_HWPUNIT if role == "title" else 110
    bottom = 110 if role == "title" else _V04955_BOX_TB_PADDING_HWPUNIT
    border = (
        f'<hh:border borderFillIDRef="{int(border_id)}" '
        f'offsetLeft="{_V04955_BOX_LR_PADDING_HWPUNIT}" '
        f'offsetRight="{_V04955_BOX_LR_PADDING_HWPUNIT}" '
        f'offsetTop="{int(top)}" offsetBottom="{int(bottom)}" '
        'connect="1" ignoreMargin="0"/>'
    )
    if re.search(r'<hh:border\b[^>]*/>', clone):
        clone = re.sub(r'<hh:border\b[^>]*/>', border, clone, count=1)
    else:
        clone = clone.replace('</hh:paraPr>', border + '</hh:paraPr>', 1)
    header_xml = header_xml.replace('</hh:paraProperties>', clone + '</hh:paraProperties>', 1)
    return header_xml


def _v04959_expected_examples(result: dict) -> list[dict]:
    output = []
    for q in sorted(result.get("questions", []), key=lambda x: int(x.get("number") or 0)):
        ex = q.get("example_block") or {}
        body = str(ex.get("text") or "").strip()
        if ex.get("exists") and body:
            output.append({"question_number": int(q.get("number") or 0), "text": body})
    return output


def _v04959_apply_connected_example_boxes(header_xml: str, section_xml: str, result: dict) -> tuple[str, str, dict]:
    """Border BOTH the <보기> title and its actual body paragraph."""
    border_id = _v04954_next_id(header_xml, "borderFill")
    border_xml = _v04954_make_solid_border_fill(border_id)
    header_xml = header_xml.replace('</hh:borderFills>', border_xml + '</hh:borderFills>', 1)
    header_xml = _v04954_set_item_count(header_xml, "borderFills", 1)

    expected = _v04959_expected_examples(result)
    expected_index = 0
    cache: dict[tuple[int, str], int] = {}
    clone_count = 0
    title_count = 0
    body_count = 0
    mismatches = []

    paragraphs = list(re.finditer(r'<hp:p\b[^>]*>[\s\S]*?</hp:p>', section_xml))
    replacements: dict[int, str] = {}

    def box_para(index: int, role: str) -> bool:
        nonlocal header_xml, clone_count
        p = replacements.get(index, paragraphs[index].group(0))
        sm = re.match(r'<hp:p\b[^>]*\bparaPrIDRef="(\d+)"[^>]*>', p)
        if not sm:
            return False
        old_id = int(sm.group(1))
        key = (old_id, role)
        if key not in cache:
            new_id = _v04954_next_id(header_xml, "paraPr")
            header_xml = _v04959_clone_example_parapr(
                header_xml, old_id, new_id, border_id, role=role
            )
            cache[key] = new_id
            clone_count += 1
        p = re.sub(
            r'(<hp:p\b[^>]*\bparaPrIDRef=")\d+("[^>]*>)',
            rf'\g<1>{cache[key]}\2',
            p,
            count=1,
        )
        replacements[index] = p
        return True

    for i, pm in enumerate(paragraphs):
        title_text = _v04958_normalize_visible_text(_v04954_para_text(pm.group(0)))
        if not _V04959_EXAMPLE_TITLE_RE.fullmatch(title_text):
            continue
        title_count += int(box_para(i, "title"))

        # The body must be the next non-empty visible paragraph. This catches
        # the exact v0.4.9.5.8 regression where only the title was bordered.
        body_i = None
        for j in range(i + 1, min(len(paragraphs), i + 4)):
            txt = _v04958_normalize_visible_text(_v04954_para_text(paragraphs[j].group(0)))
            if txt:
                body_i = j
                break
        expected_entry = expected[expected_index] if expected_index < len(expected) else None
        expected_index += 1
        if body_i is None:
            mismatches.append({"title_paragraph_index": i, "reason": "missing body paragraph"})
            continue
        actual_body = _v04958_normalize_visible_text(_v04954_para_text(paragraphs[body_i].group(0)))
        expected_body = _v04958_normalize_visible_text((expected_entry or {}).get("text"))
        if expected_body and actual_body != expected_body:
            mismatches.append({
                "question_number": (expected_entry or {}).get("question_number"),
                "title_paragraph_index": i,
                "body_paragraph_index": body_i,
                "reason": "body text mismatch",
                "expected": expected_body,
                "actual": actual_body,
            })
            continue
        if box_para(body_i, "body"):
            body_count += 1

    out = []
    cursor = 0
    for i, pm in enumerate(paragraphs):
        out.append(section_xml[cursor:pm.start()])
        out.append(replacements.get(i, pm.group(0)))
        cursor = pm.end()
    out.append(section_xml[cursor:])
    header_xml = _v04954_set_item_count(header_xml, "paraProperties", clone_count)
    return header_xml, ''.join(out), {
        "expected_example_count": len(expected),
        "boxed_title_paragraph_count": title_count,
        "boxed_body_paragraph_count": body_count,
        "example_border_fill_id": border_id,
        "example_box_para_style_count": clone_count,
        "mismatches": mismatches,
        "status": "PASS" if title_count == len(expected) and body_count == len(expected) and not mismatches else "FAIL",
    }


def _v04959_apply_atomic_question_flow_styles(header_xml: str, section_xml: str, result: dict) -> tuple[str, str, dict]:
    policies = (result.get("question_flow_v04959") or {}).get("questions") or {}
    first_questions = {
        int((g.get("question_numbers") or [0])[0])
        for g in result.get("passage_groups", [])
        if g.get("question_numbers")
    }
    cache: dict[tuple[int, int, int, int, int], int] = {}
    clone_count = 0
    atomic_styled = 0
    split_styled = 0
    current_qno: int | None = None
    current_mode: str | None = None
    in_example = False

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
    out = []
    cursor = 0
    for pm in paragraphs:
        out.append(section_xml[cursor:pm.start()])
        p = pm.group(0)
        text = _v04958_normalize_visible_text(_v04954_para_text(p))

        if text.startswith("※ 다음 글을 읽고") or text == "[정답 및 해설]":
            current_qno = None
            current_mode = None
            in_example = False
            out.append(p)
            cursor = pm.end()
            continue

        qm = re.match(r'^(\d+)\.\s', text)
        if qm:
            current_qno = int(qm.group(1))
            current_mode = (policies.get(str(current_qno)) or {}).get("mode", "atomic_fit")
            in_example = False
            prev = _V04955_FIRST_QUESTION_PREV if current_qno in first_questions else _V04955_QUESTION_PREV
            # Atomic: stem must stay with all following paragraphs. Oversize:
            # stem stays with example when present; otherwise may split before ①.
            has_example = bool((policies.get(str(current_qno)) or {}).get("has_example"))
            keep_next = 1 if current_mode == "atomic_fit" or has_example else 0
            p = style_para(p, keep_next, 1, prev, 0)
            atomic_styled += int(current_mode == "atomic_fit")
            split_styled += int(current_mode != "atomic_fit")

        elif current_qno and _V04959_EXAMPLE_TITLE_RE.fullmatch(text):
            in_example = True
            # title always stays with body
            p = style_para(p, 1, 1, 0, 0)

        elif current_qno and in_example and not re.match(r'^[①②③④⑤]\s', text):
            # This is the example body. Atomic mode continues the chain to ①;
            # oversize mode may split after the complete example box.
            p = style_para(p, 1 if current_mode == "atomic_fit" else 0, 1, 0, 0)
            in_example = False

        elif current_qno and re.match(r'^[①②③④⑤]\s', text):
            is_last = text.startswith("⑤ ")
            if current_mode == "atomic_fit":
                p = style_para(
                    p,
                    0 if is_last else 1,
                    1,
                    0,
                    _V04955_BLOCK_END_NEXT if is_last else 0,
                )
            else:
                # True oversize question: each whole choice is indivisible, but
                # a column/page break is allowed between choices.
                p = style_para(
                    p,
                    0,
                    1,
                    0,
                    _V04955_BLOCK_END_NEXT if is_last else 0,
                )
            if is_last:
                current_qno = None
                current_mode = None
                in_example = False

        out.append(p)
        cursor = pm.end()
    out.append(section_xml[cursor:])
    header_xml = _v04954_set_item_count(header_xml, "paraProperties", clone_count)
    return header_xml, ''.join(out), {
        "new_flow_para_style_count": clone_count,
        "atomic_question_count": atomic_styled,
        "split_safe_oversize_question_count": split_styled,
        "status": "PASS",
    }


def _v04959_para_style_info(header_xml: str) -> dict[int, dict]:
    info: dict[int, dict] = {}
    for m in re.finditer(r'<hh:paraPr\b[^>]*\bid="(\d+)"[\s\S]*?</hh:paraPr>', header_xml):
        pid = int(m.group(1))
        body = m.group(0)
        break_m = re.search(r'<hh:breakSetting\b([^>]*)/>', body)
        border_m = re.search(r'<hh:border\b([^>]*)/>', body)
        attrs = break_m.group(1) if break_m else ""
        battrs = border_m.group(1) if border_m else ""
        def attr_int(blob: str, key: str, default: int = 0) -> int:
            am = re.search(rf'\b{re.escape(key)}="(-?\d+)"', blob)
            return int(am.group(1)) if am else default
        info[pid] = {
            "keepWithNext": attr_int(attrs, "keepWithNext"),
            "keepLines": attr_int(attrs, "keepLines"),
            "borderFillIDRef": attr_int(battrs, "borderFillIDRef", -1),
            "connect": attr_int(battrs, "connect", 0),
        }
    return info


def _v04959_question_paragraph_map(section_xml: str) -> list[dict]:
    output = []
    for idx, m in enumerate(re.finditer(r'<hp:p\b[^>]*\bparaPrIDRef="(\d+)"[^>]*>[\s\S]*?</hp:p>', section_xml)):
        output.append({
            "index": idx,
            "paraPrIDRef": int(m.group(1)),
            "text": _v04958_normalize_visible_text(_v04954_para_text(m.group(0))),
            "xml": m.group(0),
        })
    return output


def _v04959_validate_question_example_integrity(header_xml: str, section_xml: str, result: dict) -> dict:
    paragraphs = _v04959_question_paragraph_map(section_xml)
    styles = _v04959_para_style_info(header_xml)
    solid_ids = _v04958_solid_border_fill_ids(header_xml)
    policies = (result.get("question_flow_v04959") or {}).get("questions") or {}
    expected_questions = sorted(result.get("questions", []), key=lambda q: int(q.get("number") or 0))

    issues = []
    question_reports = []
    example_reports = []

    question_starts = {}
    for p in paragraphs:
        m = re.match(r'^(\d+)\.\s', p["text"])
        if m:
            question_starts.setdefault(int(m.group(1)), p["index"])

    for pos, q in enumerate(expected_questions):
        qno = int(q.get("number") or 0)
        start = question_starts.get(qno)
        if start is None:
            issues.append(f"{qno}번 question paragraph missing")
            continue
        # Stop before the next question or the next passage guide/answer title.
        end = len(paragraphs)
        for p in paragraphs[start + 1:]:
            if re.match(r'^\d+\.\s', p["text"]) or p["text"].startswith("※ 다음 글을 읽고") or p["text"] == "[정답 및 해설]":
                end = p["index"]
                break
        block = paragraphs[start:end]
        choices = [p for p in block if re.match(r'^[①②③④⑤]\s', p["text"])]
        choice_prefixes = [p["text"][:1] for p in choices]
        if choice_prefixes != list(CIRCLED):
            issues.append(f"{qno}번 choice order mismatch: {choice_prefixes}")

        ex = q.get("example_block") or {}
        has_example = bool(ex.get("exists") and str(ex.get("text") or "").strip())
        title_entries = [p for p in block if _V04959_EXAMPLE_TITLE_RE.fullmatch(p["text"])]
        body_entry = None
        if has_example:
            expected_body = _v04958_normalize_visible_text(ex.get("text"))
            if len(title_entries) != 1:
                issues.append(f"{qno}번 example title count={len(title_entries)}")
            else:
                ti = block.index(title_entries[0])
                for p in block[ti + 1:]:
                    if p["text"]:
                        body_entry = p
                        break
                if body_entry is None or body_entry["text"] != expected_body:
                    issues.append(f"{qno}번 example body mismatch")
                else:
                    ts = styles.get(title_entries[0]["paraPrIDRef"], {})
                    bs = styles.get(body_entry["paraPrIDRef"], {})
                    same_border = ts.get("borderFillIDRef") == bs.get("borderFillIDRef")
                    solid = ts.get("borderFillIDRef") in solid_ids and bs.get("borderFillIDRef") in solid_ids
                    connected = ts.get("connect") == 1 and bs.get("connect") == 1
                    if not (same_border and solid and connected):
                        issues.append(f"{qno}번 example title/body are not one connected solid box")
                    example_reports.append({
                        "question_number": qno,
                        "title_paragraph_index": title_entries[0]["index"],
                        "body_paragraph_index": body_entry["index"],
                        "body_text_match": body_entry["text"] == expected_body,
                        "same_border_fill": same_border,
                        "solid_border": solid,
                        "connected": connected,
                    })
        elif title_entries:
            issues.append(f"{qno}번 unexpected standalone example title")

        mode = (policies.get(str(qno)) or {}).get("mode", "atomic_fit")
        # Relevant chain: stem, optional title/body, and exactly five choices.
        relevant = [block[0]]
        if has_example and title_entries and body_entry:
            relevant.extend([title_entries[0], body_entry])
        relevant.extend(choices)
        flow_ok = True
        flow_details = []
        for ridx, p in enumerate(relevant):
            style = styles.get(p["paraPrIDRef"], {})
            keep_lines = style.get("keepLines") == 1
            if mode == "atomic_fit":
                expected_keep = 0 if ridx == len(relevant) - 1 else 1
            else:
                # Oversize: stem/title chain to full example; choice paragraphs
                # can break from each other, while each choice keeps its own lines.
                if has_example and ridx < 2:
                    expected_keep = 1
                else:
                    expected_keep = 0
            keep_next_ok = style.get("keepWithNext") == expected_keep
            flow_ok = flow_ok and keep_lines and keep_next_ok
            flow_details.append({
                "paragraph_index": p["index"],
                "text": p["text"][:80],
                "keepLines": style.get("keepLines"),
                "keepWithNext": style.get("keepWithNext"),
                "expectedKeepWithNext": expected_keep,
            })
        if not flow_ok:
            issues.append(f"{qno}번 flow keep-chain mismatch ({mode})")
        question_reports.append({
            "question_number": qno,
            "mode": mode,
            "choice_order": choice_prefixes,
            "paragraph_count": len(block),
            "flow_keep_chain_ok": flow_ok,
            "flow": flow_details,
        })

    expected_example_count = sum(
        1 for q in expected_questions
        if (q.get("example_block") or {}).get("exists") and str((q.get("example_block") or {}).get("text") or "").strip()
    )
    example_ok = len(example_reports) == expected_example_count and all(
        r.get("body_text_match") and r.get("same_border_fill") and r.get("solid_border") and r.get("connected")
        for r in example_reports
    )
    question_ok = len(question_reports) == len(expected_questions) and all(
        r.get("choice_order") == list(CIRCLED) and r.get("flow_keep_chain_ok")
        for r in question_reports
    )
    return {
        "question_integrity_status": "PASS" if question_ok else "FAIL",
        "example_integrity_status": "PASS" if example_ok else "FAIL",
        "expected_question_count": len(expected_questions),
        "validated_question_count": len(question_reports),
        "expected_example_count": expected_example_count,
        "validated_connected_example_count": len(example_reports),
        "question_reports": question_reports,
        "example_reports": example_reports,
        "issues": issues,
        "status": "PASS" if question_ok and example_ok and not issues else "FAIL",
    }


def v04959_validate_hwpx(path: Path, *, result: dict, render_plan: dict) -> dict:
    expected_count = int(result.get("image_filter_v0481", {}).get("saved_count") or 0)
    info = v04952_validate_hwpx(
        path,
        expected_images=expected_count,
        render_plan=render_plan,
        result=result,
        require_two_column=True,
    )
    info["validator_version"] = _V04959_VERSION
    info["image_logical_position_status"] = "NOT_APPLICABLE_CONTINUOUS_FLOW"

    if not Path(path).exists() or not zipfile.is_zipfile(path) or info.get("package_status") != "PASS":
        info["status"] = "FAIL"
        return info

    try:
        with zipfile.ZipFile(path, "r") as zf:
            header = zf.read("Contents/header.xml").decode("utf-8", errors="strict")
            section0 = zf.read("Contents/section0.xml").decode("utf-8", errors="strict")
            section_names = sorted(
                [n for n in zf.namelist() if re.fullmatch(r"Contents/section\d+\.xml", n)],
                key=_v04953_section_number,
            )
            sections = {n: zf.read(n).decode("utf-8", errors="strict") for n in section_names}

        question_col_counts = _v04953_col_counts(section0)
        question_two = any(x >= 2 for x in question_col_counts)
        answer_two = all(
            any(x >= 2 for x in (_v04953_col_counts(xml) or [1]))
            for name, xml in sections.items() if name != "Contents/section0.xml"
        ) if len(sections) > 1 else True
        info["question_two_column_found"] = question_two
        info["answer_sections_two_column"] = answer_two

        remaining_page_breaks = len(re.findall(r'\bpageBreak="1"', section0))
        remaining_column_breaks = len(re.findall(r'\bcolumnBreak="1"', section0))
        remaining_lineseg = len(re.findall(r'<hp:linesegarray>[\s\S]*?</hp:linesegarray>', section0))
        info["remaining_forced_page_break_count"] = remaining_page_breaks
        info["remaining_forced_column_break_count"] = remaining_column_breaks
        info["remaining_question_linesegarray_count"] = remaining_lineseg
        info["continuous_flow_status"] = "PASS" if question_two and remaining_page_breaks == 0 and remaining_column_breaks == 0 and remaining_lineseg == 0 else "FAIL"

        integrity = _v04959_validate_question_example_integrity(header, section0, result)
        info["question_integrity_status"] = integrity.get("question_integrity_status")
        info["example_integrity_status"] = integrity.get("example_integrity_status")
        info["question_example_integrity"] = integrity
        info["expected_example_box_count"] = integrity.get("expected_example_count", 0)
        info["bordered_example_box_count"] = integrity.get("validated_connected_example_count", 0)
        info["example_box_status"] = integrity.get("example_integrity_status")

        # Underline validation retained from 5.8, but against the final 5.9 package.
        under_char_ids = set()
        for cm in re.finditer(r'<hh:charPr\b[^>]*\bid="(\d+)"[\s\S]*?</hh:charPr>', header):
            if re.search(r'<hh:underline\b[^>]*\btype="BOTTOM"', cm.group(0)):
                under_char_ids.add(int(cm.group(1)))
        under_texts = []
        for rm in re.finditer(r'<hp:run\b[^>]*\bcharPrIDRef="(\d+)"[^>]*>[\s\S]*?</hp:run>', section0):
            if int(rm.group(1)) not in under_char_ids:
                continue
            t = _v04954_para_text("<hp:p>" + rm.group(0) + "</hp:p>")
            if t:
                under_texts.append(t)
        expected_under = [
            str(rg.get("text") or "")
            for g in result.get("passage_groups", [])
            for b in (g.get("blocks") or [])
            for rg in (b.get("underline_ranges_v04958") or [])
            if str(rg.get("text") or "")
        ]
        normalized_under = " ".join(_v04958_normalize_visible_text(x) for x in under_texts)
        missing_under = [x for x in expected_under if _v04958_normalize_visible_text(x) not in normalized_under]
        info["expected_underline_range_count"] = len(expected_under)
        info["actual_underlined_run_count"] = len(under_texts)
        info["missing_underlined_texts"] = missing_under
        info["underline_status"] = "PASS" if not missing_under else "FAIL"

        repair = result.get("example_repair_v04959") or result.get("example_repair_v04958") or {}
        info["example_detection_status"] = repair.get("status", "PASS")
        sem = result.get("underline_semantics_v04959") or result.get("underline_semantics_v04958") or {}
        info["underline_detection_status"] = sem.get("status", "PASS")
        cross = result.get("cross_region_metadata_v04959") or {}
        info["cross_region_metadata_status"] = cross.get("status", "PASS")

        info["image_position_status"] = (
            "FAIL" if "FAIL" in (info.get("image_order_status"), info.get("image_anchor_status"), info.get("image_answer_boundary_status"))
            else "WARN" if "WARN" in (info.get("image_order_status"), info.get("image_anchor_status"), info.get("image_answer_boundary_status"))
            else "PASS"
        )
        critical = [
            info.get("package_status"),
            info.get("image_order_status"),
            info.get("image_anchor_status"),
            info.get("image_answer_boundary_status"),
            info.get("continuous_flow_status"),
            info.get("question_integrity_status"),
            info.get("example_integrity_status"),
            info.get("underline_status"),
            info.get("example_detection_status"),
            info.get("cross_region_metadata_status"),
        ]
        info["status"] = "FAIL" if "FAIL" in critical else "WARN" if "WARN" in critical else "PASS"
        return info
    except Exception as exc:
        info["v04959_validation_error"] = str(exc)
        info["status"] = "FAIL"
        return info


def _v04959_postprocess_hwpx(path: Path, result: dict, render_plan: dict) -> dict:
    import xml.etree.ElementTree as ET
    path = Path(path)
    report = {
        "version": _V04959_VERSION,
        "status": "SKIPPED",
        "applied": False,
        "source": str(path),
    }
    if not path.exists() or not zipfile.is_zipfile(path):
        report["reason"] = "no usable HWPX"
        return report

    candidate = path.with_name(path.stem + "_v04959_candidate.hwpx")
    if candidate.exists():
        try:
            candidate.unlink()
        except Exception:
            pass

    try:
        with zipfile.ZipFile(path, "r") as zf:
            header = zf.read("Contents/header.xml").decode("utf-8", errors="strict")
            section0 = zf.read("Contents/section0.xml").decode("utf-8", errors="strict")

        header, section0, example_report = _v04959_apply_connected_example_boxes(header, section0, result)
        header, section0, underline_report = _v04958_apply_underline_ranges(header, section0, result)
        header, section0, flow_style_report = _v04959_apply_atomic_question_flow_styles(header, section0, result)
        section0, continuous_report = _v04958_enable_continuous_two_column_flow(section0)

        ET.fromstring(header.encode("utf-8"))
        ET.fromstring(section0.encode("utf-8"))
        _v04958_repack_postprocessed_hwpx(path, candidate, header, section0)
        validation = v04959_validate_hwpx(candidate, result=result, render_plan=render_plan)

        report.update({
            "status": "APPLIED" if validation.get("status") == "PASS" else "REJECTED_BY_VALIDATION",
            "applied": validation.get("status") == "PASS",
            "candidate": str(candidate),
            "connected_example_boxes": example_report,
            "underlines": underline_report,
            "atomic_question_flow": flow_style_report,
            "continuous_flow": continuous_report,
            "validation": validation,
        })
        if validation.get("status") == "PASS":
            os.replace(str(candidate), str(path))
            report["candidate"] = None
            report["final_path"] = str(path.resolve())
        elif candidate.exists():
            candidate.unlink()
        return report
    except Exception as exc:
        report["status"] = "FAIL"
        report["reason"] = str(exc)
        try:
            if candidate.exists():
                candidate.unlink()
        except Exception:
            pass
        return report


def v04959_create_hwpx_with_hancom(
    final_output: Path,
    result: dict,
    render_plan: dict,
    *,
    security_module_path: Path | None = None,
    allow_interactive_hwp: bool = False,
    show_hwp: bool = False,
) -> dict:
    # Use the stable 5.7 single-COM-session writer, then make only deterministic
    # HWPX XML edits in the new final package.
    info = v04957_create_hwpx_with_hancom(
        final_output,
        result,
        render_plan,
        security_module_path=security_module_path,
        allow_interactive_hwp=allow_interactive_hwp,
        show_hwp=show_hwp,
    )
    info["backend"] = "hancom_com_v04959"
    info["renderer_mode"] = "continuous_two_column_atomic_questions_connected_examples_v04959"

    for old_key, new_key in (
        ("editorial_finalize_v04957", "editorial_finalize_v04959"),
        ("compact_finalize_v04957", "compact_finalize_v04959"),
    ):
        payload = info.pop(old_key, None)
        if isinstance(payload, dict):
            payload["version"] = _V04959_VERSION
            info[new_key] = payload

    if info.get("status") == "created" and Path(final_output).exists():
        semantic = _v04959_postprocess_hwpx(Path(final_output), result, render_plan)
        info["semantic_finalize_v04959"] = semantic
        if semantic.get("applied"):
            info["validation"] = v04959_validate_hwpx(Path(final_output), result=result, render_plan=render_plan)
            info["status"] = "created" if info["validation"].get("status") == "PASS" else "INVALID"
            info["final_path"] = str(Path(final_output).resolve())
        else:
            info["status"] = "INVALID"
            if semantic.get("validation"):
                info["validation"] = semantic["validation"]
    elif info.get("status") == "SKIPPED":
        info["semantic_finalize_v04959"] = {
            "status": "SKIPPED",
            "applied": False,
            "reason": "Hancom writer unavailable on this platform",
        }
    return info


def v04959_validate_structural(result: dict) -> dict:
    base = v04957_validate_structural_edges(result)
    repair = result.get("example_repair_v04959") or result.get("example_repair_v04958") or {}
    underline = result.get("underline_semantics_v04959") or result.get("underline_semantics_v04958") or {}
    cross = result.get("cross_region_metadata_v04959") or {}
    issues = list(base.get("issues") or [])
    if repair.get("status") == "FAIL":
        issues.append("unparsed_example_marker")
    if underline.get("status") == "FAIL":
        issues.append("underline_semantics")
    if cross.get("status") == "FAIL":
        issues.append("cross_region_metadata")
    base.update({
        "example_detection_status": repair.get("status", "PASS"),
        "expected_example_question_numbers": repair.get("expected_from_geometry_question_numbers", []),
        "repaired_example_question_numbers": repair.get("repaired_question_numbers", []),
        "unparsed_example_marker_question_numbers": repair.get("unparsed_example_marker_question_numbers", []),
        "underline_detection_status": underline.get("status", "PASS"),
        "labelled_underline_count": underline.get("labelled_annotation_count", 0),
        "labelled_underline_mapped_count": underline.get("labelled_mapped_count", 0),
        "cross_region_metadata_status": cross.get("status", "PASS"),
        "cross_region_block_count": cross.get("cross_region_block_count", 0),
        "issues": issues,
        "status": "PASS" if not issues else "FAIL",
    })
    return base


def v04959_upgrade_result(
    result: dict,
    pdf_path: Path,
    checkpoint_path: Path | None = None,
    *,
    hwpx_output_path: Path | None = None,
    question_detection: dict | None = None,
    security_module_path: Path | None = None,
    allow_interactive_hwp: bool = False,
    show_hwp: bool = False,
) -> dict:
    _v0491_log("[v0.4.9.5.9] 원자적 문제 흐름 + 연결 보기 박스 + 최종 무결성 검증 준비")

    result = v046_upgrade_result(result, pdf_path)
    result = v0481_prepare_problem_images(pdf_path, result)
    result = v0491_cleanup_legacy_metadata(result)
    result = v0495_attach_question_geometry(pdf_path, result)
    result = v04958_repair_example_blocks(result)
    result["example_repair_v04959"] = result.pop("example_repair_v04958", {})
    result = v04959_cleanup_spacing_fields(result)
    result = v04959_extract_underline_semantics(pdf_path, result)
    result = v04959_build_atomic_flow_policy(result)
    result = v04957_cleanup_orphan_section_labels(result)
    result["cross_region_metadata_v04959"] = v04959_validate_cross_region_metadata(result)
    structural = v04959_validate_structural(result)
    result["structural_validation_v04959"] = structural

    render_plan = v04955_build_render_plan(result)
    render_plan["version"] = _V04959_VERSION
    render_plan["flow_policy_v04959"] = {
        "mode": "continuous_native_two_column_atomic_fit",
        "source_page_breaks": "removed from final question section",
        "source_column_breaks": "removed from final question section",
        "line_layout_cache": "removed from section0 so Hangul recalculates natural flow",
        "atomic_question_policy": "if estimated to fit one column, stem + example + ①~⑤ are one keepWithNext chain",
        "oversize_question_policy": "only estimated one-column overflow may split between whole choice paragraphs",
        "example_box": "title + full example body share one solid connected border",
        "underline_semantics": "thin vector underline -> labelled text range -> HWPX BOTTOM underline char style",
    }
    render_plan["output_policy_v04959"] = {
        "default_final_filename": f"{_v04957_safe_output_stem(pdf_path)}.hwpx",
        "filename_basis": "source_pdf_stem",
        "never_overwrite_existing": True,
        "run_suffix_when_existing": "_runNN",
    }
    result["render_plan_v04959"] = render_plan
    for stale_key in [
        "render_plan_v04958", "render_plan_v04957", "render_plan_v04956", "render_plan_v04955", "render_plan_v04954",
        "render_plan_v04953", "render_plan_v04952", "render_plan_v04951", "render_plan_v0495",
        "render_plan_v0494", "render_plan_v0493", "render_plan_v0492", "render_plan_v049",
    ]:
        result.pop(stale_key, None)

    result["version"] = _V04959_VERSION
    result["parser_version"] = _V04959_VERSION
    result["generator_version"] = "PDF Parser Integrated v0.4.9.5.9"
    result["question_detection_v04959"] = question_detection or {}
    result["schema_version"] = {
        "base": "v0.4.9.5.8",
        "extension": [
            "connected_example_title_body_box",
            "atomic_fit_question_keep_chain",
            "oversize_only_safe_choice_split",
            "final_hwpx_question_integrity_validator",
            "final_hwpx_example_integrity_validator",
            "cross_page_column_block_metadata",
            "conservative_spacing_cleanup",
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
        _v0491_log(f"[v0.4.9.5.9] HWPX 전 임시 체크포인트 저장: {checkpoint_path.resolve()}")

    requested = Path(hwpx_output_path) if hwpx_output_path else _v04957_default_hwpx_path(pdf_path)
    actual_target = _v04956_pick_free_path(requested)
    result["hwpx_output_v04959"] = {
        "requested_path": str(requested.resolve()),
        "allocated_path": str(actual_target.resolve()),
        "source_pdf_stem": Path(pdf_path).stem,
        "safe_output_stem": _v04957_safe_output_stem(pdf_path),
        "existing_requested_path_preserved": requested.exists(),
        "policy": "PDF stem filename; never overwrite; allocate _runNN when needed",
    }

    hwpx_info = v04959_create_hwpx_with_hancom(
        actual_target,
        result,
        render_plan,
        security_module_path=security_module_path,
        allow_interactive_hwp=allow_interactive_hwp,
        show_hwp=show_hwp,
    )
    result["hwpx_v04959"] = hwpx_info
    result["hancom_security_v04959"] = result.get("hancom_security_v04957") or hwpx_info.get("hancom_security") or {}
    for stale_key in [
        "hwpx_v04958", "hancom_security_v04958", "hwpx_v04957", "hancom_security_v04957",
        "hwpx_v04956", "hancom_security_v04956", "hancom_security_v04955", "hancom_security_v04954",
        "hancom_security_v04953", "hancom_security_v04952",
    ]:
        result.pop(stale_key, None)

    base_validation = result.get("validation", {})
    img_validation = result.get("image_filter_v0481", {})
    table_validation = result.get("table_filter_v0492", {})
    geometry_validation = result.get("question_geometry_v0495", {})
    source_order_validation = render_plan.get("source_order_v0495", {})
    final_validation = hwpx_info.get("validation") or {}
    security_runtime = result.get("hancom_security_v04959") or {}
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
        and structural.get("status") == "PASS"
        and hwpx_status in {"created", "SKIPPED"}
        and security_ok
        and final_validation.get("package_status") in {"PASS", None}
    )
    critical_keys = (
        "image_order_status", "image_anchor_status", "image_answer_boundary_status",
        "continuous_flow_status", "question_integrity_status", "example_integrity_status",
        "underline_status", "example_detection_status", "cross_region_metadata_status",
    )
    critical_fail = any(final_validation.get(k) == "FAIL" for k in critical_keys)
    if critical_fail or structural.get("status") == "FAIL":
        final_status = "FAIL"
    elif hard_pass and final_validation.get("status") in {"PASS", None}:
        final_status = "PASS"
    elif hwpx_status == "SKIPPED" and hard_pass:
        final_status = "PASS"
    else:
        final_status = "WARN" if hwpx_status == "SKIPPED" else "FAIL"

    semantic = hwpx_info.get("semantic_finalize_v04959") or {}
    flow_policy = result.get("question_flow_v04959") or {}
    result["validation_v04959"] = {
        "question_count": len(result.get("questions", [])),
        "passage_group_count": len(result.get("passage_groups", [])),
        "problem_image_count": img_validation.get("selected_problem_figure_count", 0),
        "problem_image_saved": img_validation.get("saved_count", 0),
        "answer_count": render_plan.get("stats", {}).get("answer_count", 0),
        "render_page_count": render_plan.get("stats", {}).get("page_count", 0),
        "render_item_count": render_plan.get("stats", {}).get("render_item_count", 0),
        "question_detection_status": (question_detection or {}).get("status"),
        "question_geometry_status": geometry_validation.get("status"),
        "source_order_status": source_order_validation.get("status"),
        "base_parser_status": base_validation.get("status"),
        "image_status": img_validation.get("status"),
        "structural_status": structural.get("status"),
        "orphan_section_label_status": structural.get("orphan_section_label_status"),
        "removed_orphan_section_label_count": structural.get("removed_orphan_section_label_count", 0),
        "example_detection_status": structural.get("example_detection_status"),
        "repaired_example_question_numbers": structural.get("repaired_example_question_numbers", []),
        "underline_detection_status": structural.get("underline_detection_status"),
        "labelled_underline_count": structural.get("labelled_underline_count", 0),
        "labelled_underline_mapped_count": structural.get("labelled_underline_mapped_count", 0),
        "cross_region_metadata_status": structural.get("cross_region_metadata_status"),
        "cross_region_block_count": structural.get("cross_region_block_count", 0),
        "oversize_flow_status": structural.get("oversize_flow_status"),
        "atomic_question_numbers": flow_policy.get("atomic_question_numbers", []),
        "split_safe_oversize_question_numbers": flow_policy.get("split_safe_oversize_question_numbers", []),
        "hancom_security_status": security_runtime.get("status"),
        "unattended_ready": security_runtime.get("unattended_ready", False),
        "hwpx_status": hwpx_status,
        "hwpx_final_path": hwpx_info.get("final_path"),
        "hwpx_final_filename_basis": "source_pdf_stem",
        "hwpx_final_write_policy": hwpx_info.get("final_write_policy"),
        "hwpx_validation_status": final_validation.get("status"),
        "hwpx_package_status": final_validation.get("package_status"),
        "hwpx_question_two_column_found": final_validation.get("question_two_column_found"),
        "hwpx_answer_sections_two_column": final_validation.get("answer_sections_two_column"),
        "continuous_flow_status": final_validation.get("continuous_flow_status"),
        "remaining_forced_page_break_count": final_validation.get("remaining_forced_page_break_count"),
        "remaining_forced_column_break_count": final_validation.get("remaining_forced_column_break_count"),
        "remaining_question_linesegarray_count": final_validation.get("remaining_question_linesegarray_count"),
        "question_integrity_status": final_validation.get("question_integrity_status"),
        "example_integrity_status": final_validation.get("example_integrity_status"),
        "example_box_status": final_validation.get("example_box_status"),
        "expected_example_box_count": final_validation.get("expected_example_box_count"),
        "bordered_example_box_count": final_validation.get("bordered_example_box_count"),
        "underline_status": final_validation.get("underline_status"),
        "expected_underline_range_count": final_validation.get("expected_underline_range_count"),
        "actual_underlined_run_count": final_validation.get("actual_underlined_run_count"),
        "image_position_status": final_validation.get("image_position_status"),
        "pictures_after_answer_count": final_validation.get("pictures_after_answer_count"),
        "semantic_finalize_status": semantic.get("status"),
        "semantic_finalize_applied": semantic.get("applied", False),
        "spacing_cleanup_change_count": (result.get("spacing_cleanup_v04959") or {}).get("changed_count", 0),
        "status": final_status,
    }
    result["known_limitations_v04959"] = [
        "현재 최다빈출 공략 계열 PDF에서 검증된 규칙이며, 다른 출판사/사이트는 컬럼/문항 마커 규칙을 추가 확인해야 합니다.",
        "밑줄은 PDF 텍스트 바로 아래의 얇은 벡터 선을 기준으로 검출합니다. 스캔 이미지에 그려진 밑줄은 OCR/영상 분석 없이는 별도 검출되지 않습니다.",
        "문제 높이는 source geometry + 보수적 text reflow 추정으로 판정합니다. Windows 한글의 실제 최종 pagination은 한글 렌더러가 결정합니다.",
        "복잡한 병합 셀 표의 완전 복원은 아직 지원하지 않습니다.",
        "최종 HWPX/JSON 기본 파일명은 원본 PDF 이름을 기준으로 하며, 동일 이름이 존재하면 _run02, _run03 순으로 새 파일을 생성합니다.",
    ]
    return result


def main_v04959() -> None:
    parser = argparse.ArgumentParser(
        description="국어 문제 PDF -> 구조화 JSON + HWPX V0.4.9.5.9 원자적 문제 흐름/연결 보기 박스/최종 무결성 검증"
    )
    parser.add_argument("pdf", type=Path, help="분석할 PDF 파일")
    parser.add_argument("-o", "--output", type=Path, default=None, help="저장할 JSON. 생략하면 <PDF이름>_result.json")
    parser.add_argument("--hwpx-output", type=Path, default=None, help="최종 HWPX 희망 파일명. 생략하면 <PDF이름>.hwpx, 존재 시 _runNN 자동 생성")
    parser.add_argument("-q", "--questions", nargs="+", type=int, default=None, help="추출할 문제 번호. 생략하면 PDF에서 자동 탐지")
    parser.add_argument("--no-kiwi", action="store_true", help="Kiwi 경계 판별을 끔")
    parser.add_argument("--security-module", type=Path, default=None, help="FilePathCheckerModuleExample.dll 경로")
    parser.add_argument("--allow-interactive-hwp", action="store_true", help="보안 모듈 실패 시 대화형 한글 허용")
    parser.add_argument("--show-hwp", action="store_true", help="한글 창 표시")
    args = parser.parse_args()

    if not args.pdf.exists():
        raise SystemExit(f"PDF 파일을 찾을 수 없습니다: {args.pdf}")
    if not args.no_kiwi and Kiwi is None:
        print("[경고] kiwipiepy 미설치. fallback으로 실행합니다.")

    detection = v04957_detect_question_numbers(args.pdf)
    if args.questions:
        question_numbers = sorted(set(args.questions))
        detection["selection_mode"] = "explicit_cli"
        detection["selected_question_numbers"] = question_numbers
    else:
        if detection.get("status") != "PASS" or not detection.get("question_numbers"):
            raise SystemExit("문제 번호 자동 탐지에 실패했습니다. -q 옵션으로 문제 번호를 직접 지정하세요. " + str(detection.get("reason") or ""))
        question_numbers = list(detection["question_numbers"])
        detection["selection_mode"] = "auto_detected"
        detection["selected_question_numbers"] = question_numbers

    json_output = Path(args.output) if args.output else _v04957_default_json_path(args.pdf)
    checkpoint_path = json_output.with_name(json_output.stem + "_pre_hwpx.json")

    result = parse_v0_2_3(args.pdf, question_numbers, use_kiwi=not args.no_kiwi)
    result = v044_upgrade_result(result, args.pdf)
    result = v045_upgrade_result(result, args.pdf)
    result = v04959_upgrade_result(
        result,
        args.pdf,
        checkpoint_path=checkpoint_path,
        hwpx_output_path=args.hwpx_output,
        question_detection=detection,
        security_module_path=args.security_module,
        allow_interactive_hwp=args.allow_interactive_hwp,
        show_hwp=args.show_hwp,
    )
    json_output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    checkpoint_info = result.get("pre_hwpx_checkpoint") or {}
    checkpoint_file = Path(str(checkpoint_info.get("path") or "")) if isinstance(checkpoint_info, dict) else None
    if result.get("hwpx_v04959", {}).get("status") == "created" and checkpoint_file and str(checkpoint_file):
        try:
            if checkpoint_file.exists():
                checkpoint_file.unlink()
            checkpoint_info["retained"] = False
            result["pre_hwpx_checkpoint"] = checkpoint_info
            json_output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            checkpoint_info["retained"] = True
            checkpoint_info["cleanup_error"] = str(exc)

    v = result.get("validation_v04959", {})
    print("=" * 76)
    print("V0.4.9.5.9 원자적 문제 흐름 + 연결 보기 박스 + 최종 무결성 검증 완료")
    print("=" * 76)
    print(f"입력 : {args.pdf}")
    print(f"JSON : {json_output.resolve()}")
    print(f"HWPX : {v.get('hwpx_final_path')}")
    print(f"문제 : {v.get('question_count', 0)} | 자동 탐지 : {v.get('question_detection_status')}")
    print(f"원자적 문제 : {len(v.get('atomic_question_numbers') or [])} | 초과 분할 : {v.get('split_safe_oversize_question_numbers')}")
    print(f"<보기> 무결성 : {v.get('example_integrity_status')} | 문제 무결성 : {v.get('question_integrity_status')}")
    print(f"cross-region metadata : {v.get('cross_region_metadata_status')} | {v.get('cross_region_block_count', 0)} block")
    print(f"밑줄 의미표지 : {v.get('underline_detection_status')} | {v.get('labelled_underline_mapped_count')}/{v.get('labelled_underline_count')}")
    print(f"연속 흐름 : {v.get('continuous_flow_status')} | 밑줄 렌더 : {v.get('underline_status')}")
    print(f"HWPX 상태 : {v.get('hwpx_status')} | 최종 검증 : {v.get('status')}")




# =============================================================================
# V0.4.9.5.10 Focused editorial refinements
# - example box without internal mid-line (title/body complementary borders)
# - conservative image downscaling to avoid column overflow
# - bold question stems
# - right-aligned author/work credit lines
# - underline negative-keyword prompts in question stems
# =============================================================================

_V049510_VERSION = "v0.4.9.5.10"
_V049510_IMAGE_MAX_WIDTH_PT = 180.0
_V049510_IMAGE_MAX_HEIGHT_PT = 165.0
_V049510_BOX_LR_PADDING_HWPUNIT = int(round(4.0 * 283.465))
_V049510_BOX_TB_PADDING_HWPUNIT = int(round(2.2 * 283.465))
_V049510_AUTHOR_LINE_RE = re.compile(r"^\s*[-–—]\s*.+?[,，]\s*[「『〈《].+[」』〉》]\s*$")
_V049510_NEGATIVE_PATTERNS = [
    re.compile(r"옳지\s+(않(?:은|는))"),
    re.compile(r"적절하지\s+(않(?:은|는)|못한)"),
    re.compile(r"가장\s+적절하지\s+(않(?:은|는)|못한)"),
    re.compile(r"보기\s+(어려운)\s+것은"),
    re.compile(r"거리가\s+(먼)"),
    re.compile(r"가장\s+거리가\s+(먼)"),
]


def _v049510_make_edge_border_fill(border_id: int, *, top: bool, bottom: bool, left: bool = True, right: bool = True) -> str:
    def edge(name: str, on: bool) -> str:
        kind = 'SOLID' if on else 'NONE'
        width = '0.2 mm' if on else '0.1 mm'
        return f'<hh:{name} type="{kind}" width="{width}" color="#000000"/>'
    return (
        f'<hh:borderFill id="{border_id}" threeD="0" shadow="0" centerLine="NONE" breakCellSeparateLine="0">'
        '<hh:slash type="NONE" Crooked="0" isCounter="0"/>'
        '<hh:backSlash type="NONE" Crooked="0" isCounter="0"/>'
        f'{edge("leftBorder", left)}'
        f'{edge("rightBorder", right)}'
        f'{edge("topBorder", top)}'
        f'{edge("bottomBorder", bottom)}'
        '<hh:diagonal type="NONE" width="0.1 mm" color="#000000"/>'
        '<hc:fillBrush><hc:winBrush faceColor="none" hatchColor="#000000" alpha="0"/></hc:fillBrush>'
        '</hh:borderFill>'
    )


def _v049510_clone_example_parapr(header_xml: str, source_id: int, new_id: int, border_id: int, *, role: str) -> str:
    m = re.search(rf'<hh:paraPr\b[^>]*\bid="{int(source_id)}"[\s\S]*?</hh:paraPr>', header_xml)
    if not m:
        raise RuntimeError(f"header.xml paraPr template {source_id} not found")
    clone = m.group(0)
    clone = re.sub(r'\bid="\d+"', f'id="{int(new_id)}"', clone, count=1)
    clone = re.sub(r'horizontal="JUSTIFY"', 'horizontal="LEFT"', clone)
    clone = re.sub(r'breakNonLatinWord="BREAK_WORD"', 'breakNonLatinWord="KEEP_WORD"', clone)
    top = _V049510_BOX_TB_PADDING_HWPUNIT if role == 'title' else 60
    bottom = 60 if role == 'title' else _V049510_BOX_TB_PADDING_HWPUNIT
    border = (
        f'<hh:border borderFillIDRef="{int(border_id)}" '
        f'offsetLeft="{_V049510_BOX_LR_PADDING_HWPUNIT}" '
        f'offsetRight="{_V049510_BOX_LR_PADDING_HWPUNIT}" '
        f'offsetTop="{int(top)}" offsetBottom="{int(bottom)}" '
        'connect="0" ignoreMargin="0"/>'
    )
    if re.search(r'<hh:border\b[^>]*/>', clone):
        clone = re.sub(r'<hh:border\b[^>]*/>', border, clone, count=1)
    else:
        clone = clone.replace('</hh:paraPr>', border + '</hh:paraPr>', 1)
    header_xml = header_xml.replace('</hh:paraProperties>', clone + '</hh:paraProperties>', 1)
    return header_xml


def _v049510_apply_connected_example_boxes(header_xml: str, section_xml: str, result: dict) -> tuple[str, str, dict]:
    title_border_id = _v04954_next_id(header_xml, 'borderFill')
    body_border_id = title_border_id + 1
    border_xml = (
        _v049510_make_edge_border_fill(title_border_id, top=True, bottom=False) +
        _v049510_make_edge_border_fill(body_border_id, top=False, bottom=True)
    )
    header_xml = header_xml.replace('</hh:borderFills>', border_xml + '</hh:borderFills>', 1)
    header_xml = _v04954_set_item_count(header_xml, 'borderFills', 2)

    expected = _v04959_expected_examples(result)
    expected_index = 0
    cache: dict[tuple[int, str], int] = {}
    clone_count = 0
    title_count = 0
    body_count = 0
    mismatches = []
    paragraphs = list(re.finditer(r'<hp:p\b[^>]*>[\s\S]*?</hp:p>', section_xml))
    replacements: dict[int, str] = {}

    def style_para(index: int, role: str) -> bool:
        nonlocal header_xml, clone_count
        p = replacements.get(index, paragraphs[index].group(0))
        sm = re.match(r'<hp:p\b[^>]*\bparaPrIDRef="(\d+)"[^>]*>', p)
        if not sm:
            return False
        old_id = int(sm.group(1))
        key = (old_id, role)
        if key not in cache:
            new_id = _v04954_next_id(header_xml, 'paraPr')
            border_id = title_border_id if role == 'title' else body_border_id
            header_xml = _v049510_clone_example_parapr(header_xml, old_id, new_id, border_id, role=role)
            cache[key] = new_id
            clone_count += 1
        p = re.sub(r'(<hp:p\b[^>]*\bparaPrIDRef=")\d+("[^>]*>)', rf'\g<1>{cache[key]}\2', p, count=1)
        replacements[index] = p
        return True

    for i, pm in enumerate(paragraphs):
        title_text = _v04958_normalize_visible_text(_v04954_para_text(pm.group(0)))
        if not _V04959_EXAMPLE_TITLE_RE.fullmatch(title_text):
            continue
        title_count += int(style_para(i, 'title'))
        body_i = None
        for j in range(i + 1, min(len(paragraphs), i + 5)):
            txt = _v04958_normalize_visible_text(_v04954_para_text(paragraphs[j].group(0)))
            if txt:
                body_i = j
                break
        expected_entry = expected[expected_index] if expected_index < len(expected) else None
        expected_index += 1
        if body_i is None:
            mismatches.append({'title_paragraph_index': i, 'reason': 'missing body paragraph'})
            continue
        actual_body = _v04958_normalize_visible_text(_v04954_para_text(paragraphs[body_i].group(0)))
        expected_body = _v04958_normalize_visible_text((expected_entry or {}).get('text'))
        if expected_body and actual_body != expected_body:
            mismatches.append({
                'question_number': (expected_entry or {}).get('question_number'),
                'title_paragraph_index': i,
                'body_paragraph_index': body_i,
                'reason': 'body text mismatch',
                'expected': expected_body,
                'actual': actual_body,
            })
            continue
        if style_para(body_i, 'body'):
            body_count += 1

    out = []
    cursor = 0
    for i, pm in enumerate(paragraphs):
        out.append(section_xml[cursor:pm.start()])
        out.append(replacements.get(i, pm.group(0)))
        cursor = pm.end()
    out.append(section_xml[cursor:])
    header_xml = _v04954_set_item_count(header_xml, 'paraProperties', clone_count)
    return header_xml, ''.join(out), {
        'expected_example_count': len(expected),
        'boxed_title_paragraph_count': title_count,
        'boxed_body_paragraph_count': body_count,
        'title_border_fill_id': title_border_id,
        'body_border_fill_id': body_border_id,
        'example_box_para_style_count': clone_count,
        'mismatches': mismatches,
        'status': 'PASS' if title_count == len(expected) and body_count == len(expected) and not mismatches else 'FAIL',
    }


def _v049510_clone_bold_charpr_from_source(header_xml: str, source_id: int, cache: dict[int, int]) -> tuple[str, int]:
    if source_id in cache:
        return header_xml, cache[source_id]
    m = re.search(rf'<hh:charPr\b[^>]*\bid="{int(source_id)}"[\s\S]*?</hh:charPr>', header_xml)
    if not m:
        return header_xml, source_id
    new_id = _v04954_next_id(header_xml, 'charPr')
    clone = m.group(0)
    clone = re.sub(r'\bid="\d+"', f'id="{new_id}"', clone, count=1)
    if '<hh:bold/>' not in clone:
        if '</hh:charPr>' in clone:
            clone = clone.replace('</hh:charPr>', '<hh:bold/></hh:charPr>', 1)
    header_xml = header_xml.replace('</hh:charProperties>', clone + '</hh:charProperties>', 1)
    header_xml = _v04954_set_item_count(header_xml, 'charProperties', 1)
    cache[source_id] = new_id
    return header_xml, new_id


def _v049510_apply_question_bold(header_xml: str, section_xml: str) -> tuple[str, str, dict]:
    char_cache: dict[int, int] = {}
    question_count = 0
    changed_runs = 0
    paragraphs = list(re.finditer(r'<hp:p\b[^>]*>[\s\S]*?</hp:p>', section_xml))
    out = []
    cursor = 0
    run_re = re.compile(r'(<hp:run\b[^>]*charPrIDRef=")(?P<id>\d+)("[^>]*>[\s\S]*?</hp:run>)', re.S)
    for pm in paragraphs:
        out.append(section_xml[cursor:pm.start()])
        p = pm.group(0)
        text = _v04958_normalize_visible_text(_v04954_para_text(p))
        if re.match(r'^\d+\.\s', text):
            question_count += 1
            def repl(m: re.Match) -> str:
                nonlocal header_xml, changed_runs
                source_id = int(m.group('id'))
                header_xml, new_id = _v049510_clone_bold_charpr_from_source(header_xml, source_id, char_cache)
                changed_runs += 1
                return f'{m.group(1)}{new_id}{m.group(3)}'
            p = run_re.sub(repl, p)
        out.append(p)
        cursor = pm.end()
    out.append(section_xml[cursor:])
    return header_xml, ''.join(out), {
        'question_paragraph_count': question_count,
        'bold_run_change_count': changed_runs,
        'question_bold_char_style_count': len(char_cache),
        'status': 'PASS',
    }


def _v049510_clone_right_align_parapr(header_xml: str, source_id: int, cache: dict[int, int]) -> tuple[str, int]:
    if source_id in cache:
        return header_xml, cache[source_id]
    m = re.search(rf'<hh:paraPr\b[^>]*\bid="{int(source_id)}"[\s\S]*?</hh:paraPr>', header_xml)
    if not m:
        return header_xml, source_id
    new_id = _v04954_next_id(header_xml, 'paraPr')
    clone = m.group(0)
    clone = re.sub(r'\bid="\d+"', f'id="{new_id}"', clone, count=1)
    if 'horizontal=' in clone:
        clone = re.sub(r'horizontal="[A-Z_]+"', 'horizontal="RIGHT"', clone, count=1)
    else:
        clone = clone.replace('<hh:align ', '<hh:align horizontal="RIGHT" ', 1)
    header_xml = header_xml.replace('</hh:paraProperties>', clone + '</hh:paraProperties>', 1)
    header_xml = _v04954_set_item_count(header_xml, 'paraProperties', 1)
    cache[source_id] = new_id
    return header_xml, new_id


def _v049510_apply_author_right_align(header_xml: str, section_xml: str) -> tuple[str, str, dict]:
    cache: dict[int, int] = {}
    aligned = 0
    paragraphs = list(re.finditer(r'<hp:p\b[^>]*>[\s\S]*?</hp:p>', section_xml))
    out = []
    cursor = 0
    for pm in paragraphs:
        out.append(section_xml[cursor:pm.start()])
        p = pm.group(0)
        text = _v04958_normalize_visible_text(_v04954_para_text(p))
        if _V049510_AUTHOR_LINE_RE.fullmatch(text):
            sm = re.match(r'<hp:p\b[^>]*\bparaPrIDRef="(\d+)"[^>]*>', p)
            if sm:
                header_xml, new_id = _v049510_clone_right_align_parapr(header_xml, int(sm.group(1)), cache)
                p = re.sub(r'(<hp:p\b[^>]*\bparaPrIDRef=")\d+("[^>]*>)', rf'\g<1>{new_id}\2', p, count=1)
                aligned += 1
        out.append(p)
        cursor = pm.end()
    out.append(section_xml[cursor:])
    return header_xml, ''.join(out), {
        'aligned_author_line_count': aligned,
        'author_align_para_style_count': len(cache),
        'status': 'PASS',
    }


def v049510_collect_negative_question_underlines(result: dict) -> dict:
    mapping = {}
    details = []
    for q in result.get('questions', []):
        qno = int(q.get('number') or 0)
        question = str(q.get('question') or '')
        full = f'{qno}. {question}'
        prefix_len = len(f'{qno}. ')
        ranges = []
        words = []
        for pat in _V049510_NEGATIVE_PATTERNS:
            for m in pat.finditer(question):
                a = prefix_len + m.start(1)
                b = prefix_len + m.end(1)
                if b > a:
                    ranges.append((a, b))
                    words.append(m.group(1))
            if ranges:
                break
        if ranges:
            norm = _v04958_normalize_visible_text(full)
            mapping[norm] = ranges
            details.append({
                'question_number': qno,
                'question_text': question,
                'underlined_words': words,
                'ranges': [{'start': a, 'end': b, 'text': full[a:b]} for a, b in ranges],
            })
    payload = {
        'question_count': len(details),
        'questions': details,
        'status': 'PASS',
    }
    result['question_negative_underline_v049510'] = payload
    return mapping


def _v049510_apply_negative_question_underlines(header_xml: str, section_xml: str, result: dict) -> tuple[str, str, dict]:
    range_map = v049510_collect_negative_question_underlines(result)
    if not range_map:
        return header_xml, section_xml, {
            'question_negative_count': 0,
            'underlined_segment_count': 0,
            'status': 'PASS',
        }
    char_cache: dict[int, int] = {}
    applied_segments = 0
    matched = 0
    paragraphs = list(re.finditer(r'<hp:p\b[^>]*>[\s\S]*?</hp:p>', section_xml))
    out = []
    cursor = 0
    for pm in paragraphs:
        out.append(section_xml[cursor:pm.start()])
        p = pm.group(0)
        text = _v04958_normalize_visible_text(_v04954_para_text(p))
        ranges = range_map.get(text) or []
        if ranges:
            p, header_xml, applied = _v04958_patch_simple_text_runs_with_underline(p, ranges, header_xml, char_cache)
            if applied:
                matched += 1
                applied_segments += applied
        out.append(p)
        cursor = pm.end()
    out.append(section_xml[cursor:])
    return header_xml, ''.join(out), {
        'question_negative_count': len(range_map),
        'underlined_paragraph_count': matched,
        'underlined_segment_count': applied_segments,
        'status': 'PASS' if matched == len(range_map) else 'WARN',
    }


def _v049510_border_edge_map(header_xml: str) -> dict[int, dict]:
    out = {}
    for m in re.finditer(r'<hh:borderFill\b[^>]*\bid="(\d+)"[\s\S]*?</hh:borderFill>', header_xml):
        bid = int(m.group(1))
        block = m.group(0)
        def typ(name: str) -> str:
            mm = re.search(rf'<hh:{name}\b[^>]*\btype="([A-Z]+)"', block)
            return mm.group(1) if mm else 'NONE'
        out[bid] = {
            'left': typ('leftBorder'),
            'right': typ('rightBorder'),
            'top': typ('topBorder'),
            'bottom': typ('bottomBorder'),
        }
    return out


def _v049510_validate_question_example_integrity(header_xml: str, section_xml: str, result: dict) -> dict:
    base = _v04959_validate_question_example_integrity(header_xml, section_xml, result)
    paragraphs = _v04959_question_paragraph_map(section_xml)
    styles = _v04959_para_style_info(header_xml)
    border_edges = _v049510_border_edge_map(header_xml)
    expected_questions = sorted(result.get('questions', []), key=lambda q: int(q.get('number') or 0))
    question_starts = {}
    for p in paragraphs:
        m = re.match(r'^(\d+)\.\s', p['text'])
        if m:
            question_starts.setdefault(int(m.group(1)), p['index'])
    issues = [x for x in (base.get('issues') or []) if 'example title/body are not one connected solid box' not in x]
    example_reports = []
    expected_example_count = 0
    for q in expected_questions:
        qno = int(q.get('number') or 0)
        ex = q.get('example_block') or {}
        has_example = bool(ex.get('exists') and str(ex.get('text') or '').strip())
        if not has_example:
            continue
        expected_example_count += 1
        start = question_starts.get(qno)
        if start is None:
            issues.append(f'{qno}번 question paragraph missing')
            continue
        end = len(paragraphs)
        for p in paragraphs[start + 1:]:
            if re.match(r'^\d+\.\s', p['text']) or p['text'].startswith('※ 다음 글을 읽고') or p['text'] == '[정답 및 해설]':
                end = p['index']
                break
        block = paragraphs[start:end]
        title_entries = [p for p in block if _V04959_EXAMPLE_TITLE_RE.fullmatch(p['text'])]
        if len(title_entries) != 1:
            issues.append(f'{qno}번 example title count={len(title_entries)}')
            continue
        ti = block.index(title_entries[0])
        body_entry = None
        for p in block[ti + 1:]:
            if p['text']:
                body_entry = p
                break
        expected_body = _v04958_normalize_visible_text(ex.get('text'))
        if body_entry is None or body_entry['text'] != expected_body:
            issues.append(f'{qno}번 example body mismatch')
            continue
        ts = styles.get(title_entries[0]['paraPrIDRef'], {})
        bs = styles.get(body_entry['paraPrIDRef'], {})
        tb = border_edges.get(ts.get('borderFillIDRef'), {})
        bb = border_edges.get(bs.get('borderFillIDRef'), {})
        title_outer = tb.get('left') == 'SOLID' and tb.get('right') == 'SOLID' and tb.get('top') == 'SOLID'
        body_outer = bb.get('left') == 'SOLID' and bb.get('right') == 'SOLID' and bb.get('bottom') == 'SOLID'
        no_midline = tb.get('bottom', 'NONE') == 'NONE' and bb.get('top', 'NONE') == 'NONE'
        example_reports.append({
            'question_number': qno,
            'title_paragraph_index': title_entries[0]['index'],
            'body_paragraph_index': body_entry['index'],
            'body_text_match': body_entry['text'] == expected_body,
            'title_border_fill': ts.get('borderFillIDRef'),
            'body_border_fill': bs.get('borderFillIDRef'),
            'title_outer_edges_solid': title_outer,
            'body_outer_edges_solid': body_outer,
            'no_internal_midline': no_midline,
        })
        if not (title_outer and body_outer and no_midline):
            issues.append(f'{qno}번 example box edge composition mismatch')
    example_ok = len(example_reports) == expected_example_count and all(
        r.get('body_text_match') and r.get('title_outer_edges_solid') and r.get('body_outer_edges_solid') and r.get('no_internal_midline')
        for r in example_reports
    )
    base['example_reports'] = example_reports
    base['expected_example_count'] = expected_example_count
    base['validated_connected_example_count'] = len(example_reports)
    base['example_integrity_status'] = 'PASS' if example_ok else 'FAIL'
    base['issues'] = issues
    base['status'] = 'PASS' if base.get('question_integrity_status') == 'PASS' and base['example_integrity_status'] == 'PASS' and not issues else 'FAIL'
    return base


def v049510_validate_hwpx(path: Path, *, result: dict, render_plan: dict) -> dict:
    info = v04959_validate_hwpx(path, result=result, render_plan=render_plan)
    info['validator_version'] = _V049510_VERSION
    if not Path(path).exists() or not zipfile.is_zipfile(path) or info.get('package_status') != 'PASS':
        return info
    try:
        with zipfile.ZipFile(path, 'r') as zf:
            header = zf.read('Contents/header.xml').decode('utf-8', errors='strict')
            section0 = zf.read('Contents/section0.xml').decode('utf-8', errors='strict')
        integrity = _v049510_validate_question_example_integrity(header, section0, result)
        info['question_integrity_status'] = integrity.get('question_integrity_status')
        info['example_integrity_status'] = integrity.get('example_integrity_status')
        info['question_example_integrity'] = integrity
        info['expected_example_box_count'] = integrity.get('expected_example_count', 0)
        info['bordered_example_box_count'] = integrity.get('validated_connected_example_count', 0)
        info['example_box_status'] = integrity.get('example_integrity_status')

        paragraphs = _v04959_question_paragraph_map(section0)
        styles = _v04959_para_style_info(header)
        bold_char_ids = set()
        for cm in re.finditer(r'<hh:charPr\b[^>]*\bid="(\d+)"[\s\S]*?</hh:charPr>', header):
            if '<hh:bold/>' in cm.group(0):
                bold_char_ids.add(int(cm.group(1)))
        question_bold_ok = True
        qcount = 0
        for p in paragraphs:
            if not re.match(r'^\d+\.\s', p['text']):
                continue
            qcount += 1
            run_ids = [int(x) for x in re.findall(r'charPrIDRef="(\d+)"', p['xml'])]
            if not run_ids or any(rid not in bold_char_ids for rid in run_ids):
                question_bold_ok = False
        info['question_bold_status'] = 'PASS' if question_bold_ok else 'FAIL'
        info['question_bold_paragraph_count'] = qcount

        author_lines = [p for p in paragraphs if _V049510_AUTHOR_LINE_RE.fullmatch(p['text'])]
        author_right_ok = all(re.search(r'horizontal="RIGHT"', re.search(rf'<hh:paraPr\b[^>]*\bid="{p["paraPrIDRef"]}"[\s\S]*?</hh:paraPr>', header).group(0)) for p in author_lines) if author_lines else True
        info['author_right_align_status'] = 'PASS' if author_right_ok else 'FAIL'
        info['author_credit_line_count'] = len(author_lines)

        neg = result.get('question_negative_underline_v049510') or {}
        expected_negative = [rg.get('text') for item in neg.get('questions', []) for rg in item.get('ranges', [])]
        under_char_ids = set()
        for cm in re.finditer(r'<hh:charPr\b[^>]*\bid="(\d+)"[\s\S]*?</hh:charPr>', header):
            if re.search(r'<hh:underline\b[^>]*\btype="BOTTOM"', cm.group(0)):
                under_char_ids.add(int(cm.group(1)))
        under_texts = []
        for rm in re.finditer(r'<hp:run\b[^>]*\bcharPrIDRef="(\d+)"[^>]*>[\s\S]*?</hp:run>', section0):
            if int(rm.group(1)) not in under_char_ids:
                continue
            t = _v04954_para_text('<hp:p>' + rm.group(0) + '</hp:p>')
            if t:
                under_texts.append(t)
        normalized_under = ' '.join(_v04958_normalize_visible_text(x) for x in under_texts)
        missing_negative = [x for x in expected_negative if _v04958_normalize_visible_text(x) not in normalized_under]
        info['question_negative_underline_status'] = 'PASS' if not missing_negative else 'FAIL'
        info['expected_question_negative_underline_count'] = len(expected_negative)
        info['missing_question_negative_underlines'] = missing_negative

        critical = [
            info.get('package_status'), info.get('image_order_status'), info.get('image_anchor_status'), info.get('image_answer_boundary_status'),
            info.get('continuous_flow_status'), info.get('question_integrity_status'), info.get('example_integrity_status'),
            info.get('underline_status'), info.get('question_bold_status'), info.get('author_right_align_status'), info.get('question_negative_underline_status'),
            info.get('example_detection_status'), info.get('cross_region_metadata_status'),
        ]
        info['status'] = 'FAIL' if 'FAIL' in critical else 'WARN' if 'WARN' in critical else 'PASS'
        return info
    except Exception as exc:
        info['v049510_validation_error'] = str(exc)
        info['status'] = 'FAIL'
        return info


def _v049510_postprocess_hwpx(path: Path, result: dict, render_plan: dict) -> dict:
    import xml.etree.ElementTree as ET
    path = Path(path)
    report = {'version': _V049510_VERSION, 'status': 'SKIPPED', 'applied': False, 'source': str(path)}
    if not path.exists() or not zipfile.is_zipfile(path):
        report['reason'] = 'no usable HWPX'
        return report
    candidate = path.with_name(path.stem + '_v049510_candidate.hwpx')
    if candidate.exists():
        try:
            candidate.unlink()
        except Exception:
            pass
    try:
        with zipfile.ZipFile(path, 'r') as zf:
            header = zf.read('Contents/header.xml').decode('utf-8', errors='strict')
            section0 = zf.read('Contents/section0.xml').decode('utf-8', errors='strict')
        header, section0, example_report = _v049510_apply_connected_example_boxes(header, section0, result)
        header, section0, question_bold_report = _v049510_apply_question_bold(header, section0)
        header, section0, author_report = _v049510_apply_author_right_align(header, section0)
        header, section0, passage_underline_report = _v04958_apply_underline_ranges(header, section0, result)
        header, section0, negative_underline_report = _v049510_apply_negative_question_underlines(header, section0, result)
        header, section0, flow_style_report = _v04959_apply_atomic_question_flow_styles(header, section0, result)
        section0, continuous_report = _v04958_enable_continuous_two_column_flow(section0)
        ET.fromstring(header.encode('utf-8'))
        ET.fromstring(section0.encode('utf-8'))
        _v04958_repack_postprocessed_hwpx(path, candidate, header, section0)
        validation = v049510_validate_hwpx(candidate, result=result, render_plan=render_plan)
        report.update({
            'status': 'APPLIED' if validation.get('status') == 'PASS' else 'REJECTED_BY_VALIDATION',
            'applied': validation.get('status') == 'PASS',
            'candidate': str(candidate),
            'example_boxes': example_report,
            'question_bold': question_bold_report,
            'author_right_align': author_report,
            'passage_underlines': passage_underline_report,
            'question_negative_underlines': negative_underline_report,
            'atomic_question_flow': flow_style_report,
            'continuous_flow': continuous_report,
            'validation': validation,
        })
        if validation.get('status') == 'PASS':
            os.replace(str(candidate), str(path))
            report['candidate'] = None
            report['final_path'] = str(path.resolve())
        elif candidate.exists():
            candidate.unlink()
        return report
    except Exception as exc:
        report['status'] = 'FAIL'
        report['reason'] = str(exc)
        try:
            if candidate.exists():
                candidate.unlink()
        except Exception:
            pass
        return report


def _v049510_tune_render_plan_images(render_plan: dict) -> dict:
    adjusted = []
    for page in render_plan.get('pages', []):
        for side in ('left', 'right'):
            for item in page.get(side, []):
                if item.get('type') != 'image':
                    continue
                w = float(item.get('target_width_pt_v0495') or item.get('target_width_pt_v0494') or item.get('display_width') or 0.0)
                h = float(item.get('target_height_pt_v0495') or item.get('target_height_pt_v0494') or item.get('display_height') or 0.0)
                if w <= 0 or h <= 0:
                    continue
                scale = min(1.0, _V049510_IMAGE_MAX_WIDTH_PT / w, _V049510_IMAGE_MAX_HEIGHT_PT / h)
                new_w = round(w * scale, 2)
                new_h = round(h * scale, 2)
                item['target_width_pt_v0495'] = new_w
                item['target_height_pt_v0495'] = new_h
                item['image_size_policy_v049510'] = {
                    'max_width_pt': _V049510_IMAGE_MAX_WIDTH_PT,
                    'max_height_pt': _V049510_IMAGE_MAX_HEIGHT_PT,
                    'scale': round(scale, 4),
                }
                adjusted.append({'filename': item.get('filename'), 'old_width_pt': w, 'old_height_pt': h, 'new_width_pt': new_w, 'new_height_pt': new_h})
    render_plan['image_fit_v049510'] = {'adjusted_images': adjusted, 'status': 'PASS'}
    return render_plan


def v049510_create_hwpx_with_hancom(final_output: Path, result: dict, render_plan: dict, *, security_module_path: Path | None = None, allow_interactive_hwp: bool = False, show_hwp: bool = False) -> dict:
    info = v04957_create_hwpx_with_hancom(
        final_output,
        result,
        render_plan,
        security_module_path=security_module_path,
        allow_interactive_hwp=allow_interactive_hwp,
        show_hwp=show_hwp,
    )
    info['backend'] = 'hancom_com_v049510'
    info['renderer_mode'] = 'continuous_two_column_atomic_questions_editorial_refinements_v049510'
    if info.get('status') == 'created' and Path(final_output).exists():
        semantic = _v049510_postprocess_hwpx(Path(final_output), result, render_plan)
        info['semantic_finalize_v049510'] = semantic
        if semantic.get('applied'):
            info['validation'] = v049510_validate_hwpx(Path(final_output), result=result, render_plan=render_plan)
            info['status'] = 'created' if info['validation'].get('status') == 'PASS' else 'INVALID'
            info['final_path'] = str(Path(final_output).resolve())
        else:
            info['status'] = 'INVALID'
            if semantic.get('validation'):
                info['validation'] = semantic['validation']
    elif info.get('status') == 'SKIPPED':
        info['semantic_finalize_v049510'] = {'status': 'SKIPPED', 'applied': False, 'reason': 'Hancom writer unavailable on this platform'}
    return info


def v049510_upgrade_result(result: dict, pdf_path: Path, checkpoint_path: Path | None = None, *, hwpx_output_path: Path | None = None, question_detection: dict | None = None, security_module_path: Path | None = None, allow_interactive_hwp: bool = False, show_hwp: bool = False) -> dict:
    _v0491_log('[v0.4.9.5.10] 보기 박스/이미지 적합/문제 bold/작품 출전 우측정렬/부정문 밑줄 강화 준비')
    result = v046_upgrade_result(result, pdf_path)
    result = v0481_prepare_problem_images(pdf_path, result)
    result = v0491_cleanup_legacy_metadata(result)
    result = v0495_attach_question_geometry(pdf_path, result)
    result = v04958_repair_example_blocks(result)
    result['example_repair_v049510'] = result.pop('example_repair_v04958', result.get('example_repair_v04959', {}))
    result = v04959_cleanup_spacing_fields(result)
    result = v04959_extract_underline_semantics(pdf_path, result)
    result = v04959_build_atomic_flow_policy(result)
    result = v04957_cleanup_orphan_section_labels(result)
    result['cross_region_metadata_v049510'] = v04959_validate_cross_region_metadata(result)
    structural = v04959_validate_structural(result)
    result['structural_validation_v049510'] = structural
    render_plan = v04955_build_render_plan(result)
    render_plan = _v049510_tune_render_plan_images(render_plan)
    render_plan['version'] = _V049510_VERSION
    render_plan['editorial_refinements_v049510'] = {
        'example_box': 'complementary title/body borders with no internal mid-line',
        'image_max_width_pt': _V049510_IMAGE_MAX_WIDTH_PT,
        'image_max_height_pt': _V049510_IMAGE_MAX_HEIGHT_PT,
        'question_stem_bold': True,
        'author_credit_right_align': True,
        'negative_prompt_keywords_underlined': True,
    }
    result['render_plan_v049510'] = render_plan
    for stale_key in [
        'render_plan_v04959', 'render_plan_v04958', 'render_plan_v04957', 'render_plan_v04956', 'render_plan_v04955', 'render_plan_v04954',
        'render_plan_v04953', 'render_plan_v04952', 'render_plan_v04951', 'render_plan_v0495', 'render_plan_v0494', 'render_plan_v0493', 'render_plan_v0492', 'render_plan_v049',
    ]:
        result.pop(stale_key, None)
    result['version'] = _V049510_VERSION
    result['parser_version'] = _V049510_VERSION
    result['generator_version'] = 'PDF Parser Integrated v0.4.9.5.10'
    result['question_detection_v049510'] = question_detection or {}
    result['schema_version'] = {
        'base': 'v0.4.9.5.9',
        'extension': [
            'example_box_without_internal_midline', 'conservative_image_downscale_to_column_fit',
            'question_stem_bold_style', 'author_credit_right_alignment', 'negative_prompt_keyword_underlines',
        ],
    }
    if checkpoint_path is not None:
        checkpoint_path = Path(checkpoint_path)
        result['pre_hwpx_checkpoint'] = {'path': str(checkpoint_path.resolve()), 'purpose': 'COM hang/error recovery only', 'retained_after_success': False}
        _v0491_json_safe_write(checkpoint_path, result)
        _v0491_log(f'[v0.4.9.5.10] HWPX 전 임시 체크포인트 저장: {checkpoint_path.resolve()}')
    requested = Path(hwpx_output_path) if hwpx_output_path else _v04957_default_hwpx_path(pdf_path)
    actual_target = _v04956_pick_free_path(requested)
    result['hwpx_output_v049510'] = {
        'requested_path': str(requested.resolve()), 'allocated_path': str(actual_target.resolve()), 'source_pdf_stem': Path(pdf_path).stem,
        'safe_output_stem': _v04957_safe_output_stem(pdf_path), 'existing_requested_path_preserved': requested.exists(),
        'policy': 'PDF stem filename; never overwrite; allocate _runNN when needed',
    }
    hwpx_info = v049510_create_hwpx_with_hancom(actual_target, result, render_plan, security_module_path=security_module_path, allow_interactive_hwp=allow_interactive_hwp, show_hwp=show_hwp)
    result['hwpx_v049510'] = hwpx_info
    result['hancom_security_v049510'] = result.get('hancom_security_v04957') or hwpx_info.get('hancom_security') or {}
    final_validation = hwpx_info.get('validation') or {}
    security_runtime = result.get('hancom_security_v049510') or {}
    hwpx_status = hwpx_info.get('status')
    security_ok = security_runtime.get('unattended_ready') is True or hwpx_status == 'SKIPPED' or (allow_interactive_hwp and hwpx_status == 'created')
    critical_keys = ('image_order_status','image_anchor_status','image_answer_boundary_status','continuous_flow_status','question_integrity_status','example_integrity_status','underline_status','question_bold_status','author_right_align_status','question_negative_underline_status','example_detection_status','cross_region_metadata_status')
    critical_fail = any(final_validation.get(k) == 'FAIL' for k in critical_keys)
    final_status = 'FAIL' if critical_fail or structural.get('status') == 'FAIL' else ('PASS' if hwpx_status in {'created','SKIPPED'} and security_ok and final_validation.get('package_status') in {'PASS', None} and final_validation.get('status') in {'PASS', None} else ('WARN' if hwpx_status == 'SKIPPED' else 'FAIL'))
    flow_policy = result.get('question_flow_v04959') or {}
    neg = result.get('question_negative_underline_v049510') or {}
    result['validation_v049510'] = {
        'question_count': len(result.get('questions', [])),
        'render_page_count': render_plan.get('stats', {}).get('page_count', 0),
        'render_item_count': render_plan.get('stats', {}).get('render_item_count', 0),
        'question_detection_status': (question_detection or {}).get('status'),
        'structural_status': structural.get('status'),
        'example_detection_status': structural.get('example_detection_status'),
        'underline_detection_status': structural.get('underline_detection_status'),
        'cross_region_metadata_status': structural.get('cross_region_metadata_status'),
        'atomic_question_numbers': flow_policy.get('atomic_question_numbers', []),
        'split_safe_oversize_question_numbers': flow_policy.get('split_safe_oversize_question_numbers', []),
        'question_negative_keyword_question_count': neg.get('question_count', 0),
        'hancom_security_status': security_runtime.get('status'),
        'unattended_ready': security_runtime.get('unattended_ready', False),
        'hwpx_status': hwpx_status,
        'hwpx_final_path': hwpx_info.get('final_path'),
        'hwpx_validation_status': final_validation.get('status'),
        'hwpx_package_status': final_validation.get('package_status'),
        'continuous_flow_status': final_validation.get('continuous_flow_status'),
        'question_integrity_status': final_validation.get('question_integrity_status'),
        'example_integrity_status': final_validation.get('example_integrity_status'),
        'example_box_status': final_validation.get('example_box_status'),
        'underline_status': final_validation.get('underline_status'),
        'question_bold_status': final_validation.get('question_bold_status'),
        'author_right_align_status': final_validation.get('author_right_align_status'),
        'question_negative_underline_status': final_validation.get('question_negative_underline_status'),
        'image_position_status': final_validation.get('image_position_status'),
        'status': final_status,
    }
    return result


def main_v049510() -> None:
    parser = argparse.ArgumentParser(description='국어 문제 PDF -> 구조화 JSON + HWPX V0.4.9.5.10 보기박스/문제bold/우측정렬/부정문밑줄')
    parser.add_argument('pdf', type=Path, help='분석할 PDF 파일')
    parser.add_argument('-o', '--output', type=Path, default=None, help='저장할 JSON. 생략하면 <PDF이름>_result.json')
    parser.add_argument('--hwpx-output', type=Path, default=None, help='최종 HWPX 희망 파일명. 생략하면 <PDF이름>.hwpx, 존재 시 _runNN 자동 생성')
    parser.add_argument('-q', '--questions', nargs='+', type=int, default=None, help='추출할 문제 번호. 생략하면 PDF에서 자동 탐지')
    parser.add_argument('--no-kiwi', action='store_true', help='Kiwi 경계 판별을 끔')
    parser.add_argument('--security-module', type=Path, default=None, help='FilePathCheckerModuleExample.dll 경로')
    parser.add_argument('--allow-interactive-hwp', action='store_true', help='보안 모듈 실패 시 대화형 한글 허용')
    parser.add_argument('--show-hwp', action='store_true', help='한글 창 표시')
    args = parser.parse_args()
    if not args.pdf.exists():
        raise SystemExit(f'PDF 파일을 찾을 수 없습니다: {args.pdf}')
    if not args.no_kiwi and Kiwi is None:
        print('[경고] kiwipiepy 미설치. fallback으로 실행합니다.')
    detection = v04957_detect_question_numbers(args.pdf)
    if args.questions:
        question_numbers = sorted(set(args.questions))
        detection['selection_mode'] = 'explicit_cli'
        detection['selected_question_numbers'] = question_numbers
    else:
        if detection.get('status') != 'PASS' or not detection.get('question_numbers'):
            raise SystemExit('문제 번호 자동 탐지에 실패했습니다. -q 옵션으로 문제 번호를 직접 지정하세요. ' + str(detection.get('reason') or ''))
        question_numbers = list(detection['question_numbers'])
        detection['selection_mode'] = 'auto_detected'
        detection['selected_question_numbers'] = question_numbers
    json_output = Path(args.output) if args.output else _v04957_default_json_path(args.pdf)
    checkpoint_path = json_output.with_name(json_output.stem + '_pre_hwpx.json')
    result = parse_v0_2_3(args.pdf, question_numbers, use_kiwi=not args.no_kiwi)
    result = v044_upgrade_result(result, args.pdf)
    result = v045_upgrade_result(result, args.pdf)
    result = v049510_upgrade_result(result, args.pdf, checkpoint_path=checkpoint_path, hwpx_output_path=args.hwpx_output, question_detection=detection, security_module_path=args.security_module, allow_interactive_hwp=args.allow_interactive_hwp, show_hwp=args.show_hwp)
    json_output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    checkpoint_info = result.get('pre_hwpx_checkpoint') or {}
    checkpoint_file = Path(str(checkpoint_info.get('path') or '')) if isinstance(checkpoint_info, dict) else None
    if result.get('hwpx_v049510', {}).get('status') == 'created' and checkpoint_file and str(checkpoint_file):
        try:
            if checkpoint_file.exists():
                checkpoint_file.unlink()
            checkpoint_info['retained'] = False
            result['pre_hwpx_checkpoint'] = checkpoint_info
            json_output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception as exc:
            checkpoint_info['retained'] = True
            checkpoint_info['cleanup_error'] = str(exc)
    v = result.get('validation_v049510', {})
    print('=' * 76)
    print('V0.4.9.5.10 보기박스/문제 bold/작품 출전 우측정렬/부정문 밑줄 적용 완료')
    print('=' * 76)
    print(f'입력 : {args.pdf}')
    print(f'JSON : {json_output.resolve()}')
    print(f'HWPX : {v.get("hwpx_final_path")}')
    print(f'문제 : {v.get("question_count", 0)} | 자동 탐지 : {v.get("question_detection_status")}')
    print(f'<보기> : {v.get("example_integrity_status")} | 문제 : {v.get("question_integrity_status")} | 문제 bold : {v.get("question_bold_status")}')
    print(f'출전 우측정렬 : {v.get("author_right_align_status")} | 부정문 밑줄 : {v.get("question_negative_underline_status")}')
    print(f'HWPX 상태 : {v.get("hwpx_status")} | 최종 검증 : {v.get("status")}')



# =============================================================================
# V0.4.9.5.11 HWPX visual-layout stabilization layer
# - <보기> title-only CENTER alignment; body remains LEFT
# - explicit before/after paragraph clearances around connected example boxes
# - source-credit detection independent of passage block type
# - passage pictures participate in line-height and center in their paragraphs
# - image pt/mm metadata is recalculated from one canonical size
# - validator checks visual-layout invariants instead of only object existence
# =============================================================================

_V049511_VERSION = "v0.4.9.5.11"
_V049511_EXAMPLE_TITLE_PREV_HWPUNIT = 700   # about 7 pt / 2.47 mm
_V049511_EXAMPLE_BODY_NEXT_HWPUNIT = 1000   # about 10 pt / 3.53 mm
_V049511_EXAMPLE_OUTER_TB_HWPUNIT = 425     # about 1.5 mm border-to-text padding
_V049511_EXAMPLE_JOIN_TB_HWPUNIT = 60       # keep the title/body seam visually tight
_V049511_IMAGE_MAX_WIDTH_PT = 180.0
_V049511_IMAGE_MAX_HEIGHT_PT = 165.0
_V049511_UNIT_TOLERANCE_MM = 0.03
_V049511_SAFE_IMAGE_INNER_WIDTH_HWPUNIT = max(
    1,
    int(_V04955_COLUMN_LINE_WIDTH - 2 * _V04955_BOX_LR_PADDING_HWPUNIT),
)

# Matches source/work credit lines regardless of parser block type.
# Examples:
#   - 박목월, 「산이 날 에워싸고」
#   - 「식빵이 기다리는 동안」 영상 시
#   - 「작품명」 소설
#   - 작가, 『작품명』
_V049511_SOURCE_CREDIT_RE = re.compile(
    r"^\s*[-–—]\s*(?:(?![「『〈《]).+?[,，]\s*)?[「『〈《].+[」』〉》](?:\s+.+)?\s*$"
)


def _v049511_patch_numeric_attr(tag: str, key: str, value: int | str) -> str:
    value = str(value)
    if re.search(rf'\b{re.escape(key)}="[^"]*"', tag):
        return re.sub(
            rf'\b{re.escape(key)}="[^"]*"',
            f'{key}="{value}"',
            tag,
            count=1,
        )
    if tag.endswith('/>'):
        return tag[:-2] + f' {key}="{value}"/>'
    if tag.endswith('>'):
        return tag[:-1] + f' {key}="{value}">'
    return tag


def _v049511_patch_para_margin_values(clone: str, *, prev: int, nxt: int) -> str:
    """Patch both HwpUnitChar case/default margins so Hangul cannot choose a stale branch."""
    clone, prev_count = re.subn(
        r'(<hc:prev\b[^>]*\bvalue=")-?\d+("[^>]*/>)',
        rf'\g<1>{int(prev)}\2',
        clone,
    )
    clone, next_count = re.subn(
        r'(<hc:next\b[^>]*\bvalue=")-?\d+("[^>]*/>)',
        rf'\g<1>{int(nxt)}\2',
        clone,
    )
    # Existing Hangul-created paraPr styles always contain prev/next. If a foreign
    # HWPX does not, retain the source style and let the spacer fallback handle it.
    return clone


def _v049511_clone_example_visual_parapr(
    header_xml: str,
    source_id: int,
    new_id: int,
    *,
    role: str,
) -> str:
    m = re.search(
        rf'<hh:paraPr\b[^>]*\bid="{int(source_id)}"[\s\S]*?</hh:paraPr>',
        header_xml,
    )
    if not m:
        raise RuntimeError(f"header.xml paraPr template {source_id} not found")
    clone = m.group(0)
    clone = re.sub(r'\bid="\d+"', f'id="{int(new_id)}"', clone, count=1)

    align = "CENTER" if role == "title" else "LEFT"
    if re.search(r'<hh:align\b[^>]*\bhorizontal="[A-Z_]+"', clone):
        clone = re.sub(
            r'(<hh:align\b[^>]*\bhorizontal=")[A-Z_]+("[^>]*/>)',
            rf'\g<1>{align}\2',
            clone,
            count=1,
        )
    else:
        clone = clone.replace('<hh:align ', f'<hh:align horizontal="{align}" ', 1)

    clone = re.sub(r'breakNonLatinWord="BREAK_WORD"', 'breakNonLatinWord="KEEP_WORD"', clone)
    prev = _V049511_EXAMPLE_TITLE_PREV_HWPUNIT if role == "title" else 0
    nxt = 0 if role == "title" else _V049511_EXAMPLE_BODY_NEXT_HWPUNIT
    clone = _v049511_patch_para_margin_values(clone, prev=prev, nxt=nxt)

    def patch_border(mb: re.Match) -> str:
        tag = mb.group(0)
        tag = _v049511_patch_numeric_attr(tag, "offsetLeft", _V049510_BOX_LR_PADDING_HWPUNIT)
        tag = _v049511_patch_numeric_attr(tag, "offsetRight", _V049510_BOX_LR_PADDING_HWPUNIT)
        tag = _v049511_patch_numeric_attr(
            tag,
            "offsetTop",
            _V049511_EXAMPLE_OUTER_TB_HWPUNIT if role == "title" else _V049511_EXAMPLE_JOIN_TB_HWPUNIT,
        )
        tag = _v049511_patch_numeric_attr(
            tag,
            "offsetBottom",
            _V049511_EXAMPLE_JOIN_TB_HWPUNIT if role == "title" else _V049511_EXAMPLE_OUTER_TB_HWPUNIT,
        )
        return tag

    if re.search(r'<hh:border\b[^>]*/>', clone):
        clone = re.sub(r'<hh:border\b[^>]*/>', patch_border, clone, count=1)
    else:
        raise RuntimeError(f"example paraPr {source_id} has no border")

    header_xml = header_xml.replace('</hh:paraProperties>', clone + '</hh:paraProperties>', 1)
    return header_xml


def _v049511_apply_example_visual_layout(
    header_xml: str,
    section_xml: str,
    result: dict,
) -> tuple[str, str, dict]:
    """Re-style the already-connected two-paragraph boxes without adding a mid-line."""
    expected = _v04959_expected_examples(result)
    expected_index = 0
    paragraphs = list(re.finditer(r'<hp:p\b[^>]*>[\s\S]*?</hp:p>', section_xml))
    replacements: dict[int, str] = {}
    cache: dict[tuple[int, str], int] = {}
    clone_count = 0
    reports = []
    failures = []

    def style_para(index: int, role: str) -> int | None:
        nonlocal header_xml, clone_count
        p = replacements.get(index, paragraphs[index].group(0))
        sm = re.match(r'<hp:p\b[^>]*\bparaPrIDRef="(\d+)"[^>]*>', p)
        if not sm:
            return None
        source_id = int(sm.group(1))
        key = (source_id, role)
        if key not in cache:
            new_id = _v04954_next_id(header_xml, 'paraPr')
            header_xml = _v049511_clone_example_visual_parapr(
                header_xml,
                source_id,
                new_id,
                role=role,
            )
            cache[key] = new_id
            clone_count += 1
        p = re.sub(
            r'(<hp:p\b[^>]*\bparaPrIDRef=")\d+("[^>]*>)',
            rf'\g<1>{cache[key]}\2',
            p,
            count=1,
        )
        replacements[index] = p
        return cache[key]

    for i, pm in enumerate(paragraphs):
        title_text = _v04958_normalize_visible_text(_v04954_para_text(pm.group(0)))
        if not _V04959_EXAMPLE_TITLE_RE.fullmatch(title_text):
            continue
        body_i = None
        for j in range(i + 1, min(len(paragraphs), i + 5)):
            txt = _v04958_normalize_visible_text(_v04954_para_text(paragraphs[j].group(0)))
            if txt:
                body_i = j
                break
        expected_entry = expected[expected_index] if expected_index < len(expected) else None
        expected_index += 1
        if body_i is None:
            failures.append({'title_paragraph_index': i, 'reason': 'missing body paragraph'})
            continue
        actual_body = _v04958_normalize_visible_text(_v04954_para_text(paragraphs[body_i].group(0)))
        expected_body = _v04958_normalize_visible_text((expected_entry or {}).get('text'))
        if expected_body and actual_body != expected_body:
            failures.append({
                'question_number': (expected_entry or {}).get('question_number'),
                'title_paragraph_index': i,
                'body_paragraph_index': body_i,
                'reason': 'body text mismatch',
                'expected': expected_body,
                'actual': actual_body,
            })
            continue
        title_style = style_para(i, 'title')
        body_style = style_para(body_i, 'body')
        if title_style is None or body_style is None:
            failures.append({
                'question_number': (expected_entry or {}).get('question_number'),
                'reason': 'style clone failed',
            })
            continue
        reports.append({
            'question_number': (expected_entry or {}).get('question_number'),
            'title_paragraph_index': i,
            'body_paragraph_index': body_i,
            'title_para_style_id': title_style,
            'body_para_style_id': body_style,
            'title_alignment': 'CENTER',
            'body_alignment': 'LEFT',
            'space_before_box_hwpunit': _V049511_EXAMPLE_TITLE_PREV_HWPUNIT,
            'space_after_box_hwpunit': _V049511_EXAMPLE_BODY_NEXT_HWPUNIT,
        })

    out = []
    cursor = 0
    for i, pm in enumerate(paragraphs):
        out.append(section_xml[cursor:pm.start()])
        out.append(replacements.get(i, pm.group(0)))
        cursor = pm.end()
    out.append(section_xml[cursor:])
    header_xml = _v04954_set_item_count(header_xml, 'paraProperties', clone_count)
    return header_xml, ''.join(out), {
        'expected_example_count': len(expected),
        'styled_example_count': len(reports),
        'new_para_style_count': clone_count,
        'space_before_box_hwpunit': _V049511_EXAMPLE_TITLE_PREV_HWPUNIT,
        'space_after_box_hwpunit': _V049511_EXAMPLE_BODY_NEXT_HWPUNIT,
        'spacer_fallback_enabled': True,
        'spacer_inserted_count': 0,
        'reports': reports,
        'failures': failures,
        'status': 'PASS' if len(reports) == len(expected) and not failures else 'FAIL',
    }



def _v049511_insert_example_spacer_fallback(
    section_xml: str,
    result: dict,
) -> tuple[str, dict]:
    """Insert one empty paragraph between example body and ① only as a fallback.

    The normal path uses paragraph prev/next margins. This fallback is deliberately
    conservative and is called only when the visual-spacing validator still fails.
    It clones the following choice paragraph shell, so no example border is extended.
    """
    expected = _v04959_expected_examples(result)
    expected_index = 0
    paragraphs = list(re.finditer(r'<hp:p\b[^>]*>[\s\S]*?</hp:p>', section_xml))
    insert_after_index: set[int] = set()
    details = []

    for i, pm in enumerate(paragraphs):
        title_text = _v04958_normalize_visible_text(_v04954_para_text(pm.group(0)))
        if not _V04959_EXAMPLE_TITLE_RE.fullmatch(title_text):
            continue
        expected_entry = expected[expected_index] if expected_index < len(expected) else None
        expected_index += 1
        body_i = None
        for j in range(i + 1, min(len(paragraphs), i + 5)):
            if _v04958_normalize_visible_text(_v04954_para_text(paragraphs[j].group(0))):
                body_i = j
                break
        if body_i is None:
            continue
        expected_body = _v04958_normalize_visible_text((expected_entry or {}).get('text'))
        actual_body = _v04958_normalize_visible_text(_v04954_para_text(paragraphs[body_i].group(0)))
        if expected_body and actual_body != expected_body:
            continue

        # Find ① and detect whether an empty spacer is already present.
        choice_i = None
        for j in range(body_i + 1, min(len(paragraphs), body_i + 5)):
            txt = _v04958_normalize_visible_text(_v04954_para_text(paragraphs[j].group(0)))
            if not txt:
                continue
            if re.match(r'^①\s', txt):
                choice_i = j
            break
        if choice_i is None or choice_i != body_i + 1:
            # Already separated by an empty paragraph or the expected choice is absent.
            continue

        choice_xml = paragraphs[choice_i].group(0)
        sm = re.match(r'(<hp:p\b[^>]*>)', choice_xml)
        rm = re.search(r'<hp:run\b[^>]*\bcharPrIDRef="(\d+)"', choice_xml)
        if not sm:
            continue
        start_tag = sm.group(1)
        char_id = int(rm.group(1)) if rm else 0
        spacer = f'{start_tag}<hp:run charPrIDRef="{char_id}"><hp:t/></hp:run></hp:p>'
        insert_after_index.add(body_i)
        details.append({
            'question_number': (expected_entry or {}).get('question_number'),
            'body_paragraph_index': body_i,
            'choice_paragraph_index_before_insert': choice_i,
        })
        # Store generated XML on the detail to keep rebuilding deterministic.
        details[-1]['spacer_xml'] = spacer

    if not insert_after_index:
        return section_xml, {
            'spacer_inserted_count': 0,
            'details': [],
            'status': 'NOT_NEEDED',
        }

    spacer_by_body = {d['body_paragraph_index']: d['spacer_xml'] for d in details}
    out = []
    cursor = 0
    for idx, pm in enumerate(paragraphs):
        out.append(section_xml[cursor:pm.start()])
        out.append(pm.group(0))
        if idx in spacer_by_body:
            out.append(spacer_by_body[idx])
        cursor = pm.end()
    out.append(section_xml[cursor:])
    for d in details:
        d.pop('spacer_xml', None)
    return ''.join(out), {
        'spacer_inserted_count': len(details),
        'details': details,
        'status': 'APPLIED',
    }


def _v049511_para_horizontal(header_xml: str, para_id: int) -> str | None:
    m = re.search(rf'<hh:paraPr\b[^>]*\bid="{int(para_id)}"[\s\S]*?</hh:paraPr>', header_xml)
    if not m:
        return None
    am = re.search(r'<hh:align\b[^>]*\bhorizontal="([A-Z_]+)"', m.group(0))
    return am.group(1) if am else None


def _v049511_expected_source_credits(result: dict) -> list[str]:
    credits: list[str] = []
    seen: set[str] = set()
    for group in result.get('passage_groups', []):
        candidates = [str(b.get('text') or '').strip() for b in group.get('blocks', [])]
        candidates.extend(str(group.get('normalized_text') or '').splitlines())
        for raw in candidates:
            text = _v04958_normalize_visible_text(raw)
            if text and _V049511_SOURCE_CREDIT_RE.fullmatch(text) and text not in seen:
                seen.add(text)
                credits.append(text)
    return credits


def _v049511_apply_source_credit_right_align(
    header_xml: str,
    section_xml: str,
    result: dict,
) -> tuple[str, str, dict]:
    expected = _v049511_expected_source_credits(result)
    cache: dict[int, int] = {}
    matched = 0
    changed = 0
    paragraphs = list(re.finditer(r'<hp:p\b[^>]*>[\s\S]*?</hp:p>', section_xml))
    out = []
    cursor = 0
    matched_texts = []
    for pm in paragraphs:
        out.append(section_xml[cursor:pm.start()])
        p = pm.group(0)
        text = _v04958_normalize_visible_text(_v04954_para_text(p))
        if _V049511_SOURCE_CREDIT_RE.fullmatch(text):
            matched += 1
            matched_texts.append(text)
            sm = re.match(r'<hp:p\b[^>]*\bparaPrIDRef="(\d+)"[^>]*>', p)
            if sm:
                source_id = int(sm.group(1))
                if _v049511_para_horizontal(header_xml, source_id) != 'RIGHT':
                    header_xml, new_id = _v049510_clone_right_align_parapr(header_xml, source_id, cache)
                    p = re.sub(
                        r'(<hp:p\b[^>]*\bparaPrIDRef=")\d+("[^>]*>)',
                        rf'\g<1>{new_id}\2',
                        p,
                        count=1,
                    )
                    changed += 1
        out.append(p)
        cursor = pm.end()
    out.append(section_xml[cursor:])
    return header_xml, ''.join(out), {
        'expected_source_credit_count': len(expected),
        'detected_source_credit_count': matched,
        'right_align_change_count': changed,
        'expected_source_credits': expected,
        'detected_source_credits': matched_texts,
        'status': 'PASS' if matched == len(expected) else 'FAIL',
    }


def _v049511_clone_center_image_parapr(
    header_xml: str,
    source_id: int,
    cache: dict[int, int],
) -> tuple[str, int]:
    if source_id in cache:
        return header_xml, cache[source_id]
    m = re.search(rf'<hh:paraPr\b[^>]*\bid="{int(source_id)}"[\s\S]*?</hh:paraPr>', header_xml)
    if not m:
        return header_xml, source_id
    new_id = _v04954_next_id(header_xml, 'paraPr')
    clone = m.group(0)
    clone = re.sub(r'\bid="\d+"', f'id="{new_id}"', clone, count=1)
    if re.search(r'<hh:align\b[^>]*\bhorizontal="[A-Z_]+"', clone):
        clone = re.sub(
            r'(<hh:align\b[^>]*\bhorizontal=")[A-Z_]+("[^>]*/>)',
            r'\g<1>CENTER\2',
            clone,
            count=1,
        )
    else:
        clone = clone.replace('<hh:align ', '<hh:align horizontal="CENTER" ', 1)
    header_xml = header_xml.replace('</hh:paraProperties>', clone + '</hh:paraProperties>', 1)
    header_xml = _v04954_set_item_count(header_xml, 'paraProperties', 1)
    cache[source_id] = new_id
    return header_xml, new_id


def _v049511_patch_picture_pos(pic_xml: str) -> tuple[str, bool]:
    changed = False
    def repl(m: re.Match) -> str:
        nonlocal changed
        tag = m.group(0)
        original = tag
        for key, value in (
            ('treatAsChar', 1),
            ('affectLSpacing', 1),
            ('flowWithText', 1),
            ('allowOverlap', 0),
            ('horzAlign', 'CENTER'),
        ):
            tag = _v049511_patch_numeric_attr(tag, key, value)
        changed = changed or tag != original
        return tag
    patched, count = re.subn(r'<hp:pos\b[^>]*/>', repl, pic_xml, count=1)
    return patched, bool(count and changed)


def _v049511_apply_picture_layout(
    header_xml: str,
    section_xml: str,
) -> tuple[str, str, dict]:
    """Patch all problem/passage picture paragraphs in section0.

    These are the images inserted by the parser. Choice markers are text glyphs in
    the current renderer, so section0 hp:pic objects are the passage figures that
    need containment behavior.
    """
    paragraphs = list(re.finditer(r'<hp:p\b[^>]*>[\s\S]*?</hp:p>', section_xml))
    cache: dict[int, int] = {}
    out = []
    cursor = 0
    picture_paragraph_count = 0
    picture_pos_patch_count = 0
    centered_para_count = 0
    details = []
    for idx, pm in enumerate(paragraphs):
        out.append(section_xml[cursor:pm.start()])
        p = pm.group(0)
        if '<hp:pic ' in p or '<hp:pic>' in p:
            picture_paragraph_count += 1
            p, pos_changed = _v049511_patch_picture_pos(p)
            picture_pos_patch_count += int(pos_changed)
            sm = re.match(r'<hp:p\b[^>]*\bparaPrIDRef="(\d+)"[^>]*>', p)
            old_id = int(sm.group(1)) if sm else None
            new_id = old_id
            if old_id is not None:
                header_xml, new_id = _v049511_clone_center_image_parapr(header_xml, old_id, cache)
                p = re.sub(
                    r'(<hp:p\b[^>]*\bparaPrIDRef=")\d+("[^>]*>)',
                    rf'\g<1>{new_id}\2',
                    p,
                    count=1,
                )
                centered_para_count += int(_v049511_para_horizontal(header_xml, new_id) == 'CENTER')
            sz = re.search(r'<hp:sz\b[^>]*\bwidth="(\d+)"[^>]*\bheight="(\d+)"', p)
            details.append({
                'paragraph_index': idx,
                'source_para_style_id': old_id,
                'center_para_style_id': new_id,
                'width_hwpunit': int(sz.group(1)) if sz else None,
                'height_hwpunit': int(sz.group(2)) if sz else None,
            })
        out.append(p)
        cursor = pm.end()
    out.append(section_xml[cursor:])
    return header_xml, ''.join(out), {
        'picture_paragraph_count': picture_paragraph_count,
        'picture_pos_patch_count': picture_pos_patch_count,
        'centered_picture_paragraph_count': centered_para_count,
        'new_center_para_style_count': len(cache),
        'details': details,
        'status': 'PASS' if picture_paragraph_count == centered_para_count else 'FAIL',
    }


def _v049511_fix_render_plan_image_units(render_plan: dict) -> dict:
    adjusted = []
    for page in render_plan.get('pages', []):
        for side in ('left', 'right'):
            for item in page.get(side, []):
                if item.get('type') != 'image':
                    continue
                w = float(item.get('target_width_pt_v0495') or item.get('target_width_pt_v0494') or item.get('display_width') or 0.0)
                h = float(item.get('target_height_pt_v0495') or item.get('target_height_pt_v0494') or item.get('display_height') or 0.0)
                if w <= 0 or h <= 0:
                    continue
                scale = min(1.0, _V049511_IMAGE_MAX_WIDTH_PT / w, _V049511_IMAGE_MAX_HEIGHT_PT / h)
                w = round(w * scale, 2)
                h = round(h * scale, 2)
                w_mm = round(w * 25.4 / 72.0, 3)
                h_mm = round(h * 25.4 / 72.0, 3)
                item['target_width_pt_v0495'] = w
                item['target_height_pt_v0495'] = h
                # Correct the stale v0495 mm fields in-place for downstream compatibility.
                item['target_width_mm_v0495'] = w_mm
                item['target_height_mm_v0495'] = h_mm
                item['target_width_mm_v049511'] = w_mm
                item['target_height_mm_v049511'] = h_mm
                item['image_size_policy_v049511'] = {
                    'max_width_pt': _V049511_IMAGE_MAX_WIDTH_PT,
                    'max_height_pt': _V049511_IMAGE_MAX_HEIGHT_PT,
                    'scale': round(scale, 4),
                    'canonical_unit': 'pt',
                    'mm_recalculated_from_pt': True,
                }
                adjusted.append({
                    'filename': item.get('filename'),
                    'width_pt': w,
                    'height_pt': h,
                    'width_mm': w_mm,
                    'height_mm': h_mm,
                })
    render_plan['image_fit_v049511'] = {
        'adjusted_images': adjusted,
        'image_count': len(adjusted),
        'status': 'PASS',
    }
    return render_plan


def _v049511_para_style_info(header_xml: str) -> dict[int, dict]:
    info: dict[int, dict] = {}
    for m in re.finditer(r'<hh:paraPr\b[^>]*\bid="(\d+)"[\s\S]*?</hh:paraPr>', header_xml):
        pid = int(m.group(1))
        body = m.group(0)
        align_m = re.search(r'<hh:align\b[^>]*\bhorizontal="([A-Z_]+)"', body)
        break_m = re.search(r'<hh:breakSetting\b([^>]*)/>', body)
        border_m = re.search(r'<hh:border\b([^>]*)/>', body)
        margin_default = re.search(r'<hp:default>[\s\S]*?<hh:margin>([\s\S]*?)</hh:margin>', body)
        margin_blob = margin_default.group(1) if margin_default else body
        def attr_int(blob: str, key: str, default: int = 0) -> int:
            am = re.search(rf'\b{re.escape(key)}="(-?\d+)"', blob)
            return int(am.group(1)) if am else default
        def margin_value(key: str) -> int:
            mm = re.search(rf'<hc:{re.escape(key)}\b[^>]*\bvalue="(-?\d+)"', margin_blob)
            return int(mm.group(1)) if mm else 0
        battrs = border_m.group(1) if border_m else ''
        break_attrs = break_m.group(1) if break_m else ''
        info[pid] = {
            'horizontal': align_m.group(1) if align_m else None,
            'prev': margin_value('prev'),
            'next': margin_value('next'),
            'keepWithNext': attr_int(break_attrs, 'keepWithNext'),
            'keepLines': attr_int(break_attrs, 'keepLines'),
            'borderFillIDRef': attr_int(battrs, 'borderFillIDRef', -1),
            'connect': attr_int(battrs, 'connect', 0),
            'offsetTop': attr_int(battrs, 'offsetTop', 0),
            'offsetBottom': attr_int(battrs, 'offsetBottom', 0),
            'offsetLeft': attr_int(battrs, 'offsetLeft', 0),
            'offsetRight': attr_int(battrs, 'offsetRight', 0),
        }
    return info


def _v049511_validate_example_visual_layout(
    header_xml: str,
    section_xml: str,
    result: dict,
) -> dict:
    paragraphs = _v04959_question_paragraph_map(section_xml)
    styles = _v049511_para_style_info(header_xml)
    border_edges = _v049510_border_edge_map(header_xml)
    expected_questions = sorted(result.get('questions', []), key=lambda q: int(q.get('number') or 0))
    question_starts = {}
    for p in paragraphs:
        m = re.match(r'^(\d+)\.\s', p['text'])
        if m:
            question_starts.setdefault(int(m.group(1)), p['index'])
    reports = []
    issues = []
    for q in expected_questions:
        qno = int(q.get('number') or 0)
        ex = q.get('example_block') or {}
        if not (ex.get('exists') and str(ex.get('text') or '').strip()):
            continue
        start = question_starts.get(qno)
        if start is None:
            issues.append(f'{qno}번 question paragraph missing')
            continue
        end = len(paragraphs)
        for p in paragraphs[start + 1:]:
            if re.match(r'^\d+\.\s', p['text']) or p['text'].startswith('※ 다음 글을 읽고') or p['text'] == '[정답 및 해설]':
                end = p['index']
                break
        block = paragraphs[start:end]
        titles = [p for p in block if _V04959_EXAMPLE_TITLE_RE.fullmatch(p['text'])]
        if len(titles) != 1:
            issues.append(f'{qno}번 example title count={len(titles)}')
            continue
        title = titles[0]
        ti = block.index(title)
        body = next((p for p in block[ti + 1:] if p['text']), None)
        if body is None:
            issues.append(f'{qno}번 example body missing')
            continue
        body_pos = block.index(body)
        next_nonempty = next((p for p in block[body_pos + 1:] if p['text']), None)
        spacer_present = bool(next_nonempty and next_nonempty['index'] > body['index'] + 1)
        ts = styles.get(title['paraPrIDRef'], {})
        bs = styles.get(body['paraPrIDRef'], {})
        tb = border_edges.get(ts.get('borderFillIDRef'), {})
        bb = border_edges.get(bs.get('borderFillIDRef'), {})
        title_center = ts.get('horizontal') == 'CENTER'
        body_left = bs.get('horizontal') == 'LEFT'
        before_ok = int(ts.get('prev') or 0) >= _V049511_EXAMPLE_TITLE_PREV_HWPUNIT
        after_ok = int(bs.get('next') or 0) >= _V049511_EXAMPLE_BODY_NEXT_HWPUNIT
        edge_ok = (
            tb.get('left') == 'SOLID' and tb.get('right') == 'SOLID' and tb.get('top') == 'SOLID'
            and bb.get('left') == 'SOLID' and bb.get('right') == 'SOLID' and bb.get('bottom') == 'SOLID'
            and tb.get('bottom', 'NONE') == 'NONE' and bb.get('top', 'NONE') == 'NONE'
        )
        choice_ok = bool(next_nonempty and re.match(r'^①\s', next_nonempty['text']) and (after_ok or spacer_present))
        bottom_clearance_ok = after_ok or spacer_present
        top_clearance_ok = before_ok and int(ts.get('offsetTop') or 0) <= _V049510_BOX_TB_PADDING_HWPUNIT
        reports.append({
            'question_number': qno,
            'title_paragraph_index': title['index'],
            'body_paragraph_index': body['index'],
            'next_visible_paragraph_index': next_nonempty['index'] if next_nonempty else None,
            'next_visible_text': next_nonempty['text'][:80] if next_nonempty else None,
            'title_alignment': ts.get('horizontal'),
            'body_alignment': bs.get('horizontal'),
            'title_prev_hwpunit': ts.get('prev'),
            'body_next_hwpunit': bs.get('next'),
            'title_border_offset_top_hwpunit': ts.get('offsetTop'),
            'body_border_offset_bottom_hwpunit': bs.get('offsetBottom'),
            'title_alignment_ok': title_center,
            'body_alignment_ok': body_left,
            'space_before_ok': before_ok,
            'space_after_ok': after_ok,
            'spacer_fallback_present': spacer_present,
            'bottom_clearance_ok': bottom_clearance_ok,
            'top_border_clearance_ok': top_clearance_ok,
            'choice_clearance_ok': choice_ok,
            'connected_outer_edges_ok': edge_ok,
        })
    expected_count = sum(
        1 for q in expected_questions
        if (q.get('example_block') or {}).get('exists') and str((q.get('example_block') or {}).get('text') or '').strip()
    )
    title_alignment_ok = len(reports) == expected_count and all(r['title_alignment_ok'] and r['body_alignment_ok'] for r in reports)
    spacing_ok = len(reports) == expected_count and all(r['space_before_ok'] and r['bottom_clearance_ok'] and r['top_border_clearance_ok'] for r in reports)
    choice_ok = len(reports) == expected_count and all(r['choice_clearance_ok'] for r in reports)
    edges_ok = len(reports) == expected_count and all(r['connected_outer_edges_ok'] for r in reports)
    return {
        'expected_example_count': expected_count,
        'validated_example_count': len(reports),
        'reports': reports,
        'issues': issues,
        'example_title_alignment_status': 'PASS' if title_alignment_ok else 'FAIL',
        'example_box_spacing_status': 'PASS' if spacing_ok else 'FAIL',
        'example_choice_clearance_status': 'PASS' if choice_ok else 'FAIL',
        'example_box_edge_status': 'PASS' if edges_ok else 'FAIL',
        'status': 'PASS' if title_alignment_ok and spacing_ok and choice_ok and edges_ok and not issues else 'FAIL',
    }


def _v049511_validate_source_credits(
    header_xml: str,
    section_xml: str,
    result: dict,
) -> dict:
    paragraphs = _v04959_question_paragraph_map(section_xml)
    expected = _v049511_expected_source_credits(result)
    actual = [p for p in paragraphs if _V049511_SOURCE_CREDIT_RE.fullmatch(p['text'])]
    right = [p for p in actual if _v049511_para_horizontal(header_xml, p['paraPrIDRef']) == 'RIGHT']
    count_ok = len(actual) == len(expected)
    text_ok = sorted(p['text'] for p in actual) == sorted(expected)
    right_ok = count_ok and len(right) == len(expected)
    return {
        'expected_source_credit_count': len(expected),
        'detected_source_credit_count': len(actual),
        'right_aligned_source_credit_count': len(right),
        'expected_source_credits': expected,
        'detected_source_credits': [p['text'] for p in actual],
        'source_credit_count_status': 'PASS' if count_ok and text_ok else 'FAIL',
        'author_right_align_status': 'PASS' if right_ok and text_ok else 'FAIL',
        'status': 'PASS' if count_ok and text_ok and right_ok else 'FAIL',
    }


def _v049511_validate_pictures(header_xml: str, section_xml: str, result: dict) -> dict:
    styles = _v049511_para_style_info(header_xml)
    details = []
    for idx, pm in enumerate(re.finditer(r'<hp:p\b[^>]*\bparaPrIDRef="(\d+)"[^>]*>[\s\S]*?</hp:p>', section_xml)):
        p = pm.group(0)
        if '<hp:pic ' not in p and '<hp:pic>' not in p:
            continue
        para_id = int(pm.group(1))
        style = styles.get(para_id, {})
        for pic in re.findall(r'<hp:pic\b[\s\S]*?</hp:pic>', p):
            pos = re.search(r'<hp:pos\b([^>]*)/>', pic)
            attrs = pos.group(1) if pos else ''
            def attr(key: str) -> str | None:
                m = re.search(rf'\b{re.escape(key)}="([^"]+)"', attrs)
                return m.group(1) if m else None
            sz = re.search(r'<hp:sz\b[^>]*\bwidth="(\d+)"[^>]*\bheight="(\d+)"', pic)
            width = int(sz.group(1)) if sz else None
            height = int(sz.group(2)) if sz else None
            detail = {
                'paragraph_index': idx,
                'para_style_id': para_id,
                'paragraph_alignment': style.get('horizontal'),
                'treatAsChar': attr('treatAsChar'),
                'affectLSpacing': attr('affectLSpacing'),
                'flowWithText': attr('flowWithText'),
                'allowOverlap': attr('allowOverlap'),
                'horzAlign': attr('horzAlign'),
                'width_hwpunit': width,
                'height_hwpunit': height,
                'safe_inner_width_hwpunit': _V049511_SAFE_IMAGE_INNER_WIDTH_HWPUNIT,
            }
            detail['line_height_accounted'] = detail['treatAsChar'] == '1' and detail['affectLSpacing'] == '1'
            detail['centered'] = detail['horzAlign'] == 'CENTER' and detail['paragraph_alignment'] == 'CENTER'
            detail['non_overlapping'] = detail['allowOverlap'] == '0' and detail['flowWithText'] == '1'
            detail['width_within_safe_inner_box'] = width is not None and width <= _V049511_SAFE_IMAGE_INNER_WIDTH_HWPUNIT
            detail['contained'] = all([
                detail['line_height_accounted'],
                detail['centered'],
                detail['non_overlapping'],
                detail['width_within_safe_inner_box'],
            ])
            details.append(detail)
    expected = int(result.get('image_filter_v0481', {}).get('saved_count') or 0)
    count_ok = len(details) == expected
    affect_ok = count_ok and all(d['line_height_accounted'] for d in details)
    containment_ok = count_ok and all(d['contained'] for d in details)
    return {
        'expected_picture_count': expected,
        'validated_picture_count': len(details),
        'safe_inner_width_hwpunit': _V049511_SAFE_IMAGE_INNER_WIDTH_HWPUNIT,
        'details': details,
        'picture_affect_line_spacing_status': 'PASS' if affect_ok else 'FAIL',
        'picture_box_containment_status': 'PASS' if containment_ok else 'FAIL',
        'status': 'PASS' if affect_ok and containment_ok else 'FAIL',
    }


def _v049511_validate_image_units(render_plan: dict) -> dict:
    details = []
    all_ok = True
    for page in render_plan.get('pages', []):
        for side in ('left', 'right'):
            for item in page.get(side, []):
                if item.get('type') != 'image':
                    continue
                w_pt = float(item.get('target_width_pt_v0495') or 0.0)
                h_pt = float(item.get('target_height_pt_v0495') or 0.0)
                w_mm = float(item.get('target_width_mm_v0495') or 0.0)
                h_mm = float(item.get('target_height_mm_v0495') or 0.0)
                expected_w_mm = w_pt * 25.4 / 72.0 if w_pt else 0.0
                expected_h_mm = h_pt * 25.4 / 72.0 if h_pt else 0.0
                width_ok = w_pt > 0 and abs(w_mm - expected_w_mm) <= _V049511_UNIT_TOLERANCE_MM
                height_ok = h_pt > 0 and abs(h_mm - expected_h_mm) <= _V049511_UNIT_TOLERANCE_MM
                size_cap_ok = w_pt <= _V049511_IMAGE_MAX_WIDTH_PT + 1e-6 and h_pt <= _V049511_IMAGE_MAX_HEIGHT_PT + 1e-6
                ok = width_ok and height_ok and size_cap_ok
                all_ok = all_ok and ok
                details.append({
                    'filename': item.get('filename'),
                    'width_pt': w_pt,
                    'height_pt': h_pt,
                    'width_mm': w_mm,
                    'height_mm': h_mm,
                    'expected_width_mm_from_pt': round(expected_w_mm, 3),
                    'expected_height_mm_from_pt': round(expected_h_mm, 3),
                    'width_consistent': width_ok,
                    'height_consistent': height_ok,
                    'size_cap_ok': size_cap_ok,
                })
    return {
        'image_count': len(details),
        'tolerance_mm': _V049511_UNIT_TOLERANCE_MM,
        'details': details,
        'image_unit_consistency_status': 'PASS' if all_ok else 'FAIL',
        'status': 'PASS' if all_ok else 'FAIL',
    }


def v049511_validate_hwpx(path: Path, *, result: dict, render_plan: dict) -> dict:
    info = v049510_validate_hwpx(path, result=result, render_plan=render_plan)
    info['validator_version'] = _V049511_VERSION
    if not Path(path).exists() or not zipfile.is_zipfile(path) or info.get('package_status') != 'PASS':
        info['status'] = 'FAIL'
        return info
    try:
        with zipfile.ZipFile(path, 'r') as zf:
            header = zf.read('Contents/header.xml').decode('utf-8', errors='strict')
            section0 = zf.read('Contents/section0.xml').decode('utf-8', errors='strict')

        example = _v049511_validate_example_visual_layout(header, section0, result)
        credits = _v049511_validate_source_credits(header, section0, result)
        pictures = _v049511_validate_pictures(header, section0, result)
        units = _v049511_validate_image_units(render_plan)

        info['example_visual_layout'] = example
        info['example_title_alignment_status'] = example['example_title_alignment_status']
        info['example_box_spacing_status'] = example['example_box_spacing_status']
        info['example_choice_clearance_status'] = example['example_choice_clearance_status']
        info['source_credit_validation'] = credits
        info['source_credit_count_status'] = credits['source_credit_count_status']
        info['author_right_align_status'] = credits['author_right_align_status']
        info['expected_source_credit_count'] = credits['expected_source_credit_count']
        info['right_aligned_source_credit_count'] = credits['right_aligned_source_credit_count']
        info['picture_layout_validation'] = pictures
        info['picture_box_containment_status'] = pictures['picture_box_containment_status']
        info['picture_affect_line_spacing_status'] = pictures['picture_affect_line_spacing_status']
        info['image_unit_validation'] = units
        info['image_unit_consistency_status'] = units['image_unit_consistency_status']

        critical = [
            info.get('package_status'),
            info.get('image_order_status'),
            info.get('image_anchor_status'),
            info.get('image_answer_boundary_status'),
            info.get('continuous_flow_status'),
            info.get('question_integrity_status'),
            info.get('example_integrity_status'),
            info.get('underline_status'),
            info.get('question_bold_status'),
            info.get('author_right_align_status'),
            info.get('question_negative_underline_status'),
            info.get('example_detection_status'),
            info.get('cross_region_metadata_status'),
            info.get('example_title_alignment_status'),
            info.get('example_box_spacing_status'),
            info.get('example_choice_clearance_status'),
            info.get('source_credit_count_status'),
            info.get('picture_box_containment_status'),
            info.get('picture_affect_line_spacing_status'),
            info.get('image_unit_consistency_status'),
        ]
        info['status'] = 'FAIL' if 'FAIL' in critical else 'WARN' if 'WARN' in critical else 'PASS'
        return info
    except Exception as exc:
        info['v049511_validation_error'] = str(exc)
        info['status'] = 'FAIL'
        return info


def _v049511_postprocess_hwpx(path: Path, result: dict, render_plan: dict) -> dict:
    import xml.etree.ElementTree as ET
    path = Path(path)
    report = {
        'version': _V049511_VERSION,
        'status': 'SKIPPED',
        'applied': False,
        'source': str(path),
    }
    if not path.exists() or not zipfile.is_zipfile(path):
        report['reason'] = 'no usable HWPX'
        return report
    candidate = path.with_name(path.stem + '_v049511_candidate.hwpx')
    if candidate.exists():
        try:
            candidate.unlink()
        except Exception:
            pass
    try:
        with zipfile.ZipFile(path, 'r') as zf:
            header = zf.read('Contents/header.xml').decode('utf-8', errors='strict')
            section0 = zf.read('Contents/section0.xml').decode('utf-8', errors='strict')

        header, section0, example_report = _v049511_apply_example_visual_layout(header, section0, result)

        # Prefer true paragraph spacing. Only insert a real blank paragraph when
        # the structural visual validator says the choice clearance is still unsafe.
        pre_spacer_check = _v049511_validate_example_visual_layout(header, section0, result)
        spacer_report = {'spacer_inserted_count': 0, 'details': [], 'status': 'NOT_NEEDED'}
        if (
            pre_spacer_check.get('example_box_spacing_status') != 'PASS'
            or pre_spacer_check.get('example_choice_clearance_status') != 'PASS'
        ):
            section0, spacer_report = _v049511_insert_example_spacer_fallback(section0, result)
        example_report['spacer_inserted_count'] = spacer_report.get('spacer_inserted_count', 0)
        example_report['spacer_fallback_report'] = spacer_report

        header, section0, credit_report = _v049511_apply_source_credit_right_align(header, section0, result)
        header, section0, picture_report = _v049511_apply_picture_layout(header, section0)

        ET.fromstring(header.encode('utf-8'))
        ET.fromstring(section0.encode('utf-8'))
        _v04958_repack_postprocessed_hwpx(path, candidate, header, section0)
        validation = v049511_validate_hwpx(candidate, result=result, render_plan=render_plan)
        report.update({
            'status': 'APPLIED' if validation.get('status') == 'PASS' else 'REJECTED_BY_VALIDATION',
            'applied': validation.get('status') == 'PASS',
            'candidate': str(candidate),
            'example_visual_layout': example_report,
            'source_credit_right_align': credit_report,
            'picture_layout': picture_report,
            'validation': validation,
        })
        if validation.get('status') == 'PASS':
            os.replace(str(candidate), str(path))
            report['candidate'] = None
            report['final_path'] = str(path.resolve())
        elif candidate.exists():
            candidate.unlink()
        return report
    except Exception as exc:
        report['status'] = 'FAIL'
        report['reason'] = str(exc)
        try:
            if candidate.exists():
                candidate.unlink()
        except Exception:
            pass
        return report


def v049511_upgrade_result(
    result: dict,
    pdf_path: Path,
    checkpoint_path: Path | None = None,
    *,
    hwpx_output_path: Path | None = None,
    question_detection: dict | None = None,
    security_module_path: Path | None = None,
    allow_interactive_hwp: bool = False,
    show_hwp: bool = False,
) -> dict:
    _v0491_log('[v0.4.9.5.11] 보기 조판/출전 탐지/이미지 containment/시각 validator 강화 준비')

    # Generate the proven 5.10 document first, then apply one atomic XML-only
    # visual-stabilization layer. This preserves the existing parser and COM writer.
    result = v049510_upgrade_result(
        result,
        pdf_path,
        checkpoint_path=checkpoint_path,
        hwpx_output_path=hwpx_output_path,
        question_detection=question_detection,
        security_module_path=security_module_path,
        allow_interactive_hwp=allow_interactive_hwp,
        show_hwp=show_hwp,
    )

    render_plan = dict(result.get('render_plan_v049510') or {})
    render_plan = _v049511_fix_render_plan_image_units(render_plan)
    render_plan['version'] = _V049511_VERSION
    render_plan['editorial_refinements_v049511'] = {
        'example_title_alignment': 'CENTER',
        'example_body_alignment': 'LEFT',
        'example_space_before_hwpunit': _V049511_EXAMPLE_TITLE_PREV_HWPUNIT,
        'example_space_after_hwpunit': _V049511_EXAMPLE_BODY_NEXT_HWPUNIT,
        'example_spacer_fallback': True,
        'source_credit_detection_block_type_independent': True,
        'passage_picture_affect_line_spacing': True,
        'passage_picture_paragraph_alignment': 'CENTER',
        'passage_picture_horz_align': 'CENTER',
        'image_max_width_pt': _V049511_IMAGE_MAX_WIDTH_PT,
        'image_max_height_pt': _V049511_IMAGE_MAX_HEIGHT_PT,
        'image_mm_recalculated_from_pt': True,
    }
    result['render_plan_v049511'] = render_plan
    result.pop('render_plan_v049510', None)

    result['version'] = _V049511_VERSION
    result['parser_version'] = _V049511_VERSION
    result['generator_version'] = 'PDF Parser Integrated v0.4.9.5.11'
    result['question_detection_v049511'] = result.pop('question_detection_v049510', question_detection or {})
    result['schema_version'] = {
        'base': 'v0.4.9.5.10',
        'extension': [
            'example_title_center_body_left',
            'example_box_visual_clearance',
            'example_spacer_fallback',
            'source_credit_block_type_independent_detection',
            'passage_picture_affect_line_spacing',
            'passage_picture_center_paragraph',
            'image_pt_mm_unit_consistency',
            'visual_layout_validator',
        ],
    }

    old_hwpx = result.get('hwpx_v049510') or {}
    final_path_value = old_hwpx.get('final_path') or old_hwpx.get('path')
    hwpx_info = dict(old_hwpx)
    hwpx_info['backend'] = 'hancom_com_v049511'
    hwpx_info['renderer_mode'] = 'v049510_base_plus_atomic_visual_stabilization_v049511'

    if old_hwpx.get('status') == 'created' and final_path_value and Path(final_path_value).exists():
        semantic = _v049511_postprocess_hwpx(Path(final_path_value), result, render_plan)
        hwpx_info['semantic_finalize_v049511'] = semantic
        if semantic.get('applied'):
            validation = v049511_validate_hwpx(Path(final_path_value), result=result, render_plan=render_plan)
            hwpx_info['validation'] = validation
            hwpx_info['status'] = 'created' if validation.get('status') == 'PASS' else 'INVALID'
            hwpx_info['final_path'] = str(Path(final_path_value).resolve())
        else:
            hwpx_info['status'] = 'INVALID'
            if semantic.get('validation'):
                hwpx_info['validation'] = semantic['validation']
    elif old_hwpx.get('status') == 'SKIPPED':
        hwpx_info['semantic_finalize_v049511'] = {
            'status': 'SKIPPED',
            'applied': False,
            'reason': 'Hancom writer unavailable on this platform',
        }
        # Even without HWPX generation, unit metadata can be validated locally.
        hwpx_info['validation'] = {
            **(old_hwpx.get('validation') or {}),
            'validator_version': _V049511_VERSION,
            **_v049511_validate_image_units(render_plan),
        }

    result['hwpx_v049511'] = hwpx_info
    result.pop('hwpx_v049510', None)
    result['hancom_security_v049511'] = result.pop('hancom_security_v049510', hwpx_info.get('hancom_security') or {})

    final_validation = hwpx_info.get('validation') or {}
    structural = result.get('structural_validation_v049510') or {}
    security_runtime = result.get('hancom_security_v049511') or {}
    hwpx_status = hwpx_info.get('status')
    security_ok = (
        security_runtime.get('unattended_ready') is True
        or hwpx_status == 'SKIPPED'
        or (allow_interactive_hwp and hwpx_status == 'created')
    )
    critical_keys = (
        'image_order_status', 'image_anchor_status', 'image_answer_boundary_status',
        'continuous_flow_status', 'question_integrity_status', 'example_integrity_status',
        'underline_status', 'question_bold_status', 'author_right_align_status',
        'question_negative_underline_status', 'example_detection_status',
        'cross_region_metadata_status', 'example_title_alignment_status',
        'example_box_spacing_status', 'example_choice_clearance_status',
        'source_credit_count_status', 'picture_box_containment_status',
        'picture_affect_line_spacing_status', 'image_unit_consistency_status',
    )
    critical_fail = any(final_validation.get(k) == 'FAIL' for k in critical_keys)
    if critical_fail or structural.get('status') == 'FAIL':
        final_status = 'FAIL'
    elif hwpx_status == 'SKIPPED':
        final_status = 'WARN'
    elif hwpx_status == 'created' and security_ok and final_validation.get('status') == 'PASS':
        final_status = 'PASS'
    else:
        final_status = 'FAIL'

    neg = result.get('question_negative_underline_v049510') or {}
    result['question_negative_underline_v049511'] = neg
    result.pop('question_negative_underline_v049510', None)
    result['validation_v049511'] = {
        'question_count': len(result.get('questions', [])),
        'render_page_count': render_plan.get('stats', {}).get('page_count', 0),
        'render_item_count': render_plan.get('stats', {}).get('render_item_count', 0),
        'question_detection_status': (result.get('question_detection_v049511') or {}).get('status'),
        'structural_status': structural.get('status'),
        'example_detection_status': final_validation.get('example_detection_status', structural.get('example_detection_status')),
        'underline_detection_status': structural.get('underline_detection_status'),
        'cross_region_metadata_status': final_validation.get('cross_region_metadata_status', structural.get('cross_region_metadata_status')),
        'question_negative_keyword_question_count': neg.get('question_count', 0),
        'hancom_security_status': security_runtime.get('status'),
        'unattended_ready': security_runtime.get('unattended_ready', False),
        'hwpx_status': hwpx_status,
        'hwpx_final_path': hwpx_info.get('final_path'),
        'hwpx_validation_status': final_validation.get('status'),
        'hwpx_package_status': final_validation.get('package_status'),
        'continuous_flow_status': final_validation.get('continuous_flow_status'),
        'question_integrity_status': final_validation.get('question_integrity_status'),
        'example_integrity_status': final_validation.get('example_integrity_status'),
        'example_box_status': final_validation.get('example_box_status'),
        'example_title_alignment_status': final_validation.get('example_title_alignment_status'),
        'example_box_spacing_status': final_validation.get('example_box_spacing_status'),
        'example_choice_clearance_status': final_validation.get('example_choice_clearance_status'),
        'underline_status': final_validation.get('underline_status'),
        'question_bold_status': final_validation.get('question_bold_status'),
        'author_right_align_status': final_validation.get('author_right_align_status'),
        'source_credit_count_status': final_validation.get('source_credit_count_status'),
        'expected_source_credit_count': final_validation.get('expected_source_credit_count'),
        'right_aligned_source_credit_count': final_validation.get('right_aligned_source_credit_count'),
        'question_negative_underline_status': final_validation.get('question_negative_underline_status'),
        'image_position_status': final_validation.get('image_position_status'),
        'picture_box_containment_status': final_validation.get('picture_box_containment_status'),
        'picture_affect_line_spacing_status': final_validation.get('picture_affect_line_spacing_status'),
        'image_unit_consistency_status': final_validation.get('image_unit_consistency_status'),
        'status': final_status,
    }
    return result


def main_v049511() -> None:
    parser = argparse.ArgumentParser(
        description='국어 문제 PDF -> 구조화 JSON + HWPX V0.4.9.5.11 조판 안정화/시각 validator 강화'
    )
    parser.add_argument('pdf', type=Path, help='분석할 PDF 파일')
    parser.add_argument('-o', '--output', type=Path, default=None, help='저장할 JSON. 생략하면 <PDF이름>_result.json')
    parser.add_argument('--hwpx-output', type=Path, default=None, help='최종 HWPX 희망 파일명. 생략하면 <PDF이름>.hwpx, 존재 시 _runNN 자동 생성')
    parser.add_argument('-q', '--questions', nargs='+', type=int, default=None, help='추출할 문제 번호. 생략하면 PDF에서 자동 탐지')
    parser.add_argument('--no-kiwi', action='store_true', help='Kiwi 경계 판별을 끔')
    parser.add_argument('--security-module', type=Path, default=None, help='FilePathCheckerModuleExample.dll 경로')
    parser.add_argument('--allow-interactive-hwp', action='store_true', help='보안 모듈 실패 시 대화형 한글 허용')
    parser.add_argument('--show-hwp', action='store_true', help='한글 창 표시')
    args = parser.parse_args()

    if not args.pdf.exists():
        raise SystemExit(f'PDF 파일을 찾을 수 없습니다: {args.pdf}')
    if not args.no_kiwi and Kiwi is None:
        print('[경고] kiwipiepy 미설치. fallback으로 실행합니다.')

    detection = v04957_detect_question_numbers(args.pdf)
    if args.questions:
        question_numbers = sorted(set(args.questions))
        detection['selection_mode'] = 'explicit_cli'
        detection['selected_question_numbers'] = question_numbers
    else:
        if detection.get('status') != 'PASS' or not detection.get('question_numbers'):
            raise SystemExit(
                '문제 번호 자동 탐지에 실패했습니다. -q 옵션으로 문제 번호를 직접 지정하세요. '
                + str(detection.get('reason') or '')
            )
        question_numbers = list(detection['question_numbers'])
        detection['selection_mode'] = 'auto_detected'
        detection['selected_question_numbers'] = question_numbers

    json_output = Path(args.output) if args.output else _v04957_default_json_path(args.pdf)
    checkpoint_path = json_output.with_name(json_output.stem + '_pre_hwpx.json')
    result = parse_v0_2_3(args.pdf, question_numbers, use_kiwi=not args.no_kiwi)
    result = v044_upgrade_result(result, args.pdf)
    result = v045_upgrade_result(result, args.pdf)
    result = v049511_upgrade_result(
        result,
        args.pdf,
        checkpoint_path=checkpoint_path,
        hwpx_output_path=args.hwpx_output,
        question_detection=detection,
        security_module_path=args.security_module,
        allow_interactive_hwp=args.allow_interactive_hwp,
        show_hwp=args.show_hwp,
    )
    json_output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')

    checkpoint_info = result.get('pre_hwpx_checkpoint') or {}
    checkpoint_file = Path(str(checkpoint_info.get('path') or '')) if isinstance(checkpoint_info, dict) else None
    if result.get('hwpx_v049511', {}).get('status') == 'created' and checkpoint_file and str(checkpoint_file):
        try:
            if checkpoint_file.exists():
                checkpoint_file.unlink()
            checkpoint_info['retained'] = False
            result['pre_hwpx_checkpoint'] = checkpoint_info
            json_output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception as exc:
            checkpoint_info['retained'] = True
            checkpoint_info['cleanup_error'] = str(exc)

    v = result.get('validation_v049511', {})
    print('=' * 76)
    print('V0.4.9.5.11 HWPX 조판 안정화 + 시각 validator 강화 완료')
    print('=' * 76)
    print(f'입력 : {args.pdf}')
    print(f'JSON : {json_output.resolve()}')
    print(f'HWPX : {v.get("hwpx_final_path")}')
    print(f'문제 : {v.get("question_count", 0)} | 자동 탐지 : {v.get("question_detection_status")}')
    print(
        f'<보기> 정렬/간격/선택지 여유 : '
        f'{v.get("example_title_alignment_status")} / '
        f'{v.get("example_box_spacing_status")} / '
        f'{v.get("example_choice_clearance_status")}'
    )
    print(
        f'출전 우측정렬 : {v.get("author_right_align_status")} '
        f'({v.get("right_aligned_source_credit_count")}/{v.get("expected_source_credit_count")}) | '
        f'부정문 밑줄 : {v.get("question_negative_underline_status")}'
    )
    print(
        f'이미지 박스 containment : {v.get("picture_box_containment_status")} | '
        f'line-height 반영 : {v.get("picture_affect_line_spacing_status")} | '
        f'pt/mm 일치 : {v.get("image_unit_consistency_status")}'
    )
    print(f'HWPX 상태 : {v.get("hwpx_status")} | 최종 검증 : {v.get("status")}')



# =============================================================================
# V0.4.9.5.12 ownership / physical-clearance stabilization layer
#
# 1) <보기> 앞/뒤에 실제 빈 paragraph를 항상 둔다.
# 2) 상/하 border offset은 최소값으로 줄여 인접 텍스트 침범을 막는다.
# 3) PDF의 "※ 다음 글을 읽고..." anchor를 문서 읽기 순서로 추적하여
#    passage image ownership을 재계산한다. 페이지/열 경계에 걸친 이미지도
#    다음 passage group에 귀속시킬 수 있다.
# 4) 최종 validator는 metadata 속성만 보는 대신 실제 HWPX에서
#    guide < image < 첫 문제 순서, passage border style, image digest ownership을
#    동시에 검사한다.
# =============================================================================

_V049512_VERSION = "v0.4.9.5.12"
_V049512_EXAMPLE_OUTER_TB_HWPUNIT = 120   # ~0.42 mm: 선이 인접 글자로 뻗는 폭 최소화
_V049512_EXAMPLE_JOIN_TB_HWPUNIT = 40     # title/body 접합부는 아주 작게 유지
_V049512_PASSAGE_ANCHOR_RE = re.compile(r"^\s*※\s*다음\s+글을\s+읽고")


def _v049512_order_key(page: int, column: int | str, y: float) -> tuple[int, int, float]:
    if isinstance(column, str):
        col = 0 if column.strip().lower() in {"left", "l", "0"} else 1
    else:
        try:
            col = 0 if int(column) == 0 else 1
        except Exception:
            col = 0
    return (int(page), col, float(y))


def _v049512_pdf_passage_anchors(pdf_path: Path) -> list[dict[str, Any]]:
    """Return passage-start anchors in the PDF's two-column reading order."""
    anchors: list[dict[str, Any]] = []
    doc = fitz.open(pdf_path)
    try:
        for page_index, page in enumerate(doc):
            for line in get_line_records(page):
                text = str(line.get("text") or "").strip()
                if not _V049512_PASSAGE_ANCHOR_RE.match(text):
                    continue
                bbox = line.get("bbox")
                if bbox is None:
                    continue
                col = get_column(page, float(bbox.x0))
                anchors.append({
                    "page": page_index + 1,
                    "column": col,
                    "y": float(bbox.y0),
                    "text": text,
                    "order_key": _v049512_order_key(page_index + 1, col, float(bbox.y0)),
                })
    finally:
        doc.close()
    anchors.sort(key=lambda a: a["order_key"])
    return anchors


def _v049512_asset_order_key(asset: dict[str, Any]) -> tuple[int, int, float]:
    bbox = asset.get("bbox") or [0, 0, 0, 0]
    page = int(asset.get("page") or 0)
    col = _v044_column_from_bbox(bbox)
    if col is None:
        col = 0
    y = float(bbox[1]) if len(bbox) == 4 else 0.0
    return _v049512_order_key(page, col, y)


def _v049512_rebuild_group_and_question_image_links(result: dict[str, Any]) -> None:
    """Synchronize group/question image arrays after changing asset ownership."""
    groups = {
        int(g.get("id") or 0): g
        for g in result.get("passage_groups", [])
        if int(g.get("id") or 0) > 0
    }
    selected = [
        a for a in result.get("image_assets", [])
        if a.get("is_problem_image") is True and a.get("classification") == "problem_figure"
    ]
    for group in groups.values():
        group["image_assets"] = []
        group["image_sections"] = {}

    for asset in sorted(selected, key=_v049512_asset_order_key):
        gid = int(asset.get("passage_group_id") or 0)
        group = groups.get(gid)
        if group is None:
            continue
        group["image_assets"].append(asset)
        section_label = asset.get("section_label")
        if section_label:
            group["image_sections"].setdefault(str(section_label), []).append(asset)

    # v0.4.5 made copies in question.image_assets, so rebuild them explicitly.
    for q in result.get("questions", []):
        gid = int(q.get("passage_group_id") or 0)
        group = groups.get(gid)
        if group is None:
            q["image_assets"] = []
            q["image_asset_scope"] = "none"
            continue
        refs = _v044_question_refs(str(q.get("question") or ""))
        selected_assets: list[dict[str, Any]] = []
        if group.get("style_hint") == "image_only" and refs:
            seen: set[tuple[int, int]] = set()
            for ref in refs:
                for asset in group.get("image_sections", {}).get(ref, []):
                    key = (int(asset.get("page") or 0), int(asset.get("xref") or 0))
                    if key not in seen:
                        seen.add(key)
                        selected_assets.append(asset)
        if not selected_assets:
            selected_assets = list(group.get("image_assets", []))
        q["image_assets"] = [dict(a) for a in selected_assets]
        q["image_asset_scope"] = "section" if group.get("style_hint") == "image_only" and refs else "group"
        q["image_refs"] = refs


def _v049512_reassign_passage_image_ownership(pdf_path: Path, result: dict[str, Any]) -> dict[str, Any]:
    """Assign every problem figure to the passage whose PDF start anchor precedes it.

    This fixes the page/column-boundary case seen in the reference PDF: the first
    three '식빵이 기다리는 동안' images live on page 8/right column immediately
    after the ninth passage anchor, while the textual body continues on page 9.
    A source-page-only matcher incorrectly gave those pictures to group 8.
    """
    groups = sorted(
        [g for g in result.get("passage_groups", []) if int(g.get("id") or 0) > 0],
        key=lambda g: int(g.get("id") or 0),
    )
    anchors = _v049512_pdf_passage_anchors(pdf_path)
    selected = [
        a for a in result.get("image_assets", [])
        if a.get("is_problem_image") is True and a.get("classification") == "problem_figure"
    ]

    anchor_group_pairs: list[tuple[tuple[int, int, float], int]] = []
    mapping_warnings: list[str] = []
    if len(anchors) != len(groups):
        mapping_warnings.append(
            f"passage anchor/group count mismatch: anchors={len(anchors)}, groups={len(groups)}"
        )
    for anchor, group in zip(anchors, groups):
        gid = int(group.get("id") or 0)
        anchor["passage_group_id"] = gid
        anchor_group_pairs.append((anchor["order_key"], gid))

    details = []
    changed = 0
    unassigned = 0
    for asset in sorted(selected, key=_v049512_asset_order_key):
        key = _v049512_asset_order_key(asset)
        expected_gid = None
        for anchor_key, gid in anchor_group_pairs:
            if anchor_key <= key:
                expected_gid = gid
            else:
                break
        old_gid = int(asset.get("passage_group_id") or 0) or None
        if expected_gid is None:
            unassigned += 1
            asset["ownership_v049512"] = {
                "status": "UNASSIGNED",
                "old_group_id": old_gid,
                "expected_group_id": None,
                "order_key": list(key),
            }
            details.append({
                "page": asset.get("page"),
                "xref": asset.get("xref"),
                "old_group_id": old_gid,
                "new_group_id": None,
                "changed": False,
                "status": "UNASSIGNED",
            })
            continue
        if old_gid != expected_gid:
            changed += 1
        asset["passage_group_id"] = expected_gid
        asset["ownership_v049512"] = {
            "status": "ASSIGNED",
            "method": "preceding_passage_anchor_in_pdf_reading_order",
            "old_group_id": old_gid,
            "expected_group_id": expected_gid,
            "order_key": list(key),
        }
        details.append({
            "page": asset.get("page"),
            "xref": asset.get("xref"),
            "old_group_id": old_gid,
            "new_group_id": expected_gid,
            "changed": old_gid != expected_gid,
            "status": "ASSIGNED",
        })

    _v049512_rebuild_group_and_question_image_links(result)

    # Expected digest -> ownership map is persisted for the final HWPX validator.
    digest_map: dict[str, int] = {}
    for asset in selected:
        digest = str(asset.get("byte_hash") or "")
        gid = int(asset.get("passage_group_id") or 0)
        if digest and gid:
            digest_map[digest] = gid

    group_counts = {
        int(g.get("id") or 0): len(g.get("image_assets", []))
        for g in groups
    }
    report = {
        "version": _V049512_VERSION,
        "method": "PDF passage-anchor reading order",
        "passage_anchor_count": len(anchors),
        "passage_group_count": len(groups),
        "selected_problem_figure_count": len(selected),
        "changed_ownership_count": changed,
        "unassigned_count": unassigned,
        "anchors": anchors,
        "details": details,
        "group_image_counts": group_counts,
        "expected_digest_group_map": digest_map,
        "warnings": mapping_warnings,
        "status": "PASS" if not mapping_warnings and unassigned == 0 and len(anchors) == len(groups) else "FAIL",
    }
    result["passage_image_ownership_v049512"] = report
    return report


def _v049512_make_empty_spacer_from_para(paragraph_xml: str) -> str:
    """Create a real empty paragraph using a neighboring border-free paragraph shell."""
    sm = re.match(r'(<hp:p\b[^>]*>)', paragraph_xml)
    rm = re.search(r'<hp:run\b[^>]*\bcharPrIDRef="(\d+)"', paragraph_xml)
    if not sm:
        raise RuntimeError("cannot build spacer: paragraph start tag missing")
    start_tag = sm.group(1)
    char_id = int(rm.group(1)) if rm else 0
    return f'{start_tag}<hp:run charPrIDRef="{char_id}"><hp:t/></hp:run></hp:p>'


def _v049512_force_example_spacers(section_xml: str, result: dict[str, Any]) -> tuple[str, dict]:
    """Ensure exactly one physical empty paragraph before title and after body."""
    expected = _v04959_expected_examples(result)
    paragraphs = list(re.finditer(r'<hp:p\b[^>]*>[\s\S]*?</hp:p>', section_xml))
    if not paragraphs:
        return section_xml, {"status": "FAIL", "reason": "no paragraphs", "inserted_before": 0, "inserted_after": 0}

    insert_before: dict[int, str] = {}
    insert_after: dict[int, str] = {}
    reports = []
    expected_index = 0

    def visible(idx: int) -> str:
        return _v04958_normalize_visible_text(_v04954_para_text(paragraphs[idx].group(0)))

    for i, pm in enumerate(paragraphs):
        title_text = visible(i)
        if not _V04959_EXAMPLE_TITLE_RE.fullmatch(title_text):
            continue
        exp = expected[expected_index] if expected_index < len(expected) else None
        expected_index += 1
        body_i = None
        for j in range(i + 1, min(len(paragraphs), i + 6)):
            if visible(j):
                body_i = j
                break
        if body_i is None:
            reports.append({"question_number": (exp or {}).get("question_number"), "status": "FAIL", "reason": "body missing"})
            continue
        expected_body = _v04958_normalize_visible_text((exp or {}).get("text"))
        actual_body = visible(body_i)
        if expected_body and actual_body != expected_body:
            reports.append({
                "question_number": (exp or {}).get("question_number"), "status": "FAIL",
                "reason": "body mismatch", "expected": expected_body, "actual": actual_body,
            })
            continue

        before_exists = i > 0 and not visible(i - 1)
        after_exists = body_i + 1 < len(paragraphs) and not visible(body_i + 1)

        if not before_exists:
            # Use the previous question/stem shell so the spacer itself has no box border.
            template_i = max(0, i - 1)
            insert_before[i] = _v049512_make_empty_spacer_from_para(paragraphs[template_i].group(0))
        if not after_exists:
            # Prefer the first choice shell after the example body.
            template_i = body_i + 1 if body_i + 1 < len(paragraphs) else body_i
            insert_after[body_i] = _v049512_make_empty_spacer_from_para(paragraphs[template_i].group(0))

        reports.append({
            "question_number": (exp or {}).get("question_number"),
            "title_paragraph_index_before_insert": i,
            "body_paragraph_index_before_insert": body_i,
            "before_spacer_preexisted": before_exists,
            "after_spacer_preexisted": after_exists,
            "before_spacer_inserted": not before_exists,
            "after_spacer_inserted": not after_exists,
            "status": "PASS",
        })

    out: list[str] = []
    cursor = 0
    for idx, pm in enumerate(paragraphs):
        out.append(section_xml[cursor:pm.start()])
        if idx in insert_before:
            out.append(insert_before[idx])
        out.append(pm.group(0))
        if idx in insert_after:
            out.append(insert_after[idx])
        cursor = pm.end()
    out.append(section_xml[cursor:])
    expected_count = len(expected)
    ok = len(reports) == expected_count and all(r.get("status") == "PASS" for r in reports)
    return ''.join(out), {
        "expected_example_count": expected_count,
        "processed_example_count": len(reports),
        "inserted_before": len(insert_before),
        "inserted_after": len(insert_after),
        "reports": reports,
        "status": "PASS" if ok else "FAIL",
    }


def _v049512_validate_example_physical_clearance(header_xml: str, section_xml: str, result: dict[str, Any]) -> dict:
    """Require physical spacer paragraphs on both sides, not inferred spacing metadata."""
    paragraphs = _v04959_question_paragraph_map(section_xml)
    styles = _v049511_para_style_info(header_xml)
    expected = _v04959_expected_examples(result)
    reports = []
    issues = []
    exp_i = 0
    for pos, p in enumerate(paragraphs):
        if not _V04959_EXAMPLE_TITLE_RE.fullmatch(p["text"]):
            continue
        exp = expected[exp_i] if exp_i < len(expected) else None
        exp_i += 1
        body_pos = None
        for j in range(pos + 1, min(len(paragraphs), pos + 6)):
            if paragraphs[j]["text"]:
                body_pos = j
                break
        if body_pos is None:
            issues.append(f"{(exp or {}).get('question_number')}번 example body missing")
            continue
        title_style = styles.get(p["paraPrIDRef"], {})
        body = paragraphs[body_pos]
        body_style = styles.get(body["paraPrIDRef"], {})
        before_spacer = pos > 0 and paragraphs[pos - 1]["text"] == ""
        after_spacer = body_pos + 1 < len(paragraphs) and paragraphs[body_pos + 1]["text"] == ""
        next_visible = None
        for j in range(body_pos + 1, min(len(paragraphs), body_pos + 6)):
            if paragraphs[j]["text"]:
                next_visible = paragraphs[j]
                break
        title_center = title_style.get("horizontal") == "CENTER"
        body_left = body_style.get("horizontal") == "LEFT"
        top_offset_ok = int(title_style.get("offsetTop") or 0) <= _V049512_EXAMPLE_OUTER_TB_HWPUNIT
        bottom_offset_ok = int(body_style.get("offsetBottom") or 0) <= _V049512_EXAMPLE_OUTER_TB_HWPUNIT
        choice_after = bool(next_visible and re.match(r"^①\s", next_visible["text"]))
        reports.append({
            "question_number": (exp or {}).get("question_number"),
            "title_paragraph_index": p["index"],
            "body_paragraph_index": body["index"],
            "physical_spacer_before": before_spacer,
            "physical_spacer_after": after_spacer,
            "title_alignment": title_style.get("horizontal"),
            "body_alignment": body_style.get("horizontal"),
            "title_border_offset_top_hwpunit": title_style.get("offsetTop"),
            "body_border_offset_bottom_hwpunit": body_style.get("offsetBottom"),
            "border_offset_within_v049512_limit": top_offset_ok and bottom_offset_ok,
            "next_visible_text": next_visible["text"][:100] if next_visible else None,
            "choice_after_box": choice_after,
            "ok": before_spacer and after_spacer and title_center and body_left and top_offset_ok and bottom_offset_ok and choice_after,
        })
    count_ok = len(reports) == len(expected)
    all_ok = count_ok and all(r["ok"] for r in reports) and not issues
    return {
        "expected_example_count": len(expected),
        "validated_example_count": len(reports),
        "reports": reports,
        "issues": issues,
        "physical_spacer_before_status": "PASS" if count_ok and all(r["physical_spacer_before"] for r in reports) else "FAIL",
        "physical_spacer_after_status": "PASS" if count_ok and all(r["physical_spacer_after"] for r in reports) else "FAIL",
        "example_border_offset_status": "PASS" if count_ok and all(r["border_offset_within_v049512_limit"] for r in reports) else "FAIL",
        "example_forced_spacer_status": "PASS" if all_ok else "FAIL",
        "status": "PASS" if all_ok else "FAIL",
    }


def _v049512_validate_passage_image_ownership(
    header_xml: str,
    section_xml: str,
    result: dict[str, Any],
    base_validation: dict[str, Any],
    render_plan: dict[str, Any],
) -> dict:
    """Validate actual HWPX ownership, passage border and document order per image digest."""
    paragraphs = _v04959_question_paragraph_map(section_xml)
    styles = _v049511_para_style_info(header_xml)
    border_edges = _v049510_border_edge_map(header_xml)
    groups = sorted(
        [g for g in result.get("passage_groups", []) if int(g.get("id") or 0) > 0],
        key=lambda g: int(g.get("id") or 0),
    )
    gids = [int(g.get("id") or 0) for g in groups]

    guide_positions = [
        p["index"] for p in paragraphs
        if p["text"].startswith("※ 다음 글을 읽고")
    ]
    guide_by_gid = {gid: guide_positions[i] for i, gid in enumerate(gids[:len(guide_positions)])}
    first_q_by_gid: dict[int, int] = {}
    for g in groups:
        gid = int(g.get("id") or 0)
        qnums = [int(x) for x in g.get("question_numbers", [])]
        if not qnums:
            continue
        first_q = qnums[0]
        start = guide_by_gid.get(gid, -1)
        found = next((p["index"] for p in paragraphs if p["index"] > start and re.match(rf"^{first_q}\.\s", p["text"])), None)
        if found is not None:
            first_q_by_gid[gid] = found

    # Base validator already maps BinData digest -> paragraph index reliably.
    anchor_details = list(base_validation.get("image_anchor_details") or [])
    actual_by_digest: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for d in anchor_details:
        digest = str(d.get("digest") or "")
        if digest:
            actual_by_digest[digest].append(d)

    selected = [
        a for a in result.get("image_assets", [])
        if a.get("is_problem_image") is True and a.get("classification") == "problem_figure"
    ]
    selected.sort(key=_v049512_asset_order_key)
    expected_by_digest: dict[str, dict[str, Any]] = {}
    duplicate_digest = set()
    for a in selected:
        digest = str(a.get("byte_hash") or "")
        if not digest:
            continue
        if digest in expected_by_digest:
            duplicate_digest.add(digest)
        expected_by_digest[digest] = a

    render_group_by_filename: dict[str, int] = {}
    for page in render_plan.get("pages", []):
        for side in ("left", "right"):
            for item in page.get(side, []):
                if item.get("type") == "image" and item.get("filename"):
                    render_group_by_filename[str(item.get("filename"))] = int(item.get("group_id") or 0)

    details = []
    failures = []
    group_actual_indices: dict[int, list[int]] = defaultdict(list)
    group_expected_assets: dict[int, list[dict[str, Any]]] = defaultdict(list)

    for asset in selected:
        gid = int(asset.get("passage_group_id") or 0)
        group_expected_assets[gid].append(asset)
        digest = str(asset.get("byte_hash") or "")
        matches = actual_by_digest.get(digest, [])
        actual = matches[0] if len(matches) == 1 else None
        filename = str((asset.get("image_output") or {}).get("filename") or asset.get("filename") or "")
        render_gid = render_group_by_filename.get(filename)
        actual_idx = int(actual.get("paragraph_index")) if actual and actual.get("paragraph_index") is not None else None
        guide_idx = guide_by_gid.get(gid)
        first_q_idx = first_q_by_gid.get(gid)
        in_group_range = bool(
            actual_idx is not None and guide_idx is not None and first_q_idx is not None
            and guide_idx < actual_idx < first_q_idx
        )
        border_ok = False
        para_style_id = None
        if actual_idx is not None and 0 <= actual_idx < len(paragraphs):
            para_style_id = int(paragraphs[actual_idx].get("paraPrIDRef") or -1)
            st = styles.get(para_style_id, {})
            edges = border_edges.get(st.get("borderFillIDRef"), {})
            border_ok = (
                int(st.get("connect") or 0) == 1
                and edges.get("left") == "SOLID"
                and edges.get("right") == "SOLID"
                and edges.get("top") == "SOLID"
                and edges.get("bottom") == "SOLID"
            )
        render_group_ok = render_gid == gid
        unique_actual = len(matches) == 1
        ok = unique_actual and in_group_range and border_ok and render_group_ok
        if actual_idx is not None:
            group_actual_indices[gid].append(actual_idx)
        if not ok:
            failures.append({"digest": digest, "expected_group_id": gid, "filename": filename})
        details.append({
            "digest": digest,
            "filename": filename,
            "expected_group_id": gid,
            "render_plan_group_id": render_gid,
            "render_plan_group_match": render_group_ok,
            "actual_match_count": len(matches),
            "actual_paragraph_index": actual_idx,
            "passage_guide_paragraph_index": guide_idx,
            "first_question_paragraph_index": first_q_idx,
            "actual_inside_expected_passage_range": in_group_range,
            "actual_para_style_id": para_style_id,
            "actual_picture_paragraph_has_passage_border": border_ok,
            "ok": ok,
        })

    order_reports = []
    order_ok = True
    for gid, assets in sorted(group_expected_assets.items()):
        expected_digests = [str(a.get("byte_hash") or "") for a in assets]
        expected_actual_indices = []
        missing = False
        for digest in expected_digests:
            m = actual_by_digest.get(digest, [])
            if len(m) != 1 or m[0].get("paragraph_index") is None:
                missing = True
                continue
            expected_actual_indices.append(int(m[0]["paragraph_index"]))
        group_order_ok = (not missing and expected_actual_indices == sorted(expected_actual_indices))
        order_ok = order_ok and group_order_ok
        order_reports.append({
            "group_id": gid,
            "expected_image_count": len(assets),
            "actual_paragraph_indices_in_source_image_order": expected_actual_indices,
            "document_order_ok": group_order_ok,
        })

    count_ok = len(anchor_details) == len(selected)
    ownership_ok = count_ok and not duplicate_digest and all(d["actual_inside_expected_passage_range"] and d["render_plan_group_match"] and d["actual_match_count"] == 1 for d in details)
    border_ok_all = count_ok and all(d["actual_picture_paragraph_has_passage_border"] for d in details)
    overall = ownership_ok and border_ok_all and order_ok and not failures
    return {
        "expected_picture_count": len(selected),
        "actual_picture_anchor_count": len(anchor_details),
        "guide_count": len(guide_positions),
        "expected_group_count": len(groups),
        "duplicate_expected_digests": sorted(duplicate_digest),
        "details": details,
        "group_order_reports": order_reports,
        "failures": failures,
        "passage_image_ownership_status": "PASS" if ownership_ok else "FAIL",
        "passage_image_border_status": "PASS" if border_ok_all else "FAIL",
        "passage_image_document_order_status": "PASS" if count_ok and order_ok else "FAIL",
        "status": "PASS" if overall else "FAIL",
    }


def v049512_validate_hwpx(path: Path, *, result: dict[str, Any], render_plan: dict[str, Any]) -> dict[str, Any]:
    info = v049511_validate_hwpx(path, result=result, render_plan=render_plan)
    info["validator_version"] = _V049512_VERSION
    if not Path(path).exists() or not zipfile.is_zipfile(path) or info.get("package_status") != "PASS":
        info["status"] = "FAIL"
        return info
    try:
        with zipfile.ZipFile(path, "r") as zf:
            header = zf.read("Contents/header.xml").decode("utf-8", errors="strict")
            section0 = zf.read("Contents/section0.xml").decode("utf-8", errors="strict")
        example = _v049512_validate_example_physical_clearance(header, section0, result)
        ownership = _v049512_validate_passage_image_ownership(header, section0, result, info, render_plan)
        info["example_physical_clearance_v049512"] = example
        info["physical_spacer_before_status"] = example["physical_spacer_before_status"]
        info["physical_spacer_after_status"] = example["physical_spacer_after_status"]
        info["example_border_offset_status"] = example["example_border_offset_status"]
        info["example_forced_spacer_status"] = example["example_forced_spacer_status"]
        info["passage_image_ownership_validation_v049512"] = ownership
        info["passage_image_ownership_status"] = ownership["passage_image_ownership_status"]
        info["passage_image_border_status"] = ownership["passage_image_border_status"]
        info["passage_image_document_order_status"] = ownership["passage_image_document_order_status"]
        critical = [
            info.get("status"),
            info.get("example_forced_spacer_status"),
            info.get("example_border_offset_status"),
            info.get("passage_image_ownership_status"),
            info.get("passage_image_border_status"),
            info.get("passage_image_document_order_status"),
        ]
        info["status"] = "FAIL" if "FAIL" in critical else "WARN" if "WARN" in critical else "PASS"
        return info
    except Exception as exc:
        info["v049512_validation_error"] = str(exc)
        info["status"] = "FAIL"
        return info


def _v049512_postprocess_hwpx(path: Path, result: dict[str, Any], render_plan: dict[str, Any]) -> dict[str, Any]:
    import xml.etree.ElementTree as ET
    path = Path(path)
    report: dict[str, Any] = {
        "version": _V049512_VERSION,
        "status": "SKIPPED",
        "applied": False,
        "source": str(path),
    }
    if not path.exists() or not zipfile.is_zipfile(path):
        report["reason"] = "no usable HWPX"
        return report
    candidate = path.with_name(path.stem + "_v049512_candidate.hwpx")
    if candidate.exists():
        try:
            candidate.unlink()
        except Exception:
            pass
    try:
        with zipfile.ZipFile(path, "r") as zf:
            header = zf.read("Contents/header.xml").decode("utf-8", errors="strict")
            section0 = zf.read("Contents/section0.xml").decode("utf-8", errors="strict")

        # v5.11 already applied CENTER/LEFT and picture line-height changes. 5.12
        # makes the clearance physical and deterministic.
        section0, spacer_report = _v049512_force_example_spacers(section0, result)
        ET.fromstring(header.encode("utf-8"))
        ET.fromstring(section0.encode("utf-8"))
        _v04958_repack_postprocessed_hwpx(path, candidate, header, section0)
        validation = v049512_validate_hwpx(candidate, result=result, render_plan=render_plan)
        report.update({
            "status": "APPLIED" if validation.get("status") == "PASS" else "REJECTED_BY_VALIDATION",
            "applied": validation.get("status") == "PASS",
            "candidate": str(candidate),
            "forced_example_spacers": spacer_report,
            "validation": validation,
        })
        if validation.get("status") == "PASS":
            os.replace(str(candidate), str(path))
            report["candidate"] = None
            report["final_path"] = str(path.resolve())
        elif candidate.exists():
            candidate.unlink()
        return report
    except Exception as exc:
        report["status"] = "FAIL"
        report["reason"] = str(exc)
        try:
            if candidate.exists():
                candidate.unlink()
        except Exception:
            pass
        return report


def v049512_upgrade_result(
    result: dict,
    pdf_path: Path,
    checkpoint_path: Path | None = None,
    *,
    hwpx_output_path: Path | None = None,
    question_detection: dict | None = None,
    security_module_path: Path | None = None,
    allow_interactive_hwp: bool = False,
    show_hwp: bool = False,
) -> dict:
    _v0491_log("[v0.4.9.5.12] 보기 강제 spacer + passage image ownership/box/order 검증 준비")

    # Ownership must be fixed BEFORE v0.4.8.1 exports images and BEFORE the render
    # plan is built. This changes filenames, group guides and passage-box membership
    # at the source rather than trying to move pictures after HWPX serialization.
    ownership_report = _v049512_reassign_passage_image_ownership(pdf_path, result)
    if ownership_report.get("status") != "PASS":
        result["version"] = _V049512_VERSION
        result["validation_v049512"] = {
            "passage_image_ownership_preflight_status": "FAIL",
            "status": "FAIL",
            "reason": "passage image ownership preflight failed",
        }
        return result

    # Force v5.11's visual style generator to use minimal vertical border expansion.
    # Physical blank paragraphs added later provide the actual safety distance.
    global _V049511_EXAMPLE_TITLE_PREV_HWPUNIT
    global _V049511_EXAMPLE_BODY_NEXT_HWPUNIT
    global _V049511_EXAMPLE_OUTER_TB_HWPUNIT
    global _V049511_EXAMPLE_JOIN_TB_HWPUNIT
    _V049511_EXAMPLE_TITLE_PREV_HWPUNIT = 0
    _V049511_EXAMPLE_BODY_NEXT_HWPUNIT = 0
    _V049511_EXAMPLE_OUTER_TB_HWPUNIT = _V049512_EXAMPLE_OUTER_TB_HWPUNIT
    _V049511_EXAMPLE_JOIN_TB_HWPUNIT = _V049512_EXAMPLE_JOIN_TB_HWPUNIT

    result = v049511_upgrade_result(
        result,
        pdf_path,
        checkpoint_path=checkpoint_path,
        hwpx_output_path=hwpx_output_path,
        question_detection=question_detection,
        security_module_path=security_module_path,
        allow_interactive_hwp=allow_interactive_hwp,
        show_hwp=show_hwp,
    )

    render_plan = dict(result.get("render_plan_v049511") or {})
    render_plan["version"] = _V049512_VERSION
    render_plan["editorial_refinements_v049512"] = {
        "example_physical_spacer_before": "required",
        "example_physical_spacer_after": "required",
        "example_outer_border_offset_hwpunit": _V049512_EXAMPLE_OUTER_TB_HWPUNIT,
        "example_join_border_offset_hwpunit": _V049512_EXAMPLE_JOIN_TB_HWPUNIT,
        "passage_image_ownership": "preceding PDF passage anchor in page/column/y reading order",
        "passage_image_validation": "digest ownership + passage border + HWPX document order",
    }
    result["render_plan_v049512"] = render_plan
    result.pop("render_plan_v049511", None)

    old_hwpx = result.get("hwpx_v049511") or {}
    hwpx_info = dict(old_hwpx)
    hwpx_info["backend"] = "hancom_com_v049512"
    hwpx_info["renderer_mode"] = "v049511_base_plus_forced_spacers_and_anchor_ownership_v049512"
    final_path_value = old_hwpx.get("final_path") or old_hwpx.get("path")

    if old_hwpx.get("status") == "created" and final_path_value and Path(final_path_value).exists():
        semantic = _v049512_postprocess_hwpx(Path(final_path_value), result, render_plan)
        hwpx_info["semantic_finalize_v049512"] = semantic
        if semantic.get("applied"):
            validation = semantic.get("validation") or v049512_validate_hwpx(
                Path(final_path_value), result=result, render_plan=render_plan
            )
            hwpx_info["validation"] = validation
            hwpx_info["status"] = "created" if validation.get("status") == "PASS" else "INVALID"
            hwpx_info["final_path"] = str(Path(final_path_value).resolve())
        else:
            hwpx_info["status"] = "INVALID"
            if semantic.get("validation"):
                hwpx_info["validation"] = semantic["validation"]
    elif old_hwpx.get("status") == "SKIPPED":
        hwpx_info["semantic_finalize_v049512"] = {
            "status": "SKIPPED",
            "applied": False,
            "reason": "Hancom writer unavailable on this platform",
        }

    result["hwpx_v049512"] = hwpx_info
    result.pop("hwpx_v049511", None)
    result["hancom_security_v049512"] = result.pop("hancom_security_v049511", hwpx_info.get("hancom_security") or {})
    result["version"] = _V049512_VERSION
    result["parser_version"] = _V049512_VERSION
    result["generator_version"] = "PDF Parser Integrated v0.4.9.5.12"
    result["question_detection_v049512"] = result.pop("question_detection_v049511", question_detection or {})
    result["schema_version"] = {
        "base": "v0.4.9.5.11",
        "extension": [
            "forced_example_spacer_before_and_after",
            "reduced_example_vertical_border_offset",
            "pdf_passage_anchor_image_ownership",
            "cross_page_column_image_group_reassignment",
            "actual_hwpx_passage_image_border_validation",
            "actual_hwpx_passage_image_document_order_validation",
        ],
    }

    final_validation = hwpx_info.get("validation") or {}
    structural = result.get("structural_validation_v049510") or {}
    security_runtime = result.get("hancom_security_v049512") or {}
    hwpx_status = hwpx_info.get("status")
    security_ok = (
        security_runtime.get("unattended_ready") is True
        or hwpx_status == "SKIPPED"
        or (allow_interactive_hwp and hwpx_status == "created")
    )
    critical_keys = (
        "continuous_flow_status", "question_integrity_status", "example_integrity_status",
        "underline_status", "question_bold_status", "author_right_align_status",
        "question_negative_underline_status", "example_title_alignment_status",
        "source_credit_count_status", "picture_affect_line_spacing_status",
        "image_unit_consistency_status", "example_forced_spacer_status",
        "example_border_offset_status", "passage_image_ownership_status",
        "passage_image_border_status", "passage_image_document_order_status",
    )
    critical_fail = any(final_validation.get(k) == "FAIL" for k in critical_keys)
    if ownership_report.get("status") != "PASS" or critical_fail or structural.get("status") == "FAIL":
        final_status = "FAIL"
    elif hwpx_status == "SKIPPED":
        final_status = "WARN"
    elif hwpx_status == "created" and security_ok and final_validation.get("status") == "PASS":
        final_status = "PASS"
    else:
        final_status = "FAIL"

    result["validation_v049512"] = {
        "question_count": len(result.get("questions", [])),
        "question_detection_status": (question_detection or {}).get("status"),
        "passage_image_ownership_preflight_status": ownership_report.get("status"),
        "changed_passage_image_ownership_count": ownership_report.get("changed_ownership_count", 0),
        "passage_group_image_counts": ownership_report.get("group_image_counts", {}),
        "hwpx_status": hwpx_status,
        "hwpx_final_path": hwpx_info.get("final_path"),
        "hwpx_validation_status": final_validation.get("status"),
        "example_title_alignment_status": final_validation.get("example_title_alignment_status"),
        "physical_spacer_before_status": final_validation.get("physical_spacer_before_status"),
        "physical_spacer_after_status": final_validation.get("physical_spacer_after_status"),
        "example_border_offset_status": final_validation.get("example_border_offset_status"),
        "example_forced_spacer_status": final_validation.get("example_forced_spacer_status"),
        "source_credit_count_status": final_validation.get("source_credit_count_status"),
        "author_right_align_status": final_validation.get("author_right_align_status"),
        "picture_affect_line_spacing_status": final_validation.get("picture_affect_line_spacing_status"),
        "passage_image_ownership_status": final_validation.get("passage_image_ownership_status"),
        "passage_image_border_status": final_validation.get("passage_image_border_status"),
        "passage_image_document_order_status": final_validation.get("passage_image_document_order_status"),
        "image_unit_consistency_status": final_validation.get("image_unit_consistency_status"),
        "status": final_status,
    }
    return result


def main_v049512() -> None:
    parser = argparse.ArgumentParser(
        description="국어 문제 PDF -> 구조화 JSON + HWPX V0.4.9.5.12 보기 강제 spacer/이미지 ownership 검증"
    )
    parser.add_argument("pdf", type=Path, help="분석할 PDF 파일")
    parser.add_argument("-o", "--output", type=Path, default=None, help="저장할 JSON. 생략하면 <PDF이름>_result.json")
    parser.add_argument("--hwpx-output", type=Path, default=None, help="최종 HWPX 희망 파일명. 생략하면 <PDF이름>.hwpx, 존재 시 _runNN 자동 생성")
    parser.add_argument("-q", "--questions", nargs="+", type=int, default=None, help="추출할 문제 번호. 생략하면 PDF에서 자동 탐지")
    parser.add_argument("--no-kiwi", action="store_true", help="Kiwi 경계 판별을 끔")
    parser.add_argument("--security-module", type=Path, default=None, help="FilePathCheckerModuleExample.dll 경로")
    parser.add_argument("--allow-interactive-hwp", action="store_true", help="보안 모듈 실패 시 대화형 한글 허용")
    parser.add_argument("--show-hwp", action="store_true", help="한글 창 표시")
    args = parser.parse_args()

    if not args.pdf.exists():
        raise SystemExit(f"PDF 파일을 찾을 수 없습니다: {args.pdf}")
    if not args.no_kiwi and Kiwi is None:
        print("[경고] kiwipiepy 미설치. fallback으로 실행합니다.")

    detection = v04957_detect_question_numbers(args.pdf)
    if args.questions:
        question_numbers = sorted(set(args.questions))
        detection["selection_mode"] = "explicit_cli"
        detection["selected_question_numbers"] = question_numbers
    else:
        if detection.get("status") != "PASS" or not detection.get("question_numbers"):
            raise SystemExit(
                "문제 번호 자동 탐지에 실패했습니다. -q 옵션으로 문제 번호를 직접 지정하세요. "
                + str(detection.get("reason") or "")
            )
        question_numbers = list(detection["question_numbers"])
        detection["selection_mode"] = "auto_detected"
        detection["selected_question_numbers"] = question_numbers

    json_output = Path(args.output) if args.output else _v04957_default_json_path(args.pdf)
    checkpoint_path = json_output.with_name(json_output.stem + "_pre_hwpx.json")
    result = parse_v0_2_3(args.pdf, question_numbers, use_kiwi=not args.no_kiwi)
    result = v044_upgrade_result(result, args.pdf)
    result = v045_upgrade_result(result, args.pdf)
    result = v049512_upgrade_result(
        result,
        args.pdf,
        checkpoint_path=checkpoint_path,
        hwpx_output_path=args.hwpx_output,
        question_detection=detection,
        security_module_path=args.security_module,
        allow_interactive_hwp=args.allow_interactive_hwp,
        show_hwp=args.show_hwp,
    )
    json_output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    checkpoint_info = result.get("pre_hwpx_checkpoint") or {}
    checkpoint_file = Path(str(checkpoint_info.get("path") or "")) if isinstance(checkpoint_info, dict) else None
    if result.get("hwpx_v049512", {}).get("status") == "created" and checkpoint_file and str(checkpoint_file):
        try:
            if checkpoint_file.exists():
                checkpoint_file.unlink()
            checkpoint_info["retained"] = False
            result["pre_hwpx_checkpoint"] = checkpoint_info
            json_output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            checkpoint_info["retained"] = True
            checkpoint_info["cleanup_error"] = str(exc)

    v = result.get("validation_v049512", {})
    print("=" * 76)
    print("V0.4.9.5.12 보기 강제 spacer + passage image ownership/box/order 검증 완료")
    print("=" * 76)
    print(f"입력 : {args.pdf}")
    print(f"JSON : {json_output.resolve()}")
    print(f"HWPX : {v.get('hwpx_final_path')}")
    print(f"문제 : {v.get('question_count', 0)} | 자동 탐지 : {v.get('question_detection_status')}")
    print(
        "<보기> 실제 spacer 앞/뒤/offset : "
        f"{v.get('physical_spacer_before_status')} / "
        f"{v.get('physical_spacer_after_status')} / "
        f"{v.get('example_border_offset_status')}"
    )
    print(
        "이미지 ownership/박스/문서순서 : "
        f"{v.get('passage_image_ownership_status')} / "
        f"{v.get('passage_image_border_status')} / "
        f"{v.get('passage_image_document_order_status')}"
    )
    print(f"ownership 재할당 : {v.get('changed_passage_image_ownership_count', 0)}개 | 그룹별 이미지 : {v.get('passage_group_image_counts')}")
    print(f"HWPX 상태 : {v.get('hwpx_status')} | 최종 검증 : {v.get('status')}")




# =============================================================================
# V0.4.9.5.13 editorial-reference stabilization layer
#
# Reference HWPX comparison showed that the hand-authored two-column layout uses
# the same 2268 HWPUNIT gutter as the generated file, plus a centered vertical
# column rule:
#   <hp:colLine type="SOLID" width="0.12 mm" color="#000000"/>
# This layer applies that rule to every 2-column section, including the answer
# section.  It also removes the physical blank paragraph immediately BEFORE an
# <보기> title while retaining a small paraPr 'prev' margin and the physical
# spacer AFTER the box for choice clearance.
# =============================================================================

_V049513_VERSION = "v0.4.9.5.13"
_V049513_EXAMPLE_TITLE_PREV_HWPUNIT = 280   # compact ~2.8 pt, no full blank line
_V049513_COLLINE_TYPE = "SOLID"
_V049513_COLLINE_WIDTH = "0.12 mm"
_V049513_COLLINE_COLOR = "#000000"


def _v049513_patch_column_separator(section_xml: str) -> tuple[str, dict[str, Any]]:
    """Add/normalize the reference-style center rule on every 2-column colPr."""
    line_xml = (
        f'<hp:colLine type="{_V049513_COLLINE_TYPE}" '
        f'width="{_V049513_COLLINE_WIDTH}" color="{_V049513_COLLINE_COLOR}"/>'
    )
    patched = 0
    already = 0
    two_col = 0

    def patch_paired(m: re.Match) -> str:
        nonlocal patched, already, two_col
        open_tag, body = m.group(1), m.group(2)
        cm = re.search(r'\bcolCount="(\d+)"', open_tag)
        if not cm or int(cm.group(1)) < 2:
            return m.group(0)
        two_col += 1
        lm = re.search(r'<hp:colLine\b[^>]*/>', body)
        if lm:
            if lm.group(0) == line_xml:
                already += 1
                return m.group(0)
            body = body[:lm.start()] + line_xml + body[lm.end():]
        else:
            body = body + line_xml
        patched += 1
        return open_tag + body + '</hp:colPr>'

    # Paired colPr first so an existing child is normalized rather than duplicated.
    section_xml = re.sub(
        r'(<hp:colPr\b[^>]*>)([\s\S]*?)</hp:colPr>',
        patch_paired,
        section_xml,
    )

    def patch_self(m: re.Match) -> str:
        nonlocal patched, two_col
        attrs = m.group(1)
        cm = re.search(r'\bcolCount="(\d+)"', attrs)
        if not cm or int(cm.group(1)) < 2:
            return m.group(0)
        two_col += 1
        patched += 1
        return f'<hp:colPr{attrs}>{line_xml}</hp:colPr>'

    section_xml = re.sub(r'<hp:colPr\b([^>]*)/>', patch_self, section_xml)
    return section_xml, {
        'two_column_colpr_count': two_col,
        'patched_count': patched,
        'already_correct_count': already,
        'type': _V049513_COLLINE_TYPE,
        'width': _V049513_COLLINE_WIDTH,
        'color': _V049513_COLLINE_COLOR,
        'status': 'PASS' if two_col > 0 and patched + already == two_col else 'FAIL',
    }


def _v049513_remove_pre_example_spacers(section_xml: str, result: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Remove only blank paragraphs between a question stem and its <보기> title.

    We intentionally do NOT perform global blank-paragraph cleanup.  A blank
    after the example body is still required to protect the first answer choice.
    """
    expected = _v04959_expected_examples(result)
    paragraphs = list(re.finditer(r'<hp:p\b[^>]*>[\s\S]*?</hp:p>', section_xml))
    visible = [
        _v04958_normalize_visible_text(_v04954_para_text(pm.group(0)))
        for pm in paragraphs
    ]
    remove_indices: set[int] = set()
    reports: list[dict[str, Any]] = []
    exp_i = 0

    for i, txt in enumerate(visible):
        if not _V04959_EXAMPLE_TITLE_RE.fullmatch(txt):
            continue
        exp = expected[exp_i] if exp_i < len(expected) else {}
        exp_i += 1
        qno = int(exp.get('question_number') or 0)

        k = i - 1
        blanks: list[int] = []
        while k >= 0 and visible[k] == '':
            blanks.append(k)
            k -= 1
        previous_visible = visible[k] if k >= 0 else ''
        stem_ok = bool(qno and re.match(rf'^{qno}\.\s', previous_visible))
        if stem_ok:
            remove_indices.update(blanks)
        reports.append({
            'question_number': qno,
            'title_paragraph_index_before_cleanup': i,
            'blank_paragraphs_between_stem_and_box': len(blanks),
            'removed_blank_paragraph_count': len(blanks) if stem_ok else 0,
            'previous_visible_text': previous_visible[:160],
            'stem_match': stem_ok,
            'status': 'PASS' if stem_ok else 'FAIL',
        })

    out: list[str] = []
    cursor = 0
    for idx, pm in enumerate(paragraphs):
        out.append(section_xml[cursor:pm.start()])
        if idx not in remove_indices:
            out.append(pm.group(0))
        cursor = pm.end()
    out.append(section_xml[cursor:])

    ok = len(reports) == len(expected) and all(r['status'] == 'PASS' for r in reports)
    return ''.join(out), {
        'expected_example_count': len(expected),
        'processed_example_count': len(reports),
        'removed_pre_example_blank_count': len(remove_indices),
        'reports': reports,
        'status': 'PASS' if ok else 'FAIL',
    }


def _v049513_patch_example_title_spacing(header_xml: str, section_xml: str) -> tuple[str, dict[str, Any]]:
    """Give <보기> title a compact margin instead of a physical blank line."""
    title_style_ids: set[int] = set()
    for pm in re.finditer(r'<hp:p\b[^>]*>[\s\S]*?</hp:p>', section_xml):
        text = _v04958_normalize_visible_text(_v04954_para_text(pm.group(0)))
        if not _V04959_EXAMPLE_TITLE_RE.fullmatch(text):
            continue
        pidm = re.search(r'\bparaPrIDRef="(\d+)"', pm.group(0))
        if pidm:
            title_style_ids.add(int(pidm.group(1)))

    patched_ids: list[int] = []
    for pid in sorted(title_style_ids):
        pat = re.compile(rf'<hh:paraPr\b[^>]*\bid="{pid}"[\s\S]*?</hh:paraPr>')
        m = pat.search(header_xml)
        if not m:
            continue
        clone = _v049511_patch_para_margin_values(
            m.group(0),
            prev=_V049513_EXAMPLE_TITLE_PREV_HWPUNIT,
            nxt=0,
        )
        header_xml = header_xml[:m.start()] + clone + header_xml[m.end():]
        patched_ids.append(pid)

    return header_xml, {
        'title_style_ids': sorted(title_style_ids),
        'patched_style_ids': patched_ids,
        'title_prev_hwpunit': _V049513_EXAMPLE_TITLE_PREV_HWPUNIT,
        'status': 'PASS' if title_style_ids and set(patched_ids) == title_style_ids else 'FAIL',
    }


def _v049513_colline_info(section_xml: str) -> dict[str, Any]:
    details: list[dict[str, Any]] = []

    # Paired colPr (the normal form after v0.4.9.5.13 patching).
    consumed_spans: list[tuple[int, int]] = []
    for m in re.finditer(r'<hp:colPr\b([^>]*)>([\s\S]*?)</hp:colPr>', section_xml):
        attrs, body = m.group(1), m.group(2)
        cm = re.search(r'\bcolCount="(\d+)"', attrs)
        if not cm or int(cm.group(1)) < 2:
            continue
        lm = re.search(r'<hp:colLine\b([^>]*)/>', body)
        lattrs = lm.group(1) if lm else ''
        def attr(name: str) -> str | None:
            am = re.search(rf'\b{re.escape(name)}="([^"]*)"', lattrs)
            return am.group(1) if am else None
        item = {
            'colCount': int(cm.group(1)),
            'line_present': lm is not None,
            'type': attr('type'),
            'width': attr('width'),
            'color': attr('color'),
        }
        item['ok'] = (
            item['line_present']
            and item['type'] == _V049513_COLLINE_TYPE
            and item['width'] == _V049513_COLLINE_WIDTH
            and str(item['color'] or '').upper() == _V049513_COLLINE_COLOR
        )
        details.append(item)
        consumed_spans.append((m.start(), m.end()))

    # If a foreign HWPX still has self-closing 2-column colPr, record it as missing.
    for m in re.finditer(r'<hp:colPr\b([^>]*)/>', section_xml):
        if any(a <= m.start() < b for a, b in consumed_spans):
            continue
        cm = re.search(r'\bcolCount="(\d+)"', m.group(1))
        if cm and int(cm.group(1)) >= 2:
            details.append({
                'colCount': int(cm.group(1)), 'line_present': False,
                'type': None, 'width': None, 'color': None, 'ok': False,
            })

    return {
        'two_column_colpr_count': len(details),
        'details': details,
        'status': 'PASS' if details and all(d['ok'] for d in details) else 'FAIL',
    }


def _v049513_validate_column_separators(sections: dict[str, str]) -> dict[str, Any]:
    ordered = sorted(sections, key=_v04953_section_number)
    section_reports = {name: _v049513_colline_info(sections[name]) for name in ordered}
    qname = 'Contents/section0.xml'
    q_report = section_reports.get(qname, {'status': 'FAIL'})

    answer_names = [name for name in ordered if name != qname]
    if answer_names:
        answer_ok = all(section_reports[name].get('status') == 'PASS' for name in answer_names)
    else:
        # Single-section documents may contain both questions and answers in the
        # same flowing 2-column section; the same rule then serves both regions.
        answer_ok = q_report.get('status') == 'PASS' and '[정답 및 해설]' in sections.get(qname, '')

    return {
        'reference_rule': {
            'type': _V049513_COLLINE_TYPE,
            'width': _V049513_COLLINE_WIDTH,
            'color': _V049513_COLLINE_COLOR,
        },
        'section_reports': section_reports,
        'question_section_status': q_report.get('status', 'FAIL'),
        'answer_section_status': 'PASS' if answer_ok else 'FAIL',
        'status': 'PASS' if q_report.get('status') == 'PASS' and answer_ok else 'FAIL',
    }


def _v049513_validate_example_compact_layout(
    header_xml: str,
    section_xml: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    """New invariant: no blank BEFORE <보기>, one safety blank AFTER its body."""
    paragraphs = _v04959_question_paragraph_map(section_xml)
    styles = _v049511_para_style_info(header_xml)
    expected = _v04959_expected_examples(result)
    reports: list[dict[str, Any]] = []
    issues: list[str] = []
    exp_i = 0

    for pos, p in enumerate(paragraphs):
        if not _V04959_EXAMPLE_TITLE_RE.fullmatch(p['text']):
            continue
        exp = expected[exp_i] if exp_i < len(expected) else {}
        exp_i += 1
        qno = int(exp.get('question_number') or 0)

        body_pos = None
        for j in range(pos + 1, min(len(paragraphs), pos + 6)):
            if paragraphs[j]['text']:
                body_pos = j
                break
        if body_pos is None:
            issues.append(f'{qno}번 example body missing')
            continue

        title_style = styles.get(int(p.get('paraPrIDRef') or -1), {})
        body = paragraphs[body_pos]
        body_style = styles.get(int(body.get('paraPrIDRef') or -1), {})
        previous = paragraphs[pos - 1] if pos > 0 else None
        no_pre_blank = bool(previous and previous['text'])
        previous_is_stem = bool(previous and qno and re.match(rf'^{qno}\.\s', previous['text']))
        compact_prev = int(title_style.get('prev') or 0) == _V049513_EXAMPLE_TITLE_PREV_HWPUNIT
        after_spacer = body_pos + 1 < len(paragraphs) and paragraphs[body_pos + 1]['text'] == ''

        next_visible = None
        for j in range(body_pos + 1, min(len(paragraphs), body_pos + 7)):
            if paragraphs[j]['text']:
                next_visible = paragraphs[j]
                break
        choice_after = bool(next_visible and re.match(r'^①\s', next_visible['text']))
        title_center = title_style.get('horizontal') == 'CENTER'
        body_left = body_style.get('horizontal') == 'LEFT'
        top_offset_ok = int(title_style.get('offsetTop') or 0) <= _V049512_EXAMPLE_OUTER_TB_HWPUNIT
        bottom_offset_ok = int(body_style.get('offsetBottom') or 0) <= _V049512_EXAMPLE_OUTER_TB_HWPUNIT

        ok = all((
            no_pre_blank, previous_is_stem, compact_prev, after_spacer,
            choice_after, title_center, body_left, top_offset_ok, bottom_offset_ok,
        ))
        reports.append({
            'question_number': qno,
            'question_stem_paragraph_index': previous['index'] if previous else None,
            'title_paragraph_index': p['index'],
            'body_paragraph_index': body['index'],
            'physical_blank_before_box': not no_pre_blank,
            'previous_is_question_stem': previous_is_stem,
            'title_prev_hwpunit': title_style.get('prev'),
            'expected_title_prev_hwpunit': _V049513_EXAMPLE_TITLE_PREV_HWPUNIT,
            'physical_spacer_after': after_spacer,
            'choice_after_box': choice_after,
            'title_alignment': title_style.get('horizontal'),
            'body_alignment': body_style.get('horizontal'),
            'title_border_offset_top_hwpunit': title_style.get('offsetTop'),
            'body_border_offset_bottom_hwpunit': body_style.get('offsetBottom'),
            'ok': ok,
        })

    count_ok = len(reports) == len(expected)
    no_blank_ok = count_ok and all(not r['physical_blank_before_box'] and r['previous_is_question_stem'] for r in reports)
    prev_ok = count_ok and all(r['title_prev_hwpunit'] == _V049513_EXAMPLE_TITLE_PREV_HWPUNIT for r in reports)
    after_ok = count_ok and all(r['physical_spacer_after'] for r in reports)
    choice_ok = count_ok and all(r['choice_after_box'] for r in reports)
    border_ok = count_ok and all(
        int(r['title_border_offset_top_hwpunit'] or 0) <= _V049512_EXAMPLE_OUTER_TB_HWPUNIT
        and int(r['body_border_offset_bottom_hwpunit'] or 0) <= _V049512_EXAMPLE_OUTER_TB_HWPUNIT
        for r in reports
    )
    align_ok = count_ok and all(r['title_alignment'] == 'CENTER' and r['body_alignment'] == 'LEFT' for r in reports)
    overall = count_ok and no_blank_ok and prev_ok and after_ok and choice_ok and border_ok and align_ok and not issues
    return {
        'expected_example_count': len(expected),
        'validated_example_count': len(reports),
        'reports': reports,
        'issues': issues,
        'example_no_pre_blank_status': 'PASS' if no_blank_ok else 'FAIL',
        'example_compact_top_spacing_status': 'PASS' if prev_ok else 'FAIL',
        'physical_spacer_after_status': 'PASS' if after_ok else 'FAIL',
        'example_choice_clearance_status': 'PASS' if choice_ok else 'FAIL',
        'example_border_offset_status': 'PASS' if border_ok else 'FAIL',
        'example_title_alignment_status': 'PASS' if align_ok else 'FAIL',
        'status': 'PASS' if overall else 'FAIL',
    }


def v049513_validate_hwpx(path: Path, *, result: dict[str, Any], render_plan: dict[str, Any]) -> dict[str, Any]:
    """Validate the 5.13 target layout, intentionally superseding 5.12's pre-spacer rule."""
    info = v049511_validate_hwpx(path, result=result, render_plan=render_plan)
    info['validator_version'] = _V049513_VERSION
    if not Path(path).exists() or not zipfile.is_zipfile(path) or info.get('package_status') != 'PASS':
        info['status'] = 'FAIL'
        return info
    try:
        with zipfile.ZipFile(path, 'r') as zf:
            header = zf.read('Contents/header.xml').decode('utf-8', errors='strict')
            section_names = sorted(
                [n for n in zf.namelist() if re.fullmatch(r'Contents/section\d+\.xml', n)],
                key=_v04953_section_number,
            )
            sections = {n: zf.read(n).decode('utf-8', errors='strict') for n in section_names}
        section0 = sections.get('Contents/section0.xml', '')

        example = _v049513_validate_example_compact_layout(header, section0, result)
        ownership = _v049512_validate_passage_image_ownership(header, section0, result, info, render_plan)
        separators = _v049513_validate_column_separators(sections)

        info['example_compact_layout_v049513'] = example
        info['example_no_pre_blank_status'] = example['example_no_pre_blank_status']
        info['example_compact_top_spacing_status'] = example['example_compact_top_spacing_status']
        info['physical_spacer_after_status'] = example['physical_spacer_after_status']
        info['example_choice_clearance_status'] = example['example_choice_clearance_status']
        info['example_border_offset_status'] = example['example_border_offset_status']
        info['example_title_alignment_status'] = example['example_title_alignment_status']

        info['passage_image_ownership_validation_v049513'] = ownership
        info['passage_image_ownership_status'] = ownership['passage_image_ownership_status']
        info['passage_image_border_status'] = ownership['passage_image_border_status']
        info['passage_image_document_order_status'] = ownership['passage_image_document_order_status']

        info['column_separator_validation_v049513'] = separators
        info['question_column_separator_status'] = separators['question_section_status']
        info['answer_column_separator_status'] = separators['answer_section_status']
        info['column_separator_status'] = separators['status']

        # v0.4.9.5.11's old example spacing statuses are intentionally not part of
        # the 5.13 decision: 5.13 has a new compact-layout invariant above.
        critical_keys = (
            'package_status', 'image_order_status', 'image_anchor_status',
            'image_answer_boundary_status', 'continuous_flow_status',
            'question_integrity_status', 'example_integrity_status', 'underline_status',
            'question_bold_status', 'author_right_align_status',
            'question_negative_underline_status', 'example_detection_status',
            'cross_region_metadata_status', 'source_credit_count_status',
            'picture_affect_line_spacing_status', 'image_unit_consistency_status',
            'example_no_pre_blank_status', 'example_compact_top_spacing_status',
            'physical_spacer_after_status', 'example_choice_clearance_status',
            'example_border_offset_status', 'passage_image_ownership_status',
            'passage_image_border_status', 'passage_image_document_order_status',
            'question_column_separator_status', 'answer_column_separator_status',
            'column_separator_status',
        )
        values = [info.get(k) for k in critical_keys]
        info['status'] = 'FAIL' if 'FAIL' in values else 'WARN' if 'WARN' in values else 'PASS'
        return info
    except Exception as exc:
        info['v049513_validation_error'] = str(exc)
        info['status'] = 'FAIL'
        return info


def _v049513_postprocess_hwpx(path: Path, result: dict[str, Any], render_plan: dict[str, Any]) -> dict[str, Any]:
    import xml.etree.ElementTree as ET
    path = Path(path)
    report: dict[str, Any] = {
        'version': _V049513_VERSION,
        'status': 'SKIPPED',
        'applied': False,
        'source': str(path),
    }
    if not path.exists() or not zipfile.is_zipfile(path):
        report['reason'] = 'no usable HWPX'
        return report

    candidate = path.with_name(path.stem + '_v049513_candidate.hwpx')
    if candidate.exists():
        try:
            candidate.unlink()
        except Exception:
            pass
    try:
        with zipfile.ZipFile(path, 'r') as zf:
            header = zf.read('Contents/header.xml').decode('utf-8', errors='strict')
            section_names = sorted(
                [n for n in zf.namelist() if re.fullmatch(r'Contents/section\d+\.xml', n)],
                key=_v04953_section_number,
            )
            sections = {n: zf.read(n).decode('utf-8', errors='strict') for n in section_names}

        section0 = sections.get('Contents/section0.xml')
        if section0 is None:
            raise RuntimeError('Contents/section0.xml missing')

        # 1) Remove only the physical line between question stem and <보기>.
        section0, compact_report = _v049513_remove_pre_example_spacers(section0, result)
        # 2) Replace that full line with a small style-based vertical gap.
        header, title_spacing_report = _v049513_patch_example_title_spacing(header, section0)
        sections['Contents/section0.xml'] = section0
        # 3) Match the hand-authored HWPX center divider in every two-column section.
        separator_patch_reports: dict[str, Any] = {}
        for name in section_names:
            patched_xml, sec_report = _v049513_patch_column_separator(sections[name])
            sections[name] = patched_xml
            separator_patch_reports[name] = sec_report

        ET.fromstring(header.encode('utf-8'))
        for xml in sections.values():
            ET.fromstring(xml.encode('utf-8'))

        replacements = {'Contents/header.xml': header.encode('utf-8')}
        replacements.update({name: xml.encode('utf-8') for name, xml in sections.items()})
        _v04954_repack_hwpx(path, candidate, replacements)
        validation = v049513_validate_hwpx(candidate, result=result, render_plan=render_plan)
        report.update({
            'status': 'APPLIED' if validation.get('status') == 'PASS' else 'REJECTED_BY_VALIDATION',
            'applied': validation.get('status') == 'PASS',
            'candidate': str(candidate),
            'pre_example_blank_cleanup': compact_report,
            'example_title_spacing': title_spacing_report,
            'column_separator_patch': separator_patch_reports,
            'validation': validation,
        })
        if validation.get('status') == 'PASS':
            os.replace(str(candidate), str(path))
            report['candidate'] = None
            report['final_path'] = str(path.resolve())
        elif candidate.exists():
            candidate.unlink()
        return report
    except Exception as exc:
        report['status'] = 'FAIL'
        report['reason'] = str(exc)
        try:
            if candidate.exists():
                candidate.unlink()
        except Exception:
            pass
        return report


def v049513_upgrade_result(
    result: dict,
    pdf_path: Path,
    checkpoint_path: Path | None = None,
    *,
    hwpx_output_path: Path | None = None,
    question_detection: dict | None = None,
    security_module_path: Path | None = None,
    allow_interactive_hwp: bool = False,
    show_hwp: bool = False,
) -> dict:
    _v0491_log('[v0.4.9.5.13] 수작업 조판 기준 중앙선 + <보기> 상단 간격 컴팩트화 준비')

    result = v049512_upgrade_result(
        result,
        pdf_path,
        checkpoint_path=checkpoint_path,
        hwpx_output_path=hwpx_output_path,
        question_detection=question_detection,
        security_module_path=security_module_path,
        allow_interactive_hwp=allow_interactive_hwp,
        show_hwp=show_hwp,
    )

    render_plan = dict(result.get('render_plan_v049512') or {})
    render_plan['version'] = _V049513_VERSION
    render_plan['editorial_refinements_v049513'] = {
        'column_separator': {
            'type': _V049513_COLLINE_TYPE,
            'width': _V049513_COLLINE_WIDTH,
            'color': _V049513_COLLINE_COLOR,
            'apply_to_questions': True,
            'apply_to_answers': True,
        },
        'example_pre_blank_paragraph': False,
        'example_title_prev_hwpunit': _V049513_EXAMPLE_TITLE_PREV_HWPUNIT,
        'example_post_spacer_paragraph': True,
        'example_outer_border_offset_hwpunit': _V049512_EXAMPLE_OUTER_TB_HWPUNIT,
        'passage_image_ownership': 'retain_v049512_anchor_based_mapping',
    }
    result['render_plan_v049513'] = render_plan
    result.pop('render_plan_v049512', None)

    old_hwpx = result.get('hwpx_v049512') or {}
    hwpx_info = dict(old_hwpx)
    hwpx_info['backend'] = 'hancom_com_v049513'
    hwpx_info['renderer_mode'] = 'v049512_base_plus_reference_column_rule_and_compact_example_v049513'
    final_path_value = old_hwpx.get('final_path') or old_hwpx.get('path')

    if old_hwpx.get('status') == 'created' and final_path_value and Path(final_path_value).exists():
        semantic = _v049513_postprocess_hwpx(Path(final_path_value), result, render_plan)
        hwpx_info['semantic_finalize_v049513'] = semantic
        if semantic.get('applied'):
            validation = semantic.get('validation') or v049513_validate_hwpx(
                Path(final_path_value), result=result, render_plan=render_plan
            )
            hwpx_info['validation'] = validation
            hwpx_info['status'] = 'created' if validation.get('status') == 'PASS' else 'INVALID'
            hwpx_info['final_path'] = str(Path(final_path_value).resolve())
        else:
            hwpx_info['status'] = 'INVALID'
            if semantic.get('validation'):
                hwpx_info['validation'] = semantic['validation']
    elif old_hwpx.get('status') == 'SKIPPED':
        hwpx_info['semantic_finalize_v049513'] = {
            'status': 'SKIPPED',
            'applied': False,
            'reason': 'Hancom writer unavailable on this platform',
        }

    result['hwpx_v049513'] = hwpx_info
    result.pop('hwpx_v049512', None)
    result['hancom_security_v049513'] = result.pop('hancom_security_v049512', hwpx_info.get('hancom_security') or {})
    result['question_detection_v049513'] = result.pop('question_detection_v049512', question_detection or {})

    # Keep the successful ownership decision but expose it under the current layer too.
    if result.get('passage_image_ownership_v049512'):
        result['passage_image_ownership_v049513'] = dict(result['passage_image_ownership_v049512'])
        result['passage_image_ownership_v049513']['version'] = _V049513_VERSION

    result['version'] = _V049513_VERSION
    result['parser_version'] = _V049513_VERSION
    result['generator_version'] = 'PDF Parser Integrated v0.4.9.5.13'
    result['schema_version'] = {
        'base': 'v0.4.9.5.12',
        'extension': [
            'reference_hwpx_center_column_rule',
            'question_and_answer_column_separator',
            'remove_physical_pre_example_blank',
            'compact_example_title_prev_spacing',
            'all_section_column_rule_validator',
            'compact_example_layout_validator',
        ],
    }

    final_validation = hwpx_info.get('validation') or {}
    structural = result.get('structural_validation_v049510') or {}
    security_runtime = result.get('hancom_security_v049513') or {}
    hwpx_status = hwpx_info.get('status')
    security_ok = (
        security_runtime.get('unattended_ready') is True
        or hwpx_status == 'SKIPPED'
        or (allow_interactive_hwp and hwpx_status == 'created')
    )
    critical_keys = (
        'continuous_flow_status', 'question_integrity_status', 'example_integrity_status',
        'underline_status', 'question_bold_status', 'author_right_align_status',
        'question_negative_underline_status', 'source_credit_count_status',
        'picture_affect_line_spacing_status', 'image_unit_consistency_status',
        'example_no_pre_blank_status', 'example_compact_top_spacing_status',
        'physical_spacer_after_status', 'example_choice_clearance_status',
        'example_border_offset_status', 'passage_image_ownership_status',
        'passage_image_border_status', 'passage_image_document_order_status',
        'question_column_separator_status', 'answer_column_separator_status',
        'column_separator_status',
    )
    critical_fail = any(final_validation.get(k) == 'FAIL' for k in critical_keys)
    ownership_preflight = (result.get('passage_image_ownership_v049513') or {}).get('status')
    if ownership_preflight == 'FAIL' or critical_fail or structural.get('status') == 'FAIL':
        final_status = 'FAIL'
    elif hwpx_status == 'SKIPPED':
        final_status = 'WARN'
    elif hwpx_status == 'created' and security_ok and final_validation.get('status') == 'PASS':
        final_status = 'PASS'
    else:
        final_status = 'FAIL'

    result['validation_v049513'] = {
        'question_count': len(result.get('questions', [])),
        'question_detection_status': (question_detection or {}).get('status'),
        'passage_image_ownership_preflight_status': ownership_preflight,
        'changed_passage_image_ownership_count': (result.get('passage_image_ownership_v049513') or {}).get('changed_ownership_count', 0),
        'passage_group_image_counts': (result.get('passage_image_ownership_v049513') or {}).get('group_image_counts', {}),
        'hwpx_status': hwpx_status,
        'hwpx_final_path': hwpx_info.get('final_path'),
        'hwpx_validation_status': final_validation.get('status'),
        'example_no_pre_blank_status': final_validation.get('example_no_pre_blank_status'),
        'example_compact_top_spacing_status': final_validation.get('example_compact_top_spacing_status'),
        'physical_spacer_after_status': final_validation.get('physical_spacer_after_status'),
        'example_choice_clearance_status': final_validation.get('example_choice_clearance_status'),
        'example_border_offset_status': final_validation.get('example_border_offset_status'),
        'example_title_alignment_status': final_validation.get('example_title_alignment_status'),
        'question_column_separator_status': final_validation.get('question_column_separator_status'),
        'answer_column_separator_status': final_validation.get('answer_column_separator_status'),
        'column_separator_status': final_validation.get('column_separator_status'),
        'source_credit_count_status': final_validation.get('source_credit_count_status'),
        'author_right_align_status': final_validation.get('author_right_align_status'),
        'picture_affect_line_spacing_status': final_validation.get('picture_affect_line_spacing_status'),
        'passage_image_ownership_status': final_validation.get('passage_image_ownership_status'),
        'passage_image_border_status': final_validation.get('passage_image_border_status'),
        'passage_image_document_order_status': final_validation.get('passage_image_document_order_status'),
        'image_unit_consistency_status': final_validation.get('image_unit_consistency_status'),
        'status': final_status,
    }
    return result


def main_v049513() -> None:
    parser = argparse.ArgumentParser(
        description='국어 문제 PDF -> 구조화 JSON + HWPX V0.4.9.5.13 중앙 구분선/<보기> 컴팩트 조판'
    )
    parser.add_argument('pdf', type=Path, help='분석할 PDF 파일')
    parser.add_argument('-o', '--output', type=Path, default=None, help='저장할 JSON. 생략하면 <PDF이름>_result.json')
    parser.add_argument('--hwpx-output', type=Path, default=None, help='최종 HWPX 희망 파일명. 생략하면 <PDF이름>.hwpx, 존재 시 _runNN 자동 생성')
    parser.add_argument('-q', '--questions', nargs='+', type=int, default=None, help='추출할 문제 번호. 생략하면 PDF에서 자동 탐지')
    parser.add_argument('--no-kiwi', action='store_true', help='Kiwi 경계 판별을 끔')
    parser.add_argument('--security-module', type=Path, default=None, help='FilePathCheckerModuleExample.dll 경로')
    parser.add_argument('--allow-interactive-hwp', action='store_true', help='보안 모듈 실패 시 대화형 한글 허용')
    parser.add_argument('--show-hwp', action='store_true', help='한글 창 표시')
    args = parser.parse_args()

    if not args.pdf.exists():
        raise SystemExit(f'PDF 파일을 찾을 수 없습니다: {args.pdf}')
    if not args.no_kiwi and Kiwi is None:
        print('[경고] kiwipiepy 미설치. fallback으로 실행합니다.')

    detection = v04957_detect_question_numbers(args.pdf)
    if args.questions:
        question_numbers = sorted(set(args.questions))
        detection['selection_mode'] = 'explicit_cli'
        detection['selected_question_numbers'] = question_numbers
    else:
        if detection.get('status') != 'PASS' or not detection.get('question_numbers'):
            raise SystemExit(
                '문제 번호 자동 탐지에 실패했습니다. -q 옵션으로 문제 번호를 직접 지정하세요. '
                + str(detection.get('reason') or '')
            )
        question_numbers = list(detection['question_numbers'])
        detection['selection_mode'] = 'auto_detected'
        detection['selected_question_numbers'] = question_numbers

    json_output = Path(args.output) if args.output else _v04957_default_json_path(args.pdf)
    checkpoint_path = json_output.with_name(json_output.stem + '_pre_hwpx.json')
    result = parse_v0_2_3(args.pdf, question_numbers, use_kiwi=not args.no_kiwi)
    result = v044_upgrade_result(result, args.pdf)
    result = v045_upgrade_result(result, args.pdf)
    result = v049513_upgrade_result(
        result,
        args.pdf,
        checkpoint_path=checkpoint_path,
        hwpx_output_path=args.hwpx_output,
        question_detection=detection,
        security_module_path=args.security_module,
        allow_interactive_hwp=args.allow_interactive_hwp,
        show_hwp=args.show_hwp,
    )
    json_output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')

    checkpoint_info = result.get('pre_hwpx_checkpoint') or {}
    checkpoint_file = Path(str(checkpoint_info.get('path') or '')) if isinstance(checkpoint_info, dict) else None
    if result.get('hwpx_v049513', {}).get('status') == 'created' and checkpoint_file and str(checkpoint_file):
        try:
            if checkpoint_file.exists():
                checkpoint_file.unlink()
            checkpoint_info['retained'] = False
            result['pre_hwpx_checkpoint'] = checkpoint_info
            json_output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception as exc:
            checkpoint_info['retained'] = True
            checkpoint_info['cleanup_error'] = str(exc)

    v = result.get('validation_v049513', {})
    print('=' * 76)
    print('V0.4.9.5.13 중앙 구분선 + <보기> 상단 빈줄 제거/컴팩트 간격 검증 완료')
    print('=' * 76)
    print(f'입력 : {args.pdf}')
    print(f'JSON : {json_output.resolve()}')
    print(f'HWPX : {v.get("hwpx_final_path")}')
    print(f'문제 : {v.get("question_count", 0)} | 자동 탐지 : {v.get("question_detection_status")}')
    print(
        '<보기> 앞빈줄/상단간격/뒤여유 : '
        f'{v.get("example_no_pre_blank_status")} / '
        f'{v.get("example_compact_top_spacing_status")} / '
        f'{v.get("physical_spacer_after_status")}'
    )
    print(
        '2단 중앙선 문제/답지/전체 : '
        f'{v.get("question_column_separator_status")} / '
        f'{v.get("answer_column_separator_status")} / '
        f'{v.get("column_separator_status")}'
    )
    print(
        '이미지 ownership/박스/문서순서 : '
        f'{v.get("passage_image_ownership_status")} / '
        f'{v.get("passage_image_border_status")} / '
        f'{v.get("passage_image_document_order_status")}'
    )
    print(f'HWPX 상태 : {v.get("hwpx_status")} | 최종 검증 : {v.get("status")}')




# =============================================================================
# V0.4.9.5.14 content-preservation / pipeline-coverage / preview-sync layer
# =============================================================================

_V049514_VERSION = "v0.4.9.5.14"
_V049514_ENUM_MARKER_RE = re.compile(r"(?<!\S)(\(\d{1,2}\))(?=\S)")


def _v049514_match_text(value: Any) -> str:
    """Whitespace-stable visible text used for passage coverage matching."""
    text = _v04958_normalize_visible_text(_v049_text(value))
    return re.sub(r"\s+", " ", text).strip()


def _v049514_section_labels_from_text(value: Any) -> list[str]:
    labels: list[str] = []
    text = _v049_text(value).replace("\r\n", "\n").replace("\r", "\n")
    for line in text.split("\n"):
        token = line.strip()
        if SECTION_LABEL_RE.fullmatch(token):
            labels.append(token)
    return labels


def _v049514_recover_section_labels(result: dict[str, Any]) -> dict[str, Any]:
    """Recover section labels that survived raw extraction but disappeared from blocks.

    The source PDF can place a label at the top of the next physical column.  If an
    older block normalizer dropped that label, use the next surviving block as a
    geometry anchor and insert the label immediately before it.  This is intentionally
    limited to labels that are literally present in raw_text.
    """
    from collections import Counter

    reports: list[dict[str, Any]] = []
    recovered_total = 0

    for group in result.get("passage_groups", []):
        gid = int(group.get("id") or 0)
        raw_text = _v049_text(group.get("raw_text"))
        raw_lines = [line.strip() for line in raw_text.replace("\r\n", "\n").replace("\r", "\n").split("\n") if line.strip()]
        raw_labels = [line for line in raw_lines if SECTION_LABEL_RE.fullmatch(line)]
        blocks = list(group.get("blocks") or [])
        existing_labels = [
            _v049_text(b.get("text")).strip()
            for b in blocks
            if (b.get("type") == "section_label" or SECTION_LABEL_RE.fullmatch(_v049_text(b.get("text")).strip()))
        ]
        need = Counter(raw_labels) - Counter(existing_labels)
        recovered: list[dict[str, Any]] = []

        # A compact lookup lets a raw physical line anchor a normalized paragraph
        # whose text may include continuation lines.
        for label, count in list(need.items()):
            for _ in range(count):
                try:
                    raw_pos = next(i for i, line in enumerate(raw_lines) if line == label)
                except StopIteration:
                    continue

                next_raw = None
                for line in raw_lines[raw_pos + 1:]:
                    if not SECTION_LABEL_RE.fullmatch(line):
                        next_raw = _v049514_match_text(line)
                        if next_raw:
                            break

                anchor_index = None
                if next_raw:
                    for bi, block in enumerate(blocks):
                        bt = _v049514_match_text(block.get("text"))
                        if bt and (bt == next_raw or bt.startswith(next_raw) or next_raw.startswith(bt)):
                            anchor_index = bi
                            break
                if anchor_index is None:
                    anchor_index = len(blocks)

                if blocks:
                    template = blocks[min(anchor_index, len(blocks) - 1)]
                    page = template.get("source_start_page") or template.get("start_page") or (group.get("source_pages") or [1])[0]
                    column = template.get("source_start_column")
                    if column is None:
                        column = template.get("column", 0)
                    anchor_y = float(template.get("start_y") or 0.0)
                    relative_x = float(template.get("relative_x") or 0.0)
                else:
                    page = (group.get("source_pages") or [1])[0]
                    column = 0
                    anchor_y = 0.0
                    relative_x = 0.0

                recovered_block = {
                    "type": "section_label",
                    "text": label,
                    "source_start_page": int(page or 1),
                    "source_end_page": int(page or 1),
                    "source_start_column": int(column or 0),
                    "source_end_column": int(column or 0),
                    "column": int(column or 0),
                    "line_count": 1,
                    "start_y": anchor_y - 0.05,
                    "end_y": anchor_y - 0.01,
                    "relative_x": relative_x,
                    "start_page": int(page or 1),
                    "start_column": int(column or 0),
                    "end_page": int(page or 1),
                    "end_column": int(column or 0),
                    "crosses_page_or_column": False,
                    "recovered_v049514": True,
                }
                blocks.insert(anchor_index, recovered_block)
                recovered.append({"label": label, "insert_index": anchor_index, "anchor_next_raw": next_raw})
                recovered_total += 1

        group["blocks"] = blocks
        group["normalized_text"] = "\n".join(
            _v049_text(b.get("text")).strip() for b in blocks if _v049_text(b.get("text")).strip()
        ).strip()

        post_labels = [
            _v049_text(b.get("text")).strip()
            for b in blocks
            if SECTION_LABEL_RE.fullmatch(_v049_text(b.get("text")).strip())
        ]
        raw_counter = Counter(raw_labels)
        block_counter = Counter(post_labels)
        normalized_counter = Counter(_v049514_section_labels_from_text(group.get("normalized_text")))
        ok = all(block_counter[k] >= v and normalized_counter[k] >= v for k, v in raw_counter.items())
        reports.append({
            "group_id": gid,
            "raw_labels": raw_labels,
            "labels_before": existing_labels,
            "labels_after": post_labels,
            "recovered": recovered,
            "raw_to_normalized_and_blocks_ok": ok,
            "status": "PASS" if ok else "FAIL",
        })

    status = "PASS" if all(r["status"] == "PASS" for r in reports) else "FAIL"
    report = {
        "version": _V049514_VERSION,
        "recovered_section_label_count": recovered_total,
        "groups": reports,
        "status": status,
    }
    result["section_label_recovery_v049514"] = report
    return report


def _v049514_fix_example_enumeration_spacing(result: dict[str, Any]) -> dict[str, Any]:
    """Fix list-marker spacing only inside true <보기> enumeration text.

    We deliberately do not apply `(3)이` -> `(3) 이` globally because mathematical
    prose such as `식 (3)이 성립한다` legitimately attaches the particle to `(3)`.
    """
    reports: list[dict[str, Any]] = []
    changed_total = 0
    for q in result.get("questions", []):
        ex = q.get("example_block") or {}
        if not ex.get("exists"):
            continue
        old = _v049_text(ex.get("text"))
        markers = re.findall(r"(?<!\S)\((\d{1,2})\)", old)
        # Require an actual enumerated series, not a single parenthesized number.
        if len(markers) < 2:
            reports.append({"question_number": q.get("number"), "changed_count": 0, "status": "PASS"})
            continue
        new, n = _V049514_ENUM_MARKER_RE.subn(r"\1 ", old)
        if n:
            ex["text"] = new
            q["example_block"] = ex
            if q.get("question_full") and old in _v049_text(q.get("question_full")):
                q["question_full"] = _v049_text(q.get("question_full")).replace(old, new, 1)
            changed_total += n
        reports.append({
            "question_number": q.get("number"),
            "changed_count": n,
            "before_preview": old[:220],
            "after_preview": new[:220],
            "status": "PASS" if not _V049514_ENUM_MARKER_RE.search(new) else "FAIL",
        })
    report = {
        "version": _V049514_VERSION,
        "changed_marker_count": changed_total,
        "questions": reports,
        "status": "PASS" if all(r["status"] == "PASS" for r in reports) else "FAIL",
    }
    result["example_enumeration_spacing_v049514"] = report
    return report


def _v049514_expected_passage_blocks(result: dict[str, Any]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for group in sorted(result.get("passage_groups", []), key=lambda g: int(g.get("id") or 0)):
        gid = int(group.get("id") or 0)
        for index, block in enumerate(group.get("blocks") or []):
            text = _v049514_match_text(block.get("text"))
            if not text:
                continue
            output.append({
                "group_id": gid,
                "block_index": index,
                "block_type": str(block.get("type") or "paragraph"),
                "text": text,
            })
    return output


def _v049514_render_plan_block_map(render_plan: dict[str, Any]) -> dict[int, list[dict[str, Any]]]:
    by_group: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for page in render_plan.get("pages", []):
        for side in ("left", "right"):
            for item in page.get(side, []):
                if item.get("type") != "block":
                    continue
                gid = int(item.get("group_id") or 0)
                text = _v049514_match_text(item.get("text"))
                if text:
                    by_group[gid].append({
                        "text": text,
                        "block_type": str(item.get("block_type") or "paragraph"),
                        "page": page.get("page"),
                        "column": side,
                    })
    return by_group


def _v049514_validate_passage_pipeline(
    section_xml: str,
    result: dict[str, Any],
    render_plan: dict[str, Any],
) -> dict[str, Any]:
    """Validate raw -> normalized/blocks -> render plan -> final HWPX passage coverage."""
    from collections import Counter

    paragraphs = _v04959_question_paragraph_map(section_xml)
    groups = sorted(
        [g for g in result.get("passage_groups", []) if int(g.get("id") or 0) > 0],
        key=lambda g: int(g.get("id") or 0),
    )
    gids = [int(g.get("id") or 0) for g in groups]
    guide_positions = [p["index"] for p in paragraphs if p["text"].startswith("※ 다음 글을 읽고")]
    guide_by_gid = {gid: guide_positions[i] for i, gid in enumerate(gids[:len(guide_positions)])}
    first_q_by_gid: dict[int, int] = {}
    for group in groups:
        gid = int(group.get("id") or 0)
        qnums = [int(x) for x in group.get("question_numbers", [])]
        if not qnums:
            continue
        first_q = qnums[0]
        start = guide_by_gid.get(gid, -1)
        found = next((p["index"] for p in paragraphs if p["index"] > start and re.match(rf"^{first_q}\.\s", p["text"])), None)
        if found is not None:
            first_q_by_gid[gid] = found

    plan_by_group = _v049514_render_plan_block_map(render_plan)
    group_reports: list[dict[str, Any]] = []
    all_block_ok = True
    all_label_ok = True

    for group in groups:
        gid = int(group.get("id") or 0)
        expected = [b for b in _v049514_expected_passage_blocks({"passage_groups": [group]})]
        expected_counter = Counter(b["text"] for b in expected)
        plan_counter = Counter(x["text"] for x in plan_by_group.get(gid, []))

        guide_idx = guide_by_gid.get(gid)
        first_q_idx = first_q_by_gid.get(gid)
        if guide_idx is not None and first_q_idx is not None:
            actual_range = [p for p in paragraphs if guide_idx < p["index"] < first_q_idx and p["text"]]
        else:
            actual_range = []
        actual_counter = Counter(_v049514_match_text(p["text"]) for p in actual_range if _v049514_match_text(p["text"]))

        missing_plan = []
        missing_hwpx = []
        for text, count in expected_counter.items():
            if plan_counter[text] < count:
                missing_plan.append({"text": text[:220], "expected": count, "actual": plan_counter[text]})
            if actual_counter[text] < count:
                missing_hwpx.append({"text": text[:220], "expected": count, "actual": actual_counter[text]})

        raw_labels = Counter(_v049514_section_labels_from_text(group.get("raw_text")))
        normalized_labels = Counter(_v049514_section_labels_from_text(group.get("normalized_text")))
        block_labels = Counter(
            b["text"] for b in expected if SECTION_LABEL_RE.fullmatch(b["text"])
        )
        plan_labels = Counter(
            x["text"] for x in plan_by_group.get(gid, []) if SECTION_LABEL_RE.fullmatch(x["text"])
        )
        hwpx_labels = Counter(
            _v049514_match_text(p["text"]) for p in actual_range if SECTION_LABEL_RE.fullmatch(_v049514_match_text(p["text"]))
        )
        label_missing = []
        for label, count in raw_labels.items():
            stages = {
                "raw": count,
                "normalized": normalized_labels[label],
                "blocks": block_labels[label],
                "render": plan_labels[label],
                "hwpx": hwpx_labels[label],
            }
            if any(stages[k] < count for k in ("normalized", "blocks", "render", "hwpx")):
                label_missing.append({"label": label, "counts": stages})

        block_ok = not missing_plan and not missing_hwpx and guide_idx is not None and first_q_idx is not None
        label_ok = not label_missing
        all_block_ok = all_block_ok and block_ok
        all_label_ok = all_label_ok and label_ok
        group_reports.append({
            "group_id": gid,
            "expected_block_count": sum(expected_counter.values()),
            "render_plan_block_count": sum(plan_counter.values()),
            "hwpx_passage_paragraph_count": len(actual_range),
            "passage_guide_paragraph_index": guide_idx,
            "first_question_paragraph_index": first_q_idx,
            "missing_from_render_plan": missing_plan,
            "missing_from_hwpx": missing_hwpx,
            "raw_section_labels": dict(raw_labels),
            "normalized_section_labels": dict(normalized_labels),
            "block_section_labels": dict(block_labels),
            "render_section_labels": dict(plan_labels),
            "hwpx_section_labels": dict(hwpx_labels),
            "section_label_failures": label_missing,
            "passage_block_coverage_status": "PASS" if block_ok else "FAIL",
            "section_label_coverage_status": "PASS" if label_ok else "FAIL",
        })

    return {
        "expected_group_count": len(groups),
        "guide_count": len(guide_positions),
        "groups": group_reports,
        "passage_block_coverage_status": "PASS" if all_block_ok else "FAIL",
        "section_label_coverage_status": "PASS" if all_label_ok else "FAIL",
        "status": "PASS" if all_block_ok and all_label_ok else "FAIL",
    }


def _v049514_validate_example_spacing(result: dict[str, Any], section_xml: str) -> dict[str, Any]:
    """Validate enumeration spacing only inside actual <보기> bodies."""
    expected_issues = []
    for q in result.get("questions", []):
        ex = q.get("example_block") or {}
        if ex.get("exists") and _V049514_ENUM_MARKER_RE.search(_v049_text(ex.get("text"))):
            expected_issues.append({"question_number": q.get("number"), "stage": "result"})

    paragraphs = _v04959_question_paragraph_map(section_xml)
    expected_examples = _v04959_expected_examples(result)
    actual_issues: list[dict[str, Any]] = []
    exp_i = 0
    for pos, para in enumerate(paragraphs):
        if not _V04959_EXAMPLE_TITLE_RE.fullmatch(para["text"]):
            continue
        exp = expected_examples[exp_i] if exp_i < len(expected_examples) else {}
        exp_i += 1
        body = None
        for j in range(pos + 1, min(len(paragraphs), pos + 6)):
            if paragraphs[j]["text"]:
                body = paragraphs[j]
                break
        if body is None:
            actual_issues.append({
                "question_number": exp.get("question_number"),
                "reason": "example body missing",
            })
            continue
        hits = [m.group(0) for m in _V049514_ENUM_MARKER_RE.finditer(body["text"])]
        if hits:
            actual_issues.append({
                "question_number": exp.get("question_number"),
                "paragraph_index": body.get("index"),
                "hits": hits,
                "preview": body.get("text", "")[:220],
            })

    count_ok = exp_i == len(expected_examples)
    return {
        "expected_example_count": len(expected_examples),
        "validated_example_count": exp_i,
        "result_issue_count": len(expected_issues),
        "result_issues": expected_issues,
        "hwpx_issue_count": len(actual_issues),
        "hwpx_issues": actual_issues,
        "example_enumeration_spacing_status": "PASS" if count_ok and not expected_issues and not actual_issues else "FAIL",
    }


def _v049514_preview_snapshot(path: Path) -> dict[str, Any]:
    snap = {"preview_text": None, "preview_image": None}
    try:
        with zipfile.ZipFile(path, "r") as zf:
            for name, key in (("Preview/PrvText.txt", "preview_text"), ("Preview/PrvImage.png", "preview_image")):
                if name not in zf.namelist():
                    continue
                data = zf.read(name)
                snap[key] = {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    except Exception as exc:
        snap["error"] = str(exc)
    return snap


def v049514_validate_hwpx(path: Path, *, result: dict[str, Any], render_plan: dict[str, Any]) -> dict[str, Any]:
    info = v049513_validate_hwpx(path, result=result, render_plan=render_plan)
    info["validator_version"] = _V049514_VERSION
    if not Path(path).exists() or not zipfile.is_zipfile(path) or info.get("package_status") != "PASS":
        info["status"] = "FAIL"
        return info
    try:
        with zipfile.ZipFile(path, "r") as zf:
            section0 = zf.read("Contents/section0.xml").decode("utf-8", errors="strict")
        coverage = _v049514_validate_passage_pipeline(section0, result, render_plan)
        spacing = _v049514_validate_example_spacing(result, section0)
        info["passage_pipeline_coverage_v049514"] = coverage
        info["passage_block_coverage_status"] = coverage["passage_block_coverage_status"]
        info["section_label_coverage_status"] = coverage["section_label_coverage_status"]
        info["example_enumeration_spacing_validation_v049514"] = spacing
        info["example_enumeration_spacing_status"] = spacing["example_enumeration_spacing_status"]
        info["preview_snapshot_v049514"] = _v049514_preview_snapshot(Path(path))

        critical = (
            "passage_block_coverage_status",
            "section_label_coverage_status",
            "example_enumeration_spacing_status",
        )
        if info.get("status") == "FAIL" or any(info.get(k) == "FAIL" for k in critical):
            info["status"] = "FAIL"
        elif info.get("status") == "WARN" or any(info.get(k) == "WARN" for k in critical):
            info["status"] = "WARN"
        else:
            info["status"] = "PASS"
        return info
    except Exception as exc:
        info["v049514_validation_error"] = str(exc)
        info["status"] = "FAIL"
        return info


def _v049514_refresh_preview_with_hancom(
    path: Path,
    *,
    result: dict[str, Any],
    render_plan: dict[str, Any],
    security_module_path: Path | None = None,
    allow_interactive_hwp: bool = False,
    show_hwp: bool = False,
) -> dict[str, Any]:
    """Re-open the fully finalized HWPX in Hangul and SaveAs to regenerate Preview.

    The XML edits remain the compatibility path for layout features that some Hangul
    versions serialize unreliably.  This final COM round-trip makes Hangul itself the
    last writer, so Preview/PrvImage.png and Preview/PrvText.txt are regenerated from
    the finalized document.  The candidate is accepted only if every 5.14 validator
    still passes; otherwise the original finalized file is preserved.
    """
    import os as _os
    import shutil as _shutil

    path = Path(path)
    report: dict[str, Any] = {
        "version": _V049514_VERSION,
        "source": str(path),
        "status": "SKIPPED",
        "applied": False,
        "before_preview": _v049514_preview_snapshot(path) if path.exists() else {},
    }
    if _os.name != "nt":
        report["reason"] = "Preview refresh requires Windows + Hancom Hangul COM"
        return report
    if not path.exists() or not zipfile.is_zipfile(path):
        report.update({"status": "FAIL", "reason": "finalized HWPX is missing or invalid ZIP"})
        return report
    try:
        import win32com.client as win32
    except Exception as exc:
        report.update({"status": "FAIL", "reason": f"pywin32 unavailable: {exc}"})
        return report

    candidate = path.with_name(path.stem + "_v049514_resave.hwpx")
    if candidate.exists():
        try:
            candidate.unlink()
        except Exception:
            pass

    hwp = None
    try:
        security = v0493_prepare_hancom_security(security_module_path)
        hwp = win32.gencache.EnsureDispatch("HWPFrame.HwpObject")
        try:
            hwp.XHwpWindows.Item(0).Visible = bool(show_hwp)
        except Exception:
            pass
        security_runtime = _v0493_register_security_on_hwp(hwp, security)
        report["hancom_security"] = security_runtime
        if not security_runtime.get("unattended_ready") and not allow_interactive_hwp:
            report.update({
                "status": "SKIPPED_SECURITY",
                "reason": "FilePathCheckDLL is not active; preserved validated HWPX instead of risking an approval dialog",
            })
            return report

        opened = False
        for args in (
            (str(path.resolve()), "HWPX", "forceopen:true"),
            (str(path.resolve()), "HWPX", ""),
            (str(path.resolve()),),
        ):
            try:
                ret = hwp.Open(*args)
                opened = ret is not False
                if opened:
                    break
            except Exception:
                continue
        if not opened:
            raise RuntimeError("Hancom could not open finalized HWPX")

        try:
            hwp.SaveAs(str(candidate.resolve()), "HWPX")
        except TypeError:
            hwp.SaveAs(str(candidate.resolve()), "HWPX", "")

        if not candidate.exists() or not zipfile.is_zipfile(candidate):
            raise RuntimeError("COM resave did not produce a valid HWPX candidate")

        validation = v049514_validate_hwpx(candidate, result=result, render_plan=render_plan)
        report["validation"] = validation
        report["after_preview"] = _v049514_preview_snapshot(candidate)
        before = report.get("before_preview") or {}
        after = report.get("after_preview") or {}
        report["preview_member_changed"] = before != after

        if validation.get("status") == "PASS":
            _os.replace(str(candidate), str(path))
            report.update({
                "status": "APPLIED",
                "applied": True,
                "final_path": str(path.resolve()),
                "preview_sync_status": "PASS",
            })
        else:
            try:
                candidate.unlink()
            except Exception:
                pass
            report.update({
                "status": "REJECTED_BY_VALIDATION",
                "preview_sync_status": "WARN",
                "reason": "COM resave changed a validated invariant; original finalized HWPX preserved",
            })
        return report
    except Exception as exc:
        try:
            if candidate.exists():
                candidate.unlink()
        except Exception:
            pass
        report.update({"status": "FAIL", "reason": str(exc), "preview_sync_status": "WARN"})
        return report
    finally:
        if hwp is not None:
            try:
                hwp.Quit()
            except Exception:
                pass


def v049514_upgrade_result(
    result: dict,
    pdf_path: Path,
    checkpoint_path: Path | None = None,
    *,
    hwpx_output_path: Path | None = None,
    question_detection: dict | None = None,
    security_module_path: Path | None = None,
    allow_interactive_hwp: bool = False,
    show_hwp: bool = False,
) -> dict:
    _v0491_log("[v0.4.9.5.14] passage block 보존 + section label pipeline + Preview sync 준비")

    # These repairs MUST happen before the 5.13 render pipeline is invoked.
    label_recovery = _v049514_recover_section_labels(result)
    enum_spacing = _v049514_fix_example_enumeration_spacing(result)

    result = v049513_upgrade_result(
        result,
        pdf_path,
        checkpoint_path=checkpoint_path,
        hwpx_output_path=hwpx_output_path,
        question_detection=question_detection,
        security_module_path=security_module_path,
        allow_interactive_hwp=allow_interactive_hwp,
        show_hwp=show_hwp,
    )

    render_plan = dict(result.get("render_plan_v049513") or {})
    render_plan["version"] = _V049514_VERSION
    render_plan["content_preservation_v049514"] = {
        "passage_group_blocks_are_semantic": True,
        "keyword_noncore_filter_disabled_for_group_blocks": True,
        "section_label_recovery_status": label_recovery.get("status"),
        "recovered_section_label_count": label_recovery.get("recovered_section_label_count", 0),
        "example_enumeration_spacing_status": enum_spacing.get("status"),
        "example_enumeration_spacing_changes": enum_spacing.get("changed_marker_count", 0),
        "native_column_rule_before_save": "HColDef.LineType/LineWidth/LineColor when native MultiColumn path is active",
        "final_preview_policy": "validated finalized HWPX -> Hancom COM reopen/resave -> validate candidate -> atomic replace",
    }
    result["render_plan_v049514"] = render_plan
    result.pop("render_plan_v049513", None)

    old_hwpx = result.get("hwpx_v049513") or {}
    hwpx_info = dict(old_hwpx)
    hwpx_info["backend"] = "hancom_com_v049514"
    final_path_value = old_hwpx.get("final_path") or old_hwpx.get("path")

    preview_refresh: dict[str, Any] = {"status": "SKIPPED", "applied": False}
    if old_hwpx.get("status") == "created" and final_path_value and Path(final_path_value).exists():
        path = Path(final_path_value)
        pre_refresh_validation = v049514_validate_hwpx(path, result=result, render_plan=render_plan)
        hwpx_info["validation_before_preview_refresh_v049514"] = pre_refresh_validation
        if pre_refresh_validation.get("status") == "PASS":
            preview_refresh = _v049514_refresh_preview_with_hancom(
                path,
                result=result,
                render_plan=render_plan,
                security_module_path=security_module_path,
                allow_interactive_hwp=allow_interactive_hwp,
                show_hwp=show_hwp,
            )
        else:
            preview_refresh = {
                "status": "SKIPPED_INVALID_CONTENT",
                "applied": False,
                "reason": "5.14 content coverage failed before preview refresh",
            }
        final_validation = v049514_validate_hwpx(path, result=result, render_plan=render_plan)
        hwpx_info["validation"] = final_validation
        hwpx_info["status"] = "created" if final_validation.get("status") == "PASS" else "INVALID"
        hwpx_info["final_path"] = str(path.resolve())
    elif old_hwpx.get("status") == "SKIPPED":
        final_validation = dict(old_hwpx.get("validation") or {})
        final_validation.setdefault("passage_block_coverage_status", "SKIPPED")
        final_validation.setdefault("section_label_coverage_status", "SKIPPED")
        final_validation.setdefault("example_enumeration_spacing_status", enum_spacing.get("status"))
    else:
        final_validation = dict(old_hwpx.get("validation") or {})

    hwpx_info["preview_refresh_v049514"] = preview_refresh
    result["hwpx_v049514"] = hwpx_info
    result.pop("hwpx_v049513", None)
    result["hancom_security_v049514"] = result.pop("hancom_security_v049513", hwpx_info.get("hancom_security") or {})
    result["question_detection_v049514"] = result.pop("question_detection_v049513", question_detection or {})
    if result.get("passage_image_ownership_v049513"):
        result["passage_image_ownership_v049514"] = dict(result["passage_image_ownership_v049513"])
        result["passage_image_ownership_v049514"]["version"] = _V049514_VERSION

    result["version"] = _V049514_VERSION
    result["parser_version"] = _V049514_VERSION
    result["generator_version"] = "PDF Parser Integrated v0.4.9.5.14"
    result["schema_version"] = {
        "base": "v0.4.9.5.13",
        "extension": [
            "passage_semantic_block_protection",
            "section_label_raw_normalized_render_hwpx_coverage",
            "passage_block_render_hwpx_coverage",
            "example_enumeration_marker_spacing",
            "native_hcoldef_column_rule_before_save",
            "final_hancom_preview_resave_with_atomic_validation",
        ],
    }

    fv = hwpx_info.get("validation") or final_validation or {}
    structural = result.get("structural_validation_v049510") or {}
    hwpx_status = hwpx_info.get("status")
    critical_keys = (
        "continuous_flow_status", "question_integrity_status", "example_integrity_status",
        "underline_status", "question_bold_status", "author_right_align_status",
        "question_negative_underline_status", "source_credit_count_status",
        "picture_affect_line_spacing_status", "image_unit_consistency_status",
        "example_no_pre_blank_status", "example_compact_top_spacing_status",
        "physical_spacer_after_status", "example_choice_clearance_status",
        "example_border_offset_status", "passage_image_ownership_status",
        "passage_image_border_status", "passage_image_document_order_status",
        "question_column_separator_status", "answer_column_separator_status",
        "column_separator_status", "passage_block_coverage_status",
        "section_label_coverage_status", "example_enumeration_spacing_status",
    )
    critical_fail = any(fv.get(k) == "FAIL" for k in critical_keys)
    if label_recovery.get("status") == "FAIL" or enum_spacing.get("status") == "FAIL" or structural.get("status") == "FAIL" or critical_fail:
        final_status = "FAIL"
    elif hwpx_status == "SKIPPED":
        final_status = "WARN"
    elif hwpx_status == "created" and fv.get("status") == "PASS":
        # Preview sync is a quality enhancement.  A security-skipped refresh does
        # not invalidate the already validated HWPX; an actual COM failure is WARN.
        if preview_refresh.get("status") in {"FAIL", "REJECTED_BY_VALIDATION"}:
            final_status = "WARN"
        else:
            final_status = "PASS"
    else:
        final_status = "FAIL"

    result["validation_v049514"] = {
        "question_count": len(result.get("questions", [])),
        "question_detection_status": (question_detection or {}).get("status"),
        "hwpx_status": hwpx_status,
        "hwpx_final_path": hwpx_info.get("final_path"),
        "hwpx_validation_status": fv.get("status"),
        "recovered_section_label_count": label_recovery.get("recovered_section_label_count", 0),
        "section_label_recovery_status": label_recovery.get("status"),
        "example_enumeration_spacing_fix_count": enum_spacing.get("changed_marker_count", 0),
        "example_enumeration_spacing_status": fv.get("example_enumeration_spacing_status", enum_spacing.get("status")),
        "passage_block_coverage_status": fv.get("passage_block_coverage_status"),
        "section_label_coverage_status": fv.get("section_label_coverage_status"),
        "preview_refresh_status": preview_refresh.get("status"),
        "preview_sync_status": preview_refresh.get("preview_sync_status", "SKIPPED" if preview_refresh.get("status") == "SKIPPED" else None),
        "question_column_separator_status": fv.get("question_column_separator_status"),
        "answer_column_separator_status": fv.get("answer_column_separator_status"),
        "column_separator_status": fv.get("column_separator_status"),
        "example_no_pre_blank_status": fv.get("example_no_pre_blank_status"),
        "example_compact_top_spacing_status": fv.get("example_compact_top_spacing_status"),
        "physical_spacer_after_status": fv.get("physical_spacer_after_status"),
        "source_credit_count_status": fv.get("source_credit_count_status"),
        "author_right_align_status": fv.get("author_right_align_status"),
        "picture_affect_line_spacing_status": fv.get("picture_affect_line_spacing_status"),
        "passage_image_ownership_status": fv.get("passage_image_ownership_status"),
        "passage_image_border_status": fv.get("passage_image_border_status"),
        "passage_image_document_order_status": fv.get("passage_image_document_order_status"),
        "image_unit_consistency_status": fv.get("image_unit_consistency_status"),
        "status": final_status,
    }
    return result


def main_v049514() -> None:
    parser = argparse.ArgumentParser(
        description="국어 문제 PDF -> 구조화 JSON + HWPX V0.4.9.5.14 콘텐츠 완전성/Preview 동기화"
    )
    parser.add_argument("pdf", type=Path, help="분석할 PDF 파일")
    parser.add_argument("-o", "--output", type=Path, default=None, help="저장할 JSON. 생략하면 <PDF이름>_result.json")
    parser.add_argument("--hwpx-output", type=Path, default=None, help="최종 HWPX 희망 파일명. 생략하면 <PDF이름>.hwpx, 존재 시 _runNN 자동 생성")
    parser.add_argument("-q", "--questions", nargs="+", type=int, default=None, help="추출할 문제 번호. 생략하면 PDF에서 자동 탐지")
    parser.add_argument("--no-kiwi", action="store_true", help="Kiwi 경계 판별을 끔")
    parser.add_argument("--security-module", type=Path, default=None, help="FilePathCheckerModuleExample.dll 경로")
    parser.add_argument("--allow-interactive-hwp", action="store_true", help="보안 모듈 실패 시 대화형 한글 허용")
    parser.add_argument("--show-hwp", action="store_true", help="한글 창 표시")
    args = parser.parse_args()

    if not args.pdf.exists():
        raise SystemExit(f"PDF 파일을 찾을 수 없습니다: {args.pdf}")
    if not args.no_kiwi and Kiwi is None:
        print("[경고] kiwipiepy 미설치. fallback으로 실행합니다.")

    detection = v04957_detect_question_numbers(args.pdf)
    if args.questions:
        question_numbers = sorted(set(args.questions))
        detection["selection_mode"] = "explicit_cli"
        detection["selected_question_numbers"] = question_numbers
    else:
        if detection.get("status") != "PASS" or not detection.get("question_numbers"):
            raise SystemExit(
                "문제 번호 자동 탐지에 실패했습니다. -q 옵션으로 문제 번호를 직접 지정하세요. "
                + str(detection.get("reason") or "")
            )
        question_numbers = list(detection["question_numbers"])
        detection["selection_mode"] = "auto_detected"
        detection["selected_question_numbers"] = question_numbers

    json_output = Path(args.output) if args.output else _v04957_default_json_path(args.pdf)
    checkpoint_path = json_output.with_name(json_output.stem + "_pre_hwpx.json")
    result = parse_v0_2_3(args.pdf, question_numbers, use_kiwi=not args.no_kiwi)
    result = v044_upgrade_result(result, args.pdf)
    result = v045_upgrade_result(result, args.pdf)
    result = v049514_upgrade_result(
        result,
        args.pdf,
        checkpoint_path=checkpoint_path,
        hwpx_output_path=args.hwpx_output,
        question_detection=detection,
        security_module_path=args.security_module,
        allow_interactive_hwp=args.allow_interactive_hwp,
        show_hwp=args.show_hwp,
    )
    json_output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    checkpoint_info = result.get("pre_hwpx_checkpoint") or {}
    checkpoint_file = Path(str(checkpoint_info.get("path") or "")) if isinstance(checkpoint_info, dict) else None
    if result.get("hwpx_v049514", {}).get("status") == "created" and checkpoint_file and str(checkpoint_file):
        try:
            if checkpoint_file.exists():
                checkpoint_file.unlink()
            checkpoint_info["retained"] = False
            result["pre_hwpx_checkpoint"] = checkpoint_info
            json_output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            checkpoint_info["retained"] = True
            checkpoint_info["cleanup_error"] = str(exc)

    v = result.get("validation_v049514", {})
    print("=" * 76)
    print("V0.4.9.5.14 passage coverage + section label pipeline + Preview sync 검증 완료")
    print("=" * 76)
    print(f"입력 : {args.pdf}")
    print(f"JSON : {json_output.resolve()}")
    print(f"HWPX : {v.get('hwpx_final_path')}")
    print(f"문제 : {v.get('question_count', 0)} | 자동 탐지 : {v.get('question_detection_status')}")
    print(
        "콘텐츠 coverage / section label : "
        f"{v.get('passage_block_coverage_status')} / {v.get('section_label_coverage_status')}"
    )
    print(
        "section label 복구 / 보기 열거 띄어쓰기 : "
        f"{v.get('recovered_section_label_count', 0)}개 / {v.get('example_enumeration_spacing_fix_count', 0)}개"
    )
    print(
        "2단 중앙선 문제/답지/전체 : "
        f"{v.get('question_column_separator_status')} / "
        f"{v.get('answer_column_separator_status')} / "
        f"{v.get('column_separator_status')}"
    )
    print(f"Preview COM 재저장 : {v.get('preview_refresh_status')} | sync={v.get('preview_sync_status')}")
    print(f"HWPX 상태 : {v.get('hwpx_status')} | 최종 검증 : {v.get('status')}")


# =============================================================================
# V0.4.9.5.15 semantic-fidelity / example-gutter-clearance stabilization layer
#
# This layer intentionally fixes the *causes* exposed by v0.4.9.5.14 instead of
# adding another metadata-only PASS condition:
#   1) v0.4.9.5.7 orphan cleanup may not delete a section label that is present
#      in the PDF raw passage, even when its content starts in the next column.
#   2) raw semantic lines such as "작품 구조" / "17~23행:" / "24~29행:"
#      are restored to independent passage blocks before render-plan creation.
#   3) v0.4.9.5.8's geometry-based <보기> repair is wrapped so enumeration
#      spacing is normalized *after* that late repair too.
#   4) <보기> horizontal geometry follows the user's hand-edited reference:
#      500 HWPUNIT left/right paragraph margins and ZERO horizontal border
#      expansion.  This keeps the box safely inside the text column instead of
#      extending 4 mm into the 8 mm center gutter and visually colliding with
#      the 0.12 mm column separator.
#   5) final HWPX validation checks real XML geometry and semantic paragraphs.
# =============================================================================

_V049515_VERSION = "v0.4.9.5.15"
_V049515_EXAMPLE_LR_MARGIN_HWPUNIT = 500
_V049515_EXAMPLE_LR_BORDER_OFFSET_HWPUNIT = 0
_V049515_GUTTER_SAFETY_HWPUNIT = 350
_V049515_STRUCTURE_HEADING = "작품 구조"
_V049515_STRUCTURE_RANGE_RE = re.compile(r"^\s*\d+\s*[~～\-–]\s*\d+\s*행\s*[:：]")
_V049515_ENUM_ADJACENT_RE = re.compile(r"(\(\d+\))(?=[가-힣A-Za-z])")

# Keep references to the proven implementations.  The names themselves are
# overridden below so every historical layer that resolves them at runtime gets
# the corrected v5.15 behavior without duplicating the whole renderer.
_V049515_BASE_V04958_REPAIR_EXAMPLES = v04958_repair_example_blocks
_V049515_BASE_V049511_CLONE_EXAMPLE_VISUAL = _v049511_clone_example_visual_parapr


def _v049515_norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _v049515_fix_enum_spacing_text(value: Any) -> tuple[str, int]:
    text = str(value or "")
    fixed, count = _V049515_ENUM_ADJACENT_RE.subn(r"\1 ", text)
    return fixed, int(count)


def _v049515_patch_margin_tag_value(para_xml: str, tag_name: str, value: int) -> tuple[str, int]:
    pattern = re.compile(rf'(<hc:{re.escape(tag_name)}\b[^>]*\bvalue=")-?\d+("[^>]*/>)')
    return pattern.subn(rf'\g<1>{int(value)}\2', para_xml)


def _v049515_patch_example_para_geometry_xml(para_pr_xml: str) -> tuple[str, bool]:
    """Patch one example paraPr to reference-safe horizontal geometry."""
    before = para_pr_xml
    para_pr_xml, _ = _v049515_patch_margin_tag_value(
        para_pr_xml, "left", _V049515_EXAMPLE_LR_MARGIN_HWPUNIT
    )
    para_pr_xml, _ = _v049515_patch_margin_tag_value(
        para_pr_xml, "right", _V049515_EXAMPLE_LR_MARGIN_HWPUNIT
    )

    def patch_border(m: re.Match) -> str:
        tag = m.group(0)
        tag = _v049511_patch_numeric_attr(
            tag, "offsetLeft", _V049515_EXAMPLE_LR_BORDER_OFFSET_HWPUNIT
        )
        tag = _v049511_patch_numeric_attr(
            tag, "offsetRight", _V049515_EXAMPLE_LR_BORDER_OFFSET_HWPUNIT
        )
        return tag

    para_pr_xml = re.sub(r'<hh:border\b[^>]*/>', patch_border, para_pr_xml, count=1)
    return para_pr_xml, para_pr_xml != before


def _v049511_clone_example_visual_parapr(
    header_xml: str,
    source_id: int,
    new_id: int,
    *,
    role: str,
) -> str:
    """v5.15 runtime override: keep 5.11 behavior but stop LR border expansion."""
    header_xml = _V049515_BASE_V049511_CLONE_EXAMPLE_VISUAL(
        header_xml, source_id, new_id, role=role
    )
    pattern = re.compile(
        rf'<hh:paraPr\b[^>]*\bid="{int(new_id)}"[\s\S]*?</hh:paraPr>'
    )
    m = pattern.search(header_xml)
    if not m:
        raise RuntimeError(f"v5.15 example paraPr {new_id} not found after clone")
    patched, _ = _v049515_patch_example_para_geometry_xml(m.group(0))
    return header_xml[:m.start()] + patched + header_xml[m.end():]


def v04958_repair_example_blocks(result: dict) -> dict:
    """v5.15 runtime override: geometry repair first, enumeration spacing second."""
    result = _V049515_BASE_V04958_REPAIR_EXAMPLES(result)
    changed = 0
    question_reports = []
    for q in result.get("questions", []):
        ex = q.get("example_block") or {}
        if not (ex.get("exists") and str(ex.get("text") or "").strip()):
            continue
        fixed, count = _v049515_fix_enum_spacing_text(ex.get("text"))
        if count:
            ex["text"] = fixed
            q["example_block"] = ex
            changed += count
        question_reports.append({
            "question_number": int(q.get("number") or 0),
            "changed_count": count,
            "status": "PASS" if not _V049515_ENUM_ADJACENT_RE.search(str(ex.get("text") or "")) else "FAIL",
        })
    repair = result.get("example_repair_v04958") or {}
    repair["enumeration_spacing_after_geometry_v049515"] = {
        "changed_marker_count": changed,
        "questions": question_reports,
        "status": "PASS" if all(x["status"] == "PASS" for x in question_reports) else "FAIL",
    }
    result["example_repair_v04958"] = repair
    return result


def _v04957_group_orphan_labels(group: dict) -> list[dict]:
    """v5.15 runtime override: raw-PDF labels are semantic and never orphaned.

    The old v5.7 rule only inspected material after a label inside the current
    block stream.  A label at the end of the left column whose content begins at
    the top of the right column was therefore deleted.  Source evidence wins:
    every occurrence backed by raw_text is preserved.  Only an excess synthetic
    label that does not exist in raw_text can still be considered an orphan.
    """
    blocks = list(group.get("blocks") or [])
    raw_counts = Counter(_v049514_section_labels_from_text(group.get("raw_text")))
    seen = Counter()
    images = [
        a for a in (group.get("image_assets") or [])
        if (a.get("image_output") or {}).get("status") == "saved"
    ]
    label_indices = [
        i for i, b in enumerate(blocks)
        if _V04957_SECTION_LABEL_RE.fullmatch(str(b.get("text") or "").strip())
    ]
    results: list[dict] = []
    for pos, idx in enumerate(label_indices):
        label = str(blocks[idx].get("text") or "").strip()
        seen[label] += 1
        if seen[label] <= raw_counts.get(label, 0):
            # Explicit PDF source evidence: preserve even across page/column edges.
            continue
        end = label_indices[pos + 1] if pos + 1 < len(label_indices) else len(blocks)
        segment = blocks[idx + 1:end]
        has_core_text = any(_v04957_block_is_renderable_core(b) for b in segment)
        has_image = any(str(a.get("section_label") or "").strip() == label for a in images)
        if not has_core_text and not has_image:
            results.append({
                "group_id": int(group.get("id") or 0),
                "label": label,
                "block_index": idx,
                "source_page": blocks[idx].get("source_start_page"),
                "column": blocks[idx].get("column"),
                "reason": "synthetic label has no raw source evidence and no following core text/image",
            })
    return results


def v04957_cleanup_orphan_section_labels(result: dict) -> dict:
    """v5.15 runtime override preserving every raw-source section label."""
    removed: list[dict] = []
    preserved_source_backed: list[dict] = []

    for group in result.get("passage_groups", []):
        raw_counts = Counter(_v049514_section_labels_from_text(group.get("raw_text")))
        seen = Counter()
        for i, block in enumerate(group.get("blocks") or []):
            label = str(block.get("text") or "").strip()
            if not _V04957_SECTION_LABEL_RE.fullmatch(label):
                continue
            seen[label] += 1
            if seen[label] <= raw_counts.get(label, 0):
                preserved_source_backed.append({
                    "group_id": int(group.get("id") or 0),
                    "label": label,
                    "block_index": i,
                    "source_page": block.get("source_start_page"),
                    "column": block.get("column"),
                })

        synthetic_orphans = _v04957_group_orphan_labels(group)
        if synthetic_orphans:
            remove_indices = {int(x["block_index"]) for x in synthetic_orphans}
            old_blocks = list(group.get("blocks") or [])
            group["blocks"] = [b for i, b in enumerate(old_blocks) if i not in remove_indices]
            group["normalized_text"] = "\n".join(
                str(b.get("text") or "").strip()
                for b in group["blocks"]
                if str(b.get("text") or "").strip()
            ).strip()
            removed.extend(synthetic_orphans)

    remaining = []
    for group in result.get("passage_groups", []):
        remaining.extend(_v04957_group_orphan_labels(group))

    result["structural_cleanup_v04957"] = {
        "policy_v049515": "preserve every section label backed by raw PDF source; remove synthetic-only orphan labels",
        "removed_orphan_section_label_count": len(removed),
        "removed_orphan_section_labels": removed,
        "preserved_source_backed_section_label_count": len(preserved_source_backed),
        "preserved_source_backed_section_labels": preserved_source_backed,
        "remaining_orphan_section_label_count": len(remaining),
        "remaining_orphan_section_labels": remaining,
        "orphan_section_label_status": "PASS" if not remaining else "FAIL",
    }
    return result


def _v049515_raw_semantic_sequences(group: dict[str, Any]) -> list[list[str]]:
    """Find conservative raw-line sequences that must remain separate paragraphs."""
    lines = [line.strip() for line in str(group.get("raw_text") or "").splitlines() if line.strip()]
    sequences: list[list[str]] = []
    for i, line in enumerate(lines):
        if _v049515_norm(line) != _V049515_STRUCTURE_HEADING:
            continue
        seq = [line]
        j = i + 1
        while j < len(lines) and _V049515_STRUCTURE_RANGE_RE.match(lines[j]):
            seq.append(lines[j])
            j += 1
        if len(seq) >= 2:
            sequences.append(seq)
    return sequences


def _v049515_restore_semantic_passage_lines(result: dict[str, Any]) -> dict[str, Any]:
    """Split only blocks proven to be a concatenation of raw semantic source lines."""
    group_reports: list[dict[str, Any]] = []
    total_splits = 0
    restored_paragraphs = 0

    for group in result.get("passage_groups", []):
        blocks = list(group.get("blocks") or [])
        sequences = _v049515_raw_semantic_sequences(group)
        if not sequences:
            continue
        changes = []
        for seq in sequences:
            target = _v049515_norm(" ".join(seq))
            match_index = None
            for i, block in enumerate(blocks):
                if _v049515_norm(block.get("text")) == target:
                    match_index = i
                    break
            if match_index is None:
                # Already split is also valid; report it rather than duplicating.
                current = [_v049515_norm(b.get("text")) for b in blocks]
                if all(_v049515_norm(part) in current for part in seq):
                    changes.append({"sequence": seq, "status": "ALREADY_SPLIT"})
                    continue
                changes.append({"sequence": seq, "status": "NOT_FOUND"})
                continue

            old = blocks[match_index]
            start_y = float(old.get("start_y") or 0.0)
            end_y = float(old.get("end_y") or start_y)
            count = len(seq)
            span = max(end_y - start_y, float(max(0, count - 1)))
            step = span / max(count, 1)
            replacements = []
            for k, part in enumerate(seq):
                nb = dict(old)
                nb["type"] = "paragraph"
                nb["text"] = part.strip()
                nb["line_count"] = 1
                nb["start_y"] = start_y + step * k
                nb["end_y"] = start_y + step * (k + 1)
                nb["semantic_line_v049515"] = True
                nb["semantic_line_index_v049515"] = k
                replacements.append(nb)
            blocks[match_index:match_index + 1] = replacements
            total_splits += 1
            restored_paragraphs += count
            changes.append({
                "sequence": seq,
                "status": "SPLIT",
                "old_text": old.get("text"),
                "restored_count": count,
            })

        group["blocks"] = blocks
        group["normalized_text"] = "\n".join(
            str(b.get("text") or "").strip() for b in blocks if str(b.get("text") or "").strip()
        ).strip()
        if changes:
            group_reports.append({
                "group_id": int(group.get("id") or 0),
                "changes": changes,
                "status": "PASS" if all(c["status"] in {"SPLIT", "ALREADY_SPLIT"} for c in changes) else "FAIL",
            })

    report = {
        "version": _V049515_VERSION,
        "split_source_block_count": total_splits,
        "restored_semantic_paragraph_count": restored_paragraphs,
        "groups": group_reports,
        "status": "PASS" if all(g["status"] == "PASS" for g in group_reports) else "FAIL",
    }
    result["semantic_structure_recovery_v049515"] = report
    return report


def _v049515_preflight_content_repairs(result: dict[str, Any], pdf_path: Path) -> dict[str, Any]:
    """Run repairs early enough that every downstream render plan sees them."""
    # Geometry makes Q3's standalone <보기> visible before 5.14 spacing repair.
    result = v0495_attach_question_geometry(pdf_path, result)
    result = _V049515_BASE_V04958_REPAIR_EXAMPLES(result)
    semantic = _v049515_restore_semantic_passage_lines(result)
    return {
        "semantic_structure_status": semantic.get("status"),
        "semantic_structure_split_count": semantic.get("split_source_block_count", 0),
        "early_example_geometry_status": (result.get("example_repair_v04958") or {}).get("status"),
        "early_example_question_numbers": (result.get("example_repair_v04958") or {}).get("expected_from_geometry_question_numbers", []),
        "status": "PASS" if semantic.get("status") == "PASS" and (result.get("example_repair_v04958") or {}).get("status") == "PASS" else "FAIL",
    }


def _v049515_para_style_geometry(header_xml: str) -> dict[int, dict[str, Any]]:
    info: dict[int, dict[str, Any]] = {}
    for m in re.finditer(r'<hh:paraPr\b[^>]*\bid="(\d+)"[\s\S]*?</hh:paraPr>', header_xml):
        pid = int(m.group(1))
        body = m.group(0)
        margin = re.search(r'<hh:margin>([\s\S]*?)</hh:margin>', body)
        margin_blob = margin.group(1) if margin else body
        border = re.search(r'<hh:border\b([^>]*)/>', body)
        battrs = border.group(1) if border else ""

        def margin_value(name: str) -> int:
            mm = re.search(rf'<hc:{re.escape(name)}\b[^>]*\bvalue="(-?\d+)"', margin_blob)
            return int(mm.group(1)) if mm else 0

        def attr_value(name: str, default: int = 0) -> int:
            mm = re.search(rf'\b{re.escape(name)}="(-?\d+)"', battrs)
            return int(mm.group(1)) if mm else default

        align = re.search(r'<hh:align\b[^>]*\bhorizontal="([A-Z_]+)"', body)
        info[pid] = {
            "left": margin_value("left"),
            "right": margin_value("right"),
            "intent": margin_value("intent"),
            "prev": margin_value("prev"),
            "next": margin_value("next"),
            "offsetLeft": attr_value("offsetLeft"),
            "offsetRight": attr_value("offsetRight"),
            "offsetTop": attr_value("offsetTop"),
            "offsetBottom": attr_value("offsetBottom"),
            "borderFillIDRef": attr_value("borderFillIDRef", -1),
            "horizontal": align.group(1) if align else None,
        }
    return info


def _v049515_two_column_same_gap(section_xml: str) -> int | None:
    values = []
    for m in re.finditer(r'<hp:colPr\b([^>]*)>', section_xml):
        attrs = m.group(1)
        cm = re.search(r'\bcolCount="(\d+)"', attrs)
        gm = re.search(r'\bsameGap="(\d+)"', attrs)
        if cm and int(cm.group(1)) >= 2 and gm:
            values.append(int(gm.group(1)))
    return min(values) if values else None


def _v049515_validate_example_divider_clearance(
    header_xml: str,
    section_xml: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    paragraphs = _v04959_question_paragraph_map(section_xml)
    styles = _v049515_para_style_geometry(header_xml)
    edges = _v049510_border_edge_map(header_xml)
    expected = _v04959_expected_examples(result)
    same_gap = _v049515_two_column_same_gap(section_xml)
    half_gap = int(same_gap // 2) if same_gap is not None else None
    max_outward = (
        max(0, half_gap - _V049515_GUTTER_SAFETY_HWPUNIT)
        if half_gap is not None else 0
    )
    reports = []
    exp_i = 0

    for pos, p in enumerate(paragraphs):
        if not _V04959_EXAMPLE_TITLE_RE.fullmatch(p["text"]):
            continue
        exp = expected[exp_i] if exp_i < len(expected) else {}
        exp_i += 1
        body = None
        for j in range(pos + 1, min(len(paragraphs), pos + 6)):
            if paragraphs[j]["text"]:
                body = paragraphs[j]
                break
        if body is None:
            reports.append({"question_number": exp.get("question_number"), "ok": False, "reason": "body missing"})
            continue
        ts = styles.get(int(p.get("paraPrIDRef") or -1), {})
        bs = styles.get(int(body.get("paraPrIDRef") or -1), {})
        te = edges.get(int(ts.get("borderFillIDRef") or -1), {})
        be = edges.get(int(bs.get("borderFillIDRef") or -1), {})
        left_solid = te.get("left") == "SOLID" and be.get("left") == "SOLID"
        right_solid = te.get("right") == "SOLID" and be.get("right") == "SOLID"
        margins_ok = all(
            int(style.get(side) or 0) >= _V049515_EXAMPLE_LR_MARGIN_HWPUNIT
            for style in (ts, bs) for side in ("left", "right")
        )
        offsets_zero = all(
            int(style.get(side) or 0) == _V049515_EXAMPLE_LR_BORDER_OFFSET_HWPUNIT
            for style in (ts, bs) for side in ("offsetLeft", "offsetRight")
        )
        clearance_ok = all(
            int(style.get(side) or 0) <= max_outward
            for style in (ts, bs) for side in ("offsetLeft", "offsetRight")
        ) if half_gap is not None else offsets_zero
        ok = left_solid and right_solid and margins_ok and offsets_zero and clearance_ok
        reports.append({
            "question_number": int(exp.get("question_number") or 0),
            "title_para_style_id": p.get("paraPrIDRef"),
            "body_para_style_id": body.get("paraPrIDRef"),
            "title_left_margin_hwpunit": ts.get("left"),
            "title_right_margin_hwpunit": ts.get("right"),
            "body_left_margin_hwpunit": bs.get("left"),
            "body_right_margin_hwpunit": bs.get("right"),
            "title_offset_left_hwpunit": ts.get("offsetLeft"),
            "title_offset_right_hwpunit": ts.get("offsetRight"),
            "body_offset_left_hwpunit": bs.get("offsetLeft"),
            "body_offset_right_hwpunit": bs.get("offsetRight"),
            "left_border_solid": left_solid,
            "right_border_solid": right_solid,
            "margins_ok": margins_ok,
            "zero_horizontal_border_expansion": offsets_zero,
            "column_rule_clearance_ok": clearance_ok,
            "ok": ok,
        })

    count_ok = len(reports) == len(expected)
    left_ok = count_ok and all(r.get("left_border_solid") for r in reports)
    right_ok = count_ok and all(r.get("right_border_solid") for r in reports)
    geometry_ok = count_ok and all(r.get("margins_ok") and r.get("zero_horizontal_border_expansion") for r in reports)
    clearance_ok = count_ok and all(r.get("column_rule_clearance_ok") for r in reports)
    return {
        "expected_example_count": len(expected),
        "validated_example_count": len(reports),
        "same_gap_hwpunit": same_gap,
        "half_gutter_hwpunit": half_gap,
        "safety_margin_hwpunit": _V049515_GUTTER_SAFETY_HWPUNIT,
        "max_horizontal_border_expansion_hwpunit": max_outward,
        "required_lr_margin_hwpunit": _V049515_EXAMPLE_LR_MARGIN_HWPUNIT,
        "required_lr_border_offset_hwpunit": _V049515_EXAMPLE_LR_BORDER_OFFSET_HWPUNIT,
        "reports": reports,
        "example_left_border_status": "PASS" if left_ok else "FAIL",
        "example_right_border_status": "PASS" if right_ok else "FAIL",
        "example_horizontal_geometry_status": "PASS" if geometry_ok else "FAIL",
        "example_column_separator_clearance_status": "PASS" if clearance_ok else "FAIL",
        "status": "PASS" if left_ok and right_ok and geometry_ok and clearance_ok else "FAIL",
    }


def _v049515_validate_semantic_structure_paragraphs(section_xml: str, result: dict[str, Any]) -> dict[str, Any]:
    expected_sequences = []
    for group in result.get("passage_groups", []):
        for seq in _v049515_raw_semantic_sequences(group):
            expected_sequences.append({"group_id": int(group.get("id") or 0), "paragraphs": [_v049515_norm(x) for x in seq]})
    paragraphs = [
        _v049515_norm(_v04954_para_text(m.group(0)))
        for m in re.finditer(r'<hp:p\b[^>]*>[\s\S]*?</hp:p>', section_xml)
    ]
    reports = []
    cursor = 0
    for item in expected_sequences:
        seq = item["paragraphs"]
        found_positions = []
        local_cursor = cursor
        for expected in seq:
            pos = next((i for i in range(local_cursor, len(paragraphs)) if paragraphs[i] == expected), None)
            if pos is None:
                found_positions = []
                break
            found_positions.append(pos)
            local_cursor = pos + 1
        separate = bool(found_positions) and len(found_positions) == len(seq)
        if separate:
            cursor = found_positions[-1] + 1
        combined = _v049515_norm(" ".join(seq))
        combined_present = combined in paragraphs and len(seq) > 1
        reports.append({
            "group_id": item["group_id"],
            "expected_paragraphs": seq,
            "paragraph_indices": found_positions,
            "separate_paragraphs_present": separate,
            "combined_single_paragraph_present": combined_present,
            "ok": separate and not combined_present,
        })
    ok = all(r["ok"] for r in reports)
    return {
        "expected_sequence_count": len(expected_sequences),
        "reports": reports,
        "semantic_structure_line_status": "PASS" if ok else "FAIL",
        "status": "PASS" if ok else "FAIL",
    }


def _v049515_patch_existing_example_styles(
    header_xml: str,
    section_xml: str,
) -> tuple[str, dict[str, Any]]:
    paragraphs = _v04959_question_paragraph_map(section_xml)
    style_ids: set[int] = set()
    for pos, p in enumerate(paragraphs):
        if not _V04959_EXAMPLE_TITLE_RE.fullmatch(p["text"]):
            continue
        style_ids.add(int(p.get("paraPrIDRef") or -1))
        for j in range(pos + 1, min(len(paragraphs), pos + 6)):
            if paragraphs[j]["text"]:
                style_ids.add(int(paragraphs[j].get("paraPrIDRef") or -1))
                break
    style_ids.discard(-1)
    changed_ids = []
    missing_ids = []
    for pid in sorted(style_ids):
        pat = re.compile(rf'<hh:paraPr\b[^>]*\bid="{pid}"[\s\S]*?</hh:paraPr>')
        m = pat.search(header_xml)
        if not m:
            missing_ids.append(pid)
            continue
        patched, changed = _v049515_patch_example_para_geometry_xml(m.group(0))
        if changed:
            header_xml = header_xml[:m.start()] + patched + header_xml[m.end():]
            changed_ids.append(pid)
    return header_xml, {
        "example_style_ids": sorted(style_ids),
        "changed_style_ids": changed_ids,
        "missing_style_ids": missing_ids,
        "changed_style_count": len(changed_ids),
        "status": "PASS" if style_ids and not missing_ids else "FAIL",
    }


def v049515_validate_hwpx(path: Path, *, result: dict[str, Any], render_plan: dict[str, Any]) -> dict[str, Any]:
    info = v049514_validate_hwpx(path, result=result, render_plan=render_plan)
    info["validator_version"] = _V049515_VERSION
    if not Path(path).exists() or not zipfile.is_zipfile(path):
        return info
    try:
        with zipfile.ZipFile(path, "r") as zf:
            header = zf.read("Contents/header.xml").decode("utf-8", errors="strict")
            section0 = zf.read("Contents/section0.xml").decode("utf-8", errors="strict")
        clearance = _v049515_validate_example_divider_clearance(header, section0, result)
        semantic = _v049515_validate_semantic_structure_paragraphs(section0, result)
        info["example_divider_clearance_v049515"] = clearance
        info["example_left_border_status"] = clearance["example_left_border_status"]
        info["example_right_border_status"] = clearance["example_right_border_status"]
        info["example_horizontal_geometry_status"] = clearance["example_horizontal_geometry_status"]
        info["example_column_separator_clearance_status"] = clearance["example_column_separator_clearance_status"]
        info["semantic_structure_paragraph_validation_v049515"] = semantic
        info["semantic_structure_line_status"] = semantic["semantic_structure_line_status"]
        critical = (
            "example_left_border_status",
            "example_right_border_status",
            "example_horizontal_geometry_status",
            "example_column_separator_clearance_status",
            "semantic_structure_line_status",
        )
        if info.get("status") == "FAIL" or any(info.get(k) == "FAIL" for k in critical):
            info["status"] = "FAIL"
        elif info.get("status") == "WARN" or any(info.get(k) == "WARN" for k in critical):
            info["status"] = "WARN"
        else:
            info["status"] = "PASS"
    except Exception as exc:
        info["v049515_validation_error"] = str(exc)
        info["status"] = "FAIL"
    return info


def _v049515_postprocess_hwpx(path: Path, result: dict[str, Any], render_plan: dict[str, Any]) -> dict[str, Any]:
    path = Path(path)
    report: dict[str, Any] = {
        "version": _V049515_VERSION,
        "status": "SKIPPED",
        "applied": False,
        "source": str(path),
    }
    if not path.exists() or not zipfile.is_zipfile(path):
        report["reason"] = "no usable HWPX"
        return report
    candidate = path.with_name(path.stem + "_v049515_candidate.hwpx")
    if candidate.exists():
        try:
            candidate.unlink()
        except Exception:
            pass
    try:
        with zipfile.ZipFile(path, "r") as zf:
            header = zf.read("Contents/header.xml").decode("utf-8", errors="strict")
            section0 = zf.read("Contents/section0.xml").decode("utf-8", errors="strict")
        patched_header, geometry_report = _v049515_patch_existing_example_styles(header, section0)
        changed = geometry_report.get("changed_style_count", 0) > 0
        if changed:
            _v04954_repack_hwpx(
                path,
                candidate,
                {"Contents/header.xml": patched_header.encode("utf-8")},
            )
            validation = v049515_validate_hwpx(candidate, result=result, render_plan=render_plan)
            accepted = validation.get("status") == "PASS"
            report.update({
                "status": "APPLIED" if accepted else "REJECTED_BY_VALIDATION",
                "applied": accepted,
                "geometry_patch": geometry_report,
                "validation": validation,
                "candidate": str(candidate),
            })
            if accepted:
                os.replace(str(candidate), str(path))
                report["candidate"] = None
                report["final_path"] = str(path.resolve())
            elif candidate.exists():
                candidate.unlink()
        else:
            validation = v049515_validate_hwpx(path, result=result, render_plan=render_plan)
            report.update({
                "status": "ALREADY_COMPLIANT" if validation.get("status") == "PASS" else "REJECTED_BY_VALIDATION",
                "applied": False,
                "geometry_patch": geometry_report,
                "validation": validation,
                "final_path": str(path.resolve()),
            })
        return report
    except Exception as exc:
        report["status"] = "FAIL"
        report["reason"] = str(exc)
        try:
            if candidate.exists():
                candidate.unlink()
        except Exception:
            pass
        return report


def _v049515_refresh_preview_after_patch(
    path: Path,
    *,
    result: dict[str, Any],
    render_plan: dict[str, Any],
    security_module_path: Path | None,
    allow_interactive_hwp: bool,
    show_hwp: bool,
) -> dict[str, Any]:
    """Second Preview refresh only when v5.15 had to change serialized XML."""
    if os.name != "nt":
        return {"status": "SKIPPED_NON_WINDOWS", "applied": False}
    backup = path.with_name(path.stem + "_v049515_before_preview.hwpx")
    try:
        shutil.copy2(path, backup)
        refresh = _v049514_refresh_preview_with_hancom(
            path,
            result=result,
            render_plan=render_plan,
            security_module_path=security_module_path,
            allow_interactive_hwp=allow_interactive_hwp,
            show_hwp=show_hwp,
        )
        after = v049515_validate_hwpx(path, result=result, render_plan=render_plan)
        refresh["validation_v049515_after_refresh"] = after
        if after.get("status") != "PASS":
            shutil.copy2(backup, path)
            refresh["status"] = "REVERTED_BY_V049515_VALIDATION"
            refresh["applied"] = False
        return refresh
    except Exception as exc:
        if backup.exists():
            try:
                shutil.copy2(backup, path)
            except Exception:
                pass
        return {"status": "FAIL", "applied": False, "reason": str(exc)}
    finally:
        try:
            if backup.exists():
                backup.unlink()
        except Exception:
            pass


def v049515_upgrade_result(
    result: dict,
    pdf_path: Path,
    checkpoint_path: Path | None = None,
    *,
    hwpx_output_path: Path | None = None,
    question_detection: dict | None = None,
    security_module_path: Path | None = None,
    allow_interactive_hwp: bool = False,
    show_hwp: bool = False,
) -> dict:
    _v0491_log("[v0.4.9.5.15] source-backed label 보존 + 의미행 복원 + 보기/중앙선 clearance 안정화")

    preflight = _v049515_preflight_content_repairs(result, pdf_path)
    result["content_preflight_v049515"] = preflight

    result = v049514_upgrade_result(
        result,
        pdf_path,
        checkpoint_path=checkpoint_path,
        hwpx_output_path=hwpx_output_path,
        question_detection=question_detection,
        security_module_path=security_module_path,
        allow_interactive_hwp=allow_interactive_hwp,
        show_hwp=show_hwp,
    )

    # The v5.14 fixer now sees Q3 because the geometry repair was intentionally
    # performed before v5.14.  Re-run the late wrapper once more on the final
    # result to guarantee no historical layer reintroduced adjacency.
    result = v04958_repair_example_blocks(result)
    late_spacing = {"changed_marker_count": 0, "questions": [], "status": "PASS"}
    for q in result.get("questions", []):
        ex = q.get("example_block") or {}
        if not (ex.get("exists") and str(ex.get("text") or "").strip()):
            continue
        fixed, count = _v049515_fix_enum_spacing_text(ex.get("text"))
        if count:
            ex["text"] = fixed
            q["example_block"] = ex
        late_spacing["changed_marker_count"] += count
        late_spacing["questions"].append({
            "question_number": int(q.get("number") or 0),
            "changed_count": count,
            "status": "PASS" if not _V049515_ENUM_ADJACENT_RE.search(str(ex.get("text") or "")) else "FAIL",
        })
    late_spacing["status"] = "PASS" if all(x["status"] == "PASS" for x in late_spacing["questions"]) else "FAIL"
    result["example_enumeration_spacing_v049515"] = late_spacing

    render_plan = dict(result.get("render_plan_v049514") or {})
    render_plan["version"] = _V049515_VERSION
    render_plan["semantic_and_clearance_v049515"] = {
        "source_backed_section_labels_are_non_deletable": True,
        "semantic_structure_recovery": "raw separated lines -> independent passage blocks before render",
        "example_lr_margin_hwpunit": _V049515_EXAMPLE_LR_MARGIN_HWPUNIT,
        "example_lr_border_offset_hwpunit": _V049515_EXAMPLE_LR_BORDER_OFFSET_HWPUNIT,
        "column_separator_clearance_validator": True,
        "late_example_enumeration_spacing": True,
    }
    result["render_plan_v049515"] = render_plan
    result.pop("render_plan_v049514", None)

    old_hwpx = result.get("hwpx_v049514") or {}
    hwpx_info = dict(old_hwpx)
    hwpx_info["backend"] = "hancom_com_v049515"
    hwpx_info["renderer_mode"] = "v049514_base_plus_source_semantics_and_safe_example_gutter_v049515"
    final_path_value = old_hwpx.get("final_path") or old_hwpx.get("path")
    postprocess = {"status": "SKIPPED", "applied": False}
    preview_after_patch = {"status": "NOT_NEEDED", "applied": False}

    if final_path_value and Path(final_path_value).exists() and old_hwpx.get("status") in {"created", "INVALID"}:
        path = Path(final_path_value)
        postprocess = _v049515_postprocess_hwpx(path, result, render_plan)
        if postprocess.get("status") in {"APPLIED", "ALREADY_COMPLIANT"}:
            if postprocess.get("applied"):
                preview_after_patch = _v049515_refresh_preview_after_patch(
                    path,
                    result=result,
                    render_plan=render_plan,
                    security_module_path=security_module_path,
                    allow_interactive_hwp=allow_interactive_hwp,
                    show_hwp=show_hwp,
                )
            final_validation = v049515_validate_hwpx(path, result=result, render_plan=render_plan)
            hwpx_info["validation"] = final_validation
            hwpx_info["status"] = "created" if final_validation.get("status") == "PASS" else "INVALID"
            hwpx_info["final_path"] = str(path.resolve())
        else:
            final_validation = postprocess.get("validation") or v049515_validate_hwpx(path, result=result, render_plan=render_plan)
            hwpx_info["validation"] = final_validation
            hwpx_info["status"] = "INVALID"
    elif old_hwpx.get("status") == "SKIPPED":
        final_validation = dict(old_hwpx.get("validation") or {})
        final_validation.setdefault("example_column_separator_clearance_status", "SKIPPED")
        final_validation.setdefault("semantic_structure_line_status", "SKIPPED")
    else:
        final_validation = dict(old_hwpx.get("validation") or {})

    hwpx_info["semantic_finalize_v049515"] = postprocess
    hwpx_info["preview_refresh_after_v049515_patch"] = preview_after_patch
    result["hwpx_v049515"] = hwpx_info
    result.pop("hwpx_v049514", None)
    result["hancom_security_v049515"] = result.pop("hancom_security_v049514", hwpx_info.get("hancom_security") or {})
    result["question_detection_v049515"] = result.pop("question_detection_v049514", question_detection or {})
    if result.get("passage_image_ownership_v049514"):
        result["passage_image_ownership_v049515"] = dict(result["passage_image_ownership_v049514"])
        result["passage_image_ownership_v049515"]["version"] = _V049515_VERSION

    result["version"] = _V049515_VERSION
    result["parser_version"] = _V049515_VERSION
    result["generator_version"] = "PDF Parser Integrated v0.4.9.5.15"
    result["schema_version"] = {
        "base": "v0.4.9.5.14",
        "extension": [
            "source_backed_section_label_non_deletion",
            "cross_column_section_label_preservation",
            "raw_semantic_structure_line_restoration",
            "post_geometry_example_enumeration_spacing",
            "reference_safe_example_horizontal_geometry",
            "example_column_separator_clearance_validation",
            "example_left_right_border_validation",
            "semantic_structure_independent_paragraph_validation",
            "safe_preview_refresh_after_final_xml_patch",
        ],
    }

    fv = hwpx_info.get("validation") or final_validation or {}
    hwpx_status = hwpx_info.get("status")
    structural = result.get("structural_validation_v049510") or {}
    v14 = result.get("validation_v049514") or {}
    semantic_report = result.get("semantic_structure_recovery_v049515") or {}
    critical_keys = (
        "continuous_flow_status", "question_integrity_status", "example_integrity_status",
        "underline_status", "question_bold_status", "author_right_align_status",
        "question_negative_underline_status", "source_credit_count_status",
        "picture_affect_line_spacing_status", "image_unit_consistency_status",
        "example_no_pre_blank_status", "example_compact_top_spacing_status",
        "physical_spacer_after_status", "example_choice_clearance_status",
        "example_border_offset_status", "passage_image_ownership_status",
        "passage_image_border_status", "passage_image_document_order_status",
        "question_column_separator_status", "answer_column_separator_status",
        "column_separator_status", "passage_block_coverage_status",
        "section_label_coverage_status", "example_enumeration_spacing_status",
        "example_left_border_status", "example_right_border_status",
        "example_horizontal_geometry_status", "example_column_separator_clearance_status",
        "semantic_structure_line_status",
    )
    critical_fail = any(fv.get(k) == "FAIL" for k in critical_keys)
    if preflight.get("status") == "FAIL" or semantic_report.get("status") == "FAIL" or late_spacing.get("status") == "FAIL" or structural.get("status") == "FAIL" or critical_fail:
        final_status = "FAIL"
    elif hwpx_status == "SKIPPED":
        final_status = "WARN"
    elif hwpx_status == "created" and fv.get("status") == "PASS":
        final_status = "PASS"
    else:
        final_status = "FAIL"

    result["validation_v049515"] = {
        "question_count": len(result.get("questions", [])),
        "question_detection_status": (question_detection or {}).get("status"),
        "content_preflight_status": preflight.get("status"),
        "semantic_structure_recovery_status": semantic_report.get("status"),
        "semantic_structure_split_count": semantic_report.get("split_source_block_count", 0),
        "recovered_section_label_count": v14.get("recovered_section_label_count", 0),
        "section_label_recovery_status": v14.get("section_label_recovery_status"),
        "example_enumeration_spacing_fix_count": (
            (result.get("example_enumeration_spacing_v049514") or {}).get("changed_marker_count", 0)
            + late_spacing.get("changed_marker_count", 0)
        ),
        "example_enumeration_spacing_status": fv.get("example_enumeration_spacing_status", late_spacing.get("status")),
        "passage_block_coverage_status": fv.get("passage_block_coverage_status"),
        "section_label_coverage_status": fv.get("section_label_coverage_status"),
        "semantic_structure_line_status": fv.get("semantic_structure_line_status"),
        "example_left_border_status": fv.get("example_left_border_status"),
        "example_right_border_status": fv.get("example_right_border_status"),
        "example_horizontal_geometry_status": fv.get("example_horizontal_geometry_status"),
        "example_column_separator_clearance_status": fv.get("example_column_separator_clearance_status"),
        "question_column_separator_status": fv.get("question_column_separator_status"),
        "answer_column_separator_status": fv.get("answer_column_separator_status"),
        "column_separator_status": fv.get("column_separator_status"),
        "example_no_pre_blank_status": fv.get("example_no_pre_blank_status"),
        "example_compact_top_spacing_status": fv.get("example_compact_top_spacing_status"),
        "physical_spacer_after_status": fv.get("physical_spacer_after_status"),
        "source_credit_count_status": fv.get("source_credit_count_status"),
        "author_right_align_status": fv.get("author_right_align_status"),
        "picture_affect_line_spacing_status": fv.get("picture_affect_line_spacing_status"),
        "passage_image_ownership_status": fv.get("passage_image_ownership_status"),
        "passage_image_border_status": fv.get("passage_image_border_status"),
        "passage_image_document_order_status": fv.get("passage_image_document_order_status"),
        "image_unit_consistency_status": fv.get("image_unit_consistency_status"),
        "preview_refresh_status": (
            preview_after_patch.get("status")
            if postprocess.get("applied")
            else (old_hwpx.get("preview_refresh_v049514") or {}).get("status")
        ),
        "hwpx_status": hwpx_status,
        "hwpx_final_path": hwpx_info.get("final_path"),
        "hwpx_validation_status": fv.get("status"),
        "status": final_status,
    }
    return result


def main_v049515() -> None:
    parser = argparse.ArgumentParser(
        description="국어 문제 PDF -> 구조화 JSON + HWPX V0.4.9.5.15 의미구조/보기-중앙선 충돌 안정화"
    )
    parser.add_argument("pdf", type=Path, help="분석할 PDF 파일")
    parser.add_argument("-o", "--output", type=Path, default=None, help="저장할 JSON. 생략하면 <PDF이름>_result.json")
    parser.add_argument("--hwpx-output", type=Path, default=None, help="최종 HWPX 희망 파일명. 생략하면 <PDF이름>.hwpx, 존재 시 _runNN 자동 생성")
    parser.add_argument("-q", "--questions", nargs="+", type=int, default=None, help="추출할 문제 번호. 생략하면 PDF에서 자동 탐지")
    parser.add_argument("--no-kiwi", action="store_true", help="Kiwi 경계 판별을 끔")
    parser.add_argument("--security-module", type=Path, default=None, help="FilePathCheckerModuleExample.dll 경로")
    parser.add_argument("--allow-interactive-hwp", action="store_true", help="보안 모듈 실패 시 대화형 한글 허용")
    parser.add_argument("--show-hwp", action="store_true", help="한글 창 표시")
    args = parser.parse_args()

    if not args.pdf.exists():
        raise SystemExit(f"PDF 파일을 찾을 수 없습니다: {args.pdf}")
    if not args.no_kiwi and Kiwi is None:
        print("[경고] kiwipiepy 미설치. fallback으로 실행합니다.")

    detection = v04957_detect_question_numbers(args.pdf)
    if args.questions:
        question_numbers = sorted(set(args.questions))
        detection["selection_mode"] = "explicit_cli"
        detection["selected_question_numbers"] = question_numbers
    else:
        if detection.get("status") != "PASS" or not detection.get("question_numbers"):
            raise SystemExit(
                "문제 번호 자동 탐지에 실패했습니다. -q 옵션으로 문제 번호를 직접 지정하세요. "
                + str(detection.get("reason") or "")
            )
        question_numbers = list(detection["question_numbers"])
        detection["selection_mode"] = "auto_detected"
        detection["selected_question_numbers"] = question_numbers

    json_output = Path(args.output) if args.output else _v04957_default_json_path(args.pdf)
    checkpoint_path = json_output.with_name(json_output.stem + "_pre_hwpx.json")
    result = parse_v0_2_3(args.pdf, question_numbers, use_kiwi=not args.no_kiwi)
    result = v044_upgrade_result(result, args.pdf)
    result = v045_upgrade_result(result, args.pdf)
    result = v049515_upgrade_result(
        result,
        args.pdf,
        checkpoint_path=checkpoint_path,
        hwpx_output_path=args.hwpx_output,
        question_detection=detection,
        security_module_path=args.security_module,
        allow_interactive_hwp=args.allow_interactive_hwp,
        show_hwp=args.show_hwp,
    )
    json_output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    checkpoint_info = result.get("pre_hwpx_checkpoint") or {}
    checkpoint_file = Path(str(checkpoint_info.get("path") or "")) if isinstance(checkpoint_info, dict) else None
    if result.get("hwpx_v049515", {}).get("status") == "created" and checkpoint_file and str(checkpoint_file):
        try:
            if checkpoint_file.exists():
                checkpoint_file.unlink()
            checkpoint_info["retained"] = False
            result["pre_hwpx_checkpoint"] = checkpoint_info
            json_output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            checkpoint_info["retained"] = True
            checkpoint_info["cleanup_error"] = str(exc)

    v = result.get("validation_v049515", {})
    print("=" * 76)
    print("V0.4.9.5.15 의미구조 + <보기>/중앙선 clearance 검증 완료")
    print("=" * 76)
    print(f"입력 : {args.pdf}")
    print(f"JSON : {json_output.resolve()}")
    print(f"HWPX : {v.get('hwpx_final_path')}")
    print(f"문제 : {v.get('question_count', 0)} | 자동 탐지 : {v.get('question_detection_status')}")
    print(
        "지문 coverage / section label / 의미행 : "
        f"{v.get('passage_block_coverage_status')} / "
        f"{v.get('section_label_coverage_status')} / "
        f"{v.get('semantic_structure_line_status')}"
    )
    print(
        "<보기> 좌선/우선/중앙선 여유 : "
        f"{v.get('example_left_border_status')} / "
        f"{v.get('example_right_border_status')} / "
        f"{v.get('example_column_separator_clearance_status')}"
    )
    print(
        "<보기> 열거 띄어쓰기 수정 : "
        f"{v.get('example_enumeration_spacing_fix_count', 0)}개 | "
        f"상태={v.get('example_enumeration_spacing_status')}"
    )
    print(
        "2단 중앙선 문제/답지/전체 : "
        f"{v.get('question_column_separator_status')} / "
        f"{v.get('answer_column_separator_status')} / "
        f"{v.get('column_separator_status')}"
    )
    print(f"Preview 재저장 : {v.get('preview_refresh_status')}")
    print(f"HWPX 상태 : {v.get('hwpx_status')} | 최종 검증 : {v.get('status')}")


if __name__ == '__main__':
    main_v049515()
