"""공통 데이터 모델 (페이지 모델 + IR)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional, Union

# 원문자 아이콘 이미지가 들어간 자리에 임시로 넣는 사설 영역 문자 시작값.
ICON_PUA_BASE = 0xE000
CIRCLED_DIGITS = "①②③④⑤⑥⑦⑧⑨⑩"
# 줄 안의 빈칸 네모(예: "주제 : [      ]"). 글자 크기 1em마다 한 글자씩 넣어 너비를 전한다.
BLANK_BOX = "\uF8F0"
# "① 윗글의 (a)와 (b)에 해당하는 의미를 찾아 쓰시오."처럼 원문자가 선택지가 아니라 서술형 하위 물음일 때의 끝말
WRITE_RE = re.compile(r"(쓰시오|쓰라|적으시오|서술하시오|설명하시오|고치시오|채우시오)\s*[.)]?\s*$")


@dataclass
class Glyph:
    c: str
    x0: float
    y0: float
    x1: float
    y1: float
    size: float
    bold: bool = False
    underline: bool = False
    icon: Optional[str] = None  # 아이콘 이미지 해시(원문자)
    color: Optional[str] = None  # 검정이 아닌 글자 색("#28448E" 등)
    shade: Optional[str] = None  # 글자 뒤 형광펜 색
    boxed: bool = False  # 낱말을 둘러싼 작은 네모 안의 글자(글자 테두리)

    @property
    def is_space(self) -> bool:
        return self.c.isspace()


@dataclass
class Line:
    page: int
    col: int
    glyphs: list[Glyph]
    x0: float
    y0: float
    x1: float  # 공백이 아닌 마지막 글자의 오른쪽 끝
    y1: float
    size: float
    lead_size: float  # 첫 글자 조각의 글자 크기(문제 번호 판별용)
    trailing_space: bool = False  # 텍스트 레이어에서 줄이 공백으로 끝남
    box: Optional[int] = None
    cell: Optional[tuple[float, float]] = None  # 표 칸 안의 줄이면 그 칸의 (왼쪽, 오른쪽)
    bracket: Optional[int] = None  # [A] 묶음 괄호 안의 줄이면 괄호 id
    bracket_label: bool = False    # 묶음 괄호 옆의 [A] 표시 줄
    frame: Optional[str] = None    # 박스 안에서 이 줄만 둘러싼 띠 테두리: "SOLID" | "DOUBLE_SLIM"

    @property
    def text(self) -> str:
        return "".join(g.c for g in self.glyphs)

    @property
    def height(self) -> float:
        return self.y1 - self.y0


@dataclass
class ImageEl:
    page: int
    col: int
    x0: float
    y0: float
    x1: float
    y1: float
    digest: str
    xref: int
    box: Optional[int] = None
    png: Optional[bytes] = None  # 렌더링된 PNG (지연 생성)
    in_cell: bool = False

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0


@dataclass
class Box:
    id: int
    page: int
    col: int
    x0: float
    y0: float
    x1: float
    y1: float
    inner_drawings: int = 0
    framed_lines: int = 0  # 박스 안 작은 사각형(도식의 칸) 속에 든 줄 수
    fill: Optional[str] = None  # 바탕색(문제 공략 Tip 의 연두, 지문의 회색 등)
    border_color: Optional[str] = None  # 테두리 색(검정이 아니면)
    border: bool = True  # False: 선 없이 바탕색만 칠한 영역
    brackets: list = field(default_factory=list)  # 상자 안 닫는 괄호 "]" (x, y0, y1): 시 풀이의 장 묶음
    items: list[Union[Line, ImageEl]] = field(default_factory=list)
    # 단/페이지를 넘어 이어지는 박스 조각
    parts: list["Box"] = field(default_factory=list)

    def all_items(self) -> list[Union[Line, ImageEl]]:
        out = list(self.items)
        for p in self.parts:
            out.extend(p.items)
        return out


@dataclass
class PageInfo:
    number: int
    width: float
    height: float
    split_x: float
    content_top: float
    content_bottom: float
    col_left: tuple[float, float]  # (left, right) of column 0
    col_right: tuple[float, float]  # (left, right) of column 1
    single: bool = False  # 단 구분 없이 쪽 전체 폭을 쓰는 쪽(작품 개관·표·구조도 등). 모든 내용이 단 0


@dataclass
class Cell:
    row: int
    col: int
    rowspan: int
    colspan: int
    x0: float
    y0: float
    x1: float
    y1: float
    fill: Optional[str] = None  # 칸 배경색 "#RRGGBB"
    sides: tuple = ()  # 선 없는 배치용 표에서 이 칸에만 긋는 변(시 풀이의 닫는 괄호 칸은 위·오른쪽·아래)
    valign: str = ""  # 칸 세로 정렬("CENTER" 등). 비우면 표 종류를 따른다
    items: list = field(default_factory=list)  # Line | ImageEl (원문 순서)
    paras: list = field(default_factory=list)  # IR 단계에서 채움: list[Para]


@dataclass
class TableEl:
    """선으로 그려진 표. 칸 경계(xs, ys)와 병합된 칸 목록."""
    page: int
    col: int
    xs: list[float]
    ys: list[float]
    cells: list[Cell] = field(default_factory=list)
    box: Optional[int] = None
    lines: bool = True  # False: 선 없는 배치용 표(전폭 상자 안 좌우 두 칸)
    nested: bool = False  # 다른 표의 칸 안에 든 표(그 칸의 items 에 들어 있다)
    text_pt: float = 0.0  # 원문 위치를 살리는 배치용 표: 본문 글자 크기(pt). 칸 폭·왼쪽 여백을 글자 크기 비율로 키운다
    memo: bool = False  # 쪽 크기 한 행 표(메모 칸 | 본문 칸): 쪽 본문 높이에 맞추고 글은 칸 위에서부터

    @property
    def x0(self) -> float:
        return self.xs[0]

    @property
    def x1(self) -> float:
        return self.xs[-1]

    @property
    def y0(self) -> float:
        return self.ys[0]

    @property
    def y1(self) -> float:
        return self.ys[-1]


@dataclass
class Bracket:
    """지문 왼쪽의 [A] 묶음 괄호: 세로선 + 위/아래 짧은 가로선."""
    id: int
    page: int
    col: int
    label: str
    x: float
    y0: float
    y1: float


FlowItem = Union[Line, ImageEl, Box, TableEl]


# ---------------------------------------------------------------- IR -------

@dataclass
class Run:
    text: str
    underline: bool = False
    bold: bool = False
    color: Optional[str] = None  # 검정이 아닌 글자 색
    size: float = 0.0  # 원문 글자 크기(pt). 본문 크기 대비 비율은 rel
    rel: float = 1.0  # 원문 본문 글자 크기 대비 비율(문제 밖 내용에서 작은 설명 글 등을 줄여 쓸 때)
    shade: Optional[str] = None  # 글자 뒤 형광펜 색
    boxed: bool = False  # 글자 테두리(낱말 네모)


@dataclass
class Para:
    """출력 문단. kind: text | blank | image | table | bracket."""
    kind: str = "text"
    runs: list[Run] = field(default_factory=list)
    align: str = "LEFT"  # LEFT | CENTER | RIGHT
    indent_pt: float = 0.0  # +: 첫 줄 들여쓰기, -: 내어쓰기
    image: Optional[ImageEl] = None
    role: str = ""  # label | credit | annotation | ...
    table: Optional["TableEl"] = None    # kind == "table"
    label: str = ""                      # kind == "bracket": "[A]"
    children: list = field(default_factory=list)  # kind == "bracket": 괄호 안 문단들
    frame: Optional[str] = None  # 이 문단만 둘러싼 띠 테두리("SOLID" | "DOUBLE_SLIM", 낱말 띠 등)
    left_pt: float = 0.0  # 왼쪽 여백(pt): 시 풀이에서 구절 아래 풀이를 원문 위치에 맞출 때
    spacing: int = 0  # 원문 자간(%): 한글 글자 사이 간격으로 잰 값(원문 모양을 살리는 문제 밖 내용에만 쓴다)
    wide: bool = False  # 전폭 쪽(PageInfo.single)의 문제 밖 내용: 새 쪽에 한 단(가운데 선 없음)으로
    top: bool = False  # 원문 쪽의 첫 내용(전폭 부분은 여기서 쪽을 나눈다)

    @property
    def text(self) -> str:
        return "".join(r.text for r in self.runs)


@dataclass
class AuxBlock:
    title: str  # "<보기>" 등, 제목 없는 박스는 ""
    kind: str  # 보기 | 조건 | 기타
    paras: list[Para] = field(default_factory=list)
    diagram: Optional[ImageEl] = None  # 도식 박스는 영역 이미지로 대체
    wide: bool = False  # Para.wide 와 같음
    fill: Optional[str] = None  # 바탕색
    border_color: Optional[str] = None  # 테두리 색
    border: bool = True  # False: 선 없이 바탕색만
    top: bool = False  # 원문 쪽의 첫 내용


@dataclass
class Choice:
    label: str
    para: Para
    extra: list[Para] = field(default_factory=list)  # 선택지 아래 오른쪽 정렬 출전 등


@dataclass
class ChoiceGrid:
    """표 모양 선택지(머리 ㉠ ㉡ ㉢ + ① 수리함 좋은 사람 늦기 전에 …): 열 위치를 맞춰 보이지 않는 표로 출력."""
    label_x: float               # 원문자 위치(단 왼쪽 기준, pt)
    cols_x: list[float]          # 각 열 시작 위치(단 왼쪽 기준, pt)
    width: float                 # 단 폭(pt)
    header: list[list["Run"]]    # 열마다 머리 글자(없으면 빈 목록)
    rows: list[tuple[str, list[list["Run"]]]]  # (원문자, 열마다 글자)


@dataclass
class Question:
    number: int
    stem: Para
    passage_id: Optional[int]
    blocks: list[Union[AuxBlock, Para]] = field(default_factory=list)  # 보조박스/그림/기타 문단 (원문 순서)
    choices: list[Choice] = field(default_factory=list)
    after: list = field(default_factory=list)  # 선택지 뒤에 나온 문단/박스/그림 (원문 순서)
    answer: str = ""
    explanation: list[Para] = field(default_factory=list)
    page: int = 0
    grid: Optional[ChoiceGrid] = None
    top: bool = False  # 원문 쪽의 첫 내용

    @property
    def written_parts(self) -> bool:
        """원문자 ①②…가 고르는 선택지가 아니라 '…쓰시오'로 끝나는 서술형 하위 물음인 문제."""
        return bool(self.choices) and all(WRITE_RE.search(c.para.text) for c in self.choices)

    @property
    def qtype(self) -> str:
        return "objective" if self.choices and not self.written_parts else "subjective"


@dataclass
class Passage:
    id: int
    guide: Para
    paras: list[Para] = field(default_factory=list)
    boxed: bool = True
    top: bool = False  # 원문 쪽의 첫 내용
    question_numbers: list[int] = field(default_factory=list)


@dataclass
class AnswerEntry:
    number: int
    head: Para
    paras: list[Para] = field(default_factory=list)


@dataclass
class Document:
    source: str
    items: list = field(default_factory=list)  # Passage | Question | AuxBlock | Para (원문 순서)
    answers: list[AnswerEntry] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    image_only_lines: list = field(default_factory=list)
    # 원문 대조용으로 글자를 고친 줄: id(Line) -> 고친 글. 예) 마침표 없던 문제 번호 "1 위 작품의…" -> "1. 위 작품의…"
    source_fixes: dict = field(default_factory=dict)
    faithful: bool = False  # 원문 쪽마다 새 쪽(쪽 테두리가 있는 학원 자체 교재)
    loose_notes: list[str] = field(default_factory=list)  # 문제/지문 밖 내용(단원 제목 등) 기록  # 도식 박스처럼 그림으로 대체된 원문 줄

    @property
    def questions(self) -> list[Question]:
        return [x for x in self.items if isinstance(x, Question)]

    @property
    def passages(self) -> list[Passage]:
        return [x for x in self.items if isinstance(x, Passage)]
