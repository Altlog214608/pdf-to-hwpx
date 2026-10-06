# PDF -> 한글 변환 사이트를 AWS Lightsail 컨테이너 서비스에 올립니다. (Windows PowerShell 5.1)
# (기본 배포는 인스턴스 방식 deploy_lightsail.ps1. 이 파일은 컨테이너 서비스 한도가 있는 계정용)
#
#   처음 / 코드를 고친 뒤:   powershell -ExecutionPolicy Bypass -File .\tools\deploy_lightsail_container.ps1
#   초대 링크만 다시 보기:   ... -File .\tools\deploy_lightsail_container.ps1 -Links
#   사이트 끄기(요금 중지):  ... -File .\tools\deploy_lightsail_container.ps1 -Delete
#
# 하는 일: 1) 준비물 확인(AWS CLI, Docker Desktop, 로그인, lightsailctl 자동 다운로드)
#          2) 초대 키 만들기(deploy\access_keys.txt, git 에 올라가지 않음)
#          3) 컨테이너 서비스가 없으면 만들기(서울, micro, 1대)  4) 이미지 빌드 + 올리기  5) 배포 + 초대 링크 출력
param(
    [string]$Service = 'pdf2hwpx',
    [string]$Region = 'ap-northeast-2',
    [string]$Power = 'micro',
    [string[]]$Names = @('me', 'guest'),
    [switch]$Links,
    [switch]$Delete
)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
$DeployDir = Join-Path $Root 'deploy'
$KeyFile = Join-Path $DeployDir 'access_keys.txt'
$Image = "$Service-web:latest"

function Say([string]$msg, [string]$color = 'Gray') { Write-Host $msg -ForegroundColor $color }
function Fail([string]$msg) { Say ''; Say $msg 'Red'; Say ''; exit 1 }
function Write-Utf8([string]$path, [string]$text) {
    # AWS CLI 는 BOM 이 붙은 JSON 을 못 읽으므로 BOM 없이 쓴다
    [IO.File]::WriteAllText($path, $text, (New-Object System.Text.UTF8Encoding($false)))
}

# aws 명령 실행: 오류 글자(stderr)도 받아서 돌려준다. (5.1 에서 2>&1 이 예외가 되지 않게 잠시 Continue)
function Invoke-Aws {
    $old = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    # stderr 줄은 5.1 에서 빈 RemoteException 으로 감싸져 나오므로 그 줄은 버린다
    $out = & aws @args --region $Region 2>&1 | ForEach-Object { "$_" } |
        Where-Object { $_ -ne 'System.Management.Automation.RemoteException' }
    $code = $LASTEXITCODE
    $ErrorActionPreference = $old
    return @{ ok = ($code -eq 0); text = ($out -join "`n") }
}

function Get-ServiceInfo {
    $r = Invoke-Aws lightsail get-container-services --service-name $Service --output json
    if (-not $r.ok) { return $null }
    return ($r.text | ConvertFrom-Json).containerServices[0]
}

function New-Key {
    $b = New-Object byte[] 18
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
    return ([Convert]::ToBase64String($b)).Replace('+', '-').Replace('/', '_').TrimEnd('=')
}

function Get-Keys {
    if (-not (Test-Path $KeyFile)) {
        New-Item -ItemType Directory -Force $DeployDir | Out-Null
        $lines = @('# 이름:키  (한 줄에 한 사람. 줄을 지우고 다시 배포하면 그 사람의 초대 링크가 끊깁니다)')
        foreach ($n in $Names) { $lines += ('{0}:{1}' -f $n, (New-Key)) }
        Write-Utf8 $KeyFile (($lines -join "`r`n") + "`r`n")
        Say "초대 키를 새로 만들었습니다: deploy\access_keys.txt (git 에 올라가지 않음)" 'Yellow'
    }
    $pairs = @(Get-Content $KeyFile -Encoding UTF8 | ForEach-Object { $_.Trim() } |
        Where-Object { $_ -and -not $_.StartsWith('#') -and $_ -match ':[A-Za-z0-9_-]{8,}$' })
    if ($pairs.Count -eq 0) { Fail "deploy\access_keys.txt 에 '이름:키' 줄이 없습니다. 파일을 지우고 다시 실행하면 새로 만듭니다." }
    return $pairs
}

function Show-Links($svc) {
    if (-not $svc -or -not $svc.url) { Say '아직 사이트 주소가 없습니다(배포 전).' 'Yellow'; return }
    $url = "$($svc.url)".TrimEnd('/')
    Say ''
    Say "사이트 주소: $url" 'Green'
    Say '초대 링크 (사람마다 따로 보내세요. 한 번 열면 그 브라우저는 180일 동안 계속 쓸 수 있습니다):' 'Green'
    foreach ($p in (Get-Keys)) {
        $i = $p.LastIndexOf(':')
        Say ('  {0,-10} {1}/join/{2}' -f $p.Substring(0, $i), $url, $p.Substring($i + 1)) 'White'
    }
    Say ''
}

function Wait-Service([scriptblock]$done, [string]$what, [int]$minutes = 20) {
    $until = (Get-Date).AddMinutes($minutes)
    while ((Get-Date) -lt $until) {
        $svc = Get-ServiceInfo
        $r = & $done $svc
        if ($r -eq 'ok') { return $svc }
        if ($r -eq 'fail') { return $null }
        Write-Host ("  {0} … ({1})" -f $what, $(if ($svc) { $svc.state } else { '?' })) -ForegroundColor DarkGray
        Start-Sleep -Seconds 15
    }
    Fail "$what 이(가) $minutes 분 안에 끝나지 않았습니다. Lightsail 콘솔에서 상태를 확인하세요."
}

# ---------------------------------------------------------------- 준비물 --
if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
    Fail ("AWS CLI 가 없습니다. 아래를 실행한 뒤 PowerShell 을 새로 열어 주세요.`n" +
          "  winget install -e --id Amazon.AWSCLI")
}
$who = Invoke-Aws sts get-caller-identity --output json
if (-not $who.ok) {
    Fail ("AWS 에 로그인되어 있지 않습니다. 아래 중 하나를 먼저 하세요.`n" +
          "  aws login --region $Region      (브라우저로 AWS 콘솔 로그인, AWS CLI 2.32 이상)`n" +
          "  aws configure                   (IAM 사용자 액세스 키)`n" + $who.text)
}
Say ("AWS 계정: " + (($who.text | ConvertFrom-Json).Account)) 'Cyan'

if ($Links) { Show-Links (Get-ServiceInfo); exit 0 }

if ($Delete) {
    $svc = Get-ServiceInfo
    if (-not $svc) { Say "'$Service' 서비스가 없습니다. 이미 꺼져 있습니다." 'Green'; exit 0 }
    Say "'$Service' 컨테이너 서비스를 지웁니다. 사이트가 꺼지고 요금이 더 나오지 않습니다." 'Yellow'
    $ans = Read-Host "지우려면 서비스 이름($Service)을 입력하세요"
    if ($ans -ne $Service) { Say '취소했습니다.'; exit 0 }
    $r = Invoke-Aws lightsail delete-container-service --service-name $Service
    if (-not $r.ok) { Fail $r.text }
    Say '지웠습니다. (다시 올리려면 -Delete 없이 실행)' 'Green'
    exit 0
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Fail ("Docker Desktop 이 없습니다. 아래를 실행하고 재부팅한 뒤 Docker Desktop 을 한 번 켜 주세요.`n" +
          "  winget install -e --id Docker.DockerDesktop")
}
$old = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
& docker info *> $null
$dockerOk = ($LASTEXITCODE -eq 0); $ErrorActionPreference = $old
if (-not $dockerOk) { Fail 'Docker Desktop 이 켜져 있지 않습니다. 시작 메뉴에서 Docker Desktop 을 켜고 고래 아이콘이 멈출 때까지 기다린 뒤 다시 실행하세요.' }

# lightsailctl: push-container-image 에 필요한 AWS 플러그인. 없으면 tools\bin 에 받아 둔다.
if (-not (Get-Command lightsailctl -ErrorAction SilentlyContinue)) {
    $bin = Join-Path $Root 'tools\bin'
    $exe = Join-Path $bin 'lightsailctl.exe'
    if (-not (Test-Path $exe)) {
        Say 'lightsailctl(Lightsail 이미지 업로드 도구)을 받는 중…' 'Cyan'
        New-Item -ItemType Directory -Force $bin | Out-Null
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -UseBasicParsing -Uri 'https://s3.us-west-2.amazonaws.com/lightsailctl/latest/windows-amd64/lightsailctl.exe' -OutFile $exe
    }
    $env:PATH = "$bin;$env:PATH"
}

$pairs = Get-Keys

# ------------------------------------------------------- 1. 컨테이너 서비스 --
$svc = Get-ServiceInfo
if (-not $svc) {
    Say "컨테이너 서비스 '$Service' 를 만듭니다 (서울, $Power, 1대). 몇 분 걸립니다." 'Cyan'
    $r = Invoke-Aws lightsail create-container-service --service-name $Service --power $Power --scale 1 --output json
    if (-not $r.ok) {
        if ($r.text -match 'maximum limit of Lightsail Container Services') {
            $all = Invoke-Aws lightsail get-container-services --query 'containerServices[].containerServiceName' --output text
            Fail ("이 계정의 Lightsail 컨테이너 서비스 한도에 걸렸습니다.`n" +
                  "  지금 서울 리전에 있는 서비스: " + $(if ($all.text.Trim()) { $all.text.Trim() } else { '(없음)' }) + "`n" +
                  "  - 다른 서비스가 있으면: -Service 그이름 으로 실행하거나, 안 쓰는 서비스를 지우세요.`n" +
                  "  - 없으면 새 계정의 한도가 0인 경우입니다. AWS Support Center 에서 한도 증가를 요청하세요`n" +
                  "    (Service limit increase > Lightsail > Container services, 리전 서울, 새 한도 1).`n" + $r.text)
        }
        Fail ("서비스를 만들지 못했습니다.`n" + $r.text)
    }
    $svc = Wait-Service { param($s) if ($s -and $s.state -in @('READY', 'RUNNING')) { 'ok' } } '서비스 준비 중'
}

# ------------------------------------------------------- 2. 이미지 빌드/업로드 --
Say '이미지를 만드는 중… (처음에는 몇 분)' 'Cyan'
& docker build --platform linux/amd64 -t $Image .
if ($LASTEXITCODE -ne 0) { Fail 'docker build 실패. 위의 오류를 확인하세요.' }

Say 'Lightsail 에 이미지를 올리는 중…' 'Cyan'
$r = Invoke-Aws lightsail push-container-image --service-name $Service --label web --image $Image
if (-not $r.ok) { Fail ("이미지를 올리지 못했습니다.`n" + $r.text) }
$m = [regex]::Match($r.text, 'Refer to this image as "([^"]+)"')
if (-not $m.Success) { Fail ("올린 이미지 이름을 찾지 못했습니다.`n" + $r.text) }
$imageRef = $m.Groups[1].Value
Say "올린 이미지: $imageRef" 'Cyan'

# ------------------------------------------------------- 3. 배포 --
$containers = @{
    web = @{
        image       = $imageRef
        ports       = @{ '8000' = 'HTTP' }
        environment = [ordered]@{
            ACCESS_KEYS     = ($pairs -join ',')
            JOB_TTL_MIN     = '30'
            DOWNLOAD_TTL_MIN = '10'
            MAX_FILES       = '10'
            MAX_TOTAL_PAGES = '200'
        }
    }
}
$endpoint = @{
    containerName = 'web'
    containerPort = 8000
    healthCheck   = @{ path = '/healthz'; intervalSeconds = 30; timeoutSeconds = 5
                       healthyThreshold = 2; unhealthyThreshold = 3; successCodes = '200' }
}
$cFile = Join-Path $DeployDir 'containers.json'
$eFile = Join-Path $DeployDir 'endpoint.json'
Write-Utf8 $cFile ($containers | ConvertTo-Json -Depth 6)
Write-Utf8 $eFile ($endpoint | ConvertTo-Json -Depth 6)
try {
    $r = Invoke-Aws lightsail create-container-service-deployment --service-name $Service `
        --containers "file://$cFile" --public-endpoint "file://$eFile" --output json
} finally {
    Remove-Item $cFile, $eFile -ErrorAction SilentlyContinue  # 초대 키가 들어 있으므로 바로 지운다
}
if (-not $r.ok) { Fail ("배포를 시작하지 못했습니다.`n" + $r.text) }
$ver = ($r.text | ConvertFrom-Json).containerService.nextDeployment.version
Say "배포 $ver 시작. 컨테이너가 켜지고 헬스체크를 통과할 때까지 기다립니다(보통 3~5분)." 'Cyan'

$svc = Wait-Service {
    param($s)
    if (-not $s) { return }
    if ($s.nextDeployment -and $s.nextDeployment.state -eq 'FAILED') { return 'fail' }
    if ($s.currentDeployment -and $s.currentDeployment.version -eq $ver) {
        if ($s.currentDeployment.state -eq 'FAILED') { return 'fail' }
        if ($s.currentDeployment.state -eq 'ACTIVE' -and $s.state -eq 'RUNNING') { return 'ok' }
    }
} '배포 중'
if (-not $svc) {
    Fail ("배포가 실패했습니다. 컨테이너 기록을 확인하세요:`n" +
          "  aws lightsail get-container-log --region $Region --service-name $Service --container-name web")
}
Say '배포 완료!' 'Green'
Show-Links $svc
Say '요금 알림을 아직 안 만들었다면: AWS 콘솔 > Billing and Cost Management > Budgets > 예산 생성(월 5달러 등).' 'Yellow'
