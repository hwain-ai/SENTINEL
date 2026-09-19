## 첫 호출에서 준비하기

현재 프로젝트 폴더, `sentinel.workspace.json`, 사용 언어와 소스·테스트 폴더를 먼저 확인한다. 실행기는 사용자가 알려 준 경로, 현재 환경의 `sentinel`, 사용자 홈의 `.local/share/sentinel/SENTINEL/.venv/bin/sentinel` 순서로 확인한다. 설치된 프로그램을 덮어쓰지 않는다.

실행기가 없거나 필요한 언어 도구가 없으면 사용자가 설치 프롬프트를 작성하게 하지 않는다. 확인된 환경·프로젝트·언어를 요약하고 아직 모르는 항목과 설치 동의만 함께 묻는다. 예: "현재 프로젝트는 Python입니다. SENTINEL 실행기와 Python 검사 도구를 이 환경에 설치하고 검사를 이어갈까요?" 기존 대화에서 해당 설치가 승인됐다면 바로 진행한다. Windows는 WSL 배포판·프로젝트 경로를 확인한다.

승인 후 Linux·macOS 또는 확인된 WSL 안에서 공식 실행기를 설치한다. Git과 Python 3.9+·가상환경 기능을 확인하고, 없는 시스템 도구는 필요한 설치를 안내한다. 아래는 설치 경로가 아직 없는 경우다.

```sh
mkdir -p "$HOME/.local/share/sentinel"
git clone --depth 1 --config core.autocrlf=false https://github.com/hwain-ai/SENTINEL.git "$HOME/.local/share/sentinel/SENTINEL"
python3 -m venv "$HOME/.local/share/sentinel/SENTINEL/.venv"
"$HOME/.local/share/sentinel/SENTINEL/.venv/bin/python" -m pip install "$HOME/.local/share/sentinel/SENTINEL"
```

확인한 실행기·프로젝트 경로로 아래 `setup`을 수행한다. 설정의 기능 코드·테스트 범위를 실제 폴더와 대조하고 `plan`·`version`을 확인한다. `start`만 요청했다면 준비 완료를 보고하고 끝낸다. 검사 또는 수정·재검사도 요청했다면 그 작업을 이어간다. 다음 호출에서는 기존 실행기와 프로젝트 설정을 사용한다. 플러그인 설치 직후의 훅이 아니라 스킬 호출에서 준비한다.

## 실행 파일과 프로젝트 경로를 분리한 기본 호출

`SENTINEL_EXECUTABLE`은 확인된 실행 파일, `SENTINEL_PROJECT`는 프로젝트 루트다. `plan`은 설정된 모듈 목록, `version`는 설치 상태, `check`는 실제 검사다. `setup`을 포함한 네 명령 모두 JSON이 기본 출력이므로 아래의 `--format json`은 생략할 수 있다. 텍스트 요약은 `--format text`로 요청한다.

```sh
"$SENTINEL_EXECUTABLE" plan --project "$SENTINEL_PROJECT" --format json
"$SENTINEL_EXECUTABLE" version --project "$SENTINEL_PROJECT" --format json
"$SENTINEL_EXECUTABLE" check --project "$SENTINEL_PROJECT" --format json
```

## Windows에서 WSL로 호출

Windows 호스트에서는 SENTINEL을 네이티브 Python으로 실행하지 않는다. 사용자가 지정했거나 이번 설치 작업에서 확인한 WSL 배포판 이름, WSL 안의 SENTINEL 실행 파일 절대 경로, WSL 안의 프로젝트 절대 경로를 사용한다. Windows 경로를 Linux 경로로 추측해서 바꾸지 않는다. 필요한 경우 지정된 배포판의 `wslpath`로 변환하고 실제 대상 폴더를 확인한다. 새 설치는 WSL 내부 파일 시스템에서 진행하며 Git의 LF 줄바꿈을 보존한다.

PowerShell에서는 다음과 같이 실행한다. `SENTINEL_DISTRIBUTION`은 확인한 배포판 이름이다. 명령과 각 옵션은 개별 인자로 전달하고, 명령 전체를 하나의 문자열이나 `bash -c`로 조립하지 않는다. `plan` 대신 요청 의도에 맞는 `version`, `check`, `setup`을 같은 방식으로 호출한다.

```powershell
# wsl.exe는 지정한 Linux 환경에서 명령을 실행하고, --exec 뒤에는 확인한 실행 파일과 개별 인자를 전달한다.
& wsl.exe -d $SENTINEL_DISTRIBUTION --exec $SENTINEL_EXECUTABLE plan --project $SENTINEL_PROJECT --format json
```

이미 WSL 안에서 실행 중이면 앞의 Linux 명령 예시를 그대로 사용한다. WSL 접근이나 실행이 거부되면 실제 오류를 알리고 호스트의 정상 승인 절차를 따른다. 실패를 성공으로 바꾸거나 다른 검사 엔진으로 대신 실행하지 않는다.

## 첫 실행 설정

이 플러그인이 지원하는 언어는 Python, TypeScript, Java 세 가지다. 프로젝트에 `sentinel.workspace.json`이 없거나 `version`이 `dependencyError`를 보고하면, 검사할 언어와 기준값, 모듈 폴더를 확인해 `setup`을 실행한다. 같은 대화에서 사용자가 이미 설치와 해당 범위를 승인했다면 다시 승인을 요청하지 않는다. 다른 언어의 검사는 요청받아도 실행하지 않고 지원 범위 밖이라고 설명한다. 기준값은 CRAP 상한 `--crap-max`(기본 8)와 변이 검사의 최소 kill 비율 `--mutation-min`(기본 90)이며, 소수점 두 자리까지의 숫자 문자열로 넘긴다. `setup`은 언어 저장소를 사용자 홈의 `.sentinel/sources`에 받고, 잠금 파일에 적힌 공식 주소·지문으로만 언어 SDK를 내려받은 뒤, 도구 묶음을 설치하고 설정 파일을 쓴다. 세 언어를 모두 준비하면 약 2GB를 내려받으므로 설치 요청이 아직 승인되지 않았다면 먼저 설명하고 승인받는다. 언어는 `--language`를 반복해 명시한다.

새로 여러 언어를 함께 준비할 때는 `--module-root python=api --module-root typescript=web`처럼 사용자가 확인한 프로젝트 기준 상대 폴더를 언어마다 지정한다. 예시 폴더 이름을 실제 프로젝트에 임의로 적용하지 않는다. 모듈 폴더는 서로 같거나 포함 관계일 수 없다. 기존 모듈의 폴더와 설정은 유지하며, 단일 언어의 새 프로젝트는 기본적으로 프로젝트 루트 `.`을 사용한다. 언어를 생략하면 세 언어가 선택되므로 폴더가 불명확한 상태에서 생략하지 않는다.

```bash
# $SENTINEL_EXECUTABLE은 사용자가 선택한 신뢰된 실행 파일, setup은 첫 실행 설정 명령, --project와 $SENTINEL_PROJECT는 명시된 프로젝트 루트, --language와 $SENTINEL_LANGUAGE는 준비할 언어 하나(반복 가능), --format json은 JSON 결과 요청이다.
"$SENTINEL_EXECUTABLE" setup --project "$SENTINEL_PROJECT" --language "$SENTINEL_LANGUAGE" --format json
```

Python 프로젝트의 테스트가 외부 패키지를 쓰면 사용자에게 요구사항 파일 경로를 확인한 뒤 `--python-requirements <프로젝트 기준 상대 경로>`를 `setup`에 붙인다. Maven 프로젝트(`pom.xml`)는 사용자 승인을 받은 뒤 `--java-dependencies`를 붙인다. `setup`이 그 프로젝트의 기본 시험 빌드를 온라인으로 한 번 실행해 빌드 의존성을 `<프로젝트>/.sentinel-m2`에 받고, 이후 검사는 그 폴더만으로 오프라인 실행된다. 이 폴더가 없으면 검사기의 잠긴 저장소만 쓰므로 외부 의존성이 있는 프로젝트는 검사가 실패한다. `setup`이 만든 `sentinel.config.json`의 production·testRoots 기본값은 일반적인 폴더 구조를 가정한 것이다. 결과의 `projectConfig`가 `created`이면 사용자에게 실제 소스·테스트 폴더와 맞는지 확인하도록 안내한다. 검사가 `unclassifiedSource`로 거부되면 그 파일이 생산 코드도 테스트도 아닌지 사용자에게 확인한 뒤 해당 모듈의 `excluded` 글롭 목록에 추가한다. `setup` 외의 방법으로 SDK·패키지·컨테이너를 설치하지 않는다.

`--experimental`을 추가하지 않는다. 실행기 설치는 위 공식 저장소 절차, 언어 SDK·검사기 설치는 `setup`을 사용한다. 오류가 나도 네이티브 엔진을 직접 실행해 재시도하거나 승인 목록·잠금 파일을 바꾸지 않는다. 거부된 권한을 우회하지 않는다. 결과에는 요청한 파일·함수의 상대 경로와 측정값을 제공한다.
