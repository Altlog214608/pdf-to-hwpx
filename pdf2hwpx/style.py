"""출력 HWPX의 문서 스타일 옵션 (웹 화면/CLI에서 지정)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# 한글에서 흔히 쓰는 글꼴. 사용자 PC에 없으면 한글이 비슷한 글꼴로 대체해서 연다.
FONTS = ["함초롬바탕", "함초롬돋움", "맑은 고딕", "바탕", "돋움", "나눔명조", "나눔고딕"]


@dataclass
class DocStyle:
    body_font: str = "함초롬바탕"   # 본문(지문·문제·선택지·해설) 글꼴
    title_font: str = "함초롬돋움"  # 바탕쪽 제목/학원 이름 글꼴
    body_size: float = 10.0          # 본문 글자 크기(pt)
    academy_name: str = ""           # 바탕쪽 왼쪽 위 학원 이름(검은 칸에 흰 글씨)
    logo: Optional[bytes] = None     # 학원 로고 그림(PNG/JPG). 있으면 이름 대신 사용
    title: str = ""                  # 바탕쪽 제목, 예: "[중간 대비] 2. 품격을 높이는 언어생활 ①"
    title_size: float = 14.0
    frame: bool = False              # 페이지 바깥 네모 테두리
    extra: dict = field(default_factory=dict)

    @property
    def header_enabled(self) -> bool:
        return bool(self.academy_name.strip() or self.logo or self.title.strip())

    @property
    def uses_masterpage(self) -> bool:
        return self.header_enabled or self.frame

    def validate(self) -> "DocStyle":
        self.body_size = max(7.0, min(16.0, float(self.body_size)))
        self.title_size = max(9.0, min(24.0, float(self.title_size)))
        self.academy_name = self.academy_name.strip()[:30]
        self.title = self.title.strip()[:80]
        for name in ("body_font", "title_font"):
            v = str(getattr(self, name) or "").strip()[:40]
            setattr(self, name, v or DocStyle.__dataclass_fields__[name].default)
        return self

    @classmethod
    def from_dict(cls, d: dict, logo: Optional[bytes] = None) -> "DocStyle":
        s = cls(
            body_font=str(d.get("body_font") or cls.body_font),
            title_font=str(d.get("title_font") or cls.title_font),
            body_size=float(d.get("body_size") or cls.body_size),
            academy_name=str(d.get("academy_name") or ""),
            logo=logo,
            title=str(d.get("title") or ""),
            title_size=float(d.get("title_size") or cls.title_size),
            frame=bool(d.get("frame")),
        )
        return s.validate()

    def summary(self) -> dict:
        return {"body_font": self.body_font, "title_font": self.title_font, "body_size": self.body_size,
                "academy_name": self.academy_name, "logo": bool(self.logo), "title": self.title,
                "title_size": self.title_size, "frame": self.frame}
