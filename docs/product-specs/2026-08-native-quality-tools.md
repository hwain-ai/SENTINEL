---
type: product-spec
slug: native-quality-tools
created: 2026-08-31
updated: 2026-09-03
status: approved
owner: Codex
requirements: 요구사항-01..요구사항-55
constraints: 공통규칙-01..공통규칙-10
related:
  - docs/design-docs/2026-08-native-quality-tools.md
  - docs/exec-plans/active/2026-08-native-quality-tools.md
---

# SENTINEL 다언어 품질 게이트

결론: 이 명세는 Python, TypeScript, Go, Java, Clojure 프로젝트를 같은 기준으로 검사하기 위해 6개 SENTINEL 저장소가 갖춰야 할 기능과 합격 조건 55개를 확정한다.

## 먼저 알아둘 말

|용어|뜻|
|---|---|
|SENTINEL·repository|SENTINEL은 이 명세에 따라 품질을 검사하는 도구 모음이고, repository(저장소)는 코드와 변경 이력을 함께 보관하는 폴더 단위다.|
|source·test·module|source는 검사할 원본 코드, test는 실제 결과가 예상과 같은지 확인하는 코드, module은 한 저장소 안에서 언어·검사 범위·test 명령을 함께 설정하는 실행 단위다.|
|production code|사용자에게 실제 기능을 제공하는 코드다. test code와 자동 생성 코드는 여기에 포함하지 않는다.|
|callable|함수나 메서드처럼 이름을 지정해 실행할 수 있는 코드 단위다.|
|coverage|test가 production code를 실제로 실행한 비율이다.|
|CRAP|함수가 복잡하고 test되지 않은 부분이 많을수록 커지는 코드 위험 점수다. 이 문서에서는 반올림 전 점수가 8.0 이하여야 통과한다.|
|mutation test|production code의 연산자나 조건을 일부러 조금 바꾼 뒤 test가 그 잘못을 잡는지 확인하는 검사다. 이렇게 만든 변경본을 `mutant`라고 한다.|
|in-scope mutant|설정한 검사 범위에 들어가 합격 판정에 반드시 포함해야 하는 mutant다.|
|killed·survived·uncovered|test가 잘못을 잡으면 killed, 잡지 못하면 survived, 해당 코드를 test가 실행하지 않았으면 uncovered 상태다.|
|timedOut·error·pending·ignored|제한 시간 초과, 컴파일·실행·도구 오류, 미완료, 무시 상태다. 이 문서의 strict 검증에서는 모두 실패 원인이 된다.|
|backend|언어별 mutant 생성과 실행을 실제로 담당하는 외부 도구다. SENTINEL은 그 결과를 공통 형식으로 바꾸고 합격 여부를 판정한다.|
|wrapper|backend를 직접 사용하기 쉽도록 공통 명령과 규칙으로 감싸는 프로그램이다.|
|gate|검사 결과가 정해진 기준을 모두 만족할 때만 통과시키는 판정 단계다.|
|strict·fresh|strict는 예외를 허용하지 않는 최종 판정이고, fresh는 이전 결과를 재사용하지 않고 새로 전체를 검사한다는 뜻이다.|
|baseline test|mutant를 만들기 전에 변경하지 않은 원본 코드가 정상인지 먼저 확인하는 test다.|
|runtime·dependency|runtime은 프로그램이 실행되는 언어 환경이고, dependency는 실행에 필요한 외부 package나 도구다.|
|operator inventory·상태 정규화|operator inventory는 backend가 mutant를 만들 때 사용한 변경 종류의 전체 목록이고, 상태 정규화는 backend마다 다른 결과 이름을 SENTINEL 공통 이름으로 바꾸는 처리다.|
|cache·incremental|cache는 이전 실행 결과를 다시 쓰기 위한 임시 저장소이고, incremental은 바뀐 범위만 다시 검사하는 방식이다.|
|CLI·CI|CLI(Command-Line Interface)는 터미널에서 실행하는 명령이고, CI(Continuous Integration)는 원격 서버가 변경된 코드를 자동 검사하는 절차다.|
|fixture|특정 입력과 예상 결과를 고정해 도구 동작을 반복 검증하는 test 자료다.|
|version·schema·artifact|version은 계약이나 도구의 변경 단계를 식별하는 번호, schema는 기계용 결과의 항목과 자료형을 정한 규칙, artifact는 CI가 보관하는 실행 결과 파일이다.|
|exit code|명령이 성공했는지 또는 어떤 종류로 실패했는지 운영체제에 숫자로 알리는 값이다.|
|hash·digest|파일 내용으로 계산한 비교값이다. 이 문서에서는 실행 전후 내용이 같은지 검사하는 데 사용한다.|
|N/A·raw|N/A는 필요한 자료가 없어 값을 계산할 수 없는 상태이고, raw는 정리하거나 비밀값을 제거하기 전의 원본 결과다.|
|harness|코드 작성, test 실행과 결과 판정을 순서대로 조정하는 자동화 도구다. SwarmForge는 이 도구를 사용할 수 있는 하네스 중 하나다.|
|golden fixture·conformance|golden fixture는 정답을 미리 고정한 test 자료이고, conformance는 실제 결과가 그 공통 계약과 일치하는지 확인하는 검사다.|
|fingerprint|같은 종류의 결함이 다시 나타났는지 비교하기 위한 비식별 표식이다.|
|allowlist·canary|allowlist는 명시적으로 허용한 항목만 통과시키는 목록이고, canary는 금지 정보가 새는지 찾기 위해 일부러 넣는 탐지용 값이다.|
|append-only·redacted export|append-only는 기존 기록을 고치지 않고 새 기록만 추가하는 방식이며, redacted export는 비밀값과 식별정보를 제거한 내보내기 파일이다.|
|branch·HEAD|branch는 Git 변경 이력이 이어지는 작업선이고, HEAD는 로컬 저장소가 현재 가리키는 commit이다.|
|OKF v0.2 bundle|문서 설명 정보인 frontmatter와 `index.md`, `log.md`를 포함하는 이 프로젝트의 지식 문서 묶음 형식이다.|

## 실제 입력 → 처리 → 출력

1. 입력: 검사할 production source, test, 언어별 설정과 검사 범위를 받는다.
2. 처리: fresh coverage로 callable별 CRAP을 계산하고, 승인된 backend로 in-scope mutant를 실행한 뒤 결과 상태를 공통 형식으로 바꾼다.
3. 판정: 최대 CRAP의 반올림 전 값이 8.0 이하이고 모든 in-scope mutant가 killed인 경우에만 strict gate를 통과시킨다.
4. 출력: 사람이 읽는 결과, schema에 맞는 기계용 증거, 종료 코드와 프로젝트별 결함 이력을 남긴다.

예를 들어 in-scope mutant 10개가 모두 killed이고 최대 CRAP이 7.5라면 두 품질 기준을 만족한다. 10개 중 1개라도 survived이거나 최대 CRAP이 8.0을 초과하면 실패한다.

## 읽는 순서

1. `성공 기준`에서 최종 완료 모습을 확인한다.
2. `공통규칙`에서 55개 요구사항 모두에 적용되는 제한을 확인한다.
3. `요구사항` 표에서 필요한 ID의 기능과 검증 방법을 함께 읽는다.
4. `범위 밖`과 `미해결 항목`에서 이번 구현에 포함하지 않는 일을 확인한다.
5. `PRD 원문 대조`와 `변경이력`에서 사용자 요청이 어떤 문장으로 확정됐는지 확인한다.

## 1. 배경과 목표

Python, TypeScript, Go, Java, Clojure 프로젝트에 같은 CRAP·mutation 품질 기준을 적용할 독립 도구 모음이 필요하다. CRAP은 언어별 구문과 coverage를 직접 분석하고, mutation은 검증된 언어별 backend를 사용하되 SENTINEL이 검사 범위, 상태 해석, 엄격한 합격 판정을 통제한다.

목표는 공통 계약 저장소 `SENTINEL_SPEC`과 실행형 언어 저장소 `SENTINEL_PY`, `SENTINEL_TS`, `SENTINEL_GO`, `SENTINEL_JAVA`, `SENTINEL_CLJ`를 구현하는 것이다. 사람, CI, SwarmForge와 다른 코딩 하네스가 같은 명령과 결과 계약을 사용하고, 실행 과정에서 발견·해결·재발한 결함을 프로젝트별 이력으로 남겨 반복 문제를 확인할 수 있어야 한다.

별도 우선순위 지시가 없으므로 아래 요구사항은 모두 필수다.

## 2. 성공 기준

이 작업이 끝났다고 판정하려면 다음 조건이 모두 참이어야 한다.

- `SENTINEL_SPEC`과 5개 실행형 SENTINEL을 각각 비공개 저장소에서 설치·검증할 수 있다.
- 5개 실행형 SENTINEL은 공통 의미의 `crap`, `mutation`, `check`, `doctor`, `history` 기능을 제공한다.
- 각 실행형 SENTINEL의 모든 production 함수는 coverage가 확인되며 최대 CRAP이 8.0 이하이다.
- 각 실행형 SENTINEL의 fresh 전체 mutation 검증은 in-scope mutant가 1개 이상이고 전부 killed이며 survived, uncovered, timeout, compile·runtime·tool error, pending, ignored, 무단 제외가 모두 0이다.
- 모든 실행 결과는 공통 계약에 맞는 사람용 결과, 기계용 증거, 종료 코드를 제공한다.
- 최초 실패부터 수정·재실행·해결·재발까지 프로젝트 소유의 이력으로 남고, 현재 프로젝트 안에서 반복 결함을 조회할 수 있다.
- 공용 증거, 이력, export와 기본 CI artifact에 소스·mutant 원문, 비밀값, 절대 경로, 저장소 식별정보, raw 출력이 포함되지 않는다.
- 6개 비공개 GitHub 저장소의 기본 branch와 로컬 HEAD가 일치하고 원격 CI가 성공한다.
- 기존 Robert Martin 원본 저장소와 SwarmForge 저장소의 내용은 바뀌지 않는다.
- 6개 저장소 내부 문서 번들이 OKF v0.2 점검을 통과한다.

## 3. 공통규칙

모든 요구사항과 모든 구현 작업에 적용한다.

|ID|제약|
|---|---|
|공통규칙-01|`SENTINEL_SPEC`, `SENTINEL_PY`, `SENTINEL_TS`, `SENTINEL_GO`, `SENTINEL_JAVA`, `SENTINEL_CLJ` 6개 비공개 저장소를 구현한다.|
|공통규칙-02|v1에서는 mutation 엔진을 새로 구현하지 않고 승인·고정한 언어별 backend를 wrapper로 사용한다. SENTINEL은 검사 범위, 상태 정규화, 증거, 엄격한 gate를 소유한다.|
|공통규칙-03|CRAP은 반올림 전 값 기준 최대 8.0 이하이고, mutation은 모든 in-scope mutant가 killed일 때만 통과한다.|
|공통규칙-04|SwarmForge뿐 아니라 앞으로 사용하는 다른 코딩 하네스, 사람, CI가 동일한 독립 CLI로 실행할 수 있게 만든다.|
|공통규칙-05|6개 원격 저장소는 인증된 GitHub 계정 `hwain-ai`에 비공개로 만든다.|
|공통규칙-06|기존 `crap4clj`, `crap4go`, `crap4java`, `clj-mutate`, `mutate4go`, `mutate4java`, `swarm-forge` 저장소는 고정된 비교 자료와 backend 근거로만 사용하고 수정하지 않는다.|
|공통규칙-07|Git 명령은 반드시 각 소유 child repository 안에서만 실행한다. workspace root는 Git 저장소로 취급하지 않는다.|
|공통규칙-08|모든 production 동작은 실패하는 test를 먼저 확인한 뒤 구현한다.|
|공통규칙-09|사용자 소스는 mutation 실행 중 손상되거나 다른 편집으로 덮어써지면 안 된다.|
|공통규칙-10|6개 저장소 내부에 들어가는 지식 문서는 OKF 형식으로 작성한다.|

## 4. 요구사항

|ID|우선순위|요구사항|검증 방법|
|---|---|---|---|
|요구사항-01|필수|`SENTINEL_PY`는 독립 설치·실행 가능한 Python CRAP·mutation 품질 게이트여야 한다.|깨끗한 Python 환경에서 설치 후 공통 CLI와 Python fixture를 실행한다.|
|요구사항-02|필수|`SENTINEL_TS`는 독립 설치·실행 가능한 TypeScript·TSX CRAP·mutation 품질 게이트여야 한다.|깨끗한 Node 환경에서 설치 후 공통 CLI와 TypeScript·TSX fixture를 실행한다.|
|요구사항-03|필수|Python mutation 결과는 승인된 backend에서 얻고 SENTINEL 공통 상태·증거·엄격한 gate로 정규화해야 한다.|backend 결과별 fixture가 공통 상태와 합격 여부로 정확히 변환되는지 검사한다.|
|요구사항-04|필수|TypeScript·TSX mutation 결과는 승인된 backend에서 얻고 SENTINEL 공통 상태·증거·엄격한 gate로 정규화해야 한다.|backend 결과별 fixture가 공통 상태와 합격 여부로 정확히 변환되는지 검사한다.|
|요구사항-05|필수|5개 실행형 SENTINEL은 특정 하네스 라이브러리 없이 명령줄에서 실행할 수 있어야 한다.|각 package 의존성과 실행 경로에서 SwarmForge나 다른 하네스 전용 의존성이 없는지 검사한다.|
|요구사항-06|필수|5개 실행형 SENTINEL은 사람이 읽는 결과와 versioned 기계용 결과를 함께 제공해야 한다.|같은 fixture 실행의 사람용 결과와 기계용 결과의 핵심 수치가 일치하는지 검사한다.|
|요구사항-07|필수|공통 결과 계약은 SENTINEL·schema version, 언어, backend, 입력 범위, 측정값, 상태별 개수, 합격 여부를 포함해야 한다.|공통 schema fixture로 필수 field와 type을 검증한다.|
|요구사항-08|필수|정상, 사용 오류, 품질 실패, baseline 실패, dependency·backend·증거 오류를 종료 코드로 구분해야 한다.|각 상태 fixture의 process exit code를 검사한다.|
|요구사항-09|필수|모든 CLI는 외부 작업 없이 사용법을 보여주는 help를 제공해야 한다.|help 실행 시 test·coverage·backend·source·history 작업이 0회인지 검사한다.|
|요구사항-10|필수|5개 실행형 SENTINEL은 언어별 callable의 CC, coverage, CRAP을 보고해야 한다.|각 언어 공식 fixture의 callable별 세 값과 기대값을 비교한다.|
|요구사항-11|필수|CRAP은 `CC² × (1 - coverage)³ + CC` 공식으로 계산해야 한다.|100%, 50%, 0% coverage의 고정 예제로 계산값을 검증한다.|
|요구사항-12|필수|Python CRAP은 일반·비동기·메서드·중첩 함수를 서로 구분해야 한다.|각 callable이 있는 fixture에서 독립 결과와 중복 없는 coverage를 검사한다.|
|요구사항-13|필수|TypeScript CRAP은 함수·메서드·getter·setter·함수 표현식·arrow·TSX callback을 서로 구분해야 한다.|각 callable이 있는 TS·TSX fixture의 독립 결과를 검사한다.|
|요구사항-14|필수|CRAP 분석은 오래된 coverage 결과로 통과하면 안 된다.|오래된 report를 둔 뒤 fresh coverage 실패 시 분석도 실패하는지 검사한다.|
|요구사항-15|필수|coverage 누락, 형식 오류, 모호한 source 연결은 품질 통과로 처리하면 안 된다.|누락·손상·경로 충돌 fixture가 오류 또는 N/A 품질 실패인지 검사한다.|
|요구사항-16|필수|CRAP 결과는 반올림 전 값 기준 최대 8.0까지만 통과해야 한다.|정확히 8.0은 성공하고 8.0 초과는 품질 실패하는지 검사한다.|
|요구사항-17|필수|CRAP 보고서는 위험도가 큰 callable부터 안정적으로 정렬해야 한다.|동점과 N/A를 포함한 결과 순서를 반복 실행해 비교한다.|
|요구사항-18|필수|Mutation은 명시적이고 비어 있지 않은 production 범위를 검사하며 strict 실행은 설정된 전체 production 범위를 빠짐없이 포함해야 한다.|부분·빈·test·generated 범위 fixture와 전체 inventory를 대조한다.|
|요구사항-19|필수|Python mutation은 backend가 실제 사용한 operator inventory, version, 대상, 제외·무시 항목을 증거에 남겨야 한다.|operator와 제외 설정을 바꾼 fixture에서 증거와 strict 판정 변화를 검사한다.|
|요구사항-20|필수|TypeScript·TSX mutation은 backend가 실제 사용한 operator inventory, version, 대상, 제외·무시 항목을 증거에 남겨야 한다.|operator와 제외 설정을 바꾼 fixture에서 증거와 strict 판정 변화를 검사한다.|
|요구사항-21|필수|`doctor`는 runtime, dependency, backend, 설정과 검사 범위를 진단하되 test·coverage·mutation·source·history write를 실행하면 안 된다.|각 외부 작업 호출 횟수 0과 source·history hash 불변을 검사한다.|
|요구사항-22|필수|정상 mutation 전에 원본 baseline test가 통과해야 한다.|baseline 실패 fixture에서 mutant 실행 0회와 전용 종료 코드를 검사한다.|
|요구사항-23|필수|coverage가 없는 mutant는 uncovered로 보고하고 strict gate에서 실패시켜야 한다.|covered·uncovered 혼합 fixture의 상태와 합격 여부를 검사한다.|
|요구사항-24|필수|SENTINEL은 backend의 격리 실행을 검증하고 각 mutant가 원본 사용자 소스를 오염시키지 않게 해야 한다.|병렬·중단·backend 오류 fixture에서 원본 hash와 worker 결과 격리를 검사한다.|
|요구사항-25|필수|Mutation timeout은 killed와 분리해 보고하고 strict gate에서 실패시켜야 한다.|hang fixture에서 process 종료, timeout 상태와 품질 실패를 검사한다.|
|요구사항-26|필수|Mutation 결과는 killed, survived, uncovered, timedOut, compileError, runtimeError, pending, ignored, toolError를 중복 없이 정규화해야 하며 알 수 없는 상태를 성공으로 처리하면 안 된다.|모든 상태와 unknown 상태 fixture의 불변식·실패 여부를 검사한다.|
|요구사항-27|필수|실행 중단·오류·동시 편집이 있어도 원본 source 내용이 보존되어야 한다.|정상, timeout, signal, backend 오류, hash 충돌 뒤 원본 byte hash를 비교한다.|
|요구사항-28|필수|일반 로컬 실행은 검증된 cache·incremental 결과를 사용할 수 있지만 strict 인증 실행은 fresh 전체 결과만 사용해야 한다.|같은 변경에서 local cache 사용과 strict fresh 재실행을 각각 확인한다.|
|요구사항-29|필수|부분·변경 범위 결과는 전체 strict 통과 증거를 생성하거나 대체할 수 없다.|부분 실행 전후 전체 통과 증거가 생성·변경되지 않는지 검사한다.|
|요구사항-30|필수|Strict kill rate는 `killed / in-scope mutant × 100`으로 계산하며 in-scope mutant가 0개이면 100%로 처리하지 않아야 한다.|고정 count와 0 mutant fixture에서 반올림 전 값과 실패 여부를 검사한다.|
|요구사항-31|필수|Fresh 전체 strict gate는 모든 in-scope mutant가 killed이고 survived, uncovered, timedOut, compileError, runtimeError, pending, ignored, toolError, 무단 제외가 모두 0일 때만 통과해야 한다.|상태 하나씩 1개인 반례와 모두 killed인 fixture를 비교한다.|
|요구사항-32|필수|Project 설정과 CLI override는 예측 가능한 우선순위를 가지며 실제 backend identity·version, operator inventory, 범위와 설정 digest를 증거에 남겨야 한다.|설정 우선순위, version 변경, missing dependency fixture를 검사한다.|
|요구사항-33|필수|5개 실행형 저장소는 unit, integration, acceptance, clean-install test를 가지고 `SENTINEL_SPEC`은 schema·golden conformance test를 가져야 한다.|6개 저장소의 전체 test와 격리 설치·conformance 명령을 실행한다.|
|요구사항-34|필수|5개 실행형 저장소 자체의 모든 production callable은 CRAP 8 이하이고 coverage N/A가 없어야 한다.|각 저장소에서 fresh coverage 기반 전체 CRAP gate를 실행한다.|
|요구사항-35|필수|5개 실행형 저장소는 자기 production 범위를 fresh strict mutation으로 검증하고 원격 CI를 통과해야 한다.|각 저장소의 전체 strict evidence와 최신 원격 CI 성공을 확인한다.|
|요구사항-36|필수|6개 저장소는 사용법, 지원 범위, 공통 결과·종료 코드·로그 계약, native CRAP 책임, mutation backend 책임, Robert Martin 방식에서 이어받은 부분과 확장한 부분을 설명해야 한다.|README와 specification의 필수 항목을 문서 검사와 사람 검토로 확인한다.|
|요구사항-37|필수|6개 저장소의 내부 지식 문서는 OKF v0.2 bundle이어야 한다.|각 docs에서 frontmatter, index.md, log.md, 링크, 한 파일 한 개념을 OKF lint로 검사한다.|
|요구사항-38|필수|`SENTINEL_SPEC`은 공통 CLI 의미, 결과·로그 schema, 종료 코드, 상태 분류, strict gate, fingerprint 의미와 privacy allowlist의 유일한 계약이어야 한다.|schema, golden fixture와 계약 version 검증을 실행한다.|
|요구사항-39|필수|`SENTINEL_GO`는 독립 설치·실행 가능한 Go CRAP·mutation 품질 게이트여야 한다.|깨끗한 Go 환경에서 설치 후 공통 CLI와 Go fixture를 실행한다.|
|요구사항-40|필수|`SENTINEL_JAVA`는 독립 설치·실행 가능한 Java CRAP·mutation 품질 게이트여야 한다.|깨끗한 Java 환경에서 설치 후 공통 CLI와 Java fixture를 실행한다.|
|요구사항-41|필수|`SENTINEL_CLJ`는 독립 설치·실행 가능한 Clojure CRAP·mutation 품질 게이트여야 한다.|깨끗한 Clojure 환경에서 설치 후 공통 CLI와 Clojure fixture를 실행한다.|
|요구사항-42|필수|5개 실행형 SENTINEL은 `crap`, `mutation`, `check`, `doctor`, `history`를 같은 의미로 제공해야 한다.|공통 CLI golden fixture를 각 언어에서 실행한다.|
|요구사항-43|필수|각 mutation backend의 이름, 정확한 version, artifact identity, operator inventory와 공통 상태 mapping을 검증·기록해야 한다.|backend·version·mapping 변경 시 증거와 compatibility 판정 변화를 검사한다.|
|요구사항-44|필수|5개 실행형 SENTINEL은 지정한 `SENTINEL_SPEC` version의 공통 conformance fixture를 통과해야 한다.|각 저장소의 결과·종료 코드·로그를 같은 golden fixture와 비교한다.|
|요구사항-45|필수|CRAP, mutation, 통합 check 명령마다 고유 실행 증거를 남기고 성공·품질 실패·baseline 실패·tool 오류·취소·불완전 상태를 구분해야 한다. 증거를 완결하지 못한 실행은 검증된 통과로 인정하면 안 된다.|각 terminal 상태와 비정상 종료 fixture가 별도 증거 또는 불완전 실행으로 조회되고 증거 write 실패가 통과하지 않는지 검사한다.|
|요구사항-46|필수|요구사항-45에서 정한 각 품질 명령 실행은 고유 `runId`를 가지고, 최초 실패부터 수정·재실행·최종 해결까지의 작업 묶음은 별도 `correlationId`로 연결해야 한다.|같은 correlationId로 품질 명령을 3회 실행해 서로 다른 runId, 순서와 최종 상태를 검사한다.|
|요구사항-47|필수|Finding의 발견·지속·해결·재발은 append-only 구조화 이벤트로 추가하고 기존 이벤트와 완료된 실행 증거를 정상 명령이 덮어쓰면 안 된다.|재실행 전후 기존 event prefix와 완료 증거 hash가 같은지 검사한다.|
|요구사항-48|필수|Finding은 프로젝트 코드·테스트 문제, mutation backend 문제, SENTINEL 문제, 환경·설정·flaky 문제를 구분하고 발견·해결·재발 lifecycle을 표현해야 한다.|실패, 통과, 동일 실패가 이어지는 fixture의 분류와 lifecycle을 검사한다.|
|요구사항-49|필수|Finding은 versioned occurrence, context, family fingerprint를 제공해 같은 프로젝트 위치, 같은 backend 맥락, 프로젝트 비식별 문제 종류를 각각 구분해야 한다.|위치 이동은 occurrence, backend version 변경은 context, 다른 결함은 family 구분에 반영되고 같은 문제 family는 프로젝트 식별정보 없이 비교되는지 검사한다.|
|요구사항-50|필수|동일한 fingerprint 종류·version·값이 서로 다른 완료 runId에서 2회 이상 관측될 때만 반복으로 세고, `history`는 현재 프로젝트의 횟수, 최초·최근 발견, 영향받은 실행과 현재 상태를 네트워크 없이 보여줘야 한다.|같은 종류·version·값, 다른 version, 같은 run retry가 섞인 fixture와 offline history를 검사한다.|
|요구사항-51|필수|실행 증거와 이력의 소유권, 보존 기간, 접근 권한, 만료된 실행 묶음 삭제는 검사받는 프로젝트와 CI 정책이 결정하며 보존 중인 기록은 수정하지 않아야 한다.|서로 다른 보존 정책과 만료 삭제 fixture에서 보존 중 기록 불변을 검사한다.|
|요구사항-52|필수|공용 증거·finding·history·export·기본 CI artifact에는 소스·mutant 원문, 비밀·환경 변수 값, 절대 경로, 저장소 URL·사용자명, raw stdout·stderr·stack trace를 포함하면 안 된다.|각 금지값 canary를 넣고 공용 산출물 전체 byte scan이 0건인지 검사한다.|
|요구사항-53|필수|Raw backend report는 기본 이력·export·CI artifact에서 제외하고 필요할 때만 프로젝트가 접근 제한 자료로 별도 보관해야 한다.|기본 산출물에는 raw report가 없고 명시적 project 보관에서만 생성되는지 검사한다.|
|요구사항-54|필수|Redacted export는 allowlist field만 담은 로컬 파일을 만들고 자동 네트워크 전송을 하지 않으며 export 실패가 기존 품질 판정을 바꾸면 안 된다.|network 차단 환경과 export 실패 fixture에서 품질 결과 불변을 검사한다.|
|요구사항-55|필수|한 저장소에 여러 지원 언어가 있으면 repository 이름이 아니라 설정된 production module별 언어·범위·test command로 각 SENTINEL을 실행해야 한다.|Python·TypeScript가 함께 있는 fixture에서 두 언어 범위와 test가 각각 검사되는지 확인한다.|

## 5. 범위 밖

- v1에서는 Python·TypeScript·Go·Java·Clojure 외 언어의 빈 저장소를 미리 만들지 않는다. 새 언어는 coverage와 mutation backend가 확인된 뒤 `SENTINEL_<LANG_ID>` 규칙으로 추가한다.
- v1에서는 mutation 엔진 자체를 새로 구현하지 않는다. 확인된 backend 결함은 이력으로 수집한 뒤 반복 근거가 있을 때 adapter 보정, plugin, backend 교체 또는 자체 구현을 별도 결정한다.
- v1에는 `SENTINEL_HUB`, 중앙 DB·서버·dashboard, telemetry, 자동 업로드, cross-project 자동 집계를 포함하지 않는다.
- Raw backend report를 공통 이력, redacted export 또는 기본 CI artifact로 모으지 않는다.
- 기존 application 저장소나 SwarmForge에 5개 SENTINEL을 실제 연결하는 작업은 6개 저장소 구현 이후 별도 작업으로 둔다.
- test source와 generated source를 mutation하지 않는다.
- package registry 공개 배포와 GitHub public 전환은 하지 않는다.
- 원본 Robert Martin 저장소의 기존 구현·history·remote는 바꾸지 않는다.

## 6. 미해결 항목

없음.

## 7. PRD 원문 대조

|ID|PRD 원문|정제문|바꾼 이유|
|---|---|---|---|
|공통규칙-01|“로버트 마틴의 방법으로 4개 테스트 레포 구현”|“`SENTINEL_SPEC`과 `SENTINEL_PY`, `SENTINEL_TS`, `SENTINEL_GO`, `SENTINEL_JAVA`, `SENTINEL_CLJ`를 구현한다.”|후속 승인에서 언어별 이름, Go·Java·Clojure 추가와 공통 계약 저장소가 확정됐다.|
|공통규칙-02|“로버트 마틴은 mutmut·StrykerJS 같은 라이브러리를 아예 안 썼어?”|“v1은 검증된 언어별 mutation backend를 wrapper로 사용하고 SENTINEL이 공통 판정을 소유한다.”|목표는 mutation 엔진 복제가 아니라 모든 하네스에서 재현되는 엄격한 품질 계약이다.|
|공통규칙-03|“CRAP 8 이하와 mutation 100% 이상으로 검증”|“CRAP raw 값은 최대 8.0 이하이고 모든 in-scope mutant가 killed일 때만 통과한다.”|100% 표시만으로 timeout·uncovered·ignored를 숨길 수 없도록 성공 조건을 상태 단위로 고정했다.|
|공통규칙-04|“swam forge 뿐만 아니라 앞으로 코딩시 다른 하네스에서도 사용할 테스터기”|“SwarmForge, 다른 코딩 하네스, 사람과 CI가 같은 독립 CLI를 사용한다.”|오타를 바로잡고 특정 하네스에 종속되지 않는 요구를 명확히 했다.|
|공통규칙-05|“내 github 에 비공개로 레포”|“인증된 GitHub 계정 `hwain-ai`에 6개 비공개 저장소를 만든다.”|저장소 수와 소유 계정을 후속 승인에 맞춰 고정했다.|
|요구사항-30|“mutation 100% 이상”|“strict kill rate는 killed를 전체 in-scope mutant 수로 나누며 mutant 0개는 통과하지 않는다.”|timeout을 killed처럼 계산하거나 빈 검사로 100%가 되는 거짓 통과를 막는다.|
|요구사항-38..요구사항-44|“다른 언어들도 이런 식으로 다 추가해”|“확인된 5개 언어와 `SENTINEL_SPEC`을 구현하고 같은 CLI·계약으로 conformance를 검증한다.”|빈 미래 언어 저장소를 양산하지 않고 실제 backend가 확인된 언어만 v1 범위로 확정했다.|
|요구사항-45..요구사항-54|“반복적인 결함이 발견되는지 알려면 뭔가 로그를 남기도록 만들어야 할 것 같다.”|“실행별 증거, append-only finding event, 3종 fingerprint, 프로젝트 로컬 history와 redacted export를 제공한다.”|반복 결함을 재현 가능하게 세면서도 소스·비밀·저장소 식별정보가 중앙으로 새지 않게 했다.|
|요구사항-55|“다른 언어들도 이런 식으로 다 추가해”|“다중 언어 저장소는 repository 이름이 아니라 module별 언어·범위·test command로 실행한다.”|실제 application 저장소가 여러 언어를 함께 가질 때 잘못된 단일 언어 판정을 막는다.|

## 변경이력

- 2026-08-31 | 제품 요구사항 최초 작성 | 변경: 승인된 네이티브 설계와 mutation 100%·범용 하네스 요구를 9개 공통규칙과 36개 요구사항으로 분해 | 검증: 원문 대조, 요구사항 ID 연속성, 성공 기준 대응 자기 검토
- 2026-08-31 | 제품 요구사항 승인 | 변경: 상태를 `approved`로 전환 | 검증: 사용자 승인 응답 확인
- 2026-08-31 | OKF 문서 규칙 추가 | 변경: 공통규칙-10과 요구사항-37 추가 | 검증: 사용자 `$okf` 명시 요청 및 OKF v0.2 규칙 대조
- 2026-08-31 | Mutation 100% 판정 강화 | 변경: timeout을 성공 분자에만 의존하지 않고 최종 gate에서 timedOut 0과 killed 100%를 추가 | 검증: 전 mutant timeout이 100%로 오인되는 반례 대조
- 2026-09-02 | SENTINEL 제품 방향 승인 반영 | 변경: 기존 4개 자체 엔진을 `SENTINEL_SPEC`과 5개 언어별 품질 게이트로 대체하고, mutation backend wrapper, strict killed-only gate, 프로젝트 소유 결함 이력·fingerprint·privacy 요구사항을 추가 | 검증: 요구사항-01..55 연속성, 공통규칙-01..10, 성공 기준 대응, 기존 번호 보존, 범위 밖과 사용자 승인 내용 대조
- 2026-09-02 | SENTINEL 제품 요구사항 승인 | 변경: 55개 요구사항과 10개 공통규칙의 상태를 `approved`로 전환 | 검증: 사용자 승인 응답 확인
- 2026-09-02 | 승인 실행계획 연결 | 변경: 활성 exec-plan을 related에 추가해 spec에서 구현 작업으로 이동하는 경로를 고정 | 검증: 상대 경로 존재와 plan의 spec 역참조 확인
- 2026-09-03 | 쉬운 설명 추가 | 변경: 문서 앞에 한 문장 결론, 용어 풀이, 실제 입력부터 출력까지의 순서와 읽는 순서를 추가 | 검증: 요구사항 표 55개 ID의 연속성·고유성과 기존 내용 보존 확인
