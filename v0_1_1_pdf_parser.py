#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
V0.1.1 - 국어 문제 PDF 구조화 + PDF Fragment Repair + Text Normalizer
=====================================================================

V0.1.1의 핵심 변경점
--------------------
1) 문제문 / 선택지 / 해설의 "물리적 PDF 줄바꿈"을 먼저 제거한다.
   - 예: "대\n상에"  -> "대상에"
   - 예: "흐\n름에"  -> "흐름에"
   - 예: "색\n채어"   -> "색채어"
   - 예: "관\n조적인" -> "관조적인"

2) 그 다음 Kiwi 띄어쓰기 보정을 적용한다.
   - 예: "지배하려하고" -> "지배하려 하고"
   - 예: "사용하고있다" -> "사용하고 있다"

3) Kiwi가 문학 용어를 잘못 띄우는 경우를 후처리한다.
   - 예: "영 탄적" -> "영탄적"
   - 예: "색 채어" -> "색채어"
   - 예: "관 조적" -> "관조적"

4) 시/문학 지문은 기존 V0.1 정책 유지
   - 원래 작품의 행갈이는 최대한 보존
   - "것입니\\n다", "그늘에\\n서"처럼 명백한 단어 분절만 결합

필요 패키지
-----------
    pip install pymupdf kiwipiepy

실행
----
    python v0_1_1_pdf_parser.py "원본.pdf"

출력 파일 지정
--------------
    python v0_1_1_pdf_parser.py "원본.pdf" -o v0_1_1_result.json

Kiwi 없이 규칙 기반 fallback 테스트
-----------------------------------
    python v0_1_1_pdf_parser.py "원본.pdf" --no-kiwi
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

SAFE_LINE_SUFFIX_FRAGMENTS = {
    "다", "서", "며", "고", "는", "은", "을", "를",
    "이", "가", "의", "로", "와", "과", "도", "만",
    "께", "게", "듯", "때", "지", "면", "니", "요",
    "데", "라", "나",
}

SECTION_LABEL_RE = re.compile(r"^\([가-힣A-Za-z0-9]+\)$")

# Kiwi가 문학/국어교육 용어를 잘못 쪼개는 경우를 막기 위한
# 최소한의 도메인 용어 목록.
# 새 PDF에서 반복적으로 오분석되는 용어가 확인되면 여기에 추가하면 된다.
DOMAIN_TERMS = [
    "영탄적",
    "색채어",
    "관조적",
]


class TextNormalizer:
    def __init__(self, use_kiwi: bool = True) -> None:
        self.kiwi = None

        if use_kiwi and Kiwi is not None:
            self.kiwi = Kiwi()

            # 형태소 분석기에게도 도메인 단어임을 알려준다.
            # 버전에 따라 add_user_word가 실패해도 후처리 규칙이 한 번 더 보호한다.
            for term in DOMAIN_TERMS:
                try:
                    self.kiwi.add_user_word(term, "NNG", 0)
                except Exception:
                    pass

    @property
    def engine_name(self) -> str:
        if self.kiwi is not None:
            return "PDF fragment repair + kiwipiepy.Kiwi.space + domain post rules"
        return "PDF fragment repair + rule-based fallback"

    @staticmethod
    def repair_prose_linewraps(text: str) -> str:
        """
        문제문 / 선택지 / 해설 전용 PDF Fragment Repair.

        PDF에서 줄 끝이 단어 중간에 걸려도 텍스트 레이어에는
        줄바꿈만 존재하는 경우가 많다.

        예:
            "두 작품 모두 시간의 흐\\n"
            "름에 따라 ..."

        여기에서 줄바꿈을 공백으로 바꾸면:
            "흐 름에"

        가 되어 형태소 분석기가 복원하지 못할 수 있다.

        따라서 prose 영역은 줄바꿈을 '공백 없이' 먼저 붙이고,
        이후 Kiwi가 실제 단어 사이의 띄어쓰기를 복원하도록 한다.
        """
        if not text:
            return ""

        lines: list[str] = []

        for line in text.splitlines():
            line = re.sub(r"[ \t]+", " ", line.strip())

            if line:
                lines.append(line)

        # 핵심: PDF 물리 행갈이를 공백 없이 결합
        return "".join(lines)

    @staticmethod
    def _cleanup_punctuation(text: str) -> str:
        text = re.sub(r"[ \t]+", " ", text)

        # 문장부호 앞 공백 제거
        text = re.sub(r"\s+([,.!?;:%)\]}>])", r"\1", text)

        # 여는 괄호 뒤 공백 제거
        text = re.sub(r"([(\[<{])\s+", r"\1", text)

        # 따옴표 안쪽의 불필요한 공백
        text = re.sub(r"([‘“])\s+", r"\1", text)
        text = re.sub(r"\s+([’”])", r"\1", text)

        # PDF 줄 결합으로 문장부호 다음 문장이 붙은 경우
        text = re.sub(r"([.!?])([가-힣A-Za-z])", r"\1 \2", text)

        return text.strip()

    @staticmethod
    def _repair_domain_terms(text: str) -> str:
        """
        Kiwi가 잘못 분절하기 쉬운 국어/문학 용어를 복원한다.
        문자 사이에 공백이 여러 개 있어도 복원 가능하다.

        예:
            영 탄적 -> 영탄적
            색 채어 -> 색채어
            관 조적인 -> 관조적인
        """
        for term in DOMAIN_TERMS:
            # '영탄적' -> r'영\s*탄\s*적'
            pattern = r"\s*".join(re.escape(ch) for ch in term)
            text = re.sub(pattern, term, text)

        return text

    @staticmethod
    def _post_spacing_rules(text: str) -> str:
        """
        Kiwi 이후에도 남을 수 있는 몇 가지 일반 연결 표현 보정.

        특정 문제 문장 자체를 하드코딩하는 것이 아니라
        활용 형태를 기준으로 적용한다.
        """
        # '~하려하고 / ~하려한다' 계열
        text = re.sub(r"하려\s*하고", "하려 하고", text)
        text = re.sub(r"하려\s*한다", "하려 한다", text)

        # '~하지않다' 류가 붙는 경우
        text = re.sub(r"하지\s*않", "하지 않", text)

        return text

    @staticmethod
    def _fallback_spacing(text: str) -> str:
        """
        Kiwi를 설치하지 않았을 때의 최소 fallback.
        V0.1.1에서는 PDF 줄바꿈 자체는 이미 repair_prose_linewraps()
        단계에서 처리되므로, 대표적인 후처리만 수행한다.
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
        }

        for before, after in replacements.items():
            text = text.replace(before, after)

        return text

    def normalize_prose(self, text: str) -> str:
        """
        문제문 / 선택지 / 해설용 정규화.

        처리 순서:
            raw PDF lines
            -> PDF Fragment Repair
            -> Kiwi spacing
            -> Domain term repair
            -> Post spacing rules
            -> punctuation cleanup
        """
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
        문학 지문의 원래 행갈이는 살리고,
        명백히 PDF에서 단어가 쪼개진 경우만 연결한다.
        """
        left = left.rstrip()
        right = right.lstrip()

        if not left or not right:
            return False

        # (가), (나) 등 구조 구분
        if SECTION_LABEL_RE.fullmatch(left) or SECTION_LABEL_RE.fullmatch(right):
            return False

        if left in {
            "<보기>",
            "※ 다음 글을 읽고 물음에 답하시오.",
            "※ 다음 글을 읽고, 물음에 답하시오.",
        }:
            return False

        if right in {"<보기>", "(중략)", "<중략>"}:
            return False

        # 이미 문장이 종료된 경우
        if re.search(r"[.!?。！？…」』”’)]$", left):
            return False

        # 시에서 동일 행 반복 보호
        if left.strip() == right.strip():
            return False

        # 것입니 + 다 / 그늘에 + 서
        if right in SAFE_LINE_SUFFIX_FRAGMENTS:
            return True

        if len(right) <= 2 and re.fullmatch(r"[가-힣]+", right):
            endings = (
                "다", "서", "고", "며", "는", "은", "을", "를",
                "로", "와", "과", "도", "만", "면", "니", "요",
            )

            if right.endswith(endings):
                return True

        return False

    def normalize_passage(self, text: str) -> str:
        """
        문학 지문 전용.

        시의 원래 행갈이를 보존해야 하므로,
        prose처럼 모든 줄을 합치지 않는다.
        """
        raw_lines = [line.rstrip() for line in text.splitlines()]
        raw_lines = [line for line in raw_lines if line.strip()]

        if not raw_lines:
            return ""

        result: list[str] = []
        i = 0

        while i < len(raw_lines):
            current = raw_lines[i].strip()

            while i + 1 < len(raw_lines):
                nxt = raw_lines[i + 1].strip()

                if not self._should_join_passage_lines(current, nxt):
                    break

                current = current + nxt
                i += 1

            result.append(current)
            i += 1

        return "\n".join(result).strip()


def clean_inline_text(text: str) -> str:
    """
    한 줄 내부의 최소한의 정리만 수행.
    V0.1.1의 핵심 정규화는 TextNormalizer가 담당한다.
    """
    text = re.sub(r"[ \t]+", " ", text).strip()
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)
    return text


def get_line_records(page: fitz.Page) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    for block in page.get_text("dict")["blocks"]:
        if block["type"] != 0:
            continue

        for line in block["lines"]:
            raw_text = "".join(span["text"] for span in line["spans"])
            text = raw_text.strip()

            if text:
                records.append(
                    {
                        "text": text,
                        "bbox": fitz.Rect(line["bbox"]),
                    }
                )

    return records


def get_image_instances(page: fitz.Page) -> list[dict[str, Any]]:
    instances: list[dict[str, Any]] = []
    seen_xrefs: set[int] = set()

    for image_info in page.get_images(full=True):
        xref = image_info[0]

        if xref in seen_xrefs:
            continue

        seen_xrefs.add(xref)

        try:
            image_bytes = page.parent.extract_image(xref)["image"]
        except Exception:
            pix = fitz.Pixmap(page.parent, xref)
            image_bytes = pix.tobytes("png")

        image_hash = hashlib.md5(image_bytes).hexdigest()

        for rect in page.get_image_rects(xref):
            instances.append(
                {
                    "xref": xref,
                    "rect": rect,
                    "hash": image_hash,
                    "pixel_width": image_info[2],
                    "pixel_height": image_info[3],
                }
            )

    return instances


def get_question_headers(page: fitz.Page) -> list[tuple[int, fitz.Rect]]:
    result: list[tuple[int, fitz.Rect]] = []

    for record in get_line_records(page):
        match = re.fullmatch(r"(\d+)\.", record["text"])

        if match:
            result.append((int(match.group(1)), record["bbox"]))

    return sorted(result, key=lambda item: item[1].y0)


def build_digit_icon_map(
    page: fitz.Page,
    question_number: int = 1,
) -> dict[str, int]:
    headers = get_question_headers(page)

    index = next(
        i
        for i, (number, _) in enumerate(headers)
        if number == question_number
    )

    start_y = headers[index][1].y0
    end_y = (
        headers[index + 1][1].y0
        if index + 1 < len(headers)
        else page.rect.height
    )

    images = [
        item
        for item in get_image_instances(page)
        if start_y < item["rect"].y0 < end_y
        and item["rect"].width < 20
        and item["rect"].height < 20
    ]

    groups: dict[int, list[dict[str, Any]]] = defaultdict(list)

    for image in images:
        groups[round(image["rect"].x0)].append(image)

    candidates = [
        group
        for group in groups.values()
        if len(group) >= 5
    ]

    if not candidates:
        raise RuntimeError(
            "①~⑤ 선택지 아이콘을 찾지 못했습니다. "
            "이 PDF 형식은 현재 V0.1.1 규칙과 다를 수 있습니다."
        )

    choice_icons = sorted(
        max(candidates, key=len),
        key=lambda item: item["rect"].y0,
    )[:5]

    return {
        image["hash"]: index + 1
        for index, image in enumerate(choice_icons)
    }


def extract_passage(
    page: fitz.Page,
    first_question: int = 1,
) -> str:
    text = page.get_text("text")

    anchors = [
        "※ 다음 글을 읽고, 물음에 답하시오.",
        "※ 다음 글을 읽고 물음에 답하시오.",
    ]

    start = -1
    selected_anchor = ""

    for anchor in anchors:
        start = text.find(anchor)

        if start >= 0:
            selected_anchor = anchor
            break

    if start < 0:
        raise RuntimeError("지문 시작 문구를 찾지 못했습니다.")

    body = text[start + len(selected_anchor):]

    question_pattern = re.compile(
        rf"\n{first_question}\.\s*\nzb{first_question}\)"
    )
    match = question_pattern.search(body)

    if match is None:
        match = re.search(rf"\n{first_question}\.", body)

    if match is None:
        raise RuntimeError(
            f"{first_question}번 문제 시작 지점을 찾지 못했습니다."
        )

    return body[:match.start()].strip()


def extract_question(
    page: fitz.Page,
    question_number: int,
) -> dict[str, Any]:
    """
    V0.1.1 변경점:
    줄들을 공백으로 합치지 않고 '\\n'으로 보존해 TextNormalizer에 넘긴다.

    이것이 다음과 같은 PDF 분절을 복원하는 핵심이다.

        '대'
        '상에 순응하려 한다.'

    -> normalize_prose()
    -> '대상에 순응하려 한다.'
    """
    lines = get_line_records(page)
    headers = get_question_headers(page)

    index = next(
        i
        for i, (number, _) in enumerate(headers)
        if number == question_number
    )

    question_box = headers[index][1]
    start_y = question_box.y0
    end_y = (
        headers[index + 1][1].y0
        if index + 1 < len(headers)
        else page.rect.height - 40
    )

    images = [
        item
        for item in get_image_instances(page)
        if start_y < item["rect"].y0 < end_y
        and item["rect"].width < 20
        and item["rect"].height < 20
    ]

    groups: dict[int, list[dict[str, Any]]] = defaultdict(list)

    for image in images:
        groups[round(image["rect"].x0)].append(image)

    candidate_groups = [
        group
        for group in groups.values()
        if len(group) >= 5
    ]

    if not candidate_groups:
        raise RuntimeError(
            f"{question_number}번 문제의 선택지 아이콘을 찾지 못했습니다."
        )

    markers = sorted(
        min(
            candidate_groups,
            key=lambda group: abs(
                sum(item["rect"].x0 for item in group) / len(group)
                - question_box.x0
            ),
        ),
        key=lambda item: item["rect"].y0,
    )[:5]

    first_choice_y = markers[0]["rect"].y0 - 4
    min_x = question_box.x0 - 5

    stem_lines = [
        line
        for line in lines
        if start_y <= line["bbox"].y0 < first_choice_y
        and line["bbox"].x0 >= min_x
        and not re.fullmatch(r"\d+\.", line["text"])
        and not line["text"].startswith("zb")
    ]

    stem_lines.sort(
        key=lambda line: (
            line["bbox"].y0,
            line["bbox"].x0,
        )
    )

    # 중요: 공백이 아니라 newline으로 연결
    question_text = "\n".join(
        clean_inline_text(line["text"])
        for line in stem_lines
    )

    choices: list[str] = []

    for choice_index, marker in enumerate(markers):
        choice_start = marker["rect"].y0 - 4

        choice_end = (
            markers[choice_index + 1]["rect"].y0 - 4
            if choice_index + 1 < len(markers)
            else end_y
        )

        choice_lines = [
            line
            for line in lines
            if choice_start <= line["bbox"].y0 < choice_end
            and line["bbox"].x0 > marker["rect"].x1
        ]

        choice_lines.sort(
            key=lambda line: (
                line["bbox"].y0,
                line["bbox"].x0,
            )
        )

        # 마지막 선택지 아래 푸터 등이 딸려오는 것을 막는다.
        if choice_index == len(markers) - 1 and choice_lines:
            filtered = [choice_lines[0]]
            previous_bottom = choice_lines[0]["bbox"].y1

            for line in choice_lines[1:]:
                vertical_gap = line["bbox"].y0 - previous_bottom

                if vertical_gap > 25:
                    break

                filtered.append(line)
                previous_bottom = line["bbox"].y1

            choice_lines = filtered

        # 중요: PDF 물리 행갈이를 TextNormalizer가 판단할 수 있도록
        # 줄 구분을 보존한다.
        choice_text = "\n".join(
            clean_inline_text(line["text"])
            for line in choice_lines
        )

        choices.append(choice_text)

    return {
        "number": question_number,
        "question": question_text,
        "choices": choices,
    }


def extract_answer_lines(
    page: fitz.Page,
) -> list[tuple[int, fitz.Rect]]:
    answers: list[tuple[int, fitz.Rect]] = []

    for record in get_line_records(page):
        match = re.fullmatch(
            r"(\d+)\)\s*\[정답\]",
            record["text"],
        )

        if match:
            answers.append(
                (
                    int(match.group(1)),
                    record["bbox"],
                )
            )

    return answers


def extract_answer_digits(
    document: fitz.Document,
    digit_icon_map: dict[str, int],
) -> dict[int, int]:
    result: dict[int, int] = {}

    for page in document:
        answer_lines = extract_answer_lines(page)

        if not answer_lines:
            continue

        images = get_image_instances(page)

        for question_number, answer_box in answer_lines:
            candidates = []

            for image in images:
                rect = image["rect"]

                same_line = abs(rect.y0 - answer_box.y0) <= 5

                just_right_of_answer = (
                    answer_box.x1 - 3
                    <= rect.x0
                    <= answer_box.x1 + 30
                )

                small_icon = (
                    rect.width < 20
                    and rect.height < 20
                )

                known_digit = (
                    image["hash"] in digit_icon_map
                )

                if (
                    same_line
                    and just_right_of_answer
                    and small_icon
                    and known_digit
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
                    digit_icon_map[selected["hash"]]
                )

    return result


def extract_explanations(
    document: fitz.Document,
) -> dict[int, str]:
    """
    V0.1.1 변경점:
    해설을 여기서 한 줄로 강제하지 않는다.

    PDF 원래 줄바꿈을 그대로 TextNormalizer로 넘겨
    '흐\\n름', '색\\n채어', '관\\n조적'을 복원한다.
    """
    result: dict[int, str] = {}

    pattern = re.compile(
        r"(?ms)^(\d+)\)\s*\[정답\]\s*\n"
        r"\[해설\]\s*(.*?)"
        r"(?=^\d+\)\s*\[정답\]|\Z)"
    )

    for page in document:
        text = page.get_text("text")

        if "[정답]" not in text or "[해설]" not in text:
            continue

        for match in pattern.finditer(text):
            question_number = int(match.group(1))

            # clean_inline_text()를 쓰지 않고 줄바꿈 보존
            explanation = match.group(2).strip()

            result[question_number] = explanation

    return result


def parse_v0_1_1(
    pdf_path: Path,
    question_numbers: list[int],
    use_kiwi: bool = True,
) -> dict[str, Any]:
    document = fitz.open(pdf_path)
    normalizer = TextNormalizer(use_kiwi=use_kiwi)

    try:
        first_page = document[0]

        digit_icon_map = build_digit_icon_map(
            first_page,
            question_numbers[0],
        )

        answers = extract_answer_digits(
            document,
            digit_icon_map,
        )

        explanations = extract_explanations(document)

        raw_passage = extract_passage(
            first_page,
            question_numbers[0],
        )

        normalized_passage = (
            normalizer.normalize_passage(raw_passage)
        )

        questions: list[dict[str, Any]] = []

        for number in question_numbers:
            raw_question = extract_question(
                first_page,
                number,
            )

            answer_number = answers.get(number)
            raw_explanation = explanations.get(number)

            normalized_question = normalizer.normalize_prose(
                raw_question["question"]
            )

            normalized_choices = [
                normalizer.normalize_prose(choice)
                for choice in raw_question["choices"]
            ]

            normalized_explanation = (
                normalizer.normalize_prose(
                    raw_explanation
                )
                if raw_explanation
                else None
            )

            questions.append(
                {
                    "number": number,
                    "question": normalized_question,
                    "choices": normalized_choices,
                    "answer": (
                        CIRCLED[answer_number - 1]
                        if answer_number is not None
                        else None
                    ),
                    "answer_index": answer_number,
                    "explanation": normalized_explanation,
                }
            )

        return {
            "version": "v0.1.1",
            "source_file": pdf_path.name,
            "scope": (
                "첫 지문 묶음 + 1~2번 문제 + "
                "PDF Fragment Repair + 텍스트 정규화"
            ),
            "normalization": {
                "engine": normalizer.engine_name,
                "fragment_repair": (
                    "문제문/선택지/해설의 PDF 물리 행갈이는 "
                    "공백 없이 먼저 결합한 뒤 Kiwi로 실제 띄어쓰기 복원"
                ),
                "passage_policy": (
                    "문학 지문의 줄바꿈은 보존하고, "
                    "명백히 잘린 단어만 연결"
                ),
                "domain_terms": DOMAIN_TERMS,
            },
            "passage": {
                "raw_text": raw_passage,
                "normalized_text": normalized_passage,
            },
            "questions": questions,
            "known_limitations": [
                "V0.1.1은 첫 페이지의 첫 문제 묶음만 대상으로 함",
                "시와 산문을 완벽히 자동 분류하지 않고 지문 줄바꿈 보존 정책을 사용함",
                "<보기>, 표, 이미지 문제는 아직 구조화하지 않음",
                "Kiwi 자동 띄어쓰기는 고유명사/고문/방언/문학적 표현을 일부 수정할 수 있어 추후 검수 규칙이 필요함",
                "다른 출판사/사이트 PDF는 레이아웃 규칙을 추가해야 할 수 있음",
            ],
        }

    finally:
        document.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "국어 문제 PDF -> 구조화 JSON V0.1.1 "
            "+ PDF Fragment Repair + Text Normalizer"
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
        default=Path("v0_1_1_result.json"),
        help=(
            "저장할 JSON 파일명 "
            "(기본: v0_1_1_result.json)"
        ),
    )

    parser.add_argument(
        "-q",
        "--questions",
        nargs="+",
        type=int,
        default=[1, 2],
        help="추출할 문제 번호 (기본: 1 2)",
    )

    parser.add_argument(
        "--no-kiwi",
        action="store_true",
        help=(
            "Kiwi 띄어쓰기 보정을 끄고 "
            "fallback 규칙만 사용"
        ),
    )

    args = parser.parse_args()

    if not args.pdf.exists():
        raise SystemExit(
            f"PDF 파일을 찾을 수 없습니다: {args.pdf}"
        )

    if not args.no_kiwi and Kiwi is None:
        print(
            "[경고] kiwipiepy가 설치되어 있지 않아 "
            "규칙 기반 fallback으로 실행합니다."
        )
        print(
            "       권장 설치: "
            "pip install kiwipiepy"
        )
        print()

    result = parse_v0_1_1(
        args.pdf,
        args.questions,
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

    print("=" * 70)
    print(
        "V0.1.1 PDF 구조화 + "
        "Fragment Repair + Text Normalizer 완료"
    )
    print("=" * 70)

    print(f"입력       : {args.pdf}")
    print(f"출력       : {args.output.resolve()}")
    print(
        f"Normalizer : "
        f"{result['normalization']['engine']}"
    )
    print()

    print("[지문 정규화 예시]")
    print(
        result["passage"]["normalized_text"][:500]
    )
    print("\n...")

    for question in result["questions"]:
        print()
        print(f"[{question['number']}번]")
        print(question["question"])
        print(f"정답: {question['answer']}")

        for index, choice in enumerate(
            question["choices"],
            start=1,
        ):
            print(
                f"  {CIRCLED[index - 1]} "
                f"{choice}"
            )

        if question["explanation"]:
            preview = question["explanation"][:220]

            print(
                "해설: "
                f"{preview}"
                f"{'...' if len(question['explanation']) > 220 else ''}"
            )


if __name__ == "__main__":
    main()
