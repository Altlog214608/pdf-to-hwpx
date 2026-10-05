#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
V0.1 - 국어 문제 PDF 구조화 + Text Normalizer
================================================

V0에서 하던 일
- 첫 지문 묶음 추출
- 1~2번 문제 / 선택지 추출
- 뒤쪽 정답/해설 매칭
- JSON 저장

V0.1에서 추가된 일
- PDF 행갈이 때문에 생긴 잘못된 공백 보정
- 문제문 / 선택지 / 해설에 한국어 띄어쓰기 보정 적용
- 시/문학 지문의 줄바꿈은 최대한 보존
- '것입니\\n다', '그늘에\\n서'처럼 명백히 단어가 잘린 줄바꿈만 복원
- raw passage와 normalized passage를 함께 저장해서 비교 가능

필요 패키지
    pip install pymupdf kiwipiepy

실행
    python v0_1_pdf_parser.py "원본.pdf"

출력 파일명 지정
    python v0_1_pdf_parser.py "원본.pdf" -o v0_1_result.json

Kiwi 띄어쓰기 보정을 끄고 규칙 기반 fallback만 테스트
    python v0_1_pdf_parser.py "원본.pdf" --no-kiwi
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

# 시/지문에서 PDF가 단어 중간을 잘라 다음 줄로 넘겼다고
# 비교적 안전하게 판단할 수 있는 짧은 뒷조각들.
#
# 예:
#   것입니
#   다
#
#   그늘에
#   서
#
# 반면:
#   산에
#   산에
# 는 원래 시의 행이므로 합치면 안 된다.
SAFE_LINE_SUFFIX_FRAGMENTS = {
    "다", "서", "며", "고", "는", "은", "을", "를",
    "이", "가", "의", "로", "와", "과", "도", "만",
    "께", "게", "듯", "때", "지", "면", "니", "요",
    "데", "라", "나",
}

SECTION_LABEL_RE = re.compile(r"^\([가-힣A-Za-z0-9]+\)$")
QUESTION_NUMBER_RE = re.compile(r"^\d+\.$")


class TextNormalizer:
    def __init__(self, use_kiwi: bool = True) -> None:
        self.kiwi = None

        if use_kiwi and Kiwi is not None:
            self.kiwi = Kiwi()

    @property
    def engine_name(self) -> str:
        return "kiwipiepy.Kiwi.space + post rules" if self.kiwi else "rule-based fallback"

    @staticmethod
    def _cleanup_punctuation(text: str) -> str:
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\s+([,.!?;:%)\]}>])", r"\1", text)
        text = re.sub(r"([(\[<{])\s+", r"\1", text)

        # 따옴표 안쪽의 불필요한 공백 일부 정리
        text = re.sub(r"([‘“])\s+", r"\1", text)
        text = re.sub(r"\s+([’”])", r"\1", text)

        # 쉼표/마침표 뒤에는 다음 문자가 붙어 있을 경우 공백 1개
        # 단, 줄바꿈은 건드리지 않는다.
        text = re.sub(r"([,.;!?])([가-힣A-Za-z])", r"\1 \2", text)

        return text.strip()

    @staticmethod
    def _fallback_spacing(text: str) -> str:
        """
        Kiwi를 사용할 수 없을 때의 최소한의 fallback.
        완전한 한국어 띄어쓰기 교정기가 아니라,
        현재 PDF에서 자주 보이는 대표적인 깨짐만 줄인다.
        """
        replacements = {
            "사용 하고": "사용하고",
            "있 다.": "있다.",
            "있 다": "있다",
            "대 상": "대상",
            "화 자": "화자",
            "공 통점": "공통점",
            "성찰 을": "성찰을",
            "이 해": "이해",
            "없으므 로": "없으므로",
            "흐 름": "흐름",
            "나 타나": "나타나",
            "색 채어": "색채어",
            "관 조적인": "관조적인",
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
        문제문 / 선택지 / 해설처럼 줄바꿈 자체에 의미가 거의 없는 텍스트.
        """
        text = re.sub(r"\s+", " ", text).strip()

        if self.kiwi is not None:
            try:
                text = self.kiwi.space(text)
            except Exception:
                text = self._fallback_spacing(text)
        else:
            text = self._fallback_spacing(text)

        return self._cleanup_punctuation(text)

    @staticmethod
    def _should_join_passage_lines(left: str, right: str) -> bool:
        """
        시의 줄바꿈은 살리되, PDF 래핑 때문에 잘린 단어만 제한적으로 붙인다.
        """
        left = left.rstrip()
        right = right.lstrip()

        if not left or not right:
            return False

        # (가), (나), <보기> 같은 구조 표시는 절대 합치지 않는다.
        if SECTION_LABEL_RE.fullmatch(left) or SECTION_LABEL_RE.fullmatch(right):
            return False

        if left in {"<보기>", "※ 다음 글을 읽고 물음에 답하시오."}:
            return False

        if right in {"<보기>", "(중략)", "<중략>"}:
            return False

        # 문장이 이미 끝난 경우.
        if re.search(r"[.!?。！？…」』”’)]$", left):
            return False

        # 시의 반복 행 보호:
        # 산에 / 산에 같은 경우는 유지한다.
        if left.strip() == right.strip():
            return False

        # 다음 행이 1글짜리 조사/어미에 가까운 경우:
        # 것입니 + 다
        # 그늘에 + 서
        if right in SAFE_LINE_SUFFIX_FRAGMENTS:
            return True

        # 다음 행이 1~2글자이고 조각처럼 보이는 경우 중
        # 자주 발생하는 종결/연결형.
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
        문학 지문용.
        원래의 행 구분을 최대한 살리면서 '것입니\\n다'처럼
        확실히 깨진 부분만 이어 붙인다.
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

                # 단어 중간이 잘린 것이므로 공백 없이 붙인다.
                current = current + nxt
                i += 1

            result.append(current)
            i += 1

        return "\n".join(result).strip()


def clean_inline_text(text: str) -> str:
    """
    V0 파서 단계에서 사용.
    여기서는 최소 정리만 하고 진짜 한국어 보정은 TextNormalizer가 담당한다.
    """
    text = re.sub(r"\s+", " ", text).strip()
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
        i for i, (number, _) in enumerate(headers)
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
            "이 PDF 형식은 현재 V0.1 규칙과 다를 수 있습니다."
        )

    choice_icons = sorted(
        max(candidates, key=len),
        key=lambda item: item["rect"].y0,
    )[:5]

    return {
        image["hash"]: index + 1
        for index, image in enumerate(choice_icons)
    }


def extract_passage(page: fitz.Page, first_question: int = 1) -> str:
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
        raise RuntimeError(f"{first_question}번 문제 시작 지점을 찾지 못했습니다.")

    return body[:match.start()].strip()


def extract_question(page: fitz.Page, question_number: int) -> dict[str, Any]:
    lines = get_line_records(page)
    headers = get_question_headers(page)

    index = next(
        i for i, (number, _) in enumerate(headers)
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

    stem_lines.sort(key=lambda line: (line["bbox"].y0, line["bbox"].x0))
    question_text = clean_inline_text(
        " ".join(line["text"] for line in stem_lines)
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

        choice_lines.sort(key=lambda line: (line["bbox"].y0, line["bbox"].x0))

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

        choice_text = clean_inline_text(
            " ".join(line["text"] for line in choice_lines)
        )
        choices.append(choice_text)

    return {
        "number": question_number,
        "question": question_text,
        "choices": choices,
    }


def extract_answer_lines(page: fitz.Page) -> list[tuple[int, fitz.Rect]]:
    answers: list[tuple[int, fitz.Rect]] = []

    for record in get_line_records(page):
        match = re.fullmatch(r"(\d+)\)\s*\[정답\]", record["text"])

        if match:
            answers.append((int(match.group(1)), record["bbox"]))

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
                small_icon = rect.width < 20 and rect.height < 20
                known_digit = image["hash"] in digit_icon_map

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
                    key=lambda image: abs(image["rect"].x0 - answer_box.x1),
                )
                result[question_number] = digit_icon_map[selected["hash"]]

    return result


def extract_explanations(document: fitz.Document) -> dict[int, str]:
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
            explanation = clean_inline_text(match.group(2))
            result[question_number] = explanation

    return result


def parse_v0_1(
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

        answers = extract_answer_digits(document, digit_icon_map)
        explanations = extract_explanations(document)

        raw_passage = extract_passage(
            first_page,
            question_numbers[0],
        )

        normalized_passage = normalizer.normalize_passage(raw_passage)

        questions: list[dict[str, Any]] = []

        for number in question_numbers:
            raw_question = extract_question(first_page, number)

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
                normalizer.normalize_prose(raw_explanation)
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
            "version": "v0.1",
            "source_file": pdf_path.name,
            "scope": "첫 지문 묶음 + 1~2번 문제 + 텍스트 정규화",
            "normalization": {
                "engine": normalizer.engine_name,
                "passage_policy": (
                    "문학 지문의 줄바꿈은 보존하고, "
                    "명백히 잘린 단어만 연결"
                ),
                "prose_policy": (
                    "문제문/선택지/해설은 한 문단으로 병합한 뒤 "
                    "한국어 띄어쓰기 보정"
                ),
            },
            "passage": {
                "raw_text": raw_passage,
                "normalized_text": normalized_passage,
            },
            "questions": questions,
            "known_limitations": [
                "V0.1은 첫 페이지의 첫 문제 묶음만 대상으로 함",
                "시와 산문을 완벽히 자동 분류하지 않고 지문 줄바꿈 보존 정책을 사용함",
                "<보기>, 표, 이미지 문제는 아직 구조화하지 않음",
                "Kiwi 자동 띄어쓰기는 고유명사/고문/방언/의도적 문학 표현을 일부 수정할 수 있어 추후 검수 규칙이 필요함",
                "다른 출판사/사이트 PDF는 레이아웃 규칙을 추가해야 할 수 있음",
            ],
        }

    finally:
        document.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="국어 문제 PDF -> 구조화 JSON V0.1 + Text Normalizer"
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
        default=Path("v0_1_result.json"),
        help="저장할 JSON 파일명 (기본: v0_1_result.json)",
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
        help="Kiwi 띄어쓰기 보정을 끄고 fallback 규칙만 사용",
    )

    args = parser.parse_args()

    if not args.pdf.exists():
        raise SystemExit(f"PDF 파일을 찾을 수 없습니다: {args.pdf}")

    if not args.no_kiwi and Kiwi is None:
        print(
            "[경고] kiwipiepy가 설치되어 있지 않아 "
            "규칙 기반 fallback으로 실행합니다."
        )
        print("       권장 설치: pip install kiwipiepy")
        print()

    result = parse_v0_1(
        args.pdf,
        args.questions,
        use_kiwi=not args.no_kiwi,
    )

    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("=" * 64)
    print("V0.1 PDF 구조화 + Text Normalizer 완료")
    print("=" * 64)
    print(f"입력       : {args.pdf}")
    print(f"출력       : {args.output.resolve()}")
    print(f"Normalizer : {result['normalization']['engine']}")
    print()

    print("[지문 정규화 예시]")
    print(result["passage"]["normalized_text"][:500])
    print("\n...")

    for question in result["questions"]:
        print()
        print(f"[{question['number']}번]")
        print(question["question"])
        print(f"정답: {question['answer']}")

        for index, choice in enumerate(question["choices"], start=1):
            print(f"  {CIRCLED[index - 1]} {choice}")

        if question["explanation"]:
            preview = question["explanation"][:180]
            print(f"해설: {preview}{'...' if len(question['explanation']) > 180 else ''}")


if __name__ == "__main__":
    main()
