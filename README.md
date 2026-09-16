# SENTINEL 통합 실행기

SENTINEL은 하나의 명령으로 등록된 프로젝트를 검사하고, 필요한 언어 도구만 버전을 고정해 설치하는 로컬 실행기입니다.

- 플러그인이 지원하는 언어: Python, TypeScript, Java 세 가지입니다. 각 언어는 공개 프로젝트에서 원본 도구와 결과를 대조해 확인했습니다.
- 기본 `check` 는 승인된 도구 묶음만 실행합니다. 승인이란 각 언어 검사기 저장소의 CI(자체 시험 전체)를 통과한 commit 의 어댑터를 이 저장소의 `src/sentinel/admission.json` 에 기록한 것이고, 모든 모듈이 승인된 묶음으로 통과하면 결과가 `certified=true` 가 됩니다. 승인되지 않은 묶음은 `--experimental` 로만 실행되며 그 결과는 인증되지 않습니다.
- 최신 진행 상황은 [현재 진행 순서](docs/exec-plans/active/2026-09-sentinel-unified-entry.md#현재-진행-순서), 실제 설치·호출 결과는 [호스트·WSL 검증 기록](docs/references/sentinel-host-validation.md)에서 확인합니다.

## 현재 제공하는 것

|명령|실제 동작|외부 도구 실행|
|---|---|---|
|plan|설정 파일에서 전체 또는 선택한 모듈 목록을 확인한다.|없음|
|doctor|선택한 설치 파일의 버전·내용 지문을 확인한다. 언어 SDK 자체의 실행 가능성을 확인하는 명령은 아니다.|없음|
|install|신뢰하는 로컬 도구 묶음을 언어·버전·지문별 독립 폴더에 복사한다.|없음|
|check|설치와 승인을 먼저 확인한다. 승인된 묶음의 모듈만 실행하고, 승인되지 않은 모듈은 backendNotAdmitted(6)로 두고 시작하지 않는다.|있음. 승인된 묶음만|
|check --experimental|승인 여부와 상관없이 선택한 도구들을 차례로 호출한다. 정식 인증은 하지 않는다.|있음. 정식 인증은 하지 않음|
|setup|언어 저장소·SDK·도구 묶음을 준비하고 두 설정 파일과 기준값을 쓴다. 처음 한 번, 또는 언어를 추가할 때 실행한다.|있음. git·언어 bootstrap 스크립트|

모듈은 따로 검사할 프로젝트 폴더입니다. 예를 들어 Python 서버와 TypeScript 화면을 서로 다른 모듈로 등록할 수 있습니다. 전체 실행은 **등록된 모듈 전체**를 뜻하며, 저장소의 모든 언어나 파일을 자동으로 발견했다는 뜻이 아닙니다.

SDK는 해당 언어의 프로그램을 빌드하고 실행하는 도구 모음입니다. SENTINEL 명령의 설치와 언어 도구·SDK의 준비는 별개입니다.

## 지원 플랫폼

통합 실행기의 현재 지원 경로는 **Linux이며 Windows에서는 WSL2 내부에 설치해서 사용합니다.** 이번 실제 검증 환경은 Ubuntu x86_64 / WSL2입니다. Windows의 Codex·Claude Code는 `wsl.exe`로 Linux 실행 파일을 호출합니다. CLI·언어 도구·검사할 프로젝트는 WSL의 Linux 파일시스템에 준비하는 것을 권장합니다. Windows에서 변환된 줄바꿈은 승인된 실행 파일 지문과 달라질 수 있습니다.

macOS의 통합 설치는 현재 지원하지 않습니다. 묶음 게시에 Linux `renameat2`가 필요하기 때문입니다. 언어 검사기별 SDK 잠금과 여러 플랫폼 CI가 있어도 통합 설치·호스트 호출의 지원을 뜻하지 않습니다. 다른 CPU·커널 조합도 해당 경로를 별도로 검증해야 합니다. WSL의 오래된 커널에서는 선택적 격리 코드의 일부 시험이 실패하며, 기본 세 언어 명령 시험과 구분해 [검증 기록](docs/references/sentinel-host-validation.md)에 남깁니다.

## 첫 실행 설정

sentinel 명령을 설치한 뒤 검사할 프로젝트에서 한 번 실행합니다. 언어는 python, typescript, java 중에서 반복 지정하고, 생략하면 세 언어를 모두 선택합니다. 새로 여러 언어를 설정할 때는 서로 겹치지 않는 기존 폴더를 `--module-root 언어=폴더`로 각각 지정해야 합니다. 단일 언어를 처음 설정할 때만 기본 폴더가 `.`입니다.

```bash
# api/와 web/가 이미 존재하는 프로젝트 예시. 실제 폴더명으로 바꾼다.
# setup = 첫 실행 설정; --module-root = 언어별 검사 폴더
# --crap-max 8 = CRAP 상한(기본 8); --mutation-min 100 = 변이 최소 kill 비율 %(기본 100)
.venv/bin/sentinel setup --project . --language python --language typescript --module-root python=api --module-root typescript=web --crap-max 8 --mutation-min 100
```

setup은 아래 항목을 준비합니다. 폴더 구성을 먼저 검증하고 언어 도구·프로젝트 의존성 설치가 모두 성공하면 각 모듈 설정을 만든 뒤 workspace를 마지막에 기록합니다.

1. 언어 저장소를 `~/.sentinel/sources/SENTINEL_PY` 같은 폴더에 둡니다. 없으면 github.com/hwain-ai 의 같은 이름 저장소를 git clone 합니다. 다른 위치는 `--sources`로 지정합니다.
2. 각 저장소의 `sentinel-tool/setup.sh`를 실행합니다. 이 스크립트는 잠금 파일의 공식 주소·SHA-256으로 언어 SDK를 내려받고 검사기를 준비합니다. 이미 준비돼 있으면 확인만 하고 지나갑니다. 세 언어를 모두 준비하면 약 2GB를 내려받습니다.
3. 저장소의 `sentinel-tool/sentinel-tool` 실행 파일과 저장소 위치를 적은 `home` 파일로 도구 묶음을 만들어 `--tools`(기본 프로젝트의 .sentinel-tools)에 설치합니다.
4. `sentinel.workspace.json`에 언어별 모듈과 `gate`(crapMax, mutationMin)를 씁니다. 기존 모듈의 ID·폴더·설정과 기준값은 보존하고 선택한 언어의 도구 버전·지문만 갱신합니다. 폴더·기준값을 명시하면 그 값으로 바꿉니다. 같은 언어의 모듈이 여러 개이면 언어 하나에 폴더 하나를 지정하는 변경은 모호하므로 거부합니다. 잘못된 폴더 구성은 다운로드 전에 거부합니다.
5. Python·TypeScript 검사기가 읽는 `sentinel.config.json`을 **각 모듈 폴더 안에** 만듭니다. 기본값은 소스 `src/`, 테스트 `tests/` 또는 `test/`이며, 기존 파일이나 별도 사용자 설정 경로는 보존합니다. 결과의 projectConfig가 created이면 실제 폴더 구조에 맞게 고칩니다. 생산도 테스트도 아닌 소스(docs/conf.py, build.config.ts 등)가 있어 검사가 unclassifiedSource로 거부되면 그 모듈의 `excluded` 글롭 목록에 적습니다.
6. Python 테스트가 외부 패키지를 쓰면 `--python-requirements requirements.txt`를 함께 줍니다. 이 경로는 **각 Python 모듈 기준**입니다. 검사기의 고정 Python으로 wheel만 `<모듈>/.sentinel-deps`에 설치하고 검사 때 PYTHONPATH에 올립니다. 이 폴더는 분석·변이 대상이 아니므로 `.gitignore`에 넣습니다. 캐시에 없으면 공식 인덱스에서 내려받으며, 목록에 지문이 없으면 지문 검증도 없습니다.
7. Maven 프로젝트는 `--java-dependencies`를 함께 줍니다. **각 Java 모듈의 `pom.xml`**에서 고정 JDK·Maven으로 `mvn test`를 온라인으로 한 번 실행해 `<모듈>/.sentinel-m2`에 의존성을 받습니다. 이후 검사는 이 폴더로 오프라인 실행됩니다. 폴더가 없으면 검사기의 잠긴 저장소만 사용하므로 외부 의존성이 있는 프로젝트는 실패할 수 있습니다. 이 폴더도 `.gitignore`에 넣습니다.

## 원본 도구보다 kill 수가 적게 나오는 이유

SENTINEL 은 변이를 잡은 테스트 실패가 단언(assert) 실패일 때만 killed 로 셉니다. 테스트가 예외(TypeError, NullPointerException 등)로 죽은 변이는 runtimeError 로 따로 세고 kill 비율에 넣지 않습니다. mutmut·Stryker·mutate4java 는 이 둘을 구분하지 않고 모두 killed 로 세므로, 같은 프로젝트를 원본 도구로 돌린 killed 수는 SENTINEL 의 killed 와 runtimeError 를 더한 값과 같습니다. 2026-09-13 에 공개 프로젝트 3개로 확인한 값은 다음과 같습니다(ItsDangerous 는 mutmut 3 이 인자를 None 으로 바꾸는 변이를 많이 만들어 runtimeError 가 많습니다).

|프로젝트|SENTINEL killed + runtimeError|원본 도구 killed|
|---|---|---|
|ItsDangerous 2.2.0 (Python, 변이 567)|72 + 346 = 418|mutmut 418|
|unjs/scule v1.3.0 (TypeScript, 변이 81)|74 + 1 = 75|Stryker 75|
|Commons CLI 1.10.0 (Java, 변경 파일 1개, 변이 10)|5 + 5 = 10|mutate4java 10|

## 변경분만 검사

`check --changed`는 git 으로 변경된 파일만 검사 대상으로 넘깁니다. 기준은 `--changed-base`(기본 HEAD)와 작업 트리의 차이이며, 아직 추가하지 않은 새 파일도 포함하고 지운 파일은 제외합니다. 각 모듈에는 그 모듈 폴더 안의 변경 파일만 모듈 기준 상대 경로로 전달되고, 변경 파일이 하나도 없는 모듈은 도구를 실행하지 않고 `noChanges`(종료 0)로 표시합니다. 언어 도구는 전달받은 경로 중 생산 코드만 CRAP·변이 대상으로 삼고 테스트는 전체를 실행하며, 생산 코드 변경이 없어 실제 검사를 생략하면 어댑터도 `noChanges`로 응답하며 인증하지 않습니다. 프로젝트가 git 작업 트리가 아니거나 기준 ref가 없으면 종료 3으로 거부합니다.

```bash
# --changed = 기준 커밋 이후 바뀐 파일만; --changed-base main = 기준을 main 브랜치로
.venv/bin/sentinel check --project . --changed --changed-base main --timeout-seconds 900 --format json
```

기준값은 정수 또는 소수점 두 자리까지의 문자열입니다. crapMax는 0보다 커야 하고 mutationMin은 0 이상 100 이하입니다. `check --crap-max 10`처럼 한 번만 다른 값으로 돌릴 수도 있습니다. 기준값은 검사 요청 JSON의 `gate` 항목으로 각 언어 도구에 전달되며, 통합 실행기는 판정하지 않습니다.

## 통합 명령 설치

Python 3.9 이상에서 실행하며 실행 중 추가 Python 패키지를 요구하지 않습니다. 프로세스 관리 기능은 Linux를 대상으로 검증합니다. 아래는 uv가 설치된 Linux 환경에서 이 저장소 폴더 안에만 설치하는 명령입니다. uv는 Python 설치 환경과 패키지를 관리하는 도구입니다. 패키지 빌드에는 setuptools가 필요하며 설치 시 내려받을 수 있습니다. 다른 언어 SDK는 설치하지 않습니다.

```bash
# uv venv = 독립 Python 설치 폴더 생성; --python = 사용할 실행기; .venv = 새 폴더
uv venv --python /usr/bin/python3 .venv
# uv pip install = 패키지 설치; --python = 설치 대상 Python; 마지막 . = 현재 저장소
# --link-mode=copy = 캐시와 설치 폴더가 다른 디스크여도 파일을 복사해 설치
uv pip install --python .venv/bin/python --link-mode=copy .
# .venv/bin/sentinel = 방금 설치한 명령; --help = 사용법; --version = 버전
.venv/bin/sentinel --help
.venv/bin/sentinel --version
```

아직 없는 .venv 폴더에서 처음 설치하는 예시입니다. 이미 같은 이름의 폴더가 있으면 다른 새 폴더 이름을 사용하고, 아래 실행 경로도 그 이름에 맞춥니다. 이 설치는 Codex·Claude Code의 설정이나 시스템 전체 명령을 변경하지 않습니다.

## 검사 범위 설정

검사할 프로젝트의 sentinel.workspace.json에 다음 필드를 둡니다. 파일 형식은 JSON이며 중복 필드와 알 수 없는 필드는 거부합니다.

|위치와 필드|넣을 값|
|---|---|
|최상위 schemaVersion|고정 문자열 sentinel-workspace-v1|
|최상위 modules|1개 이상 128개 이하의 모듈 목록|
|최상위 gate|선택 항목. crapMax(기본 "8")와 mutationMin(기본 "100") 문자열|
|모듈 id|영문자로 시작하는 영숫자·밑줄·하이픈 식별자, 최대 64자|
|모듈 language|python, typescript, java 중 하나|
|모듈 root|프로젝트 기준 상대 폴더 경로. 프로젝트 자체는 점 한 개로 지정한다.|
|모듈 toolVersion|해당 도구 묶음의 정확한 버전. 예시: 1.2.3. 실제 배포 버전과 일치해야 한다.|
|모듈 toolDigest|해당 묶음의 sentinel-tool.json 원본 파일 SHA-256, 소문자 64자리|
|모듈 config|선택 항목. 해당 모듈 안에 있는 언어별 설정 파일의 상대 경로|

SHA-256은 파일 내용에서 계산하는 지문입니다. 버전이 같아도 내용이 다르면 다른 지문으로 구분합니다. 기존 SENTINEL_PY 등의 소스 폴더를 그대로 설치할 도구 묶음으로 지정할 수는 없습니다. 아래의 별도 묶음 형식이 필요합니다. 테스트에 쓰는 모의 도구는 공통 호출 계약만 시험하며 언어 품질 검사를 대신하지 않습니다.

모듈의 폴더가 서로 같거나 포함 관계이면 거부합니다. 설정 경로의 탈출, 심볼릭 링크와 특수 파일도 허용하지 않습니다. 선택 옵션을 주지 않으면 등록된 모듈 전체를 선택합니다. 같은 선택 옵션을 반복할 수 있지만 언어 선택과 모듈 선택은 한 호출에 섞지 않습니다.

```bash
# plan = 실행 범위 확인; --project . = 현재 프로젝트; --format json = 구조화된 결과
.venv/bin/sentinel plan --project . --format json
# --language python = 등록된 모듈 중 Python만 선택
.venv/bin/sentinel plan --project . --language python --format json
# doctor = 설치 지문 확인. 검사기와 프로젝트 테스트는 실행하지 않음
.venv/bin/sentinel doctor --project . --format json
# check = 검사 요청(승인된 묶음만 실행); --timeout-seconds 7200 = 모듈당 실행 제한 7200초(생략하면 언어 도구 3600초, 최대 86400초)
.venv/bin/sentinel check --project . --timeout-seconds 7200 --format json
# --experimental = 승인되지 않은 묶음도 실행(결과는 인증되지 않음)
.venv/bin/sentinel check --project . --experimental --format json
```

위 명령은 프로젝트와 이 패키지의 설치 위치가 같은 폴더라는 예시입니다. 다른 프로젝트에서는 설치한 sentinel 명령의 경로를 사용하고 --project에 검사할 폴더를 지정합니다. --config는 프로젝트 기준 workspace 설정 경로, --tools는 언어 도구를 보관한 폴더이며 생략 시 프로젝트 아래 .sentinel-tools를 사용합니다.

## 언어 도구 묶음의 제작·설치 계약

언어별 저장소에서 실행 파일과 결과 변환 코드를 만들고 아래 묶음 설정 문서(manifest)를 함께 배포합니다. 이름은 sentinel-tool.json이고 형식은 JSON입니다. 통합 실행기 안에 언어별 변이 규칙을 복사하지 않습니다.

|묶음 설정 필드|내용|
|---|---|
|schemaVersion|sentinel-tool-bundle-v1|
|protocolVersion|sentinel-tool-protocol-v1|
|language|지원하는 언어 이름 하나|
|version|이 묶음의 정확한 버전|
|entrypoint|실행 파일의 상대 경로|
|files|상대 파일 경로를 키로, 각 파일의 SHA-256을 값으로 가진 완전한 목록|

entrypoint도 files에 포함하며 manifest 자체는 제외합니다. 미기재 파일, 파일 내용 불일치, 링크·특수 파일과 구성요소가 256개를 넘는 과도하게 깊은 상대 경로는 거부합니다. 최대 파일 4,096개, 파일당 16 MiB, 전체 64 MiB인 작은 실행 연결용 묶음입니다. Java SDK처럼 큰 언어 실행 환경 전체를 여기에 넣는 설계가 아닙니다.

제작자는 manifest의 원본 지문을 별도로 제공해야 합니다. 사용자는 신뢰한 로컬 묶음 폴더를 install의 --bundle에, 그 지문을 --sha256에, 보관 폴더를 --tools에 지정합니다. 묶음과 보관 폴더 경로에는 상위 폴더로 이동하는 두 점을 넣지 않고 명확한 경로나 절대 경로를 사용합니다. 설치 주소는 보관 폴더/언어/버전/지문입니다. 기존 설치는 덮어쓰지 않으며 새 버전은 나란히 보관합니다. 이전 버전으로 되돌릴 때는 workspace의 버전과 지문을 이전 설치에 맞춥니다. 자동 업데이트·원격 패키지 검색·SDK 다운로드는 하지 않습니다.

원자 설치, 즉 검증이 끝난 묶음을 한 번에 게시하면서 기존 대상을 덮어쓰지 않는 동작은 Linux의 renameat2 기능을 사용합니다. 지원하지 않는 환경에서는 설치를 거부하며 덮어쓰는 방식으로 자동 전환하지 않습니다. 새 설치 디렉터리는 소유자만 접근하도록 만들고, 기존 사용자 폴더의 권한을 임의로 바꾸지 않습니다.

처음 확인한 뒤 원본 파일이 바뀔 수 있으므로 복사할 때도 파일별 지문과 누적 크기를 쓰기 전에 다시 확인합니다. 바뀐 내용을 발견하면 설치를 중단하고 기존 설치는 유지합니다.

일반 실행 파일 형식의 실험 실행에서 도구는 표준 입력으로 JSON 요청 하나를 받고, 표준 출력으로 JSON 응답 하나를 내보냅니다. 요청에는 protocolVersion, 새 requestId, command(check), moduleId, language, projectRoot(선택 모듈의 절대 경로), config(설정 파일 절대 경로 또는 null), gate(crapMax·mutationMin 문자열)가 있고, `check --changed`일 때만 changedFiles(모듈 기준 상대 경로 목록)가 붙습니다. 작업 디렉터리도 선택한 모듈입니다. 응답은 protocolVersion, requestId, command, moduleId, language, toolVersion, status, exitCode, passed만 허용하며 요청과 도구의 신원이 일치해야 합니다. stdout에 로그를 섞으면 계약 위반입니다.

## 결과 해석과 안전 경계

공통 결과의 selection이 allConfigured이면 등록 모듈 전체, partial이면 일부만 대상으로 했습니다. moduleCount는 그 개수입니다. results에는 모듈 식별자, 언어, 관측 상태, 관측 종료 코드와 해당하는 경우 승인 여부(admitted)를 담습니다. 원본 로그나 경로는 싣지 않습니다.

plan·doctor의 pass는 각각 범위 확인·설치 확인의 성공일 뿐입니다. doctor의 `admitted`는 묶음이 승인 목록에 있는지 알려 줍니다. 기본 check는 선택한 모든 모듈이 승인됐고 **실제로 검사되어 `passed`**일 때만 certified=true입니다. `--changed`에서 하나라도 `noChanges`이면 정상 종료(pass=true, 종료 0)할 수 있지만 certified=false이며, 검사하지 않은 코드를 품질 통과로 표시하면 안 됩니다. 부분 선택의 인증은 그 선택 범위에만 적용됩니다. 승인되지 않은 모듈은 실행하지 않고 backendNotAdmitted(6), certified=false입니다. `--experimental`은 언제나 certified=false이며 모두 passed여도 종료 6입니다.

## 승인 목록(admission.json)

승인 목록은 `src/sentinel/admission.json`이며 패키지와 함께 배포됩니다. 항목 하나는 언어, 어댑터 버전(`sentinel-tool/version`), 어댑터 실행 파일(`sentinel-tool/sentinel-tool`)의 SHA-256, 그 파일을 읽은 저장소와 commit, 그 commit 에서 성공한 CI 실행 주소, 승인 날짜로 이루어집니다. 검사 때는 설치된 묶음의 매니페스트에 적힌 실행 파일 지문을 이 목록과 맞춰 볼 뿐이라 네트워크가 필요 없습니다. 어댑터 실행 파일이 바뀌면 지문이 달라져 다시 승인해야 하고, 검사기 내부만 바뀌면 어댑터의 `version`을 올려 새 항목을 만드는 것이 규칙입니다.

항목은 `scripts/admission.py`로 다룹니다. `add`는 GitHub에서 그 commit 의 `ci` 워크플로가 main 에서 성공했는지 확인하고 버전·지문을 읽어 항목을 씁니다. `verify`는 모든 항목을 GitHub 와 다시 대조하고, `lint`는 네트워크 없이 형식과 중복을 검사합니다. 이 저장소의 CI 는 `lint`와 `verify`를 매번 돌립니다. 언어 저장소가 공개라서 워크플로의 기본 토큰으로 읽을 수 있습니다.

```bash
# add = 항목 추가; --language = 언어; --commit = CI 를 통과한 언어 저장소의 commit(main)
python3 scripts/admission.py add --language python --commit <commit>
# verify = 모든 항목을 GitHub 와 대조; lint = 형식·중복 검사(오프라인)
python3 scripts/admission.py verify
python3 scripts/admission.py lint
```

`--admission <파일>`을 doctor·check 에 주면 패키지의 목록 대신 그 파일을 씁니다. 조직이 자체 승인 목록을 운영할 때 씁니다.

도구의 실제 실패 상태는 toolError=1, qualityFailed=2, usageConfigError=3, baselineFailed=4, dependencyError=5, backendError=6, evidenceError=7, cancelled=8로 구분합니다. 여러 실패가 섞이면 7,1,5,6,8,4,3,2 순서로 전체 종료 코드를 정합니다. 설치 누락이나 손상이 발견되면 선택한 도구를 하나도 실행하지 않습니다.

취소와 자식 프로세스 정리 실패가 겹치면 해당 모듈은 backendError=6으로 남기고, 아직 시작하지 않은 모듈은 cancelled=8로 표시합니다. 이후 도구는 실행하지 않습니다. 명령의 출력 통로가 닫혔거나 사용할 수 없으면 내부 예외 대신 종료 코드 3으로 끝냅니다.

일반 실행 파일 형식에는 실행 시간과 합계 1 MiB 출력 제한, 최소 환경 변수, 프로세스 그룹 정리를 적용합니다. 이것만으로 파일·네트워크·자원을 강제로 격리하지는 못합니다. 지문 일치도 제작자의 신뢰나 악성 코드 부재를 증명하지 않습니다.

## 개발자 참고

실행기의 내부 함수·격리 설정·과거 시험 이력은 [개발자 참고](docs/references/sentinel-execution-api.md)에 있습니다. 실제 프로젝트 관측과 한계는 [세 언어 비교 기록](docs/references/sentinel-original-tool-comparison.md)에서 확인합니다. 두 호스트가 공유하는 한글 검사 지침과 기본 프롬프트는 [플러그인 안내](plugins/sentinel/README.md)에 연결돼 있습니다. 이 저장소 자체가 마켓플레이스입니다. Claude Code는 `claude plugin marketplace add hwain-ai/SENTINEL` 뒤 `claude plugin install sentinel@sentinel`, Codex는 `codex plugin marketplace add hwain-ai/SENTINEL` 뒤 `codex plugin add sentinel@sentinel`로 설치합니다. 플러그인은 지침만 담으므로 sentinel 명령과 setup은 따로 실행해야 합니다.

## 남은 단계

현재 실제 결과와 남은 항목은 [호스트·WSL 검증 기록](docs/references/sentinel-host-validation.md)에서 관리합니다. 과거의 언어 연결·CI 승인 대기와 현재의 호스트 인증·실제 호출 검증을 구분합니다. 플러그인은 동일 sentinel 명령을 호출하며 별도 품질 판정을 하지 않습니다.

각 언어는 원래 빌드·품질 결과·원본 보호·중단 뒤 정리가 확인된 범위만 지원 대상으로 기록합니다. 단위·프로세스 테스트 통과를 실제 호스트 검증 대신 사용하지 않습니다. 기존 언어별 검사 도구의 기본값과 잠금 버전은 유지합니다.
