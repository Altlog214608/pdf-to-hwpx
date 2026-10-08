"""출력 HWPX의 문서 스타일 옵션 (웹 화면/CLI에서 지정)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

# 한글에서 흔히 쓰는 글꼴. 사용자 PC에 없으면 한글이 비슷한 글꼴로 대체해서 연다.
FONTS = ["함초롬바탕", "함초롬돋움", "맑은 고딕", "바탕", "돋움", "나눔명조", "나눔고딕"]


@dataclass
class DocStyle:
    body_font: str = "함초롬바탕"   # 본문(지문·문제·선택지·해설) 글꼴
    title_font: str = "함초롬돋움"  # 바탕쪽 제목/학원 이름 글꼴
    body_size: float = 10.0          # 본문 글자 크기(pt)
    academy_name: str = ""           # 바탕쪽 왼쪽 위 학원 이름(검은 칸에 흰 글씨), 예: "김한춘"
    academy_sub: str = ""            # 학원 이름 뒤에 작은 글씨로 붙는 부분, 예: "국어전문학원"
    academy_size: float = 14.0       # 학원 이름 글자 크기(pt)
    academy_sub_size: float = 11.0   # 뒷부분 글자 크기(pt)
    logo: Optional[bytes] = None     # 학원 로고 그림(PNG/JPG). 있으면 이름 대신 사용
    title: str = ""                  # 바탕쪽 제목, 예: "[중간 대비] 2. 품격을 높이는 언어생활 ①"
    title_size: float = 14.0
    title_color: str = "#000000"     # 제목 글자 색(#RRGGBB)
    answers_as_endnotes: bool = False  # 정답·해설을 각 문제에 연결된 미주로 넣기(문서 끝에 모임)
    frame: bool = False              # 페이지 바깥 네모 테두리
    auto_number: bool = True         # 문제 번호를 한글 문단 번호로(문제를 더 넣거나 이어 붙이면 번호가 자동으로 이어짐)
    preset: str = ""                 # 바탕쪽 프리셋 id(pdf2hwpx/presets, 예: "hakwon1"). 있으면 학원/제목/테두리 대신 그 바탕쪽
    template: Optional[dict] = None  # 프리셋의 바탕쪽 묶음(master_template 형식). preset 으로 채운다
    extra: dict = field(default_factory=dict)

    @property
    def header_enabled(self) -> bool:
        return bool(self.academy_name.strip() or self.academy_sub.strip() or self.logo or self.title.strip())

    @property
    def uses_masterpage(self) -> bool:
        return self.header_enabled or self.frame or bool(self.template)

    def validate(self) -> "DocStyle":
        self.body_size = max(7.0, min(16.0, float(self.body_size)))
        self.title_size = max(9.0, min(24.0, float(self.title_size)))
        self.academy_size = max(8.0, min(24.0, float(self.academy_size)))
        self.academy_sub_size = max(8.0, min(24.0, float(self.academy_sub_size)))
        self.academy_name = self.academy_name.strip()[:30]
        self.academy_sub = self.academy_sub.strip()[:30]
        self.title = self.title.strip()[:80]
        c = str(self.title_color or "").strip()
        self.title_color = c.upper() if re.fullmatch(r"#[0-9A-Fa-f]{6}", c) else "#000000"
        for name in ("body_font", "title_font"):
            v = str(getattr(self, name) or "").strip()[:40]
            setattr(self, name, v or DocStyle.__dataclass_fields__[name].default)
        if self.preset and self.template is None:
            from .presets import load
            self.template = load(self.preset)
            if self.template is None:
                raise ValueError(f"바탕쪽 프리셋 '{self.preset}'이 없습니다.")
        if self.template is not None:
            from .master_template import check_template
            check_template(self.template)  # TemplateError(ValueError)
        return self

    @classmethod
    def from_dict(cls, d: dict, logo: Optional[bytes] = None) -> "DocStyle":
        s = cls(
            body_font=str(d.get("body_font") or cls.body_font),
            title_font=str(d.get("title_font") or cls.title_font),
            body_size=float(d.get("body_size") or cls.body_size),
            academy_name=str(d.get("academy_name") or ""),
            academy_sub=str(d.get("academy_sub") or ""),
            academy_size=float(d.get("academy_size") or cls.academy_size),
            academy_sub_size=float(d.get("academy_sub_size") or cls.academy_sub_size),
            logo=logo,
            title=str(d.get("title") or ""),
            title_size=float(d.get("title_size") or cls.title_size),
            frame=bool(d.get("frame")),
            title_color=str(d.get("title_color") or "#000000"),
            answers_as_endnotes=bool(d.get("answers_as_endnotes")),
            auto_number=bool(d.get("auto_number", True)),
            preset=str(d.get("preset") or "")[:40],  # 바탕쪽 XML은 받지 않고 서버에 있는 프리셋 이름만
        )
        return s.validate()

    def summary(self) -> dict:
        return {"body_font": self.body_font, "title_font": self.title_font, "body_size": self.body_size,
                "academy_name": self.academy_name, "academy_sub": self.academy_sub,
                "academy_size": self.academy_size, "academy_sub_size": self.academy_sub_size,
                "logo": bool(self.logo), "title": self.title,
                "title_size": self.title_size, "frame": self.frame, "title_color": self.title_color,
                "answers_as_endnotes": self.answers_as_endnotes, "auto_number": self.auto_number,
                "preset": self.preset}
