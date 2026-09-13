---
name: sentinel
description: 기존의 신뢰된 SENTINEL CLI로 명시된 워크스페이스의 계획, 설치 진단 또는 기본 품질 검사를 요청할 때 사용한다. 설명만 요청한 경우에는 실행하지 않는다.
---

# SENTINEL 워크스페이스 검사

사용자의 의도와 검사 범위를 먼저 확인한다. 실행 요청이면 사용자가 선택한, 이미 설치되어 신뢰할 수 있는 SENTINEL 0.1.0 실행 파일을 `SENTINEL_EXECUTABLE`로 사용하고 사용자가 명시한 프로젝트 루트를 `SENTINEL_PROJECT`로 사용한다. 프로젝트 안의 임의 파일을 실행해 실행 파일을 찾거나, 프로젝트 설정을 추측하거나, 비밀 정보를 요청하지 않는다. 두 필수 경로 중 하나라도 없거나 확인할 수 없으면 누락된 전제 조건을 설명하고 중단한다.

요청 의도에 맞춰 다음 중 하나만 실행한다. 사용법 설명만 요청한 경우에는 `check`를 포함해 어떤 명령도 실행하지 않는다.

- 구조와 선택 대상만 확인하려면 `plan`을 사용한다.
- 설치된 도구의 준비 상태를 확인하려면 `doctor`를 사용한다.
- 품질 검사가 명시적으로 요청되면 우회 옵션 없는 기본 `check`를 사용한다.
- 방금 고친 코드만 검사해 달라는 요청이면 기본 `check` 뒤에 `--changed`를 붙인다. 기준 커밋을 사용자가 지정하면 `--changed-base <ref>`도 붙인다. 변경 파일이 없는 모듈은 `noChanges`로 표시되며 이는 통과가 아니라 미검사다.

`--config`와 `--tools`는 사용자가 경로를 명시했을 때만 추가한다. 범위 선택도 사용자가 명시했을 때만 반복 가능한 `--language` 또는 반복 가능한 `--module` 중 하나를 추가하며 둘을 함께 쓰지 않는다. 설치 이름만 보고 지원 언어를 만들어 내지 않는다. 모든 경로와 선택 값은 개별 인자로 전달한다.

```bash
# $SENTINEL_EXECUTABLE은 사용자가 선택한 신뢰된 실행 파일, plan은 실행 없이 대상을 계획하는 명령, --project와 $SENTINEL_PROJECT는 명시된 프로젝트 루트, --format json은 JSON 결과 요청이다.
"$SENTINEL_EXECUTABLE" plan --project "$SENTINEL_PROJECT" --format json
```

```bash
# $SENTINEL_EXECUTABLE은 사용자가 선택한 신뢰된 실행 파일, doctor는 설치 상태 진단 명령, --project와 $SENTINEL_PROJECT는 명시된 프로젝트 루트, --format json은 JSON 결과 요청이다.
"$SENTINEL_EXECUTABLE" doctor --project "$SENTINEL_PROJECT" --format json
```

```bash
# $SENTINEL_EXECUTABLE은 사용자가 선택한 신뢰된 실행 파일, check는 기본 품질 검사 요청, --project와 $SENTINEL_PROJECT는 명시된 프로젝트 루트, --format json은 JSON 결과 요청이다.
"$SENTINEL_EXECUTABLE" check --project "$SENTINEL_PROJECT" --format json
```

JSON의 실제 `selection`, 모듈별 `status`와 `exitCode`, 전체 `pass`, `certified`, `exitCode`를 기준으로 결과를 요약한다. `planned`나 `ready`, 또는 검사 외 명령의 종료 코드 0은 품질 인증이 아니다. 기본 `check`가 거부되면 그 상태와 종료 코드를 그대로 설명하고 우회하지 않는다.

## 첫 실행 설정

프로젝트에 `sentinel.workspace.json`이 없거나 `doctor`가 `dependencyError`를 보고하면, 검사할 언어(python, typescript, java 중 복수 가능)와 기준값을 사용자에게 확인한 뒤 `setup`을 실행한다. 기준값은 CRAP 상한 `--crap-max`(기본 8)와 변이 검사의 최소 kill 비율 `--mutation-min`(기본 100)이며, 소수점 두 자리까지의 숫자 문자열로 넘긴다. `setup`은 언어 저장소를 사용자 홈의 `.sentinel/sources`에 받고, 잠금 파일에 적힌 공식 주소·지문으로만 언어 SDK를 내려받은 뒤, 도구 묶음을 설치하고 두 설정 파일을 쓴다. 세 언어를 모두 준비하면 약 2GB를 내려받으므로 실행 전에 반드시 사용자 승인을 받는다. 언어는 `--language`를 반복해 지정한다.

```bash
# $SENTINEL_EXECUTABLE은 사용자가 선택한 신뢰된 실행 파일, setup은 첫 실행 설정 명령, --project와 $SENTINEL_PROJECT는 명시된 프로젝트 루트, --language와 $SENTINEL_LANGUAGE는 준비할 언어 하나(반복 가능), --format json은 JSON 결과 요청이다.
"$SENTINEL_EXECUTABLE" setup --project "$SENTINEL_PROJECT" --language "$SENTINEL_LANGUAGE" --format json
```

Python 프로젝트의 테스트가 외부 패키지를 쓰면 사용자에게 요구사항 파일 경로를 확인한 뒤 `--python-requirements <프로젝트 기준 상대 경로>`를 `setup`에 붙인다. Maven 프로젝트(`pom.xml`)는 사용자 승인을 받은 뒤 `--java-dependencies`를 붙인다. `setup`이 그 프로젝트의 기본 시험 빌드를 온라인으로 한 번 실행해 빌드 의존성을 `<프로젝트>/.sentinel-m2`에 받고, 이후 검사는 그 폴더만으로 오프라인 실행된다. 이 폴더가 없으면 검사기의 잠긴 저장소만 쓰므로 외부 의존성이 있는 프로젝트는 검사가 실패한다. `setup`이 만든 `sentinel.config.json`의 production·testRoots 기본값은 일반적인 폴더 구조를 가정한 것이다. 결과의 `projectConfig`가 `created`이면 사용자에게 실제 소스·테스트 폴더와 맞는지 확인하도록 안내한다. 검사가 `unclassifiedSource`로 거부되면 그 파일이 생산 코드도 테스트도 아닌지 사용자에게 확인한 뒤 해당 모듈의 `excluded` 글롭 목록에 추가한다. `setup` 외의 방법으로 SDK·패키지·컨테이너를 설치하지 않는다.

`--experimental`을 추가하지 않는다. 도구가 없거나 손상되면 위 `setup` 외의 방법으로 설치하지 않고 전제 조건이 충족되지 않았다고 설명한다. 오류가 나도 네이티브 엔진을 직접 실행해 재시도하지 않고, 잠금이나 설정을 바꾸지 않으며, `setup` 외의 SDK 설치, 컨테이너 생성, 플러그인 등록이나 활성화, 거부를 피하기 위한 네트워크 호출을 하지 않는다. 사용자 요약에는 원본 소스, 비밀 정보, 실제 경로 또는 길이 제한 없는 로그를 출력하지 않는다.
