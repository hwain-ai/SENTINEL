---
type: design-doc
slug: sentinel-unified-entry
created: 2026-09-08
updated: 2026-09-10
status: approved-direction
owner: Codex
spec: docs/product-specs/2026-09-sentinel-unified-entry.md
related:
  - docs/exec-plans/active/2026-09-sentinel-unified-entry.md
---

# SENTINEL 통합 실행기 설계

결론: 독립적인 `SENTINEL` front door가 명시적 module 설정과 버전 고정된 언어 bundle을 연결한다. 다섯 언어 runtime을 서로 import하거나 SPEC에 mutation 엔진을 넣지 않는다.

## 구조와 책임

|구성요소|책임|
|---|---|
|SENTINEL|설정 읽기, 언어·module 선택, 로컬 bundle 설치·무결성 확인, 컨테이너 생성·시간 제한·정리, 결과 요약|
|SENTINEL_SPEC|기존 품질·증거 계약의 단일 기준. 통합 결과는 기존 품질 인증을 대체하지 않는 별도 transport envelope다.|
|언어별 SENTINEL|자기 언어의 빌드·coverage·mutation·typed evidence 처리와 native 배포물 생성|
|Codex·Claude Code plugin|호스트별 manifest와 검사 요청 skill. 동일 CLI를 호출하며 품질 판정 알고리즘은 두지 않는다.|

첫 front door는 Python 3.9 이상 표준 라이브러리만 사용하는 작은 별도 package로 구현한다. 기존 언어 SDK·backend의 version은 바꾸지 않는다. 추후 배포 시 독립 실행 파일로 묶을 수 있지만 이번에는 필요 없는 언어 SDK를 묶지 않는다.

2026-09-10 사용자 확정: 컨테이너 생성·시간 제한·정리는 통합 SENTINEL이 직접 소유한다. 언어별 연결부는 입력 준비·검사 명령·결과 변환을 맡고, 플러그인은 같은 통합 명령을 호출한다. 별도 상주 관리 프로그램은 추가하지 않는다. Go의 설치된 통합 명령에는 이 구조를 적용했으며, 다른 언어는 같은 경계를 유지하며 순차 연결한다. 부모 SENTINEL 자체가 SIGKILL로 사라진 경우의 다음 실행 복구는 별도 검증 항목이지 자동으로 해결되는 보장이 아니다. 기존 일반 bundle의 요청·응답 계약은 조용히 바꾸지 않는다.

## 공식 배포처의 최초 준비 신뢰

2026-09-10 사용자 승인: 실제 공개 Java·Python 프로젝트 비교에 필요한 새 빌드·테스트 도구는 공식 Maven Central·PyPI의 HTTPS 배포를 최초 신뢰 기준으로 준비한다. 도구 버전·정확한 다운로드 주소·SHA-256을 기록하고, 준비된 전체 파일 목록과 지문을 고정한다. Java 빌드 준비 도구의 만료된 서명을 통과한 것으로 기록하지 않는다. 같은 배포처의 파일과 체크섬 대조는 손상·변경 확인이며 공급자 서명 인증과 다르다.

외부 접속은 이 준비 단계에 한정한다. 검증한 도구로 실제 프로젝트를 빌드·테스트하는 단계는 네트워크가 차단된 컨테이너에서만 실행한다. 승인 범위는 상용 도구 구매, 기본 검사 엔진 전환, 정식 품질 인증, 호스트 플러그인 자동 활성화를 포함하지 않는다. 이후 의존성 갱신도 새 버전·파일 지문과 호환성 시험을 남기고 기존 고정 설치물을 덮어쓰지 않는다.

## 설정과 선택

`sentinel.workspace.json`에는 schemaVersion, modules를 둔다. module은 id, language, root, toolVersion, toolDigest를 필수로 가지며 config는 선택 항목이다. language의 허용값은 python, typescript, go, java, clojure다. root와 config는 workspace 안의 실제 경로만 허용한다. symlink, 경로 탈출, 같은 경로 또는 조상·자손 module 중복, 중복 id, 알 수 없는 field, 빈 modules는 거부한다. module별 source·build·test 세부 사항은 native config에 남기며 front door가 만들어내지 않는다.

`check`와 `doctor`는 기본으로 모든 설정 module을 선택한다. `--language` 또는 `--module`은 선택 범위를 줄이며, 없는 대상을 요청하면 사용 오류다. 같은 종류의 선택 옵션은 반복할 수 있지만 두 종류를 한 호출에 혼용하면 거부해 의도하지 않은 합집합 실행을 막는다. 전체라는 표현은 `allConfigured`를 의미하며 repository의 모든 파일 발견이나 strict 전체 인증을 증명하지 않는다. 자동 탐지는 이후 설정 제안에만 사용하며 자동 실행 범위를 만들지 않는다.

## 선택형 로컬 설치

`install --bundle DIR --sha256 DIGEST --tools DIR`는 정확한 manifest digest가 지정된 bundle만 복사한다. bundle manifest는 language, version, protocolVersion, entrypoint, files를 가진다. files는 상대 경로와 SHA-256의 완전한 목록이며 manifest 자신은 제외한다. entrypoint는 files에 포함된 실행 파일이다. 하위 디렉터리 이외의 symlink·특수 파일, 목록 누락·추가, 경로 탈출, digest 불일치, 정해진 크기 제한 초과를 거부한다.

설치 주소는 tools/language/version/digest이며 내용 기준으로 불변이다. 임시 디렉터리에서 검증·복사하고 atomic rename으로 게시한다. 동일 bundle 재설치는 다시 무결성을 검사한 뒤 성공하고 기존 파일을 덮어쓰지 않는다. 서로 다른 version은 나란히 유지하고, 되돌리기는 project 설정의 고정 version/digest를 이전 것으로 바꾼다. 기존 SDK를 download하거나 실행하는 동작은 없다. 도구 목록은 project 코드 안에서 임의 검색하지 않는다.

복사 시점에도 manifest와 각 파일의 실제 지문을 앞서 검증한 pin과 다시 비교하고 누적 크기를 제한한 뒤 쓴다. 첫 검증 후 원본 내용이 바뀌면 staging에 그 내용을 복사하지 않으며 이전 설치는 유지한다.

RISK(race): 게시에는 Linux renameat2의 no-replace 기능을 사용한다. 기존 대상을 교체할 수 있는 일반 rename으로 대체하지 않으며 기능이 없으면 고정 오류로 거부한다. 새 디렉터리는 0700으로 생성하고 기존 사용자 폴더를 임의 chmod하지 않는다. 원본 bundle과 설치 경로의 parent traversal은 거부하고 내부 상대 경로 구성요소는 256개 이하로 제한해 깊은 tree가 raw 재귀 예외로 이어지지 않게 한다. 이는 적대적인 동시 path substitution 전체를 막는 sandbox 보장이 아니다.

## process 연결 계약

실행기는 표준 입력의 JSON 요청 한 개를 받고 표준 출력으로 JSON 결과 한 개를 반환한다. 요청에는 protocolVersion, requestId, command, moduleId, language, projectRoot, config가 있다. projectRoot는 선택한 module의 절대 경로이며, 자식 process의 작업 디렉터리도 그 module이다. config가 없는 경우 null이다. command는 check만 허용한다. doctor는 통합 실행기 안에서 설치 파일만 확인하고 protocol 요청이나 자식 process를 만들지 않는다. 응답은 protocolVersion, requestId, command, moduleId, language, toolVersion, status, exitCode, passed만 허용한다. 임의 메시지·경로·소스·raw log는 공용 결과에 옮기지 않는다.

protocol의 status와 exitCode의 고정 대응은 passed=0, toolError=1, qualityFailed=2, usageConfigError=3, baselineFailed=4, dependencyError=5, backendError=6, evidenceError=7, cancelled=8이다. passed status에서만 passed=true다. ready는 doctor가 내는 로컬 설치 확인 상태이며 protocol 응답이 아니다. identity·자료형·상태·process exit·응답 exit가 다르거나 JSON key가 중복되면 backendError다. 오류의 raw stdout·stderr는 출력하지 않는다. 각 module의 실제 관측 종료 코드를 먼저 모으고, 실패가 하나라도 있으면 고정 우선순위 7,1,5,6,8,4,3,2로 보존한다. 실제 실패가 없는 experimental check만 전체 종료 코드를 backendNotAdmitted의 6으로 바꾼다.

RISK(security): bundle은 사용자가 신뢰한 실행 코드다. hash 검사는 인증이나 sandbox가 아니며, 원본 프로젝트 경로를 받는 실행기의 악의적 접근을 막지 못한다. 첫 버전은 명시적인 `--experimental` check만 허용한다. 이 플래그가 없으면 child process를 시작하지 않고 backendNotAdmitted를 반환한다. experimental check도 certified=false, pass=false이며, 실행기별 관측 성공과 제품 인증을 구분한다. 정식 품질 통과가 가능해지려면 native evidence 검증과 운영 격리 admission을 별도 구현해야 한다.

실행은 우선 순차로 한다. timeout과 전체 출력 byte 제한을 적용하고 process group을 종료·회수한다. 환경은 최소 PATH와 locale만 전달하며 사용자 secret 환경 변수를 상속하지 않는다. process group 탈출 차단, CPU·메모리·network·filesystem 보안 경계는 후속 sandbox 검증 대상이다. help·plan·doctor는 품질 검사를 실행하지 않는다. doctor는 bundle 설치 상태만 확인하며 실행 코드도 호출하지 않는다.

취소 요청과 회수 실패는 서로 지우지 않는다. 둘이 겹치면 현재 module의 backendError/6을 보존하고, 남은 module은 cancelled/8로 채워 실행을 중단한다. 전체 종료 우선순위는 그대로다. CLI의 parser 출력과 마지막 flush도 오류 경계에 포함하며 출력 통로 실패는 고정 exit 3으로 처리한다. 정상 사용자 출력 통로는 교체하지 않는다.

## 운영 격리 전의 읽기 전용 사전 검증

Task 2a의 [oci.py](../../src/sentinel/oci.py)는 기존 T01에 승인된 실행기 조건을 검사하는 준비 코드다. 명시적 외부 lock과 원본 SHA-256을 받아 로컬 Docker의 실행 파일, socket, client/server/Engine version을 대조한다. 현재 환경을 자동 승인하지 않으며 정식 SPEC lock이나 품질 계약을 대체하지 않는다.

prepare_session은 Git 밖 소유자 전용 새 폴더의 기록을 봉인하고 지문을 반환한다. recheck_session은 같은 입력과 현재 환경을 다시 읽으며 파일을 쓰지 않는다. Docker version 조회 외의 명령을 받는 API는 없다. 기존 CLI의 help·plan·doctor·check·install에는 자동 연결하지 않는다. 추가 metadata가 있는 Docker JSON은 중복 key·NaN/Infinity를 별도로 거부하며, process 제한·회수는 기존 collector를 재사용한다.

RISK(security): 조회 전후 신원과 기록 파일의 FD·지문 대조는 실제 container sandbox의 검증이 아니다. 신뢰된 host에서 수행하는 준비 단계이며, 같은 UID의 악성 process가 모든 syscall 사이에서 계속 경로를 교체하는 전체 경쟁을 방어했다고 주장하지 않는다. 후속 driver에는 별도의 image·읽기 전용 runtime-root·project copy·network·resource 검증이 필요하다. SDK나 여러 native 실행 파일을 현재의 작은 bundle에 그대로 복사하는 것으로 배포 완료를 대체하지 않는다.

기록 게시의 완료 시점은 내용·신원·동기화·최종 경로 검증과 기록 FD 닫기를 모두 마친 때다. 그 이전 취소는 정리 후 전파하지만, 완료 뒤 마지막 읽기용 root FD 닫기의 OS 오류·취소는 이미 끝난 결과를 보존한다. RISK(cancellation): 후속 driver는 이 API의 반환과 별도로 사용자 취소 상태를 유지하고 다음 OCI/native 실행 전 확인해야 한다. 이 준비 코드가 아직 연결되지 않은 다단계 작업의 취소 제어까지 구현한 것은 아니다. 프로세스 사망을 포함한 모든 시점에서 저장과 호출자 acknowledgement가 원자적이라는 보장은 하지 않는다.

## 실제 격리 실행으로 연결

후속 Task 2b는 이미지 내용 검증과 실제 컨테이너 수명을 분리한다. oci_image.py는 원본 manifest·config bytes의 지문과 Linux amd64 조건만 검사하며 network를 호출하지 않는다. sandbox.py는 Task 2a의 봉인된 실행기 session을 매 Docker 호출 전후 재검사하고, 명시적인 이미지 준비와 컨테이너 실행을 담당한다. 기존 언어 엔진이나 공통 CLI의 품질 판정을 복제하지 않는다.

순서는 고정 image reference의 명시적 pull, config digest와 inspect image ID 대조, image ID로 create, 생성된 보안 설정 inspect, start, 종료 상태 확인, 자기 ID의 삭제·부재 확인이다. timeout이나 Docker client 취소만으로 컨테이너가 종료됐다고 가정하지 않는다. 별도 취소 상태를 유지하고, 정리가 실패하면 성공·단순 취소로 바꾸지 않는다. 원시 출력은 내부에서 크기·지문 관측에만 사용하고 공용 품질 결과로 내보내지 않는다.

첫 실제 시험은 host mount 0개인 고정 프로필이다. non-root 사용자, network none, read-only root, capability 제거, 추가 권한 획득 금지, private namespace, CPU·메모리·PID와 tmpfs 제한을 요청하고 실제 inspect 값으로 재확인한다. 이렇게 검증한 수명 관리에 다음 Task 2c의 내용 고정 runtime·artifact·fixture·offline dependency를 연결한다. 기존 SDK를 그대로 mount하거나 bundle 크기 제한을 높여 독립 배포 검증을 생략하지 않는다.

RISK(security): 같은 host의 Docker/커널은 신뢰 기반이다. 이 시험은 VM 수준이나 알려지지 않은 취약점까지의 차단을 보장하지 않는다. 현재 단계에는 host mount가 없으므로 실제 프로젝트의 복사·읽기 전용 source·허용 출력 경로 검증은 별도로 남는다. SIGKILL 직후 복구와 운영 admission도 이 단계의 성공만으로 승인하지 않는다.

## 3~5수 앞의 결과와 회복

1. 현재: 기존 여섯 저장소를 건드리지 않고 통합 명령과 설치·호출 계약을 시험한다.
2. 다음: native bundle을 언어별로 만들고 동일 실제 프로젝트·빌드 조합의 근거를 붙인다. CLI 차이는 해당 언어 adapter에서 처리한다.
3. 운영 전: 원본 보호, filesystem/network 격리, 강제 종료·자원 제한을 검증하고 별도 admission 계약을 추가한다.
4. 호스트 연결: 같은 CLI를 Codex·Claude Code skill에 연결한다. 명시적 검사부터 시작하며 자동 hook은 넣지 않는다.
5. 6개월 후: 외부 검사 도구 변경은 해당 bundle과 호환성 시험에 한정한다. 호환성이 깨지면 이전 digest를 선택하고 전체 결과 계약·다른 언어 설치는 유지한다.

## 변경이력

- 2026-09-10 | 실행 책임과 공식 준비 신뢰 확정 | 변경: 사용자 승인에 따라 통합 SENTINEL의 컨테이너 수명 관리와 Maven Central·PyPI 최초 준비 범위를 명시 | 검증: 승인 문면을 실행 계획과 대조. 공급자 서명·실제 프로젝트 통과·운영 허용으로 확대 해석하지 않음.
- 2026-09-09 | Go 설치·격리 기반의 실패 처리 검증 완료 | 변경: 입력 검사부터 종료 후 검사까지 취소 상태 유지, 기존 회수 실패 보존, 신호 처리기 복원과 경로 오류 비공개 처리 | 검증: 전체216 tests/10.962초, 재설치 source 일치, 독립 후속 ACCEPT, Go 실제 격리10종·복구와 공통 재시험·마지막 컨테이너0. [실제 관측과 한계](https://github.com/hwain-ai/SENTINEL_GO/blob/main/docs/sentinel-go-native-validation.md)를 기준으로 전체 backend 비교·admission·plugin은 미완료로 유지.
- 2026-09-09 | Task 2b 승인 이후 Go 독립 입력 연결 | 변경: 네 content-addressed root와 Go 전용 제한 profile을 공통 OCI lifecycle에 연결, 기존 no-host API 유지 | 검증: Task2b 최종 독립 승인과 새 설치본 재시험, 전체199 tests, Go 원래 make build·입력 보존. Go 전체 비교·운영 admission·plugin은 미완료이며 [실제 관측](https://github.com/hwain-ai/SENTINEL_GO/blob/main/docs/sentinel-go-native-validation.md)에 분리 기록.
- 2026-09-09 | Task 2b 실행 연결 검증 및 최종 검토 대기 | 변경: raw image identity와 실제 container 생성·검사·회수, 고정 권한·자원과 취소 경계 구현 | 검증: 최신136 tests, 설치본의 filesystem·environment·network·cgroup·timeout·escape·OOM·PID·CPU·overflow·SIGINT 및 owned container 0. 독립 검토와 Task2c native input 연결은 진행 중
- 2026-09-09 | Task 2 사전 검증 경계 | 변경: 기존 저장소 수정 없이 외부 승인 lock을 받는 읽기 전용 OCI 준비 API, 게시·취소 경계와 별도 runtime-root 필요성을 명시 | 검증: root의 최종114-test·설치본 Docker 조회·파일/FD/취소 반례 시험과 독립 v3 spec/quality 승인. 운영 admission·native bundle·plugin은 미완료

- 2026-09-08 | 승인 방향 구체화 | 변경: 통합 실행, 독립 bundle, preview와 정식 인증의 경계 및 설치 안전 조건 | 검증: 기존 native CLI와 language별 출력 차이를 소스에서 대조
