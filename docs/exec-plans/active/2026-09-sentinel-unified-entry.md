---
type: exec-plan
slug: sentinel-unified-entry
created: 2026-09-08
updated: 2026-09-13
status: active
owner: Codex
spec: docs/product-specs/2026-09-sentinel-unified-entry.md
design: docs/design-docs/2026-09-sentinel-unified-entry.md
covers: 통합-01..통합-06
---

# SENTINEL 통합 명령 실행 계획

목표: 하나의 실행 명령과 언어별 독립 설치라는 승인 방향을, 거짓 통과 없는 실행 가능한 로컬 기반부터 순서대로 구현한다.

## 현재 진행 순서

|구분|현재 확인한 범위|남은 일|
|---|---|---|
|공통 실행부·Go|통합 명령에서 공개 Go 프로젝트 한 개의 결과 반환·시간 제한·취소·원본 보존·컨테이너 정리를 확인했다.|모든 Go 프로젝트 지원이나 정식 품질 통과로 확대하지 않는다.|
|Python|통합 명령에 연결했다. `sentinel setup --language python`이 SENTINEL_PY의 `sentinel-tool/`로 묶음을 만들어 설치하고, 작은 프로젝트에서 setup→doctor→check --experimental 경로로 기본 기준 통과, `--crap-max 0.5` 품질 실패, `--mutation-min 0` 통과와 증거의 기준값 기록을 확인했다. 2026-09-13에 공개 프로젝트 ItsDangerous 2.2.0을 `setup --python-requirements`로 준비해 엄격 검사(종료 2)와 원본 mutmut 직접 실행을 대조했다. 변이 567개에서 SENTINEL killed 72+runtimeError 346 = 직접 killed 418, survived 121, uncovered 28이 일치했고, 이 과정에서 mutmut 실행 환경에 프로젝트 의존성 폴더가 빠져 있던 결함을 고쳤다. [대조 표](https://github.com/hwain-ai/SENTINEL_PY/blob/main/docs/sentinel-python-native-validation.md#현재-원본-mutmut-직접-실행과의-대조-결과2026-09-13)|CI 승인. 변이별 기록은 집계만 남는다.|
|Java|통합 명령에 연결했다. 어댑터(`sentinel-tool/`)가 프로젝트 사본에서 Maven+JaCoCo로 coverage를 만들고 CRAP 판정, 원본 위치에서 mutate4java 변이 판정을 이어 돌린다. 기준값(`--crap-max`, `--mutation-min`)을 CLI에 추가했고, 작은 Maven 프로젝트에서 setup→doctor→check --experimental 기본 통과와 `--crap-max 0.5` 실패, 원본에 target 미생성을 확인했다. 2026-09-13에 공개 프로젝트 Apache Commons CLI 1.10.0을 `setup --language java --java-dependencies`로 준비(온라인 `mvn test` 1회, 968개 테스트 통과, 102초)하고 검사했다. 전체 변이 검사는 변이 1개마다 `mvn test`를 돌려 약 40초가 걸리므로 중단했고, 주석 한 줄을 고친 MissingOptionException.java를 `check --changed`로 검사해 CRAP 4개 함수 기준 이내, 변이 10개 중 killed 5·runtimeError 5(kill 비율 50%, 종료 2)를 얻었다(663초). 같은 파일을 원본 mutate4java(잠긴 jar, commit 7b05fdd)로 새 사본에서 같은 오프라인 저장소·`--mutate-all --max-workers 1`로 직접 돌리면 변이 10개 전부 killed(396초)다. SENTINEL의 5+5 = 10과 맞고, 손으로 변이를 넣어 확인하면 null 치환 5개는 테스트가 예외(Errors)로, 연산자·상수 치환 5개는 단언 실패(Failures)로 죽어 SENTINEL이 전자를 runtimeError로 분리한 것과 일치한다. 이를 위해 프로젝트별 오프라인 Maven 저장소 `.sentinel-m2`, SENTINEL 소유 파일의 빌드 트리 제외(apache-rat 대응), JUnit 리스너의 건너뛴 테스트·매개변수 테스트 허용을 추가했다.|CI 승인. 전체 변이 검사 시간(변이당 전체 테스트 1회)은 변경분 모드로만 실용적이다. Commons CLI 비교, 변경분 모드, CI 승인. 대상 프로젝트 의존성은 검사기 `.toolchain/m2` 오프라인 범위만 해석한다.|
|TypeScript|통합 명령에 연결했다. `check --project`가 사본에서 잠긴 Vitest로 coverage를 직접 만들어 CRAP을 계산한 뒤 Stryker 변이를 돌린다. setup→doctor→check --experimental 경로로 기본 통과와 `--crap-max 0.5` 실패를 확인했다. 2026-09-13에 공개 프로젝트 unjs/scule v1.3.0을 검사(종료 2, 변이 81개: killed 72·survived 7·uncovered 1·runtimeError 1)하고 직접 Stryker 실행(killed 75·survived 5·NoCoverage 1)과 대조했다. 이를 위해 `excluded` 글롭, vite.config·설정 없음 허용, Stryker tsconfig 고쳐 쓰기 끄기를 추가했다. 변이 id 대조로 killed 차이 3개 중 2개(모듈 최상위 정규식 상수의 static 변이)가 SENTINEL의 미탐지 결함임을 확인해 실행기를 고쳤고(테스트 필터 때문에 runtime으로 켜지던 static 변이를 import 전에 켬), 재검사에서 변이 81개가 직접 Stryker와 전부 일치한다(killed 74·survived 5·uncovered 1·runtimeError 1). [대조 표](https://github.com/hwain-ai/SENTINEL_TS/blob/main/docs/sentinel-typescript-native-validation.md#공개-프로젝트-검사2026-09-13)|CI 승인. 대상 테스트는 검사기 node_modules로 실행되므로 소스가 devDependency를 import하는 프로젝트(unjs/pathe)는 검사할 수 없다.|
|Clojure|실행 환경·의존성·clj-mutate 설치 내용만 재확인했다.|이번 축소 범위 밖. 독립 설치·통합 연결 미착수.|
|호스트 플러그인|Codex·Claude Code 마켓플레이스 파일을 저장소 루트에 두고, 스킬에 `setup` 명령과 설치 전 사용자 확인 규칙을 넣었다. 기준값은 setup이 `sentinel.workspace.json`의 `gate`에 쓰고 check가 도구 요청으로 넘긴다. 2026-09-13에 플러그인 범위를 검증한 세 언어(Python·TypeScript·Java)로 한정했고, `setup`은 언어를 생략하면 그 세 언어를 준비한다.|실제 호스트 설치·동작 검증.|
|CI·승인(5단계)|2026-09-13에 SENTINEL·SENTINEL_SPEC·SENTINEL_PY·SENTINEL_TS·SENTINEL_JAVA에 GitHub Actions 워크플로를 두어 push·PR마다 자체 시험 전체를 돌린다. 첫 실행이 모두 통과했다(SENTINEL 321개 32초, SPEC 19초, PY 433개 1분 39초, TS 180개 2분, JAVA 269개 6분 36초). 이를 위해 새 clone에서 실패하던 세 가지를 고쳤다: Java 오프라인 Maven 저장소를 채우는 bootstrap-m2.sh, TypeScript dist 지문의 파일 권한 의존, Python coverage 픽스처의 .gitignore 누락.|CI 통과 기록을 근거로 기본 `check`가 도구 묶음을 받아들이는 승인(admission.json) 설계·구현. 설계안은 사용자 확인 대기.|

가장 최근 Python 실제 검사는 종료 2/qualityFailed다. 이전 결과 저장 오류는 해소됐고 상세 기록을 회수했지만, 프로젝트의 품질 통과나 직접 도구 비교 완료를 뜻하지는 않는다. [Python 검증 기록](https://github.com/hwain-ai/SENTINEL_PY/blob/main/docs/sentinel-python-native-validation.md)에서 실제 결과와 남은 일을 구분한다. 원본 설정·검사 범위·네트워크 차단·품질 통과 기준은 유지한다.

[TypeScript 설치·수집 공백](https://github.com/hwain-ai/SENTINEL_TS/blob/main/docs/sentinel-typescript-native-validation.md)은 별도 기록에 둔다. TypeScript의 실행 링크 처리 방식과 Java의 공식 문서 자료 준비·오프라인 연결은 사용자 확인 중이며, 답변 전에는 해당 설정을 바꾸지 않는다.

[Clojure 준비 기록](https://github.com/hwain-ai/SENTINEL_CLJ/blob/main/docs/sentinel-clojure-native-validation.md)은 잠긴 입력의 확인과 아직 하지 않은 독립 실행을 구분한다. 현재 명령 구현과 달랐던 README 설명도 바로잡았다.

구조는 세 부분으로 유지한다. 공통 SENTINEL은 실행 제한·정리, 언어별 연결부는 도구 호출·결과 변환, 플러그인은 공통 명령 호출만 맡는다. 별도 관리 서비스는 추가하지 않는다. 정식 운영 허용과 실제 호스트 활성화는 별도로 확인한다.

읽기 쉽게 유지하는 기준: 사용자에게는 **완료한 것·현재 작업·남은 일**을 먼저 보여준다. 자세한 실패 로그와 파일 지문은 검증 기록에 두고, 사용 안내에 섞지 않는다. 언어를 추가할 때 공통 실행부나 플러그인에 언어별 빌드 로직을 복사하지 않는다.

남은 작업은 세 묶음이다. ① Python·Java의 실제 검사 비교와 연결, ② TypeScript·Clojure의 검증과 연결, ③ 검증된 범위의 플러그인 설치·동작 확인이다. 이 세 묶음의 작업량이 같지는 않으므로 개수만으로 완료율을 계산하지 않는다.

전체 다국어 목표는 유지한다. 새 프롬프트·설계·사용 안내·검토 보고서는 한글로 쓰며, 명령·코드 식별자·원본 로그만 그대로 둔다. [방향 검토와 단순화 기준](../../../docs/references/sentinel-direction-review.md)을 따른다.

## 공통규칙과 작업 경계

- 기존 여섯 하위 저장소와 그 안의 사용자 변경을 보존한다. 새 로컬 SENTINEL 폴더에서 기능을 구현하며 작업 공간 루트에 Git을 만들지 않는다.
- 새 변이 검사 엔진, 자동 원격 게시, 검사 도구 기본값 전환, 프로젝트별 설정 추측은 하지 않는다.
- 공용 결과에 원본 표준 출력·오류 출력·비밀값·절대 경로를 넣지 않는다.
- 새 동작은 시험 실패를 먼저 확인한 뒤 구현해 통과시킨다. 계약 확인용 시험 자료를 실제 프로젝트 품질 검사 완료로 세지 않는다.
- 통합 실행 기반과 정식 품질 인증은 다르다. 운영 허용 전 check는 명시적인 --experimental 요청이 필요하며 certified와 pass는 모두 false다.
- 이번 변경에서는 Git 커밋·푸시나 기존 저장소의 작업 사본 변경을 하지 않는다. 새 독립 구성요소의 작업 브랜치에 미커밋 결과를 남긴다.

### 확정된 사용자 승인과 현재 경계

2026-09-10에 다음 세 선택이 확정됐다. 아래의 과거 진행 기록에 있는 승인 대기는 당시 상태이며 현재 대기가 아니다.

1. 통합 SENTINEL이 컨테이너 생성·시간 제한·정리를 직접 관리한다. Go에서 검증한 공통 실행 경계를 다른 언어에도 재사용한다. 플러그인에 별도 컨테이너 관리 기능을 만들지 않는다.
2. Java 빌드 준비 도구는 공식 Maven Central의 HTTPS·체크섬으로 최초 다운로드를 허용하고 받은 전체 파일의 지문을 고정한다. 만료된 공급자 서명이 검증된 것으로 처리하지 않는다.
3. 실제 공개 Java·Python 프로젝트 비교에 필요한 새 빌드·테스트 도구도 공식 Maven Central·PyPI의 버전·다운로드 주소·SHA-256을 고정해 준비한다. 검증 후 실제 프로젝트 실행은 네트워크 차단 컨테이너에서만 수행한다.

이는 준비와 연결의 승인이다. 상용 도구 구매·기본 엔진 전환·정식 운영 허용·실제 호스트 플러그인 활성화를 승인한 것으로 확대하지 않는다. Java의 이전 비공개 임시 폴더 /tmp/sentinel-java-task2c.dn3EY9는 현재 위치에 없으므로 새 준비 전 기존 저장소의 고정 SDK와 확보 가능한 기록을 다시 확인한다. 부재 원인이나 삭제 주체는 확인하지 못했으며 이번 작업에서 삭제하지 않았다.

## 파일 책임

|파일|책임|
|---|---|
|SENTINEL/src/sentinel/workspace.py|작업 공간 설정 형식, 안전한 모듈 경로와 선택|
|SENTINEL/src/sentinel/bundle.py|고정된 묶음 설정과 파일 검증, 독립적인 로컬 설치|
|SENTINEL/src/sentinel/protocol.py|제한 시간·출력 크기·프로세스 회수, 요청 신원과 응답 상태의 엄격한 대조|
|SENTINEL/src/sentinel/cli.py|명령 선택·실험 실행·공용 결과 요약|
|SENTINEL/src/sentinel/native_go.py|Go 설치 설정·선택 모듈 검증과 기존 격리 실행기의 직접 호출|
|SENTINEL/src/sentinel/oci.py|승인된 잠금 파일과 로컬 Docker 환경의 읽기 전용 사전 대조. 컨테이너 실행·품질 승인은 하지 않음|
|SENTINEL/src/sentinel/oci_image.py|고정 이미지 목록·설정 원문과 로컬 이미지 식별자의 지문 대조|
|SENTINEL/src/sentinel/sandbox.py|검증된 Docker 세션으로 제한된 컨테이너 생성·설정 검사·실행·회수. 언어별 품질 판정은 하지 않음|
|SENTINEL/tests/|단위·실제 하위 프로세스·설치·정보 노출·중단 회귀 시험|
|SENTINEL/README.md|실제로 동작하는 사용법과 미완료 범위|

## Task 1: 통합 실행 기반

충족 요구사항: 통합-01..05의 로컬 transport·설치 부분. 정식 native 검사와 운영 sandbox는 Task 2다.

작업 디렉터리: `/home/ec2-user/work/Cognet9-Official/SENTINEL`. Python 3.9 이상 표준 라이브러리만 사용하는 src-layout package를 만든다. console entry point는 `sentinel`, import package도 `sentinel`이다. pyproject는 setuptools build backend로 외부 언어 SDK 의존성 없이 설치한다. 빈 초기 저장소라 baseline test는 없으며 첫 test부터 RED/GREEN을 기록한다. README를 제외한 docs와 다른 저장소는 수정하지 않는다. 무커밋 작업이므로 task report에는 commit 없음과 변경 파일 목록을 기록한다.

CLI 계약:

- `--help`, `--version`: 프로젝트·도구 파일을 읽거나 쓰거나 process를 실행하지 않는다.
- `plan`, `doctor`, `check`: `--project` 기본 현재 디렉터리, `--config` 기본 sentinel.workspace.json, `--tools` 기본 project/.sentinel-tools, `--language` 또는 `--module` 반복 선택, `--format text|json` 기본 text. 두 종류의 선택 옵션을 한 호출에 혼용하면 사용 오류로 거부한다.
- `plan`: module 선택 결과를 보여주고 process·파일 쓰기는 하지 않는다.
- `doctor`: 선택한 모든 bundle의 파일 무결성과 version/digest를 확인한다. 검사기 자체를 실행하지 않는다. ready와 품질 인증을 혼동하지 않도록 certified=false다.
- `check`: 기본적으로 backendNotAdmitted/exit6, process 0회. `--experimental`이 있을 때만 protocol request로 실행하고 관측 결과를 요약한다. 모든 module을 먼저 검증하고 누락/손상이 있으면 어떤 child도 시작하지 않는다. 선택 범위는 allConfigured/partial이며, partial 결과로 전체 완료를 주장하지 않는다.
- `install --bundle DIR --sha256 DIGEST --tools DIR`: 고정된 local directory bundle을 해당 언어/version/digest에 설치한다. install은 SDK 준비나 실행을 하지 않는다. 모든 tool 사용은 project의 version/digest에 의해 선택되고 global active pointer는 없다.
- unknown flag, unknown JSON field, duplicate JSON key, bool을 숫자로 준 입력, 비정상 timeout은 usage error다. timeout은 check 옵션 `--timeout-seconds`, 기본 60초, 0보다 크고 최대 3600초다.
- 공용 envelope는 schemaVersion=sentinel-workspace-result-v1, command, selection, moduleCount, results, pass, certified, exitCode를 포함한다. 공용 results는 moduleId, language, status, exitCode만 가지며 임의 child 데이터는 옮기지 않는다. check는 절대 exit0을 내지 않는다. experimental의 모든 관측 성공은 exit6/backendNotAdmitted로 요약한다. 실제 child 실패가 있으면 7,1,5,6,8,4,3,2 순의 고정 우선순위로 실패를 보존한다.

workspace shape: schemaVersion=sentinel-workspace-v1, modules=[{id,language,root,toolVersion,toolDigest,config?}]. id는 영문자로 시작하는 영숫자/하이픈/밑줄 1..64자, version은 정확한 semantic version, digest는 64자 lowercase hex다. modules는 1..128개, JSON은 최대 1MiB. root와 config는 lexical/real 경로 양쪽에서 project 내부여야 하며 모든 symlink와 특수 파일을 거부한다. module root의 중첩도 거부한다. config는 module root 안의 regular file, module root 기준 상대 경로다.

bundle shape: schemaVersion=sentinel-tool-bundle-v1, protocolVersion=sentinel-tool-protocol-v1, language, version, entrypoint, files. files는 상대 POSIX 경로를 key로 SHA-256을 value로 갖는 비어 있지 않은 object다. manifest 이름은 sentinel-tool.json이며 files 목록에는 자신을 넣지 않는다. manifest 원본 byte SHA-256이 install 인자의 digest와 같아야 한다. entrypoint는 files에 포함된 상대 경로다. bundle은 파일 최대 4096개, 전체 최대 64MiB, 개별 파일 최대 16MiB로 제한한다. 디렉터리/regular file만 허용하며 symlink, FIFO, socket, hardlink(st_nlink != 1), path traversal, 미기재 파일을 거부한다. native SDK 전체를 이 작은 bundle에 묶으라는 뜻이 아니라 검증된 launcher와 adapter의 배포 계약이다.

protocol request: protocolVersion, requestId(UUID), command=check, moduleId, language, projectRoot(선택한 module의 absolute local 경로), config(absolute local 또는 null). 자식 process의 cwd도 해당 module root다. response의 exact keys: protocolVersion, requestId, command, moduleId, language, toolVersion, status, exitCode, passed. status/exit 매핑: passed=0, toolError=1, qualityFailed=2, usageConfigError=3, baselineFailed=4, dependencyError=5, backendError=6, evidenceError=7, cancelled=8. passed는 status passed일 때만 true다. process exitCode와 JSON exitCode가 일치하고 identity가 모두 요청·bundle과 같아야 한다. requestId는 module 실행마다 새로 만든다. 중복 JSON key, identity·자료형·상태·종료 코드의 불일치는 backendError 6이다. 정식 인증 gate를 이 응답 boolean만으로 구현하지 않는다.

process는 shell=False, stdin JSON, stdout/stderr 각각 pipe, env는 PATH=/usr/bin:/bin과 LANG/LC_ALL=C.UTF-8만 전달한다. JSON/stdout+stderr 누적 합 최대 1MiB. timeout, 초과 출력, cancel 시 자기 process group을 kill하고 reap한다. group cleanup은 성공 종료 때에도 잔여 descendant를 남기지 않는다. 이 기능을 보안 sandbox라고 부르지 않는다. OSError/raw child error는 고정된 진단 코드로 바꾸고 absolute path·raw output을 내보내지 않는다. KeyboardInterrupt는 exit8로 나타낸다.

검증 순서:

1. test에서 CLI subprocess를 실행해 아직 명령이 없는 상태를 assert 실패로 확인한다. 실제 module 파일/fixture bundle을 임시 디렉터리에 만든다.
2. config 선택·경로 음성 test를 통과시키는 최소 구현을 추가한다.
3. 설치 test를 먼저 실패시킨 뒤 manifest pin, 무결성, 원자적·멱등 설치를 구현한다. 기존 install의 digest가 다르면 덮어쓰지 않는다. 재설치 실패 후 기존 내용 불변을 assert한다.
4. 실제 작은 executable fixture가 stdin request를 읽고 response를 만드는 test를 먼저 실패시킨다. 두 언어 호출, missing module preflight 0회 실행, wrong nonce/exit/type/oversized output/timeout/secret stderr를 검사한다.
5. 구현 후 `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v` 전체 실행, clean install과 import/CLI help smoke를 수행한다.
6. root agent가 diff를 검토하고 독립 reviewer의 spec/code quality 검토 뒤 findings를 해결한다. production 테스트 fixture의 통과 수를 native 언어 지원 증거로 사용하지 않는다.

초기 test의 형태는 `subprocess.run([sys.executable, '-m', 'sentinel', '--help'], ...)`의 반환 코드가 0인지 비교하는 것이다. subprocess는 실제 명령 실행, sys.executable은 현재 Python 실행기, -m은 package 실행, --help는 사용법 요청이다. 설치 전에는 명령이 없어서 실패해야 한다. test 실행 환경의 PYTHONPATH만 src로 지정하며 production child 환경에는 넘기지 않는다.

상태: 로컬 통합 실행 기반 완료(2026-09-08, Task 1 한정). 최종 71개 테스트가 9.364초에 경고 없이 통과했고, 새 package build/install과 독립 spec/quality 검토가 승인됐다. 검토의 Critical/Important/Minor 잔여 항목은 없다. 검토 후 12개 파일의 지문과 설치본의 source 일치도 다시 확인했다. commit/push는 하지 않았다.

- 설치된 명령으로 전체/선택 실행, 독립 version 추가·되돌리기, 손상 preflight의 child 0회 실행, 새 설치 디렉터리 권한을 확인했다. 다섯 language label의 시험 도구를 사용했으며 실제 다섯 언어 지원의 근거가 아니다.
- 실제 설치본의 출력 FD 부재·닫힘은 고정 exit 3이며 원본 예외를 내보내지 않았다. 막힌 출력·오류 진단의 첫 취소는 추가 drain 없이 exit 8로 끝났다.
- 정리 중 첫 취소의 selector/group/pipe 시점에서 테스트가 대신 정리하기 전에 실제 child와 세 pipe가 회수됐다. wait 시점·원래 signal handler 복구·취소와 정리 오류가 겹친 6/remaining 8 및 후속 child 0은 실제 child 회귀 테스트에서 확인했다.
- 실제 언어 도구 배포·품질 결과·원본 보호·운영 sandbox와 host plugin은 Task 2/3의 미완료 범위다. 기본 check는 여전히 실행 거부, experimental check는 pass=false/certified=false다.

## Task 2: 언어 도구 묶음과 운영 투입 검증

충족 요구사항: 통합-02..05의 실제 언어 도구 배포·품질·빌드·격리 부분. Task 1의 설치기와 실제 언어 도구 배포물 제작을 구분한다.

현재 소스 확인: Python과 Clojure는 프로젝트 check 명령, TypeScript check는 추가 입력 자료, Go check는 자체 옵션, Java는 분리된 명령 시작 함수를 가진다. 이 차이를 언어별 연결부에서 처리하며 공통 실행기에서 언어별 빌드 로직을 늘리지 않는다.

지원 project/build 조합을 각 언어별 fixture와 실제 프로젝트로 구분해 기록한다. 실제 application working tree를 직접 검사 대상으로 변경하지 않는다. 각 언어의 승인된 fixture 또는 사용자 지정 복사본에서 기존·신규 도구를 같은 source/test에 실행한다. 동적 Java test 등 미지원 조합은 거부 상태를 유지한다. process group 밖으로 벗어나는 자식, 외부 경로 쓰기, network, 메모리/CPU 고갈, cancel 뒤 복구 시험을 통과해야 해당 runner를 admitted로 승격하는 별도 계약을 작성한다. 이 단계의 근거 없이는 통합 check의 정식 pass를 구현하거나 backend 기본값을 바꾸지 않는다.

현재 상태(2026-09-10): Go의 공개 참조 비교·원래 빌드·격리 기반에 이어, 설치된 통합 명령의 실제 Go 연결을 확인했다. 같은 공개 프로젝트 복사본의 검사 결과는 qualityFailed/2, 80초 제한 실행은 backendError/6, 실행 연결 뒤 Ctrl+C는 cancelled/8이었다. 각 종료 뒤 프로젝트 22파일 보존과 소유 컨테이너 0개를 확인했다. 시간 예산·취소 연결의 독립 재검토는 지적 0건이며 새 전체 297개 시험도 통과했다. [실제 통합 명령 검증과 한계](https://github.com/hwain-ai/SENTINEL_GO/blob/main/docs/sentinel-go-native-validation.md#설치된-통합-명령의-go-연결-검증)에 상세 범위를 남겼다. 다른 언어의 실제 연결, 정식 운영 허용, 호스트 설치·활성화는 미완료다. 공개 참조 프로젝트를 회사 애플리케이션의 대표 사례로 해석하지 않는다. 아래 날짜별 기록은 당시 상태를 보존한 것이다.

실제 비교 대상 확인(2026-09-08): workspace의 일반 파일에서 SENTINEL 저장소·dependency·build 산출물을 제외하고 go.mod, pom.xml, build.gradle 및 Kotlin Gradle 설정을 찾았으나 일반 애플리케이션의 Go·Java 빌드 설정은 확인하지 못했다. 검색 결과는 upstream/unclebob의 mutate4go·crap4go·mutate4java·crap4java 도구 저장소였다. 이것을 사용자 애플리케이션의 대표 사례로 임의 선정하지 않는다. 사용자에게 우선 검증할 Go·Java 저장소 경로와 Java 빌드 방식 정보를 요청했다. 기존 소형 fixture의 실행 결과로 실제 프로젝트 비교를 대체하지 않는다.

실제 대상이 정해지면 먼저 고정 source/test와 빌드 명령·의존성·미지원 기능을 기록한다. Java의 현 PIT profile은 Maven/Gradle 파일이 있어도 그 빌드를 실행하지 않으므로, 단순 소스 컴파일 성공을 원래 프로젝트 빌드 지원으로 보고하지 않는다. 언어별 bundle은 기존 sealed launcher의 SDK 위치·내용 지문을 어떻게 고정할지도 포함해야 하며, 검사기 폴더의 절대 경로만 담아 배포 가능한 설치로 표시하지 않는다.

사전 환경 확인(2026-09-08): Docker client 25.0.14, Engine 25.0.16, API 1.44/Linux amd64와 /usr/bin/docker 지문 `c0b4d78635d4e2171a36fcfa1cdee696167ad87e2f7775220f95e7fcb024557a`는 기존 승인 계획의 값과 일치했다. /run/docker.sock은 root:docker, socket, 0660이었다. 빈 Docker 설정 폴더와 제거된 ambient 환경으로 로컬 socket을 명시해 다시 조회했다. 이것은 실행 격리 시험이 아니라 읽기 전용 환경 확인이다.

2026-09-08 당시 없었던 준비물: 승인 계획의 Ubuntu image digest `sha256:1e0a86e57d247923571b75e0aaf48a1449cf8c543d51fb3e07a4a7d7bfa79316`은 로컬 daemon에 없었다. SENTINEL_SPEC의 clean-install-executor.lock.json, tools/verify_oci_executor.py, tools/run_cross_runtime.py도 당시 존재하지 않았다. 이 조회에서 image pull, container 생성·실행, daemon 설정 변경은 하지 않았다. Docker가 있다는 사실만으로 운영 sandbox가 검증됐다고 표시하지 않으며, 기존 T01/T25의 미완료 executor 계약과 실제 비교 프로젝트·빌드 profile을 먼저 연결해야 한다.

### 2026-09-09 소스 기반 연결 점검

아래는 실행 코드를 읽은 결과이지, 실제 application을 빌드·검사한 결과가 아니다. 다섯 도구 모두 argv 방식이므로 공통 stdin/stdout protocol을 직접 구현하지 않는다. 입력·출력을 바꾸는 작은 연결 코드(adapter)가 필요하며, 명령 존재와 배포 가능성을 구분한다.

|언어|현재 명령과 연결 공백|다음 검증 경계|
|---|---|---|
|Python|check와 strict 모드가 존재한다. 공용 protocol 변환과 고정 Python·프로젝트 의존성의 독립 배치가 필요하다.|원래 저장소가 보이지 않는 곳에서 pytest·coverage·mutation과 evidence 기록을 실행한다.|
|TypeScript|check는 별도 --input CRAP 자료를 반드시 읽는다. 공통 요청에는 이 입력이 없으므로 wrapper만으로 완전한 check가 되지 않는다.|CRAP 수집 책임과 Vitest 설정을 먼저 확정한다. 임의 입력·과거 결과로 빈 부분을 채우지 않는다.|
|Go|check는 있으나 빌드 스크립트가 Go SDK의 저장소 절대 경로를 바이너리에 넣는다. GOWORK=off이므로 workspace 다중 모듈 지원을 가정하지 않는다.|옮겨 설치한 실행기·SDK 및 단일/중첩 module 경계를 검증한다.|
|Java|CRAP과 mutation의 진입점이 나뉜다. 기존 mutation은 Maven test를 실행하지만 PIT probe는 그 Maven/Gradle 빌드를 실행하지 않는다.|실제 빌드 방식, test inventory·JaCoCo·classpath를 명시한 뒤 combined check를 연결한다.|
|Clojure|check는 있으나 launcher가 저장소 src·.toolchain·dependency lock의 상대 배치를 전제로 한다.|원래 저장소를 숨긴 독립 설치와 프로젝트 명령·보고서·evidence를 검증한다.|

근거: [Python CLI](https://github.com/hwain-ai/SENTINEL_PY/blob/main/src/sentinel_py/cli.py), [TypeScript check](https://github.com/hwain-ai/SENTINEL_TS/blob/main/src/cli.ts), [Go build](https://github.com/hwain-ai/SENTINEL_GO/blob/main/scripts/build.sh), [Go 환경](https://github.com/hwain-ai/SENTINEL_GO/blob/main/internal/gotoolchain/environment.go), [Java mutation 진입점](https://github.com/hwain-ai/SENTINEL_JAVA/blob/main/src/main/java/io/github/hwainhwang/sentinel/cli/MutationCommandMain.java), [Java Maven 실행](https://github.com/hwain-ai/SENTINEL_JAVA/blob/main/src/main/java/io/github/hwainhwang/sentinel/mutation/TypedMavenRunner.java), [Clojure launcher](https://github.com/hwain-ai/SENTINEL_CLJ/blob/main/scripts/sentinel-clj.sh).

배포 경계: 현재 bundle 설치기는 전체 64 MiB/파일 16 MiB를 허용하고 entrypoint만 실행 권한을 준다. 따라서 SDK 전체나 여러 native 실행 파일을 그대로 복사하는 방식은 현재 계약에 맞지 않는다. 기존 T25의 별도 지문 검증 runtime-root·installed artifact와 작은 연결용 bundle을 구분해야 한다. 제한을 임의로 높이거나, 원래 저장소의 절대 경로를 남긴 채 독립 설치 완료로 표시하지 않는다. 개발 환경의 .toolchain에는 캐시도 포함되므로 그 폴더의 디스크 사용량을 실제 배포 크기로 제시하지 않는다.

공개 참조 후보를 조사했고, 2026-09-09 후속 실행에서는 아래 두 저장소를 회사 프로젝트 대표성이 없는 공개 참조 검증용으로 내려받았다. 새 private 임시 폴더의 clone HEAD를 아래 commit과 대조했고 git fsck는 둘 다 exit 0이었다. 사용자 프로젝트를 대체하지 않으며 아직 원래 build·mutation 비교 결과는 없다.

|공개 후보|고정 source와 확인한 조건|검증 전 판단|
|---|---|---|
|HashiCorp go-multierror v1.1.1|commit 9974e9ec57696378079ecc3accd3d6f29401b3a0의 [go.mod](https://raw.githubusercontent.com/hashicorp/go-multierror/9974e9ec57696378079ecc3accd3d6f29401b3a0/go.mod)는 단일 Go module과 errwrap v1.0.0을 선언한다. [Makefile](https://raw.githubusercontent.com/hashicorp/go-multierror/9974e9ec57696378079ecc3accd3d6f29401b3a0/Makefile)은 테스트 앞에 go generate를 둔다.|단일 module 참조 후보. 현재 native go test 경로와 생성 단계 차이, offline 의존성과 고정 SDK 빌드를 먼저 확인해야 한다.|
|Apache Commons CLI 1.10.0|commit 04581158dbebe688518a6d384cf7b611a074ef7a의 [POM](https://github.com/apache/commons-cli/blob/04581158dbebe688518a6d384cf7b611a074ef7a/pom.xml)은 Maven parent·JUnit·추가 테스트 의존성을 사용하며 [HelpFormatterTest](https://github.com/apache/commons-cli/blob/04581158dbebe688518a6d384cf7b611a074ef7a/src/test/java/org/apache/commons/cli/HelpFormatterTest.java)에 ParameterizedTest가 있다.|Maven 빌드 통합 후보이지만 현재 PIT probe의 추가 의존성·동적 테스트 제한 밖이다. Maven 성공으로 PIT 지원을 주장하거나 일부 테스트만 골라 전체 비교로 표시하지 않는다. Gradle 검증 후보도 아니다.|

현재 PIT 제한 근거: [실행 profile](https://github.com/hwain-ai/SENTINEL_JAVA/blob/main/docs/pit-execution-probe.md). 위 판단은 공식 소스와 현재 구현 제한을 대조한 추론이며 실제 비교 결과가 아니다.

공개 참조 준비의 새 관측(2026-09-09): go-multierror의 전체 Go 파일에서 go:generate 지시문을 찾지 못했고, 외부 의존성 errwrap v1.0.0을 별도 빈 cache로 내려받아 go.sum의 module/go.mod 지문 두 개와 대조했다. 이어 network download를 끈 go mod verify가 exit 0/all modules verified였다. Commons CLI의 실제 source 11개 테스트 파일에서 ParameterizedTest 계열 사용을 확인했다. 기존 SDK 설치 tree를 먼저 검증한 뒤 Git 밖으로 Go·JDK·Maven을 복사했고, 복사본 tree·binary 지문과 버전 출력도 잠금값과 일치했다. 이는 독립 복사 준비이며 아직 컨테이너 안 실행·프로젝트 빌드·배포물 admission의 완료가 아니다.

### Task 2a: 읽기 전용 OCI 실행기 사전 검증

충족 범위: 통합-05의 준비 단계만. 기존 T01의 실행기 고정 조건을 사용하되 기존 여섯 저장소는 변경하지 않는다. 정식 SPEC lock과 T25 driver를 대신 구현하거나 원본 계획을 완료로 표시하지 않는다. OCI는 컨테이너 실행 규격이며, 여기서는 그 실행 도구인 로컬 Docker의 신원만 확인한다.

파일: 새 SENTINEL/src/sentinel/oci.py, SENTINEL/tests/test_oci.py. 기존 process collector를 재사용한다. Docker 응답은 추가 metadata를 허용하므로 NaN/Infinity·중복 key를 별도로 거부하는 엄격한 JSON 경계를 둔다. 기존 Task 1의 입력 의미는 변경하지 않는다. README에는 내부 API와 미완료 경계를 기록한다.

받는 것: 명시적 외부 lock 경로·원본 SHA-256, Git 밖 소유자 전용 parent 아래의 새 session 경로. lock의 exact object는 schemaVersion, client, server, socket, image이며 현재 환경에서 값을 자동 승인·생성하지 않는다. 기존 T01 승인 값은 개발 검증용 외부 파일에만 옮긴다. image pin 보존은 image의 실제 검증을 뜻하지 않는다.

주는 것: prepare_session은 새 session.json의 SHA-256을 반환하고, recheck_session은 동일 lock·record·실행 파일·socket·빈 config·version을 다시 확인한다. 실행 가능한 Docker 명령을 받는 API, 새 통합 CLI 명령, 품질 승인 boolean은 추가하지 않는다.

1. 실패 시험: 잘못된 lock/hash/경로/권한/JSON, root-owned binary와 socket 조건, 빈 config 오염, 버전·context 불일치, 조회 전후 identity 교체, 기존 기록 보존과 재검증 변조를 제품 API에서 확인한다. 기능 부재의 RED를 먼저 기록한다.
2. 최소 구현: 고정 absolute Docker argv로 version만 조회한다. HOME·DOCKER_*·TLS·proxy를 전달하지 않고, 조회 전후 신원을 대조한다. 10초/합계 1 MiB 제한과 process 회수를 적용한다. private 기록은 0700 directory/0600 file, no-replace 및 file/directory sync를 사용한다.
3. 검증: 전체 SENTINEL unittest, 승인 값으로 실제 로컬 Docker 조회·세션 재검증, 손상 입력의 child 0회 실행과 독립 spec/quality review를 수행한다. image pull/container 실행이나 운영 격리 성공은 주장하지 않는다.
4. 다음 단계: 실제 프로젝트/빌드 profile을 정하고, image·runtime·dependency 검증과 격리 시험을 수행한다. 그 후에만 native runner admission과 Task 3를 진행한다.

RISK(security): 신원 확인은 Docker daemon이나 프로젝트 실행의 보안 격리를 증명하지 않는다. 향후 container driver는 이 검증을 각 작업 전후 호출하고 별도의 image·mount·network·resource 검증을 해야 한다. Docker 업데이트로 pin이 달라지면 중단하며 자동 수용하지 않는다. 실패한 private session은 재사용하지 않고 새 경로에서 재시도한다. 6개월 뒤에도 언어별 엔진과 품질 계약은 유지하고 실행 환경 lock만 검토 후 교체할 수 있게 한다.

기준선(2026-09-09): 변경 전 SENTINEL 71 tests/9.687초/OK, SENTINEL_SPEC 113 tests/0.062초/OK. 새 기능 완료의 근거가 아니라 회귀 비교 기준이다. 실제 Docker version read-only 조회에서도 기존 client/server/API/commit 지문과 socket 조건이 일치했다.

검토 이력(2026-09-09): 최초 93-test 이후 독립 검토의 Important 3개(마지막 폴더 확인 실패 뒤 기록 잔존, 생성·재검증 경로 조건 불일치, 실제 binary/socket validator 시험 누락)를 수정했다. 추가로 저장·폴더 생성의 다중 FD 정리와 게시 완료 뒤 취소의 결과 반환을 보완했다. caller가 성공 digest를 받지 못했다는 사실만으로 잔존 기록의 재사용이 막히지는 않으므로, 게시 이전 정리와 게시 이후 완료 결과 보존의 경계를 명시했다. 후속 driver는 별도 취소 상태를 확인해야 한다.

상태: Task 2a 로컬 준비 단계 완료. Root의 최종 전체 114 tests/9.162초/OK/경고 0, copy-mode 재빌드·설치, 설치본의 실제 로컬 Docker version 2회 및 잘못된 입력의 추가 child 0, 파일 변조·동기화 실패·다중 FD 회수·게시 전후 취소 시험을 통과했다. 설치된 Python source 8개가 현재 source와 같고 독립 v3 spec/quality 검토도 승인됐다(Critical 0/Important 0/Minor 0). 기존 Task 1의 README 제외 11개 파일은 보존했고 native 여섯 저장소의 HEAD·branch·status를 시작값과 대조했다. 이 완료는 실제 프로젝트 비교·컨테이너 격리·native admission·플러그인 연결의 완료가 아니다.

### Task 2b: 실제 이미지와 컨테이너 격리 실행

충족 범위: 통합-05의 실제 격리 실행 경계. Task 2a를 반복하지 않고 승인된 T01/T25의 이미지·설정 대조와 생성/실행/회수를 연결한다. Task 2 전체의 완료 조건은 그대로이며 이 하위 작업으로 native admission이나 Task 3를 완료 처리하지 않는다.

파일: 새 oci_image.py·sandbox.py와 대응 tests. 기존 oci.py·protocol.py의 검증 및 collector를 재사용한다. 현재 단계의 컨테이너에는 host 경로를 하나도 mount하지 않는다. 실제 설치 runtime·fixture·offline dependency의 읽기 전용 mount는 아래 Task 2c에서 내용 검증과 함께 추가한다.

받는 것: 승인 lock·SHA, 준비된 session·SHA, content-addressed raw image manifest와 config bytes, 명시적인 컨테이너 내부 argv·시간 제한. 이미지 다운로드는 별도 명시적 prepare 호출에서만 수행하고 태그나 임의 image reference를 입력받지 않는다. 주어진 raw manifest 지문은 lock의 full reference와, config 지문·크기는 manifest descriptor와 일치해야 한다. 지원 형식은 단일 Linux amd64 OCI/Docker v2 manifest이며 multi-platform index는 거부한다.

주는 것: 이미지 준비 후 검증한 image ID, 실행 후 제한된 관측값(종료 코드·timeout/취소·OOM·출력 크기와 지문·회수 확인). raw 출력과 Docker 오류는 public 결과에 넣지 않고 정식 품질 통과 boolean을 만들지 않는다. 각 실행은 start 전 container inspect에서 모든 요청 설정을 확인하며, 완료·실패·취소 뒤 자기 container ID만 회수하고 부재를 확인한다.

1. TDD: manifest/config 지문·JSON·platform 불일치, inspect의 image ID/RepoDigests 불일치, create 설정 변조의 start 0회, 실패·timeout·취소·output overflow 뒤 ID 한정 회수, 잘못된 session의 Docker mutation 0회를 먼저 실패시킨다.
2. 이미지: full digest를 --platform linux/amd64로 pull하고 manifest/config/inspect ID를 대조한다. create는 검증된 image ID와 --pull never만 사용한다. 매 Docker 호출 전후 Task 2a의 session 재검증을 수행한다.
3. 실행: network none, read-only root, cap-drop ALL, no-new-privileges, private PID/IPC/cgroup namespace, non-root UID/GID, 고정 제한 자원, 크기 제한 tmpfs, host mount·추가 device·port·권한 없음, 고정 locale/PATH만 전달한다. image entrypoint·healthcheck·환경의 암묵적 실행을 막는다. Docker 생성 요청과 실제 inspect를 대조한 후에만 start한다.
4. 실제 검증: 승인된 Ubuntu image에서 원본/sibling 경로·Docker socket 비노출, root 쓰기·네트워크 거부, tmpfs 정상 쓰기, CPU/메모리/PID 제한, process-group 밖 자식의 container 종료, timeout·SIGINT·출력 초과 뒤 부재 및 다음 실행 복구를 시험한다. 자원 고갈은 inspect로 제한이 확인된 컨테이너 안에서만 수행한다.
5. 검토: 전체 unittest·설치본 실제 실행, 독립 spec/quality 검토를 완료한다. 원본6개 repo 불변과 기존 CLI 기본 거부를 보존한다.

RISK(security/cancellation): Docker는 신뢰된 host의 기존 daemon을 사용한다. 설정·커널 격리 시험은 취약점 없는 VM 보장을 뜻하지 않는다. 별도의 취소 상태를 유지하여 사전검증 반환 뒤 취소가 있으면 다음 create/start를 하지 않는다. 정리 실패는 성공이나 단순 취소로 숨기지 않는다. 이미지 pull은 해당 digest의 로컬 캐시만 추가하며 daemon 설정이나 다른 컨테이너를 바꾸지 않는다.

상태(2026-09-09): Task 2b 완료. 독립 재검토에서 Critical/Important 0건으로 승인됐고 이미지·샌드박스 41개 테스트가 통과했다. 취소가 기록된 뒤 새 child를 시작하는 경우, signal handler 복원 오류 분류, Docker 응답의 숫자·boolean 혼동, 불명확한 삭제 확인을 회귀 테스트로 차단했다. 최신 전체 테스트는 183개/10.558초/OK이며 여기에는 별도 검토 중인 Task 2c 테스트도 포함된다. 새 copy-mode 설치본과 source의 재귀 비교는 차이가 없었고 설치 명령의 버전·도움말도 통과했다.

최신 설치본의 실제 Docker 재검증: 공식 registry raw manifest 424 bytes와 config 2052 bytes의 지문 및 고정 image ID를 대조했다. 비루트·원본 및 Docker socket 비노출·read-only root·network none·capability 없음·no-new-privileges·고정 환경·cgroup v2 CPU/메모리/PID 제한을 확인했다. timeout, 별도 session 자식, OOM, PID/CPU 제한, 출력 초과, SIGINT 뒤 exact-ID 회수와 새 instance 복구가 모두 통과했으며 마지막 ownership-label 조회는 정확한 빈 출력, 컨테이너 0개였다. 이 완료는 host mount 없는 실행 생명주기의 범위이며 모든 관측은 certified=false다. 실제 언어 배포물·프로젝트 build·native admission은 다음 Task 2c·2d에 남아 있다.

### Task 2c·2d: 언어 배포물과 실제 프로젝트 검증으로 연결

다음 경계는 SDK·installed artifact·offline dependency의 독립 설치와 내용 검증(Task 2c), 고정 프로젝트의 원래 build와 기존/후보 검사기 비교 및 운영 admission(Task 2d)이다. Task 2b의 no-host-mount 시험을 이 둘의 완료로 대체하지 않는다. 실제 사용자 애플리케이션은 지정된 복사본만 사용하고, 공개 참조를 실행하는 경우에도 회사 프로젝트 대표성이나 미실행 build 조합의 지원을 주장하지 않는다. 모든 단계 후 Task 3를 이어가며 단계마다 계속 진행 여부를 재요청하지 않는다.

Task 2c 입력 전달에는 세 대안을 대조했다. A는 runtime·native artifact·offline dependency·project corpus를 각자 content-addressed root로 설치해 read-only bind하고 작업 project와 state만 tmpfs로 만드는 방식, B는 이들을 언어별 큰 composite root 하나로 묶는 방식, C는 언어 runner마다 새 OCI image를 만드는 방식이다. A를 구현 기준으로 선택한다. B는 runner 한 항목 변경에도 SDK·dependency 전체를 복제하고, C는 현재 범위를 넘어 registry·signature·retention 공급망이 추가된다. A는 mount 검사가 많지만 네 digest를 독립 추가·되돌릴 수 있고, 향후 같은 manifest를 C의 image layer 입력으로 전환할 수 있다.

공통 no-host-mount Sandbox의 UID65534·mount0·60초 계약은 바꾸지 않는다. 별도의 closed language profile만 검증된 PreparedRoot를 받으며 호출자가 host/container path, user, mount, environment를 지정하지 못한다. 원본 Git tree를 mount하지 않고 Git 밖 content root만 read-only로 연결한다. source/test/config/build 입력은 실행마다 UID 소유 tmpfs project로 복사하고 전후 manifest를 대조한다. SDK와 dependency는 read-only, HOME·cache·build output은 제한된 tmpfs만 writable이다. create 전후와 container 안에서 runtime/artifact/dependency/corpus digest를 다시 확인하고, inspect의 exact source·destination·RW·tmpfs·user를 대조한 뒤에만 project code를 시작한다.

Go 첫 profile은 Go1.27.1 SDK, native artifact, project module cache, go-multierror 1.1.1 corpus를 네 root로 분리한다. native source에는 독립 bin/libexec 배치·실행 전 companion SHA 확인·읽기 전용 module cache 허용만 보완하고, build ldflags로 container의 고정 Go path와 test-runner path를 넣는다. 현재 T25의 bin/libexec 표에 빠진 `sentinel-go-test-runner`를 필수 artifact로 명시한다. 두 새 output의 세 native binary digest 일치를 확인했으며 version 문자열만으로 파일 지문을 대체하지 않는다. 공개 reference의 원래 generate/list/test 순서, sentinel-go mutate4go, go-mutesting은 같은 source/test manifest의 독립 lane으로 실행한다.

2026-09-09 content root 준비 코드의 독립 검토는 ACCEPT다. 해당 시점의 관련 31개를 포함한 전체 186개 테스트가 10.291초에 통과했고 clean install의 source 일치·version 실행을 확인했다. 이어 runtime의 기존 gnu-tar-v1 지문과 네 독립 root 검증, mounted Go profile을 구현했다. go-multierror의 offline preflight·원래 make build·native doctor가 컨테이너 안에서 종료 0이었고 입력 보존·해당 ID 회수를 관측했다. Go 전용 입력·격리 기반의 구현과 아래 실패 시험은 완료했으나, 실제 전체 mutation 비교·다른 언어 설치·admission은 진행 중이다.

최신 근거는 [Go 실제 검증 기록](https://github.com/hwain-ai/SENTINEL_GO/blob/main/docs/sentinel-go-native-validation.md)에 모은다. 구버전 Go 선언을 깨뜨리는 생성 helper 문법과 기록 byte·lock identity·깊은 JSON, 입력 검사·signal handler 복원 중 취소 및 OS 경로 오류의 변환을 재현 후 수정했다. 관련 runtime/input·Go/common lifecycle 후속 검토는 ACCEPT이며 전체 216개 테스트/10.962초, copy-mode 재설치본과 source의 일치를 확인했다. Go profile의 기본 설정·timeout·별도 session 자식·CPU·PID·초기 검사 취소·최종 검사 취소·실행 중 취소·OOM·출력 초과 10종과 각각의 새 인스턴스 복구가 통과했다. 공통 profile도 재시험했으며 모든 실행 종료 뒤 소유 컨테이너는 0개였다. OOM/timeout은 native 결과와 내부 입력 보존의 정상 완료로 인정하지 않는다.

두 번 빌드한 수정 artifact는 네 Go binary 지문이 같고 SDK·dependency·corpus는 기존 root를 재사용한다. 수정본의 make·doctor는 다시 종료 0이었다. 처음 7파일 mutate4go 실행은 backendTimedOut였고 go-mutesting은 수정 전 baselineFailed였다. 수정 후 sort.go의 go-mutesting 비교는 원본 테스트를 유지한 상태에서 후보 1개/survived 1개를 관측했으나 backendNotAdmitted다. mutate4go의 strict 품질 검사는 같은 부분 목록을 mutationSourceInventoryMismatch로 거부했다. 이 기존 전체 범위 정책을 완화하지 않으며, 일부 관측을 전체 비교나 검출 성공으로 계산하지 않는다.

Go 후속 v4 관측(2026-09-09): 실행 종료 후 제한된 이벤트 수집, 출력 제한 우회 차단과 선택형 개별 변이 재실행 시간을 독립 검토·시험한 뒤 새 artifact를 두 번 빌드했다. 124개 source manifest와 네 binary 지문이 각각 같았고 기존 root·lock·버전은 유지했다. 통합 실행기 내부 comparison 연결의 전체223 tests/10.862초, 재설치14개 source byte 일치와 설치본 전용6 tests가 통과했다. 새 설치본으로 원래 make·doctor는 각각 native0, go-mutesting은 같은 전체7파일에서29개 후보의 보고서를138.234초에 얻었다. killed7/survived8/timedOut1/compileError6/runtimeError7이며 오류나 시간 초과를 killed에 합치지 않았다. 원본 control2회와 변이58회의 식별값은 모두 달랐고 테스트 목록 지문은 같았다. 각 lane의 입력 보존·회수·소유 컨테이너0을 확인했다. comparison-and-numbers-v1 규칙에 한정된 실험 관측으로 certified=false/backendNotAdmitted를 유지한다. mutate4go 회수·시간 제한 보완, 두 backend 비교와 admission은 다음 범위다.

실제 빌드 준비에서 확인한 보완: 고정 Ubuntu image에는 make가 없으므로 artifact root 안에 고정 Ubuntu make와 go-mutesting 비교 실행기를 추가하고 별도 support record와 전체 content manifest에 포함한다. native artifact.json의 세 native payload 계약은 유지하되 root 전체는 두 record가 지정한 파일만 허용한다. SDK 15,639개 파일과 1,714개 폴더는 모두 release mode 0644/0755다. 설치 권한을 0400/0500으로 제한한 뒤에도 원래 release mode로 직렬화한 gnu-tar-v1 값이 기존 lock과 같은지 별도 검증한다. 원래 hash를 새 임의 알고리즘으로 바꾸지 않는다. 작업 project는 mutation snapshot이 파일 권한을 복사하므로 tmpfs 파생본만 0600/0700으로 두고 전후 입력을 대조한다. 원본 corpus와 module cache는 읽기 전용으로 유지한다.

Java 첫 profile은 JDK17·Maven3.9.16과 Apache Commons CLI1.10.0의 project별 Maven closure를 분리해 고정한다. 인자 없는 upstream Maven default build를 먼저 실행하고, byte가 같은 fresh copy에서 mutate4java와 Maven-aware PIT를 독립 비교한다. 현재 standalone PIT profile은 추가 dependency·test resource·parameterized test를 지원하지 않으므로 Commons CLI 지원 근거로 사용하지 않는다. listener v2와 Maven runtime 경계가 선행된다. Certitude는 제품 신원·배포 형태·라이선스·접근 권한·output 계약이 확인되지 않았으므로 fake adapter나 지원 상태를 만들지 않는다. local artifact, Maven plugin, SaaS는 자료가 생긴 뒤 서로 다른 보안 경계로 검증한다.

Java 준비물 재확인(2026-09-09): Git 밖 JDK17.0.20.1+1·Maven3.9.16에 기존 toolchain_lock.py의 --require-locked/--verify-tree를 실행해 모두 종료 0을 확인했다. JDK에는 legal 아래 상대 symlink 208개가 있고 그 밖에는 없었으며 Maven에는 symlink가 없었다. 링크를 거부하는 공통 content root에 그대로 넣을 수 없으므로, 원본 runtime 잠금 검증과 설치용 표현의 지문을 구분해야 한다. 현재까지 실제 Maven build는 실행하지 않았다.

JDK 설치 표현의 대안은 A: 검증된 내부 symlink를 보존하는 별도 runtime manifest, B: 원본 archive/tree를 먼저 검증한 뒤 legal 링크의 동일 내용을 일반 파일로 복사하고 별도 파생 지문을 붙이는 방식, C: 검증된 별도 runtime image다. 첫 검증의 추천은 B다. A는 공통 링크 거부 경계를 넓히는 추가 검증이 필요하고 C는 이미지 공급망을 추가한다. B는 원래 tree SHA와 다르므로 같은 설치라고 표시하지 않으며 원본 SHA·변환 규칙·파생 manifest SHA·변하지 않은 실행 파일 SHA를 함께 기록해야 한다. 라이선스 내용을 삭제하거나 기존 lock을 덮어쓰지 않는다. Java 전용 표현을 정식 지원으로 승인하는 결정은 실제 빌드·읽기 전용 mount·복구 검증 뒤에 남긴다.

Java 파생 준비 관측(2026-09-09): B를 private 준비 스크립트로 검증했다. 링크 byte·실행 권한·원본 보존·재실행, legal 밖 링크 거부, 잘못된 lock 거부, Maven 독립 준비의 4개 테스트가 0.050초에 통과했다. 실제 JDK는 legal 링크 208개를 포함해 454개 일반 파일/333,699,498 bytes로 봉인했고 파생 content SHA는 679ca07e708168ea2f90f61ce4b7959084d8eaa87cbfd168bfd061e000e42a1f다. Maven은 96개 파일/10,869,833 bytes이며 content SHA는 c7f04fd0465fd18d4e717c7b57b4ff105dc461be331f0b0c6a1d873212237725다. 기존 toolchain lock·source tree·실행 파일 SHA는 따로 보존·대조했다. 공통 content root의 기존 dependencies 종류를 사용하며 새 runtime 종류나 링크 허용을 제품 API에 추가하지 않았다. 준비 결과는 certified=false이고 실제 Maven build·Java 격리·설치 지원 승인은 아직 없다.

Commons CLI의 전체 138파일/1,112,781 bytes도 같은 원본 source manifest와 대조해 별도 corpus로 봉인했다. content SHA는 210dfe5b0038433121abfe0854c1eb6887641bfe5e52b5f892801b2c1eac2aba다. 원본에 실행 권한이 있는 이미지 파일의 mode를 보존했으며, private 복사본의 그룹 쓰기 권한 거부 후 그 복사본만 0600/0700으로 제한했다. 관련 5개 테스트가 0.034초에 통과했고 원본 clone의 git status는 비어 있었다. 기존 Java 공유 Maven cache는 이 프로젝트의 잠긴 의존성 집합이 아니므로 그대로 승인·재사용하지 않는다.

Java 설치 표현의 후속 검증(2026-09-09): 원본 파일 종류·경로·권한·링크 대상을 별도 기록하고, 설치본의 byte와 기존 native serializer로 원래 tree 지문을 재구성했다. 실제 JDK 542개 node와 Maven 109개 node에서 기존 lock 값이 일치했다. 원본 경로 없이 재검증, descriptor 변경·누락·중복 거부, 설치 byte 변조 거부와 별도 정상 manifest로 봉인한 잘못된 라이선스 복사본 거부의 새 5개 시험이 통과했고, private 준비 전체 14개 시험은 0.162초/OK였다. 기존 lock과 파생 root는 덮어쓰지 않았다. 이는 별도 개발용 출처 기록이며 공급자 서명·실제 Maven build·Java admission을 뜻하지 않는다.

상용 Java 후보 재확인(2026-09-09): 공식 Synopsys Certitude 자료는 반도체 RTL 검증을 설명하며 Java·JUnit·Maven 지원 근거는 확인하지 못했다. Java용 상용 PIT 확장은 ArcMutate 공식 문서에서 확인했다. [후보 재확인 기록](https://github.com/hwain-ai/SENTINEL_JAVA/blob/main/docs/sentinel-java-commercial-candidates.md)에 근거·대안·한계를 분리했다. 사용자가 지칭한 별도 Certitude 제품의 URL·배포 자료는 여전히 필요하며, ArcMutate는 조사 후보일 뿐 구매·설치·기본값 변경을 하지 않는다. 현재 PIT 공개 참조 검증은 계속한다.

3~5수 결과: 먼저 공통 content root와 Go closed profile을 만들고, 그 다음 공개 Go 원래 build·도구 비교, Java closure·원래 build·backend lane을 검증한다. 이후 Python·TypeScript·Clojure는 content root와 OCI lifecycle을 재사용하되 언어별 build logic은 각 adapter에 둔다. Task 3 plugin은 admission digest tuple만 읽는 동일 CLI를 호출한다. 6개월 뒤 SDK나 backend가 바뀌면 바뀐 root와 조합만 새 admission으로 검증하고 이전 digest tuple로 되돌린다. 실패 회복 시 기존 root와 admission은 덮어쓰지 않는다.

Java 실행 전 검증(2026-09-09): 원래 default goal과 전체138파일을 고정하는 private 입력 검사7개를 추가했다. 고정 SDK·Maven·corpus의 읽기 전용 mount와 network none 컨테이너에서 Java/Maven 버전 명령만 실행했다. 첫 실행은 내부 실패 단계 기록이 부족했고, 진단 실행은 Maven Jansi가 noexec 임시 폴더에 보조 라이브러리를 풀어 경고를 내는 원인을 확인했다. Maven 임시 경로만 이미 허용된 작업 전용 실행 폴더로 지정한 뒤7.755초/exit0, 입력 불변·회수·소유 컨테이너0을 확인했다. 새5개 runtime 준비 시험을 포함한 private 전체26 tests/0.281초가 통과했다. 실패 기록과 각 driver 지문은 보존했고 권한·네트워크·버전은 바꾸지 않았다. 원래 Maven 프로젝트 빌드·의존성 전체 잠금·Java admission은 아직 미완료다.

Go v5 후속 관측(2026-09-09): mutate4go 회수·출력·선택형 변이 시간 제한과 통합 mutation·check 내부 연결을 독립 검토·검증했다. 새 전체 시험은 native 본체13개/bridge6개 패키지, 통합230 tests이며 재설치14파일 byte 일치와 설치 연결12 tests를 확인했다. 같은132파일 source에서 두 번 만든4개 실행 파일이 같았고 새 artifact content SHA는235b4f24bb85ccd4a6ca57c41d2bfa35307b4e62429a06d3aa86b105c7b5c049다. 실제 원래 빌드·진단은 각 종료0, 전체7파일 mutate4go는147.912초에33개 상태 요약과qualityFailed/2를 얻었다. killed13/survived5/uncovered2/timedOut1/runtimeError12이며 오류를 검출 성공에 합치지 않았다. 세 실행 모두 입력 불변·회수·최종 소유 컨테이너0이며 완료 기록도 보존했다. 상세 control/replay·테스트 목록 지문은 native 공개 요약에 없으므로 두 도구의 동일 테스트나 운영 admission 근거로 확대하지 않는다. [실제 기록과 다음 범위](https://github.com/hwain-ai/SENTINEL_GO/blob/main/docs/sentinel-go-native-validation.md)를 갱신했다.

Java J1 준비 기준 확인(2026-09-09): 실제 프로젝트와 무관한 합성 설정으로 고정 Maven dependency-plugin을 다운로드 도구로 쓰는 대안을 검토했다. 설정·저장소·실행 한도는 구체화했지만 도구 자체의 전체 실행 의존성 신뢰가 선행 조건이다. 공식3.8.1 JAR·POM·구성 목록만 실행 없이 받았고, 서명의 수학적 일치와 만료키 경고를 함께 확인했다. Apache 공식 키 자료도 만료 상태이며 현재 신뢰된 사전 고정 의존성 전체 목록은 없다. 준비 도구에 한해 공식Central HTTPS·체크섬 최초 신뢰를 허용할지 사용자에게 확인 요청했다. 답변 전에는 Java 준비용 Maven 실행을 하지 않으며, 실제 프로젝트는 어느 선택에서도 검증된 network-none OCI 밖에서 실행하지 않는다. Go 등 다른 검증은 계속한다.

Go 상세 비교 준비 E1 완료(2026-09-09): 기존 계산을 재사용하는 별도 reference runner를 추가하고 원본 입력·정적 테스트 목록·실행 결과·실패 지문과 요청/실행 식별값을 기록한다. 작업 복사본 준비 중 취소와 정리 시험을 보완한 뒤 새 전체15개 테스트 패키지·개발 명령 시험2개를 통과했고 독립 검토는 Approved/C0/I0/M0이다. 기존 source132파일과 locks는 그대로다. 다음 E2는 기존 bridge의 명시적 비교 옵션에 실제 control/replay 호출·엄격한 기록 검사·컴파일 및 미실행 기록을 함께 연결한다. E3는 별도 설치 지문과 잘리지 않은 출력 보존을 검증한다. E1은 비교 전용 소스 검증이며 실제 프로젝트 결과·정식 설치·운영 admission을 대신하지 않는다.

Go 상세 비교 연결 E2 완료(2026-09-09): 명시적 옵션 쌍에서만 실제 원본 대조·변이별 재실행 기록, 컴파일 및 미실행 단계, 엄격한 JSON·식별값 대조를 연결했다. 중첩6개·상위15개 테스트 패키지와 독립 개발 명령2개/5.117초가 통과했고 독립 검토는 SHAbcaf93cb Approved/C0/I0/M0이다. 첫 독립 명령 시험의 Go 캐시 환경 누락과 초기 중단 구현의 TDD 이력 미확인은 성공 근거와 분리해 보존했다. 변경 대상 bridge 본문 외 기존131파일과 E1 5파일은 그대로다. E3 소스 구현을 시작하며, 기존 설치 경로와 비교용 설치 경로를 명시적으로 구분하고 같은 격리·회수 코드로 전체 결과를 보존한다. 이후 새 설치·재현 빌드·실제 OCI 상세 비교를 검증한다. 운영 admission과 호스트 plugin은 여전히 별도 후속 단계다.

Go 전체 출력 전달 E3 소스·설치본 검증 완료(2026-09-09): 기본9파일 구성과 비교용10파일 구성을 명시적으로 분리하고, 기존 격리·회수 코드를 재사용해 실행 식별값과 전체 출력 지문을 검사한다. 컨테이너 제거·원본 재검사·신호 복원이 끝난 뒤에만 완전한 결과를 보관하며 품질 승인으로 취급하지 않는다. 전체259 tests/11.894초와 독립 검토 SHA91a95153 Approved/C0/I0/M0, 오프라인 재설치15파일 일치, 설치본95 tests/2.504초를 확인했다. 이후 소스144파일 지문0d52a459에서 빈 캐시로 독립 빌드한5개 실행 파일이 모두 같았고, 새10파일·31,890,535바이트 설치물(content756cec43)을 만든 뒤 실제 설치본의 명시적v2 입력 검사를 통과했다. 복사한 바이트와 최종 파일 목록을 빌드 비교 지문에 결합하는 보완도 독립 승인했다. 이어 수행한 실제 OCI 상세 비교 기록 검증은 아래에 기록한다. 기존 결과를 소급해 보강하거나 운영 admission·plugin 완료로 표시하지 않는다.

Go 새 상세 비교·보관 증거 검토 완료(2026-09-09): 새 비교용 설치물로 같은 생산 코드7파일 전체를 실행해160.132초/종료0,33후보와 원본 대조2회·변이 재실행62회의 상세 기록을 얻었다. 원본 입력·정적 테스트 목록·원본 대조 결과 지문은 기존 go-mutesting 기록과 같고, 변이 후 전체 입력 지문이 같은 공통13개의 결과도 같았다. 새33개 후보 식별값·상태는 이전 mutate4go 요약과 같았다. 두 도구의 전체 변이 규칙은 다르므로 검출 개수만으로 우열을 판단하지 않는다. 전체 원문62,921바이트, 보관 여섯 파일·외부 프레임 지문, 원본 보호·회수·최종 소유 컨테이너0을 확인했고 독립 실제 기록 검토 SHAc40393e0 Approved/C0/I0/M0을 완료했다. 새 원래 Makefile 실행·전체 실패 시험 재실행·기록 발급자 인증·운영 admission·Task3는 이 비교의 완료 범위가 아니다.

Go 새 비교용 설치물의 원래 빌드 관측 반영(2026-09-10): content756cec43의 같은10파일 설치물과 고정20파일 corpus로 인자 없는 원래 make를 실행했다. 생성 단계·실제 패키지 테스트 출력, 외부/native 종료0, 입력 보존·timeout/OOM 없음·회수와 별도 소유 컨테이너0을 확인했다. 첫 시도의 이미지 부재 실패와 동일 승인 지문의 명시적 복구는 새 성공과 분리해 보존했다. 실제 출력86바이트·오류0바이트·전체457바이트 프레임 및 보관 여섯 파일이 기록 지문과 일치했다. 관측72.973초는 환경 준비부터 관측 저장까지이며 순수 빌드 시간으로 비교하지 않는다. 독립 실제 리뷰 SHA15b38fad Approved/C0/I0/M1의 비차단 지적은 정적 리뷰 중간본 지문 인용 오류였고, 최종본을 다시 읽고 정정 이력을 남겼다. 제품 파일·실제 실행 증거·원래 리뷰는 보존했다. 이는 보관된 실제 빌드의 검토·문서 반영이며 문서 갱신 때 재실행했다고 세지 않는다. [상세 기록](https://github.com/hwain-ai/SENTINEL_GO/blob/main/docs/sentinel-go-native-validation.md)에 집중10개·전체269개 시험과 최초 umask fixture 실패도 구분했다. 그 뒤 수행한 같은 설치물의 격리 시험은 다음 기록에서 구분한다. native 연결·운영 admission·다른 언어·Task3는 미완료다.

Go 동일 support-v2 설치물의 격리 검토 완료(2026-09-10): 같은10파일 설치물·고정 SDK와 의존성·설치본15파일로 basic/timeout/escaped/memory/output/pids/cpu/initial-cancel/final-cancel/cancel 10종을 순차 실행하고 독립 실제 기록 검토를 완료했다. 각 시험은 새로 작성한 네 파일 입력을 사용했으며 공개 참조 프로젝트20파일과 구분했다. 모든 시험 뒤 새 실행 객체의 도움말 복구가 외부/native 종료0·입력 보존·제거 true였고, 정리20회는 소유 컨테이너0을 기록했다. OOM의 외부 종료0을 native 성공으로 세지 않았고, 출력128MiB는 저장 공간 제한만 증명한다. 취소는 예약뿐 아니라 실제 발생 단계와 실행 연결 자식의 생존을 확인했다. 완료10개와 결합80항목 지문, 최종 제품35/plugin5/설치15/native144 및 검증기4파일·보호 입력 보존과 소유 컨테이너0을 대조했다. 최종 독립 검토 SHA-256은 4bf9ca14fb99372b635505b1b625321d177fe6c54f71dfb6d4d992ef47231ba2, PASS/Spec compliant/Approved/C0/I0/M0이다. CPU·PID 전후 수치 미보관, 터미널 세션 종료 응답의 독립 보관 부재, 특정 시험 명령 도달 여부와 전체 출력 전달 미검증은 [상세 관측과 한계](https://github.com/hwain-ai/SENTINEL_GO/blob/main/docs/sentinel-go-native-validation.md#동일-support-v2-설치물의-격리-10종과-새-실행-복구)에 유지한다. 제품 실행 코드·버전·기본 도구·제한은 변경하지 않았으며 문서 갱신 때 실제 실행을 반복하지 않았다. 전체 Task2/3, 임의 SIGKILL 뒤 회복·native 연결·운영 admission·다른 언어·호스트 활성화는 미완료다.

Go 실험용 설치 연결의 경계 재검토(2026-09-09): 제품 명세는 admission 전 experimental bundle을 허용한다. 다음은 실제 native check의 작은 연결 도구와 module 입력·시간 예산·회수 책임 검증이다. 현재 통합 실행기가 자식 그룹을 강제 종료해도 별도 세션의 Docker 호출 종료까지 확인되는 것은 아니므로, 소유권 식별값을 부모에 보관하는 것만으로 충분하다는 내부 구현안을 보류했다. 제품 코드는 변경하지 않았고 미실행 테스트 초안은 별도 보관했다. 기존 source·tests·README·패키지 파일 일치와 새 전체259 tests/12.049초를 확인했다. [연결 경계 검토](../../../docs/references/sentinel-native-connection-boundary.md)는 부모가 생성·실행·정리를 소유하는 대안을 권고하지만 새 public 계약이나 Task3 사용 승인을 대신하지 않는다.

Python 독립 설치 준비(2026-09-10): 현재 소스의 별도 사본 두 곳에서 만든 wheel은 각각59,991바이트와 SHA c69538c7cae16234636b13146acda4e1e03e95f507f762e587b1c00aab9b9d06으로 같고, 기존 버전과24개 소스 내용을 유지했다. wheel 독립 검토는 SHA a00aeca8aefbc4bede4c3fa41fca21022cb8853fd6b410c4a888823ef10cb894, Approved/C0/I0/M0이다. 기존 uv.lock의 Linux용19개 wheel/6,634,843바이트를 고정 주소·크기·지문으로 준비하고, 검증한 Python3.12.13·uv0.12.9 사본과 새 가상환경에 오프라인 설치했다.20패키지·1,497개 설치 파일과 실제 모듈 위치를 대조했고 설치 help/doctor는 종료0, 원본 입력29개와 원본·복사SDK는 그대로였다. 설치 독립 검토는 진행 중이다. 이는 호스트의 모듈 검색 경로·설치 내용 검증이며 원래 저장소를 숨긴 컨테이너나 실제 프로젝트 품질 검사는 아니다. SDK 내부 링크1,048개의 보존 가능한 설치 표현, 네 읽기 전용 입력과 임시 가상환경, 실제 프로젝트·Python 격리·운영 승인·호스트 연결이 남는다. [Python 준비 기록](https://github.com/hwain-ai/SENTINEL_PY/blob/main/docs/sentinel-python-native-validation.md)에 두 검증 스크립트의 잘못된 가정·수정과 미완료 경계를 구분했다. 기존 source·lock·기본 도구·public 계약은 변경하지 않았다.

Python 설치 검토 후속(2026-09-10): 위 준비 관측의 첫 독립 검토는 SHA b7e7f3580c20c13ae9c8a33bf9cd0145351376c59f46c971508dc7a3dcc6f806, Needs fixes/C0/I2/M1이다. 보관된 설치물 자체의 불일치는 관측하지 않았지만 검증 전에 설치 코드가 실행되고, 전체 설치 목록에서 예상 밖 파일을 배제하지 못하는 검증기 공백을 확인했다. 실제 경로 해석도 보완한다. 자동 패키지 로딩 없는 사전 검사와 그 뒤 별도 실행 진단을 새 시도로 검증하며 이전 성공 기록을 새 순서의 근거로 소급하지 않는다. 원본 SDK·설치물·이전 검토와 실패 기록은 보존한다.

Python 설치 검증 보완 승인(2026-09-10): 최종 독립 검토 SHA 38c7185cf74ec7b1a5b8d5648f9856ef96abf47cb78ef0b0a3d89964ef1ae094는 승인·치명적 0건·중요 0건·경미 0건이다. 고정 SDK의 자동 패키지 로딩을 끈 사전 검사, wheel·설치기 형식에서 도출한 전체 목록, 실제 경로 해석 뒤 실행 진단을 분리했다. 주 담당자가 관측한 새 순서의 15개 시험, 정적 검사 전후 일치, 설치물 1,596항목·원본 29입력·SDK·합성 입력 보존 기록과 지문을 재검토했다. 최초 동작 실패 시험의 전체 로그 부재는 한계로 유지하며 검토 수용 때 성공한 설치·시험을 반복하지 않았다. 다음은 기존 Java 방식과 같은 원본 지문에 결합한 SDK 별칭 복사 준비다. 공통 설치기의 링크 거부 규칙·공개 형식·버전·기본 도구는 바꾸지 않는다. Python 실제 프로젝트·컨테이너 연결·운영 승인·Task 3는 미완료다.

Python SDK 준비 승인과 실제 사본 생성(2026-09-10): 최초 전체 실패 시험 원문을 원래 에이전트 실행 기록에서 회수했고, 독립 재검토는 요구 충족·코드 품질 승인과 치명적·중요·경미 지적 각 0건으로 끝났다. 예외 승인이나 사후 재실행으로 처리하지 않는다. 승인된 코드로 Python 4,533파일·193,454,315바이트와 uv 2파일·49,660,896바이트의 새 읽기 전용 사본을 만들었다. 실제 준비 종료 0, 파생 내용과 재구성한 원본 tree의 잠금 일치, 원본 입력 29개·공통 실행기 소스와 설치본 16파일 보존을 확인했다. [SDK 준비 기록](https://github.com/hwain-ai/SENTINEL_PY/blob/main/docs/sentinel-python-native-validation.md#읽기-전용-sdk-사본-준비)에 지문과 근거를 남겼다. 다음은 기존 격리 실행기로 SDK·표준 라이브러리·빈 가상환경을 실제 실행하는 단계다. 지금까지 이 준비 단계의 SDK·프로젝트·컨테이너 실행은 0회이며 전체 목표는 계속 진행 중이다.

Python SDK 첫 실제 진단(2026-09-10): 공통 파일 검사 재사용과 오류 판정을 보완한 연결부는 설치본 기준 13개 시험과 독립 재검토를 통과했다. 첫 실제 컨테이너 실행에서는 고정 SDK의 내장 확장 모듈에 별도 파일 경로가 있다고 가정한 진단 오류가 발생해 종료 1이었다. 원문과 종료 응답을 보관하고 소유 컨테이너 0·원본과 봉인 SDK·원본 입력 29개·공통 실행기 소스 및 설치본 16개 보존을 확인했다. [실패 원인과 수정 경계](https://github.com/hwain-ai/SENTINEL_PY/blob/main/docs/sentinel-python-native-validation.md#sdk-컨테이너-첫-실행과-진단-보완)에 따라 내장 모듈 신원을 검사하도록 보완한다. SDK·버전·격리 제한은 바꾸지 않으며 실제 실행 검증과 Task 2·3은 미완료다.

### 공식 배포처 기준의 비교 준비 진행

2026-09-10의 승인에 따라 새 준비 파일을 고정했다. 준비 완료와 실제 프로젝트 실행 성공은 구분한다.

- Python: ItsDangerous 2.2.0의 commit 096c8d42545d3b68ea21a4f890fb2b2d8979c0bd에서 추적 파일60개 전체와 공식 PyPI의 빌드·시험 도구10개를 고정했다. 이후 실제 오프라인 배포 빌드와 전체 시험297개를 두 번 통과했고 원본 보존·컨테이너0을 확인했다. [실제 결과와 남은 비교](https://github.com/hwain-ai/SENTINEL_PY/blob/main/docs/sentinel-python-native-validation.md#공개-프로젝트의-실제-배포-빌드전체-시험)를 따른다. SENTINEL 품질 판정·변이 비교·통합 Python 지원의 완료가 아니다.
- Java: 고정 JDK·Maven을 재검증한 뒤 소스 없는 합성 POM으로 maven-dependency-plugin 3.8.1의 다운로드 준비만 실행했다. 실제 프로젝트의 POM·빌드·시험은 실행하지 않았다. 공식 Central에서 받은 JAR·POM 219개와 부속 파일을 포함한 606개, 총 17,890,651바이트를 고정했다. 공식 SHA-1은 HTTPS 최초 신뢰에 대한 손상 대조이며 공급자 서명 인증이 아니다. 재사용 기준은 전체 SHA-256 목록이다. Commons CLI 1.10.0도 원래 commit 04581158dbebe688518a6d384cf7b611a074ef7a의 추적 파일 138개·1,112,781바이트 전체를 다시 준비했다. Git 무결성과 개별 blob 내용을 대조했으며 새 소스 목록 지문은 65dac026ef69789e30e20864aa2d478800b2e2f94c722bdea183a576c2dacdf7다.
- Java 준비 중 목록의 경로 정렬과 새 임시 파일의 쓰기 권한이 공통 입력 계약에 맞지 않았다. 기존 실패를 보존하고 목록만 문자열 순서로 정렬했으며, 이번에 만든 캐시만 폴더 0700·파일 0600으로 좁혔다. 공통 검증 규칙·SDK·공유 캐시를 바꾸지 않고 읽기 전용 사본 봉인에 성공했다.
- Java 선언 의존성 준비: 원본 POM·commons-parent85·JUnit BOM5.13.1을 대조해 JUnit Jupiter API/engine/params5.13.1, Commons IO2.20.0, Commons Text1.14.0, Mockito4.11.0의 공식 JAR·POM12개, 총2,804,511바이트를 별도로 받았다. HTTPS·공식 SHA-1을 대조하고 재사용 SHA-256 목록을 고정했다. 목록 지문은5320565f37f3df125090cebc830e073482312014019530a3d8f6755df6c3a9e4이며 비공개 근거는 /tmp/sentinel-java-libraries.PdCjN8U2다. 이 라이브러리들이 추가로 요구하는 전체 의존성이나 프로젝트 빌드 지원이 완성된 것은 아니며, 내려받은 코드는 실행하지 않았다.
- 같은 POM에서 확인한 추가 의존성8종도 준비해 현재 JAR·POM은28개·8,285,102바이트다. 추가 목록은 Commons Lang3.18.0, OpenTest4J1.3.0, JUnit Platform commons/engine1.13.1, API Guardian1.1.2, Byte Buddy/agent1.12.19, Objenesis3.3이다. 합친 공식 파일 목록의 지문은24b829da9dfef3bcb52a9c59aaeeb1e37dd0a3df434b5e36b137d9e07b80188d다. Maven이 요구하는 모든 부모·빌드 플러그인의 준비 완료나 실제 실행 성공으로 확대하지 않는다.

비공개 Java 최초 준비 근거는 /tmp/sentinel-java-prepare.Sg3BBNv5다. 내용 목록 m2-manifest-v2.json의 SHA-256은 820375bcdad36e31324323aa5a1bb299f8fe43f6f9ef90b4fd7bf2d8f36e05c9, 공식 주소·체크섬 목록은 f322e904147db56b720554251f26ac2b4009510f858cbc430d974763c282a6d2, 준비 기록은 9ca4abcbf5a2f0afc7011cc67362e094424a389412afe79cf0076e9817a272c4다.

후속 준비에서는 이 606개 봉인 파일을 새 비공개 캐시에 복사하고, 합성 POM의 다운로드 도구를 오프라인으로 실행해 종료 0을 확인했다. 이어 원본·부모 POM의 고정 좌표 30개에 대한 다운로드만 수행했다. 31개 준비 호출은 모두 종료 0이었고 경고·오류 출력은 없었다. 실제 프로젝트 POM이나 다운로드한 빌드 플러그인은 실행하지 않았다.

추가 준비 결과는 JAR 316개·POM 621개와 부속 파일을 합친 2,494개·132,629,352바이트다. 모든 JAR·POM의 공식 HTTPS 주소·SHA-1 손상 대조·재사용 SHA-256을 기록하고 읽기 전용 사본으로 봉인했다. /tmp/sentinel-java-build-inputs.AY8Nf14M의 내용 목록 지문은 d5c89f11fb54adfc9ba977c83498ef360b65ac6b0e2538158aa0fc97bffcf5f4, 공식 파일 목록은 76cc09bcfebf4682ab03c4b02bb12566c09540f4dd3c2c80f1bd783def935815, 준비 기록은 3d94b3a7bc9e0ea699624ab1015fa0ed41f450006a2c361727f0438f8f59057f다. 원래 SDK와 이전 봉인 캐시는 보존했다. 실제 오프라인 프로젝트 빌드는 아직 실행 전이며, 의존성이 빠짐없이 준비됐거나 Java 연결·운영 허용이 완료됐다는 뜻은 아니다.

실행 환경의 새 파일 사본도 /tmp/sentinel-java-runtime.nbHRqtQZ에 준비했다. JDK는 454개·333,699,498바이트이며 라이선스 링크 208개를 같은 내용의 일반 파일로 보존했다. Maven은 96개·10,869,833바이트다. 기존 원래 tree 재구성 검사를 재사용해 원본 잠금과의 연결, 실행 파일 지문, 원본 전후 보존을 확인했다. 새 준비 기록 지문은 각각 5711b9cf5fb5e1a9c3ede3f8d1d576d42ce445f583a3de048d6098746dc6ba23과 c0fc1977f4b4051a952a55271f4bd3b6bb6eeef9f4acad6d9fdb4430de712d8e다. 독립 검토는 요구 충족·품질 승인, 치명적·중요·경미 지적 각 0건이다. 검토 원문 지문 a2366c1b248df409522190475ab5060451f5073d994314b597ed32d0ecfef413을 대조했다. 새 사본의 SDK·프로젝트 실행은 0회이며 다음은 실제 컨테이너 실행이다.

기본 활성 profile의 추가 도구 build-helper3.6.1·buildnumber3.2.1도 공식 준비했다. 최신 Java 입력은 /tmp/sentinel-java-build-extra.O2YRbyYE의2741파일147853085바이트이며 manifest b79e9a003c79f0c1032f2ce04d4ac908a5b04936b25b3e2310ec61d39de212b5, 공식 목록c0942d96f82a5485f6b740969bf055266685aff5d366f61667ca6865ba75e4bd다. 이전 입력을 덮어쓰지 않았다. 다음 원래 Maven 빌드 연결은 기존 공통 실행기와 이 입력만 사용하며, 다운로드 도구 외 실제 프로젝트 실행은 아직 하지 않았다.

원래 빌드 연결의 독립 검토에서는 실패 로그 유실과 입력 검사에 시간 제한이 빠진 문제를 확인했다. 공통 실행·정리를 복제하지 않고, 수집한 로그를 오류 처리 전에 전달하는 작은 내부 연결점만 추가했다. 전체 시험 301개와 새 설치본의 실행 관련 시험 72개를 통과했고, 공통 변경의 독립 검토 지적은 0건이다. 이전 설치본은 보존했다.

Java 연결에도 같은 600초 마감과 이번 컨테이너만 확인하는 사후 조회를 적용했다. 새 공통 설치본과 결합한 시험 31개가 통과했다. 최초 검사가 실패해 사후 확인을 못 했는데도 원본 보존으로 표시되던 문제도 실패 시험으로 재현한 뒤 수정했다.

독립 검토에서는 예외 경계 2건이 추가로 확인됐다. 사후 입력 검사 중 취소될 때 수집 결과가 사라지는 경우와, 시간 초과 뒤 실제 확인하지 못한 메모리 초과 여부가 false로 기록되는 경우다. 둘 다 가짜 실행으로 재현했으며 같은 연결 코드에서 최소 보완 중이다. 별도 관리 서비스·새 컨테이너 생명주기·원래 Maven 명령 변경은 없다. 실제 Java 빌드는 아직 실행 전이다. 상세 근거는 /tmp/sentinel-java-baseline-fix.p8Q4F2eZ의 common-installation-report.md, common-review.md, root-private-verification.md, private-review.md에 보관한다.

## Task 3: 호스트 설치 플러그인 연결

충족 요구사항: 통합-06.

Task 2에서 승인된 언어 범위에만 연결한다. Codex plugin manifest와 Claude Code manifest는 각 호스트 규격으로 만들고 skill은 공통 CLI의 plan/doctor/check를 호출한다. marketplace 게시·개인 설정 활성화는 실제 설치 검증 후 명시적으로 수행한다. 자동 hook, 임의 외부 plugin 발견, MCP server는 첫 구현에 넣지 않는다. `plugin-creator` scaffold와 validator, skill validator를 사용하고 local install smoke에서 누락 도구·부분 실행·미승인 backend의 거부를 확인한다.

상태: 비활성 플러그인 파일 준비와 기존 CLI 연결 검증은 완료했다. 실제 호스트 설치·활성화는 Task 2의 운영 admission 대기이며, 준비되지 않은 native runner를 사용 가능하다고 표시하지 않는다.

플러그인 파일 준비와 검사 활성화의 구분(2026-09-10): 사용자가 플러그인 제작에 컨테이너가 필요한지 질문한 뒤 공식 호스트 문서와 현재 CLI를 대조했다. 컨테이너는 플러그인 제작의 필수 조건이 아니라 Task 2의 실제 검사 실행 격리를 위한 선택이다. Task 2의 승인 조건은 그대로 두고, 기존 공통 명령을 안내하는 로컬 plugin 파일과 실행 거부 시험을 먼저 준비했다. 한 plugins/sentinel 폴더에 두 호스트 manifest와 공통 skill을 두며, 별도 서버·자동 hook·Docker 실행 코드·SDK·품질 판정은 추가하지 않는다. plan/doctor/default check의 기존 동작만 연결하고 --experimental 우회나 검사기 직접 실행을 안내하지 않는다. 파일 구조·모의 도구 연결 시험은 실제 언어 검사·호스트 설치/활성화 성공으로 세지 않는다. marketplace 등록·개인 설정 변경은 하지 않았다.

파일 준비 검증 완료(2026-09-10): [두 호스트 공통 패키지](../../../plugins/sentinel/README.md)와 [명령 연결 시험](../../../tests/test_host_plugin.py)을 추가했다. 집중 시험 10개와 새 전체 시험 269개가 통과했고, 전체 시험은 12.875초였다. Codex 구조 검사, 공통 skill 검사, Claude Code 2.1.267의 엄격 manifest 검사는 오류·경고 없이 통과했다. 독립 리뷰에서 발견한 중복 명령 예시 감지 공백은 세 명령별 실패 재현 뒤 수정했다. 재검토는 Approved/Critical 0/Important 0/Minor 0이며 검토 원문 SHA-256은 76280b4059b15efad82aea48f9df84746d1a603b8a3739049aad9276cd93e92a다.

설치된 CLI 연결은 소스가 없는 공백 포함 별도 경로에서 합성 도구로 확인했다. 전체 계획·설치 진단·전체/부분 검사 요청·도구 누락·파일 내용 손상 여섯 관측을 확인했으며, 누락·손상은 종료 5, 미승인은 종료 6으로 거부했고 검사기 실행은 0회였다. 품질 인증 값은 모두 false였다. 첫 비공개 시험의 설치 경로 비교는 lib와 lib64가 같은 폴더라는 점을 반영하지 못해 실패했고, 실제 폴더 일치를 확인한 뒤 검증 스크립트만 수정했다. 기존 CLI 소스·기존 테스트·루트 README·패키지 설정과 설치본의 내용은 보존했다. 이는 호스트가 skill을 실제로 불러 실행한 시험이나 다국어 프로젝트 검사 완료가 아니다. native 수명 관리 계약·Java 최초 신뢰·실제 언어 검증·운영 admission·호스트 설치/활성화는 그대로 남는다.

## 변경이력

- 2026-09-13 | 5단계 착수: 저장소별 CI와 플러그인 범위 한정, main 병합 | 변경: 여섯 저장소의 feat 브랜치를 main에 fast-forward 병합하고 GitHub 계정 이름 변경(hwain-ai)을 코드·문서·마켓플레이스에 반영. 플러그인 범위를 Python·TypeScript·Java로 한정하고 `setup --language` 생략 시 세 언어를 준비. 다섯 저장소에 GitHub Actions 워크플로(`.github/workflows/ci.yml`) 추가. 새 clone에서 드러난 결함 세 가지 수정(Java bootstrap-m2.sh, TypeScript dist 권한 지문, Python 픽스처 미추적) | 검증: 다섯 워크플로 첫 실행 전부 통과. 승인(admission.json) 설계는 사용자 확인 대기.

- 2026-09-13 | 원본 도구 비교를 한 문서로 정리 | 변경: 세 언어의 SENTINEL 결과와 원본 도구(mutmut·Stryker·mutate4java) 결과를 규칙 하나(SENTINEL killed + runtimeError = 원본 killed)로 설명하는 [비교 문서](../../../docs/references/sentinel-original-tool-comparison.md)를 새로 작성. Java는 같은 파일을 mutate4java로 직접 돌려 10개 전부 killed(SENTINEL 5+5)를 확인했고, TypeScript는 변이 id 81개를 대조해 static 변이 2개 미탐지 결함을 찾아 기록 | 검증: 예시 변이 4개(Java null·연산자, TypeScript `??`→`&&`·정규식 2개)를 손으로 넣어 실패 종류 확인.
- 2026-09-13 | TypeScript static 변이 결함 수정 | 변경: Stryker 계획기가 테스트 필터가 있는 변이를 runtime에 켜는 규칙 때문에 SENTINEL의 닫힌 설정(`testFiles` 명시)에서 static 변이가 import 이후에 켜지던 것을, 실행기가 reloadEnvironment 요청을 static 활성화로 위임하도록 수정(SENTINEL_TS dcbcf3e) | 검증: unjs/scule 재검사에서 변이 81개 상태가 직접 Stryker와 전부 일치, 자체 시험 180개 통과.

- 2026-09-13 | 4단계 공개 프로젝트 대조 완료(Python·TypeScript·Java) | 변경: Python ItsDangerous(변이 567, killed 72+runtimeError 346 = 직접 mutmut killed 418), TypeScript unjs/scule(변이 81, killed 72 대 직접 Stryker 75), Java Commons CLI(변경분 모드 1파일, 변이 10, killed 5·runtimeError 5 = 직접 mutate4java killed 10)를 통합 명령으로 검사하고 직접 실행과 대조. 이를 위해 Python mutmut 환경의 의존성 경로 결함 수정, TypeScript `excluded`·vite.config·설정 없음·tsconfig 처리, Java `--java-dependencies`(.sentinel-m2)·SENTINEL 파일 빌드 트리 제외·JUnit 리스너의 건너뛴/매개변수 테스트 허용, 통합 실행기의 `--timeout-seconds` 기본 3600(Go 900)·최대 86400과 `.sentinel*` 폴더의 변경분 제외를 추가 | 검증: 통합 실행기 320개, Python 511개, TypeScript 179개 자체 시험 통과. Java 전체 시험은 부하 없는 상태에서 재실행. pathe는 소스가 devDependency를 import해 검사 불가(TypeScript 프로젝트 의존성 링크 미구현).

- 2026-09-13 | 공개 프로젝트 비교 준비: Python 프로젝트 의존성·제외 파일 | 변경: `sentinel setup --python-requirements`가 검사기 launcher의 deps 모드로 프로젝트 테스트 요구사항을 `<프로젝트>/.sentinel-deps`에 wheel만 설치하고, Python 검사기가 그 폴더를 PYTHONPATH에 올리되 분석·변이·보호 대상에서 제외. 모듈 설정에 `excluded` 글롭을 추가해 docs/conf.py 같은 파일을 생산·테스트가 아닌 범주로 선언 | 검증: 통합 실행기 시험과 Python 단위 시험 통과. 이전 세션의 ItsDangerous 비교 입력(/tmp)은 재부팅으로 사라져 새 사본(scratchpad)에서 다시 준비한다.
- 2026-09-13 | 축소 범위 3단계: 변경분 검사 | 변경: `check --changed`(기준 `--changed-base`, 기본 HEAD)가 git 변경 파일을 모듈별 상대 경로로 도구 요청에 넘기고 변경 없는 모듈은 noChanges로 표시. Python·TypeScript·Java 검사기에 `--changed-file`(Java CRAP은 `--only`)을 추가해 생산 코드만 좁혀 판정하고, 생산 코드 변경이 없으면 검사 없이 통과로 응답 | 검증: SENTINEL 317·PY 430·TS 176 시험 통과, Python·TypeScript·Java 변경분 e2e(변경 없음→noChanges, 테스트만 변경→통과, 생산 변경→판정) 확인, JAVA 268 시험 통과.
- 2026-09-13 | 축소 범위 완성 1·2단계 | 변경: SPEC에 기준값 계약(crapMax 기본 8, mutationMin 기본 100, 소수 두 자리 문자열)과 증거 구성요소의 기준값 필드 추가. 통합 실행기에 setup 명령·gate 전달·마켓플레이스 파일 추가. Python·TypeScript·Java 검사기에 기준값 인자와 통합 어댑터(`sentinel-tool/`) 추가, TypeScript는 사본 coverage로 CRAP을 직접 계산 | 검증: SPEC 125·SENTINEL 313·PY 427·TS 173 시험 통과, JAVA 267 시험 통과, Python·TypeScript·Java e2e 통과. 컨테이너 격리·admission은 CI 방식으로 대체하기로 사용자 승인(2026-09-13).
- 2026-09-11 | Python 실제 결과 반영 | 변경: 결과 회수 완료와 직접 도구 비교·통합 연결의 미완료를 구분 | 검증: 실제 검사 2/qualityFailed, 변이 567개·기본 테스트 297개 두 번·이전 소스/빌드/테스트 동일·원본 보존·잔여 컨테이너 0을 ed4388/0에서 대조. 전체 Task 2·3은 진행 중.

- 2026-09-11 | Python 수정본 입력 준비와 가독성 정리 | 변경: 설치 파일·입력 준비를 실제 프로젝트 결과와 구분하고 현재 작업·남은 일 중심으로 안내 | 검증: 같은 wheel 두 개, 입력 26개·외부 25개 불변·공통 16파일·원본 60파일 대조. 수집기9개 시험·독립 검토 지적0건. 실제 전송 연결·재검증·전체 Task 2·3은 미완료.
- 2026-09-11 | Python 수정본 실제 실행 종료 | 변경: 실행 중 표시를 결과 기록 오류 조사로 갱신 | 검증: 원래 source·build·tests 전체 일치, 기본 시험 297개 두 번·원본 보존·정리·사후 오류 0. 실제 check는 종료 7/evidenceInvalid이며 도구 비교·통합 연결은 미완료.

- 2026-09-11 | Python 수정본의 공개 재검증 시작 | 변경: 외부 도구 25개를 유지하고 로컬 설치 파일 한 개만 교체해 기존 실행기에 연결. 안내에서 현재 실행과 이전 실패를 구분 | 검증: 연결 시험 61개·독립 검토 지적 0건, 주 담당의 입력 시험 4개·최종 부모 연결 시험 7개 통과. 실제 실행을 한 번 시작했으며 종료 결과·전체 목표 완료는 아직 아님.

- 2026-09-11 | Python 일반 예외 구분과 안내 단순화 | 변경: 검증된 일반 예외를 실행 오류로 남기고 긴 판정 함수의 검증 역할을 분리. README의 역할·순서·통과 조건을 한글로 정리 | 검증: 자체 시험 417개·주 담당 실제 명령 시험 1개 통과, 독립 검토 지적 0건, 설치 파일 두 개와 현재 소스 일치. 공개 프로젝트 재실행·도구 비교·통합 연결은 미완료.

- 2026-09-11 | 진단 준비 승인과 가독성 정리 | 변경: README 첫 화면에서 확인한 범위·미완료 범위·최신 진행 위치를 분리하고 남은 작업을 세 묶음으로 일치시킴. Python 승인 진단 한 번 시작 | 검증: 최종 독립 검토 승인, 보고서 시간 원문 정정, 지문 결합4개/0.060초/종료0. 실제 진단 결과는 아직 미확인.

- 2026-09-11 | Python 진단 보완과 결과 판독 준비 | 변경: 원래 검사 결과를 보존하는 진단 보완과 누락·깨진 진단 거부를 비공개 코드에 한정 | 검증: 주 담당 연결 시험20개·판독 시험5개 통과, 저장된 실제 빈 진단 거부, 기존 고정 이미지 존재 확인. 독립 재검토와 실제 진단은 아직 완료하지 않음.

- 2026-09-10 | Python 증거 진단 준비와 Clojure 입력 확인 | 변경: 진단 전용 연결의 시작 차단·새 시도 이름을 준비하고 Clojure의 오래된 구현 상태 설명 정정 | 검증: Python controller 시험 4개, Clojure 읽기 전용 고정 입력 검사 4개 종료 0. 새 실제 Python 진단과 Clojure SDK·프로젝트 실행은 아직 하지 않음.

- 2026-09-10 | Python 실제 재실행 종료와 남은 작업 갱신 | 변경: 진행 중 표시를 실제 증거 검사 오류와 다음 진단으로 바꾸고, 완료·남음·역할 구분을 앞에 유지 | 검증: 실제 check 종료 6/killProofInvalid. 이전 source·build·tests·tools 전체 일치, 기본 297개 시험 두 번 통과, 원본 보존·컨테이너 제거·잔여 0·사후 오류 0. 전체 검사 성공·통합 연결·플러그인 설치는 미완료.

- 2026-09-10 | Python 실행 조건 보완과 실제 재검증 착수 | 변경: 내부 임시 공간 보완 상태와 TypeScript의 독립 설치·수집 공백을 간단히 기록 | 검증: Python 최소 재현의 실패·성공, 관련 9개·승인 결합 4개 시험과 독립 검토 지적 0건. TypeScript 읽기 전용 지문 검사 2개 명령 종료 0. Python 실제 재실행은 진행 중이며 전체 목표는 미완료.

- 2026-09-10 | Python 진단과 읽기 쉬운 진행 상태 갱신 | 변경: 현재 표·다음 작업을 실제 잠금 생성 오류와 남은 세 묶음으로 정리 | 검증: 진단 독립 승인·새 연결3개, 실제 mutmut 종료1/check6, 원래297개 시험 두 번과 입력 보존·정리. 사라진 승인 이미지는 같은 지문으로 복구. 격리 조건 보완·비교·통합 연결은 미완료.

- 2026-09-10 | Python 수정본 실제 재실행 | 변경: 현재 실패 지점을 보고서 처리에서 변이 검사 도구 실행으로 갱신 | 검증: jo_5u4sv 부모 종료 0·실제 check 종료 6/backendProcessFailed, 이전 source/build/tests 전체 일치·297개 시험 두 번·원본 보존·컨테이너 0·사후 오류 0. 전체 검사 성공은 아니며 상세 원인 회수가 다음이다.

- 2026-09-10 | Python 설정 수정 승인과 실제 재검증 준비 | 변경: 첫 요약에서 코드 수정 완료와 실제 검증 미완료를 분리하고, 재실행 준비의 크기 확인값 누락 보완을 명시 | 검증: 제품 회귀 시험·독립 코드 검토 승인, 동일한 두 설치 파일 준비. 기존 입력과 실행 제한은 유지하며 실제 재실행 전이다.

- 2026-09-10 | Python 검사 오류 원인과 작은 수정 범위 확정 | 변경: 첫 진행 표와 다음 작업을 검사 전용 설정 수정으로 갱신. 원본 설정·검사 범위·도구 버전은 유지 | 검증: 실제 보고서와 예외 회수, 원래 빌드·전체 시험 일치 재확인(0996e0/종료 0), 기존 parser 시험 35개 통과. 제품 수정·실제 재실행·변이 비교·통합 연결은 아직 미완료.

- 2026-09-10 | Python 새 환경의 실제 비교 완료 | 변경: 첫 요약을 실제 종료 기록에 맞추고 다음 작업을 SENTINEL 검사로 이동 | 검증: 새26개 입력으로 빌드·전체297개 시험 두 번 통과, 원래/새 source·build·tests 객체 전체 일치, 입력 보존·정리·소유0. 연결21개 시험과 독립 검토를 거쳤으며 controller 시험의 작은 보완 의견1개는 남아 있다. 실제 근거는 /tmp/sentinel-python-comparison-live.en4p6hah/actual-record.md이며 전체 언어 지원·정식 인증은 미완료다.

- 2026-09-10 | Java UTF-8 실제 검증·Python 비교 입력 준비 | 변경: Java guest 문자 설정 한 줄과 회귀 시험을 추가하고, Python은 기존 입력25개와 로컬 수정본1개를 재사용했다. | 검증: Java 관련40개·독립 검토 통과, 실제 빌드는 문자 오류 해소 뒤 외부 문서 조회로 실패했다. Python26개 입력의 원본 대조·봉인·독립 검토 완료, 실제 새 환경 실행은 미완료다. 상세 근거는 /tmp/sentinel-java-utf8.RHEJxeko, /tmp/sentinel-java-original-live.r2lqfm9s, /tmp/sentinel-python-comparison.lQ3ak0Tz에 보존한다.

- 2026-09-10 | 검사 복사본 측정·실제 Java 후속 확인 | 변경: Python coverage가 기존 경로 함수를 재사용하도록 두 줄 변경, 새 배포 파일 준비, Java 공식 부재 기록과 실제 입력의 전후 결합 확인, 진행 표를 완료·현재·남은 일로 정리 | 검증: root Python85개/32.887초와 독립 검토, 동일 wheel2개·내용 검토 승인, Java39개/0.227초와 재검토 승인. 실제 Java는 Checkstyle·SpotBugs·PMD 단계를 넘었으나 마지막 Javadoc 문자 인코딩 오류로 종료1이며 원본·입력·정리·소유0을 확인했다. 전체 비교·언어 연결·플러그인은 미완료.

- 2026-09-10 | Python 기준 검사·변이 재검사 경로 보완 완료 | 변경: 기존 환경 함수에서 검사 복사본의 source→src→root 순서를 고정하고 내부 결과 기록 모듈을 우선. 새 실행 관리자·설정 기능 없음 | 검증: 실제 합성 하위 프로세스의 네 배치와 보조 모듈·동명 파일 보호를 확인. 구현자 집중84개·실제mutmut5개·전체412개 통과, 주 담당 새 집중84개/23.866초, 독립 재검토 승인·잔여0. 코드 실행 범위 측정과 공개 프로젝트 비교는 후속 범위.
- 2026-09-10 | 자동 생략 해소와 남은 실패 지점 갱신 | 변경: Java 부모 site XML의 한정 준비와 Maven 옵션 보완 후 실제 아홉 번째 실행을 반영. 요약과 구조 설명을 분리 | 검증: 준비 시험4개·실행 연결 시험35개·각 독립 검토 지적0. gyhw0cge는 종료1, 테스트968개 중 실패0/오류0/비활성61. 두 보고서 작업 실행 뒤 선택적 apache35 site XML 조회가 네트워크 차단으로 실패. 원본 보존·입력 검증·정리와 소유 컨테이너0 확인. Python 경로 보완은 독립 검토에서 공존 경로 문제1건을 찾아 수정 중.
- 2026-09-10 | 실제 진행 상태 갱신 | 변경: Java 테스트·Checkstyle 진행과 SpotBugs 보고서 실패, Python 재검사 경로 보완을 첫 요약에 반영 | 검증: Java 실제 em_frwre 종료1·968개 중 실패0/오류0/비활성61·원본 보존·컨테이너0을 확인. 온라인 전용 작업2개 자동 생략과 전체 목표 미완료를 명시.
- 2026-09-10 | 공식 프로젝트 빌드 입력 준비 진전 | 변경: Python 빌드 도구의 중첩 배포 정보 선택 보완과 Java 고정 빌드 후보 다운로드·봉인 | 검증: Python 새 11개 시험·독립 검토 지적 0, Java 다운로드 도구 오프라인 실행·추가 다운로드 종료 0 및 공식 파일 대조. 실제 프로젝트 빌드 성공은 아직 주장하지 않음.
- 2026-09-10 | Python 검사기 실제 컨테이너 설치 완료 | 변경: 출처 파일·줄바꿈 기대값의 좁은 보완 뒤 고정20개 설치·진단을 완료하고 공개 프로젝트 단계로 이동 | 검증: 집중19개·독립 검토 지적0, 세션80641 종료0·전후1595일반파일 검사 일치·원본 보존·소유 컨테이너0. [설치 완료 범위](https://github.com/hwain-ai/SENTINEL_PY/blob/main/docs/sentinel-python-native-validation.md#검사기-컨테이너-설치-검증-완료)를 넘어 실제 프로젝트 성공을 주장하지 않음.
- 2026-09-10 | Python SDK 후속 실제 진단 완료 | 변경: 내장 모듈 가정 수정의 v3 승인과 새 실제 성공을 기록하고 오프라인 검사기 설치로 진행 | 검증: 연결부 15개/0.538초, 새 세션26110 종료0·오류 출력 없음·원본 및 봉인 입력 보존·소유 컨테이너0. 완료 기록과 한계는 [Python 관측](https://github.com/hwain-ai/SENTINEL_PY/blob/main/docs/sentinel-python-native-validation.md#sdk-실제-후속-실행-완료)에 보관.
- 2026-09-10 | 사용자 승인 세 항목 반영 | 변경: 부모의 컨테이너 직접 관리, Java 공식 HTTPS 최초 준비, Maven Central·PyPI의 고정 도구 준비를 승인 대기에서 해소 | 검증: 사용자 답변과 설계 경계를 대조. 외부 접속은 준비만, 실제 프로젝트는 검증 후 네트워크 차단 실행을 유지.
- 2026-09-10 | SDK 첫 컨테이너 진단 실패 조사 | 변경: 합성 시험·독립 코드 승인과 실제 실행 실패를 구분하고 내장 모듈 진단 보완 기록 | 검증: 연결부 13개 통과, 실제 종료 1과 원문·회수·입력 보존 확인. 수정·재검토 및 실제 재검증은 진행 중.
- 2026-09-10 | Python SDK 사본 준비 완료 | 변경: 실패 시험 원문 회수 후 최종 승인과 실제 새 사본 생성 반영 | 검증: 준비 종료 0, 원본·파생 내용·입력 보존 재확인. SDK 컨테이너 실행·실제 프로젝트·운영 승인·Task 3는 미완료.
- 2026-09-10 | Go 통합 연결의 실제 설치·실행 확인 | 변경: 기존 격리 실행기 직접 호출과 데이터 묶음 설치, 준비 중 취소 보존, 한글 문서·프롬프트 정리 | 검증: 최종 독립 재검토 지적 0건, 주 담당 전체 297개/15.101초, 설치본 16파일 일치, 실제 2·6·8 결과와 각 원본 보존·소유 컨테이너 0. 전체 Task 2·3와 호스트 활성화는 미완료.
- 2026-09-10 | Go 통합 연결·한글 안내 정리 | 변경: Go 우선 연결 순서와 현재 상태를 앞에 명시, 부모 실행기의 시간 제한 전달 보완, 플러그인 기본 프롬프트·소개 한글화, 사용자 안내와 내부 참고 분리 | 검증: 시간 제한 독립 재검토 승인·주 담당 집중 10개 통과, 플러그인 11개와 형식 검사 통과. 실제 Go 통합 명령 실행과 호스트 활성화는 아직 미완료.
- 2026-09-10 | Python 설치 검토 보완 착수 | 변경: 첫 검토의 실행 순서·전체 목록·실제 경로 공백 기록 | 검증: 원문 SHA b7e7f358과 기존 코드 대조, C0/I2/M1. 설치 승인·실제 프로젝트·격리·Task3는 미완료.
- 2026-09-10 | Python 고정 패키지와 오프라인 설치 준비 | 변경: 새 준비 기록과 남은 SDK 표현·실제 프로젝트·격리 경계 연결 | 검증: 동일 wheel2개와 독립 검토 승인, 고정 의존성19개, 설치20패키지·1,497파일, help/doctor 종료0·입력/SDK 보존. 설치 검토 진행 중이며 전체 Task2/3는 미완료.
- 2026-09-10 | 동일 Go 설치물의 격리 10종·각 복구 승인 반영 | 변경: 실제 시험과 합성 입력의 범위, 완료 기록·검토 한계, 남은 native 연결을 분리 | 검증: 독립 실제 검토 SHA4bf9ca14 PASS/C0/I0/M0, 완료10개·결합80항목 지문 일치, 정리20회·마지막 소유 컨테이너0과 제품/설치/native 보존. 전체 Task2/3·다른 언어·admission·호스트 활성화는 미완료.
- 2026-09-10 | 새 Go 설치물의 원래 빌드 증거 반영 | 변경: 동일10파일 설치물의 실제 make·패키지 테스트, 이미지 부재·명시적 동일 지문 복구·새 성공 구분 | 검증: 종료0·입력 보존·회수·소유 컨테이너0, 여섯 파일·전체 프레임 지문 및 독립 실제 리뷰 SHA15b38fad 승인. 리뷰 인용 오류 정정 이력 보존. 전체 격리 재시험·native 연결·다른 언어·admission·호스트 활성화는 미완료.
- 2026-09-10 | 비활성 호스트 플러그인 파일 준비 검증 | 변경: 두 manifest·공통 skill·패키지 안내·명령 계약 시험, 중복 예시 거부 보완 | 검증: 집중 10개·전체 269개/12.875초, 설치 CLI 여섯 관측, 구조 검사 세 종류, 독립 재검토 SHA 76280b40 승인. 기존 소스·설정 보존. 실제 언어 검사·운영 admission·호스트 설치/활성화는 미완료.
- 2026-09-09 | Go 전체 비교 실패 원인·Java SDK 파생 준비 | 변경: 전체 go-mutesting 제한 초과와 대기 변이를 기록하고 Java legal 링크 내용을 보존한 독립 입력을 준비 | 검증: Go 입력 보존·회수·컨테이너0, Java 준비 4 tests/0.050초와 실제 SDK 잠금·파생 지문 대조. 전체 비교 결과·실제 Maven build·admission·Task3는 미완료.
- 2026-09-09 | Task 2c Go 설치·격리 기반 검증 완료 | 변경: 검사 중 취소와 회수 실패 우선순위, 신호 처리기 복원·경로 오류 비공개 처리, 부분 비교 관측과 전체 품질 범위의 분리 | 검증: 전체216 tests/10.962초, 재설치 source 일치, 독립 후속 ACCEPT, Go 격리10종·각 복구와 공통 재시험·마지막 컨테이너0. Java runtime 잠금 확인만 완료, 전체 비교·다른 언어·admission·Task3는 미완료.
- 2026-09-09 | Task 2c Go 입력·원본 build 연결 | 변경: 검증된 네 root와 closed profile, Go 1.13/1.17 생성 helper 호환성, record byte·lock·JSON 검증 보완 | 검증: 전체199 tests, Go 전체 package test, 이중 build, 실제 offline preflight·make·doctor, runtime/input 후속 ACCEPT. 전체 backend 비교·Go profile 검토·admission·Task3는 진행 중.
- 2026-09-09 | Task 2 연결 공백·선행 작업 구체화 | 변경: 소스 기반 5개 언어 연결표와 기존 저장소를 수정하지 않는 읽기 전용 OCI 검증 범위 | 검증: native source 대조, 변경 전 SENTINEL 71/SPEC 113 tests, 고정 로컬 Docker version 조회. 실제 프로젝트·컨테이너·plugin 검증은 미완료
- 2026-09-09 | Task 2a 로컬 준비 단계 완료 | 변경: 기록 게시·경로·권한 검사와 오류·취소·FD 회수 경계 보완 | 검증: 최종114 tests, 실제 설치본 조회와 회귀 probe, 독립 spec/quality 승인. Task2의 실제 프로젝트·빌드·격리·언어 배포물과 Task3는 미완료
- 2026-09-09 | Task 2b 실제 격리 시험 및 최종 검토 대기 | 변경: content-addressed image 검증, fixed container create/inspect/start/state/remove, 실제 Docker 표현에 맞춘 strict 설정 대조와 취소 경계 | 검증: 최신136 tests, copy-mode 설치본 전체 live probe와 owned container 0. native artifact/project mount·build·admission은 Task2c/2d 미완료
- 2026-09-09 | Task 2b 최종 검토·설치본 재검증 완료 | 변경: 소유권 확인 전 container ID 신뢰 금지, 취소·signal 오류와 strict inspect 타입 및 삭제 확인 보완 | 검증: 독립 승인 Critical/Important 0, focused 41 tests, 전체 183 tests, 최신 설치본 source 일치와 live probe 10개 mode·owned container 0. Task2c/2d·Task3는 계속 진행

- 2026-09-08 | 승인 방식의 실행 계획 추가 | 변경: 기존 여섯 저장소 보존, 통합 local 기반, native 검증, host 연결 순서 | 검증: 사용자 선택과 현재 CLI 지원 차이 대조. test는 아직 실행 전.
- 2026-09-08 | Task 1 로컬 기반 완료 | 변경: 선택 실행·고정 설치·엄격한 응답 검증·실행 차단·취소/정리 처리 | 검증: 최종 71 tests, 실제 설치본 검사, 독립 spec/quality 승인. 통합-02의 실제 배포물은 Task 2에도 연결하고 전체 언어 지원·운영 격리·plugin은 미완료로 유지.

## 기존 언어 실행 환경 점검

2026-09-08에 기존 실행기의 설치 진단만 새로 수행했다. 아래 결과는 실제 프로젝트 전체 품질·mutation·운영 격리 검증의 완료가 아니다.

|언어|실행 명령 또는 대상|관측|
|---|---|---|
|Python|SENTINEL_PY의 scripts/uv.sh run sentinel-py doctor --project . --format json|초기 설치 지문 불일치, 아래 원본 파일 복원 후 exit 0/passed=true|
|TypeScript|SENTINEL_TS의 scripts/node.sh --entry sentinel-ts -- doctor|exit 0/status=ready. StrykerJS와 Vitest runner 10.0.0|
|Go|SENTINEL_GO의 .toolchain/bin/sentinel-go doctor --project . --format json|exit 0/doctor.pass=true. 기존 mutate4go 기본값 유지|
|Java|SENTINEL_JAVA의 scripts/doctor.sh|exit 0/passed=true. Java·Maven·JaCoCo·기존 mutate4java 잠금 확인|
|Clojure|SENTINEL_CLJ의 scripts/sentinel-clj.sh doctor를 임시 1개 source project에 실행|exit 0/passed=true. clj-mutate 고정 commit 확인|

Python 복원 근거: 기존 설치 archive의 SHA-256은 `506191be3ee7bd190a8834dcdc1b3bc70aab50608deccc711935aa007239cabd`와 일치했다. archive와 설치 tree를 비교해 encodings/__pycache__ 아래의 __init__, aliases, utf_8의 cpython-312.pyc 세 파일 및 폴더 누락을 확인했다. 삭제 주체와 시점은 확인하지 않았다. 해당 항목만 가상으로 복원한 tree 지문이 잠금값 `c4b77b84ef44bf6390eef79e4a9d7a74bf50241e9cebb3fc8cb47d4ce21c3e83`과 일치함을 먼저 검증했다. 그 뒤 exact archive member 세 개만 기존 파일 덮어쓰기 금지·owner-only 권한으로 복원했다. 원본 source, toolchain.lock.json, backend.lock.json과 기존 Git 변경은 수정하지 않았다. 실제 복원 후 --verify-tree와 doctor가 모두 exit 0이었다.

문서 점검: 추가 요구사항 6개가 설계·작업에 모두 연결됨을 확인했고, 새 문서 3개의 owner/date, 양방향 참조와 AGENTS 활성 계획 링크가 존재한다. 기존 55개 요구사항을 완료로 승격하지 않았다.
