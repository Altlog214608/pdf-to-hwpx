#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
V0 - 국어 문제 PDF 구조화 파서
--------------------------------
목표:
1) PDF 첫 문제 묶음의 지문 추출
2) 1~2번 문제의 문제문/선택지 추출
3) 뒤쪽 정답/해설 페이지에서 정답 번호와 해설 추출
4) 결과를 JSON으로 저장

현재 V0는 업로드된 '최다빈출 공략' 형식의 PDF를 기준으로 작성되었습니다.
다음 버전에서 전체 20문제, 여러 페이지 지문, <보기>, 이미지 문제까지 확장할 예정입니다.

필요 패키지:
    pip install pymupdf

실행:
    python v0_pdf_parser.py "원본.pdf"

출력 파일 지정:
    python v0_pdf_parser.py "원본.pdf" -o result.json
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


def clean_inline_text(text: str) -> str:
    """여러 줄을 읽기 쉬운 한 줄 문자열로 정리한다."""
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)
    return text


def get_line_records(page: fitz.Page) -> list[dict[str, Any]]:
    """페이지의 텍스트 라인과 좌표를 반환한다."""
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
    """
    페이지에 삽입된 이미지의 위치와 이미지 해시를 반환한다.

    이 PDF는 ①~⑤가 일반 텍스트가 아니라 작은 이미지로 들어가 있는 경우가 있다.
    그래서 이미지 내용의 MD5를 사용해 같은 숫자 아이콘인지 비교한다.
    """
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
    """'1.', '2.' 같은 문제 번호 라인의 위치를 찾는다."""
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
    """
    1번 문제의 ①~⑤ 아이콘을 기준 템플릿으로 사용한다.

    예:
        hash(① 이미지) -> 1
        hash(② 이미지) -> 2
        ...
    """
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

    # 같은 x좌표에 세로로 5개 배치된 작은 이미지가 선택지 번호일 가능성이 높다.
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
            "이 PDF 형식은 현재 V0 규칙과 다를 수 있습니다."
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
    """
    첫 페이지에서 '※ 다음 글을...' 이후부터 1번 문제 직전까지를 지문으로 추출한다.

    V0에서는 시/소설의 의도된 줄바꿈을 보존하기 위해 지문은 raw text에 가깝게 둔다.
    """
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
        # zb 표기가 없는 변형 PDF를 위한 fallback
        match = re.search(rf"\n{first_question}\.", body)

    if match is None:
        raise RuntimeError(f"{first_question}번 문제 시작 지점을 찾지 못했습니다.")

    return body[:match.start()].strip()


def extract_question(page: fitz.Page, question_number: int) -> dict[str, Any]:
    """
    문제문과 5개 선택지를 좌표 기반으로 추출한다.

    핵심:
    - 문제 번호 위치로 문제 범위를 정한다.
    - ①~⑤ 작은 이미지 위치를 기준으로 선택지 영역을 나눈다.
    """
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

    # 문제 번호와 가장 가까운 x축의 선택지 그룹을 우선한다.
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

        # 마지막 선택지 뒤쪽의 페이지 번호/푸터가 딸려오는 것을 방지한다.
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
    """정답/해설 페이지의 '1) [정답]' 같은 라인을 찾는다."""
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
    """
    '[정답]' 오른쪽에 붙어 있는 ①~⑤ 이미지의 해시를 읽어 정답 번호로 변환한다.
    OCR 없이 PDF 내부 이미지 자체를 비교하는 방식이다.
    """
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
    """뒤쪽 정답/해설 페이지에서 문제 번호별 해설을 추출한다."""
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


def parse_v0(pdf_path: Path, question_numbers: list[int]) -> dict[str, Any]:
    document = fitz.open(pdf_path)

    try:
        # V0: 첫 문제 묶음이 첫 페이지에 존재한다고 가정한다.
        first_page = document[0]

        digit_icon_map = build_digit_icon_map(first_page, question_numbers[0])
        answers = extract_answer_digits(document, digit_icon_map)
        explanations = extract_explanations(document)

        passage = extract_passage(first_page, question_numbers[0])

        questions: list[dict[str, Any]] = []

        for number in question_numbers:
            question = extract_question(first_page, number)

            answer_number = answers.get(number)

            question["answer"] = (
                f"{'①②③④⑤'[answer_number - 1]}"
                if answer_number is not None
                else None
            )
            question["answer_index"] = answer_number
            question["explanation"] = explanations.get(number)

            questions.append(question)

        return {
            "version": "v0",
            "source_file": pdf_path.name,
            "scope": "첫 지문 묶음 + 1~2번 문제",
            "passage": {
                "raw_text": passage,
            },
            "questions": questions,
            "known_limitations": [
                "PDF 줄바꿈 때문에 일부 단어 사이에 불필요한 공백이 생길 수 있음",
                "V0는 첫 페이지의 첫 문제 묶음만 대상으로 함",
                "<보기>, 표, 이미지 문제는 아직 구조화하지 않음",
                "다른 출판사/사이트 PDF는 레이아웃 규칙을 추가해야 할 수 있음",
            ],
        }

    finally:
        document.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="국어 문제 PDF -> 구조화 JSON V0"
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
        default=Path("v0_result.json"),
        help="저장할 JSON 파일명 (기본: v0_result.json)",
    )

    parser.add_argument(
        "-q",
        "--questions",
        nargs="+",
        type=int,
        default=[1, 2],
        help="추출할 문제 번호 (기본: 1 2)",
    )

    args = parser.parse_args()

    if not args.pdf.exists():
        raise SystemExit(f"PDF 파일을 찾을 수 없습니다: {args.pdf}")

    result = parse_v0(args.pdf, args.questions)

    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("=" * 60)
    print("V0 PDF 구조화 완료")
    print("=" * 60)
    print(f"입력 : {args.pdf}")
    print(f"출력 : {args.output.resolve()}")
    print()

    for question in result["questions"]:
        print(f"[{question['number']}번]")
        print(question["question"])
        print(f"정답: {question['answer']}")

        for index, choice in enumerate(question["choices"], start=1):
            print(f"  {'①②③④⑤'[index - 1]} {choice}")

        print()


if __name__ == "__main__":
    main()
