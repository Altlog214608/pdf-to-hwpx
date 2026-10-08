# 웹 서비스 (v0.8)

PDF를 끌어다 놓으면 머리 부분(학원 이름·로고, 시험 제목, 바깥 테두리)과 본문 글꼴·크기를 미리 보며 정하고
HWPX로 내려받는 사이트입니다. 변환기(`pdf2hwpx/`)를 그대로 쓰고, 웹 부분은 `webapp/`에만 있습니다.

## 1. 로컬 실행

### 더블클릭 실행 (Python 설치 몰라도 됨)
압축을 푼 폴더에서 `실행하기.bat`을 더블클릭합니다. `tools/start_web.ps1`이 다음을 합니다.
1. Python(3.10 이상) 확인 → 없으면 `winget`으로 사용자 설치(관리자 권한 불필요). winget이 없으면 python.org 안내.
2. 폴더 안 `.venv`에 부품 설치(처음 한 번, `requirements*.txt`가 바뀌면 다시).
3. 서버 실행(8000번이 쓰이고 있으면 8001…) 후 브라우저 열기. 검은 창을 닫으면 서버도 꺼짐.

처음 받은 ZIP의 `.bat`을 실행하면 "Windows의 PC 보호" 창이 뜰 수 있습니다 → **추가 정보 → 실행**.
ZIP은 반드시 **압축을 푼 뒤** 실행합니다.

### 명령어로 실행 (Windows PowerShell)

```powershell
pip install -r requirements.txt -r webapp\requirements.txt; python .\webapp\server.py
```

브라우저에서 http://127.0.0.1:8000 을 엽니다. 설정은 환경 변수로 바꿉니다.

| 변수 | 기본값 | 뜻 |
|---|---|---|
| `JOB_TTL_MIN` | 30 | 업로드 후 작업(원본 PDF·결과)을 서버에 두는 최대 시간(분) |
| `DOWNLOAD_TTL_MIN` | 10 | 변환 후 다운로드 링크가 유효한 시간(분) |
| `MAX_MB` / `MAX_PAGES` | 40 / 80 | 업로드 제한(파일 하나당) |
| `MAX_FILES` | 10 | 한 번에 올리는 PDF 수 |
| `MAX_TOTAL_PAGES` | 200 | 통합본 전체 쪽수 |
| `USAGE_DB` | `DATA_DIR` 옆 `pdf2hwpx_usage.sqlite3` | 이용 기록 파일(SQLite) |
| `USAGE_KEEP_DAYS` | 365 | 이용 기록 보관 기간(일) |
| `ADMIN_USERS` | `ACCESS_KEYS`의 첫 사람 | 이용 기록을 볼 수 있는 초대 이름(쉼표로 여러 명) |
| `SAMPLE_KEEP_DAYS` | 14 | 문제 생긴 파일 보관 기간(일). 0이면 보관하지 않음 |
| `SAMPLE_MAX` / `SAMPLE_MAX_MB` | 30 / 1000 | 문제 생긴 파일 최대 개수·용량(넘으면 오래된 것부터 삭제) |
| `SAMPLES_DIR` | `DATA_DIR` 옆 `pdf2hwpx_samples` | 문제 생긴 파일 보관 폴더 |
| `DATA_DIR` | 시스템 임시 폴더`/pdf2hwpx_jobs` | 작업 폴더 |
| `HOST` / `PORT` | 127.0.0.1 / 8000 | 컨테이너에서는 `0.0.0.0` |

## 2. 화면 흐름

1. **올리기**: 화면 어디에 끌어 놓아도 됨(배경 흐림 + 가운데 PDF+ 아이콘). 글자 레이어를 검사해
   스캔본(글자 없음)·글자 깨짐 PDF는 변환 전에 알려 줌. 여러 개를 한 번에 놓거나 작업 화면의 `+ 추가`로 더할 수 있음.
   - 여러 파일이면 원본 카드 아래에 목록(누르면 미리보기 전환, ↑로 순서, ×로 빼기)과 "여러 파일" 설정이 나옴.
   - **파일마다 따로**: 하나씩 차례로 변환(목록에 대기/변환 중/완료) → ZIP 한 번에 또는 파일별로 받기. 제목은 파일마다.
   - **하나로 합치기**: 목록 순서대로 이어 한 HWPX. 문제·정답 번호가 끝까지 이어짐(20문제 3개 → 1~60번).
2. **디자인 설정**: 왼쪽 원본 첫 쪽, 오른쪽 HWPX 첫 쪽 윗부분 미리보기.
   - 미리보기의 학원 칸·제목 칸을 누르면 해당 입력칸으로 이동.
   - 제목 후보는 PDF 머리글에서 찾아 칩으로 보여 줌(`[중간 대비]` 같은 앞머리는 유지).
   - 본문 글꼴 7종, 크기 8~13pt(0.5 단위). 마지막 설정은 브라우저에 기억.
   - 학원 이름은 앞부분(예: 김한춘)과 작은 글씨 뒷부분(예: 국어전문학원)의 글자 크기를 따로, 제목 글자 크기도 따로 정함.
   - 머리 부분 **바탕쪽 프리셋**: "기본"(여기서 학원·제목·테두리를 꾸밈) 또는 "학원 1"처럼 작은 그림 카드를 누르면 그 학원
     시험지의 바탕쪽(학원 칸·제목 칸·테두리·산돌 등 직접 설치한 글꼴)을 그대로 쓰고 제목 칸 글자만 입력한 제목으로 바꿈.
     프리셋에 쓰인 글꼴은 본문 글꼴 목록에도 나옴. 프리셋은 개발자가 `python tools/make_preset.py 시험지.hwpx --id hakwon2 --name "학원 2"`로
     한 번 만들어 `pdf2hwpx/presets/`에 넣는다(웹에서 파일을 올려 뽑지 않음).
   - 제목 글자 색(견본 5색 + 직접 고르기), 정답·해설 방식(문서 끝에 모으기 / 문제와 미주로 연결).
   - 문제 번호를 한글 자동 번호(문단 번호)로 넣기(기본 켬): 한글에서 문제를 더 쓰거나 다른 파일을 붙여 넣으면 번호가 이어짐.
   - 오른쪽 위 버튼으로 밝은/어두운 화면 전환.
3. **다운로드**: 구조 검사 결과(문제 수·박스·정답·원문 반영률)와 남은 다운로드 시간 표시.
   설정을 바꾸면 "다시 변환" 상태가 됨.

## 3. 이용 기록 (관리자)

- 관리자(기본: 초대 키의 첫 사람 `me`)에게만 화면 오른쪽 위에 **이용 기록** 링크가 보이고, `/admin`에서 봅니다.
  다른 사람이 `/admin`·`/api/admin/*`에 들어오면 403.
- 남기는 것: 시각, 초대 이름, 동작(초대 링크 접속·PDF 올리기·변환·통합본·ZIP·내려받기·오류), 파일 수, 쪽수, 문제 수,
  결과(통과/확인 필요/문제 있음), 걸린 시간, 설정 일부(정답 미주 여부, 자동 번호, 글꼴), 접속 기기 종류(Windows/Mac/iPhone…).
- **남기지 않는 것**: 파일 내용, 파일 이름, 시험 제목, 학원 이름, IP 주소.
- 화면: 기간(7일/30일/90일/1년)·사람별 요약, 날짜별 변환 횟수 그래프, 사람별 표, 최근 기록, CSV 내려받기(엑셀용).
- `USAGE_KEEP_DAYS`(기본 365일)가 지난 기록은 자동으로 지웁니다. 서버(Lightsail)에서는 `/var/lib/pdf2hwpx/`에 있어
  다시 배포해도 유지되고, `-Delete`로 서버를 지우면 함께 사라집니다.

### 문제 생긴 파일

- 변환 결과가 **문제 있음**(FAIL)이거나 변환·업로드 중 **오류**가 난 PDF만 `webapp/samples.py`가 자동으로 보관합니다.
  정상·"확인 필요" 파일은 보관하지 않습니다.
- 함께 남는 것: 원본 PDF(원래 이름), 그때의 결과 HWPX, 검사 원인·경고, 설정(정답 미주·자동 번호·글꼴), 오류 위치(traceback), 사람, 시각.
  같은 파일이 다시 실패하면 새로 쌓지 않고 횟수와 최신 결과만 바꿉니다.
- `/admin`의 **문제 생긴 파일** 표에서 ZIP으로 내려받거나 지웁니다. `SAMPLE_KEEP_DAYS`(14일)가 지나거나
  `SAMPLE_MAX`(30개)를 넘으면 오래된 것부터 자동 삭제.
- 쓰는 방법: 내려받은 ZIP의 PDF로 원인을 고치고, 머지 전에 `$env:PDF2HWPX_SAMPLES="폴더"; python -m pytest tests -q`로 다시 확인.
  PDF는 저장소에 넣지 않습니다.
- 화면에 알림: 오른쪽 위 "파일은 자동 삭제 · 변환 실패 파일만 14일 보관", 실패했을 때 결과 칸에 "관리자에게 보관했어요(14일 뒤 삭제)".

## 4. 파일 보관 정책 (저작권 보호)

- 업로드 파일·결과물은 서버 디스크의 작업 폴더에만 있고 DB·외부 저장소에 남기지 않습니다.
  예외는 위의 **문제 생긴 파일**뿐입니다(기한·개수 제한, 관리자만, 화면에 안내).
- 페이지를 떠나면 브라우저가 `sendBeacon`으로 삭제 요청 → 즉시 폴더 삭제.
- 그렇지 않아도 `JOB_TTL_MIN`이 지나면 30초 간격 청소 스레드가 삭제. 다운로드 링크는 추측 불가능한
  토큰을 포함하고 `DOWNLOAD_TTL_MIN` 뒤 410(만료)을 돌려줍니다.
- 서버 로그와 이용 기록에 파일 내용·파일 이름은 남기지 않습니다.

## 5. API

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/api/config` | 글꼴 목록, 제한, 보관 시간 |
| POST | `/api/jobs` (multipart `file`) | 업로드 + 분석: `text_layer`, `title_candidates`, `sample`, `stats` |
| GET | `/api/jobs/{id}/page1.png` | 원본 1쪽 그림 |
| POST/DELETE | `/api/jobs/{id}/logo` | 로고 그림(PNG/JPG, 2MB) |
| POST | `/api/jobs/{id}/convert` (JSON) | `body_font, title_font, body_size, academy_name, academy_sub, academy_size, academy_sub_size, use_logo, title, title_size, title_color, frame, answers_as_endnotes, auto_number, preset`(바탕쪽 프리셋 id, `/api/config`의 `presets`), `logo_job`(다른 작업의 로고 빌려 쓰기) |
| POST | `/api/bundles/merge` (JSON `jobs, options`) | 여러 작업을 이어 통합본 하나(번호 이어서). 응답은 convert와 같은 모양 + `id`(묶음 작업) |
| POST | `/api/bundles/zip` (JSON `jobs`) | 변환을 마친 작업들의 HWPX를 ZIP 하나로 |
| GET | `/api/jobs/{id}/download/{token}` | HWPX (만료 시 410) |
| DELETE · POST `.../delete` | `/api/jobs/{id}` | 작업 삭제 |
| GET | `/healthz` | 상태 확인(로드밸런서용) |
| GET | `/admin` · `/api/admin/usage?days=&limit=&user=` · `/api/admin/usage.csv` | 이용 기록(관리자만) |
| GET · DELETE | `/api/admin/samples` · `/api/admin/samples/{id}/download` · `/api/admin/samples/{id}` | 문제 생긴 파일 목록·ZIP·삭제(관리자만) |

CLI에서도 같은 옵션을 쓸 수 있습니다:
`python .\v0_5_pdf_to_hwpx.py 파일.pdf --font 나눔명조 --size 11 --title "[중간 대비] 2-2" --academy "김한춘 국어전문학원" --logo .\logo.png`

## 6. 머리 부분은 한글에서 어떻게 만들어지나

수작업 시험지와 같은 **바탕쪽(masterpage)** 방식입니다. 바탕쪽에 '글 뒤로' 배치한 표 하나가 페이지를 덮습니다.

```
┌──────────────┬──────────────────────────┐ ← 1행: [검은 칸: 로고 그림 또는 흰 굵은 학원 이름][제목(14pt 굵게)]
├──────────────┴──────────────────────────┤
│              본문 영역                  │ ← 2행: 바깥 네모 테두리
└─────────────────────────────────────────┘
```

바탕쪽은 모든 쪽에 반복되고 본문을 고쳐도 움직이지 않습니다. 한글에서 고치려면 `쪽 → 바탕쪽`으로 들어갑니다.
머리 부분을 켜면 본문 여백도 수작업 파일 수치(바탕쪽 표 안쪽에 본문이 들어가도록)로 바뀝니다.

## 7. AWS 배포 (Lightsail 인스턴스)

변환은 CPU만 쓰고 1개 PDF당 1~3초, 메모리 300MB 안팎입니다. 변환은 서버 전체에서
한 번에 하나씩 처리하므로(대기열) 여러 파일을 올려도 메모리가 늘지 않습니다.

**구성: Lightsail 인스턴스(Ubuntu, 1GB, 서울) 1대 + 고정 IP** — 월 약 7달러.
- 서버 안: 앱(`127.0.0.1:8000`, systemd 서비스 `pdf2hwpx`) + **Caddy**가 `https://<IP>.sslip.io` 인증서(Let's Encrypt)를
  자동으로 받아 앱으로 넘김. 도메인을 살 필요 없음. 방화벽은 22(ssh)·80·443만.
- 스왑 1GB, 보안 업데이트 자동(unattended-upgrades). 설치는 `tools/server/setup.sh`(여러 번 실행해도 됨).
- 새 계정은 Lightsail **컨테이너 서비스** 한도가 0인 경우가 많아 인스턴스 방식을 기본으로 함.
  한도가 있으면 `tools/deploy_lightsail_container.ps1`(컨테이너 서비스 micro, 월 약 10달러)도 쓸 수 있음.

### 접속 제한: 사람마다 초대 링크
환경 변수 `ACCESS_KEYS="이름:키,이름:키"`를 주면 `https://주소/join/키`를 한 번 연 브라우저만 쿠키로 계속 씁니다
(180일, `ACCESS_DAYS`). 초대 링크 없이 들어오면 안내 화면만 보입니다. 한 사람을 끊으려면 그 줄을 지우고 다시 배포합니다.
`/healthz`만 열려 있습니다. 접속 기록(access log)은 키가 남지 않게 기본으로 끕니다.
`ACCESS_KEYS`가 없으면(내 PC 실행) 제한이 없습니다.

### 처음 한 번 준비 (Windows PowerShell)
```powershell
winget install -e --id Git.Git; winget install -e --id Amazon.AWSCLI
```
1. AWS 콘솔 IAM에서 사용자(콘솔 접근 없음) + 인라인 정책 `{"Effect":"Allow","Action":"lightsail:*","Resource":"*"}` +
   액세스 키(CLI) → `aws configure --profile pdf`(리전 `ap-northeast-2`). 창마다 `$env:AWS_PROFILE = "pdf"`.
2. **요금 알림**: AWS 콘솔 → Billing and Cost Management → Budgets → 월 예산(예: 10달러).
3. ssh/scp는 Windows 10/11에 기본으로 들어 있음(없으면 설정 → 선택적 기능 → OpenSSH 클라이언트). Docker는 필요 없음.

### 올리기 / 고친 뒤 다시 올리기 (같은 명령)
```powershell
$env:AWS_PROFILE = "pdf"; powershell -ExecutionPolicy Bypass -File .\tools\deploy_lightsail.ps1
```
`tools/deploy_lightsail.ps1`이 하는 일:
1. 초대 키가 없으면 `deploy\access_keys.txt`에 만듦(`me`, `guest`). 서버 접속 키는 `deploy\lightsail_key.pem`(Lightsail 기본 키).
   `deploy\`는 git과 도커 이미지에 들어가지 않음.
2. 서버 `pdf2hwpx`가 없으면 만듦(Ubuntu 24.04, 1GB 요금제 중 가장 싼 IPv4 요금제) → 고정 IP `pdf2hwpx-ip` 붙이기 → 방화벽.
3. 현재 커밋을 `git archive`로 묶어 scp로 올리고 서버에서 `setup.sh` 실행 → `https://<IP>.sslip.io/healthz` 확인 → 초대 링크 출력.
   (커밋하지 않은 변경은 올라가지 않음)

- 초대 링크만 다시 보기: `... deploy_lightsail.ps1 -Links`
- 서버에 접속해 확인: `... deploy_lightsail.ps1 -Ssh` → `sudo journalctl -u pdf2hwpx -n 50`(앱), `sudo journalctl -u caddy -n 50`(HTTPS)
- 사이트 끄기(요금 중지): `... deploy_lightsail.ps1 -Delete` (서버와 고정 IP를 함께 지움. 다시 만들면 IP와 초대 링크 주소가 바뀜)

**서버는 1대로 둡니다.** 작업 상태를 메모리와 로컬 디스크에 두므로 여러 대로 나누면 404가 납니다.
내 PC에서 컨테이너로 확인만 하려면: `docker build -t pdf2hwpx-web .; docker run --rm -p 8000:8000 pdf2hwpx-web`

**배포 전 임시 공유**: PC에서 서버를 켜고 `cloudflared tunnel --url http://localhost:8000`
(계정 없이 임시 `https://….trycloudflare.com` 주소, PC가 켜져 있는 동안만).

**사용자가 늘면 (수평 확장)**: 작업 상태를 공유 저장소로 옮깁니다.
- 원본·결과 → S3 버킷(수명 주기 규칙 1일 삭제), 다운로드는 10분짜리 presigned URL.
- 작업 메타데이터 → DynamoDB(TTL 속성으로 자동 만료) 또는 ElastiCache.
- 변환은 SQS + 워커(또는 Lambda 컨테이너 이미지, 메모리 1.5GB 이상)로 분리.
`webapp/server.py`의 `Job`/`JOBS`/`_delete`만 바꾸면 되도록 나눠 두었습니다.

## 8. 아직 없는 것

- 제목 글꼴에 학원 전용 글꼴(예: 디자인 글꼴) 지정 — 글꼴 이름을 알려 주면 목록에 추가. 단 열어 보는 PC에 설치돼 있어야 함.
