# PDF -> 한글 변환 사이트를 AWS Lightsail 인스턴스(가상 서버, 서울)에 올립니다. (Windows PowerShell 5.1)
#
#   처음 / 코드를 고친 뒤:   powershell -ExecutionPolicy Bypass -File .\tools\deploy_lightsail.ps1
#   초대 링크만 다시 보기:   ... -File .\tools\deploy_lightsail.ps1 -Links
#   서버에 직접 접속(문제 확인): ... -File .\tools\deploy_lightsail.ps1 -Ssh
#   사이트 끄기(요금 중지):  ... -File .\tools\deploy_lightsail.ps1 -Delete
#
# 구성: Ubuntu 1GB 서버 1대 + 고정 IP. 서버 안에서 앱(127.0.0.1:8000)을 systemd 로 돌리고,
#       Caddy 가 https://<IP>.sslip.io 주소의 인증서를 자동으로 받아 앱으로 넘긴다(tools/server/setup.sh).
# 올리는 코드는 지금 브랜치의 마지막 커밋(git archive)이다. 고치지 않은(커밋 안 한) 변경은 올라가지 않는다.
param(
    [string]$Name = 'pdf2hwpx',
    [string]$Region = 'ap-northeast-2',
    [string[]]$Names = @('me', 'guest'),
    [switch]$Links,
    [switch]$Ssh,
    [switch]$Delete
)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
$DeployDir = Join-Path $Root 'deploy'
$KeyFile = Join-Path $DeployDir 'access_keys.txt'
$KeyPem = Join-Path $DeployDir 'lightsail_key.pem'
$KnownHosts = Join-Path $DeployDir 'known_hosts'
$IpName = "$Name-ip"
New-Item -ItemType Directory -Force $DeployDir | Out-Null

function Say([string]$msg, [string]$color = 'Gray') { Write-Host $msg -ForegroundColor $color }
function Fail([string]$msg) { Say ''; Say $msg 'Red'; Say ''; exit 1 }
function Write-Utf8([string]$path, [string]$text) {
    [IO.File]::WriteAllText($path, $text, (New-Object System.Text.UTF8Encoding($false)))
}

# aws 명령 실행: 오류 글자(stderr)도 받아서 돌려준다. (5.1 에서 2>&1 이 예외가 되지 않게 잠시 Continue)
function Invoke-Aws {
    $old = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $out = & aws @args --region $Region 2>&1 | ForEach-Object { "$_" } |
        Where-Object { $_ -ne 'System.Management.Automation.RemoteException' }
    $code = $LASTEXITCODE
    $ErrorActionPreference = $old
    return @{ ok = ($code -eq 0); text = ($out -join "`n") }
}
function Get-Json([string[]]$cmd) {
    $r = Invoke-Aws @cmd --output json
    if (-not $r.ok) { return $null }
    return ($r.text | ConvertFrom-Json)
}

function New-Key {
    $b = New-Object byte[] 18
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
    return ([Convert]::ToBase64String($b)).Replace('+', '-').Replace('/', '_').TrimEnd('=')
}
function Get-Keys {
    if (-not (Test-Path $KeyFile)) {
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

function Get-Instance { $j = Get-Json @('lightsail', 'get-instance', '--instance-name', $Name); if ($j) { return $j.instance } }
function Get-StaticIp { $j = Get-Json @('lightsail', 'get-static-ip', '--static-ip-name', $IpName); if ($j) { return $j.staticIp } }
function Get-HostName([string]$ip) { return ($ip.Replace('.', '-') + '.sslip.io') }

function Show-Links([string]$ip) {
    $url = 'https://' + (Get-HostName $ip)
    Say ''
    Say "사이트 주소: $url" 'Green'
    Say '초대 링크 (사람마다 따로 보내세요. 한 번 열면 그 브라우저는 180일 동안 계속 쓸 수 있습니다):' 'Green'
    foreach ($p in (Get-Keys)) {
        $i = $p.LastIndexOf(':')
        Say ('  {0,-10} {1}/join/{2}' -f $p.Substring(0, $i), $url, $p.Substring($i + 1)) 'White'
    }
    Say ''
}

# ssh/scp 공통 옵션: 이 폴더의 키와 known_hosts 만 쓴다
function Get-SshOpts([switch]$Interactive) {
    $o = @('-i', $KeyPem, '-o', 'StrictHostKeyChecking=accept-new', '-o', "UserKnownHostsFile=$KnownHosts",
           '-o', 'ConnectTimeout=10')
    if (-not $Interactive) { $o += @('-o', 'BatchMode=yes') }  # 암호를 묻지 않고 바로 실패하게
    return $o
}

# 서버 접속 키: Lightsail 이 지역마다 만들어 두는 기본 키(서버를 만들 때 따로 지정하지 않으면 이 키가 들어간다)
function Initialize-KeyPem {
    if (-not (Test-Path $KeyPem)) {
        $r = Invoke-Aws lightsail download-default-key-pair --query privateKeyBase64 --output text
        if (-not $r.ok -or $r.text -notmatch 'PRIVATE KEY') { Fail ("서버 접속 키를 받지 못했습니다.`n" + $r.text) }
        Write-Utf8 $KeyPem ($r.text.Trim() + "`n")
    }
    # Windows ssh 는 다른 사용자도 읽을 수 있는 키 파일을 거부하므로 내 계정만 읽게 한다
    & icacls $KeyPem /inheritance:r /grant:r "$($env:USERNAME):R" | Out-Null
}
function Invoke-Ssh([string]$ip, [string]$cmd, [switch]$Quiet) {
    $old = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $o = Get-SshOpts
    if ($Quiet) { & ssh @o "ubuntu@$ip" $cmd 2>$null | Out-Null } else { & ssh @o "ubuntu@$ip" $cmd | Out-Host }
    $code = $LASTEXITCODE
    $ErrorActionPreference = $old
    return $code
}

# ---------------------------------------------------------------- 준비물 --
foreach ($c in @('aws', 'git', 'ssh', 'scp')) {
    if (-not (Get-Command $c -ErrorAction SilentlyContinue)) {
        if ($c -eq 'aws') { Fail "AWS CLI 가 없습니다: winget install -e --id Amazon.AWSCLI (설치 후 PowerShell 새로 열기)" }
        if ($c -eq 'git') { Fail "git 이 없습니다: winget install -e --id Git.Git (설치 후 PowerShell 새로 열기)" }
        Fail "$c 가 없습니다. 설정 > 시스템 > 선택적 기능 > 'OpenSSH 클라이언트'를 추가하세요."
    }
}
$who = Invoke-Aws sts get-caller-identity --output json
if (-not $who.ok) {
    Fail ("AWS 에 로그인되어 있지 않습니다. 프로필을 쓰면 먼저 `$env:AWS_PROFILE = `"pdf`" 를 입력하세요.`n" + $who.text)
}
Say ("AWS 계정: " + (($who.text | ConvertFrom-Json).Account)) 'Cyan'

if ($Links) {
    $sip = Get-StaticIp
    if (-not $sip) { Fail '아직 서버가 없습니다(배포 전).' }
    Show-Links $sip.ipAddress
    exit 0
}

if ($Ssh) {
    $sip = Get-StaticIp
    if (-not $sip -or -not (Get-Instance)) { Fail '아직 서버가 없습니다(배포 전).' }
    Initialize-KeyPem
    Say "서버에 접속합니다. 나가려면 exit. (앱 기록: sudo journalctl -u pdf2hwpx -n 50)" 'Cyan'
    $o = Get-SshOpts -Interactive
    & ssh @o "ubuntu@$($sip.ipAddress)"
    exit 0
}

if ($Delete) {
    $inst = Get-Instance
    $sip = Get-StaticIp
    if (-not $inst -and -not $sip) { Say '서버가 없습니다. 이미 꺼져 있습니다.' 'Green'; exit 0 }
    Say "서버 '$Name' 과 고정 IP 를 지웁니다. 사이트가 꺼지고 요금이 더 나오지 않습니다." 'Yellow'
    $ans = Read-Host "지우려면 서버 이름($Name)을 입력하세요"
    if ($ans -ne $Name) { Say '취소했습니다.'; exit 0 }
    if ($inst) {
        $r = Invoke-Aws lightsail delete-instance --instance-name $Name
        if (-not $r.ok) { Fail $r.text }
    }
    if ($sip) {  # 고정 IP 는 서버에 붙어 있지 않으면 요금이 나오므로 같이 지운다
        $r = Invoke-Aws lightsail release-static-ip --static-ip-name $IpName
        if (-not $r.ok) { Say ("고정 IP 를 지우지 못했습니다. Lightsail 콘솔 > 네트워킹에서 지워 주세요.`n" + $r.text) 'Yellow' }
    }
    Remove-Item $KnownHosts -ErrorAction SilentlyContinue
    Say '지웠습니다. (다시 올리려면 -Delete 없이 실행. 초대 링크 주소는 새 IP 로 바뀝니다)' 'Green'
    exit 0
}

$pairs = Get-Keys

# ---------------------------------------------------------- 1. 서버 --
$inst = Get-Instance
if (-not $inst) {
    $bp = (Get-Json @('lightsail', 'get-blueprints')).blueprints | Where-Object { $_.isActive } |
        Where-Object { $_.blueprintId -in @('ubuntu_24_04', 'ubuntu_22_04') } | Sort-Object blueprintId -Descending | Select-Object -First 1
    $bd = (Get-Json @('lightsail', 'get-bundles')).bundles |
        Where-Object { $_.isActive -and $_.ramSizeInGb -eq 1 -and ($_.supportedPlatforms -contains 'LINUX_UNIX') -and $_.bundleId -notmatch 'ipv6' } |
        Sort-Object price | Select-Object -First 1
    if (-not $bp -or -not $bd) { Fail 'Ubuntu 이미지나 1GB 요금제를 찾지 못했습니다. Lightsail 콘솔에서 확인해 주세요.' }
    Say ("서버를 만듭니다: {0}, 메모리 1GB, 월 {1}달러 (서울)" -f $bp.blueprintId, $bd.price) 'Cyan'
    $r = Invoke-Aws lightsail create-instances --instance-names $Name --availability-zone "${Region}a" `
        --blueprint-id $bp.blueprintId --bundle-id $bd.bundleId
    if (-not $r.ok) { Fail ("서버를 만들지 못했습니다.`n" + $r.text) }
    Remove-Item $KnownHosts -ErrorAction SilentlyContinue  # 새 서버는 서버 지문이 다르다
}
$until = (Get-Date).AddMinutes(10)
while ($true) {
    $inst = Get-Instance
    if ($inst -and $inst.state.name -eq 'running') { break }
    if ((Get-Date) -gt $until) { Fail '서버가 10분 안에 켜지지 않았습니다. Lightsail 콘솔에서 확인해 주세요.' }
    Write-Host ("  서버 켜는 중… ({0})" -f $(if ($inst) { $inst.state.name } else { '?' })) -ForegroundColor DarkGray
    Start-Sleep -Seconds 10
}

# ---------------------------------------------------------- 2. 고정 IP, 방화벽 --
$sip = Get-StaticIp
if (-not $sip) {
    $r = Invoke-Aws lightsail allocate-static-ip --static-ip-name $IpName
    if (-not $r.ok) { Fail ("고정 IP 를 만들지 못했습니다.`n" + $r.text) }
    $sip = Get-StaticIp
}
if (-not $sip.isAttached -or $sip.attachedTo -ne $Name) {
    $r = Invoke-Aws lightsail attach-static-ip --static-ip-name $IpName --instance-name $Name
    if (-not $r.ok) { Fail ("고정 IP 를 서버에 붙이지 못했습니다.`n" + $r.text) }
    Remove-Item $KnownHosts -ErrorAction SilentlyContinue
    $sip = Get-StaticIp
}
$ip = $sip.ipAddress
$hostName = Get-HostName $ip
Say "고정 IP: $ip  ->  주소 https://$hostName" 'Cyan'
# 22(관리용 ssh), 80/443(웹)만 연다. 앱 포트 8000 은 밖에서 닿지 않는다.
$r = Invoke-Aws lightsail put-instance-public-ports --instance-name $Name --port-infos `
    'fromPort=22,toPort=22,protocol=tcp' 'fromPort=80,toPort=80,protocol=tcp' 'fromPort=443,toPort=443,protocol=tcp'
if (-not $r.ok) { Fail ("방화벽을 설정하지 못했습니다.`n" + $r.text) }

# ---------------------------------------------------------- 3. 접속 --
Initialize-KeyPem
$until = (Get-Date).AddMinutes(5)
while ((Invoke-Ssh $ip 'true' -Quiet) -ne 0) {
    if ((Get-Date) -gt $until) { Fail "서버에 ssh 로 접속하지 못했습니다(5분). 잠시 뒤 다시 실행해 보세요." }
    Write-Host '  서버 접속 기다리는 중…' -ForegroundColor DarkGray
    Start-Sleep -Seconds 10
}

# ---------------------------------------------------------- 4. 코드 올리기 + 설치 --
$dirty = & git status --porcelain
if ($dirty) { Say '알림: 커밋하지 않은 변경이 있습니다. 올라가는 것은 마지막 커밋입니다.' 'Yellow' }
$tarball = Join-Path $DeployDir 'app.tar.gz'
$envFile = Join-Path $DeployDir 'pdf2hwpx.env'
& git archive --format=tar.gz -o $tarball HEAD
if ($LASTEXITCODE -ne 0) { Fail 'git archive 실패' }
Write-Utf8 $envFile ("ACCESS_KEYS=" + ($pairs -join ',') + "`nJOB_TTL_MIN=30`nDOWNLOAD_TTL_MIN=10`nMAX_FILES=10`nMAX_TOTAL_PAGES=200`n")
try {
    Say '코드를 올리는 중…' 'Cyan'
    $o = Get-SshOpts
    $old = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    & scp -q @o $tarball $envFile "ubuntu@${ip}:/tmp/"
    $code = $LASTEXITCODE; $ErrorActionPreference = $old
    if ($code -ne 0) { Fail 'scp 로 파일을 올리지 못했습니다.' }
} finally {
    Remove-Item $tarball, $envFile -ErrorAction SilentlyContinue  # 초대 키가 들어 있으므로 바로 지운다
}
Say '서버에서 설치하는 중… (처음에는 5분쯤)' 'Cyan'
$cmd = "set -e; rm -rf /tmp/p2h; mkdir -p /tmp/p2h; tar -xzf /tmp/app.tar.gz -C /tmp/p2h; rm -f /tmp/app.tar.gz; " +
       "sudo bash /tmp/p2h/tools/server/setup.sh $hostName"
if ((Invoke-Ssh $ip $cmd) -ne 0) { Fail "서버 설치가 실패했습니다. 위의 기록을 보내 주세요. (직접 확인: -Ssh)" }

# ---------------------------------------------------------- 5. HTTPS 확인 --
Say 'HTTPS 인증서 확인 중… (처음에는 1분쯤)' 'Cyan'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$ok = $false
for ($i = 0; $i -lt 18; $i++) {
    try {
        $res = Invoke-WebRequest -UseBasicParsing -TimeoutSec 10 -Uri "https://$hostName/healthz"
        if ($res.StatusCode -eq 200) { $ok = $true; break }
    } catch { }
    Start-Sleep -Seconds 10
}
if (-not $ok) {
    Say "https://$hostName 에 아직 접속되지 않습니다. 인증서 발급이 늦을 수 있으니 몇 분 뒤 브라우저로 열어 보세요." 'Yellow'
    Say "계속 안 되면 -Ssh 로 접속해 'sudo journalctl -u caddy -n 50' 기록을 보내 주세요." 'Yellow'
} else {
    Say '배포 완료!' 'Green'
}
Show-Links $ip
Say '요금 알림을 아직 안 만들었다면: AWS 콘솔 > Billing and Cost Management > Budgets > 예산 생성(월 10달러 등).' 'Yellow'
