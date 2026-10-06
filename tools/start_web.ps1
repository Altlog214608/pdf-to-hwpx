# PDF -> 한글(HWPX) 변환 사이트를 이 컴퓨터에서 실행합니다. (실행하기.bat 이 호출)
# Windows PowerShell 5.1 기준으로 작성(별도 설치 불필요).
# 1) Python 확인, 없으면 winget 으로 사용자 설치  2) 프로그램 폴더 안 .venv 에 부품 설치(처음 한 번)
# 3) 서버 실행 후 브라우저 열기. 이 창을 닫으면 서버도 꺼집니다.
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
$Host.UI.RawUI.WindowTitle = 'PDF -> 한글 변환기 (이 창을 닫으면 꺼집니다)'

function Say([string]$msg, [string]$color = 'Gray') { Write-Host $msg -ForegroundColor $color }
function Fail([string]$msg) {
    Say ''
    Say $msg 'Red'
    Say ''
    Read-Host '엔터를 누르면 창이 닫힙니다'
    exit 1
}

function Test-PythonExe([string]$exe) {
    # 3.10 이상인 진짜 Python 인지 확인 (Microsoft Store 로 연결만 해 주는 가짜 python.exe 는 제외)
    if (-not $exe -or -not (Test-Path $exe)) { return $false }
    if ($exe -like '*\WindowsApps\*') { return $false }
    try {
        $v = & $exe -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        if (-not $v) { return $false }
        $p = "$v".Trim().Split('.')
        return ([int]$p[0] -eq 3 -and [int]$p[1] -ge 10)
    } catch { return $false }
}

function Find-Python {
    $cands = @()
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        try {
            $exe = & $py.Source -3 -c "import sys; print(sys.executable)" 2>$null
            if ($exe) { $cands += "$exe".Trim() }
        } catch { }
    }
    foreach ($c in (Get-Command python -All -ErrorAction SilentlyContinue)) { $cands += $c.Source }
    foreach ($base in @("$env:LOCALAPPDATA\Programs\Python", "$env:ProgramFiles\Python*", "$env:ProgramFiles\Python")) {
        Get-ChildItem -Path $base -Filter python.exe -Recurse -Depth 2 -ErrorAction SilentlyContinue |
            Sort-Object FullName -Descending | ForEach-Object { $cands += $_.FullName }
    }
    foreach ($c in $cands) { if (Test-PythonExe $c) { return $c } }
    return $null
}

Say ''
Say '  PDF -> 한글(HWPX) 변환기' 'Cyan'
Say '  ----------------------------------------------'

# ---- 1. Python ----
$venvPy = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-PythonExe $venvPy)) {
    $python = Find-Python
    if (-not $python) {
        Say '[1/3] Python 이 없어 설치합니다. (몇 분 걸릴 수 있어요)' 'Yellow'
        $winget = Get-Command winget -ErrorAction SilentlyContinue
        if (-not $winget) {
            Fail ("자동 설치 도구(winget)를 찾지 못했습니다.`n" +
                  "https://www.python.org/downloads/ 에서 Python 을 설치한 뒤(설치 첫 화면의 'Add python.exe to PATH' 체크)`n" +
                  "이 파일을 다시 실행해 주세요.")
        }
        & $winget.Source install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
        $python = Find-Python
        if (-not $python) {
            Fail ("Python 자동 설치에 실패했습니다.`n" +
                  "https://www.python.org/downloads/ 에서 직접 설치한 뒤(설치 첫 화면의 'Add python.exe to PATH' 체크)`n" +
                  "이 파일을 다시 실행해 주세요.")
        }
    }
    Say "[1/3] Python: $python" 'Green'
    Say '[2/3] 프로그램 전용 환경을 만듭니다...'
    & $python -m venv (Join-Path $Root '.venv')
    if ($LASTEXITCODE -ne 0 -or -not (Test-PythonExe $venvPy)) { Fail '프로그램 전용 환경(.venv)을 만들지 못했습니다.' }
} else {
    Say '[1/3] Python 준비됨' 'Green'
}

# ---- 2. 부품 설치 (requirements 가 바뀌었을 때만) ----
$reqs = @('requirements.txt', 'webapp\requirements.txt') | ForEach-Object { Join-Path $Root $_ }
$stamp = Join-Path $Root '.venv\installed.txt'
$want = ($reqs | ForEach-Object { (Get-FileHash $_ -Algorithm SHA256).Hash }) -join ','
$have = ''
if (Test-Path $stamp) { $have = (Get-Content $stamp -Raw).Trim() }
if ($have -ne $want) {
    Say '[2/3] 필요한 부품을 설치합니다. (처음 한 번, 몇 분 걸려요)' 'Yellow'
    & $venvPy -m pip install --disable-pip-version-check -q --upgrade pip
    & $venvPy -m pip install --disable-pip-version-check -q -r $reqs[0] -r $reqs[1]
    if ($LASTEXITCODE -ne 0) { Fail '부품 설치에 실패했습니다. 인터넷 연결을 확인하고 다시 실행해 주세요.' }
    Set-Content -Path $stamp -Value $want -Encoding ASCII
}
Say '[2/3] 부품 준비됨' 'Green'

# ---- 3. 서버 실행 + 브라우저 ----
function Test-Url([string]$url) {
    try { Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2 | Out-Null; return $true } catch { return $false }
}
function Test-PortFree([int]$port) {
    try {
        $l = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, $port)
        $l.Start(); $l.Stop(); return $true
    } catch { return $false }
}

if (Test-Url 'http://127.0.0.1:8000/healthz') {
    Say '[3/3] 이미 실행 중입니다. 브라우저를 엽니다.' 'Green'
    Start-Process 'http://127.0.0.1:8000'
    Start-Sleep -Seconds 3
    exit 0
}
$port = 8000
while (-not (Test-PortFree $port) -and $port -lt 8020) { $port++ }
$env:HOST = '127.0.0.1'
$env:PORT = "$port"
$url = "http://127.0.0.1:$port"

Say "[3/3] 서버를 켭니다: $url" 'Green'
$server = Start-Process -FilePath $venvPy -ArgumentList @('webapp\server.py') -WorkingDirectory $Root -NoNewWindow -PassThru
$ok = $false
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Milliseconds 500
    if ($server.HasExited) { break }
    if (Test-Url "$url/healthz") { $ok = $true; break }
}
if (-not $ok) { Fail '서버가 켜지지 않았습니다. 위에 나온 오류 메시지를 캡처해서 보내 주세요.' }

Start-Process $url
Say ''
Say "  브라우저에서 $url 이 열렸어요." 'Cyan'
Say '  사용하는 동안 이 창은 켜 두세요. 다 쓰면 이 창을 닫으면 됩니다.' 'Cyan'
Say ''
try { Wait-Process -Id $server.Id } finally { if (-not $server.HasExited) { Stop-Process -Id $server.Id -Force } }
