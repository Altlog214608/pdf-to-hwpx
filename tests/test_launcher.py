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


def test_deploy_script_encoding_and_safety():
    """Lightsail 배포 스크립트: 5.1 호환 인코딩, 초대 키 파일은 git/도커 이미지에 들어가지 않음."""
    data = (ROOT / "tools" / "deploy_lightsail.ps1").read_bytes()
    assert data.startswith(b"\xef\xbb\xbf") and b"\n" not in data.replace(b"\r\n", b"")
    text = data.decode("utf-8-sig")
    assert "??" not in text and " && " not in text
    for must in ("ap-northeast-2", "create-container-service", "push-container-image", "/healthz",
                 "ACCESS_KEYS", "/join/", "--scale 1", "-Delete"):
        assert must in text, must
    # PowerShell 은 대소문자를 가리지 않으므로 함수 이름이 aws 면 aws.exe 를 가려 무한 재귀가 된다
    import re
    assert not re.search(r"(?im)^function\s+aws\b", text)
    assert "deploy/" in (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "deploy" in (ROOT / ".dockerignore").read_text(encoding="utf-8").split()


def test_dockerfile_installs_both_requirements():
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    # 같은 이름(requirements.txt) 두 개를 한 폴더로 복사하면 하나가 덮여 빌드가 깨진다
    assert "COPY requirements.txt webapp/requirements.txt" not in text
    assert "req/core.txt" in text and "req/web.txt" in text
