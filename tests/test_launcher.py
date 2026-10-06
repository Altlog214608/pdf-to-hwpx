"""Windows 더블클릭 실행 파일: 줄바꿈/인코딩이 깨지면 cmd/PowerShell 에서 한글이 깨지거나 실행이 안 된다."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_bat_is_ascii_crlf():
    data = (ROOT / "실행하기.bat").read_bytes()
    data.decode("ascii")  # cmd 는 한국어 Windows 에서 CP949 로 읽으므로 한글을 넣지 않는다
    assert b"\r\n" in data and b"\n" not in data.replace(b"\r\n", b"")
    assert b"tools\\start_web.ps1" in data and b"-ExecutionPolicy Bypass" in data


def test_ps1_is_utf8_bom_crlf():
    data = (ROOT / "tools" / "start_web.ps1").read_bytes()
    assert data.startswith(b"\xef\xbb\xbf")  # Windows PowerShell 5.1 은 BOM 이 있어야 UTF-8 로 읽는다
    assert b"\n" not in data.replace(b"\r\n", b"")
    text = data.decode("utf-8-sig")
    for must in ("winget", "Python.Python.3.12", "--scope user", ".venv", "webapp\\server.py", "/healthz"):
        assert must in text
    # 5.1 에 없는 문법(삼항, ??, &&) 금지
    assert "??" not in text and " && " not in text
