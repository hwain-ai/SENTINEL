# SENTINEL 명령·설정·도구 제작 상세 계약

처음 설치하는 분은 [README 사용 가이드](../../README.md#사용-가이드)를 먼저 따르세요. 이 문서는 기존 README의 세부 계약을 모은 개발자 참고입니다.

아래 `.venv/bin/sentinel` 예시는 실행기와 검사 프로젝트가 같은 폴더라는 가정입니다. 다른 프로젝트에는 README에서 지정한 실행 파일 경로와 `--project`, `--tools`를 사용합니다. `--experimental`은 개발자 검증용이며 정식 품질 인증을 하지 않습니다.

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

## 검사 범위 설정

검사할 프로젝트의 sentinel.workspace.json에 다음 필드를 둡니다. 파일 형식은 JSON이며 중복 필드와 알 수 없는 필드는 거부합니다.

|위치와 필드|넣을 값|
|---|---|
|최상위 schemaVersion|고정 문자열 sentinel-workspace-v1|
|최상위 modules|1개 이상 128개 이하의 모듈 목록|
|최상위 gate|선택 항목. crapMax(기본 "8")와 mutationMin(기본 "90") 문자열|
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

실행기·언어 도구의 갱신은 [README의 갱신 절차](../../README.md#승인된-도구-버전-갱신)를 따릅니다.

도구의 실제 실패 상태는 toolError=1, qualityFailed=2, usageConfigError=3, baselineFailed=4, dependencyError=5, backendError=6, evidenceError=7, cancelled=8로 구분합니다. 여러 실패가 섞이면 7,1,5,6,8,4,3,2 순서로 전체 종료 코드를 정합니다. 설치 누락이나 손상이 발견되면 선택한 도구를 하나도 실행하지 않습니다.

취소와 자식 프로세스 정리 실패가 겹치면 해당 모듈은 backendError=6으로 남기고, 아직 시작하지 않은 모듈은 cancelled=8로 표시합니다. 이후 도구는 실행하지 않습니다. 명령의 출력 통로가 닫혔거나 사용할 수 없으면 내부 예외 대신 종료 코드 3으로 끝냅니다.

일반 실행 파일 형식에는 실행 시간과 합계 1 MiB 출력 제한, 최소 환경 변수, 프로세스 그룹 정리를 적용합니다. 이것만으로 파일·네트워크·자원을 강제로 격리하지는 못합니다. 지문 일치도 제작자의 신뢰나 악성 코드 부재를 증명하지 않습니다.
