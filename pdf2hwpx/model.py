"""공통 데이터 모델 (페이지 모델 + IR)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Union

# 원문자 아이콘 이미지가 들어간 자리에 임시로 넣는 사설 영역 문자 시작값.
ICON_PUA_BASE = 0xE000
CIRCLED_DIGITS = "①②③④⑤⑥⑦⑧⑨⑩"


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


FlowItem = Union[Line, ImageEl, Box]


# ---------------------------------------------------------------- IR -------

@dataclass
class Run:
    text: str
    underline: bool = False
    bold: bool = False


@dataclass
class Para:
    """출력 문단. kind: text | blank | image."""
    kind: str = "text"
    runs: list[Run] = field(default_factory=list)
    align: str = "LEFT"  # LEFT | CENTER | RIGHT
    indent_pt: float = 0.0  # +: 첫 줄 들여쓰기, -: 내어쓰기
    image: Optional[ImageEl] = None
    role: str = ""  # label | credit | annotation | ...

    @property
    def text(self) -> str:
        return "".join(r.text for r in self.runs)


@dataclass
class AuxBlock:
    title: str  # "<보기>" 등, 제목 없는 박스는 ""
    kind: str  # 보기 | 조건 | 기타
    paras: list[Para] = field(default_factory=list)
    diagram: Optional[ImageEl] = None  # 도식 박스는 영역 이미지로 대체


@dataclass
class Choice:
    label: str
    para: Para


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

    @property
    def qtype(self) -> str:
        return "objective" if self.choices else "subjective"


@dataclass
class Passage:
    id: int
    guide: Para
    paras: list[Para] = field(default_factory=list)
    boxed: bool = True
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
    loose_notes: list[str] = field(default_factory=list)  # 문제/지문 밖 내용(단원 제목 등) 기록  # 도식 박스처럼 그림으로 대체된 원문 줄

    @property
    def questions(self) -> list[Question]:
        return [x for x in self.items if isinstance(x, Question)]

    @property
    def passages(self) -> list[Passage]:
        return [x for x in self.items if isinstance(x, Passage)]
