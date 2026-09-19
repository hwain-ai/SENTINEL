# SENTINEL

[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.2.0-green)](pyproject.toml)
[![Python](https://img.shields.io/badge/python-3.9%2B-yellow)](pyproject.toml)

> 코드의 복잡도와 테스트의 결함 탐지 능력을 함께 검사하는 로컬 품질 검사 도구입니다.

SENTINEL은 **Python·TypeScript·Java 프로젝트의 코드와 테스트를 검사**하고 정해 둔 기준을 충족했는지 알려 줍니다. 터미널에서 직접 실행하거나, Claude Code·Codex에 플러그인을 설치해 대화로 검사를 요청할 수 있습니다.

**처음 쓰는 분은 [사용 가이드](#사용-가이드)를 순서대로 따라가세요.** 플러그인 설치와 실제 검사 프로그램 설치는 별도 단계입니다.

![SENTINEL - Mutation Test and CRAP](docs/assets/the_sentinel.png)

## 목차

- [주요 기능](#주요-기능)
- [기술 스택](#기술-스택)
- [사용 가이드](#사용-가이드)
  - [0. 실행 환경 확인](#step-0)
  - [1. AI 플러그인 설치](#step-1)
  - [2. SENTINEL 실행기 설치](#step-2)
  - [3. 검사할 프로젝트 지정](#step-3)
  - [4. 프로젝트 최초 설정](#step-4)
  - [5. 첫 검사와 결과 확인](#step-5)
  - [6. AI 대화창에서 검사 요청](#step-6)
- [검사는 어디에서 실행되나요?](#검사는-어디에서-실행되나요)
- [자주 쓰는 명령](#자주-쓰는-명령)
- [문제 해결](#문제-해결)
- [승인된 도구 버전 갱신](#승인된-도구-버전-갱신)
- [프로젝트 구조](#프로젝트-구조)
- [관련 문서](#관련-문서)

## 주요 기능

- **복잡도와 테스트 범위를 함께 평가합니다.** CRAP 점수는 코드가 얼마나 복잡하고 테스트가 얼마나 실행해 봤는지를 함께 반영합니다. 기본 상한은 8입니다.
- **테스트가 잘못된 코드를 잡아내는지 확인합니다.** 변이 검사(mutation testing)는 코드를 일부러 조금 바꾼 복사본을 만들고 테스트가 이를 발견하는지 확인합니다. 기본 탐지 비율은 90%입니다.
- **필요한 언어의 검사 환경을 준비합니다.** `setup`이 언어별 검사기와 SDK(컴파일·실행 도구 모음)를 준비하고 프로젝트 설정을 만듭니다.
- **검사할 파일·함수·테스트를 선택합니다.** 전체 검사와 Git 변경분 검사도 지원합니다. 모듈은 `setup`으로 설정하는 프로젝트 폴더이며, Python 서버와 TypeScript 화면을 각각 지정할 수 있습니다.
- **검사 범위와 결과를 구분합니다.** `exitCode`는 명령의 종료 코드, `selection`은 전체·부분 범위, `results[].status`는 품질 통과·미달·미검사를 표시합니다.

여기서 품질 통과는 **검사한 범위가 SENTINEL의 CRAP·mutation 기준을 충족했다는 의미**입니다. 설정에서 제외한 파일이나 제품의 모든 버그·보안 문제까지 보장하지는 않습니다.

## 기술 스택

| 구성 | 역할 |
|---|---|
| Python 3.9+ 통합 실행기 | 설치 파일 확인, 검사기 호출, 자식 프로세스 관리, 결과 집계. 실행 중 추가 Python 패키지 의존성 없음 |
| Python 검사기 | coverage.py와 mutmut을 사용하는 검사 경로 |
| TypeScript 검사기 | Vitest·Istanbul과 Stryker를 사용하는 검사 경로 |
| Java 검사기 | Maven·JaCoCo와 mutate4java를 사용하는 검사 경로 |
| Claude Code·Codex 플러그인 | 두 AI 도구가 같은 사용 지침을 읽고 SENTINEL 실행기를 호출 |
| GitHub Actions·승인 목록 | 언어 검사기의 CI 결과와 실행 파일 지문을 확인해 승인된 버전을 관리 |

## 사용 가이드

설치할 대상을 먼저 구분하면 명령이 헷갈리지 않습니다.

| 대상 | 설치하는 이유 | 설치 시점 |
|---|---|---|
| Claude Code 또는 Codex | AI에게 작업을 요청하기 위해 | 사용할 컴퓨터에서 처음 한 번 |
| SENTINEL 플러그인 | AI에게 SENTINEL 사용법을 알려 주기 위해 | 사용할 AI 도구마다 한 번 |
| SENTINEL 실행기와 언어 도구 | 실제 품질 검사를 수행하기 위해 | 실행기는 한 번, 언어 도구는 필요한 언어를 추가할 때 |

플러그인은 실행기·SDK를 포함하지 않습니다. **플러그인을 설치했어도 2~5단계가 필요합니다.** AI 없이 터미널에서만 쓸 분은 1단계와 6단계를 건너뛰면 됩니다.

<a id="step-0"></a>

### 0. 실행 환경 확인

| 운영체제 | 실제 검사를 실행할 곳 |
|---|---|
| Linux | Linux 터미널. 실제 통합 검증 환경은 Ubuntu x86_64 |
| Windows | WSL2의 Ubuntu. Windows의 Claude Code·Codex에서 이 환경을 호출할 수 있음 |
| macOS | 현재 통합 설치 미지원. Linux의 `renameat2` 기능이 필요함 |

준비물은 인터넷 연결, Git, Linux 쪽 Python 3.9 이상과 가상환경 생성 기능입니다. 검사할 프로젝트에는 소스와 실행 가능한 테스트가 있어야 합니다. AI로 요청하려면 해당 AI 도구의 설치·로그인도 마칩니다.

**Windows PowerShell에서** WSL 상태를 확인합니다.

```powershell
# 설치된 Linux 배포판과 WSL 버전을 확인합니다.
wsl --list --verbose
```

`Ubuntu` 행의 `VERSION`이 `2`인지 확인하세요. WSL이 없다면 **관리자 PowerShell에서** 아래 명령으로 설치하고 재부팅·Ubuntu 사용자 생성을 마칩니다. 기존 배포판이 있다면 재설치하지 말고 [Microsoft 안내](https://learn.microsoft.com/en-us/windows/wsl/install)를 따르세요.

```powershell
# Ubuntu를 포함한 WSL을 설치합니다. 이미 준비되어 있으면 실행하지 않습니다.
wsl --install -d Ubuntu
```

각 단계에서 **명령을 입력할 곳**을 확인하세요. PowerShell은 Windows의 AI 플러그인 설치, Ubuntu/Linux 터미널은 실행기 설치와 검사, AI 대화창은 자연어 요청에 사용합니다.

<a id="step-1"></a>

### 1. AI 플러그인 설치

**SENTINEL 저장소를 미리 `git clone`할 필요는 없습니다.** `marketplace add`로 GitHub의 설치 목록을 등록한 뒤, Claude Code의 `plugin install` 또는 Codex의 `plugin add`로 플러그인을 설치합니다. 원하는 AI 도구만 선택하세요. 둘 다 쓰면 각각 설치합니다.

**Windows PowerShell에서 Claude Code를 사용할 때:**

```powershell
# 먼저 Claude Code 명령과 플러그인 기능이 있는지 확인합니다.
claude --version
claude plugin --help

# 설치 목록 등록 후 플러그인을 설치합니다.
claude plugin marketplace add hwain-ai/SENTINEL
claude plugin install sentinel@sentinel
```

**Windows PowerShell에서 Codex를 사용할 때:**

```powershell
# 먼저 Codex 명령과 플러그인 기능이 있는지 확인합니다.
codex --version
codex plugin --help

# 설치 목록 등록 후 플러그인을 설치합니다.
codex plugin marketplace add hwain-ai/SENTINEL
codex plugin add sentinel@sentinel
```

Linux에서 AI 도구를 쓰는 경우에도 같은 명령을 Linux 터미널에 입력합니다. `sentinel@sentinel`에는 역슬래시를 넣지 않습니다. Claude Code의 `--scope user`는 기본 설치 범위이므로 생략해도 사용자 전체 범위로 설치됩니다.

**확인:** 설치 명령이 성공하면 해당 AI 도구에서 새 대화를 열어 SENTINEL 스킬을 확인합니다. 아직 실제 품질 검사는 하지 않은 상태입니다. 명령이 인식되지 않으면 [명령을 찾을 수 없을 때](#command-not-found)를 먼저 해결하세요. [Claude Code 설치 목록 안내](https://code.claude.com/docs/en/discover-plugins)

<a id="step-2"></a>
<a id="통합-명령-설치"></a>

### 2. SENTINEL 실행기 설치

**Ubuntu/Linux 터미널에서 실행합니다.** Windows PowerShell에 아래 Bash 명령을 그대로 붙여 넣지 마세요. Windows에서는 시작 메뉴의 Ubuntu를 열거나 PowerShell에서 `wsl -d Ubuntu`로 들어갑니다.

Ubuntu에서 Git·Python·가상환경 기능이 없다면 준비합니다. 다른 Linux 배포판은 해당 배포판의 패키지 관리자를 사용합니다.

```bash
# Ubuntu 패키지 목록을 갱신하고 설치에 필요한 도구를 준비합니다.
sudo apt update
sudo apt install -y git python3 python3-venv
```

다음은 **아직 설치 폴더가 없는 새 설치**의 명령입니다. 같은 경로가 이미 있다면 덮어쓰거나 삭제하지 말고 [갱신 절차](#승인된-도구-버전-갱신)를 확인하세요.

```bash
# 실행기를 둘 사용자 전용 폴더를 만듭니다. HOME은 Linux 사용자 홈입니다.
mkdir -p "$HOME/.local/share/sentinel"

# 이 단계는 플러그인이 아니라 실제 실행기 소스를 받습니다. LF 줄바꿈을 유지합니다.
git clone --depth 1 --config core.autocrlf=false https://github.com/hwain-ai/SENTINEL.git "$HOME/.local/share/sentinel/SENTINEL"
cd "$HOME/.local/share/sentinel/SENTINEL"

# 시스템 Python과 분리된 가상환경을 만들고, 현재 폴더의 실행기를 설치합니다.
python3 -m venv .venv
.venv/bin/python -m pip install .

# 설치한 실행 파일의 절대 경로를 저장합니다.
SENTINEL_EXECUTABLE="$HOME/.local/share/sentinel/SENTINEL/.venv/bin/sentinel"
"$SENTINEL_EXECUTABLE" --version
```

**확인:** 현재 배포 버전은 `0.2.0`입니다. 설치 시 빌드에 필요한 setuptools를 내려받을 수 있습니다. 이 단계에서는 다른 언어의 SDK나 검사기를 아직 설치하지 않습니다.

이 가이드는 `sentinel`을 시스템 PATH에 추가하는 대신 실행 파일의 경로를 사용합니다. 따라서 실행기 폴더로 매번 이동할 필요가 없습니다. 새 Ubuntu/Linux 터미널을 열면 `SENTINEL_EXECUTABLE=...` 줄을 다시 실행하세요.

<a id="step-3"></a>

### 3. 검사할 프로젝트 지정

**Ubuntu/Linux 터미널에서**, 실행기 저장소가 아닌 **검사하려는 프로젝트**로 이동합니다. 아래 경로는 예시이므로 실제 프로젝트 경로로 바꿉니다. **`cd`가 실패하면 멈추고 경로부터 고치세요.**

```bash
# 예시 경로를 검사할 프로젝트의 실제 경로로 바꿉니다.
cd "$HOME/projects/my-app"

# 현재 프로젝트의 절대 경로와 언어 도구 보관 위치를 저장합니다.
SENTINEL_PROJECT="$(pwd -P)"
SENTINEL_TOOLS="$HOME/.local/share/sentinel/tools"

# 표시된 프로젝트가 검사하려는 폴더인지 확인합니다.
printf '프로젝트: %s\n실행기: %s\n도구: %s\n' "$SENTINEL_PROJECT" "$SENTINEL_EXECUTABLE" "$SENTINEL_TOOLS"
```

이 가이드는 언어 도구를 WSL/Linux 사용자 홈에 보관합니다. 아래 `setup`·`plan`·`doctor`·`check`에서 **같은 `--tools` 경로를 계속 사용**하세요. 이 옵션을 생략하면 기본값은 프로젝트 아래의 `.sentinel-tools/`입니다.

**프로젝트가 Windows 드라이브에 있다면:** WSL은 Windows 폴더를 `/mnt/c/...` 같은 경로로 읽을 수 있습니다. 다음 명령은 경로를 바꿔 표시할 뿐, 프로젝트를 이동하거나 복사하지 않습니다.

```bash
# Windows 경로는 예시입니다. 실제 경로로 바꾸고 Ubuntu 터미널에서 실행합니다.
SENTINEL_PROJECT="$(wslpath -u 'C:\work\my-app')"
# 실제 폴더가 있는지 확인합니다. 오류가 나면 다음 단계로 넘어가지 않습니다.
ls -ld "$SENTINEL_PROJECT"
```

**Windows 폴더를 읽을 수 있다는 사실이 SENTINEL 검사의 정상 완료를 보장하지는 않습니다.** 원본 쪽 설정·기록 저장에는 파일 권한과 파일시스템 조건도 적용됩니다. 현재 전체 검증은 WSL 내부 프로젝트에서 수행했으며, `/mnt/c` 프로젝트의 처음부터 끝까지 실행은 별도 검증 범위입니다. 처음 사용한다면 WSL 내부 프로젝트에서 시작하는 경로를 권장합니다. [Windows·Linux 파일 접근과 성능](https://learn.microsoft.com/en-us/windows/wsl/filesystems)

<a id="step-4"></a>
<a id="첫-실행-설정"></a>

### 4. 프로젝트 최초 설정

**Ubuntu/Linux 터미널에서** 언어 도구 설치와 프로젝트 설정을 한 번 실행합니다. `setup`은 실행기 설치와 다른 단계입니다. **실제로 검사할 언어를 반드시 지정**하세요. 생략하면 세 언어가 모두 선택됩니다.

아래는 **Python 프로젝트 하나를 처음 등록하는 예시**입니다. TypeScript 프로젝트는 `--language typescript`로 바꿉니다. Maven Java 프로젝트는 `--language java --java-dependencies`를 사용합니다. Java의 이 옵션은 프로젝트의 시험 빌드를 실행하고 의존 패키지를 내려받습니다.

```bash
# setup = 최초 설정; --project = 검사할 폴더; --tools = 언어 도구 보관 폴더
# --crap-max 8 = 복잡도·테스트 범위 점수 상한; --mutation-min 90 = 변이 탐지 비율 90%
# --format json = 구조화된 결과 출력(기본값이므로 생략 가능). 텍스트 요약은 --format text.
"$SENTINEL_EXECUTABLE" setup --project "$SENTINEL_PROJECT" --tools "$SENTINEL_TOOLS" --language python --crap-max 8 --mutation-min 90 --format json
```

Python 테스트가 외부 패키지를 사용하면 위 명령에 `--python-requirements requirements.txt`를 추가합니다. 파일 경로는 **해당 Python 모듈 기준**입니다. TypeScript의 프로젝트별 패키지·빌드 방식이 검사기의 실행 환경과 맞는지도 확인해야 합니다. 지원 언어라고 해서 모든 프레임워크와 기존 빌드 방식이 자동 지원되는 것은 아닙니다.

`setup`은 필요한 언어 저장소를 `~/.sentinel/sources/`에 받고, 버전·다운로드 지문이 기록된 SDK와 검사기를 준비합니다. 세 언어를 모두 준비하면 약 2GB를 내려받을 수 있습니다. 이미 받은 언어 소스를 자동으로 최신화하지는 않습니다.

**확인:** 정상 종료 후 프로젝트에 `sentinel.workspace.json`이 만들어졌는지 확인합니다. Python·TypeScript에는 모듈별 `sentinel.config.json`도 생깁니다. 새 설정의 기본 폴더가 실제 프로젝트와 일치해야 합니다.

| 언어 | 기본 소스 | 기본 테스트 | 확인할 내용 |
|---|---|---|---|
| Python | `src/**/*.py` | `tests/`의 `test_*.py` | 소스·테스트 위치와 외부 패키지 |
| TypeScript | `src/**/*.ts` | `test/`의 `*.test.ts` | 소스·테스트 위치와 Vitest 실행 조건 |
| Java | Maven의 Java 소스 | Maven 테스트 | 해당 모듈의 `pom.xml`과 의존 패키지 |

기본값이 다르면 **첫 검사 전에 설정을 맞춥니다.** 설정 파일 형식과 제외 범위는 [상세 설정](docs/references/sentinel-cli-reference.md#검사-범위-설정)을 참고하세요.

<details>
<summary>Python 서버와 TypeScript 화면처럼 여러 언어가 함께 있다면</summary>

프로젝트 안에 `api/`와 `web/`가 이미 있는 예시입니다. 실제 폴더명으로 바꾸세요. `--module-root`는 검사 폴더를 지정하며, 두 폴더는 같거나 서로 포함 관계일 수 없습니다.

```bash
# 같은 프로젝트 아래 api는 Python, web은 TypeScript로 각각 등록합니다.
"$SENTINEL_EXECUTABLE" setup --project "$SENTINEL_PROJECT" --tools "$SENTINEL_TOOLS" --language python --language typescript --module-root python=api --module-root typescript=web --crap-max 8 --mutation-min 90 --format json
```

이미 등록된 모듈의 폴더와 기준은 유지됩니다. 언어를 추가할 때도 새 언어의 폴더를 명시합니다. 여러 모듈을 전부 `.`으로 지정하면 거부됩니다.

</details>

<a id="step-5"></a>

### 5. 첫 검사와 결과 확인

**Ubuntu/Linux 터미널에서** 세 명령을 순서대로 실행합니다. 앞 단계에서 지정한 세 경로 변수를 계속 사용합니다.

```bash
# 1. 등록된 검사 대상을 확인합니다. 테스트를 실행하지 않습니다.
"$SENTINEL_EXECUTABLE" plan --project "$SENTINEL_PROJECT" --tools "$SENTINEL_TOOLS" --format json

# 2. 설치 파일의 버전·지문·승인 여부를 확인합니다. 테스트나 SDK 동작 시험은 아닙니다.
"$SENTINEL_EXECUTABLE" doctor --project "$SENTINEL_PROJECT" --tools "$SENTINEL_TOOLS" --format json

# 3. 실제 품질 검사를 실행합니다. 등록된 모듈의 범위가 대상입니다.
"$SENTINEL_EXECUTABLE" check --project "$SENTINEL_PROJECT" --tools "$SENTINEL_TOOLS" --format json
```

`plan`의 범위가 맞고 `doctor`에서 선택한 모듈이 `ready`, `admitted=true`인지 확인한 뒤 `check`로 진행하세요. `doctor`가 성공해도 실제 빌드·테스트는 실패할 수 있습니다. 변이 검사는 프로젝트 크기에 따라 수분에서 수시간이 걸릴 수 있으며, 기본 자동 실행 시간 제한은 없습니다.

| 결과 | 사용자가 이해할 의미 | 품질 통과인가? |
|---|---|---|
| `planned` | 검사할 범위를 읽었음 | 아직 검사하지 않음 |
| `ready` | 설치 파일 확인을 마침 | 아직 검사하지 않음 |
| `allConfigured`, 모든 결과가 `passed` | 설정된 전체 범위를 실제 검사해 기준을 충족 | 설정된 전체 범위에서 통과 |
| `partial`, 결과가 `passed` | 선택한 파일·함수·테스트·모듈 또는 변경분 검사가 기준을 충족 | 실제 검사한 범위에서 통과 |
| `qualityFailed` | 검사를 수행했지만 품질 기준에 미달 | 실패 |
| `noChanges` | 검사할 변경 코드가 없어 생략 | 미검사 |
| `baselineFailed` | 원래 테스트부터 실패해 검사 조건이 안 됨 | 실패 원인부터 확인 |
| `dependencyError` | 필요한 설치 파일이나 실행 의존성이 부족함 | 검사 준비 필요 |
| `backendNotAdmitted` | 현재 도구가 승인 목록에 없어 실행하지 않음 | 승인된 버전으로 갱신 필요 |

`exitCode`가 0이어도 실제 품질 검사를 했다는 뜻은 아닙니다. `results[].status`가 `passed`인지 확인하고, `selection`과 `details.scope`로 그 결과의 범위를 확인합니다. `mutation.pass`는 변이 점수의 기준 충족 여부이며, `inScope`는 점수 계산에 포함한 변이 개수입니다. [JSON 조각별 결과 해석](docs/results.md)에 예시가 있습니다.

<a id="step-6"></a>

### 6. AI 대화창에서 검사 요청

이제 **Claude Code 또는 Codex의 대화창**에서 요청합니다. 2~4단계를 마쳤다면 같은 설치를 다시 할 필요가 없습니다. 실행기만 설치된 상태라면 플러그인에 프로젝트 최초 설정부터 요청할 수도 있습니다.

먼저 Ubuntu/Linux 터미널에서 실제 경로를 확인합니다. AI가 이 셸 변수의 값을 자동으로 아는 것은 아닙니다.

```bash
# 출력된 경로를 아래 요청문에 넣습니다.
printf '실행기: %s\n프로젝트: %s\n언어 도구: %s\n' "$SENTINEL_EXECUTABLE" "$SENTINEL_PROJECT" "$SENTINEL_TOOLS"
```

다음 요청문의 `<...>`를 실제 값으로 바꾸어 입력하세요. Linux에서 직접 실행한다면 실행 환경을 Linux로 적고 WSL 배포판 항목은 생략합니다.

```text
SENTINEL 스킬로 이 프로젝트의 설치 상태를 진단해 줘.

실행 환경: Windows의 WSL2
WSL 배포판: Ubuntu
신뢰하고 사용할 SENTINEL 실행 파일: <위에서 출력한 실행기 절대 경로>
검사할 프로젝트: <위에서 출력한 프로젝트 절대 경로>
언어 도구 폴더: <위에서 출력한 언어 도구 절대 경로>

이번에는 doctor로 설치 상태만 확인하고 결과를 설명해 줘.
```

설치 상태를 확인한 뒤 같은 대화에서 아래처럼 요청합니다.

| 하고 싶은 일 | 대화창에 입력할 요청 |
|---|---|
| 최초 설정 | `이 경로의 프로젝트에 Python 검사 환경을 setup으로 준비해 줘. CRAP 상한은 8, 변이 탐지 비율은 90%로 설정해 줘.` |
| 검사 범위 확인 | `같은 프로젝트의 검사 범위를 SENTINEL plan으로 확인해 줘.` |
| 전체 등록 모듈 검사 | `같은 프로젝트의 등록된 모든 모듈에 기본 품질 검사를 실행해 줘.` |
| 수정한 코드 검사 | `같은 프로젝트에서 HEAD 이후 변경한 코드만 검사해 줘.` |
| 함수와 테스트 선택 | `src/pricing.py의 calculate_discount 함수를 tests/test_pricing.py로 검사해 줘.` |

최초 설정 요청의 언어·폴더는 실제 프로젝트에 맞게 바꿉니다. CLI가 없거나 신뢰할 실행 경로를 확인할 수 없으면 현재 플러그인은 중단합니다. 그때는 [2단계](#step-2)부터 준비해야 합니다. 새 대화에는 위 경로 정보를 다시 알려 주세요.

## 검사는 어디에서 실행되나요?

**검사기가 임시 복사본을 만들고 그 안에서 테스트와 변이 검사를 실행합니다.** 사용자가 검사할 때마다 프로젝트를 수동으로 복사할 필요는 없습니다.

```mermaid
flowchart LR
    A["원본 프로젝트<br/>소스·테스트 읽기"] --> B["검사기가<br/>임시 복사본 생성"]
    B --> C["복사본에서<br/>테스트·품질 검사"]
    C --> D["결과 수집<br/>임시 복사본 정리"]
```

Windows에서 WSL 검사기를 쓰면 기본 임시 폴더는 WSL 쪽에 만들어집니다. 실제 위치는 임시 폴더 환경 설정에 따라 달라집니다. Python은 커버리지와 변이 검사에 각각 복사본을 만들고, TypeScript와 Java도 임시 복사본을 사용합니다. `.git`이나 기존 빌드 결과 등은 언어별 규칙에 따라 복사에서 제외합니다. 정상적인 정리 경로에서 복사본을 삭제하며, 강제 종료 뒤까지 정리를 보장하는 뜻은 아닙니다.

원본 프로젝트에도 **설정·상태 파일**이 생길 수 있습니다. 검사 복사본과 용도가 다릅니다.

| 위치 | 내용 |
|---|---|
| 원본의 `sentinel.workspace.json` | 등록한 모듈과 품질 기준 |
| 각 Python·TypeScript 모듈의 `sentinel.config.json` | 소스·테스트 위치 등 언어별 설정 |
| 일부 검사기의 원본 `.sentinel/` | 결과·상태 기록 |
| 원본 `.sentinel-deps/`, `.sentinel-m2/` | 옵션으로 준비한 Python·Maven 의존 패키지 |
| 이 가이드의 `~/.local/share/sentinel/tools/` | 언어 도구 묶음. `--tools` 생략 시 원본 `.sentinel-tools/`가 기본값 |
| WSL/Linux 임시 폴더 | 실제 빌드·테스트·변이 검사를 수행하는 복사본 |

생성되는 상태·도구·의존 패키지 폴더는 프로젝트의 `.gitignore`에 반영하세요. Maven의 **최초 의존성 준비**는 원본 모듈에서 시험 빌드를 실행하므로 `target/` 같은 빌드 결과도 생길 수 있습니다. 이는 복사본에서 실행하는 품질 검사 단계와 구분합니다. 임시 복사본을 쓴다고 파일·네트워크 접근을 강제 차단하는 보안 컨테이너가 되는 것은 아닙니다.

## 자주 쓰는 명령

아래는 **Ubuntu/Linux 터미널**용입니다. 새 터미널에서는 2~3단계의 `SENTINEL_EXECUTABLE`, `SENTINEL_PROJECT`, `SENTINEL_TOOLS`를 다시 지정합니다.

```bash
# HEAD 이후 바뀐 코드만 검사합니다. 프로젝트가 Git 저장소여야 합니다.
"$SENTINEL_EXECUTABLE" check --project "$SENTINEL_PROJECT" --tools "$SENTINEL_TOOLS" --changed --format json

# 등록된 Python 모듈만 선택합니다.
"$SENTINEL_EXECUTABLE" check --project "$SENTINEL_PROJECT" --tools "$SENTINEL_TOOLS" --language python --format json

# 특정 기능 함수와 실행할 테스트 파일을 선택합니다. 함수명에 ()를 붙이지 않습니다.
"$SENTINEL_EXECUTABLE" check --project "$SENTINEL_PROJECT" --tools "$SENTINEL_TOOLS" --file src/pricing.py --function calculate_discount --tests tests/test_pricing.py --format json

# 설정된 기능 코드 전체와 기본 테스트 묶음을 검사합니다.
"$SENTINEL_EXECUTABLE" check --project "$SENTINEL_PROJECT" --tools "$SENTINEL_TOOLS" --all --format json
```

`--changed-base main`을 추가하면 기준을 `main`으로 바꿉니다. 해당 Git 참조가 실제로 있어야 합니다. 변경한 생산 코드를 검사 대상으로 선택해도 테스트는 전체 실행할 수 있으므로 반드시 빨리 끝난다는 뜻은 아닙니다. README만 바뀐 경우처럼 검사할 생산 코드가 없으면 `noChanges`가 될 수 있습니다.

`--file`은 기능 파일, `--function`은 그 파일 안의 함수, `--tests`는 실행할 테스트 파일입니다. 파일·테스트 옵션은 반복할 수 있고, 함수 선택은 파일 하나와 함께 사용합니다. `--tests`를 생략하면 설정된 테스트 묶음을 사용합니다. 기본 검사는 자동 시간 제한 없이 실행합니다. 테스트만 수정했어도 같은 기능 파일·함수를 지정해 재검사할 수 있습니다.

`results[].details`에는 실제 범위(`scope`), 함수별 CRAP과 파일별 최댓값(`crap`), 파일·함수별 mutation 탐지율과 변이 위치·상태(`mutation`)가 담깁니다. 부분 검사의 `passed`는 그 범위의 통과입니다. 검사 범위는 `selection`과 `scope`로 확인합니다. SENTINEL은 LLM 없이 측정값을 반환합니다. [결과 해석](docs/results.md)을 참고하세요.

Windows PowerShell에서 직접 호출해야 한다면 다음 형식을 사용합니다. `<...>`는 확인한 실제 Linux 경로로 바꿉니다. 대화로 요청할 때는 플러그인이 이 호출을 구성합니다.

```powershell
# --exec 뒤에는 WSL 안의 실행 파일과 각 인자를 전달합니다.
wsl.exe -d Ubuntu --exec "/home/<사용자>/.local/share/sentinel/SENTINEL/.venv/bin/sentinel" check --project "/home/<사용자>/projects/my-app" --tools "/home/<사용자>/.local/share/sentinel/tools" --format json
```

## 문제 해결

<a id="command-not-found"></a>

### PowerShell에서 codex 또는 claude 명령을 찾지 못합니다

앱의 실행 파일이 있어도 외부 PowerShell의 **PATH(명령을 찾을 폴더 목록)**에 등록되지 않았을 수 있습니다. 먼저 사용할 도구의 명령을 확인합니다.

```powershell
# 사용할 도구의 실행 파일 위치가 나오는지 확인합니다.
Get-Command codex
# Claude Code를 사용할 때 확인합니다.
Get-Command claude
```

찾지 못하면 [Codex CLI 공식 설치 안내](https://learn.chatgpt.com/docs/codex/cli) 또는 [Claude Code 공식 설치 안내](https://code.claude.com/docs/en/setup)에 따라 터미널용 실행기를 준비하고 **새 PowerShell 창**에서 `--version`을 확인하세요. 앱 내부에서 명령이 실행된다는 사실만으로 외부 터미널의 등록 상태를 판단하면 안 됩니다. 앱의 버전별 내부 경로를 다른 사용자 컴퓨터에 그대로 복사하지 않습니다.

버전이 나와도 `plugin` 하위 명령이 없다면 해당 호스트를 플러그인 기능이 지원되는 버전으로 갱신한 뒤 `plugin --help`로 확인합니다.

### 설치 명령을 실행했는데 sentinel 명령은 없습니다

`claude plugin install`과 `codex plugin add`는 플러그인 지침을 설치합니다. 실제 실행기는 [2단계](#step-2)에서 따로 설치하고 안내한 절대 경로로 실행합니다. 플러그인 설치만으로 시스템에 `sentinel` 명령이 등록되지는 않습니다.

### 설정이나 검사가 실패합니다

| 증상 | 확인할 것 |
|---|---|
| 마켓플레이스나 플러그인을 찾지 못함 | `marketplace add`가 성공했는지, `sentinel@sentinel`에 오타·역슬래시가 없는지 확인 |
| 실행기 경로가 없다고 함 | WSL 안의 절대 경로와 배포판 이름을 전달했는지 확인 |
| `nestedModuleRoots` 또는 폴더 지정 오류 | 언어별 `--module-root`가 서로 같거나 포함 관계인지 확인 |
| `dependencyError` | `--tools`가 최초 설정과 같은지 확인. 필요한 언어와 의존 패키지를 `setup`으로 준비 |
| `unclassifiedSource` | 소스·테스트 범위를 확인하고, 빌드 설정 파일 등 검사 대상이 아닌 파일만 명시적으로 제외 |
| `baselineFailed` | 원래 테스트의 실패나 실행 환경 문제부터 해결 |
| `backendNotAdmitted` | [실행기와 언어 도구 갱신](#승인된-도구-버전-갱신). 우회 실행을 정식 통과로 취급하지 않음 |
| `noChanges` | 실제로 검사할 생산 코드 변경이 있는지 확인. 전체 검사를 원하면 `--changed`를 제거 |
| Windows 원본에서 권한·파일 기록 오류 | `/mnt/c` 접근과 검사 완료는 별개. WSL 내부 프로젝트와 도구 경로에서 확인 |
| 설치 중 `workspaceChanged` | 사용자가 바꾼 최신 설정은 유지됨. 현재 설정을 검토한 뒤 `setup` 재실행 |

## 승인된 도구 버전 갱신

플러그인·통합 실행기·언어 도구는 별도로 설치됩니다. **플러그인 갱신만으로 언어 검사기가 갱신되지는 않습니다.** 파일·함수·테스트 선택을 지원하는 어댑터 버전은 Python·TypeScript `0.1.3`, Java `0.1.4`입니다. 승인 여부는 실행기에 포함된 [승인 목록](src/sentinel/admission.json)으로 확인합니다. 이전 승인 항목은 기존 설치의 일반 검사를 위해 유지하며, 선택 기능을 사용하려면 실행기와 해당 언어 도구를 함께 갱신합니다.

`setup`은 기존 언어 소스 저장소를 자동 갱신하지 않습니다. 아래는 이 가이드로 설치한 실행기와 기존 Python 프로젝트를 갱신하는 예시입니다. 저장소에 직접 수정한 파일이 있다면 먼저 검토하고 실패한 Git 갱신을 강제로 덮어쓰지 않습니다.

```bash
# 실행기 소스를 갱신하고 같은 가상환경에 다시 설치합니다.
git -C "$HOME/.local/share/sentinel/SENTINEL" pull --ff-only
"$HOME/.local/share/sentinel/SENTINEL/.venv/bin/python" -m pip install --force-reinstall "$HOME/.local/share/sentinel/SENTINEL"

# 아직 없는 새 소스 폴더를 사용합니다. 기존 프로젝트·도구 경로는 유지합니다.
SENTINEL_SOURCES="$HOME/.sentinel/sources-$(date -u +%Y%m%dT%H%M%SZ)"
"$SENTINEL_EXECUTABLE" setup --project "$SENTINEL_PROJECT" --tools "$SENTINEL_TOOLS" --language python --sources "$SENTINEL_SOURCES" --format json
```

기존에 사용한 `--config`, `--python-requirements`, `--java-dependencies`가 있다면 함께 지정합니다. 새 버전은 기존 도구 묶음 옆에 설치되며 이전 묶음을 덮어쓰지 않습니다. 갱신 후 5단계의 진단과 검사를 다시 수행합니다.

## 프로젝트 구조

```text
SENTINEL/
├── README.md                 # 처음 설치하는 사람을 위한 사용 가이드
├── pyproject.toml            # 버전·Python 조건·설치 진입점
├── src/sentinel/
│   ├── cli.py                # 명령 처리와 결과 집계
│   ├── selection.py          # 파일·함수·테스트 선택
│   ├── diagnostics.py        # 함수·파일별 점수와 측정 근거
│   ├── setup.py              # 언어 도구 준비와 프로젝트 설정
│   ├── bundle.py             # 도구 묶음 검증과 설치
│   ├── protocol.py           # 언어 검사기 호출과 응답 검증
│   └── admission.json        # 승인된 언어 검사기 목록
├── plugins/sentinel/         # 두 AI 도구가 함께 쓰는 플러그인
├── .claude-plugin/           # Claude Code 설치 목록
├── .agents/plugins/         # Codex 설치 목록
├── scripts/                  # 문서 검사·승인 목록 관리 도구
├── tests/                    # 통합 실행기 시험
└── docs/                     # 사용법·결과 해석·개발 참고
```

## 관련 문서

- [문서 목록](docs/index.md): 문서별 내용과 관련 코드
- [결과 해석과 출력 예시](docs/results.md): 점수·변이 개수·판정·오류 구분
- [명령·설정·도구 제작 상세 계약](docs/references/sentinel-cli-reference.md)
- [플러그인 안내와 공통 사용 지침](plugins/sentinel/README.md)
- [사용하는 외부 도구](docs/references/sentinel-quality-tools-reference.md)
- [개발과 문서 수정](docs/contributing.md): 변경 코드에 맞는 문서 확인과 push 전 검사
- [MIT 라이선스](LICENSE)
