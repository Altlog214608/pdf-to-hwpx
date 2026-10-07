#!/usr/bin/env bash
# Lightsail 인스턴스(Ubuntu)에서 실행: 앱 설치/갱신 + systemd 서비스 + Caddy(HTTPS 자동 발급).
# tools/deploy_lightsail.ps1 이 소스 묶음을 올린 뒤 `sudo bash setup.sh <주소>` 로 부른다. 여러 번 실행해도 된다.
set -euo pipefail
HOST="${1:?사용법: setup.sh <주소 예: 13-125-1-2.sslip.io>}"
SRC="$(cd "$(dirname "$0")/../.." && pwd)"
APP=/opt/pdf2hwpx
export DEBIAN_FRONTEND=noninteractive

say() { echo "[setup] $*"; }

# ---- 스왑 1GB: 메모리 1GB 서버에서 통합본(여러 PDF)을 만들 때 넘치지 않게
if ! swapon --show | grep -q .; then
  say "스왑 1GB 만들기"
  fallocate -l 1G /swapfile && chmod 600 /swapfile && mkswap /swapfile >/dev/null && swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

# ---- 패키지: python venv, Caddy, 보안 자동 업데이트
need=()
dpkg -s python3-venv >/dev/null 2>&1 || need+=(python3-venv)
dpkg -s unattended-upgrades >/dev/null 2>&1 || need+=(unattended-upgrades)
if [ ${#need[@]} -gt 0 ] || ! command -v caddy >/dev/null; then
  say "패키지 설치: ${need[*]} caddy"
  apt-get update -q
  [ ${#need[@]} -gt 0 ] && apt-get install -y -q "${need[@]}"
  if ! command -v caddy >/dev/null && ! apt-get install -y -q caddy; then
    say "Ubuntu 저장소에 caddy 가 없어 공식 저장소를 추가"
    apt-get install -y -q debian-keyring debian-archive-keyring apt-transport-https curl gnupg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor --yes -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' > /etc/apt/sources.list.d/caddy-stable.list
    apt-get update -q
    apt-get install -y -q caddy
  fi
fi

# ---- 앱 사용자와 파일
id pdf2hwpx >/dev/null 2>&1 || useradd --system --home-dir "$APP" --shell /usr/sbin/nologin pdf2hwpx
mkdir -p "$APP"
rm -rf "$APP/app.new"
mkdir -p "$APP/app.new"
cp -r "$SRC/pdf2hwpx" "$SRC/webapp" "$SRC/requirements.txt" "$APP/app.new/"
rm -rf "$APP/app.old"
[ -d "$APP/app" ] && mv "$APP/app" "$APP/app.old"
mv "$APP/app.new" "$APP/app"

# ---- 부품(venv): requirements 가 바뀔 때만 다시 설치. pytest(테스트용)는 빼고.
[ -x "$APP/venv/bin/python" ] || python3 -m venv "$APP/venv"
grep -v pytest "$APP/app/requirements.txt" > "$APP/req-core.txt"
STAMP="$(cat "$APP/req-core.txt" "$APP/app/webapp/requirements.txt" | sha256sum | cut -d' ' -f1)"
if [ "$(cat "$APP/venv/installed.txt" 2>/dev/null || true)" != "$STAMP" ]; then
  say "부품 설치(처음 한 번, 몇 분)"
  "$APP/venv/bin/pip" install -q --upgrade pip
  "$APP/venv/bin/pip" install -q -r "$APP/req-core.txt" -r "$APP/app/webapp/requirements.txt"
  echo "$STAMP" > "$APP/venv/installed.txt"
fi
chown -R root:root "$APP"

# ---- 설정(초대 키). 배포 스크립트가 /tmp/pdf2hwpx.env 로 올린다.
if [ -f /tmp/pdf2hwpx.env ]; then
  install -m 600 -o root -g root /tmp/pdf2hwpx.env /etc/pdf2hwpx.env
  rm -f /tmp/pdf2hwpx.env
fi
[ -f /etc/pdf2hwpx.env ] || { echo "/etc/pdf2hwpx.env 가 없습니다" >&2; exit 1; }

# ---- systemd 서비스: 내부 127.0.0.1:8000 (밖에서는 Caddy 를 거쳐서만)
cat > /etc/systemd/system/pdf2hwpx.service <<UNIT
[Unit]
Description=PDF to HWPX web
After=network.target

[Service]
User=pdf2hwpx
EnvironmentFile=/etc/pdf2hwpx.env
Environment=HOST=127.0.0.1 PORT=8000 DATA_DIR=/var/lib/pdf2hwpx/jobs PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 TZ=Asia/Seoul
WorkingDirectory=$APP/app
ExecStart=$APP/venv/bin/python webapp/server.py
StateDirectory=pdf2hwpx
Restart=always
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true

[Install]
WantedBy=multi-user.target
UNIT

# ---- Caddy: 주소로 들어오면 HTTPS 인증서를 자동으로 받고 앱으로 넘긴다
cat > /etc/caddy/Caddyfile <<CADDY
$HOST {
	encode gzip
	request_body {
		max_size 60MB
	}
	reverse_proxy 127.0.0.1:8000
}
CADDY

systemctl daemon-reload
systemctl enable pdf2hwpx >/dev/null 2>&1
systemctl restart pdf2hwpx
systemctl enable caddy >/dev/null 2>&1
systemctl restart caddy

for i in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8000/healthz >/dev/null 2>&1; then
    say "앱 실행 확인: $(curl -fsS http://127.0.0.1:8000/healthz)"
    rm -rf "$APP/app.old"
    case "$SRC" in /tmp/*) rm -rf "$SRC" ;; esac  # 올려 보낸 임시 소스만 지운다
    exit 0
  fi
  sleep 1
done
echo "앱이 켜지지 않았습니다. 기록:" >&2
journalctl -u pdf2hwpx -n 40 --no-pager >&2
exit 1
