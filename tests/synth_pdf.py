"""2-x 계열 특징을 흉내 낸 합성 PDF 생성기 (회귀 테스트용).

한글 워드프로세서가 PDF로 내보낸 모양을 따라 한다.
- 2단(왼쪽 56.6~283.4, 오른쪽 311.8~538.6), 가운데 세로 구분선, 위/아래 전폭 배너 이미지
- 문단 테두리는 줄마다 끊긴 세로 선분 + 위/아래 가로 선분
- 원문자 ①~⑤는 작은 이미지 아이콘, 문제 번호는 큰 글씨
- 산문은 양쪽 정렬, 줄 끝 공백 글자 보존, 한글 글자 단위 줄나눔(단어 중간 끊김)도 포함
"""
from __future__ import annotations

import pymupdf as fitz

FONT = "korea"
SIZE = 9.1
COLS = [(56.6, 283.4), (311.8, 538.6)]
TOP, BOTTOM = 70.0, 780.0


def _icon_png(ch: str) -> bytes:
    d = fitz.open()
    p = d.new_page(width=40, height=40)
    p.insert_text((4, 32), ch, fontname=FONT, fontsize=34)
    return p.get_pixmap(matrix=fitz.Matrix(6, 6), alpha=False).tobytes("png")


def _picture_png(w: int, h: int, color: tuple[float, float, float]) -> bytes:
    d = fitz.open()
    p = d.new_page(width=w, height=h)
    p.draw_rect(fitz.Rect(0, 0, w, h), color=color, fill=color)
    p.draw_circle(fitz.Point(w / 2, h / 2), min(w, h) / 3, color=(1, 1, 1), fill=(1, 1, 1))
    return p.get_pixmap(alpha=False).tobytes("png")


ICONS = {ch: _icon_png(ch) for ch in "①②③④⑤"}


def tl(text: str, size: float = SIZE) -> float:
    return fitz.get_text_length(text, fontname=FONT, fontsize=size)


class Writer:
    def __init__(self):
        self.doc = fitz.open()
        self.page = None
        self.col = 0
        self.y = TOP
        self.first_page_pad = 0.0  # 첫 쪽 맨 위를 차지한 고지문 높이(두 단 모두 그 아래부터)
        self.new_page()

    def new_page(self):
        self.page = self.doc.new_page(width=595.2, height=841.9)
        banner = _picture_png(400, 10, (0.5, 0.5, 0.5))
        self.page.insert_image(fitz.Rect(56.6, 58, 538.6, 61), stream=banner, keep_proportion=False)
        self.page.insert_image(fitz.Rect(56.6, 784, 538.6, 787), stream=banner, keep_proportion=False)
        self.page.insert_text((333, 50), "[시험에 꼭 나오는 문제] 합성 테스트", fontname=FONT, fontsize=7.9)
        self.page.insert_text((516, 800), f"- {self.doc.page_count} -", fontname=FONT, fontsize=9.1)
        self.page.draw_line(fitz.Point(297.6, 72), fitz.Point(297.6, 772), width=0.24)
        self.col, self.y = 0, TOP + 10

    def next_col(self):
        if self.col == 0:
            self.col, self.y = 1, TOP + 10 + (self.first_page_pad if self.doc.page_count == 1 else 0)
        else:
            self.new_page()

    @property
    def left(self):
        return COLS[self.col][0]

    @property
    def right(self):
        return COLS[self.col][1]

    def text(self, x, y, s, size=SIZE):
        self.page.insert_text((x, y), s, fontname=FONT, fontsize=size)

    def icon(self, ch, x, y):
        self.page.insert_image(fitz.Rect(x, y - 7.6, x + 8.4, y + 0.8), stream=ICONS[ch])

    # 양쪽 정렬 줄: words는 (단어, 뒤 공백 여부)
    def justified(self, words: list[str], x0: float, x1: float, y: float, last: bool):
        widths = [tl(w.rstrip()) for w in words]
        gaps = len(words) - 1
        space = tl(" ")
        if last or gaps == 0:
            g = space
        else:
            g = max(space, (x1 - x0 - sum(widths)) / gaps)
        x = x0
        for i, w in enumerate(words):
            # 단어 뒤 공백 글자를 텍스트 레이어에 남긴다(마지막 단어 제외 — 줄 끝 공백은 trailing 처리)
            self.text(x, y, w + (" " if i < len(words) - 1 else ""))
            x += widths[i] + g

    def wrap(self, text: str, width: float, first_indent: float = 0.0, cont_indent: float = 0.0):
        """한글 워드프로세서식 줄나눔. 반환: [(줄 단어 목록, 줄 끝이 공백에서 끊겼는지, 들여쓰기)]"""
        lines = []
        words = text.split(" ")
        cur: list[str] = []
        ind = first_indent
        split_done: set[int] = set()
        i = 0
        while i < len(words):
            w = words[i]
            trial = " ".join(cur + [w])
            if tl(trial) <= width - ind:
                cur.append(w)
                i += 1
                continue
            if cur and len(w) >= 4 and i % 3 == 0 and w == words[i] and i not in split_done:
                # 글자 단위 줄나눔: 단어를 쪼개 남은 폭을 채운다
                k = len(w) - 1
                while k > 1 and tl(" ".join(cur + [w[:k]])) > width - ind:
                    k -= 1
                if k >= 2:
                    split_done.add(i)
                    lines.append((cur + [w[:k]], False, ind))
                    words[i] = w[k:]
                    cur, ind = [], cont_indent
                    continue
            lines.append((cur, True, ind))
            cur, ind = [], cont_indent
        if cur:
            lines.append((cur, False, ind))
        return lines


def vseg(page, x, y0, y1):
    page.draw_line(fitz.Point(x, y0), fitz.Point(x, y1), width=0.48)


def boxed_lines(w: Writer, rows):
    """rows: [(draw(y), height)] 를 한 박스로 그린다. 테두리는 줄마다 끊긴 세로 선분."""
    top = w.y
    y = top + 4
    for draw, h in rows:
        draw(y)
        y += h
    w.page.draw_line(fitz.Point(w.left, top), fitz.Point(w.right, top), width=0.48)
    w.page.draw_line(fitz.Point(w.left, y + 2), fitz.Point(w.right, y + 2), width=0.48)
    yy = top
    while yy < y + 2:
        vseg(w.page, w.left, yy, min(yy + 19.4, y + 2))
        vseg(w.page, w.right, yy, min(yy + 19.4, y + 2))
        yy += 19.0
    w.y = y + 10


def boxed_split(w: Writer, rows):
    """단 아래 끝까지 채우고 남은 줄은 다음 단 맨 위에서 이어지는 박스(제목 없음)로 그린다."""
    avail = BOTTOM - w.y - 8
    acc, k = 0.0, len(rows)
    for i, (_, h) in enumerate(rows):
        if acc + h > avail:
            k = i
            break
        acc += h
    boxed_lines(w, rows[:k])
    if k < len(rows):
        w.next_col()
        boxed_lines(w, rows[k:])


PROSE1 = ("어느 날 마을 사람들이 모여 오래된 우물가에서 이야기를 나누었는데 그 자리에 있던 노인이 "
          "지난 겨울의 일을 천천히 들려주기 시작하였다 사람들은 숨을 죽이고 노인의 이야기에 귀를 기울였으며 "
          "아이들은 어른들의 소매를 붙잡고 무서운 대목마다 눈을 감았다")
DIALOG = "“그날 밤에 무슨 일이 있었습니까?” 하고 물었다."
POEM = ["바람이 불어오는 언덕에서", "나는 오래 너를 기다렸다", None, "해가 지고 별이 뜨면", "그리움도 잠이 든다"]


NOTICE_LEFT = ["◇「콘텐츠산업 진흥법 시행령」제33조에 의한 표시", "1) 제작연월일 : 2024-12-31", "2) 제작자 : 합성출판㈜",
               "3) 이 콘텐츠는 「콘텐츠산업 진흥법」에 따라", "최초 제작일부터 5년간 보호됩니다."]
NOTICE_RIGHT = ["◇「콘텐츠산업 진흥법」외에도「저작권법」에 의하여 보호되", "는 콘텐츠의 경우, 그 콘텐츠의 전부 또는 일부를 무단으",
                "로 복제하거나 전송하는 것은 법적 책임을 질 수 있습니다."]


def _notice(w: "Writer") -> None:
    """첫 쪽 맨 위 출판사 고지문: 왼쪽 © 마크(박스 안 그림) + 법정 표시 5줄, 오른쪽 박스 안 경고문 3줄."""
    y = w.y
    mark = _picture_png(40, 40, (0.3, 0.3, 0.3))
    w.page.draw_rect(fitz.Rect(57, y, 100, y + 56), width=0.5)
    w.page.insert_image(fitz.Rect(62, y + 6, 95, y + 50), stream=mark, keep_proportion=False)
    for k, t in enumerate(NOTICE_LEFT):
        w.text(104, y + 10 + 11 * k, t, 6.6)
    w.page.draw_rect(fitz.Rect(330, y, 537, y + 56), width=0.5)
    for k, t in enumerate(NOTICE_RIGHT):
        w.text(335, y + 14 + 12 * k, t, 6.6)
    w.first_page_pad = 76.0
    w.y += 76.0


def build(path: str, answer_style: str = "bracket", start: int = 1, white_bg: tuple[int, ...] = (),
          notice: bool = False) -> dict:
    """answer_style: 'bracket' = '1) [정답] ③ / [해설] …', 'plain' = '1) 정답 ③ / 오답 point / …'(최다오답·최상위 공략형)
    start: 첫 문제 번호(단원 중간부터 시작하는 문제집 일부, 예: 13번부터)
    white_bg: 발문 줄 뒤에 선 없는 흰 사각형(한글이 내보내는 문단 배경, 보이지 않음)이 깔린 문제(몇 번째, 1부터)
    notice: 첫 쪽 맨 위에 출판사 저작권·콘텐츠 보호 고지문(© 마크 포함)"""
    w = Writer()
    if notice:
        _notice(w)
    # ---------- 지문 1: (가) 산문 + (나) 시, 단을 넘어가는 박스 ----------
    w.text(w.left, w.y, "※ 다음 글을 읽고 물음에 답하시오.", 7.9)
    w.y += 10
    rows = []

    def row_text(s, x_off=0.0):
        return (lambda y, s=s, x=x_off: w.text(w.left + 5 + x, y + 9, s)), 13.4

    rows.append(row_text("(가)"))
    for _ in range(9):
        for words, at_space, ind in w.wrap(PROSE1, 226.8 - 7.3, first_indent=8.0):
            rows.append(((lambda y, words=words, ind=ind, at_space=at_space:
                          w.justified([*words[:-1], words[-1] + (" " if at_space else "")], w.left + 5 + ind, w.right - 2.3, y + 9,
                                      last=False)), 13.4))
        rows[-1] = ((lambda y, words=words, ind=ind: w.justified(words, w.left + 5 + ind, w.right - 2.3, y + 9, last=True)), 13.4)
    rows.append(row_text(DIALOG, 8.0))
    rows.append(row_text("(나)"))
    for k, ln in enumerate(POEM):
        if k == 1:  # 시 행 왼쪽에 붙은 [A] 표시
            rows.append(((lambda y, ln=ln: (w.text(w.left + 5, y + 9, "[A]"), w.text(w.left + 45, y + 9, ln))), 13.4))
        else:
            rows.append(row_text(ln, 23.0) if ln else ((lambda y: None), 19.0))
    credit = "- 홍길동, 「시험」"
    rows.append(((lambda y: w.text(w.right - 2.3 - tl(credit), y + 9, credit)), 13.4))
    boxed_split(w, rows)

    badge = _picture_png(74, 40, (0.85, 0.45, 0.3))

    def question(n: int, stem: str, with_badge: bool = False, need: float = 120):
        if w.y > BOTTOM - need:
            w.next_col()
        if with_badge:  # 문제 위의 '빈출' 배지(장식 그림)
            w.page.insert_image(fitz.Rect(w.right - 37, w.y - 2, w.right, w.y + 18), stream=badge, keep_proportion=False)
            w.y += 20
        if n in white_bg:  # 실사용 PDF: 발문 두 줄 뒤에 흰색으로만 칠한 사각형(글자보다 먼저 그림)
            w.page.draw_rect(fitz.Rect(w.left, w.y - 1, w.right, w.y + 10), color=None, fill=(1, 1, 1))
            w.page.draw_rect(fitz.Rect(w.left, w.y + 10, w.right, w.y + 20), color=None, fill=(1, 1, 1))
        n = n + start - 1
        w.text(w.left, w.y + 14, f"{n}.", 13.7)
        w.text(w.left + (24 if n < 10 else 30), w.y + 13, stem)
        w.y += 24

    def choices(items: list[str], two_per_line: bool = False, credits: list[str] | None = None):
        if w.y > BOTTOM - 16 * len(items) * (2 if credits else 1):
            w.next_col()
        if two_per_line:
            for a in range(0, len(items), 2):
                for k, idx in enumerate(range(a, min(a + 2, len(items)))):
                    x = w.left + 10 + k * 110
                    w.icon("①②③④⑤"[idx], x, w.y + 9)
                    w.text(x + 13, w.y + 9, items[idx])
                w.y += 16
        else:
            for idx, s in enumerate(items):
                w.icon("①②③④⑤"[idx], w.left + 10, w.y + 9)
                w.text(w.left + 23, w.y + 9, s)
                w.y += 16
                if credits:  # 선택지 아래 오른쪽 정렬 출전
                    c = credits[idx]
                    w.text(w.right - 2.3 - tl(c), w.y + 9, c)
                    w.y += 16
        w.y += 20

    question(1, "(가)와 (나)에 대해 고른 것은?", with_badge=True)
    choices(["ㄱ, ㄴ", "ㄱ, ㄷ", "ㄴ, ㄷ", "ㄴ, ㄹ", "ㄷ, ㄹ"], two_per_line=True)

    # ---------- 2번: <보기> 안의 그림 ----------
    question(2, "<보기>는 영상 시의 장면이다.")
    pic = _picture_png(200, 120, (0.2, 0.4, 0.8))

    def draw_pic(y):
        w.page.insert_image(fitz.Rect(w.left + 40, y, w.left + 180, y + 80), stream=pic)
    title = "<보기>"
    rows = [((lambda y: w.text((w.left + w.right) / 2 - tl(title) / 2, y + 9, title)), 19.0),
            (draw_pic, 84.0),
            ((lambda y: w.text(w.right - 2.3 - tl("- 영상 시에서"), y + 9, "- 영상 시에서")), 13.4)]
    boxed_lines(w, rows)
    choices(["청각 정보를 준다.", "시각 정보만 준다.", "상상력이 제한된다.", "감상이 어렵다.", "주체적 감상이 가능하다."])

    # ---------- 3번: 도식 박스 ----------
    question(3, "<보기>의 Ⓐ에 들어갈 장소는?")

    def draw_diagram(y):
        for k, label in enumerate(["병원", "무악재", "Ⓐ"]):
            x = w.left + 15 + k * 70
            w.page.draw_rect(fitz.Rect(x, y, x + 45, y + 20), width=0.6)
            w.text(x + 8, y + 14, label)
            if k < 2:
                w.page.draw_line(fitz.Point(x + 47, y + 10), fitz.Point(x + 68, y + 10), width=0.6)
                w.text(x + 52, y + 13, "→")
    rows = [((lambda y: w.text((w.left + w.right) / 2 - tl(title) / 2, y + 9, title)), 19.0), (draw_diagram, 26.0)]
    boxed_lines(w, rows)
    choices(["현저동", "서울역", "부산", "인천", "평양"], credits=[f"- 작가{k}, <작품{k}>" for k in range(1, 6)])

    # ---------- 4번: 서술형 + <조건> '-' 항목 ----------
    question(4, "마지막 장면을 <조건>에 맞게 쓰시오.")
    t2 = "<조건>"
    rows = [((lambda y: w.text((w.left + w.right) / 2 - tl(t2) / 2, y + 9, t2)), 19.0),
            ((lambda y: w.text(w.left + 5, y + 9, "- 작품의 주제를 먼저 언급할 것.")), 13.4),
            ((lambda y: w.text(w.left + 5, y + 9, "- 인물의 행동을 근거로 들 것.")), 13.4)]
    boxed_lines(w, rows)
    sub = "(2) 위에서 답한 장면이 작품 전체의 주제를 드러내는 데 어떤 역할을 하는지 구체적인 근거를 들어 서술하시오."
    for words, at_space, ind in w.wrap(sub, 226.8 - 20, cont_indent=12.0):
        w.justified([*words[:-1], words[-1] + (" " if at_space else "")], w.left + 8 + ind, w.right - 2.3, w.y + 9, last=not at_space)
        w.y += 13.4
    w.y += 12

    # ---------- 지문 2: 그림만 있는 지문 ----------
    if w.y > BOTTOM - 260:
        w.next_col()
    w.text(w.left, w.y, "※ 다음 글을 읽고 물음에 답하시오.", 7.9)
    w.y += 10
    pic2 = _picture_png(160, 100, (0.8, 0.3, 0.2))
    rows = [((lambda y: w.page.insert_image(fitz.Rect(w.left + 30, y, w.left + 190, y + 90), stream=pic2)), 94.0),
            ((lambda y: w.page.insert_image(fitz.Rect(w.left + 30, y, w.left + 190, y + 90), stream=pic2)), 94.0),
            ((lambda y: w.text(w.right - 2.3 - tl("- 김작가 그림, 「만화」"), y + 9, "- 김작가 그림, 「만화」")), 13.4)]
    boxed_lines(w, rows)

    # ---------- 5번: <보기 1> 산문+출전, <보기 2> 그림만 ----------
    question(5, "<보기 1>을 <보기 2>로 바꾼 효과는?", need=330)
    t3, t4 = "<보기 1>", "<보기 2>"
    prose2 = "이른바 1·4 후퇴였다 거의 다 떠난 줄 알았는데 행여나 하고 관망하던 사람들이 한꺼번에 쏟아져 나와 국도를 질주하였다"
    rows = [((lambda y: w.text((w.left + w.right) / 2 - tl(t3) / 2, y + 9, t3)), 19.0)]
    wrapped = w.wrap(prose2, w.right - 2.3 - w.left - 5, first_indent=8.0)
    for i, (words, at_space, ind) in enumerate(wrapped):
        last = i == len(wrapped) - 1
        rows.append(((lambda y, words=words, ind=ind, last=last, at_space=at_space:
                      w.justified([*words[:-1], words[-1] + (" " if at_space and not last else "")],
                                  w.left + 5 + ind, w.right - 2.3, y + 9, last)), 13.4))
    rows.append(((lambda y: w.text(w.right - 2.3 - tl("- 박완서, 소설"), y + 9, "- 박완서, 소설")), 13.4))
    boxed_lines(w, rows)
    rows = [((lambda y: w.text((w.left + w.right) / 2 - tl(t4) / 2, y + 9, t4)), 19.0),
            ((lambda y: w.page.insert_image(fitz.Rect(w.left + 30, y, w.left + 170, y + 70), stream=pic)), 74.0)]
    boxed_lines(w, rows)
    choices(["생동감이 커진다.", "갈등이 사라진다.", "시점이 바뀐다.", "배경이 바뀐다.", "주제가 바뀐다."])
    rows = [((lambda y: w.text(w.left + 5, y + 9, "2. 서사 갈래의 이해")), 13.4),
            ((lambda y: w.text(w.left + 5, y + 9, "(1) 단원 제목 박스")), 13.4)]
    if w.y > BOTTOM - 60:
        w.next_col()
    boxed_lines(w, rows)

    # ---------- 정답 및 해설 ----------
    w.new_page()
    for n, ans in enumerate(["③", "⑤", "①", "주제는 그리움이다.", "①"], start=start):
        head = f"{n}) [정답] " if answer_style == "bracket" else f"{n}) 정답 "
        w.text(w.left + 10, w.y + 9, head)
        if ans in ICONS:
            w.icon(ans, w.left + 10 + tl(head), w.y + 9)
        else:
            w.text(w.left + 10 + tl(head), w.y + 9, ans)
        w.y += 13
        if answer_style == "plain":
            w.text(w.left + 10, w.y + 9, "오답 point")
            w.y += 13
        lead = "[해설] 해설 첫 줄입니다. " if answer_style == "bracket" else "해설 첫 줄입니다. "
        w.text(w.left + 10, w.y + 9, lead)
        w.icon("②", w.left + 10 + tl(lead), w.y + 9)
        w.text(w.left + 22 + tl(lead), w.y + 9, "는 오답이다.")
        w.y += 22
    w.doc.save(path)
    return {"questions": 5, "objective": 4, "subjective": 1}


def build_tables(path: str) -> dict:
    """표·묶음 괄호 특징(족보닷컴 형식): [A] 괄호 지문, <보기> 안 표(병합 칸·칸 색·칸 안 그림), 표 모양 선택지."""
    w = Writer()
    w.text(w.left, w.y, "※ 다음 글을 읽고 물음에 답하시오.", 7.9)
    w.y += 10
    lines = ["산 너머 남촌에는 누가 살길래", "해마다 봄바람이 남으로 오네", "꽃 피는 사월이면 진달래 향기",
             "밀 익는 오월이면 보리 내음새", "어느 것 한 가진들 실어 안 오리", "남촌서 남풍 불 제 나는 좋데나"]
    top = w.y
    y = top + 4
    bx = w.left + 22  # 괄호 세로선 x
    br0, br1 = y + 13.4 * 1 + 1, y + 13.4 * 5 - 1  # 2~5행을 묶는다
    for k, ln in enumerate(lines):
        w.text(w.left + 34, y + 9, ln)
        y += 13.4
    mid = (br0 + br1) / 2
    w.text(w.left + 13, mid + 3, "[A]")
    w.page.draw_line(fitz.Point(bx, br0), fitz.Point(bx, mid - 7), width=0.5)
    w.page.draw_line(fitz.Point(bx, mid + 7), fitz.Point(bx, br1), width=0.5)
    w.page.draw_line(fitz.Point(bx, br0), fitz.Point(bx + 8, br0), width=0.5)
    w.page.draw_line(fitz.Point(bx, br1), fitz.Point(bx + 8, br1), width=0.5)
    w.page.draw_line(fitz.Point(w.left, top), fitz.Point(w.right, top), width=0.48)
    w.page.draw_line(fitz.Point(w.left, y + 2), fitz.Point(w.right, y + 2), width=0.48)
    vseg(w.page, w.left, top, y + 2)
    vseg(w.page, w.right, top, y + 2)
    w.y = y + 14

    w.text(w.left, w.y + 14, "1.", 13.7)
    w.text(w.left + 24, w.y + 13, "<보기>의 ㉠에 들어갈 말로 알맞은 것은?")
    w.y += 26
    top = w.y
    w.text((w.left + w.right) / 2 - tl("<보기>") / 2, top + 13, "<보기>")
    w.text(w.left + 8, top + 30, "다음 표는 [A]를 정리한 것이다.")
    # 줄 안의 빈칸 네모: "주제 : [        ]" (글자 없는 작은 사각형, 선 4개)
    w.text(w.left + 8, top + 132, "주제 :")
    bx0 = w.left + 8 + tl("주제 :") + 4
    bx1, by0, by1 = bx0 + 120, top + 123, top + 134
    for a1, a2 in (((bx0, by0), (bx1, by0)), ((bx0, by1), (bx1, by1)), ((bx0, by0), (bx0, by1)), ((bx1, by0), (bx1, by1))):
        w.page.draw_line(fitz.Point(*a1), fitz.Point(*a2), width=0.3)
    # 표: 3열 x 3행, 1행 첫 칸은 2행까지 병합, 1행 머리 칸 색, 3행 가운데 칸에 그림
    tx0, tx1 = w.left + 10, w.right - 10
    xs = [tx0, tx0 + 60, tx0 + 135, tx1]
    ys = [top + 40, top + 58, top + 76, top + 116]
    w.page.draw_rect(fitz.Rect(xs[1], ys[0], xs[3], ys[1]), color=None, fill=(0.85, 0.93, 0.82))
    for yy in ys:
        w.page.draw_line(fitz.Point(xs[0] if yy in (ys[0], ys[2], ys[3]) else xs[1], yy), fitz.Point(xs[3], yy), width=0.5)
    for xx in xs:
        w.page.draw_line(fitz.Point(xx, ys[0]), fitz.Point(xx, ys[3]), width=0.5)
    def ctext(c: int, y: float, t: str):  # 칸 가운데 정렬
        w.text((xs[c] + xs[c + 1]) / 2 - tl(t) / 2, y, t)
    ctext(0, ys[1] + 3, "구분")
    ctext(1, ys[0] + 12, "계절")
    ctext(2, ys[0] + 12, "소재")
    ctext(1, ys[1] + 12, "사월")
    ctext(2, ys[1] + 12, "진달래")
    ctext(0, ys[2] + 24, "오월")
    w.page.insert_image(fitz.Rect(xs[1] + 15, ys[2] + 6, xs[2] - 15, ys[3] - 6), stream=_picture_png(60, 40, (0.4, 0.6, 0.8)))
    ctext(2, ys[2] + 24, "㉠")
    bottom = ys[3] + 30
    w.page.draw_line(fitz.Point(w.left, top), fitz.Point(w.right, top), width=0.48)
    w.page.draw_line(fitz.Point(w.left, bottom), fitz.Point(w.right, bottom), width=0.48)
    vseg(w.page, w.left, top, bottom)
    vseg(w.page, w.right, top, bottom)
    w.y = bottom + 8
    w.text(w.left + 30, w.y + 9, "㉠")
    w.text(w.left + 110, w.y + 9, "㉡")
    w.y += 16
    for idx, (a1, a2) in enumerate([("보리", "남풍"), ("밀", "북풍"), ("쌀", "동풍"), ("콩", "서풍"), ("팥", "남풍")]):
        w.icon("①②③④⑤"[idx], w.left + 10, w.y + 9)
        w.text(w.left + 30, w.y + 9, a1)
        w.text(w.left + 110, w.y + 9, a2)
        w.y += 16
    w.new_page()
    w.text(w.left + 10, w.y + 9, "1) [정답] ")
    w.icon("①", w.left + 10 + tl("1) [정답] "), w.y + 9)
    w.doc.save(path)
    return {"questions": 1}


if __name__ == "__main__":
    import sys
    print(build(sys.argv[1] if len(sys.argv) > 1 else "synth.pdf"))
