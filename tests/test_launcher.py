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


def _ps1(name: str) -> str:
    data = (ROOT / "tools" / name).read_bytes()
    assert data.startswith(b"\xef\xbb\xbf") and b"\n" not in data.replace(b"\r\n", b"")  # 5.1: BOM + CRLF
    text = data.decode("utf-8-sig")
    assert "??" not in text and " && " not in text
    # PowerShell 은 대소문자를 가리지 않으므로 함수 이름이 aws/ssh 면 진짜 명령을 가려 무한 재귀가 된다
    import re
    assert not re.search(r"(?im)^function\s+(aws|ssh|scp|git)\b", text)
    return text


def test_deploy_scripts_encoding_and_safety():
    """배포 스크립트: 5.1 호환 인코딩, 초대 키·접속 키 파일은 git/도커 이미지에 들어가지 않음."""
    vm = _ps1("deploy_lightsail.ps1")  # 기본: Lightsail 인스턴스(가상 서버)
    for must in ("ap-northeast-2", "create-instances", "allocate-static-ip", "release-static-ip", "sslip.io",
                 "protocol=tcp", "download-default-key-pair", "icacls", "git archive", "tools/server/setup.sh",
                 "ACCESS_KEYS", "/join/", "-Delete", "-Ssh"):
        assert must in vm, must
    assert "fromPort=8000" not in vm  # 앱 포트는 밖에 열지 않는다(Caddy 를 거쳐서만)
    ct = _ps1("deploy_lightsail_container.ps1")
    for must in ("create-container-service", "push-container-image", "/healthz", "--scale 1"):
        assert must in ct, must
    assert "deploy/" in (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "deploy" in (ROOT / ".dockerignore").read_text(encoding="utf-8").split()


def test_server_setup_script():
    """서버 설치 스크립트: LF 줄바꿈(리눅스), 앱은 127.0.0.1 에만, Caddy 가 HTTPS 로 넘김, 키 파일은 root 만."""
    data = (ROOT / "tools" / "server" / "setup.sh").read_bytes()
    assert b"\r\n" not in data and data.startswith(b"#!/usr/bin/env bash")
    text = data.decode("utf-8")
    for must in ("set -euo pipefail", "HOST=127.0.0.1 PORT=8000", "reverse_proxy 127.0.0.1:8000",
                 "install -m 600", "EnvironmentFile=/etc/pdf2hwpx.env", "User=pdf2hwpx", "/healthz", "swapfile"):
        assert must in text, must
    assert "*.sh text eol=lf" in (ROOT / ".gitattributes").read_text(encoding="utf-8")
    import shutil
    import subprocess
    if shutil.which("bash"):
        assert subprocess.run(["bash", "-n", str(ROOT / "tools" / "server" / "setup.sh")]).returncode == 0


def test_dockerfile_installs_both_requirements():
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    # 같은 이름(requirements.txt) 두 개를 한 폴더로 복사하면 하나가 덮여 빌드가 깨진다
    assert "COPY requirements.txt webapp/requirements.txt" not in text
    assert "req/core.txt" in text and "req/web.txt" in text
