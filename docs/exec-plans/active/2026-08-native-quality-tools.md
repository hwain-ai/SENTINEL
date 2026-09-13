---
type: exec-plan
slug: native-quality-tools
created: 2026-09-02
updated: 2026-09-03
status: active
owner: Codex
spec: docs/product-specs/2026-08-native-quality-tools.md
design: docs/design-docs/2026-08-native-quality-tools.md
covers: 요구사항-01..요구사항-55
related:
  - docs/exec-plans/traceability.md
---

# SENTINEL 다언어 품질 게이트 실행 계획

한마디 요약: 이 문서는 여섯 SENTINEL 저장소를 안전하게 만들고, 다섯 언어 도구가 자기 코드에서 CRAP 8 이하와 mutation 100%를 실제로 증명한 뒤 비공개로 배포하는 순서를 정한다.

### 먼저 알아둘 말

|용어|쉬운 뜻|
|---|---|
|CRAP|함수가 복잡한데 test coverage도 낮은지를 함께 나타내는 코드 위험도 점수다. 이 계획에서는 반올림 전 8.0 이하만 통과한다.|
|mutation test|코드를 일부러 조금 바꾼 mutant(인위적 결함)를 test가 찾아내는지 검사하는 방법이다.|
|killed|넣어 둔 인위적 결함을 test가 실패로 잡았다는 뜻이다.|
|backend|mutant를 실제로 만들고 test를 실행하는 외부 도구다. SENTINEL은 backend 결과를 그대로 믿지 않고 다시 검증한다.|
|strict|일부 파일이나 cache 결과가 아니라, 승인된 production 범위 전체를 새 상태에서 검사하는 인증 mode다.|
|RED / GREEN|RED는 필요한 기능이 아직 없어서 올바른 이유로 test가 실패한 상태이고, GREEN은 최소 구현 뒤 같은 test가 통과한 상태다.|
|receipt(영수증)|어떤 입력과 결과를 검증했는지 파일 경로·해시·commit으로 고정한 기록이다.|
|SHA-256|파일 bytes가 바뀌었는지 확인하는 64자리 식별값이다. 같은 bytes만 같은 값이 나온다.|
|exact|대충 같음이 아니라 경로·순서·bytes·상태가 모두 정확히 같다는 뜻이다.|
|CAS|현재 값이 예상한 이전 값과 같을 때만 새 값으로 바꾸는 충돌 방지 방식이다.|
|owning child repository|해당 파일을 실제로 소유하는 `SENTINEL_*` 하위 Git 저장소다. workspace root는 Git 저장소가 아니다.|

### 이 문서를 읽고 실행하는 순서

1. **입력 고정:** 각 task의 `받는 것`, 시작 commit과 파일 목록을 확인한다.
2. **RED 확인:** 먼저 실패 test를 실행하고, 단순 설치 실패가 아니라 아직 없는 production 동작 때문에 실패했는지 확인한다.
3. **최소 구현:** 그 실패만 통과시키는 코드를 작성한다.
4. **전체 검증:** 정상·오류·중단·재실행 fixture와 이전 기능 전체를 다시 실행한다.
5. **원자 commit:** 준비 영수증과 바로 이전 task의 완료 영수증이 모두 맞을 때만 commit한다.
6. **다음 task 전달:** `주는 것`과 완료 영수증을 다음 task의 입력으로 넘긴다.

각 명령의 `<NAME>`은 실행 중 앞 단계가 출력한 실제 값으로 바꿀 자리다. 예를 들어 `<PREPARED_RECEIPT>`에는 staging command가 출력한 영수증 절대 경로를 넣고 `<PREPARED_RECEIPT_SHA256>`에는 같은 파일의 SHA-256을 넣는다. 예시 값을 임의로 만들어 넣으면 안 된다.

여기서 predecessor(선행 작업)는 문서상 바로 앞 번호가 아니라 **같은 저장소의 현재 변경이 실제로 이어받는 완료 상태**다. 아래 표에서 영수증 출처를 찾고, 선행 command stdout이 출력한 path와 SHA-256을 한 쌍으로 그대로 넘긴다.

|현재 저장소·phase|반드시 받는 predecessor 영수증|
|---|---|
|SPEC T01 `foundation`|없음. 새 Git root를 만드는 유일한 `unborn-bootstrap`이다.|
|PY·TS·GO·JAVA·CLJ T01 `foundation`|Git predecessor는 없음. 다만 먼저 끝난 SPEC T01 `foundation-seal`로 registry와 tool을 검증해야 한다.|
|SPEC T02 `contracts` → T03 `evidence-contracts` → T04 `rc-bundle`|같은 화살표의 바로 왼쪽 phase가 출력한 committed receipt|
|PY T05 `foundation` → T06 `crap` → T07 `admission`|PY T01부터 같은 화살표의 바로 왼쪽 committed receipt|
|PY T07 `mutation-adoption`|선택 checkout의 T07 `admission` committed receipt와 primary PY T06 committed receipt 둘 다|
|PY T07 `coverage-join` → T08 `evidence`|coverage-join은 `import-verify`의 committed-equivalent adoption receipt, T08은 coverage-join committed receipt|
|TS T09 `foundation` → T10 `crap` → T11 `admission` → T11 `coverage-join` → T12 `evidence`|TS T01부터 같은 화살표의 바로 왼쪽 committed receipt|
|GO T13 `foundation` → T14 `crap` → T15 `runner-admission` → T15 `mutation-admission` → T16 `evidence`|GO T01부터 같은 화살표의 바로 왼쪽 committed receipt|
|JAVA T17 `foundation` → T18 `crap` → T19 `mutation-admission` → T20 `evidence`|JAVA T01부터 같은 화살표의 바로 왼쪽 committed receipt|
|CLJ T21 `foundation` → T22 `crap` → T23 `mutation-admission` → T24 `evidence`|CLJ T01부터 같은 화살표의 바로 왼쪽 committed receipt|
|각 저장소 T25|SPEC은 T04, PY는 T08, TS는 T12, GO는 T16, JAVA는 T20, CLJ는 T24의 committed receipt|
|각 저장소 T26 → T27 → T28|같은 저장소 T25부터 같은 화살표의 바로 왼쪽 committed receipt 또는 그 task의 sealed committed-equivalent receipt|
|SPEC T29 `spec-candidate`, runtime T29 `runtime-candidate`|같은 저장소 T28 committed receipt와 T29 allocation attempt receipt 둘 다|
|각 저장소 T29 `release-tag`|보호 PR merge 뒤 `adopt-merged-main`이 출력한 같은 저장소의 committed-equivalent receipt|

예를 들어 T05는 전역 직전 작업인 T04 영수증을 받지 않는다. `SENTINEL_PY` 안에서 바로 앞인 T01 Python foundation 영수증을 받는다. 잘못된 저장소·task·phase의 영수증은 path가 실재하고 SHA-256이 맞아도 거부된다.

### 코드 블록 공통 직역표

아래 표는 이 문서의 모든 코드 블록에 공통으로 적용한다. 각 block 바로 앞뒤의 `실행`, `기대`, 설명 문단이 입력과 출력의 뜻을 추가로 정한다.

|표기|직역|
|---|---|
|Bash의 `#!/usr/bin/bash`|이 파일을 검증된 Bash로 실행하라는 지정이다.|
|Bash의 `set -euo pipefail`|실패, 정의되지 않은 변수, pipe 안의 실패를 숨기지 말라는 설정이다.|
|Bash의 `test`, `&&`|조건을 검사하고, 앞 명령이 성공했을 때만 다음 명령을 실행한다.|
|Python의 `def`, `class`, `return`, `raise`, `with`|함수 정의, 자료형 정의, 결과 반환, 오류 발생, 자원 범위 지정이다.|
|Python의 `@dataclass`, `frozen=True`|자료 묶음임을 선언하고 생성 뒤 값 변경을 막는다.|
|TypeScript의 `export`, `interface`, `readonly`, `const`, `async`, `await`, `throw`|외부 공개, 형태 계약, 변경 금지, 한 번 정한 변수, 비동기 함수, 완료 대기, 오류 발생이다.|
|Go의 `func`, `type`, `struct`, `error`, `return`, `defer`|함수, 새 자료형, 자료 묶음, 오류 값, 결과 반환, 함수 종료 때 실행이다.|
|Java의 `public`, `class`, `interface`, `record`, `void`, `new`, `throws`|외부 공개, 구현 자료형, 동작 계약, 불변 자료 묶음, 반환값 없음, 객체 생성, 오류 가능성 선언이다.|
|Clojure의 `defn`, `deftest`, `let`, `is`, `fn`|함수 정의, test 정의, 지역값 지정, 참인지 검사, 익명 함수다.|
|`assert`, `expect`, `assertEquals`, `is`|실제 결과가 기대값과 같은지 검사하며, 다르면 test를 실패시킨다.|

아래 표는 반복해서 나오는 나머지 문법을 직역한다. 각 코드 블록의 별도 표는 이 공통 문법에 실제 이름과 값을 대입해 입력, 판정, 출력을 설명한다.

|언어·표기|직역|
|---|---|
|공통의 `name = value`와 `name: Type`|왼쪽 이름에 오른쪽 값을 넣고, 콜론 뒤에는 그 값이 가져야 할 자료형을 적는다.|
|공통의 `name(...)`, `object.member`, `object[index]`|함수를 호출하고, 객체의 구성원에 접근하고, 순서나 key로 한 항목을 꺼낸다.|
|공통의 `==`, `!=`, `<`, `<=`, `>`, `>=`|같음, 다름, 작음, 작거나 같음, 큼, 크거나 같음을 판정한다.|
|공통의 `+`, `-`, `*`, `/`, `%`, `**`|더하기, 빼기, 곱하기, 나누기, 나머지, 거듭제곱을 계산한다.|
|공통의 `true`·`True`, `false`·`False`, `nil`·`None`|참, 거짓, 값 없음을 나타내는 literal(코드에 직접 적은 값)이다.|
|Bash의 `NAME=value`, `$NAME`, `"..."`, `$(command)`|환경·shell 변수에 값을 넣고, 그 값을 꺼내고, 공백을 포함한 하나의 값으로 보존하고, 안쪽 명령의 stdout을 값으로 받는다.|
|Bash의 `!`, `|`, `||`, `--`|판정을 뒤집고, 앞 명령 출력을 뒤 명령 입력으로 보내고, 앞 명령 실패 때 다음 명령을 실행하고, option 목록의 끝을 표시한다.|
|Bash의 `-z`, `-f`, `-e`, `-q`|문자열이 비었는지, 일반 file인지, 경로가 존재하는지, 성공·실패만 조용히 확인한다.|
|Bash의 `command --name value`|`command`를 실행하면서 `--name` option에 바로 뒤의 값을 입력한다. Exit code 0은 성공, 0이 아니면 실패다.|
|Python의 `from`·`import`, `if`, `for`·`in`, `not`, `is`, `and`·`or`|다른 module에서 이름을 가져오고, 조건을 검사하고, 항목을 순회하고, 판정을 뒤집고, 동일한 singleton인지 보고, 모든 조건·하나 이상의 조건을 결합한다.|
|Python의 `[]`, `{}`, `()`, `[x for x in y]`, `{x for x in y}`|list, dictionary 또는 set, tuple·호출 경계를 만들고, 순회 결과로 list나 set을 만든다. 문맥에 따라 빈 `{}`는 dictionary다.|
|Python의 `->`, `|`, `...`, `//`, `b"..."`, `f"..."`|반환형, 둘 중 한 자료형, 생략한 구현, 나머지를 버린 정수 나눗셈, byte literal, 값을 끼워 넣는 문자열을 뜻한다.|
|JSON의 `{}`, `[]`, `"key": value`, `,`|object, array, key와 값의 연결, 다음 항목이 이어짐을 뜻한다. JSON block에는 comment를 넣을 수 없어 바로 뒤 표에서 각 key를 설명한다.|
|TypeScript의 `function`, `let`, `if`, `while`, `implements`, `private`, `new`|함수 정의, 바꿀 수 있는 변수, 조건 분기, 조건 반복, 계약 구현, class 내부 전용 구성원, 새 객체 생성을 뜻한다.|
|TypeScript의 `() =>`, `?`, postfix `!`, `[]`, `{}`, `<T>`, `Promise<T>`|익명 함수, 선택 입력·구성원, 값이 없지 않다는 개발자 단언, array, object, generic 자료형, 나중에 끝나는 작업의 결과형을 뜻한다.|
|TypeScript의 `===`, `!==`, `&&`, `||`, `!`, `%`, `**`, `/=`|자료형까지 같은지·다른지, 두 조건·한 조건, 판정 반전, 나머지, 거듭제곱, 나눈 값을 같은 변수에 다시 넣음을 뜻한다. 숫자 뒤 `n`은 정확한 큰 정수인 `bigint` literal이다.|
|Go의 `:=`, `[]T`, `T{}`, `*T`, `_`, `nil`, `if`|새 지역 변수 지정, T의 slice, T의 빈 값, T를 가리키는 pointer, 쓰지 않을 결과, 값 없음, 조건 분기를 뜻한다.|
|Go의 `(s *Store)`, `pkg.Name`, `&&`, `||`, `!`|`Store` pointer에 붙은 method receiver, package의 공개 이름, 모든 조건·한 조건·판정 반전을 뜻한다.|
|Java의 `@Test`, `Type name = value`, `Type<T>`, `CONSTANT`, `;`|test method 표시, 지정 자료형 변수 생성, generic 자료형, 바뀌지 않는 상수 이름, 한 명령의 끝을 뜻한다.|
|Clojure의 `(name args...)`, `[name value]`, `:name`, `#(...)`|함수 호출, `let` 안 이름·값 묶음, keyword key·상태 값, 짧게 쓴 익명 함수를 뜻한다.|
|Clojure의 `=`, `not=`, `zero?`, `true?`, `false?`, `not`, `17/4`|같음, 다름, 0인지, 참인지, 거짓인지, 판정 반전, 정확한 4분의 17 ratio를 뜻한다.|

반복되는 staging·commit 명령은 다음처럼 읽는다.

|명령·option|직역|
|---|---|
|`run-spec-python.sh <tool.py> ...`|SENTINEL_SPEC에 고정된 Python으로 뒤의 tool을 실행한다.|
|`prepare-and-stage`|registry가 허용한 변경만 검사해 temporary tree와 prepared receipt를 만들고 real Git index에 정확히 게시한다.|
|`materialize-exact`|commit fixture의 selector가 가리키는 concrete path 목록을 NUL 구분 `stage.paths`로 만든다.|
|`stage-exact`|바로 앞 `stage.paths`의 경로·mode·bytes만 stage하고 prepared receipt를 만든다.|
|`commit-prepared`|prepared receipt, 현재 HEAD, predecessor receipt가 모두 맞을 때만 지정 message로 commit한다.|
|`import-prepare`·`import-resume`·`import-verify`|격리 checkout의 검증된 commit을 가져올 intent를 만들고, 중단 가능하게 적용하고, 최종 상태와 adoption receipt를 검증한다.|
|`tag-prepared`|검증된 committed receipt가 가리키는 commit에 annotated tag를 원자적으로 만든다.|
|`vendor_upstream.py`|고정 upstream commit의 tracked archive를 검증해 비어 있는 `third_party` 목적지에 안전하게 복사한다.|
|`--repository .`·`--logical-repository NAME`|현재 directory를 물리 저장소로 쓰고, 격리 checkout에서도 논리 저장소 이름은 `NAME`으로 고정한다.|
|`--task TNN`·`--phase NAME`|registry에서 사용할 task와 그 task 안의 commit 단계를 고른다.|
|`--base-head OID`·`--expected-base OID`|현재 작업이 시작해야 하는 정확한 이전 commit을 입력한다.|
|`--predecessor-receipt PATH`와 `--predecessor-receipt-sha256 HASH`|바로 앞 허용 단계의 완료 영수증 경로와 그 file bytes의 SHA-256을 한 쌍으로 입력한다.|
|`--prepared-receipt PATH`와 `--prepared-receipt-sha256 HASH`|stage 단계가 출력한 준비 영수증 경로와 SHA-256을 한 쌍으로 입력한다.|
|`--source PATH`·`--selector NAME`·`--manifest PATH`|고정 path fixture, 그 안의 분기 이름, materialize 결과 path 목록을 차례로 입력한다.|
|`--output PATH`·`--output-root PATH`|생성할 단일 결과 file 또는 attempt 묶음을 둘 VCS 밖 directory를 지정한다.|
|`--expected-message TEXT`|생성할 commit이나 tag가 가져야 할 정확한 사람이 읽는 설명을 지정한다.|
|`--` 뒤 path 목록|option 해석을 끝내고, registry 변경 목록과 교차 검사할 사람이 읽는 책임 경계를 전달한다.|

**목표:** 공통 계약 저장소 1개와 Python·TypeScript·Go·Java·Clojure 실행 저장소 5개를 구현하고, 각 실행 도구가 native CRAP 8.0 이하와 모든 in-scope mutant killed를 독립 CLI·증거·이력으로 검증하게 한다.

**접근:** 먼저 `SENTINEL_SPEC` 사전판으로 언어 사이 계약을 고정한다. 다음으로 mutmut, Stryker plan event와 Go typed runner처럼 실패 비용이 큰 backend 경계를 먼저 입장 시험한다. Python과 Go를 end-to-end로 완성해 쉬운 CLI와 가장 어려운 실행 안전성을 함께 검증한 뒤 TypeScript, Java, Clojure를 같은 계약에 맞춘다.

**기술:** JSON Schema 2020-12, SemVer, CPython 3.12.13·pytest 9.1.1·coverage.py 7.16.0·mutmut 3.7.0·PyNaCl 1.6.2, Node.js 22.23.1·TypeScript 7.0.2·Vitest·coverage-v8 4.1.11·StrykerJS 10.0.0, Go 1.27.1·mutate4go 고정 commit, Temurin JDK 17.0.20.1+1·Maven 3.9.16·JUnit 5.10.2·JaCoCo 0.8.12·mutate4java 고정 commit, Clojure CLI 1.12.5.1664·Clojure 1.12.0·tools.reader 1.4.2·Cloverage 1.2.4·clj-mutate 고정 commit, JNA 5.17.0과 Linux POSIX `fcntl`, GitHub Actions, CPython 표준 HTTPS transport.

## 공통규칙

아래 규칙은 모든 작업에 예외 없이 적용한다.

|번호|규칙|
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

---

## 범위와 완료 경계

이 계획은 6개 저장소의 로컬 구현, private GitHub 생성, CI, 1.0.0 release까지 포함한다. 기존 application 저장소와 `upstream/unclebob/swarm-forge`의 실제 수정은 포함하지 않는다. 6개 release가 끝나면 별도 product-spec과 exec-plan으로 SwarmForge와 application 연결을 승인받는다.

완료는 다음 사실을 모두 증명해야 한다.

1. 6개 저장소가 `hwain-ai` 계정의 private repo이고 default branch는 `main`이다.
2. 5개 실행형 저장소가 동일한 고정 `SENTINEL_SPEC` 1.0.0 bundle을 vendor한다.
3. 각 실행형 저장소의 clean install, unit, integration, acceptance, conformance가 통과한다.
4. 각 실행형 저장소 자신의 fresh CRAP은 모든 production callable이 8.0 이하이고 unknown이 0이다.
5. 각 실행형 저장소 자신의 fresh mutation은 mutant가 1개 이상이고 전부 killed이며 다른 상태가 0이다.
6. 공용 결과와 CI artifact의 privacy canary byte scan이 0건이다.
7. 각 private remote의 CI가 성공하고 local HEAD, remote `main`, release tag가 같은 commit이다.
8. 기존 upstream 7개 child repository의 고정 commit과 `.git/**` 제외 whole-tree path·type·mode·content digest가 T01 기준과 같다.

## 작업 전 고정 기준

|자료|고정 기준|
|---|---|
|`crap4clj`|`e068673a852a8142323ac680fa3366de65bc2227`|
|`clj-mutate`|`e27dd5df63c4efdd66438587d1c5f49e73661b69`|
|`crap4go`|`bee16dbdadb4af927a7792083f3cba2ae58841ed`|
|`mutate4go`|`9016c7adafc1c7e282b5e27768e732e477713af8`|
|`crap4java`|`69b561209f130ece728f19b0001e90df5a117c3a`|
|`mutate4java`|`7b05fdd71e8fe36327aff837806dfbff86af0572`|
|`swarm-forge`|`95e95e4a2fecace23078aac40e33158ce9040f21`|
|uv bootstrap|0.12.9 Linux x86_64 archive SHA-256 `ec7a99cd05e0cd7f80243f135ce1361c76835cb0ee60055d14d20eba8eba1460`|
|CPython managed runtime|3.12.13 python-build-standalone `20260807` Linux x86_64 install-only-stripped archive SHA-256 `506191be3ee7bd190a8834dcdc1b3bc70aab50608deccc711935aa007239cabd`|
|pytest wheel|9.1.1, SHA-256 `37a86b45efb9a47a61a36449063e8e18d0cab3161329fc099eb21783169c4f0c`|
|mutmut wheel|3.7.0, SHA-256 `1d2f9a1bfa4a474b2213df6b17223150b492bf4a85af0eda4fb322297337fb32`|
|PyNaCl wheel|1.6.2 CPython abi3 manylinux2014 x86_64, SHA-256 `22de65bb9010a725b0dac248f353bb072969c94fa8d6b1f34b87d7953cf7bbe4`|
|Cosmic Ray fallback wheel|8.7.0, SHA-256 `759510a02cf2b23ba15a00680ecc1fd6c74d3082622e5a7d2d514b5227267659`|
|coverage.py wheel|7.16.0 CPython 3.12 Linux x86_64, SHA-256 `719a3feb6220dd32ed932d4c3676d17fb8739e2643b29c0e7c3af400ff80ac44`|
|Node.js runtime|22.23.1 Linux x64 archive SHA-256 `9749e988f437343b7fa832c69ded82a312e41a03116d766797ac14f6f9eee578`|
|TypeScript compiler|7.0.2, integrity `sha512-8FYau96o3NKOhbjKi/qNvG/W5jhzxkbdm5sj9AbZ/5T5sWqn3hJgLfGx27sRKZWTvyzCP8dLRBTf5tBTSRVUNA==`|
|Vitest runner|4.1.11, integrity `sha512-fhACrNXUidIbGSBr5FlbuBkO7VWC1ZyLl0DO4CU2DrQoAPxX84Ysxs+HeGQpii5lZWV1Q4gBZTTu49mF+A6Edw==`|
|Stryker core|10.0.0, integrity `sha512-ZvMsRyaXQQ5e6Thcid9pkuODv6Fn9E3nrBQJUap+hcJuGJ4unm26afo3m6YKSjn8kinyxJ/3TXf0cTWRDaTxVw==`|
|Stryker Vitest runner|10.0.0, integrity `sha512-SHK2/vfvRUpiz7jXPnQMBnr6zLdm69DK03Mo5mPhaZWcRSygrKUqYsPqWsXsK+5ySHzlMTfCyFK5NQ/X9sJFFw==`|
|Vitest coverage-v8|4.1.11, integrity `sha512-8MVGEFnJIcdGjcbfKmeq8z0pZHH0JlVtoVZH9Q/qwUp6wyFnEJUBMrw9DCaj+ra3vShGmhavjalMIhPNxZAUcw==`|
|TypeScript libc FFI|Koffi 3.1.6, integrity `sha512-ln60chEb3o7Du1ayjwl6BFiNN1wZK+3cTM2wWGiHLEzCY/FdTIN1ER5VWDwHq7J/j4tSnnrHaH5ABS1EO6+6ag==`|
|Go toolchain|1.27.1 Linux amd64 archive SHA-256 `63d339f0da5ab53635a56f2490a7984dfe12dfcff22ad749f63edaf590168445`|
|Go POSIX syscall|`golang.org/x/sys` v0.36.0, exact module·go.mod checksum은 `go.sum`에서 검증|
|Temurin JDK|17.0.20.1+1 Linux x64 archive SHA-256 `3808d1d15e3ec6bd5b84057fb5d84c33d8a1536a258146bcea2e603fc726e08e`|
|Apache Maven|3.9.16 Linux archive SHA-256 `fca22aed9e8b9713a232f3394fd81d7f20322df75efdb2b047dbd3e3a23bb`|
|Java test·coverage|JUnit 5.10.2, Surefire·Failsafe 3.2.5, JaCoCo 0.8.12|
|Java JSON·packaging|Jackson BOM·databind 2.22.2, Maven Shade Plugin 3.6.2|
|Java·Clojure libc FFI|JNA 5.17.0, JAR와 packaged Linux x86_64 native dispatch artifact를 dependency lock에서 exact 검증|
|Clojure CLI|1.12.5.1664 archive SHA-256 `77dd6868948074adcc93e83a796f8e8f15a1a92bcb1b9002d715fd2210e476f3`|
|Clojure runtime·analysis|Clojure 1.12.0, data.json 2.5.1, tools.reader 1.4.2, Cloverage 1.2.4|
|Clojure packaging|tools.build 0.10.14|
|CI·clean-install userspace|`docker.io/library/ubuntu@sha256:1e0a86e57d247923571b75e0aaf48a1449cf8c543d51fb3e07a4a7d7bfa79316`, Ubuntu 24.04 Linux amd64 manifest|
|Local OCI executor|absolute `/usr/bin/docker`, binary SHA-256 `c0b4d78635d4e2171a36fcfa1cdee696167ad87e2f7775220f95e7fcb024557a`, client 25.0.14 commit `0bab007`·API 1.44·Linux amd64, local Engine 25.0.16 commit `6fdf0a6`·API 1.44·Linux amd64, canonical Unix socket `/run/docker.sock`|

`.git/**`만 제외하고 path·type·POSIX mode·size·file SHA-256 또는 symlink target을 canonical JSON으로 만든 whole-tree 기준은 다음과 같다. Clone 격리 과정에서 이미 있던 untracked `.git_remote_origin_backup`과 `LICENSE`도 포함하므로 새 untracked file을 숨길 수 없다.

|Upstream tree|행 수|Canonical SHA-256|
|---|---:|---|
|`clj-mutate`|38|`5a89dda8e9f19025c59ce29c196320fa7803a36db1889a8941bd9583009385a2`|
|`crap4clj`|24|`39b7f2a842f28f804dbbae7845be0686f445739eb80c94f0fb28c2b320c4e84c`|
|`crap4go`|23|`ada0f6e68feac96bbc5f5986acf13a886ca8b4dd3d0024344dfb6f3601678b3a`|
|`crap4java`|40|`1e0a2efde1a2a13b484360bf5558707f2032454f426e1cb14dbdbfaa9c3972d7`|
|`mutate4go`|27|`1f16766721061c191cd85c7438fffcf81befef04080a643ad002ccc3ac4a40c8`|
|`mutate4java`|134|`69808c7da8985e8090fba338533f6420bb88ef7078ceba27e435eff4b41b0fc0`|
|`swarm-forge`|83|`ab8426305fa60da962fa1d1bcc2c9df3d9716879f28168ae31107964afecdc1d`|

Git metadata는 working tree와 별도 기준으로 고정한다. Ref digest는 `git show-ref --head -d`의 bytewise 정렬 결과, object digest는 `git cat-file --batch-check='%(objectname) %(objecttype) %(objectsize)' --batch-all-objects`의 bytewise 정렬 결과다. Reflog digest는 `.git/logs/**` regular file의 relative path·mode·size·content SHA-256 tuple을 bytewise 정렬한 manifest다. Config는 `.git/config` raw byte이고 shallow는 `.git/shallow` raw byte다. 모든 repo의 remote config·remote ref는 0개다.

|Upstream Git|HEAD symref|Ref 수·digest|Object 수·digest|Config digest|Shallow digest|Reflog digest|
|---|---|---|---|---|---|---|
|`clj-mutate`|`refs/heads/master`|2 · `483cb695f5125553cae8944c8df2f17849ec86a7e95e799c1d192fcbf52be187`|38 · `01e468a6216c7434c513b1c948d8983d89f87ed2fd6128d6d8eec674a2857494`|`cfe7ba1238c9a78be7535d7c63bcaf5a4d5011d46b07c9b45d3bbf7d6c312dfe`|`9803c558efe9c0f9511e5c273d66f4de7c8610661ad1110e5c65c3d0b8b00daf`|`21da4b40e16a6163a6556c7d8c0f22c5415ab120c7c819bc6d1a67dcb03fef9d`|
|`crap4clj`|`refs/heads/master`|2 · `8ba5cc1c7f7e00c0d747c9279199343b15b681d729b8dca2e7308e24462d9977`|24 · `2434381d2fd9c38ac705c2bf32feb7eb67c4fb168ccd0c5d45aab191044cfcbe`|`cfe7ba1238c9a78be7535d7c63bcaf5a4d5011d46b07c9b45d3bbf7d6c312dfe`|`757bb97912966e5e2112e5b94417f8b4cd94aa6f96c57565f0fb9fc455cf3dd8`|`11a3b4fb498d197f17f5d6b8301954fa08529f9b6592888be67535620c960b0c`|
|`crap4go`|`refs/heads/master`|2 · `80f8c4b75e330f1f2cc9788adb508a5f1f2d2ed2320bd7a9fd58f0cc2f4e31fa`|23 · `c101b91fca265d5a1a6646a9c773de69c8e974ac3115801c5046e030fccc74bd`|`cfe7ba1238c9a78be7535d7c63bcaf5a4d5011d46b07c9b45d3bbf7d6c312dfe`|`1b865737b003fe412f3dedf9a6b4afca6495e35b2a5a07704e571a8c058a9e8b`|`481eaf94f73a9dff0e8867b4c897d3bdd45e8180aa0f44312840bc8d2cee05ad`|
|`crap4java`|`refs/heads/main`|2 · `c62ea1960283506b64e71a9139dfa47ee2fd60127f1b761aeb87ca43f5fc95b8`|40 · `873eeaa947b18a6180f29efa1a86c478124551240b9eeb5921a2bb860fa0346f`|`cfe7ba1238c9a78be7535d7c63bcaf5a4d5011d46b07c9b45d3bbf7d6c312dfe`|`6c1af08a0abec28eb3fcdf0e3ba91246062ec3d6b6a45fae3497fc4d7b5b0733`|`b081194e9dfd152c8f3e2348efde55e1a450f4ea9d15958ba0fc1b2c1fb9fd7e`|
|`mutate4go`|`refs/heads/master`|2 · `46d8348a7e0d0c10a81a01277e7ebdaca2596dbe09823497302c4c2f8dd60d78`|27 · `c78bdd7ecdf19c6f2dc55de3ba2f240855ed067f483936eccae66fd2ba6b763f`|`cfe7ba1238c9a78be7535d7c63bcaf5a4d5011d46b07c9b45d3bbf7d6c312dfe`|`c0ed5e071c04e4f9a650e286871435570d2628280cca8b4a5ca4acabf4b8a14a`|`8ef4b9669aa0ad6d699be4a468f8f211dd490714f8b33f459e2b8b74b62c728b`|
|`mutate4java`|`refs/heads/main`|2 · `472ab02f13516b1eae2574647a3a84656b74c508a317e7cf8b522ce0fad0a567`|134 · `b0676056e2b903b1092ba24988fa96c47c8ee1a1bce13bfc695b57543e26116a`|`cfe7ba1238c9a78be7535d7c63bcaf5a4d5011d46b07c9b45d3bbf7d6c312dfe`|`cf0a1218ec102fcca215bfa32713d6a462185c7bed35bcd0218b6d67ff924b89`|`943c3bedfcf7c9fbf727c470d084ce57c69a01fb4ca48de9366afee0b7731569`|
|`swarm-forge`|`refs/heads/main`|2 · `ac88f131c1cb036545f282089e604758d25cbf6bbf32ef7114d47be059d902a6`|83 · `e131c4d148dee17bc618579ee64ed94ad1aae088acbd2528e4f7c3249dab5c55`|`cfe7ba1238c9a78be7535d7c63bcaf5a4d5011d46b07c9b45d3bbf7d6c312dfe`|`1e4c59c5c38386aefb12e9009c0f950225fb6097b1713fe471d2bcfb817955f9`|`8beb6ccadfb9ea8bc2c743cc4dfdfd8d41781ac413c65c6cddd2c66041c7c9dd`|

Robert mutation backend의 tracked `git archive --format=tar HEAD` 기준은 다음과 같다. Vendoring은 whole-tree 기준이 아니라 이 tracked archive byte와 안전 추출 manifest를 사용한다.

|Backend archive|Tar SHA-256|
|---|---|
|`mutate4go`|`4fae40e1568649edbeadc7f3a0a164b8a2d7ae0d464fb2d4d7ed006afee59215`|
|`mutate4java`|`762c4b91ef592fbd07dace1189626013b3935c0fa41407242c52ebb1ffdeb34f`|
|`clj-mutate`|`fcd0638e1b60a46779f28d778f542ad52858738bcde4b925cf1ce28db2eb5b5a`|

## 파일 구조와 책임

아래 tree는 책임 경계를 보여 주는 대표 구조다. 각 task의 **파일** 목록은 사람이 읽는 책임 범위다. Byte 단위 commit 기준은 T01에서 미리 작성하는 `tools/task_commit_paths.json`과, 조건부 분기가 있는 T04·T07·T11·T15·T19·T23·T25..T29의 별도 concrete path manifest다. 어느 task도 실행 중 발견한 file을 자기 allowlist로 승격하지 않으며 폴더나 glob을 실제 index에 바로 stage하지 않는다.

T01의 `commit_inventory.py`가 모든 일반 commit의 단일 staging 경계다. `tools/task_commit_paths.json`은 schema version과 `<TASK>/<LOGICAL_REPOSITORY>/<PHASE>` key별 entry를 담는다. `kind="fixed"` entry는 sorted concrete `paths` array를, `kind="selector"` entry는 same-task mirror의 exact `sourcePath`·`sourceSha256`과 selector key별 sorted concrete path array를 가진다. 각 entry는 허용 직전 단계 `predecessor={task,logicalRepository,phase}`도 하나 고정하고 T01 root만 null이다. T07·T11의 admission→coverage, T15의 runner→mutation과 언어별 직렬 task는 명시 DAG(선행 작업 연결표)로 고정한다. T01 foundation부터 T29까지 모든 planned phase와 조건부 branch를 첫 RED 전에 고정하며 directory, glob, duplicate, absolute path, `.`와 `..` component는 금지한다. Static test가 각 task의 파일 책임, known repository·phase, predecessor DAG, registry missing·extra와 실제 task command의 key를 대조한다. Bootstrap 순서는 SPEC root commit이 첫 번째이고 나머지 다섯 root commit이 뒤따른다. SPEC의 `--unborn-bootstrap`만 `commit_inventory.py` source에 고정한 `BOOTSTRAP_REGISTRY_SHA256`과 working registry canonical bytes를 exact join해 사용할 수 있다. SPEC root commit 직후 registry blob OID와 tool blob OID를 receipt에 봉인하며, 다른 다섯 root commit과 T02 이후 모든 mode는 exact SPEC T01 commit·registry blob OID를 요구한다. 계획 변경으로 path를 바꿔야 하면 source를 먼저 수정하지 않고 이 execution plan과 registry를 별도 승인·commit으로 갱신해 새 base를 봉인하며, 현재 task receipt를 재사용하지 않는다.

`prepare-and-stage`는 real index가 비어 있고 HEAD가 caller가 선언한 base와 같은지 먼저 확인한 뒤, VCS 밖 owner-only temporary index에서만 `--task`, logical repository와 `--phase`가 가리키는 registry array를 읽는다. Command 끝의 path root는 사람이 읽는 책임 범위 교차 검사에만 쓰며 allowlist를 만들지 않는다. Alternate index에서 계산한 actual changed set이 registry concrete set과 정확히 같아야 하고 missing·extra가 하나라도 있으면 real index mutation 0으로 거부한다. Symlink component, submodule, unmerged entry, task 책임 밖 path, ignored build output과 pre-existing staged change도 거부한다. 검증한 concrete regular-file path만 UTF-8 path byte 순서와 path마다 trailing NUL 한 개를 붙인 `stage.paths`로 고정하고, `blobs.json`에는 sorted `(path,mode,blobSha256)` array를 기록한다. Receipt bundle은 fixed phase directory에 직접 쓰지 않는다. Owner-only `build/commit-inventory/<TASK>/<REPOSITORY>/<PHASE>/attempts/<128-bit-random-hex>/`를 exclusive-create하고 각 file을 unique temp에 완전히 쓴 뒤 file sync, same-directory no-replace rename, directory sync한다. `receipt.json`을 마지막 durable marker로 게시하며 schema version, task, logical repository name, registry blob OID와 selected array digest, physical repository root identity, base HEAD, phase, target symbolic ref, path count, path-list SHA-256, blob-manifest SHA-256과 temporary tree OID를 기록한다. Incomplete attempt는 수정·삭제하지 않고 새 attempt를 할당한다. Complete exact attempt만 재실행에서 write 0으로 채택하며 command stdout은 exact `<PREPARED_RECEIPT_PATH> <PREPARED_RECEIPT_SHA256>` 두 field다.

Git invocation은 모든 mode에서 `GIT_CONFIG_NOSYSTEM=1`, `GIT_CONFIG_GLOBAL=/dev/null`, owner-only empty HOME·XDG와 exact local config allowlist를 강제한다. `.gitattributes`, `.git/info/attributes`, `filter.*`, external diff, hook, signing, replace object와 alternates는 허용하지 않는다. Tool은 opened working file bytes를 `/usr/bin/git hash-object -w --no-filters --stdin`과 alternate index `update-index --cacheinfo`로 넣고 porcelain `git add`를 호출하지 않는다. Target tree의 blob을 다시 읽어 opened source byte digest와 대조한다. Stage 뒤 검증이 실패해 구현을 고쳐야 할 때는 `abandon-stage`만 허용한다. 이 command는 expected base HEAD, prepared receipt와 real cached path·mode·blob·tree가 모두 exact하고 commit이 생기지 않았을 때만 baseline index를 아래 atomic protocol로 게시한다. Working tree는 바꾸지 않으며 current receipt bundle을 receipt whole-file digest 이름의 owner-only `abandoned/` child로 no-replace 보존하고 abandonment receipt를 file·directory sync한다.

Exact task의 각 phase는 임시 index가 발견한 목록을 allowlist로 승격하지 않는다. Task 본문이 지정한 VCS 밖 `*.paths`에 사람이 concrete file path를 하나씩 넣거나, 사람이 관리하는 committed exact-path JSON을 `commit_inventory.py materialize-exact`로 같은 NUL bytes에 변환한다. `stage-exact`가 NUL 형식·정렬·중복 0·현재 file set·task 책임을 검증한 뒤 위와 같은 blob manifest·receipt와 real-index 비교를 수행한다. Directory와 glob entry는 exact input에서 거부한다. 아래 일반 task의 `prepare-and-stage -- <roots...>`에서 `roots`는 사람이 읽을 수 있는 responsibility 교차 검사일 뿐이고, registry의 selected concrete array만 actual changed set을 허용한다. Exact task의 commit block은 `stage-exact`만 실행한다.

### `SENTINEL_SPEC`

```text
SENTINEL_SPEC/
  VERSION
  pyproject.toml
  uv.lock
  manifest.json
  schemas/
    config.schema.json
    spec-lock.schema.json
    backend-lock.schema.json
    result.schema.json
    evidence.schema.json
    finding-event.schema.json
    export.schema.json
    local-detail.schema.json
  contracts/
    cli.md
    exit-codes.md
    mutation-states.md
    fingerprints.md
    privacy-allowlist.md
    local-details.md
    harness-integration.md
  golden/
    crap/
    gate/
    lifecycle/
    fingerprints/
    privacy/
    runners/
    projects/polyglot-py-ts/
  tools/build_manifest.py
  tests/
    test_schemas.py
    test_manifest.py
    test_golden_vectors.py
    test_breaking_version.py
    test_cross_runtime.py
  docs/
    index.md
    log.md
    architecture.md
    contracts.md
    privacy.md
  README.md
```

이 구조 블록의 직역:

|경로·표기|뜻|
|---|---|
|`SENTINEL_SPEC/`와 들여쓰기|공통 계약 저장소의 root이며 오른쪽으로 들어간 경로는 바로 위 directory 안에 있다. 입력은 아직 없는 저장소이고 출력은 아래 책임을 가진 파일 구조다.|
|`VERSION`, `pyproject.toml`, `uv.lock`, `manifest.json`|각각 SPEC version, Python project·dependency 선언, exact dependency 잠금, 배포 file 목록과 SHA-256이다.|
|`schemas/{config,spec-lock,backend-lock,result,evidence,finding-event,export,local-detail}.schema.json`|설정, SPEC 잠금, backend 잠금, 결과, 증거, 결함 event, 공개 export, local 상세 자료의 JSON 형태를 각각 판정한다.|
|`contracts/{cli,exit-codes,mutation-states,fingerprints,privacy-allowlist,local-details,harness-integration}.md`|CLI 사용법, 종료 코드, mutation 상태, fingerprint, 공개 허용 정보, local 전용 정보, 외부 harness 연결 계약을 각각 설명한다.|
|`golden/{crap,gate,lifecycle,fingerprints,privacy,runners,projects/polyglot-py-ts}`|다섯 언어가 같은 결과를 내는지 비교할 정답 fixture이며 마지막 경로는 Python·TypeScript 혼합 project 정답이다.|
|`tools/build_manifest.py`|배포 file 목록과 hash를 만드는 실행 도구다.|
|`tests/{test_schemas,test_manifest,test_golden_vectors,test_breaking_version,test_cross_runtime}.py`|schema, manifest, 공통 정답, breaking version, 다섯 runtime 일치를 각각 test한다.|
|`docs/{index,log,architecture,contracts,privacy}.md`, `README.md`|문서 색인, 변경 기록, 구조, 계약, 개인정보 규칙과 첫 사용 안내다.|

### `SENTINEL_PY`

```text
SENTINEL_PY/
  .python-version
  pyproject.toml
  uv.lock
  spec-lock.json
  backend.lock.json
  vendor/sentinel-spec/
  src/sentinel_py/
    __main__.py
    cli.py
    orchestrator.py
    contracts/{loader.py,models.py}
    config/{models.py,resolver.py,scope.py}
    platform/{entropy.py,file_ops.py,clock.py,process.py,project_key.py,hmac_sha256.py}
    crap/{models.py,formula.py,analyzer.py,coverage.py,semantic_site.py}
    runner/pytest_reporter.py
    workspace/{native_fs.py,safe_path.py,snapshot.py,process_tree.py,sandbox_lease.py}
    mutation/{protocol.py,mutmut370.py,normalizer.py,gate.py}
    evidence/{models.py,privacy.py,lock.py,store.py}
    history/{service.py,retention.py,export.py,resolver.py}
  tests/{unit,integration,acceptance,conformance,fixtures}/
  docs/{index.md,log.md,architecture.md,contracts.md,backend.md,operations.md,privacy.md,lineage.md}
  README.md
```

이 구조 블록의 직역:

|경로·표기|뜻|
|---|---|
|`SENTINEL_PY/`, `.python-version`, `pyproject.toml`, `uv.lock`|Python tester 저장소 root와 고정 Python version, package 선언, exact dependency 잠금이다. 입력은 SPEC bundle이고 출력은 설치 가능한 Python CLI 구조다.|
|`spec-lock.json`, `backend.lock.json`, `vendor/sentinel-spec/`|사용한 SPEC bytes, 선택 mutation backend, 저장소 안에 복사한 SPEC bundle을 고정한다.|
|`src/sentinel_py/{__main__,cli,orchestrator}.py`|`python -m`, 사용자 command 해석, 전체 검사 순서 제어의 시작점이다.|
|`contracts/{loader,models}.py`, `config/{models,resolver,scope}.py`|SPEC 읽기·자료형과 설정 자료형·우선순위·검사 file 분류를 담당한다.|
|`platform/{entropy,file_ops,clock,process,project_key,hmac_sha256}.py`|난수, 안전한 file 작업, 시간, child process, project key 입력, HMAC 계산의 OS 경계를 각각 감싼다.|
|`crap/{models,formula,analyzer,coverage,semantic_site}.py`|CRAP 자료형·공식·Python 구문 분석·coverage 결합·동일 callable 식별을 각각 담당한다.|
|`runner/pytest_reporter.py`, `workspace/{native_fs,safe_path,snapshot,process_tree,sandbox_lease}.py`|pytest typed event와 안전한 filesystem·복사본·process·sandbox 수명을 담당한다.|
|`mutation/{protocol,mutmut370,normalizer,gate}.py`|backend 계약, mutmut 3.7.0 연결, 상태 정규화, 100% killed 판정을 담당한다.|
|`evidence/{models,privacy,lock,store}.py`, `history/{service,retention,export,resolver}.py`|증거 자료형·비식별화·잠금·저장과 이력 조회·보존·export·local 상세 해석을 담당한다.|
|`tests/{unit,integration,acceptance,conformance,fixtures}`, `docs/{index,log,architecture,contracts,backend,operations,privacy,lineage}.md`, `README.md`|작은 단위부터 실제 CLI·언어 공통 계약까지의 test, 운영 문서, 첫 사용 안내다.|

`Mutmut370Bridge`가 입장 시험에서 candidate별 operator·location·raw status·완전성을 제공하지 못할 때만 `mutation/mutmut370.py`를 제거하고 `mutation/cosmic_ray870.py`를 만든다. 한 release에는 둘 중 하나만 존재하고 runtime fallback은 없다.

### `SENTINEL_TS`

```text
SENTINEL_TS/
  .node-version
  package.json
  package-lock.json
  tsconfig.json
  spec-lock.json
  backend.lock.json
  vendor/sentinel-spec/
  src/
    cli.ts
    orchestrator.ts
    contracts/{loader.ts,models.ts}
    config/{models.ts,resolver.ts,scope.ts}
    platform/{entropy.ts,file-ops.ts,clock.ts,process.ts,project-key.ts,hmac-sha256.ts}
    crap/{models.ts,formula.ts,analyzer.ts,coverage.ts,semantic-site.ts}
    runner/vitest-reporter.ts
    workspace/{safe-path.ts,snapshot.ts,process-tree.ts,sandbox-lease.ts}
    mutation/{protocol.ts,stryker-plan-reporter.ts,stryker-adapter.ts,normalizer.ts,gate.ts}
    evidence/{models.ts,privacy.ts,fcntl-lock.ts,store.ts}
    history/{service.ts,retention.ts,export.ts,resolver.ts}
  src/native/linux-fs.ts
  test/{unit,integration,acceptance,conformance,fixtures}/
  docs/{index.md,log.md,architecture.md,contracts.md,backend.md,operations.md,privacy.md,lineage.md}
  README.md
```

이 구조 블록의 직역:

|경로·표기|뜻|
|---|---|
|`SENTINEL_TS/`, `.node-version`, `package.json`, `package-lock.json`, `tsconfig.json`|TypeScript tester root와 Node version, package·script 선언, dependency 잠금, compiler 설정이다. 입력은 SPEC bundle이고 출력은 설치 가능한 Node CLI 구조다.|
|`spec-lock.json`, `backend.lock.json`, `vendor/sentinel-spec/`|사용한 SPEC bytes, Stryker backend, vendored SPEC bundle을 고정한다.|
|`src/{cli,orchestrator}.ts`, `contracts/{loader,models}.ts`, `config/{models,resolver,scope}.ts`|CLI, 검사 순서, SPEC 읽기·자료형, 설정·범위 분류를 담당한다.|
|`platform/{entropy,file-ops,clock,process,project-key,hmac-sha256}.ts`, `native/linux-fs.ts`|OS 난수·file·시간·process·key·HMAC과 Linux descriptor 기반 filesystem 호출을 감싼다.|
|`crap/{models,formula,analyzer,coverage,semantic-site}.ts`, `runner/vitest-reporter.ts`|CRAP 계산·TypeScript/TSX 분석·coverage 결합과 Vitest typed event 수집을 담당한다.|
|`workspace/{safe-path,snapshot,process-tree,sandbox-lease}.ts`|안전한 경로, disposable 복사본, child process tree, sandbox 수명을 담당한다.|
|`mutation/{protocol,stryker-plan-reporter,stryker-adapter,normalizer,gate}.ts`|mutation 계약, Stryker candidate plan, 실제 실행 연결, 상태 정규화, 100% killed 판정을 담당한다.|
|`evidence/{models,privacy,fcntl-lock,store}.ts`, `history/{service,retention,export,resolver}.ts`|증거·privacy·POSIX 잠금·저장과 이력·보존·export·local 상세 해석을 담당한다.|
|`test/{unit,integration,acceptance,conformance,fixtures}`, `docs/{index,log,architecture,contracts,backend,operations,privacy,lineage}.md`, `README.md`|각 깊이의 test, 운영 문서와 첫 사용 안내다.|

### `SENTINEL_GO`

```text
SENTINEL_GO/
  go.mod
  go.sum
  spec-lock.json
  backend.lock.json
  vendor/sentinel-spec/
  cmd/sentinel-go/main.go
  internal/
    version/version.go
    cli/cli.go
    orchestrator/orchestrator.go
    contracts/{loader.go,models.go}
    config/{models.go,resolver.go,scope.go}
    platform/{entropy.go,fileops.go,clock.go,process.go,projectkey.go,hmacsha256.go}
    crap/{models.go,formula.go,analyzer.go,coverage.go,semantic_site.go}
    runner/{protocol.go,ast_wrapper.go,testmain_wrapper.go,event_pipe.go}
    workspace/{safe_path.go,snapshot.go,process_tree.go,sandbox_lease.go}
    mutation/{protocol.go,mutate4go.go,normalizer.go,gate.go}
    evidence/{models.go,privacy.go,lock.go,store.go}
    history/{service.go,retention.go,export.go,resolver.go}
  third_party/mutate4go/
  upstream/{UPSTREAM.md,patches/}
  testdata/
  docs/{index.md,log.md,architecture.md,contracts.md,backend.md,operations.md,privacy.md,lineage.md}
  README.md
```

이 구조 블록의 직역:

|경로·표기|뜻|
|---|---|
|`SENTINEL_GO/`, `go.mod`, `go.sum`|Go tester root, module·dependency 선언, 내려받은 module checksum이다. 입력은 SPEC와 mutate4go archive이고 출력은 Go CLI와 library 구조다.|
|`spec-lock.json`, `backend.lock.json`, `vendor/sentinel-spec/`|SPEC bytes, backend identity, 저장소 안 SPEC bundle을 고정한다.|
|`cmd/sentinel-go/main.go`, `internal/version/version.go`, `internal/cli/cli.go`, `internal/orchestrator/orchestrator.go`|실행 시작점, version, CLI 해석, 전체 검사 순서다.|
|`contracts/{loader,models}.go`, `config/{models,resolver,scope}.go`, `platform/{entropy,fileops,clock,process,projectkey,hmacsha256}.go`|SPEC, 설정·범위, 여섯 OS 의존 경계를 담당한다.|
|`crap/{models,formula,analyzer,coverage,semantic_site}.go`|CRAP 자료형·공식·Go AST 분석·coverage·callable 식별을 담당한다.|
|`runner/{protocol,ast_wrapper,testmain_wrapper,event_pipe}.go`|typed test 계약, AST wrapper, `TestMain` wrapper, event 통로를 담당한다.|
|`workspace/{safe_path,snapshot,process_tree,sandbox_lease}.go`, `mutation/{protocol,mutate4go,normalizer,gate}.go`|안전한 실행 복사본과 mutate4go 연결·정규화·gate를 담당한다.|
|`evidence/{models,privacy,lock,store}.go`, `history/{service,retention,export,resolver}.go`|증거 저장과 결함 이력 생명주기를 담당한다.|
|`third_party/mutate4go/`, `upstream/{UPSTREAM.md,patches/}`|검증해 복사한 upstream source와 출처·제한 patch 기록이다.|
|`testdata/`, `docs/{index,log,architecture,contracts,backend,operations,privacy,lineage}.md`, `README.md`|Go fixture, 운영 문서와 첫 사용 안내다.|

### `SENTINEL_JAVA`

```text
SENTINEL_JAVA/
  pom.xml
  spec-lock.json
  backend.lock.json
  vendor/sentinel-spec/
  src/main/java/io/github/hwainhwang/sentinel/
    cli/
    orchestrator/
    contracts/
    config/
    platform/
    crap/
    runner/
    workspace/
    mutation/
    evidence/
    history/
  src/test/java/io/github/hwainhwang/sentinel/
  src/test/resources/fixtures/
  third_party/mutate4java/
  upstream/{UPSTREAM.md,patches/}
  docs/{index.md,log.md,architecture.md,contracts.md,backend.md,operations.md,privacy.md,lineage.md}
  README.md
```

이 구조 블록의 직역:

|경로·표기|뜻|
|---|---|
|`SENTINEL_JAVA/`, `pom.xml`|Java tester root와 Maven build·dependency 선언이다. 입력은 SPEC와 mutate4java archive이고 출력은 Java CLI와 JAR 구조다.|
|`spec-lock.json`, `backend.lock.json`, `vendor/sentinel-spec/`|SPEC bytes, backend identity, 저장소 안 SPEC bundle을 고정한다.|
|`src/main/java/io/github/hwainhwang/sentinel/{cli,orchestrator,contracts,config,platform,crap,runner,workspace,mutation,evidence,history}`|production package이며 각각 CLI, 순서 제어, 계약, 설정, OS 경계, CRAP, test runner, sandbox, mutation, 증거, 이력을 담당한다.|
|`src/test/java/io/github/hwainhwang/sentinel/`, `src/test/resources/fixtures/`|Java test source와 test 입력 fixture다.|
|`third_party/mutate4java/`, `upstream/{UPSTREAM.md,patches/}`|검증해 복사한 backend source와 출처·patch 기록이다.|
|`docs/{index,log,architecture,contracts,backend,operations,privacy,lineage}.md`, `README.md`|문서 색인부터 출처까지의 운영 문서와 첫 사용 안내다.|

### `SENTINEL_CLJ`

```text
SENTINEL_CLJ/
  deps.edn
  spec-lock.json
  backend.lock.json
  vendor/sentinel-spec/
  resources/sentinel-version.edn
  bin/sentinel-clj
  src/sentinel_clj/
    cli.clj
    orchestrator.clj
    contracts/{loader.clj,models.clj}
    config/{models.clj,resolver.clj,scope.clj}
    platform/{entropy.clj,file_ops.clj,clock.clj,process.clj,project_key.clj,hmac_sha256.clj}
    crap/{models.clj,formula.clj,analyzer.clj,coverage.clj,semantic_site.clj}
    runner/{clojure_test_reporter.clj,protocol.clj}
    workspace/{native_fs.clj,safe_path.clj,snapshot.clj,process_tree.clj,sandbox_lease.clj}
    mutation/{protocol.clj,clj_mutate.clj,normalizer.clj,gate.clj}
    evidence/{models.clj,privacy.clj,lock.clj,store.clj}
    history/{service.clj,retention.clj,export.clj,resolver.clj}
  test/sentinel_clj/
  third_party/clj-mutate/
  upstream/{UPSTREAM.md,patches/}
  docs/{index.md,log.md,architecture.md,contracts.md,backend.md,operations.md,privacy.md,lineage.md}
  README.md
```

이 구조 블록의 직역:

|경로·표기|뜻|
|---|---|
|`SENTINEL_CLJ/`, `deps.edn`, `resources/sentinel-version.edn`, `bin/sentinel-clj`|Clojure tester root, dependency·alias 선언, version 자료, 실행 command다. 입력은 SPEC와 clj-mutate archive이고 출력은 Clojure CLI 구조다.|
|`spec-lock.json`, `backend.lock.json`, `vendor/sentinel-spec/`|SPEC bytes, backend identity, 저장소 안 SPEC bundle을 고정한다.|
|`src/sentinel_clj/{cli,orchestrator}.clj`, `contracts/{loader,models}.clj`, `config/{models,resolver,scope}.clj`|CLI, 검사 순서, SPEC 자료형, 설정·범위 분류를 담당한다.|
|`platform/{entropy,file_ops,clock,process,project_key,hmac_sha256}.clj`|난수, file, 시간, process, project key, HMAC OS 경계를 담당한다.|
|`crap/{models,formula,analyzer,coverage,semantic_site}.clj`, `runner/{clojure_test_reporter,protocol}.clj`|CRAP 계산·분석·coverage와 clojure.test typed event 계약을 담당한다.|
|`workspace/{native_fs,safe_path,snapshot,process_tree,sandbox_lease}.clj`, `mutation/{protocol,clj_mutate,normalizer,gate}.clj`|안전한 filesystem·sandbox와 clj-mutate 연결·상태·gate를 담당한다.|
|`evidence/{models,privacy,lock,store}.clj`, `history/{service,retention,export,resolver}.clj`|증거 저장과 결함 이력 생명주기를 담당한다.|
|`test/sentinel_clj/`, `third_party/clj-mutate/`, `upstream/{UPSTREAM.md,patches/}`|Clojure test, 검증해 복사한 backend, 출처·patch 기록이다.|
|`docs/{index,log,architecture,contracts,backend,operations,privacy,lineage}.md`, `README.md`|운영 문서와 첫 사용 안내다.|

빈 개념 문서는 미리 만들지 않는다. 위 문서는 해당 책임을 처음 구현하는 task에서 **생성**하고 `docs/index.md`와 `docs/log.md`를 같은 commit에서 갱신한다. 이후 task만 해당 문서를 **수정**한다.

## 고정 interface

이름은 언어 문법에 맞게 표기하되 입력·출력 의미는 바꾸지 않는다.

|Interface|받는 것|주는 것|
|---|---|---|
|`ContractLoader`|`spec-lock.json`, vendored bytes|`VerifiedContract` 또는 `dependencyError`|
|`ConfigResolver`|argv, config, project root|`ResolvedModule`|
|`ScopeClassifier`|module과 native source inventory|`ClassifiedScope` 또는 `usageConfigError`|
|`TestRunner`|argv, test selection, execution nonce|typed start·terminal events와 exact test ID set|
|`CoverageAdapter`|fresh report와 classified scope|callable·candidate `CoverageMap`|
|`CrapAnalyzer`|source inventory와 `CoverageMap`|`CallableMetric[]`와 exact `CrapGateResult`|
|`WorkspaceProvider`|protected inventory|`SnapshotLease`, pre-copy·destination·post-run manifest|
|`MutationAdapter`|snapshot, runner, backend lock|`CandidatePlan`, `RawOutcome[]`, provenance|
|`MutationNormalizer`|candidate와 raw outcome|9개 공통 상태 record|
|`MutationGate`|normalized record와 invariant|killed-only `MutationGateResult`|
|`HmacSha256`|opaque key byte와 canonical input byte|32-byte MAC 또는 `evidenceError`|
|`EvidenceStore`|`RunDraft`, project HMAC key|불변 completed bundle 또는 `evidenceError`|
|`HistoryService`|retained bundle과 marker|lifecycle, repeated, prune, export, local JSONL|
|`Renderer`|terminal result|text, versioned JSON, exit code|

Raw source·mutant·backend report는 `WorkspaceProvider`와 `MutationAdapter` 밖의 공용 model로 전달하지 않는다. Gate는 backend 이름을 알지 못한다. 실행형 저장소는 다른 실행형 SENTINEL package를 import하지 않는다.

각 runtime의 SafePath 구현은 “새 target 게시”와 “승인된 기존 coverage 교체”를 다른 operation으로 둔다. `--output`, export, raw root와 quarantine의 final publish는 validated parent FD에서 Linux `renameat2(RENAME_NOREPLACE)` 또는 그 syscall의 exact wrapper만 사용한다. 사전 존재 확인 뒤 target이 생긴 경우 `EEXIST`로 끝내고 attacker bytes는 불변이다. 일반 replace rename은 generated-output root 안에서 descriptor로 검증한 기존 regular coverage file에만 허용한다.

## 의존 관계와 실행 wave

|Wave|작업|진행 조건|끝나면 가능한 일|
|---:|---|---|---|
|0|T01|설계 승인|6개 독립 local child repo|
|1|T02|T01|실행·gate·backend admission 계약|
|2|T03|T02|evidence·history·privacy 계약|
|3|T04|T02와 T03|SPEC 0.1.0-rc.1 bundle|
|4|T05, T09, T13, 이어서 T06, T10, T14, 이어서 T07 단계 0..4A, T11 단계 0..4A, T15 단계 1..4A|T04|세 runtime foundation·CRAP 숫자 primitive와 backend·typed runner admission 독립 commit|
|5|T07 단계 4B..6, T11 단계 4B..6, T15 단계 4B..7, 이어서 T08, T12, T16|Wave 4 admission 통과|Python·TypeScript·Go end-to-end RC|
|6|T17..T24를 각 task 의존 순서로 실행|세 선행 runtime 계약 안정|Java·Clojure end-to-end RC|
|7|T25, 이어서 T26, T27|5개 실행형 RC|공통 conformance·문서·자기 품질 통과|
|8|T28, 이어서 T29|모든 local gate 통과|6개 private GitHub 1.0.0 release|

Wave 4의 세 admission과 뒤의 Java·Clojure admission은 공통 commit inventory 계약에 따라 VCS 밖 task·phase별 NUL path manifest를 먼저 고정한다. 이 목록은 verified upstream extracted manifest의 concrete vendored path, 위에 열거한 exact patch filename, bridge가 새로 만든 concrete path와 task의 explicit first-party file inventory를 UTF-8 byte order로 담는다. Owning repo에서만 literal pathspec과 NUL mode로 stage하고 cached NUL path set과 목록을 byte 비교한다. 이 manifest 검증 없이 admission commit을 만들 수 없다.

Wave 4는 CRAP 숫자 primitive commit 뒤 세 admission의 단계 4A exact path allowlist commit과 clean-tree 확인까지 끝내야 join한 것으로 본다. 따라서 Wave 5의 backend 구현과 evidence 작업이 admission test나 문서를 자기 commit에 섞을 수 없다. Go typed runner가 T15에서 실패하면 `SENTINEL_GO` release를 중단하고 다른 언어 작업은 계속할 수 있다. 다만 T29 전체 완료는 Go admission이 해결되기 전까지 선언하지 않는다. Python bridge가 실패하면 T07의 정해진 Cosmic Ray 단일-backend 경로로 전환한다. Robert bridge가 execution·report 경계를 넘어 operator를 바꿔야 하면 해당 언어 release를 중단하고 backend 결정을 다시 승인받는다.

---


### T01: 6개 local child repository와 upstream 불변 기준 만들기

**충족 요구사항:** 공통규칙-01, 공통규칙-05..공통규칙-10의 실행 기반

**파일:**

- 생성: `SENTINEL_SPEC/.gitignore`, `SENTINEL_SPEC/README.md`, `SENTINEL_SPEC/docs/index.md`, `SENTINEL_SPEC/docs/log.md`, `SENTINEL_SPEC/toolchain.lock.json`, `SENTINEL_SPEC/pyproject.toml`, `SENTINEL_SPEC/uv.lock`, `SENTINEL_SPEC/scripts/{bootstrap-python,uv,run-spec-python}.sh`
- 생성: `SENTINEL_{PY,TS,GO,JAVA,CLJ}/.gitignore`, 각 `README.md`, 각 `docs/index.md`, 각 `docs/log.md`, 각 `toolchain.lock.json`
- 생성: `SENTINEL_PY/scripts/{bootstrap-python,uv}.sh`, `SENTINEL_TS/scripts/{bootstrap-node,node,npm}.sh`, `SENTINEL_GO/scripts/{bootstrap-go,go}.sh`, `SENTINEL_JAVA/scripts/{bootstrap-java,java,mvn}.sh`, `SENTINEL_CLJ/scripts/{bootstrap-clojure,clojure,java}.sh`
- 생성: `SENTINEL_{GO,JAVA,CLJ}/upstream/UPSTREAM.md`
- 생성: `SENTINEL_SPEC/baselines/{upstream-tree,upstream-archive,upstream-git-metadata}.json`, `SENTINEL_SPEC/{clean-install-executor,release-tools}.lock.json`
- 생성: `SENTINEL_SPEC/tools/{commit_inventory,verify_upstream_tree,verify_upstream_git_metadata,verify_oci_executor,verify_release_tools,github_api_transport}.py`, `SENTINEL_SPEC/tools/{task_commit_paths.json,git_ssh_wrapper.sh}`, `SENTINEL_SPEC/tests/{test_commit_inventory,test_spec_python_launcher,test_runtime_launchers,test_upstream_baseline,test_upstream_git_metadata,test_oci_executor,test_release_tools,test_github_api_transport}.py`
- 생성: VCS 밖 owner-only `build/t01/oci-executor-session.json`
- 생성: 각 저장소의 `scripts/verify_repository.sh`

**받는 것:** 승인된 product-spec과 design-doc, `upstream/unclebob/*`의 고정 commit 7개

**주는 것:** remote가 아직 없는 6개 독립 local Git 저장소와 upstream 불변 기록

- [ ] **단계 1: 저장소 경계 검사가 실패하도록 작성**

각 저장소에 다음 형태의 검사를 먼저 만들고 아직 `.git`이 없어서 실패하는지 확인한다.

```bash
#!/usr/bin/bash
set -euo pipefail
test "$(/usr/bin/git rev-parse --show-toplevel)" = "$(pwd -P)"
test "$(/usr/bin/git branch --show-current)" = "main"
test -z "$(/usr/bin/git remote)"
test -f docs/index.md
test -f docs/log.md
```

이 블록의 직역:

|요소|입력·판정·출력|
|---|---|
|`#!/usr/bin/bash`, `set -euo pipefail`|검증된 Bash로 실행하고 첫 실패, 미정 변수, pipe 실패를 즉시 드러낸다.|
|`/usr/bin/git rev-parse --show-toplevel`, `$(pwd -P)`, `=`|Git이 말하는 저장소 root와 symlink를 해소한 현재 실제 directory가 같은지 판정한다.|
|`/usr/bin/git branch --show-current`, `"main"`|현재 branch 이름이 literal `main`인지 판정한다.|
|`/usr/bin/git remote`, `test -z`|remote 이름 출력이 빈 문자열인지 판정한다.|
|`test -f docs/index.md`, `test -f docs/log.md`|OKF 문서 색인과 변경 기록이 일반 file로 존재하는지 판정한다.|
|출력|모든 판정이 참이면 stdout 없이 exit 0, 하나라도 거짓이면 nonzero다. 초기 RED에서는 `.git`이 없어 첫 Git 판정이 실패한다.|

- [ ] **단계 2: 실패를 확인**

실행 위치: 각 `SENTINEL_*` directory

실행: `/usr/bin/bash scripts/verify_repository.sh`

기대: `git rev-parse`가 실패하고 root workspace를 Git 저장소로 사용하지 않음

- [ ] **단계 3: 최소 repository 골격 작성**

각 directory 안에서만 다음을 실행한다. 그 전에 `/usr/bin/sha256sum /usr/bin/git /usr/bin/bash`의 결과가 각각 승인된 `7868f63309367aed4330fd3da5841634acc1c9b51f3e090451ac02c95090e202`, `1168df29c00d1492c60e6fd2f2983cdd2693fa994acb58d0db4ddfafd12e99f1`인지 확인하고 두 binary의 root owner·`0755` mode·regular-file identity도 검사한다. 이 검사가 실패하면 repository mutation과 shell script 실행은 0이다. T01에서는 아직 launcher를 신뢰할 수 없으므로 PATH lookup 없는 absolute Git과 Bash만 쓴다. 모든 committed shell script의 shebang도 exact `#!/usr/bin/bash`이며 `/usr/bin/env`를 통한 PATH 재탐색은 금지한다.

```bash
SENTINEL_BOOTSTRAP_HOME=<OWNER_ONLY_EMPTY_ABSOLUTE_DIRECTORY>
/usr/bin/env -i HOME="$SENTINEL_BOOTSTRAP_HOME" XDG_CONFIG_HOME="$SENTINEL_BOOTSTRAP_HOME/xdg" GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null PATH=/usr/bin:/bin /usr/bin/git -C . init --template="$SENTINEL_BOOTSTRAP_HOME/templates" -b main
/usr/bin/env -i HOME="$SENTINEL_BOOTSTRAP_HOME" XDG_CONFIG_HOME="$SENTINEL_BOOTSTRAP_HOME/xdg" GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null PATH=/usr/bin:/bin /usr/bin/git -C . config --local core.autocrlf false
/usr/bin/env -i HOME="$SENTINEL_BOOTSTRAP_HOME" XDG_CONFIG_HOME="$SENTINEL_BOOTSTRAP_HOME/xdg" GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null PATH=/usr/bin:/bin /usr/bin/git -C . config --local core.filemode true
/usr/bin/env -i HOME="$SENTINEL_BOOTSTRAP_HOME" XDG_CONFIG_HOME="$SENTINEL_BOOTSTRAP_HOME/xdg" GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null PATH=/usr/bin:/bin /usr/bin/git -C . config --local user.name "황화인"
/usr/bin/env -i HOME="$SENTINEL_BOOTSTRAP_HOME" XDG_CONFIG_HOME="$SENTINEL_BOOTSTRAP_HOME/xdg" GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null PATH=/usr/bin:/bin /usr/bin/git -C . config --local user.email "166008093+hwain-hwang@users.noreply.github.com"
```

이 블록의 직역:

|요소|입력·판정·출력|
|---|---|
|`SENTINEL_BOOTSTRAP_HOME=<OWNER_ONLY_EMPTY_ABSOLUTE_DIRECTORY>`|`SENTINEL_BOOTSTRAP_HOME`에 소유자만 접근하는 비어 있는 실제 절대 경로를 넣는다. `<...>`는 실행 때 검증한 실제 경로로 바꾼다.|
|`/usr/bin/env -i`와 `HOME`, `XDG_CONFIG_HOME`, `GIT_CONFIG_NOSYSTEM=1`, `GIT_CONFIG_GLOBAL=/dev/null`, `PATH=/usr/bin:/bin`|상속 환경을 비우고 Git이 읽을 home·설정·실행 경로를 이 값으로만 제한한다.|
|`/usr/bin/git -C . init --template=... -b main`|현재 child directory에 빈 template만 사용하고 첫 branch가 `main`인 Git 저장소를 만든다.|
|`config --local core.autocrlf false`|줄바꿈 bytes를 Git이 자동 변환하지 않게 이 저장소에만 설정한다.|
|`config --local core.filemode true`|실행 권한을 포함한 file mode 변경을 Git이 추적하게 한다.|
|`config --local user.name "황화인"`, `user.email "166008093+hwain-hwang@users.noreply.github.com"`|commit 작성자 이름과 GitHub noreply email을 이 저장소에만 고정한다.|
|출력|첫 명령은 `.git`과 `main` symref를 만들고, 다음 네 명령은 local config를 기록한다. 어느 명령이든 실패하면 다음 명령을 진행하지 않는다.|

`SENTINEL_BOOTSTRAP_HOME`, 그 아래 `xdg`와 `templates`는 미리 owner-only `0700`, symlink 0, empty directory로 만들고 descriptor identity를 고정한다. `/usr/bin/env -i` 때문에 inherited `GIT_DIR`, `GIT_WORK_TREE`, `GIT_OBJECT_DIRECTORY`, alternate object, config, template, hook와 loader 변수가 Git process에 들어가지 않는다. 이 identity는 앞서 GitHub `/user` REST 응답으로 확인한 login `hwain-ai`, numeric ID `166008093`, 표시 이름 `황화인`에 대응하는 GitHub noreply 주소이며 각 child repo local config에만 둔다. Global Git config는 바꾸지 않고 같은 sealed environment의 `/usr/bin/git config --local --get-regexp '^user\.(name|email)$'`로 재조회한다. `README.md`에는 repo의 한 가지 책임, private 예정 상태, design-doc 경로를 기록한다. `docs/index.md`에는 `okf_version: "0.2"`와 현재 실재하는 문서 링크만 넣고 `docs/log.md`에는 오늘의 Creation 한 건만 기록한다. Go·Java·Clojure의 `UPSTREAM.md`에는 이름, 고정 commit, 원본 URL, 가져올 범위가 execution·report boundary뿐이라는 내용을 기록한다.

다음 세 문단은 이 단계에서 미리 구현하는 지시가 아니라 단계 3A가 먼저 실패한 뒤 단계 3B에서 만족시킬 launcher acceptance 계약이다. 단계 3에서는 repository 골격, bootstrap-only test file과 그 test를 시작할 최소 lock/scaffold만 작성하고 production bootstrap·launcher 동작은 작성하지 않는다.

단계 3B의 각 bootstrap은 상단 표의 runtime archive를 고정 URL에서 받아 SHA-256을 확인한 뒤 repo-local `.toolchain`에 원자 설치하고 installed tree·version·ABI를 `toolchain.lock.json`에 대조한다. SPEC·Python `uv.sh`, TypeScript `node.sh`·`npm.sh`, Go `go.sh`, Java `java.sh`·`mvn.sh`, Clojure `java.sh`·`clojure.sh`는 T01에서 online·offline mode까지 완성하며 minimal environment와 repo-local executable만 사용한다. Java는 별도 Maven Wrapper를 만들지 않고 `mvn.sh`가 pinned `JAVA_HOME`과 repo-local Maven 3.9.16 standalone distribution만 실행한다. Clojure wrapper는 populate 때만 pinned Clojure CLI를 쓰고 offline mode는 verified classpath와 pinned Temurin을 직접 실행한다. Python 두 repository의 `uv.sh`는 inherited `UV_*`, `VIRTUAL_ENV`, `PYTHON*`, `PIP_*`, proxy·credential 변수를 제거하고 owner-only synthetic HOME·XDG directories와 verified empty NETRC를 고정한다. Pinned uv에는 global `--no-config`, `UV_KEYRING_PROVIDER=disabled`, canonical repository root 아래 exact `UV_PROJECT_ENVIRONMENT=<repo>/.toolchain/venv`와 `UV_CACHE_DIR=<repo>/.toolchain/uv-cache`를 내부에서 전달하고 두 path의 owner·mode·no-symlink identity를 검증한다. `uv.sh run`은 항상 `uv --no-config run --project <REPO_ROOT> --locked --offline --no-sync ...`로 이미 동기화된 environment만 실행하고 dependency resolution·download·implicit sync를 하지 않는다. Dependency 선언·lock 갱신의 `uv.sh add`는 반드시 `--no-sync`로 environment install 0을 보장하고, package를 environment에 채우는 동작은 별도 `uv.sh sync --locked`에만 허용한다. User·system·parent `uv.toml`, `.netrc`와 credential store는 읽지 않는다. Caller가 environment 위치나 cache를 바꿀 수 없고 repository root `.venv`는 생성하지 않는다. Pytest `cache_dir`는 exact `.toolchain/pytest-cache`로 고정하고 wrapper는 `PYTHONDONTWRITEBYTECODE=1`을 강제해 첫 commit 전 test가 top-level `.pytest_cache`나 source `__pycache__`를 만들지 않게 한다. Test가 다른 environment·cache path 설정을 주입하면 wrapper가 거부한다.

TypeScript `npm.sh`는 inherited `NPM_CONFIG_*`, `NODE_OPTIONS`, proxy와 registry environment를 제거하고 owner-only empty user config, lock-verified empty global config, repository `.npmrc` 부재, `.toolchain/npm-cache`, `audit=false`, `fund=false`, `update-notifier=false`를 내부에서 고정한다. Install lifecycle script는 기본 `ignore-scripts=true`이며, `toolchain.lock.json`에 package tar digest·script text digest·argv·network 0 sandbox가 모두 명시된 exact allowlist만 install 뒤 별도 실행할 수 있다. Unknown lifecycle hook, project·user·global config, plugin과 registry override는 package process·network 0에서 실패한다.

`npm.sh`는 dependency materialization용 `ci`와 명시적 `lock-add-exact` mode에만 쓴다. `lock-add-exact` grammar는 `--prod <NAME@EXACT_VERSION>...`와 `--dev <NAME@EXACT_VERSION>...` 두 mode뿐이고 둘을 한 호출에서 섞거나 역할을 생략하면 package·network process 0에서 거부한다. `--prod`는 pinned npm의 `install --package-lock-only --ignore-scripts --save-exact --save-prod`, `--dev`는 `install --package-lock-only --ignore-scripts --save-exact --save-dev` 동등 argv만 실행한다. 두 mode 모두 exact version argument만 받고 `package.json`과 `package-lock.json`만 갱신하며 `node_modules`와 lifecycle process는 만들지 않는다. 실제 설치는 뒤의 `ci`가 맡는다. Test·typecheck·build·Stryker와 project CLI는 npm script나 `.bin`을 거치지 않는다. `node.sh --tool <vitest|tsc|stryker> -- <ARGS>`가 logical name을 내부 allowlist로 해석하고 `package-lock.json`과 `toolchain.lock.json`에 고정된 Vitest `vitest.mjs`, TypeScript `tsc.js`, Stryker bin target의 canonical path·regular-file mode·package tree·SHA-256을 검증한 뒤 pinned Node absolute binary에 exact argv로 직접 전달한다. Caller가 executable path를 넣을 수 없고 unknown tool, `--` 누락과 빈 argv는 Node spawn 0에서 실패한다. First-party `.mjs` entry는 `node.sh <REPO_RELATIVE_ENTRY> -- <ARGS>` mode에서 canonical repository path와 file digest를 검증한다. Hostile `/bin/sh`, `PATH`, `NODE_PATH`, `node_modules/.bin` symlink와 package script는 child Node spawn 0에서 실패하도록 launcher oracle에 포함한다.

Java `mvn.sh`는 inherited `MAVEN_ARGS`, `MAVEN_OPTS`, `JAVA_TOOL_OPTIONS`, `_JAVA_OPTIONS`, `JDK_JAVA_OPTIONS`, `M2_HOME`, `MAVEN_HOME`, proxy와 mirror environment를 제거한다. Owner-only synthetic user home, owner-only empty user settings, pinned Maven distribution의 digest-verified global settings, exact `.toolchain/m2` local repository를 argv로 고정하고 project `.mvn` directory와 core extension은 허용하지 않는다. Go `go.sh`의 `GOENV=off`, `GOWORK=off`, empty `GOFLAGS`와 offline `GOVCS=*:off` 계약, Clojure의 resolver 없는 verified-classpath offline 계약도 모두 T01 launcher test를 통과해야 한다. `.toolchain/**`는 Git·release 대상에서 제외한다. 이후 이 계획의 모든 언어 command는 해당 wrapper를 사용하며 ambient runtime, package manager와 PATH 선택을 허용하지 않는다.

- [ ] **단계 3A: upstream·OCI·release verifier 실패 test 작성과 RED 확인**

Production bootstrap·launcher 동작을 작성하기 전에 `tests/test_runtime_launchers.py`에 `unittest.main()` entrypoint를 두고 `/usr/bin/python3 -I "$PWD/tests/test_runtime_launchers.py"`로 먼저 실행한다. `-I -m unittest tests...`는 current directory를 import path에서 제거하므로 사용하지 않는다. 이 bootstrap-only oracle은 여섯 repo의 missing launcher, wrong archive·installed tree·ABI, ambient runtime/PATH와 hostile PATH의 fake Bash spawn 0, non-absolute shebang, Python root `.venv`, hostile user·system·parent `uv.toml`, `.netrc`·keyring, `uv run`의 missing `--locked --offline --no-sync`, `uv add`의 missing `--no-sync`와 environment/package install 시도, direct SPEC launcher의 network 시도, npm project·user·global config와 lifecycle·audit network, hostile Go user env·parent `go.work`·proxy miss direct-VCS fallback, Maven user/global settings·`.mvn` extension·local repo, Clojure unsupported `-Soffline`·resolver 호출·classpath mismatch를 각각 기대 실패로 고정한다. 별도 bootstrap repository fixture는 inherited `GIT_DIR`, `GIT_WORK_TREE`, object directory, system/global config와 malicious init template를 넣어도 wrong repository write와 template·hook copy가 0인지 확인한다. 아직 wrapper가 없거나 semantic guard가 없어서 relevant case가 RED이고 외부 network·package process는 0이어야 한다. 그 뒤 T01 bootstrap과 launcher만 최소 구현해 이 test를 pinned SPEC pytest로도 GREEN으로 만든다.

Repo-local SPEC Python bootstrap이 끝난 직후 production verifier와 lock을 만들기 전에 `test_commit_inventory.py`, `test_spec_python_launcher.py`, `test_upstream_baseline.py`, `test_upstream_git_metadata.py`, `test_oci_executor.py`, `test_release_tools.py`를 먼저 작성한다. T01의 최소 `pyproject.toml`과 `uv.lock`은 Python 3.12.13과 pytest를 exact version·artifact digest로만 고정하며 application dependency는 아직 넣지 않는다. `scripts/uv.sh sync --locked` 뒤에만 test를 실행하고 T02는 이 두 files를 새로 만들지 않고 schema validator dependency를 추가해 lock을 갱신한다. Commit inventory test는 temporary owning repository에서 registry의 task·logical repository·phase exact lookup, missing·extra actual changed path, registry working-tree tamper, temporary-index discovery, exact NUL manifest, responsibility escape, symlink·submodule·unmerged entry, pre-staged index, crash resume와 changed path·mode·blob 검증을 다룬다. 또한 exact source의 top-level sorted path array와 selector-to-array object를 각각 검증하고, missing·unknown selector, selector 간 자동 union, output race와 existing different bytes를 거부하며 existing byte-identical NUL output만 재시도에서 채택하는지 확인한다. `abandon-stage` test는 exact staged state와 empty-index-after-crash만 복구하고, partial stage·다른 HEAD·receipt·commit이 있으면 working file과 index를 바꾸지 않는지 확인한다. Imported-commit test는 preflight intent publish 직후와 fast-forward 직후 crash를 주입해 existing exact receipt와 adopted state만 write 0으로 채택하며 logical repository·base·commit·tree·path·mode·blob 하나라도 다르면 Git mutation 0인지 확인한다. Launcher test는 다른 owning repo와 whitespace path를 caller cwd로 사용해도 cwd와 `--repository .` 의미가 그대로이고, 실행 Python·uv project·lock이 SPEC에 고정되며 ambient `UV_*`, `PYTHON*`, `PIP_*`, virtualenv와 PATH가 영향을 주지 못하는지, environment와 cache가 `.toolchain` 아래 exact path이고 root `.venv`·`.pytest_cache`·`__pycache__` 생성이 0인지 검사한다. Upstream test는 path·type·mode·content, archive member, ref·object·config·shallow·reflog 변조를 temporary fixture에서 만든다. OCI test는 wrong binary·socket identity·remote endpoint·ambient context·TLS·proxy를, release test는 binary·host key·trust-store·loader·proxy·CA·SNI·TLS·redirect·SSH injection을 각각 external call 0으로 고정한다. Test가 단순 missing fixture 때문에 모두 같은 지점에서 실패하지 않도록 각 module import 또는 lock field가 생기면 해당 semantic negative가 이어서 실패하게 한다.

`test_github_api_transport.py`도 같은 RED 묶음에 포함하며 production transport가 생기기 전에는 fake TLS semantic case가 실패해야 한다.

실행 위치: `SENTINEL_SPEC`

실행: `/usr/bin/bash scripts/bootstrap-python.sh && scripts/uv.sh sync --locked`

실행: `scripts/uv.sh run pytest tests/test_runtime_launchers.py tests/test_commit_inventory.py tests/test_spec_python_launcher.py tests/test_upstream_baseline.py tests/test_upstream_git_metadata.py tests/test_oci_executor.py tests/test_release_tools.py tests/test_github_api_transport.py -q`

기대: runtime launcher는 선행 bootstrap RED 뒤 최소 구현으로 통과하고, commit inventory·SPEC launcher·verifier module과 exact lock·baseline이 아직 없어서 나머지 7개 test file의 relevant case가 실패하며 외부 network·Git write·container 호출은 0

- [ ] **단계 3B: 최소 baseline·lock·verifier 구현**

T01 root 이외의 `prepare-and-stage`, `materialize-exact`, `stage-exact`, `commit-prepared`는 `--predecessor-receipt`와 그 whole-file SHA-256이 필수다. Tool은 registry의 predecessor key와 receipt의 repository·task·phase·committed OID·tree를 검증해 base HEAD를 내부 도출하며 caller의 `--base-head`가 그 값과 같지 않으면 index·ref mutation 0이다. 따라서 중간에 임의 commit을 만든 뒤 그 SHA를 새 base로 자가 선언할 수 없다. T07 imported admission은 source committed receipt와 별도로 primary T06 predecessor receipt도 요구한다. `import-verify`가 출력하는 typed adoption receipt는 task `T07`, phase `mutation-adoption`, primary repository identity, T06 predecessor receipt digest, source admission receipt digest와 adopted commit·tree를 모두 담는 committed-equivalent receipt다. Registry가 `coverage-join`의 유일한 predecessor를 이 `mutation-adoption`으로 고정하므로 generic completion receipt 대신 이 adoption receipt만 허용한다. T25..T29 driver도 attempt seal에 predecessor receipt path·digest를 repository별로 넣고 같은 검증을 호출한다.

`commit_inventory.py`는 repository root를 `git rev-parse --show-toplevel`로 owning child와 exact 비교하고 `/usr/bin/git`을 argv 배열로만 실행한다. Logical repository는 canonical root basename이 exact `SENTINEL_SPEC|SENTINEL_PY|SENTINEL_TS|SENTINEL_GO|SENTINEL_JAVA|SENTINEL_CLJ`면 그 값이고, 다른 basename의 isolated checkout은 `--logical-repository`가 필수다. Explicit 값도 이 allowlist 밖이면 실패한다. `prepare-and-stage`는 caller가 `--base-head`, `--task`, `--phase`, VCS 밖 absolute `--output-root`와 `--` 뒤 responsibility root를 주어야 한다. SPEC bootstrap 외에는 `--registry-source-commit <SPEC_T01_HEAD>`도 필수다. 그 commit의 `tools/task_commit_paths.json` fixed entry에서 고른 exact array와 actual changed set이 같은 경우만 alternate index에서 concrete set을 만들며, 사람이 읽는 escaped text mirror와 NUL manifest로 함께 no-replace 기록하고 둘의 round-trip이 같아야 한다. `materialize-exact`의 source는 registry의 selector entry가 지목한 사람이 관리하는 sorted concrete path JSON array 또는 bounded selector key마다 그런 array 하나를 가진 object다. T04 이후 same-task source는 authority가 아니라 T01 registry가 미리 고정한 exact source digest·selector array의 test mirror다. Materialize는 source path·canonical SHA-256과 selected array가 committed registry entry와 같은지 먼저 확인하므로 같은 commit에서 source와 변경 file을 함께 늘릴 수 없다. Object에는 `--selector <EXACT_KEY>`가 필수이며 선택한 array 하나만 NUL manifest로 변환하고 자동 union·fallback·working-tree discovery는 하지 않는다. Output은 no-replace로 만들고 재시도에서 기존 bytes가 새 canonical bytes와 byte-identical일 때만 채택한다. `stage-exact`는 그 manifest만 받는다.

두 staging mode 모두 먼저 VCS 밖 durable intent를 게시하고, real index와 같은 filesystem의 tool-owned unique `.git/sentinel-index-attempts/<attemptId>/target.index`에 complete target index를 만든다. Partial temporary file은 Git lock이 아니므로 crash 뒤 다음 attempt를 막지 않는다. Target을 file sync하고 HEAD·worktree, baseline index digest와 target path·mode·blob·tree를 검증한 뒤에만 absent `.git/index.lock`으로 `RENAME_NOREPLACE`한다. 이어 standard Git lock protocol처럼 `.git/index.lock`을 `.git/index`로 atomic rename하고 `.git` directory를 sync한다. Crash 뒤 real index는 exact baseline 또는 exact target뿐이다. Matching durable intent와 complete stale `.git/index.lock`이면 baseline index가 그대로인지 다시 확인한 뒤 finalize하고, target index가 이미 real이면 stale lock bytes까지 exact인 경우만 descriptor-safe하게 회수한다. Foreign·partial·different lock, partial intent 또는 제3의 real index에서는 ref·index·worktree mutation 0으로 중단한다.

모든 commit은 raw `git commit`과 사후 검증 두 단계가 아니라 `commit-prepared` 한 command로 만든다. 이 command는 prepared receipt path와 whole-file SHA-256, task, phase, base HEAD 또는 unborn parent, exact message를 입력받는다. 기본 target은 `refs/heads/main`이다. Prepared receipt에 target ref, expected old symbolic HEAD·OID, tree OID, parent, exact author·committer `황화인 <166008093+hwain-hwang@users.noreply.github.com>`, 처음 intent를 만든 UTC seconds와 `+0000`, UTF-8 message bytes를 먼저 durable seal한다. 이어 `/usr/bin/git --no-replace-objects commit-tree <TREE> [-p <BASE>]`에 message를 stdin으로 주고 minimal environment에 sealed identity·date만 전달한다. 만든 object의 type·tree·parent·identity·timestamp·message를 다시 parse한다. Exact new OID를 `refIntent`에 sync한 뒤 `/usr/bin/git --no-replace-objects update-ref --stdin` transaction으로 symbolic HEAD와 expected old ref를 함께 CAS한다. 일반 commit은 `start`, `symref-verify HEAD refs/heads/main`, `update refs/heads/main <NEW> <BASE_OR_ZERO>`, `prepare`, `commit`이다. Porcelain commit, hook, signing과 ambient config는 0이다. State는 `prepared -> commitObjectCreated -> refIntent -> refUpdated -> committed`만 허용한다. Crash 뒤 ref가 base이고 target index가 exact면 sealed commit object를 재채택해 CAS하고, ref가 new이며 index·worktree가 new tree와 exact면 durable completion만 쓴다. 다른 ref·index·worktree에서는 mutation 0이다.

유일한 branch-target 예외는 T29 `spec-candidate`와 `runtime-candidate` phase다. `release_orchestrator.py allocate`가 external network·Git mutation 0으로 먼저 게시한 owner-only attempt receipt와 whole-file SHA-256을 `commit-prepared --candidate-attempt <PATH> --candidate-attempt-sha256 <SHA256> --target-ref <CANDIDATE_REF>`에 준다. Frozen policy가 허용하는 `<CANDIDATE_REF>`는 SPEC의 `refs/heads/release/spec-v1.0.0-candidate-<INTENT>` 또는 각 runtime의 `refs/heads/release/v1.0.0-candidate-<INTENT>`뿐이다. Tool은 frozen registry의 phase policy, attempt ID·128-bit intent와 repository name을 exact join하고 target ref absence, current `HEAD -> refs/heads/main`, main OID=`<BASE>`를 확인한다. 한 `update-ref --stdin` transaction의 `start`, `symref-verify HEAD refs/heads/main`, `create <TARGET_REF> <NEW>`, `symref-update HEAD <TARGET_REF> ref refs/heads/main`, `prepare`, `commit`으로 candidate ref 생성과 checkout ref 전환을 함께 수행한다. Target ref 또는 HEAD만 생기는 중간 상태는 없다. T01 test는 candidate ref create·HEAD symref 전환 전후 crash, existing ref, wrong intent·repository·base와 concurrent main 변경을 주입해 exact resume 또는 Git mutation 0을 확인한다. T29 merge 뒤 local 복귀는 별도 sealed `adopt-merged-main` transaction이 `--remote-merge-receipt`와 그 whole-file SHA-256, old main, candidate ref·commit, merge commit의 single parent와 candidate와 같은 tree를 검증한 뒤 `update refs/heads/main <MERGE> <OLD_MAIN>`과 `symref-update HEAD refs/heads/main ref <CANDIDATE_REF>`를 함께 적용한다. Index·worktree가 그 공통 tree와 exact해야 하며 candidate ref는 감사 증거로 이동·삭제하지 않는다. 성공하면 immutable attempt directory에 task `T29`, phase `merged-main-adoption`, merge commit·tree·timestamp와 모든 input digest를 담은 committed-equivalent receipt를 no-replace 게시하고 stdout으로 `<PATH> <SHA256>`을 출력한다. 이 receipt가 T29 `release-tag`의 유일한 tag input이다.

Commit phase record도 prepared attempt 아래 unique owner-only subattempt에서 temp write·file sync·no-replace rename·directory sync하고 `committed.json`을 마지막 marker로 게시한다. Partial subattempt는 immutable하게 두고 same sealed intent로 새 subattempt에서 재구성한다. Existing complete `committed.json`은 whole-file digest와 live ref·tree·index·worktree가 exact일 때 write 0으로 채택한다. Command stdout은 `<COMMITTED_RECEIPT_PATH> <COMMITTED_RECEIPT_SHA256>`다. T01 test는 global/system/local config, attributes·filter, hooks·signing, index publish 각 경계, object 생성 뒤, ref intent 뒤, CAS 전·후와 completion publish 중 crash, concurrent ref 변경을 주입해 잘못된 ref·index·worktree mutation 0과 exact resume을 확인한다.

Imported commit은 `import-prepare -> import-resume -> import-verify` 전용 상태기만 사용한다. Prepare가 source repository identity와 source committed receipt path·whole-file digest, logical repository, base·selected commit·tree·path·mode·blob을 join해 durable intent를 먼저 게시한다. Resume만 `/usr/bin/git fetch --no-tags --no-write-fetch-head --no-recurse-submodules <SOURCE> <COMMIT>`을 실행하고 fetched object를 재검증한다. Changed regular file마다 current bytes가 base 또는 target 중 하나일 때만 descriptor-safe temp write·file sync·atomic rename으로 target을 materialize하므로 crash 뒤 재실행할 수 있고 제3의 byte·type은 mutation 0이다. Target index를 위 lock protocol로 게시한 뒤 exact target worktree·index에서만 `update-ref --stdin`의 `symref-verify HEAD refs/heads/main`과 expected old OID를 한 transaction으로 CAS해 base를 selected commit으로 바꾼다. State는 `intentRecorded -> objectsFetched -> worktreePrepared -> indexPrepared -> refUpdated -> adopted`뿐이다. Verify는 ref·tree·index·worktree와 source receipt를 다시 join하고 `<ADOPTION_INTENT>`가 가리키는 immutable attempt directory 아래 `committed-equivalent.json`을 내부 파생해 no-replace 게시한 뒤 stdout으로 `<PATH> <SHA256>`을 출력한다. Caller가 output path를 정할 수 없다. Raw fetch·merge와 이전 imported-commit 검증 mode는 사용하지 않는다.

`scripts/run-spec-python.sh`는 caller cwd를 저장·재검증하고 script 자신에서 canonical SPEC root를 descriptor로 해석한 뒤 T01 `uv.sh`와 같은 owner-only HOME·XDG·NETRC, global `--no-config`, disabled keyring, exact SPEC environment·cache를 사용한다. Pinned SPEC uv absolute executable에는 `run --project <SPEC_ROOT> --locked --offline --no-sync python <ABSOLUTE_SCRIPT> ...`를 argv로 전달한다. 실행 대상은 canonical `SENTINEL_SPEC/tools/` 아래 allowlisted regular file만 허용하며 inherited `UV_*`, `PYTHON*`, `VIRTUAL_ENV`, credential·loader·proxy와 `PATH`를 제거한다. Uv project와 interpreter는 SPEC lock·toolchain에서 고정하되 child의 cwd는 caller owning repository 그대로 유지한다. 따라서 다른 repo에서 `--repository .`은 그 repo를 뜻한다. SPEC T01 root commit 뒤 VCS 밖 `build/t01/spec-foundation-seal.json`은 SPEC commit, registry·tool blob OID와 receipt path·whole-file digest를 durable하게 고정한다. Launcher는 bootstrap mode 외 모든 inventory subcommand에 이 seal의 registry source commit과 blob OID를 내부에서 자동 주입하고 caller가 같은 option을 넘기거나 바꾸면 child spawn 0으로 거부한다. `prepare-and-stage`, `materialize-exact`, `stage-exact`, `commit-prepared`, import와 verify mode가 모두 같은 frozen registry를 쓴다. Launcher·tool·seal digest, SPEC environment와 caller cwd가 다르면 child spawn은 0이다.

T01 unborn mode는 별도 계약이다. `prepare-and-stage --unborn`은 `HEAD` 해석 실패, `HEAD`가 exact `refs/heads/main`을 가리킴, local branch ref·commit 0개, empty real index인 새 owning repository에서만 허용하고 parent count 0을 receipt에 고정한다. 대응 `commit-prepared --expected-unborn-parent`만 parent 0개의 exact root commit을 만들고 tree·message·index·worktree를 검증해 `committed.json`을 쓴다. SPEC의 bootstrap variant는 그 marker와 같은 transaction에서 `build/t01/spec-foundation-seal.json`도 temp write·file sync·no-replace rename·directory sync로 게시하며 SPEC commit OID, registry·tool blob OID, prepared·committed receipt path와 whole-file SHA-256을 봉인한다. Seal 게시 전 crash는 exact committed state에서 seal만 재구성하고, 다른 ref·tree·receipt이면 write 0으로 중단한다. 일반 `--base-head`와 unborn option을 함께 주면 실패한다.

Annotated tag는 porcelain `git tag`가 아니라 `tag-prepared` 상태기로만 만든다. Command는 committed receipt path·whole-file SHA-256, task·phase, exact `refs/tags/<NAME>`과 UTF-8 message를 받고 target commit·tree·identity를 receipt와 live repository에 join한다. Tagger는 exact `황화인 <166008093+hwain-hwang@users.noreply.github.com>`, timestamp는 target committed receipt의 sealed committer UTC seconds와 `+0000`으로 먼저 intent에 고정한다. Minimal Git environment에서 canonical tag object bytes를 `/usr/bin/git --no-replace-objects mktag`에 stdin으로 주고 object type·target·tagger·timestamp·message를 다시 parse한 뒤 `/usr/bin/git --no-replace-objects update-ref refs/tags/<NAME> <TAG_OBJECT> <ZERO_OID>`로 absence CAS한다. State는 `intentRecorded -> tagObjectCreated -> refUpdated -> tagged`뿐이며 tag ref가 absent이면 sealed object를 재채택하고, exact ref가 이미 있으면 read-only 검증 뒤 completion만 쓴다. 다른 tag·target·message에서는 이동·삭제·force·signing 없이 mutation 0이다. T01 test는 hostile `tag.gpgSign`, hooks·config·replacement object, object 생성 뒤와 ref CAS 전후 crash, concurrent tag 생성을 넣어 external signer·hook 0과 exact resume을 확인한다.

`clean-install-executor.lock.json`은 상단 표에서 직접 확인한 local Docker client binary digest·version·commit·API·OS·arch, local Engine version·commit·API·OS·arch, canonical `/run/docker.sock`의 socket type·root owner·docker group·`0660` mode와 허용 OCI image full reference를 exact field로 고정한다. `verify_oci_executor.py`는 `/usr/bin/docker` absolute argv만 `shell=False`로 호출하고 parent의 `DOCKER_HOST`, `DOCKER_CONTEXT`, `DOCKER_CONFIG`, TLS·proxy 변수를 전달하지 않는다. 매 session마다 canonical socket의 device·inode를 owner-only VCS 밖 session record에 잡아 모든 pull·inspect·create·run 전후 같은 identity인지 확인한다. Docker client에는 explicit `--host unix:///run/docker.sock`와 새 owner-only empty `--config` directory만 주고, client·server JSON이 lock과 다르거나 remote/context endpoint가 선택되면 container 호출 전에 실패한다. Executor나 Engine을 바꾸려면 이 exact lock과 반례 test를 명시적으로 갱신해야 하며 자동 학습은 금지한다.

`release-tools.lock.json`은 `/usr/bin/git` 2.50.1·SHA-256 `7868f63309367aed4330fd3da5841634acc1c9b51f3e090451ac02c95090e202`, `/usr/bin/ssh` OpenSSH_8.7p1/OpenSSL 3.5.5·SHA-256 `d82647712181d04868c223f1b717304a4a6e3bb348bc04ae38c82c9cb1e37eda`, `/usr/bin/ssh-keygen` 같은 suite·SHA-256 `36fb01d5dbadb0dbbac1fc75e93ebccc399e319d053b0036ee845a5ab0579ab5`, `/usr/bin/ssh-agent` 같은 suite·SHA-256 `e326507e63e5b1ef610ceacd87b3e854ca8cadeee35ddc663bc5a5de8b2febf1`, `/usr/bin/ssh-add` 같은 suite·SHA-256 `dbdfca2d07304e9eab98d1878db1efb5dfddea46be24d643374a415e2071e4f5`를 absolute path로 고정한다. GitHub host는 Ed25519 key `github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl`과 fingerprint `SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU`만 owner-only generated known_hosts에 넣는다. GitHub REST는 GitHub CLI를 거치지 않고 committed CPython transport만 사용한다.

같은 lock은 operation별 HTTPS 경계를 고정한다. Control REST는 `https://api.github.com`, SNI `api.github.com`, redirect 0, API version `2026-03-10`이다. Release asset upload는 create-release response의 URI template을 버리고 exact repository ID·release ID·percent-encoded allowlist name으로 다시 만든 `https://uploads.github.com/repos/<OWNER>/<REPO>/releases/<RELEASE_ID>/assets?name=<NAME>`, SNI `uploads.github.com`, redirect 0만 허용한다. Private asset download는 `https://api.github.com/repos/<OWNER>/<REPO>/releases/assets/<ASSET_ID>`의 status 200 또는 정확히 한 번의 302만 허용한다. 302 Location은 HTTPS, userinfo·fragment 0, host·SNI exact `release-assets.githubusercontent.com`, method GET이어야 하며 두 번째 request에는 Authorization·GitHub API header를 전달하지 않는다. Signed query는 process memory에서만 사용하고 log·trace·ledger·exception·receipt에 URL이나 query를 남기지 않는다. 모든 HTTPS operation의 minimum은 TLS 1.2다. `github_api_transport.py`는 CPython 3.12.13 표준 `http.client`·`ssl`만 사용하고 자동 redirect, `.netrc`, proxy와 ambient CA를 사용하지 않는다.

승인 trust store는 logical `/etc/ssl/certs/ca-certificates.crt`, canonical `/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem`, root:root, mode `0444`, size `218374`, SHA-256 `9c927a9eefb9117fce0228bc5e4c859e9342ef9e6be8fd44246273c54ce69abb` 하나다. `verify_release_tools.py`는 network 전 두 path를 descriptor로 열어 같은 regular file device·inode인지, owner·mode·size·digest가 lock과 같은지 검증한다. Orchestrator는 ambient CA 변수를 제거한 sealed environment에서 검증된 trust bytes와 exact hostname 검증만 transport에 전달한다. Proxy와 위 download 한 번 외 redirect는 허용하지 않는다. Production transport 생성자는 origin·port·trust-store path를 고정하고 test endpoint·test CA 주입을 거부한다. 별도 test-only constructor만 loopback fake TLS와 test CA를 받으며 production call graph에서 import하면 실패한다.

Git SSH는 shell이 해석하는 `GIT_SSH_COMMAND`를 사용하지 않는다. `release-tools.lock.json`은 `/usr/bin/bash` 5.2.15(1)-release·root:root·mode `0755`·size `1440144`·SHA-256 `1168df29c00d1492c60e6fd2f2983cdd2693fa994acb58d0db4ddfafd12e99f1`과 committed `tools/git_ssh_wrapper.sh` blob digest도 고정한다. 모든 network Git argv에는 `-c protocol.version=0`을 넣어 protocol-v2의 extra SSH argument를 끈다. Git에는 `GIT_SSH=<validated-absolute-wrapper>`, `GIT_SSH_VARIANT=ssh`, `SENTINEL_SSH_CONFIG=<validated-absolute-config>`, `SENTINEL_SSH_EXPECTED_REPOSITORY=/hwain-ai/<NAME>.git`, `SENTINEL_SSH_EXPECTED_SERVICE=git-upload-pack|git-receive-pack`만 sealed environment로 준다. Wrapper는 `/usr/bin/bash`의 고정 shebang과 quoted `"$@"`만 사용하고, host가 exact `git@github.com`, 두 번째 argument가 `git-upload-pack '/hwain-ai/<NAME>.git'` 또는 현재 operation의 exact receive-pack 동등값인 두-argument invocation인지 확인한다. Config path를 검증·확정한 뒤 `exec -c /usr/bin/ssh -F "$SENTINEL_SSH_CONFIG" -- "$@"`로 실제 SSH environment를 비운다. Eval, command substitution, PATH lookup과 다른 argument shape는 실행 전 거부한다. Orchestrator는 위 absolute argv만 쓰고 ambient dynamic-loader·proxy·runtime startup·SSH config·known_hosts·askpass를 차단하며, operator key가 든 검증된 agent socket은 T28 credential launcher가 호출 단위로만 주입한다. Tool, trust-store, endpoint 또는 host-key lock 갱신은 별도 보호 PR과 test가 필요하고 실행 중 자동 학습하지 않는다.

`test_release_tools.py`와 `test_github_api_transport.py`는 binary·host-key 반례뿐 아니라 trust-store symlink swap, wrong owner·mode·size·digest, `SSL_CERT_DIR`·다른 `SSL_CERT_FILE`, loader·proxy 주입, wrong control·upload·download origin·SNI, TLS downgrade, upload redirect, download 200·single 302 외 status, second redirect, credential forwarding과 signed-URL persistence를 각각 먼저 실패시킨다. Test-only transport의 loopback fake TLS가 method·path·header·request 수를 검사하고 production constructor는 fake endpoint·test CA를 호출 전 거부한다. Production source·blob digest를 lock과 대조하며 T28 실제 실행 직전에는 인증된 read-only `GET /user` smoke에서 login과 numeric ID를 확인한다. Wrapper test는 inherited `GIT_SSH_COMMAND`, wrong shell·wrapper digest·config, extra argument, 다른 host·repository·service와 shell metacharacter가 SSH spawn 0인지 검사한다. 어느 preflight mismatch에서도 DNS·TLS·GitHub API·Git·SSH external call은 0이어야 한다.

`upstream-git-metadata.json`은 위 고정 표의 HEAD symref·OID, logical ref·peeled target 전체, raw local config와 remote URL·fetchspec의 exact 존재/부재, shallow boundary, 모든 object OID·type·size, reflog path·mode·size·content digest를 canonical array로 저장한다. `verify_upstream_git_metadata.py`는 originals에서 Git write command 0으로 이 set을 재계산한다. Test는 original repo를 수정하지 않고 temporary depth-1 clone fixtures에서 branch·tag·ref target, config·remote·fetchspec, shallow boundary, reachable·unreachable object와 reflog를 하나씩 바꿔 각각 실패시킨다. Index stat cache·lock file 같은 가변 내부 file은 기준이 아니지만 history·ref·object·remote 의미를 구성하는 위 항목은 하나라도 달라지면 실패한다.

- [ ] **단계 4: upstream과 repository 경계 검증**

실행 위치: 각 upstream child repository

실행: `/usr/bin/git rev-parse HEAD && /usr/bin/git status --short --untracked-files=all`

기대: HEAD가 고정 기준과 같고 status에는 격리 과정에서 이미 존재한 `.git_remote_origin_backup`, `LICENSE`만 표시됨

실행 위치: `SENTINEL_SPEC`

실행: `scripts/uv.sh run pytest tests/test_runtime_launchers.py tests/test_commit_inventory.py tests/test_spec_python_launcher.py tests/test_upstream_baseline.py tests/test_upstream_git_metadata.py tests/test_oci_executor.py tests/test_release_tools.py tests/test_github_api_transport.py -q`

기대: 여섯 runtime launcher, commit inventory, cwd 보존 SPEC Python launcher, 4개 verifier와 GitHub transport의 정상 fixture 및 모든 semantic negative가 통과하고 negative case의 external network·Git write·container 호출은 0

실행: `/usr/bin/bash scripts/bootstrap-python.sh && scripts/uv.sh run python tools/verify_upstream_tree.py --baseline baselines/upstream-tree.json ../upstream/unclebob && scripts/uv.sh run python tools/verify_upstream_git_metadata.py --baseline baselines/upstream-git-metadata.json ../upstream/unclebob`

기대: `.git/**`를 제외한 directory·file·symlink의 path·type·mode·size·content 또는 target이 이 계획의 7개 canonical digest와 일치. 새 untracked file, mode 변경, 삭제도 실패. 세 Robert backend의 tracked tar SHA-256도 `baselines/upstream-archive.json`과 위 표에 일치. HEAD·all refs·object set·raw config·remote 부재·shallow boundary·reflog manifest도 `upstream-git-metadata.json`과 위 표에 exact 일치

실행: `scripts/uv.sh run python tools/verify_oci_executor.py --lock clean-install-executor.lock.json --session-output ../build/t01/oci-executor-session.json`

기대: absolute client, local Unix socket identity와 client·server version·API·OS·arch가 exact lock에 일치하고 ambient Docker endpoint·context·TLS·proxy 값은 executor process에 전달되지 않음

실행: `scripts/uv.sh run python tools/verify_release_tools.py --lock release-tools.lock.json`

기대: Git·SSH·ssh-keygen·ssh-agent·ssh-add absolute binary의 version·digest, pinned GitHub Ed25519 host entry와 repo-local CPython transport의 exact API origin·SNI·TLS·trust-store가 일치함. Ambient loader·proxy·CA override·runtime startup·SSH config·agent·askpass와 cross-origin redirect negative fixture는 external call 0에서 실패

실행 위치: 각 `SENTINEL_*` directory

실행: `/usr/bin/bash scripts/verify_repository.sh`

기대: 6개 모두 통과하고 remote 목록은 비어 있음. 각 bootstrap과 launcher self-test가 잘못된 archive digest·installed tree·ABI를 거부하고 exact version을 출력

- [ ] **단계 5: 저장소별 첫 commit**

먼저 실행 위치를 `SENTINEL_SPEC`으로 고정한다. 다른 다섯 root commit을 먼저 만들 수 없다.

```bash
/usr/bin/git check-ignore -q .toolchain
test ! -e .venv
test -z "$(find . -mindepth 1 -maxdepth 1 ! -name .git ! -name .gitignore ! -name .toolchain ! -name README.md ! -name toolchain.lock.json ! -name clean-install-executor.lock.json ! -name release-tools.lock.json ! -name pyproject.toml ! -name uv.lock ! -name docs ! -name scripts ! -name upstream ! -name baselines ! -name tools ! -name tests -print -quit)"
scripts/run-spec-python.sh tools/commit_inventory.py prepare-and-stage --repository . --logical-repository SENTINEL_SPEC --task T01 --phase foundation --unborn-bootstrap --output-root <workspace>/build/commit-inventory -- .
test -z "$(/usr/bin/git ls-files --cached --others --exclude-standard | grep '^\.toolchain/' || true)"
scripts/run-spec-python.sh tools/commit_inventory.py commit-prepared --repository . --logical-repository SENTINEL_SPEC --task T01 --phase foundation --prepared-receipt <PREPARED_RECEIPT> --prepared-receipt-sha256 <PREPARED_RECEIPT_SHA256> --expected-unborn-parent --expected-message "chore: initialize SENTINEL child repository" --foundation-seal <workspace>/build/t01/spec-foundation-seal.json
```

이 블록의 직역:

|요소|입력·판정·출력|
|---|---|
|`/usr/bin/git check-ignore -q .toolchain`|repo-local runtime directory인 `.toolchain`이 Git ignore 규칙에 들어 있는지 조용히 판정한다.|
|`test ! -e .venv`|금지한 root `.venv` 경로가 존재하지 않아야 통과한다. `!`는 존재 판정을 뒤집는다.|
|`find . -mindepth 1 -maxdepth 1 ... -print -quit`|현재 root의 바로 아래 항목 중 명시한 초기 허용 이름이 아닌 첫 항목을 찾는다. `test -z`는 그런 extra 항목 출력이 없는지 판정한다.|
|`prepare-and-stage`, `--logical-repository SENTINEL_SPEC`, `--task T01`, `--phase foundation`, `--unborn-bootstrap`|아직 parent commit이 없는 SPEC root용 registry를 사용해 정확한 foundation 변경만 stage하고 prepared receipt와 foundation seal 준비 정보를 출력한다.|
|`git ls-files --cached --others --exclude-standard`, `grep '^\.toolchain/'`, `|| true`|tracked·untracked 목록에서 `.toolchain/`이 보이는지 찾고, grep이 못 찾은 정상 case도 shell 전체 실패로 바꾸지 않는다. 바깥 `test -z`가 결과가 비었는지 판정한다.|
|`commit-prepared`, `<PREPARED_RECEIPT>`, `<PREPARED_RECEIPT_SHA256>`, `--expected-unborn-parent`|바로 앞 명령이 출력한 준비 영수증과 hash를 입력해 parent 0개인 첫 commit만 허용한다.|
|`--expected-message ...`, `--foundation-seal .../spec-foundation-seal.json`|commit message를 literal text로 고정하고 SPEC commit·registry·tool identity를 VCS 밖 seal에 기록한다.|
|출력|검사가 모두 맞으면 SPEC 첫 commit, committed receipt, foundation seal이 생긴다. extra file, `.toolchain` stage, 잘못된 receipt가 있으면 commit하지 않는다.|

`<SPEC_T01_HEAD>`와 그 commit의 registry·tool blob OID를 봉인한 뒤에만 실행 위치를 각 `SENTINEL_{PY,TS,GO,JAVA,CLJ}` directory로 바꾸고 다음을 실행한다.

```bash
/usr/bin/git check-ignore -q .toolchain
test ! -e .venv
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py prepare-and-stage --repository . --task T01 --phase foundation --unborn --output-root <workspace>/build/commit-inventory -- .
test -z "$(/usr/bin/git ls-files --cached --others --exclude-standard | grep '^\.toolchain/' || true)"
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py commit-prepared --repository . --task T01 --phase foundation --prepared-receipt <PREPARED_RECEIPT> --prepared-receipt-sha256 <PREPARED_RECEIPT_SHA256> --expected-unborn-parent --expected-message "chore: initialize SENTINEL child repository"
```

이 블록의 직역:

|요소|입력·판정·출력|
|---|---|
|입력 위치와 absolute SPEC launcher|현재 위치는 `SENTINEL_PY`, `SENTINEL_TS`, `SENTINEL_GO`, `SENTINEL_JAVA`, `SENTINEL_CLJ` 중 하나다. 이미 봉인한 SPEC Python과 `commit_inventory.py`를 absolute path로 호출한다.|
|`git check-ignore -q .toolchain`, `test ! -e .venv`|runtime directory가 ignored이고 root `.venv`가 없는지 판정한다.|
|`prepare-and-stage --repository . --task T01 --phase foundation --unborn`|현재 새 child repo의 T01 foundation 변경만 stage하고 prepared receipt를 출력한다. 일반 `--unborn`은 SPEC 전용 seal을 새로 만들지 않는다.|
|`git ls-files ... | grep '^\.toolchain/' || true`, `test -z`|`.toolchain` 아래가 tracked·untracked commit 대상에 들어오지 않았는지 판정한다.|
|`commit-prepared`, 준비 영수증 두 placeholder, `--expected-unborn-parent`|stage 출력 경로·hash를 그대로 입력해 parent 없는 첫 commit만 만든다.|
|`--expected-message "chore: initialize SENTINEL child repository"`|다섯 child repo가 같은 정확한 초기화 message를 사용하게 한다.|
|출력|각 실행은 해당 child repo의 root commit과 committed receipt를 만든다. SPEC seal 또는 다른 repo의 영수증을 재사용하면 실패한다.|

### T02: SENTINEL_SPEC 실행·CRAP·mutation gate 계약

**충족 요구사항:** 요구사항-06..요구사항-11, 요구사항-16, 요구사항-21, 요구사항-26, 요구사항-30, 요구사항-31, 요구사항-38, 요구사항-42, 요구사항-43

**파일:**

- 생성: `SENTINEL_SPEC/VERSION`
- 수정: T01의 `pyproject.toml`, `uv.lock`
- 생성: `schemas/config.schema.json`, `schemas/project-key-envelope.schema.json`, `schemas/spec-lock.schema.json`, `schemas/backend-lock.schema.json`, `schemas/result.schema.json`
- 생성: `contracts/cli.md`, `contracts/project-key-injection.md`, `contracts/exit-codes.md`, `contracts/process-safety.md`, `contracts/path-safety.md`, `contracts/result-semantics.md`, `contracts/mutation-states.md`, `contracts/backend-admission.md`
- 생성: `golden/config/*.json`, `golden/project-key/*.json`, `golden/crap/*.json`, `golden/rendering/canonical-decimal/*.json`, `golden/gate/*.json`, `golden/gate/backend-admission/*.json`, `golden/runners/*.json`
- 생성: `tools/validate_result.py`, `tools/vendor_upstream.py`
- 테스트: `tests/test_schemas.py`, `tests/test_config_safety.py`, `tests/test_result_semantics.py`, `tests/test_golden_vectors.py`, `tests/test_vendor_upstream.py`
- 수정: `docs/index.md`, `docs/log.md`, `README.md`

**받는 것:** design의 CLI, 종료 코드 0..8, exact CRAP fraction, 9개 mutant 상태와 killed-only 규칙

**주는 것:** `config`, `spec-lock`, 16-field `backend-lock`, `result`, CRAP, mutation state를 언어 중립 JSON으로 판정할 수 있는 SPEC 0.1 계약

이 task가 처음 만드는 `VERSION` exact bytes는 UTF-8 ASCII `0.1.0-dev.1`과 final LF 한 개다. 공백, BOM과 추가 줄은 금지한다.

- [ ] **단계 0: schema test dependency lock 갱신**

T01의 `pyproject.toml`과 `uv.lock`에 `jsonschema==4.26.0` wheel SHA-256 `d489f15263b8d200f8387e64b4c3a75f06629559fb73deb8fdfb525f2dab50ce`와 uv가 해석한 모든 transitive artifact exact digest를 추가한다. 실행 위치 `SENTINEL_SPEC`에서 `scripts/uv.sh add --no-sync --dev jsonschema==4.26.0 && scripts/uv.sh sync --locked`를 먼저 통과시키고 lock을 다시 생성했을 때 byte가 같음을 확인한다. Version specifier 자체가 exact이므로 uv 0.12.9에 존재하지 않는 `uv add --exact` option은 사용하지 않는다. 이 단계에는 schema, golden file과 `tools/validate_result.py` production 구현을 만들지 않는다. Test dependency import 실패가 아니라 missing contract production 때문에 단계 2가 RED가 되게 한다.

- [ ] **단계 1: 실패하는 schema·oracle test 작성**

```python
from fractions import Fraction
from pathlib import Path
import json
import jsonschema
import pytest

from tools.validate_result import ContractViolation, render_canonical_decimal, validate_result_semantics

ROOT = Path(__file__).parents[1]

def test_result_rejects_zero_mutant_pass():
    schema = json.loads((ROOT / "schemas/result.schema.json").read_text())
    invalid = json.loads((ROOT / "golden/gate/valid-all-killed.json").read_text())
    invalid["mutation"].update({"inScope": 0, "killed": 0, "pass": True})
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid, schema)

def test_semantic_validator_rejects_cross_field_mismatch():
    schema = json.loads((ROOT / "schemas/result.schema.json").read_text())
    invalid = json.loads((ROOT / "golden/gate/valid-all-killed.json").read_text())
    invalid["mutation"].update({"inScope": 2, "killed": 1, "pass": True})
    jsonschema.validate(invalid, schema)
    with pytest.raises(ContractViolation, match="stateCountMismatch"):
        validate_result_semantics(invalid)

def test_crap_boundary_uses_exact_fraction():
    cc, covered, total = 2, 1, 2
    value = Fraction(cc * cc * (total - covered) ** 3 + cc * total ** 3, total ** 3)
    assert value == Fraction(5, 2)
    assert value <= 8

def test_fraction_and_decimal_are_canonical():
    value = Fraction(272, 64)
    assert (value.numerator, value.denominator) == (17, 4)
    assert render_canonical_decimal(value) == "4.25"
    assert render_canonical_decimal(Fraction(1, 3)) == "0.333333333333"
```

Test file은 `pytest`와 semantic validator를 명시적으로 import한다. 완전한 valid result fixture에서 한 invariant만 바꿔 8.0 exact pass·8.0 초과 fail, mutant 0, killed와 inScope 불일치, 9개 상태합 불일치, unknown, timeout-only, compileError-only를 parameterize한다. Required field 누락 때문에 우연히 통과한 negative test는 인정하지 않는다.

`vendor_upstream.py`의 test는 임의 tar member의 absolute path, `..` traversal, hardlink, device·FIFO, destination 밖을 가리키는 symlink와 duplicate path를 거부한다. 정상 archive는 validated temporary directory에만 풀고 path·type·mode·content의 canonical manifest가 T01의 tracked archive baseline과 같을 때 same-filesystem no-replace rename으로 빈 destination에 게시한다. 재실행에서 destination이 이미 있으면 descriptor로 읽은 전체 path·type·mode·content manifest가 expected source commit·archive digest·baseline과 exact일 때만 완료 상태를 write 0으로 채택한다. Partial tree, extra·missing member, symlink, mode·byte·digest 불일치와 검증·rename 전 실패는 destination을 overwrite·delete·repair하지 않고 중단한다. Test는 publish 직전, rename 직후와 receipt 직전 crash를 각각 주입해 complete destination만 채택되고 partial·mismatch는 mutation 0인지 확인한다.

Runner golden은 같은 selection·서로 다른 nonce의 fresh baseline 2회가 모두 pass하고 test ID set이 같을 때만 다음 단계로 가도록 고정한다. 한 번의 failure, missing terminal, nonce reuse, ID mismatch에서는 coverage·candidate·mutant invocation count가 모두 0이어야 한다.

- [ ] **단계 2: 테스트 실패 확인**

실행 위치: `SENTINEL_SPEC`

실행: `scripts/uv.sh run pytest tests/test_schemas.py tests/test_config_safety.py tests/test_result_semantics.py tests/test_golden_vectors.py tests/test_vendor_upstream.py -q`

기대: schema와 golden file 부재로 실패

- [ ] **단계 3: 최소 계약 작성**

`result.schema.json`은 `terminalStatus`, `exitCode`, component 결과를 조건부 schema로 연결하고 mutation pass일 때 아래 count invariant를 요구한다.

```json
{
  "if": {"properties": {"pass": {"const": true}}},
  "then": {
    "properties": {
      "inScope": {"minimum": 1},
      "survived": {"const": 0},
      "uncovered": {"const": 0},
      "timedOut": {"const": 0},
      "compileError": {"const": 0},
      "runtimeError": {"const": 0},
      "pending": {"const": 0},
      "ignored": {"const": 0},
      "toolError": {"const": 0},
      "unauthorizedExclusion": {"const": 0}
    },
    "required": ["inScope", "killed"]
  }
}
```

Schema는 구조와 field 범위를 검증하고 `validate_result_semantics` golden oracle은 `inScope == 9개 상태 count 합`, `killed <= inScope`, pass이면 `inScope >= 1`, `killed == inScope`, 나머지 8개 상태와 무단 제외 0을 검증한다. 5개 runtime은 같은 semantic vectors를 자체 구현으로 통과해야 한다.

Internal CRAP 계산은 arbitrary-precision integer지만 `result.schema.json` wire의 `crapNumerator`는 regex `^(0|[1-9][0-9]*)$`, `crapDenominator`는 `^[1-9][0-9]*$`인 JSON string으로 고정한다. CRAP, coverage와 kill rate exact fraction은 `gcd`로 나눈 기약분수이고 denominator는 양수, zero는 exact `0/1`이어야 한다. Safe-integer CC·coverage unit 상한에서 생기는 값을 수용하도록 numerator·denominator에 각각 `maxLength: 96`, `maxLength: 48`을 두며 초과는 serialization error다. `cyclomaticComplexity`, covered·total units, callable·candidate·mutant·상태·inventory·event count와 epoch처럼 JSON number인 모든 nonnegative integer는 `maximum: 9007199254740991`이고, CC·required inventory는 해당 의미에 따라 minimum 1이다. Canonical JSON byte validator는 fractional·exponent lexical form을 integer field에서 거부한다.

`contracts/result-semantics.md`의 `canonical-decimal-v1`은 nonnegative `n/d`에 대해 integer-only `scaled=n×10^12`, quotient·remainder와 round-half-to-even을 적용하고 최대 12 fractional digit의 trailing zero를 제거한다. Output grammar는 `^(0|[1-9][0-9]*)(\.[0-9]*[1-9])?$`이며 zero는 `0`, integer는 decimal point 없이 쓴다. `coverageFraction`과 `crapRaw`는 reduced fraction을 그대로 render하고 kill-rate percentage만 numerator에 100을 곱힌 뒤 같은 함수를 쓴다. Text와 JSON은 같은 output byte를 재사용하고 locale formatter·binary float·추가 반올림을 금지한다. `golden/crap/fractions/*.json`과 `golden/rendering/canonical-decimal/*.json`은 `17/4 -> 4.25`, `1/3 -> 0.333333333333`, half-even down/up, 12자리 carry, zero·integer, count `2^53-1` valid, `2^53`·`2^53+1` invalid와 80-digit numerator·48-digit denominator의 exact text·JSON equivalence를 포함한다. TypeScript는 bigint를 직접 `JSON.stringify`하지 않고 검증된 decimal string으로 바꾸며 다른 runtime도 같은 byte를 낸다.

같은 contract의 `crap-row-order-v1`은 unknown 우선, known reduced fraction의 arbitrary-precision cross-multiply exact descending, canonical POSIX module-relative path UTF-8 byte lexical ascending, raw valid UTF-8 source의 0-based byte start ascending, callableId UTF-8 byte lexical ascending을 고정한다. Source range는 raw byte의 half-open interval이고 BOM·newline byte도 원본 그대로 센다. Rounded decimal, locale collation, Unicode code point·UTF-16 code unit order와 line/column을 comparator로 쓰지 않는다. `golden/crap/stable-sort/*.json`은 같은 decimal로 보이는 near-equal fraction, 한글·astral path, same start, unknown과 duplicate final key 반례를 포함한다.

`contracts/cli.md`에는 5개 command와 option 조합을, `exit-codes.md`에는 exit 0..8과 precedence를, `mutation-states.md`에는 9개 상태와 backendError 승격 규칙을 기록한다. `backend-admission.md`와 `backend-lock.schema.json`은 `backendName`, `backendVersion|sourceCommit`, `sourceArtifactDigest`, `bridgeVersion`, `bridgePatchDigest`, `supportedRuntime`, `supportedOS`, `mutationDomain`, `operatorInventory`, `operatorInventoryDigest`, `rawStateMapVersion`, `reportSchemaVersion`, `testRunnerProtocolVersion`, `coverageMatcherVersion`, `killConfirmationPolicy`, `isolationMode`의 16개 논리 field를 필수로 만들고 candidate·result ID exact equality, original control, same-mutant replay를 강제한다. 각 실행 저장소의 lock은 backend 하나만 허용한다.

`config.schema.json`은 test·coverage·optional prepare command를 non-empty argv array로만 받고 command string과 shell expansion을 거부한다. Child environment는 SPEC의 변수 이름 allowlist와 literal·secret-reference source만 허용하며 parent environment 전체 상속, ambient backend override와 raw value 기록을 금지한다. Environment contract digest의 canonical HMAC input에는 변수 이름·source·resolved value를 모두 넣되 digest 밖에는 raw value를 저장하지 않는다. 같은 이름·source에서 value가 바뀌면 config·context digest도 바뀐다. `localCacheDir`, coverage·output·raw·export root는 generated-output root로 분류하고 protected production·test·config·VCS·`.sentinel/state-v1`과 overlap, symlink·hardlink·path swap을 거부한다. `prepareCommand`도 source write 권한이 없는 disposable snapshot 안에서만 실행한다.

Stable project key 전달 방식은 raw environment 값, encrypted state restore, parent-only stdin envelope를 비교하고 v1 CLI에는 parent-only stdin envelope를 채택한다. Quality command `crap|mutation|check`에서만 `--project-key-stdin`을 허용하며 stdin은 최대 512-byte canonical JSON object 하나와 EOF만 받는다. `project-key-envelope.schema.json`은 `schemaVersion=sentinel-project-key-v1`, `operation=initialize|rotate`, base64url no-padding 256-bit `key`, JSON safe integer `1..9007199254740991`의 `keyEpoch`만 허용하고 `additionalProperties=false`다. Raw key environment·argv·file path 전달은 금지한다. CLI는 schema validation과 key decode 뒤 stdin을 즉시 닫고 모든 prepare·test·coverage·candidate·backend child stdin을 `/dev/null`로 새로 연결한다. `help`, `doctor`, `history`와 local-details는 이 option을 usageConfigError로 거부하고 stdin을 읽지 않으며 state create·rotate 0이다. Golden은 exact valid initialize·idempotent same key/epoch, same-epoch different key, lower·skipped epoch, same-key rotate, `2^53-1` valid·`2^53`·`2^53+1` invalid, fractional·scientific notation, malformed·oversize·trailing bytes와 rotate crash를 포함한다.

- [ ] **단계 4: 계약 test 통과 확인**

실행: `scripts/uv.sh run pytest tests/test_schemas.py tests/test_config_safety.py tests/test_result_semantics.py tests/test_golden_vectors.py tests/test_vendor_upstream.py -q`

기대: 모든 vector 통과, schema unknown property 거부, 0 mutant pass 거부

- [ ] **단계 5: commit**

```bash
scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py prepare-and-stage --repository . --task T02 --phase contracts --base-head <T02_BASE_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --output-root <workspace>/build/commit-inventory -- VERSION pyproject.toml uv.lock schemas contracts golden tools tests docs README.md
scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py commit-prepared --repository . --task T02 --phase contracts --prepared-receipt <PREPARED_RECEIPT> --prepared-receipt-sha256 <PREPARED_RECEIPT_SHA256> --base-head <T02_BASE_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --expected-message "feat: define executable SENTINEL contracts (요구사항-06..11,26,30,31,38,42)"
```

### T03: SENTINEL_SPEC evidence·history·fingerprint·privacy 계약

**충족 요구사항:** 요구사항-38, 요구사항-45..요구사항-54

**파일:**

- 생성: `schemas/project-state.schema.json`, `schemas/commit-sequence.schema.json`, `schemas/sandbox-lease.schema.json`, `schemas/tree-drained.schema.json`, `schemas/run-started.schema.json`, `schemas/evidence.schema.json`, `schemas/finding-event.schema.json`, `schemas/retention-marker.schema.json`, `schemas/export.schema.json`, `schemas/local-detail.schema.json`
- 생성: `contracts/history.md`, `contracts/fingerprints.md`, `contracts/process-guardian.md`, `contracts/sandbox-control-layout.md`, `contracts/privacy-allowlist.md`, `contracts/raw-report.md`, `contracts/local-details.md`
- 생성: `golden/state/*.json`, `golden/commit-sequence/*.json`, `golden/sandbox-leases/*.json`, `golden/tree-drained/*.json`, `golden/sandbox-control-layout/*.json`, `golden/lifecycle/*.json`, `golden/retention/*.json`, `golden/cache-partial/*.json`, `golden/fingerprints/*.json`, `golden/privacy/*.json`
- 테스트: `tests/test_evidence_contract.py`, `tests/test_commit_sequence_contract.py`, `tests/test_sandbox_lease_contract.py`, `tests/test_tree_drained_contract.py`, `tests/test_sandbox_control_layout.py`, `tests/test_lifecycle_vectors.py`, `tests/test_privacy_vectors.py`
- 생성: `docs/privacy.md`
- 수정: `docs/index.md`, `docs/log.md`, `README.md`

**받는 것:** T02의 version·terminal status 계약

**주는 것:** started·completed run, runId·correlationId, append-only event, HMAC fingerprint, retention·prune, local cache·partial, raw-dir, redacted export와 local-only locator의 기계 계약

- [ ] **단계 1: lifecycle과 privacy 실패 test 작성**

```python
FORBIDDEN = [
    b"SOURCE_CANARY_def_secret_function",
    b"MUTANT_REPLACEMENT_CANARY_return_false",
    b"SECRET_CANARY_7f20",
    b"ENV_VALUE_CANARY_8841",
    b"ABS_PATH_CANARY_/home/private/project",
    b"REPO_URL_CANARY_github.com/private/repo",
    b"USERNAME_CANARY_hwain",
    b"STDOUT_CANARY_backend_out",
    b"STDERR_CANARY_backend_err",
    b"STACK_CANARY_at_private_symbol",
    b"RAW_REPORT_CANARY_mutant_123",
]

def test_repeated_requires_two_completed_fresh_runs(fold_fixture):
    result = fold_fixture("same-run-retry.json")
    assert result["observationCount"] == 1
    assert result["repeated"] is False

def test_public_bundle_contains_no_forbidden_bytes(render_fixture):
    canary_input = build_privacy_canary_input(FORBIDDEN)
    public_bytes = render_fixture(canary_input)
    assert all(value not in public_bytes for value in FORBIDDEN)

def test_three_runs_share_correlation_but_not_run_id(run_fixture):
    rows = run_fixture("fail-fix-pass.json")
    assert len({row["runId"] for row in rows}) == 3
    assert len({row["correlationId"] for row in rows}) == 1
```

공통 acceptance matrix는 started-only incomplete run, `detected`·`persisted`·`resolved`·`reopened`, 같은 run retry 0 observation, cache replay 0 event·0 observation, local partial의 `certification:false`와 기존 strict evidence 불변, strict cache read 0, completed·incomplete UTC cutoff equality와 prune crash, key epoch 분리를 포함한다. Fingerprint golden은 5개 언어별 semantic site에 whitespace·line insert, anonymous node reorder와 backend ID renumber를 적용해 occurrence가 유지되는지, backend version·config만 바꾸면 occurrence·family는 유지되고 context만 바뀌는지, defect kind·operator category가 바뀌면 family와 해당 occurrence가 바뀌는지 검증한다. Python same-name 재정의, TypeScript overload 선언과 구현, Go의 서로 다른 receiver에 있는 같은 method 이름, Java overload descriptor, Clojure multi-arity defn의 identity도 expected inventory로 고정한다. Descriptor duplicate는 `identityAmbiguous`로 끝나고 fingerprint record가 0개여야 한다. Raw report는 default 0개이며 `--raw-dir` opt-in만 owner-only permission을 허용한다. `history --export`는 network 0, allowlist-only이고 write 실패가 기존 quality result를 바꾸지 않아야 한다.

Sandbox lease acceptance는 producer runtime 5개가 남긴 guardian live·drained·SIGKILL, zombie·PID-reused·unknown diagnostic과 consumer runtime 5개의 next-run cleanup·`history prune --incomplete` 조합을 위한 언어 중립 vector를 둔다. `/proc` all-dead만으로 삭제할 수 없고 valid HMAC tree-drained marker가 descendant 0의 유일한 자동 삭제 증거다. Sandbox quarantine은 valid marker+age-expired, incomplete prune은 valid marker+started-before-cutoff+completed 부재에서만 가능하다. Marker missing·guardian crash·HMAC mismatch는 cross-boot에서도 no-touch다. Lease path·raw source·report는 공용 evidence·export에 나타나지 않는다.

11종 raw forbidden canary byte는 `tests/test_privacy_vectors.py`가 test runtime의 owner-only temporary directory에서 합성하며 `golden/privacy/**`에는 canary가 제거된 canonical expected output만 둔다. T04 release allowlist의 contract·golden bytes와 SPEC archive에는 raw source, mutant replacement, secret, path, URL, username, stdout·stderr·stack·raw-report canary가 0개여야 한다.

- [ ] **단계 2: 실패 확인**

실행: `scripts/uv.sh run pytest tests/test_evidence_contract.py tests/test_commit_sequence_contract.py tests/test_sandbox_lease_contract.py tests/test_tree_drained_contract.py tests/test_sandbox_control_layout.py tests/test_lifecycle_vectors.py tests/test_privacy_vectors.py -q`

기대: evidence schema·fixture 부재로 실패

- [ ] **단계 3: 최소 schema와 canonical vector 구현**

`finding-event.schema.json`은 event를 다음 union으로 제한한다.

```json
{
  "type": "object",
  "properties": {
    "event": {"enum": ["detected", "persisted", "resolved", "reopened"]},
    "findingClass": {"enum": ["projectCode", "projectTest", "projectCodeOrTest", "backend", "sentinel", "environment"]},
    "defectKind": {"type": "string", "pattern": "^[a-z][A-Za-z0-9]{0,63}$"},
    "diagnosticCode": {"type": "string", "pattern": "^[a-z][A-Za-z0-9]{0,63}$"},
    "findingToken": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
    "fingerprintKind": {"enum": ["occurrence", "context", "family"]},
    "fingerprintVersion": {"type": "string"},
    "value": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
    "observationSource": {"const": "fresh"}
  },
  "required": ["event", "findingClass", "defectKind", "diagnosticCode", "findingToken", "fingerprintKind", "fingerprintVersion", "value", "observationSource"],
  "additionalProperties": false
}
```

`contracts/fingerprints.md`는 `canonicalizationVersion=sentinel-fingerprint-json-v1`을 고정한다. Fingerprint input object의 key는 SPEC에 열거된 ASCII key만 허용하고 UTF-8 encoded key byte 오름차순으로 정렬한다. Array는 의미상 순서를 보존하되 set field는 element canonical byte로 먼저 정렬한다. String은 Unicode normalization을 하지 않은 유효 Unicode scalar sequence 그대로 UTF-8로 내보낸다. `"`, `\`만 backslash escape하고 U+0000..U+001F는 lowercase `\u00xx` 6-byte form, `/`와 그 밖의 non-ASCII scalar는 escape하지 않는다. Whitespace, BOM, trailing newline, duplicate key, unpaired surrogate와 invalid UTF-8은 금지한다. Boolean·null은 lowercase literal이고 허용된 safe integer는 sign 없는 base-10, leading zero·fraction·exponent 없는 form이다. Runtime의 기본 map iteration, locale sort나 language JSON serializer option에 맡기지 않는다.

`golden/fingerprints/canonical-bytes/*.json`은 synthetic 256-bit key, logical input, expected canonical UTF-8 hex와 occurrence·context HMAC-SHA-256 또는 family SHA-256 expected hex를 함께 둔다. Key order permutation, quote·slash·backslash·NUL·newline, Korean non-ASCII, composed `é`와 decomposed `e`+combining acute가 서로 normalization되지 않는 vector, astral scalar, invalid surrogate·UTF-8·duplicate key를 포함한다. 5개 runtime은 logical input에서 expected byte를 독립 생성한 뒤 expected digest를 비교하고, expected fixture를 자기 serializer 출력으로 다시 쓰지 못한다.

`project-state.schema.json`은 private `.sentinel/state-v1/project.json`의 공통 byte 계약이다. `stateVersion=state-v1`, schema version, base64url no-padding 128-bit project identifier, base64url no-padding 256-bit fingerprint HMAC key, 별도 base64url no-padding 256-bit `cleanupLeaseKey`와 JSON safe integer `1..9007199254740991`의 monotonic `keyEpoch`만 허용하고 `additionalProperties=false`다. Fingerprint key는 승인된 envelope로 rotate할 수 있지만 project identifier와 cleanupLeaseKey는 project lifetime 동안 불변이다. `golden/state/**`에는 actual secret이 아닌 명시적 synthetic key vector와 invalid length·encoding·epoch 반례만 둔다. Semantic oracle은 두 key가 run·evidence·finding·history·export·artifact schema로 이동하는 것을 거부한다.

State와 sandbox lease의 `keyEpoch`·`fingerprintKeyEpochAtCreation`도 envelope와 같은 JSON safe integer `1..9007199254740991`만 허용한다. `golden/state/**`와 `golden/sandbox-leases/**`는 `2^53-1` valid, `2^53`·`2^53+1`·fraction·scientific notation invalid를 고정하고 모든 runtime parser가 동일하게 거부하는지 검사한다.

Quality command가 T02 `--project-key-stdin` envelope를 받으면 state exclusive lock 안에서 적용한다. State가 없을 때 `operation=initialize`만 새 CSPRNG project identifier·cleanupLeaseKey와 envelope fingerprint key·epoch으로 owner-only `project.json`을 exclusive-create·file-sync·directory-sync한다. Existing state에서 같은 key·epoch initialize는 idempotent read이고 write 0이다. Same epoch의 다른 key, lower epoch, `current+1`을 건너뛴 epoch, 같은 key rotate와 initialize로 epoch를 올리는 요청은 test·coverage·backend 전에 usageConfigError다. `operation=rotate`는 다른 fingerprint key와 정확히 `currentEpoch+1`만 받아 project identifier·cleanupLeaseKey bytes를 그대로 유지한 owner-only temporary write·file-sync·same-directory atomic rename·directory-sync를 수행한다. Rename 전 crash는 old complete state, rename 뒤 directory-sync 전 crash는 old 또는 new complete state만 허용하고 command는 evidenceError이며 partial·mixed key는 0이다. Retry는 실제 complete state와 envelope를 대조해 idempotent하게 끝낸다. Old epoch evidence는 그대로 보존하고 repeated·lifecycle 비교에 새 epoch를 섞지 않는다. Envelope key bytes와 cleanupLeaseKey는 child, environment-contract digest, log, cache, 공용 schema와 artifact로 전달하지 않는다.

`commit-sequence.schema.json`은 private `.sentinel/state-v1/commit-sequence.json`을 `version=commit-sequence-v1`, leading-zero-free uint64 decimal string `lastAllocated`, lowercase 64-hex `hmacSha256`, `additionalProperties=false`로 고정한다. `sequenceMacKey=HMAC-SHA-256(cleanupLeaseKey, ASCII "SENTINEL\\0commit-sequence-key\\0v1\\0")`이고 MAC input은 `ASCII "SENTINEL\\0commit-sequence\\0v1\\0" || canonicalSequenceBody`다. Body는 HMAC field를 제외한 canonical JSON이고 file은 HMAC field를 포함한 canonical JSON 한 줄+final LF다. Terminal commit은 exclusive `commit.lock` 아래 이 file의 HMAC과 `lastAllocated >= max(retained completed commitSequence, every retention marker sequenceHighWaterAtCommit)`를 먼저 증명한다. File이 없는 fresh state는 completed bundle과 retention marker가 모두 0개일 때만 허용한다. 다음 uint64 값을 배정해 sequence file temporary write·file sync·same-directory rename·state directory sync를 evidence write보다 먼저 끝낸다. 그 뒤 crash가 나면 gap은 허용하지만 번호 재사용은 금지한다. Uint64 max에서는 event·evidence write 0의 `evidenceError`다. 각 terminal `evidence.json`과 그 manifest에 속한 모든 event는 같은 `commitSequence`를 required로 가지며 lifecycle fold와 latest/current는 이 값만으로 정렬한다. `committedAtUtc`와 event UTC는 표시와 retention cutoff에만 쓰고 순서를 정하지 않는다. Missing·zero·leading-zero·overflow, duplicate completed sequence, event-evidence mismatch, sequence HMAC 변조·rollback 또는 high-water보다 큰 retained evidence는 history·commit·prune 모두 exit 7, write·delete 0이다. `golden/commit-sequence/**`는 same·backward UTC, allocation crash gap, retained evidence·retention high-water rollback, duplicate와 numeric 경계를 고정한다.

`sandbox-lease.schema.json`은 owner-only temp sandbox와 incomplete run이 공유하는 private `sandbox-lease-v1` byte 계약이다. Required field는 `runId`, producer language, stable cleanup-key HMAC `projectToken`, `fingerprintKeyEpochAtCreation`, createdAtUtc, `createdUtcSyncProof=linux-adjtimex-synchronized-v1|unknown`, valid proof일 때만 필요한 leading-zero-free uint64 decimal `createdUtcUncertaintyNanos`, `ageClockId=linux-clock-boottime-v1`, Linux `clock_gettime(CLOCK_BOOTTIME)` creation nanoseconds, cleanup-key HMAC `bootToken`, PID namespace identity, process-group ID, controller·leader·known descendant 각각의 PID와 `/proc/<pid>/stat` start identity, sandbox device·inode, lease generation과 `cleanupAgePolicy=sandbox-orphan-age-v1`이다. Cross-runtime 정밀도를 위해 boottime nanoseconds, UTC uncertainty, device, inode, PID namespace inode, PID, process-group ID, process start tick과 lease generation은 JSON number가 아니라 leading zero 없는 unsigned decimal string으로 직렬화한다. Semantic oracle은 boottime과 uncertainty만 `0..18446744073709551615`, PID·process-group ID는 `1..2147483647`, device·inode·namespace inode·process start tick·lease generation은 `1..18446744073709551615` 범위를 검사한다. Zero PID·PGID·generation 같은 corrupt identity는 절대로 signal·delete argument로 전달하지 않는다. `golden/sandbox-leases/numeric-boundaries/*.json`은 `0`, `1`, `2^53-1`, `2^53`, `2^53+1`, uint64 max와 overflow·negative·leading-zero 및 PID signed-int overflow 반례를 고정한다. Java `System.nanoTime()`, Go의 process-local monotonic component, Node·Python process-local clock origin과 floating-point 변환은 lease age에 사용할 수 없다. `projectToken` canonical input은 ASCII `SENTINEL\0sandbox-project-token\0v1\0` 뒤 decoded 16-byte projectIdentifier이고 `bootToken` input은 ASCII `SENTINEL\0sandbox-boot-token\0v1\0` 뒤 lowercase canonical 36-byte Linux boot UUID다. 둘 다 HMAC-SHA-256 key는 불변 cleanupLeaseKey이고 output은 lowercase 64-hex다. `golden/sandbox-leases/tokens/*.json`은 synthetic key·project ID·boot UUID와 expected input hex·token을 고정한다. V1 policy는 same boot에서 unsigned exact integer로 계산한 boottime age가 `86400`초를 엄격히 초과할 때, boot mismatch에서는 synchronized UTC의 conservative lower age가 `604800`초를 엄격히 초과할 때만 sandbox age-expired다. Equality는 보존한다. Same boot는 UTC를 sandbox age 근거로 쓰지 않고 current boottime이 creation보다 작거나 syscall을 지원하지 않으면 unknown이다. Cross-boot proof와 age 식은 아래 `sampleUtcWithSyncProof` 계약을 그대로 사용한다. Creation proof가 unknown이거나 uncertainty가 없고, current proof 또는 bracket이 unknown이며 conservative current lower bound가 creation upper bound보다 과거인 경우도 unknown이다. Absolute path, source·raw report byte와 secret key field는 금지하고 `additionalProperties=false`다. Golden은 exact live, leader dead·descendant live, exact PID reuse, fingerprint key rotation 뒤 stable projectToken join, boot mismatch, `/proc` unreadable unknown, 각 sandbox threshold 직전·equality·초과, UTC rollback·unsynchronized clock, HMAC provider failure, corrupt·duplicate descendant를 포함한다. Linux `/proc/<pid>/stat`은 `comm` 내부의 공백과 `)`를 허용하도록 line의 마지막 `)` 뒤에서 state와 뒤 field를 분리하고 start time field를 exact unsigned decimal로 읽는다. Namespace·PID·start identity가 exact인 entry도 state가 `Z` 또는 `X`이면 signal 없이 dead다. 그 밖의 state는 exact identity일 때 live, entry unreadable·사라짐과 재시도 경계가 모호하거나 parse가 불완전하면 unknown이다. PID는 같지만 namespace 또는 start identity가 다르면 old leased identity는 dead이며 재사용 process에는 signal을 보내지 않는다. Tree fold는 하나라도 live면 live, live 없이 하나라도 unknown이면 unknown, 전부 dead일 때만 dead인 diagnostic이다. 다른 runtime이 읽어도 같은 `/proc` diagnostic과 tree-drained marker HMAC·lease join 결과를 내야 한다. Automatic deletion의 descendant 0 근거는 diagnostic all-dead가 아니라 valid `tree-drained-v1` marker다. `mayQuarantineSandbox`는 valid marker와 sandbox age-expired가 모두 필요하다. `mayPruneIncompleteRun`은 valid marker, `startedAtUtc < cutoffUtc`, completed evidence 부재만 필요하며 sandbox age와 무관하다. `startedAtUtc == cutoffUtc`, marker missing·HMAC failure·guardian crash·corrupt lease는 incomplete run delete 0이다. Lease missing은 run phase가 guardian과 외부 child start 전임을 durable state로 증명할 때만 dead, 그 밖에는 unknown이다. Golden은 괄호·공백이 든 `comm`, exact zombie `Z`, dead `X`, malformed stat와 read 도중 disappearance을 별도 vector로 고정한다.

Lease 전체도 authenticated byte contract다. Schema는 lowercase 64-hex `hmacSha256`을 required로 추가한다. `leaseMacKey=HMAC-SHA-256(cleanupLeaseKey, ASCII "SENTINEL\\0sandbox-lease-key\\0v1\\0" || ASCII leading-zero-free leaseGeneration)`이고, MAC input은 `ASCII "SENTINEL\\0sandbox-lease\\0v1\\0" || canonicalLeaseBody`다. `canonicalLeaseBody`는 `hmacSha256` field만 제외한 모든 lease field를 T03 `sentinel-fingerprint-json-v1`로 직렬화한 exact UTF-8 bytes이며 final LF를 포함하지 않는다. File은 HMAC field까지 포함한 canonical JSON 한 줄+final LF이고 parse 후 재직렬화 byte가 원본과 다르면 거부한다. 따라서 createdAtUtc·sync proof·boottime·bootToken, 모든 controller·guardian·descendant identity, control root·leaf·sandbox device/inode, generation·age policy와 future schema field가 하나라도 바뀌면 HMAC mismatch로 signal·rename·delete 0이다. `golden/sandbox-leases/mac/*.json`은 synthetic cleanup key, derived-key input/output hex, full canonical body/input hex, expected MAC/file hex와 field order·timestamp·clock·identity·path selector·mode·extra·duplicate·HMAC tamper 반례를 고정한다.

Process containment의 진실 공급원은 `linux-subreaper-pidfd-v1` guardian과 HMAC-authenticated `tree-drained-v1` marker다. Lease의 추가 required field는 guardian PID namespace·PID·`/proc` start identity, guardian executable digest, drain protocol과 marker version이다. Controller는 first-party guardian을 spawn하고 guardian은 `prctl(PR_SET_CHILD_SUBREAPER, 1)` 성공 뒤 gate-wrapper를 자기 direct child로 spawn한다. Backend의 모든 descendant는 guardian의 descendant여야 한다. `setsid`, double-fork와 nested PID namespace를 써도 조상 관계는 벗어날 수 없다. Guardian은 controller command socket EOF를 crash로 인식해 emergency drain을 시작한다. Guardian SIGKILL·power loss, identity 불명 또는 marker 부재는 process가 나중에 사라져도 영구 unknown·automatic delete 0이며 private diagnostic과 수동 정리만 허용한다. 이 보수적 공간 누수는 다른 project나 살아 있는 process를 지울 가능성보다 우선한다.

Controller는 `drainMarkerKey=HMAC-SHA-256(cleanupLeaseKey, ASCII "SENTINEL\\0tree-drained-key\\0v1\\0" || ASCII leading-zero-free leaseGeneration)`을 계산해 raw cleanupLeaseKey 대신 guardian-only bounded anonymous channel로 한 번 전달한다. Guardian은 `PR_SET_DUMPABLE=0`을 적용하고 key FD를 backend에 상속하지 않으며 key bytes를 marker·log·argv·environment에 남기지 않는다. Guardian은 direct child마다 `pidfd_open`을 즉시 수행하고 namespace·start identity와 맞춘다. Drain 중에는 guardian-owned direct child만 pidfd로 TERM 뒤 KILL하고, child가 종료되어 adopted descendant가 direct child가 될 때마다 새 pidfd를 얻어 같은 절차를 반복한다. `waitid(P_PIDFD, ...)`로 모두 reap한 뒤 `waitid(P_ALL, ..., WNOHANG)`이 `ECHILD`임을 확인해야 descendant 0이 증명된다. 그 뒤에만 canonical `tree-drained-v1` marker를 guardian-held validated directory FD에 exclusive-create·file sync하고 directory sync한 다음 key를 zeroize하고 종료한다.

`tree-drained.schema.json`은 `version=tree-drained-v1`, canonical lowercase UUID runId, projectToken, leaseGeneration, guardian namespace inode·PID·start tick, guardian executable SHA-256, `drained=true`, `hmacSha256`만 required로 허용하고 `additionalProperties=false`다. 숫자 field는 lease와 같은 leading-zero-free decimal string이다. MAC input은 exact byte sequence `ASCII "SENTINEL\\0tree-drained-marker\\0v1\\0" || runId(36 ASCII) || 0x00 || projectToken(64 lowercase-hex ASCII) || 0x00 || leaseGeneration(decimal ASCII) || 0x00 || guardianNamespaceInode(decimal ASCII) || 0x00 || guardianPid(decimal ASCII) || 0x00 || guardianStartTick(decimal ASCII) || 0x00 || guardianExecutableSha256(64 lowercase-hex ASCII) || 0x00 || ASCII "true"`이고 output은 lowercase 64-hex다. Marker file 자체는 T03 `sentinel-fingerprint-json-v1` key ordering·string·whitespace 규칙의 canonical JSON 한 줄과 final LF로 고정하고, parse 후 다시 만든 canonical bytes가 원본과 다르면 거부한다. 다음 runtime은 cleanupLeaseKey로 derived key·MAC을 다시 계산하고 모든 field를 lease와 exact join한다. `golden/tree-drained/*.json`은 synthetic cleanup key, lease generation, derived-key input·output hex, marker MAC input hex·expected HMAC와 canonical file hex를 고정하고 field order·encoding·case·leading zero·extra·duplicate·tamper와 HMAC provider failure 반례를 포함한다. Marker write·file sync·directory sync 전 crash는 marker absent로만 보이고 delete 0이다.

Cross-runtime discovery는 `sandbox-control-layout-v1` 하나로 고정한다. Ambient `TMPDIR`, `TEMP`, `TMP`와 runtime 기본 temp API는 무시한다. Approved root candidate는 순서대로 `/run/user/<decimal getuid>/sentinel-v1`과 `/tmp/sentinel-v1-u<decimal getuid>`뿐이며 consumer는 두 곳을 모두 scan한다. `/run/user/<uid>`는 current UID 소유·mode `0700`, `/tmp`는 root 소유·sticky mode `01777`의 실제 directory여야 한다. 그 아래 SENTINEL root는 current UID 소유·mode `0700`, local filesystem이고 opened descriptor의 device·inode가 path 재확인과 같아야 한다. Directory link count는 child directory 수에 따라 달라지므로 고정값으로 판정하지 않는다. Regular control file만 link count 1을 요구한다. Producer는 첫 usable candidate를 사용하되 consumer는 환경 변수와 관계없이 두 canonical candidate를 검사한다.

Active control leaf relative layout은 exact `projects/p-<projectToken>/runs/r-<lowercase UUID runId>/g-<leading-zero-free leaseGeneration>/`이다. Allowed phase entry는 pre-drain의 `sandbox/`+`sandbox-lease.json`, drained pre-cleanup의 `sandbox/`+`sandbox-lease.json`+`tree-drained.json`, sandbox-cleaned tombstone의 `sandbox-lease.json`+`tree-drained.json` 세 set뿐이다. Lease의 추가 required field는 `controlRootKind=run-user|tmp`, decimal `controlRootDevice`·`controlRootInode`, exact `controlLeafRelative`, decimal leaf device·inode와 `sandboxRelativeName=sandbox`다. Absolute path는 저장하지 않는다. Traversal은 validated root FD에서 `openat2` beneath·no-symlink·no-magic-link와 opened-object `fstat`만 쓰고 lexical component와 lease의 projectToken·runId·generation·device·inode를 exact join한다. 두 root의 duplicate logical leaf, phase 밖 extra·missing control entry, malformed component, wrong owner·mode, regular-file link count mismatch, hardlink·symlink, root/leaf swap과 foreign projectToken은 ambiguous unknown·read/write/rename/delete 0이다. Consumer는 authenticated current projectToken과 일치하는 leaf만 판단하며 다른 project leaf를 signal하거나 정리하지 않는다.

Valid marker와 age-expired를 확인한 cleanup은 control leaf가 아니라 그 안의 `sandbox/` directory만 같은 approved root의 exact `quarantine/p-<projectToken>/runs/r-<runId>/g-<leaseGeneration>-d-<sandboxDevice>-i-<sandboxInode>/`로 `renameat2(RENAME_NOREPLACE)`한다. `sandbox-lease.json`과 `tree-drained.json` tombstone은 later incomplete prune이 인증할 수 있도록 active control leaf에 남긴다. Quarantine의 project·runs·run parent는 validated descriptor 아래 owner-only로 만들고 각 directory를 sync한 뒤 rename하며 target이 이미 있으면 clobber하지 않는다. Rename 뒤 active leaf parent와 quarantine parent directory를 모두 sync하기 전 recursive delete는 0이다. Crash resume는 active control tombstone과 quarantine을 함께 scan해 lease·marker HMAC, root kind, projectToken·runId·generation과 unchanged sandbox device·inode를 다시 join한 경우만 quarantine FD 아래를 삭제한다. Active sandbox와 quarantine target이 동시에 있거나 tombstone missing·target identity mismatch·unknown entry·partial parent면 no-delete다.

Control tombstone은 corresponding run이 valid completed evidence를 가진 경우 또는 marker-first incomplete prune이 whole run bundle delete를 끝낸 경우에만 descriptor-relative delete할 수 있다. Sandbox cleanup이 먼저 끝나도 incomplete run과 control tombstone은 유지되어 later `history prune --incomplete`가 valid marker를 재사용한다. Tombstone delete crash는 sandbox·run bundle을 되살리거나 다른 leaf를 건드리지 않고 다음 scan이 same runId·generation에 대해 idempotent하게 끝낸다. `golden/sandbox-control-layout/*.json`과 actual path-swap test는 두 root 선택·fallback, ambient temp canary 무시, phase별 active entry, sandbox-only quarantine, delayed incomplete prune, no-replace crash resume, duplicate root/leaf, foreign leaf와 identity race를 고정한다.

Phase oracle은 exact entry set으로 `active={sandbox,lease}`, `drained={sandbox,lease,marker}`, `quarantining={lease,marker}+matching quarantine sandbox`, `sandboxRemoved={lease,marker}`를 구분한다. Marker 없는 sandbox absence, marker만 또는 lease만 남은 control leaf와 active sandbox+quarantine duplicate는 unknown·no-delete다. Eligible tombstone은 generation control leaf 전체를 same root의 `retired/p-<projectToken>/runs/r-<runId>/g-<generation>-d-<leafDevice>-i-<leafInode>/`로 no-replace rename하고 active·retired parent를 sync한 뒤만 descriptor-relative delete한다. Retired crash resume는 intact lease+marker HMAC과 unchanged leaf identity가 있을 때만 계속한다. Corrupt·partial retired tombstone은 작은 영구 누수로 남기고 sandbox나 run bundle이 남았다고 추측하지 않는다. Golden과 25조합은 `active -> drained -> quarantining -> sandboxRemoved -> retired -> absent`, 각 sync crash와 sandbox cleanup 뒤 later incomplete prune 순서를 고정한다.

숫자 PID·PGID를 `kill`, `killpg`, `tgkill` 또는 shell command에 넘기는 것은 production 전체에서 금지한다. Signal은 guardian-owned child의 pidfd에 `pidfd_send_signal`로만 보낸다. PID read, pidfd open, identity join, signal, wait와 adoption 어느 경계에서 오류·identity change가 나면 unrelated signal 0, tree-drained marker 0의 `toolError`다. `mayQuarantineSandbox`는 valid tree-drained marker와 sandbox age-expired가 모두 필요하다. `mayPruneIncompleteRun`은 valid tree-drained marker, `startedAtUtc < cutoffUtc`, completed evidence 부재가 모두 필요하고 sandbox age와 무관하다. Golden과 syscall trace는 PID reuse race에서 numeric signal syscall 0과 unrelated canary 생존, guardian drain success, guardian SIGKILL 뒤 age-expired no-delete를 고정한다.

위 UTC proof의 호출 단위는 Clock의 `sampleUtcWithSyncProof` 하나다. 이 method 안에서만 `CLOCK_MONOTONIC_RAW before -> zero-filled modes=0 adjtimex before -> CLOCK_REALTIME sample -> 새 zero-filled modes=0 adjtimex after -> CLOCK_MONOTONIC_RAW after`를 실행한다. Adjtimex return은 `-1`·`TIME_ERROR(5)`가 아니고 status에 `STA_UNSYNC(0x0040)`·`STA_CLOCKERR(0x1000)`가 없어야 한다. `STA_NANO(0x2000)`에 따라 timex subsecond를 1ns 또는 1000ns 단위로 정규화하고 invalid range·signed overflow를 거부한다. `beforeUtc <= sampleUtc <= afterUtc`, raw span `0..1,000,000,000ns`, realtime span >= 0, `realtimeSpan <= rawSpan + max(before.maxerror,after.maxerror)*1000 + 1,000,000ns`를 모두 만족해야 한다. 반환 uncertainty는 `maxErrorNanos + rawSpan + 1,000,000`이고 sample UTC·proof와 한 immutable result로 묶는다. Cross-boot age는 `currentSample-currentUncertainty-(createdAt+createdUncertainty) > 604800s` exact integer일 때만 만료다. Equality·overflow·bracket 위반은 unknown이다. Golden은 `STA_NANO` on/off, micro·nano subsecond 경계, maxerror, 1초 raw span 경계, forward·backward step과 허용 1ms 직전·equality·초과를 byte 단위로 고정한다. Separate `utcNow`와 나중에 얻은 sync flag를 조합하거나 중간 clock step을 무시하는 구현은 금지한다.

Child start gate는 `sandbox-start-gate-v1` one-byte protocol이다. Guardian은 `pipe2(O_CLOEXEC)`로 pipe를 만들고 새 process group의 고정 gate-wrapper executable을 spawn한다. `posix_spawn` file action의 `dup2` 또는 동등한 explicit pass-fd가 child read end를 미리 정한 다른 descriptor로 복제하며, 그 복제본에서만 `FD_CLOEXEC`를 해제한다. Guardian write end와 원 read end를 포함한 다른 모든 copy는 wrapper에 상속하지 않는다. Wrapper는 어떤 sandbox path open·chdir이나 test·coverage·backend code load 전에 최대 60초의 process-monotonic deadline으로 gate bytes와 EOF를 읽는다. 정확히 `0x47` 한 byte 뒤 EOF인 경우에만 gate FD를 닫고 backend argv를 `exec`한다. EOF-only, short·wrong·extra byte, read error, timeout과 다른 process에 write FD가 leak되어 EOF가 오지 않는 경우는 backend·sandbox access 0에서 bounded self-exit한다. 순서는 `guardian spawn -> subreaper 확인 -> wrapper spawn -> guardian·wrapper namespace/PID/start identity를 controller에 전달 -> canonical lease exclusive-create/write -> lease file sync -> lease directory sync -> controller durable-lease ACK -> guardian 0x47 write -> guardian write end close`다. ACK 전 controller SIGKILL·power loss는 command socket EOF를 본 guardian이 GO 없이 writer를 닫고 wrapper를 reap하므로 unleased backend 실행 0이다. GO 뒤 controller crash는 durable lease와 살아 있는 guardian이 반드시 존재한다. 각 runtime은 real guardian·wrapper child와 syscall trace로 상속 FD set, leaked-writer timeout과 모든 경계를 검사하고 gate 실패를 성공으로 normalize하지 않는다.

Exact `retention-marker-first-v1`은 completed와 incomplete prune 모두 `exclusive commit lock -> exact selection·cutoff 재확인 -> owner-only marker temporary exclusive-create/write -> marker file sync -> validated same-directory atomic rename -> retention directory sync -> selected whole-bundle descriptor-relative delete` 순서를 지킨다. 모든 marker는 kind, cutoffUtc, selectionCount, commit lock 아래 관측한 `sequenceHighWaterAtCommit`과 marker HMAC을 가진다. Marker key는 `HMAC-SHA-256(cleanupLeaseKey, ASCII "SENTINEL\\0retention-marker-key\\0v1\\0" || canonical pruneId)`이고 MAC은 HMAC field를 제외한 canonical marker body에 domain `SENTINEL\\0retention-marker\\0v1\\0`을 붙여 계산한다. Marker directory sync 전에는 selected run delete가 0이어야 한다. Completed marker는 그 뒤 `(commitSequence <= sequenceHighWaterAtCommit && committedAtUtc < cutoffUtc)` pair logical view를 먼저 활성화한다. 여러 completed marker는 pair predicate의 union이고 max cutoff 단독 filter는 금지한다. Delete 도중 crash해 일부 physical bundle이 남아도 `history`는 같은 pair windows, 보수적 안내용 `historyLowerBound`, `truncated=true`와 logical result를 보여야 하고 재실행은 남은 pair-eligible bundle만 idempotent delete한다. Marker 뒤 더 큰 sequence로 terminal commit한 run은 UTC가 rollback해 cutoff 전이어도 보존한다.

`golden/retention/completed-window-boundaries.json`은 high-water `H`에 대해 sequence `H-1`, `H`, `H+1`과 UTC `before`, `equal`, `after`의 9조합을 고정한다. `H-1/before`와 `H/before`만 excluded이고 나머지 7조합은 retained다. 따라서 sequence equality는 inclusive이고 UTC equality는 exclusive cutoff 때문에 보존된다. 다섯 runtime은 같은 canonical bytes와 결론을 내야 한다.

Incomplete marker는 logical cutoff filter가 아니며 marker를 만들 때의 삭제 집합을 immutable하게 고정한다. `selection`은 canonical runId byte 오름차순으로 정렬한 entry array이고 각 entry는 exact runId, `started.json` SHA-256, lease generation, authenticated lease file SHA-256, joined `tree-drained-v1` marker SHA-256을 가진다. `selectionCount`는 array 길이와 같고 `selectionDigest`는 canonical array bytes의 SHA-256이다. Resume은 이 array의 아직 존재하는 subset만 살피며 marker 뒤 새로 started-only가 된 run은 cutoff를 만족해도 이 marker로 삭제하지 않는다. 각 selected run도 completed evidence 부재, stored started·lease·tree-drained digest와 exact HMAC join을 다시 증명한 뒤에만 삭제한다. 선택 뒤 completed가 된 run은 보존하고 다른 completed prune에서만 다룬다. 선택 밖 run, equality, marker missing·HMAC mismatch, corrupt lease와 재검증 중 identity change는 delete 0이다. Marker mismatch·corruption에서는 두 kind 모두 추가 delete 0이다. Missing selected directory는 이미 끝난 delete로만 취급하고 같은 runId가 다른 identity로 다시 나타나면 corruption으로 중단한다.

Cache replay는 evidence가 원 fresh result identity를 가리킬 수 있지만 finding event를 만들 수 없으므로 `finding-event.schema.json`의 `observationSource`는 fresh만 허용한다. 한 finding의 occurrence·context·family record는 같은 privacy-safe HMAC `findingToken`으로 묶고 세 kind가 exactly once여야 한다. Missing·duplicate kind와 서로 다른 finding의 token collision은 semantic oracle이 거부한다. Finding class·defect kind·safe diagnostic code도 세 record에서 같아야 한다. `run-started.schema.json`은 runId, correlationId, command kind, startedAtUtc, SENTINEL version, language, HMAC module token, keyed config digest를 허용하고 incomplete run은 completed evidence로 승격하지 않는다. Retention marker는 completed `committedAtUtc`와 incomplete `startedAtUtc` 경계를 분리한다.

공용 schema에는 path·symbol·raw output field 자체를 만들지 않는다. `local-detail.schema.json`만 module-relative path, qualified name, source range, operator category를 허용한다. `raw-report.md`는 common state 밖의 명시적 project-controlled directory, owner-only permission, default 미생성만 허용한다.

- [ ] **단계 4: schema·lifecycle·canary 통과 확인**

실행: `scripts/uv.sh run pytest tests/test_evidence_contract.py tests/test_commit_sequence_contract.py tests/test_sandbox_lease_contract.py tests/test_tree_drained_contract.py tests/test_sandbox_control_layout.py tests/test_lifecycle_vectors.py tests/test_privacy_vectors.py -q`

기대: private project-state, sandbox-lease와 tree-drained marker의 version·identifier·key·epoch·guardian·process identity·canonical HMAC wire 계약과 공용 schema 분리, runId·correlationId, started·completed, lifecycle·분류·세 fingerprint, semantic site 이동·context·family·duplicate 규칙, cache·partial, cross-runtime guardian drain·prune, raw-dir, export와 11종 forbidden-byte의 공용 evidence·finding·history·export·default artifact 전체 scan 통과

- [ ] **단계 5: commit**

```bash
scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py prepare-and-stage --repository . --task T03 --phase evidence-contracts --base-head <T03_BASE_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --output-root <workspace>/build/commit-inventory -- schemas contracts golden tests docs README.md
scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py commit-prepared --repository . --task T03 --phase evidence-contracts --prepared-receipt <PREPARED_RECEIPT> --prepared-receipt-sha256 <PREPARED_RECEIPT_SHA256> --base-head <T03_BASE_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --expected-message "feat: define evidence and privacy contracts (요구사항-45..54)"
```

### T04: 재현 가능한 SENTINEL_SPEC 0.1.0-rc.1 bundle

**충족 요구사항:** 요구사항-07, 요구사항-08, 요구사항-33, 요구사항-38, 요구사항-44, 요구사항-49, 요구사항-54

**파일:**

- 생성: `tools/build_manifest.py`, `tools/vendor_spec.py`, `tests/test_manifest.py`, `tests/test_breaking_version.py`, `tests/test_vendor_spec.py`, `tests/fixtures/manifest/{distributable-files,t04-commit-files}.json`
- 생성: `contracts/harness-integration.md`, `golden/projects/{python,typescript,go,java,clojure,polyglot-py-ts}/**`, `golden/acceptance/**`, `manifest.json`
- 생성: `docs/contracts.md`
- 수정: `VERSION`, `docs/index.md`, `docs/log.md`, `README.md`
- 생성: VCS 밖 owner-only `build/t04/{distributable,commit-stage}.paths`

**받는 것:** T02와 T03의 모든 schema, contract, golden fixture

**주는 것:** byte 재현 가능한 `0.1.0-rc.1` bundle, manifest SHA-256과 runtime용 `spec-lock` 입력

이 task는 `VERSION`을 UTF-8 ASCII `0.1.0-rc.1`과 final LF 한 개로 exact 교체한다. 공백, BOM과 추가 줄은 금지한다.

VCS 밖 최종 산출물은 `build/t04/SENTINEL_SPEC-0.1.0-rc.1.tar`와 `build/t04/SENTINEL_SPEC-0.1.0-rc.1.tar.sha256.json` 두 경로뿐이다. Builder는 `build/t04/attempts/<128-bit-random-hex>/` owner-only directory에 두 파일을 먼저 만들고 검증하며, 모든 fallible test가 끝난 마지막 단계에서 `build/t04/publish.lock`을 잡고 final path로 no-replace rename·file sync·directory sync한다. Complete pair는 planned bytes·size·digest·tree OID·manifest blob OID가 모두 같을 때만 채택한다. Crash로 archive만 게시된 경우 exact planned archive를 descriptor로 다시 검증한 뒤 같은 attempt의 receipt만 no-replace 게시할 수 있다. Receipt만 있거나 byte가 다르면 overwrite·delete하지 않고 중단한다. Receipt는 archive name·size·SHA-256·final index tree OID·manifest blob OID를 canonical JSON으로 기록한다.

- [ ] **단계 1: manifest 재현성 실패 test 작성**

```python
def test_manifest_is_sorted_complete_and_self_excluding(build_manifest, release_files):
    first = build_manifest()
    second = build_manifest()
    assert first == second
    assert [row["path"] for row in first["files"]] == sorted(row["path"] for row in first["files"])
    assert "manifest.json" not in {row["path"] for row in first["files"]}
    assert {row["path"] for row in first["files"]} == release_files
```

- [ ] **단계 2: 실패 확인**

실행: `scripts/uv.sh run pytest tests/test_manifest.py tests/test_breaking_version.py tests/test_vendor_spec.py -q`

기대: manifest builder와 vendor tool 부재로 실패. Vendor test는 test-owned archive fixture를 쓰므로 T04 release archive 부재가 실패 원인이 아님

- [ ] **단계 3: deterministic builder와 version rule 구현**

```python
def manifest_row(repo: Path, relative: str, mode: str, blob_oid: str) -> dict[str, str]:
    if mode not in {"100644", "100755"}:
        raise ValueError(f"unsupported distributable mode: {mode} {relative}")
    blob = subprocess.run(
        ["/usr/bin/git", "cat-file", "blob", blob_oid],
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout
    digest = hashlib.sha256(blob).hexdigest()
    return {"path": relative, "sha256": digest}
```

`tests/fixtures/manifest/distributable-files.json`은 test가 소유하는 sorted concrete path·mode 목록이며 `VERSION`, `schemas/**`, `contracts/**`, `golden/**`의 모든 배포 파일을 하나씩 열거하고 glob은 금지한다. `t04-commit-files.json`은 exact key `rc-bundle` 하나가 T04에서 생성·수정하는 production, test, fixture, contract, golden, manifest, README와 docs path를 자기 자신까지 하나씩 열거한 sorted concrete array를 값으로 갖는 사람이 관리하는 selector object다. Test가 T04 file 책임 목록, actual changed set과 이 목록의 missing·extra·duplicate를 검사하며 builder가 working change를 보고 commit allowlist를 자동 확장하는 경로는 없다. `--working-tree --write`는 real index가 비어 있고 HEAD가 `<T04_BASE_HEAD>`인지 확인한 뒤, distributable fixture에 열거된 opened regular file의 mode·bytes만 descriptor-safe하게 읽어 provisional `manifest.json`을 만든다. 이 output은 staging 권한이나 최종 배포 증거가 아니다. 그 다음 T01 `materialize-exact --selector rc-bundle`과 `stage-exact`가 `t04-commit-files.json`의 exact array 전체를 real index에 정확히 한 번 stage한다. `--index --check`의 `checksum_files`는 그 final Git index에서 distributable SSoT와 exact set·mode가 같은 entry만 읽고 `manifest.json` 자기 자신은 제외한다. 최종 `archive_files`는 이 concrete set과 `manifest.json` 하나다. Test는 distributable SSoT, index, manifest row와 archive member 네 set의 missing·extra·duplicate를 독립 비교한다. Index mode의 builder는 실행 시작에 `git write-tree`로 tree OID 하나를 고정하고 `git ls-tree -rz --full-tree <treeOid>`의 `(mode, blobOid, path)`만 읽는다. 허용 mode는 regular file `100644`와 `100755`뿐이며 symlink `120000`, submodule `160000`, unsupported mode와 unmerged index는 archive 생성 전에 거부한다. 각 authoritative digest는 working tree가 아니라 `git cat-file blob <blobOid>` bytes로 계산한다. `--check`는 staged `manifest.json` bytes를 index distributable bytes에서 다시 계산한 canonical bytes와 비교한다. 다르면 archive를 만들지 않으므로 provisional 계산과 stage 사이의 byte 변경은 통과할 수 없다.

Archive는 `git archive <treeOid>`를 사용하지 않는다. Index mode builder에는 T01 `stage-exact`가 반환한 prepared receipt path와 whole-file SHA-256이 필수다. Builder는 inherited `GIT_*`를 제거한 minimal environment와 검증된 `/usr/bin/git`만 쓰고 canonical owning repository의 real `.git/index`를 descriptor로 확인한다. Receipt의 repository·task T04·phase `rc-bundle`·base·path·mode·blob·tree를 registry와 join하고 실행 전후 `write-tree`가 receipt의 sealed tree OID와 같을 때만 그 tree의 blob bytes와 mode로 uncompressed POSIX ustar를 직접 만든다. Ambient `GIT_INDEX_FILE`, alternate object, index lock, index swap이나 같은 path의 다른 blob은 archive·receipt publish 0에서 실패한다. Member는 UTF-8 path byte lexical order, regular file type, index의 `0644` 또는 `0755`, uid·gid 0, 빈 uname·gname, mtime `1788307200`(2026-09-02T00:00:00Z), PAX·extended header 0으로 고정한다. Ustar로 표현할 수 없는 path는 실패한다. Archive 안 `manifest.json` bytes와 staged blob bytes가 다르거나 builder 실행 중 index가 바뀌면 결과를 게시하지 않는다. Working-tree-only file, test, docs, VCS와 build output은 제외한다. 재현 test는 서로 다른 locale·timezone·umask와 최소 2초 간격에서 서로 다른 fresh owner-only output directory에 두 archive를 만들고 canonical JSON bytes와 archive SHA-256이 같음을 확인한다. Schema breaking vector를 바꾸고 major version을 유지하면 `test_breaking_version.py`가 실패해야 한다. CRAP golden에는 언어별 `decision-matrix`가 들어가며 설계 6.2의 모든 CC 증가 syntax별 expected count, callable별 total CC와 nested child decision의 parent 중복 0을 고정한다.

T25가 소비할 여섯 project fixture와 공통 acceptance vector, `harness-integration.md`의 CLI·exit·artifact 계약도 이 RC에서 최종 byte로 고정한다. T25는 이 배포 allowlist를 수정하지 않고 실제 5개 runtime이 고정 vector를 통과하는지만 검증한다. 공용 conformance 입력을 바꿔야 하면 T04로 되돌아가 새 RC version·manifest를 만들고, 이미 vendor한 runtime은 전부 새 `spec-lock.json`과 bytes로 갱신한 뒤 다시 검증한다.

`tools/vendor_spec.py`는 receipt의 archive name·size·SHA-256을 먼저 확인하고 T02의 safe archive member 규칙으로 fresh owner-only temporary directory에만 푼다. Archive 안 manifest와 모든 member digest·mode·exact allowlist를 검증하고 expected destination tree·canonical lock bytes·두 target identity를 VCS 밖 owner-only `build/vendor-spec-attempts/<repository>/<attemptId>/intent.json`에 no-replace·file sync·directory sync한 뒤에만 게시를 시작한다. `spec-lock.json`에는 version, source SPEC commit, archive digest, manifest digest와 모든 vendored path·mode·digest를 canonical JSON으로 쓴다. Destination과 lock output이 모두 없으면 same-filesystem no-replace rename으로 `vendor/sentinel-spec`을 게시하고 lock을 no-replace·file sync·directory sync한다. 재실행에서 matching durable intent가 있고 한쪽만 존재하면 존재하는 쪽의 complete bytes·mode·digest·target identity를 descriptor로 exact 검증한 뒤 missing side만 no-replace 게시한다. 둘 다 존재하면 complete tree와 canonical lock bytes가 intent와 exact일 때 write 0으로 채택한다. Matching intent가 없거나 symlink, partial tree, extra·missing file, mode·byte·digest·target 불일치이면 overwrite·delete·repair하지 않고 중단한다. Test는 intent sync, extraction, destination rename, lock publish와 directory sync 경계마다 crash를 주입해 exact one-sided state는 missing side만 완성하고 complete exact pair는 write 0으로 채택하며 partial·mismatch는 mutation 0인지 확인한다. 다섯 runtime은 같은 archive·receipt를 사용하며, lock의 source commit은 T04 annotated RC tag의 peeled commit과 같아야 한다.

- [ ] **단계 4: distributable index 고정과 전체 SPEC 검증**

실행: `scripts/uv.sh run python tools/build_manifest.py --working-tree --source tests/fixtures/manifest/distributable-files.json --base-head <T04_BASE_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --write manifest.json`

실행: `scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py materialize-exact --repository . --task T04 --phase rc-bundle --base-head <T04_BASE_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --source tests/fixtures/manifest/t04-commit-files.json --selector rc-bundle --output <workspace>/build/t04/commit-stage.paths`

실행: `scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py stage-exact --repository . --task T04 --phase rc-bundle --base-head <T04_BASE_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --manifest <workspace>/build/t04/commit-stage.paths`

실행: `scripts/uv.sh run pytest -q && test -z "$(/usr/bin/git diff --name-only)" && scripts/uv.sh run python tools/build_manifest.py --index --prepared-receipt <PREPARED_RECEIPT> --prepared-receipt-sha256 <PREPARED_RECEIPT_SHA256> --check manifest.json --archive-output ../build/t04/SENTINEL_SPEC-0.1.0-rc.1.tar --receipt-output ../build/t04/SENTINEL_SPEC-0.1.0-rc.1.tar.sha256.json`

기대: 새 harness contract·project·acceptance golden을 포함한 staged checksum set과 `manifest.json` 계산 결과 일치, final archive에는 그 set과 staged `manifest.json`만 존재, archive 안 manifest bytes 일치, working-tree-only file 0개 포함, 두 archive digest 일치. Stage 뒤 pytest·index check·archive 중 하나가 실패하면 commit과 source edit를 하지 않고 T01 `abandon-stage --repository . --task T04 --phase rc-bundle --base-head <T04_BASE_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --prepared-receipt <PREPARED_RECEIPT> --prepared-receipt-sha256 <PREPARED_RECEIPT_SHA256>`로 exact stage만 해제해 failure bundle을 보존한 뒤 구현을 고치고 단계 4를 새 receipt로 다시 시작함

- [ ] **단계 5: local RC commit과 tag**

```bash
scripts/uv.sh run python tools/build_manifest.py --index --prepared-receipt <PREPARED_RECEIPT> --prepared-receipt-sha256 <PREPARED_RECEIPT_SHA256> --check manifest.json
test -z "$(/usr/bin/git diff --name-only)"
scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py commit-prepared --repository . --task T04 --phase rc-bundle --prepared-receipt <PREPARED_RECEIPT> --prepared-receipt-sha256 <PREPARED_RECEIPT_SHA256> --base-head <T04_BASE_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --expected-message "feat: publish reproducible SPEC 0.1.0-rc.1 (요구사항-33,38,44)"
scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py tag-prepared --repository . --task T04 --phase rc-tag --committed-receipt <COMMITTED_RECEIPT> --committed-receipt-sha256 <COMMITTED_RECEIPT_SHA256> --tag-ref refs/tags/spec-v0.1.0-rc.1 --expected-message "SENTINEL_SPEC 0.1.0-rc.1"
```

Commit command stdout의 `<COMMITTED_RECEIPT>`와 whole-file digest를 tag command에 그대로 넘긴다. `tag-prepared`만 annotated `spec-v0.1.0-rc.1`을 만들며 target·tagger·timestamp·message와 crash recovery는 T01 공통 상태기를 따른다. Lightweight·wrong target·wrong message이면 tag 이동·삭제 없이 중단한다.

### T05: SENTINEL_PY 설치·SPEC·config·scope·help·doctor

**충족 요구사항:** 요구사항-01, 요구사항-05, 요구사항-09, 요구사항-18, 요구사항-21, 요구사항-32, 요구사항-42, 요구사항-55

**파일:**

- 생성: `SENTINEL_PY/{.python-version,pyproject.toml,uv.lock,spec-lock.json}`, `SENTINEL_PY/vendor/sentinel-spec/**`
- 검증: T01의 `toolchain.lock.json`, `scripts/{bootstrap-python,uv}.sh`
- 생성: `src/sentinel_py/{__main__.py,cli.py,orchestrator.py,contracts/{loader.py,models.py},config/{models.py,resolver.py,scope.py}}`
- 생성: `src/sentinel_py/platform/{entropy.py,file_ops.py,clock.py,process.py,project_key.py,hmac_sha256.py}`
- 테스트: `tests/unit/test_contract_loader.py`, `test_config_resolver.py`, `test_scope.py`, `tests/unit/platform/{test_facades,test_project_key,test_hmac_sha256}.py`, `tests/acceptance/test_help_doctor.py`
- fixture: `tests/fixtures/scope/{two-test-files,partial-test-selection}/`
- 생성: `docs/contracts.md`
- 수정: `README.md`, `docs/index.md`, `docs/log.md`

**받는 것:** T04의 bundle bytes, commit과 manifest digest

**주는 것:** `VerifiedContract`, `ResolvedModule`, `ClassifiedScope`, side-effect 없는 `help`와 `doctor`

`pyproject.toml`의 project version은 Python runtime version의 단일 원본이며 exact `0.1.0-rc.1`로 시작한다. CLI·doctor·result의 `sentinel.version`과 clean-installed package metadata가 이 값과 같은지 test한다. `uv.lock`의 값은 파생 사본일 뿐 별도 version 원본이 아니다.

`platform`의 여섯 production dependency boundary는 entropy, file·directory sync·rename·descriptor operation, evidence·retention용 `utcNow`, timeout·lock deadline용 process `monotonicNow`, lease용 `leaseBoottimeNanos`와 UTC instant·동기화 proof를 한 결과로 돌려주는 `sampleUtcWithSyncProof`, child process spawn·signal·reap, project-key 입력, HMAC-SHA-256 계산을 감싸고 orchestrator constructor로 받는다. Python Clock의 lease method는 `time.clock_gettime_ns(time.CLOCK_BOOTTIME)`와 minimal `ctypes` libc `adjtimex` bracket만 사용한다. UTC wall clock은 monotonic deadline에 사용할 수 없고 process monotonic 값은 evidence timestamp나 lease에 사용할 수 없다. Default CLI는 OS implementation만 조립하며 option·config·environment로 test implementation을 선택할 수 없다. Unit·integration test implementation은 `tests/**`에만 두고 T25가 release import graph와 artifact에서 0개임을 확인한다.

`ProjectKeyProvider`는 T02의 `--project-key-stdin` canonical envelope를 bounded read·validate·decode하고 opaque 32-byte key와 epoch를 orchestrator parent에만 준 뒤 stdin을 닫는다. Raw key를 string representation·exception·argv·environment로 만들지 않으며 child process facade는 provider 사용 여부와 무관하게 stdin을 `/dev/null`로 고정한다. Option이 없으면 quality command만 OS CSPRNG local-key 경로를 사용한다. Help·doctor·history는 provider를 호출하지 않는다.

`HmacSha256` production provider는 Python 표준 `hmac`·`hashlib`만 사용해 fingerprint, projectToken과 bootToken의 모든 MAC을 계산한다. Orchestrator 밖에서 직접 HMAC을 호출하는 production path는 static inventory 0이어야 한다. Provider failure는 값을 꾸며내거나 일반 SHA-256으로 낮추지 않고 외부 child 호출·cleanup·prune delete 0의 exit 7 `evidenceError`다.

Python foundation Clock test는 Clock 전체를 fake로 바꾸지 않고 production Clock 아래의 test-only libc syscall seam만 주입한다. Exact trace는 T03의 두 `CLOCK_MONOTONIC_RAW`, 두 fresh zero-filled `timex(modes=0)` adjtimex와 중간 `CLOCK_REALTIME`의 다섯 호출이다. Extra·separate UTC read, input reuse·nonzero field를 거부한다. `STA_NANO` 정규화, maxerror·span·uncertainty 산식, before·sample·after bracket, 각 error·status와 forward·backward step vector가 같은 immutable UTC instant+uncertainty+proof result를 만들거나 unknown인지 검사한다. Default Clock의 이 seam은 production libc adapter 하나만 선택하며 우회 syscall static inventory는 0이다.

- [ ] **단계 0: production module 없는 Python test runner scaffold 고정**

T01의 pinned bootstrap으로 `.python-version`, `pyproject.toml`, `uv.lock`을 먼저 만든다. 이 commit 전 scaffold는 package metadata, empty `src` package directory, pytest·test helper dependency와 test discovery 설정만 담고 production module·CLI behavior는 담지 않는다. `/usr/bin/bash scripts/bootstrap-python.sh && scripts/uv.sh sync --locked`가 성공하고 lock digest가 두 번 같아야 한다. 실행 위치를 `SENTINEL_SPEC`으로 바꿔 `scripts/uv.sh run python tools/vendor_spec.py --archive ../build/t04/SENTINEL_SPEC-0.1.0-rc.1.tar --receipt ../build/t04/SENTINEL_SPEC-0.1.0-rc.1.tar.sha256.json --source-tag spec-v0.1.0-rc.1 --destination ../SENTINEL_PY/vendor/sentinel-spec --lock-output ../SENTINEL_PY/spec-lock.json`을 한 번 실행하고, 다시 `SENTINEL_PY`로 돌아온다. 이어 test file을 작성한 뒤 단계 2가 missing production import·module 때문에 RED가 되게 한다. Dependency 설치 실패, vendor 실패나 test 0개는 RED 근거로 인정하지 않는다.

- [ ] **단계 1: help·lock·polyglot scope 실패 test 작성**

```python
def test_help_has_no_project_side_effects(tmp_path, run_cli):
    result = run_cli("--help", cwd=tmp_path)
    assert result.returncode == 0
    assert "crap" in result.stdout
    assert not (tmp_path / ".sentinel").exists()

def test_python_module_does_not_claim_typescript_source(polyglot_project, resolve_scope):
    scope = resolve_scope(polyglot_project, module="api")
    assert scope.production == {"api/src/service.py"}
    assert "web/src/view.ts" not in scope.production
```

- [ ] **단계 2: 실패 확인**

실행 위치: `SENTINEL_PY`

실행: `/usr/bin/bash scripts/bootstrap-python.sh && scripts/uv.sh sync --locked && scripts/uv.sh run pytest tests/unit/test_contract_loader.py tests/unit/test_config_resolver.py tests/unit/test_scope.py tests/unit/platform/test_facades.py tests/unit/platform/test_project_key.py tests/unit/platform/test_hmac_sha256.py tests/acceptance/test_help_doctor.py -q`

기대: package와 CLI module 부재로 실패

Bootstrap script는 minimal environment에서 고정 URL의 uv 0.12.9 archive와 python-build-standalone 3.12.13 archive를 각각 다운로드해 위 SHA-256을 직접 확인한 뒤 `.toolchain` 아래에만 원자 설치한다. Ambient uv·Python, `UV_PYTHON_DOWNLOADS_JSON_URL`, mirror와 PATH 선택은 사용하지 않는다. T05에서는 설치된 runtime tree manifest와 `sys.version`·ABI를 `.python-version`과 `toolchain.lock.json`에 대조한다. T07에서 `backend.lock.json`이 생긴 뒤에는 같은 값을 supportedRuntime에도 추가 대조한다. 존재하지 않는 backend lock을 T05가 요구하거나 검증을 건너뛰는 fallback은 없다.

- [ ] **단계 3: 최소 contract·config·scope 구현**

```python
@dataclass(frozen=True)
class ResolvedModule:
    module_id: str
    root: Path
    language: Literal["python"]
    production: tuple[Path, ...]
    test_command: tuple[str, ...]
    coverage_command: tuple[str, ...]

def select_module(config: Config, requested: str | None) -> ResolvedModule:
    candidates = [module for module in config.modules if module.language == "python"]
    if requested is None and len(candidates) != 1:
        raise UsageConfigError("moduleSelectionRequired")
    return require_exact_module(candidates, requested)
```

Contract loader는 vendored bytes를 `spec-lock.json`의 file manifest와 모두 비교한다. Scope classifier는 `.py`를 native 발견한 뒤 production, verified test, generated, vendor, build-output 중 정확히 하나에 배정하고 `unclassifiedSource`와 overlap을 거부한다. Native test root와 naming rule로 두 test file을 모두 inventory하며 configured command가 한 file이나 `-k` ID만 고른 fixture도 full verified-test scope를 유지한다. Foundation `doctor`는 CPython·pytest·coverage.py dependency lock, vendored SPEC checksum, resolved config와 scope를 읽되 test, coverage, backend와 state write를 호출하지 않는다. Admission 전에는 backend가 아직 없다는 `backendPending` 진단을 side effect 없이 반환하고 release-capable 성공으로 오인하지 않는다. T07이 선택 backend lock·artifact·version·adapter를 추가한 뒤 같은 command와 test를 갱신해 전체 doctor를 완성한다.

Config resolver는 CLI override, project config, SPEC default 순서를 고정하고 argv array만 반환한다. `prepareCommand`, child environment 이름 allowlist, secret reference, environment contract digest, `localCacheDir`와 generated-output root를 T02 golden과 대조한다. Parent environment 전체 상속과 ambient backend override는 거부한다.

- [ ] **단계 4: foundation test 통과 확인**

실행: `scripts/uv.sh run pytest tests/unit/test_contract_loader.py tests/unit/test_config_resolver.py tests/unit/test_scope.py tests/unit/platform/test_facades.py tests/unit/platform/test_project_key.py tests/unit/platform/test_hmac_sha256.py tests/acceptance/test_help_doctor.py -q`

기대: tampered SPEC은 exit 5, ambiguous module은 exit 3, help·doctor의 외부 실행과 write는 0회, facade fault는 constructor injection으로만 도달하고 default CLI에서 test implementation 선택 경로 0개

- [ ] **단계 5: commit**

```bash
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py prepare-and-stage --repository . --task T05 --phase foundation --base-head <T05_BASE_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --output-root <workspace>/build/commit-inventory -- .python-version pyproject.toml uv.lock spec-lock.json vendor src tests README.md docs
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py commit-prepared --repository . --task T05 --phase foundation --prepared-receipt <PREPARED_RECEIPT> --prepared-receipt-sha256 <PREPARED_RECEIPT_SHA256> --base-head <T05_BASE_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --expected-message "feat: add Python contract and scope foundation (요구사항-01,05,09,18,21,32,42,55)"
```

### T06: SENTINEL_PY native CRAP

**충족 요구사항:** 요구사항-10..요구사항-12, 요구사항-14..요구사항-17, 요구사항-34

**파일:**

- 생성: `src/sentinel_py/crap/{models.py,formula.py,analyzer.py,coverage.py,semantic_site.py}`, `src/sentinel_py/rendering/canonical_decimal.py`
- 테스트: `tests/unit/crap/test_formula.py`, `test_analyzer.py`, `test_semantic_site.py`, `tests/unit/rendering/test_canonical_decimal.py`, `tests/integration/crap/test_coverage.py`, `tests/acceptance/test_crap_command.py`
- fixture: `tests/fixtures/crap/{nested,same_line,same_name_redefinition,stale,exact_boundary,decision_matrix,stable-sort}/`
- 생성: `docs/architecture.md`
- 수정: `src/sentinel_py/{cli.py,orchestrator.py}`, `docs/index.md`, `docs/log.md`

**받는 것:** T05의 `ClassifiedScope`와 T04 CRAP golden vector

**주는 것:** Python callable inventory, exact `CallableMetric`, `CrapGateResult`, `sentinel-py crap`

- [ ] **단계 1: exact formula와 nested callable 실패 test 작성**

```python
from fractions import Fraction

def test_exact_crap_fraction_has_no_float_tolerance():
    metric = calculate_crap(complexity=4, covered=3, total=4)
    assert metric.raw == Fraction(17, 4)
    assert metric.numerator == 17
    assert metric.denominator == 4

def test_nested_function_units_belong_only_to_inner(analyze_fixture):
    rows = analyze_fixture("nested")
    assert rows["outer"].total_units == 2
    assert rows["outer.<locals>.inner"].total_units == 1
```

- [ ] **단계 2: 실패 확인**

실행: `scripts/uv.sh run pytest tests/unit/crap tests/unit/rendering/test_canonical_decimal.py tests/integration/crap tests/acceptance/test_crap_command.py -q`

기대: `sentinel_py.crap` import 실패

- [ ] **단계 3: analyzer·coverage·gate 최소 구현**

```python
from math import gcd

def calculate_crap(complexity: int, covered: int, total: int) -> ExactCrap:
    if complexity < 1 or covered < 0 or total < 0 or covered > total:
        raise CoverageDependencyError("invalidCoverageCounts")
    if total == 0:
        return ExactCrap.unknown("zeroExecutableUnits")
    denominator = total**3
    numerator = complexity**2 * (total - covered) ** 3 + complexity * denominator
    divisor = gcd(numerator, denominator)
    numerator, denominator = numerator // divisor, denominator // divisor
    return ExactCrap(numerator=numerator, denominator=denominator, passed=numerator <= 8 * denominator)
```

`canonical_decimal.py`는 T02 `canonical-decimal-v1`의 10^12 integer scale·round-half-to-even·trailing-zero 제거만 구현하고 Python `float`, `Decimal` context와 format string을 사용하지 않는다. CRAP·coverage와 뒤의 mutation kill-rate renderer가 이 함수 하나를 호출한다. Unit test는 vendored SPEC의 reduce, `1/3`, half-even down/up, carry, zero·integer와 큰 fraction golden bytes를 직접 소비한다. Row comparator도 T02 `crap-row-order-v1`의 exact cross-multiply, UTF-8 byte path·callable ID와 raw UTF-8 byte offset을 구현하고 near-equal·한글·astral golden을 소비한다.

`ast` visitor는 function, async function, method, nested function, lambda를 inventory하고 child range를 parent coverage에서 제외한다. `same_name_redefinition`은 position이 아닌 normalized declaration semantic hash가 다른 exact callable ID 2개를 기대하며, 완전히 같은 duplicate는 ambiguous로 실패한다. `decision_matrix`는 branch, loop, exception handler, boolean decision, conditional expression과 comprehension filter의 syntax별 expected 증가값과 callable별 total CC를 고정한다. Nested child의 decision이 parent CC에 더해지면 실패한다. 고정 coverage.py 7.16.0 JSON schema·version만 허용하고 같은 line의 독립 callable을 구분하지 못하면 `coverageUnknown`으로 만든다. Fresh report digest·tool version·selection digest가 맞지 않으면 exit 5 또는 exit 2 계약대로 실패한다.

- [ ] **단계 4: Python CRAP test 통과 확인**

실행: `scripts/uv.sh run pytest tests/unit/crap tests/unit/rendering/test_canonical_decimal.py tests/integration/crap tests/acceptance/test_crap_command.py -q`

기대: 8.0은 통과, 8.0 초과·same-line unknown·stale report는 실패, 기약분수와 canonical decimal 모든 golden 통과, 모든 Python CC syntax의 exact count와 nested parent 중복 0, near-equal·한글·astral row 정렬은 반복 실행 byte가 같음

- [ ] **단계 5: commit**

```bash
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py prepare-and-stage --repository . --task T06 --phase crap --base-head <T06_BASE_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --output-root <workspace>/build/commit-inventory -- src/sentinel_py/crap src/sentinel_py/rendering src/sentinel_py/cli.py src/sentinel_py/orchestrator.py tests/unit/crap tests/unit/rendering tests/integration/crap tests/acceptance/test_crap_command.py tests/fixtures/crap docs/architecture.md docs/index.md docs/log.md
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py commit-prepared --repository . --task T06 --phase crap --prepared-receipt <PREPARED_RECEIPT> --prepared-receipt-sha256 <PREPARED_RECEIPT_SHA256> --base-head <T06_BASE_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --expected-message "feat: implement native Python CRAP gate (요구사항-10..17,34)"
```

### T07: SENTINEL_PY snapshot·pytest runner·mutation admission·gate

**충족 요구사항:** 요구사항-03, 요구사항-19, 요구사항-22..요구사항-32, 요구사항-43

**파일:**

- 생성: `src/sentinel_py/runner/pytest_reporter.py`
- 생성: `src/sentinel_py/runner/test_inventory.py`
- 생성: `src/sentinel_py/workspace/{native_fs.py,safe_path.py,snapshot.py,process_tree.py,sandbox_lease.py,guardian.py,start_gate.py}`
- 생성: `src/sentinel_py/mutation/{protocol.py,mutmut370.py,normalizer.py,gate.py}`, `backend.lock.json`
- 조건부 대체: `src/sentinel_py/mutation/cosmic_ray870.py`
- 수정: `pyproject.toml`, `uv.lock`
- 테스트: `tests/unit/mutation/test_gate.py`, `test_normalizer.py`, `tests/integration/test_native_fs.py`, `test_snapshot.py`, `test_sandbox_lease.py`, `test_guardian.py`, `test_start_gate.py`, `test_pytest_reporter.py`, 조건부 단일 `test_{mutmut370,cosmic_ray870}_admission.py`, `tests/acceptance/test_mutation_command.py`
- fixture: `tests/fixtures/mutation/{all-killed,survivor,coverage-failure,all_states,internal_exit_3,source_race,timeout,partial-test-file,partial-test-id}/`
- 생성: `tests/fixtures/commit/t07-files.json`
- 수정: `src/sentinel_py/cli.py`, `src/sentinel_py/orchestrator.py`, `tests/acceptance/test_help_doctor.py`
- 생성: `docs/backend.md`, `docs/operations.md`, `docs/lineage.md`
- 수정: `docs/index.md`, `docs/log.md`
- 생성: VCS 밖 owner-only `build/t07/backend-selection/<backend>/<attemptId>/{checkout,admission.json}`

**받는 것:** T05 scope와 T04 runner·mutation golden vector, 단계 5부터 T06 coverage matcher

**주는 것:** `SnapshotLease`, nonce 기반 pytest event, 단일 Python backend lock, candidate·outcome과 killed-only result

- [ ] **단계 0: production bridge 없는 mutmut candidate dependency 고정**

Primary `SENTINEL_PY`의 clean T06 HEAD·index tree를 `backendSelectionBase`로 먼저 고정한다. T01에서 digest를 검증한 `/usr/bin/git`을 `/usr/bin/env -i`로 실행하고 owner-only empty HOME·XDG·template directory, `GIT_CONFIG_NOSYSTEM=1`, `GIT_CONFIG_GLOBAL=/dev/null`, `core.hooksPath=/dev/null`, replacement·alternate object 0, explicit `protocol.file.allow=always`만 고정한다. Canonical source가 exact primary `SENTINEL_PY`, target parent가 owner-only이고 target이 absent인 경우에만 `clone --no-hardlinks --no-tags --template=<EMPTY_TEMPLATE>`로 `build/t07/backend-selection/mutmut/<attemptId>/checkout`을 만들고 같은 sealed Git로 remote를 즉시 제거한다. Clone 전후 source·target directory FD identity를 확인하고 object alternate·hardlink, replacement object, hook·template file와 source repository로 향하는 remote가 0인지 검사하며 checkout HEAD·tree가 base와 같은지 확인한다. Hostile `GIT_*`, system/global config와 template hook fixture는 clone·checkout hook 또는 다른 external process가 0이고 wrong target write가 0인지 먼저 검증한다. Isolated checkout의 basename은 repository 이름이 아니므로 이 checkout에서 실행하는 모든 `commit_inventory.py` mode에는 `--logical-repository SENTINEL_PY`를 전달하고 receipt도 그 값을 기록한다. Isolated repo의 local commit identity도 같은 sealed Git environment에서 T01과 같은 `황화인 <166008093+hwain-hwang@users.noreply.github.com>`로 exact 설정한다. `.toolchain/**`는 Git에서 제외되어 clone에 없으므로 먼저 `/usr/bin/bash scripts/bootstrap-python.sh`를 실행하고 `toolchain.lock.json`의 archive·installed tree·Python·uv version·ABI와 `.toolchain` ignore를 검증한 뒤 `scripts/uv.sh sync --locked`를 통과시킨다. 그 다음에만 `scripts/uv.sh add --no-sync mutmut==3.7.0 && scripts/uv.sh sync --locked`를 실행한다. Version specifier 자체가 exact이므로 uv 0.12.9에 존재하지 않는 `uv add --exact` option은 사용하지 않는다. 상단 고정 wheel과 transitive artifact digest를 `uv.lock`에 넣고 import·executable version smoke를 통과시킨다. 이 단계에는 runner, adapter, normalizer와 gate production module을 만들지 않는다. 따라서 단계 2는 dependency 부재가 아닌 missing bridge behavior 때문에 RED여야 한다.

단계 0..4A는 전부 이 isolated checkout에서 진행한다. Mutmut admission이 실패한 경우 그 checkout과 실패 receipt를 그대로 보존하며 수정·삭제·reset하지 않는다. 같은 `backendSelectionBase`에서 새 `build/t07/backend-selection/cosmic-ray/<attemptId>/checkout`을 만들고, 똑같이 Python bootstrap·lock·installed tree·ABI를 검증한다. 처음부터 mutmut dependency가 없는 tree에 `cosmic-ray==8.7.0` exact wheel·transitive lock을 넣어 단계 0..4A를 다시 실행한다. 한 checkout에서 dependency를 갈아 끼우거나 두 backend를 한 runtime lock·source tree에 함께 두지 않으며 runtime fallback도 구현하지 않는다.

각 `admission.json`은 `sentinel-python-backend-admission-v1`, backend 이름·exact version, attempt ID, base HEAD·tree, dependency lock digest, installed distribution manifest digest, adapter·fixture·raw outcome digest, 실행한 test argv·integer exit code, candidate·operator·상태 set digest, selected boolean과 stable diagnostic code를 canonical JSON으로 기록한다. Raw stdout·stderr와 absolute operator credential은 넣지 않는다. 실패 receipt는 해당 backend가 왜 계약을 증명하지 못했는지 남기고, 성공 receipt는 actual executable 네 fixture와 exact result가 모두 맞을 때만 `selected=true`다. Mutmut 성공이면 Cosmic Ray checkout·호출은 0이고, Mutmut 실패와 Cosmic Ray 성공이면 두 receipt의 base HEAD·tree가 같아야 한다. 둘 다 실패하면 primary Git·dependency mutation 0으로 T07을 중단한다.

- [ ] **단계 1: false-kill과 source 오염 실패 test 작성**

```python
def test_pytest_internal_exit_three_is_never_killed(normalize_fixture):
    result = normalize_fixture("internal_exit_3.json")
    assert result.mutants[0].status == "toolError"
    assert result.terminal_status == "backendError"
    assert result.exit_code == 6

def test_pass_requires_every_candidate_killed(gate):
    result = gate(candidates={"m1", "m2"}, records={"m1": "killed", "m2": "timedOut"})
    assert result.pass_ is False
    assert result.kill_rate_numerator == 1
    assert result.kill_rate_denominator == 2
```

Snapshot integration test는 symlink, hardlink, edit-and-restore, atomic path swap, SIGTERM과 timeout 뒤 원본 device·inode·mtime·ctime·content digest를 비교한다.

`test_native_fs.py`는 trusted root FD 아래 absolute·`..`·separator component, symlink·magic-link·hardlink, validation 직후 parent·leaf swap과 unsupported kernel·filesystem·ABI를 주입한다. 성공 case도 opened FD의 `fstat` identity와 실제 rename·unlink target이 같아야 하며 문자열 path를 검사 후 다시 열면 실패한다.

`SandboxLease`는 T03 `sandbox-lease-v1`, `sandbox-control-layout-v1`, guardian과 exact age policy를 구현한다. Approved root에서 lease·fixed marker filename·relative leaf·owner·mode·device·inode를 descriptor로 검증하고 gate 뒤에만 backend를 실행한다. Lease age는 T05 Clock의 `leaseBoottimeNanos`와 `sampleUtcWithSyncProof`만 소비한다. Catch 가능한 terminal은 guardian의 authenticated tree-drained marker 뒤 정리한다. 다음 run은 valid marker와 age-expired가 모두 맞을 때만 no-replace quarantine·directory sync 뒤 descriptor-relative delete한다. Marker missing·guardian crash·foreign/duplicate leaf·HMAC/path identity 불명은 cross-boot에서도 영구 no-touch다. `--raw-dir` opt-in copy는 별도다.

Python package의 first-party guardian은 T03 subreaper·pidfd·HMAC tree-drained 계약을 전부 구현한다. Controller EOF와 정상 drain에서 `setsid`·double-fork descendant가 adopted direct child가 될 때마다 pidfd TERM·KILL과 `waitid(P_PIDFD)`를 반복하고 ECHILD 뒤에만 marker를 durable commit한다. Numeric `kill`·`killpg`·`tgkill`은 0이다. Guardian SIGKILL·marker/HMAC 불명은 cross-boot와 age-expired에서도 영구 unknown·no-delete다.

Mutation 결과의 killed/in-scope fraction도 T06 reduce와 `canonical-decimal-v1` 하나로만 render한다. Gate는 decimal percentage가 아니라 exact count equality를 사용하고 0 denominator는 percentage를 만들지 않고 quality failure다.

`PytestInventoryCollector`는 classified test root·naming rule로 발견한 모든 test file을 explicit argv로 pytest collection하고 canonical node ID inventory를 만든다. 각 native test file은 collected ID가 1개 이상이어야 하며 collection inventory와 두 fresh baseline의 started·terminal ID가 exact join해야 한다. Configured command가 한 test file이나 `-k` ID만 고르거나 0·missing·extra·duplicate ID가 생기면 coverage·candidate·mutant 호출 0에서 baselineFailed다. Acceptance는 완전한 같은 selection을 서로 다른 nonce로 두 번 fresh baseline 실행한다. 하나라도 실패하거나 test ID set이 다르면 coverage·candidate generation·mutant 실행 호출은 0이다. `prepareCommand`는 disposable snapshot 안에서만 argv와 minimal child environment로 실행하며 coverage·output·raw·export·cache root가 protected path와 overlap, symlink·hardlink·path swap이면 실행 전에 실패한다.

`test_help_doctor.py`는 T05의 `backendPending`을 선택 backend admission 뒤 성공으로 바꾸고, backend lock·artifact·version·adapter 중 하나를 변조할 때 dependencyError 진단과 외부 test·coverage·mutation·state write 0회를 검증한다.

단계 1..4A에는 admission에 필요한 unit·integration test와 fixture만 만든다. 사람이 관리하는 `tests/fixtures/commit/t07-files.json`은 `mutmut-admission`, `cosmic-ray-admission`, `coverage-join` 세 selector와 각각의 sorted concrete path array를 미리 고정하고, 두 admission array는 자기 fixture path를 포함한다. Test는 선택하지 않은 backend adapter·dependency가 해당 array에 섞이지 않고 각 selector가 task 책임과 actual changed set에 exact인지 확인한다. T06 coverage matcher가 필요한 `tests/acceptance/test_mutation_command.py`와 coverage-join fixture는 단계 4A의 clean-tree checkpoint 뒤 단계 4B에서 먼저 실패하도록 작성한다.

아래 `<ADMISSION_TEST>`는 Mutmut checkout에서는 exact `tests/integration/test_mutmut370_admission.py`, Cosmic Ray checkout에서는 exact `tests/integration/test_cosmic_ray870_admission.py`다. 선택하지 않은 이름의 file은 그 checkout에 존재하면 안 된다.

- [ ] **단계 2: 실패 확인**

실행: `scripts/uv.sh run pytest tests/unit/mutation tests/integration/test_native_fs.py tests/integration/test_snapshot.py tests/integration/test_sandbox_lease.py tests/integration/test_guardian.py tests/integration/test_start_gate.py tests/integration/test_pytest_reporter.py <ADMISSION_TEST> -q`

기대: workspace와 bridge module 부재로 실패

- [ ] **단계 3: workspace·runner와 Mutmut370Bridge 구현**

```python
class MutationAdapter(Protocol):
    def generate_plan(self, snapshot: SnapshotLease) -> CandidatePlan: ...
    def run_all(self, plan: CandidatePlan, runner: TestRunner) -> tuple[RawOutcome, ...]: ...

def strict_pass(plan: CandidatePlan, records: tuple[MutantRecord, ...]) -> bool:
    return bool(plan.candidates) and {row.candidate_id for row in records} == plan.ids and all(
        row.status == "killed" for row in records
    )
```

Bridge는 mutmut 3.7.0 raw metadata에서 candidate ID·operator·location을 첫 mutant 실행 전에 고정하고, source-write와 cache를 끈 snapshot 안에서만 실행한다. Baseline, original control, mutant replay는 서로 다른 nonce를 사용한다. `killed`는 typed `AssertionError`, passing control, 같은 HMAC failure signature replay가 모두 있을 때만 확정한다. Admission은 T05 `toolchain.lock.json`의 runtime tree manifest·ABI와 `backend.lock.json.supportedRuntime`이 같은지도 검증한다.

`native_fs.py`는 Linux x86_64 syscall ABI와 glibc boundary를 명시적으로 probe한 뒤 trusted root directory FD만 받는다. `openat2` beneath·no-symlink·no-magic-link를 우선 사용하고 unavailable이면 component-by-component `os.open(..., dir_fd=..., O_NOFOLLOW)`와 opened FD `fstat` identity를 사용하되 의미를 증명할 수 없는 filesystem에서는 fallback하지 않는다. Python stdlib에 없는 `openat2`, `renameat2(RENAME_NOREPLACE)`, `unlinkat`은 stdlib `ctypes`로 이미 load된 pinned `libc.so.6` syscall·symbol boundary를 호출하며 syscall number, struct size·alignment, kernel·glibc·architecture probe를 `toolchain.lock.json` supportedOS와 대조한다. SafePath는 이 FD-bound operation만 노출하고 검증 뒤 `Path.open`, 문자열 `os.rename`·`os.unlink`로 다시 열지 않는다.

Pinned backend schema allowlist는 candidate inventory·coverage·execution을 줄일 수 있는 모든 channel을 effect table로 고정한다. Mutmut 경로에서는 `only_mutate`, `paths_to_mutate`, `do_not_mutate`, regex filter, source pragma와 `mutate_only_covered_lines`를 각각 fixture로 검사하고 `mutate_only_covered_lines=false`를 강제한다. Project의 native mutmut config 자동 load, unknown option·plugin·environment override와 source exclusion pragma는 candidate 0, mutant 0에서 backendError다. Cosmic Ray를 선택하면 그 version의 module·operator·exclude·test-command schema 전체를 같은 방식으로 열거하며 미분류 key가 0개여야 한다. Bridge exclusion inventory는 config·source scan과 exact join하고 strict run의 허용 exclusion set은 비어 있어야 한다.

Admission test는 mock adapter가 아니라 선택할 backend의 actual executable을 all-killed, survivor, timeout, coverage-failure tiny project 각각에 argv로 실행한다. Candidate ID·operator·source inventory와 raw outcome를 고정 raw fixture에 대조하고 normalizer의 canonical record를 expected canonical fixture와 byte 단위로 대조한다. Process exit 0이나 summary만 신뢰하거나 mock record만 normalize한 test는 admission 통과로 인정하지 않는다.

- [ ] **단계 4: Python backend admission 결정**

실행: `scripts/uv.sh run pytest <ADMISSION_TEST> -q`

기대 A: 네 실제 tiny project와 raw fixture의 candidate·operator·상태 set, canonical normalized record가 정확히 같으면 `backend.lock.json`에 mutmut 하나만 고정

기대 B: mutant별 operator·상태·완전성을 증명하지 못하면 실패 checkout을 보존하고 test failure 근거를 그 checkout의 `docs/backend.md`와 VCS 밖 receipt에 기록함. 같은 base의 새 Cosmic Ray checkout에는 처음부터 `mutmut370.py`와 mutmut dependency가 없으며 SHA-256이 고정된 Cosmic Ray 8.7.0 wheel의 session JSON adapter로 대응 admission test를 통과시킴. Cosmic Ray도 동일한 Python runtime·pytest reporter·candidate 완전성·control·replay admission을 통과해야 한다. 선택 결과에 맞춘 `pyproject.toml`과 `uv.lock`의 exact wheel SHA-256을 확인한다. 두 adapter 동시 포함과 runtime fallback은 test가 거부한다. Lock, installed distribution, import graph와 `src/sentinel_py/mutation/`에는 선택 backend package·adapter가 각각 정확히 1개이고 선택하지 않은 backend package·adapter는 0개여야 한다.

- [ ] **단계 4A: admission 결과를 독립 commit으로 고정**

선택된 isolated checkout의 admission manifest는 단계 0..4A에서 실제 바뀐 전체를 담는다. Exact set은 `pyproject.toml`, `uv.lock`, 선택 adapter 하나를 포함한 `src/sentinel_py/{runner,workspace,mutation}/**`, backend doctor와 mutation command wiring 갱신에 필요한 `src/sentinel_py/{cli.py,orchestrator.py}`, `backend.lock.json`, unit·native FS·snapshot·lease·guardian·start-gate·pytest reporter·선택 backend admission test, 이때 존재하는 mutation fixture, `tests/fixtures/commit/t07-files.json`, `tests/acceptance/test_help_doctor.py`, `docs/{backend,operations,lineage,index,log}.md`의 concrete file이다. T06 CRAP file, evidence file, 아직 만들지 않은 `tests/acceptance/test_mutation_command.py`와 `tests/fixtures/mutation/coverage-join/**`은 제외한다. Selected backend가 Mutmut이면 `<BACKEND_ADMISSION_SELECTOR>`는 exact `mutmut-admission`, Cosmic Ray이면 exact `cosmic-ray-admission`이다. 이 selector를 `materialize-exact`로 `build/commit-inventory/T07/SENTINEL_PY/admission/stage.paths`에 만든 뒤 stage하고 cached NUL set·blob manifest를 비교한다.

```bash
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py materialize-exact --repository . --logical-repository SENTINEL_PY --task T07 --phase admission --base-head <T06_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --source tests/fixtures/commit/t07-files.json --selector <BACKEND_ADMISSION_SELECTOR> --output <workspace>/build/commit-inventory/T07/SENTINEL_PY/admission/stage.paths
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py stage-exact --repository . --logical-repository SENTINEL_PY --task T07 --phase admission --base-head <T06_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --manifest <workspace>/build/commit-inventory/T07/SENTINEL_PY/admission/stage.paths
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py commit-prepared --repository . --logical-repository SENTINEL_PY --task T07 --phase admission --prepared-receipt <PREPARED_RECEIPT> --prepared-receipt-sha256 <PREPARED_RECEIPT_SHA256> --base-head <T06_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --expected-message "feat: admit locked Python mutation backend (요구사항-03,19,22..32,43)"
test -z "$(/usr/bin/git status --short)"
```

성공 commit은 parent가 exact `backendSelectionBase` 하나이고 tree·changed path·mode·blob이 source committed receipt와 같은지 검증한다. 그 뒤에만 primary가 여전히 clean T06 HEAD·empty index인지 확인한다. Physical checkout identity가 다른 source receipt를 primary receipt로 재사용하지 않는다. `import-prepare`가 source repository identity, committed receipt path·whole-file SHA-256, logical repository `SENTINEL_PY`, base·selected commit·tree·path·mode·blob을 교차 검증해 durable adoption intent를 먼저 게시한다. `import-resume`만 local fetch, descriptor-safe worktree materialization, exact index publish와 symbolic HEAD+old OID CAS를 수행한다. `import-verify`가 최종 HEAD·tree·index·worktree, primary T06 predecessor와 source receipt를 다시 join해 `mutation-adoption` completion receipt를 no-replace 게시하고 그 path·whole-file SHA-256을 출력한다. Resume은 common imported-commit 상태기에 정의한 exact phase만 이어가며 partial·different receipt, 다른 HEAD, nonempty index나 dirty worktree이면 Git mutation 0으로 중단한다. Primary는 failed backend object·branch를 fetch하지 않으며 backend selection checkout은 T27 완료 전까지 immutable evidence로 보존한다.

실행 위치를 primary `SENTINEL_PY`로 되돌린 뒤 다음 순서를 지킨다. `<SOURCE_COMMITTED_RECEIPT>`는 selected isolated checkout의 T07 admission `committed.json` absolute path이고 `<SOURCE_COMMITTED_RECEIPT_SHA256>`은 그 whole-file SHA-256이다. 첫 command stdout의 path·digest를 `<ADOPTION_INTENT>`와 `<ADOPTION_INTENT_SHA256>`에 그대로 전달한다.

```bash
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py import-prepare --repository . --logical-repository SENTINEL_PY --source-repository <SELECTED_CHECKOUT> --source-receipt <SOURCE_COMMITTED_RECEIPT> --source-receipt-sha256 <SOURCE_COMMITTED_RECEIPT_SHA256> --predecessor-receipt <PRIMARY_T06_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PRIMARY_T06_COMMITTED_RECEIPT_SHA256> --expected-base <T06_HEAD> --expected-commit <SELECTED_COMMIT> --output-root <workspace>/build/commit-inventory/T07/SENTINEL_PY/adoption
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py import-resume --repository . --logical-repository SENTINEL_PY --intent <ADOPTION_INTENT> --intent-sha256 <ADOPTION_INTENT_SHA256>
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py import-verify --repository . --logical-repository SENTINEL_PY --intent <ADOPTION_INTENT> --intent-sha256 <ADOPTION_INTENT_SHA256>
```

- [ ] **단계 4B: T06 뒤 coverage join acceptance test RED 확인**

T06 commit과 clean-tree를 확인한 뒤 `tests/acceptance/test_mutation_command.py`와 `tests/fixtures/mutation/coverage-join/**`을 처음 만든다. Fixture는 covered·uncovered callable, stale report, callable identity ambiguity와 full production inventory 마지막 file 누락을 포함한다.

실행: `scripts/uv.sh run pytest tests/acceptance/test_mutation_command.py -q`

기대: admitted backend는 존재하지만 T06 `CrapGateResult`의 exact coverage identity를 mutation plan에 join하는 orchestration이 아직 없어 relevant case가 실패함

- [ ] **단계 5: T06 coverage join 뒤 전체 gate 통과 확인**

CLI·mutation orchestration에 T06 coverage matcher를 연결해 classified production inventory, callable identity, candidate target과 coverage report digest가 exact join한 경우만 backend를 시작한다. Coverage로 candidate를 줄이지 않고 mismatch·stale·unknown은 backend 호출 0에서 실패하게 하는 최소 구현만 추가한다.

실행: `scripts/uv.sh run pytest tests/unit/mutation tests/integration/test_native_fs.py tests/integration/test_snapshot.py tests/integration/test_sandbox_lease.py tests/integration/test_guardian.py tests/integration/test_start_gate.py tests/integration/test_pytest_reporter.py <ADMISSION_TEST> tests/acceptance/test_mutation_command.py tests/acceptance/test_help_doctor.py -q`

기대: 1개 이상 전부 killed만 exit 0, 다른 8개 상태·unknown·누락·중복·무단 제외는 각각 exit 2 또는 6, 원본 byte·metadata 불변. SIGKILL orphan은 valid HMAC tree-drained marker+age-expired일 때만 quarantine·delete하고 marker missing·guardian crash는 영구 no-touch다. PID reuse process에는 signal 0이고 공용 evidence·finding·history·export·default artifact·diagnostic raw canary 0, catchable 또는 valid-marker cleanup 뒤 sandbox raw 0이다. 선택 backend package·adapter는 lock·설치·runtime graph 전체에서 하나뿐이고 미선택 backend 흔적은 0개

- [ ] **단계 6: commit**

```bash
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py materialize-exact --repository . --task T07 --phase coverage-join --base-head <T07_ADMISSION_HEAD> --predecessor-receipt <T07_ADOPTION_RECEIPT> --predecessor-receipt-sha256 <T07_ADOPTION_RECEIPT_SHA256> --source tests/fixtures/commit/t07-files.json --selector coverage-join --output <workspace>/build/commit-inventory/T07/SENTINEL_PY/coverage-join/stage.paths
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py stage-exact --repository . --task T07 --phase coverage-join --base-head <T07_ADMISSION_HEAD> --predecessor-receipt <T07_ADOPTION_RECEIPT> --predecessor-receipt-sha256 <T07_ADOPTION_RECEIPT_SHA256> --manifest <workspace>/build/commit-inventory/T07/SENTINEL_PY/coverage-join/stage.paths
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py commit-prepared --repository . --task T07 --phase coverage-join --prepared-receipt <PREPARED_RECEIPT> --prepared-receipt-sha256 <PREPARED_RECEIPT_SHA256> --base-head <T07_ADMISSION_HEAD> --predecessor-receipt <T07_ADOPTION_RECEIPT> --predecessor-receipt-sha256 <T07_ADOPTION_RECEIPT_SHA256> --expected-message "feat: connect Python coverage to strict mutation gate (요구사항-03,19,22..32,43)"
```

### T08: SENTINEL_PY evidence·history·privacy와 전체 command

**충족 요구사항:** 요구사항-01, 요구사항-06..요구사항-08, 요구사항-19, 요구사항-28, 요구사항-29, 요구사항-32, 요구사항-42, 요구사항-45..요구사항-54

**파일:**

- 생성: `src/sentinel_py/evidence/{models.py,privacy.py,lock.py,commit_sequence.py,store.py}`
- 생성: `src/sentinel_py/history/{service.py,retention.py,export.py,resolver.py}`
- 생성: `scripts/run-e2e-fixture.sh`, `tests/fixtures/projects/{python-pass,python-history}/**`
- 테스트: `tests/unit/evidence/*`, `tests/unit/history/*`, `tests/integration/test_atomic_commit.py`, `test_cross_process_lock.py`, `test_commit_sequence.py`, `test_project_key_rotation.py`, `tests/acceptance/test_check_history.py`, `test_privacy_canary.py`
- 생성: `docs/privacy.md`
- 수정: `src/sentinel_py/{cli.py,orchestrator.py}`, `docs/index.md`, `docs/operations.md`, `docs/log.md`, `README.md`

**받는 것:** T06 `CrapGateResult`, T07 `MutationGateResult`와 `SandboxLease`, T03 evidence·sandbox-lease golden

**주는 것:** 5개 완성 command, immutable `.sentinel/state-v1`, offline repeated history, redacted export와 local JSONL resolver

이 task의 completed와 incomplete prune은 T03 `retention-marker-first-v1`을 그대로 구현한다. 두 kind 모두 marker directory sync 전 selected bundle delete는 0이다. Completed는 각 marker의 `(commitSequence <= sequenceHighWaterAtCommit && committedAtUtc < cutoffUtc)` pair union만 적용하고 marker 뒤 더 큰 sequence run을 소급 숨기지 않는다. Incomplete는 marker의 sorted immutable selection subset만 resume하며 신규 eligible run과 선택 뒤 completed가 된 run을 삭제하지 않는다. 나머지도 stored started·lease·tree-drained digest와 HMAC join을 다시 증명한 경우만 descriptor-relative delete한다.

- [ ] **단계 1: atomicity·repeated·privacy 실패 test 작성**

```python
def test_cache_replay_does_not_increment_observation(history_fixture):
    view = history_fixture("fresh-then-cache.json")
    assert view.observation_count == 1
    assert view.repeated is False

def test_evidence_failure_revokes_calculated_pass(run_fixture):
    result = run_fixture("fsync-failure-after-events")
    assert result.terminal_status == "evidenceError"
    assert result.exit_code == 7
    assert result.certification is False

def test_sequence_is_durable_before_events(sequence_fault_fixture):
    result = sequence_fault_fixture("crash-after-sequence-sync")
    assert result.next_completed_sequence == result.crashed_sequence + 1
```

- [ ] **단계 2: 실패 확인**

실행: `scripts/uv.sh run pytest tests/unit/evidence tests/unit/history tests/integration/test_atomic_commit.py tests/integration/test_cross_process_lock.py tests/integration/test_commit_sequence.py tests/integration/test_project_key_rotation.py tests/acceptance/test_check_history.py tests/acceptance/test_privacy_canary.py -q`

기대: evidence와 history module 부재로 실패

- [ ] **단계 3: immutable store와 history fold 구현**

```python
def commit_evidence(lock: CommitLock, draft: RunDraft) -> CompletedRun:
    with lock.exclusive():
        prior = read_completed_runs(draft.state_root)
        sequence = allocate_and_sync_next_sequence(draft.state_root, prior)
        events = derive_events(prior, draft, commit_sequence=sequence)
        write_synced_event_files(events)
        return atomic_commit_evidence(draft, events, commit_sequence=sequence, committed_at_utc=clock.utc_now())
```

Lock은 byte 0 length 1의 POSIX `fcntl`만 사용한다. State create·read·commit, event manifest, export, raw output과 prune traversal·delete는 T07의 `native_fs`·SafePath FD boundary만 사용하고 validation 뒤 `Path.open`, 문자열 `os.rename`·`os.unlink`로 다시 열지 않는다. Retention은 completed `committedAtUtc < cutoffUtc`, incomplete `startedAtUtc < cutoffUtc`를 사용하고 equality는 보존한다. Persistent evidence는 실제 resolved config 우선순위·digest, scope·target·mutation domain, mutmut 또는 Cosmic Ray의 exact identity·version·artifact, operator·exclusion inventory와 bridge·runner version을 privacy-safe field로 기록한다. 공용 bytes는 HMAC token과 allowlist field만 가지며 `--local-details --format jsonl`만 현재 source 위치를 stdout으로 일시 resolve한다.

T05 `ProjectKeyProvider` output은 T03 규칙대로 첫 quality run의 project state initialize 또는 exact next-epoch atomic rotation에만 적용한다. Same key·epoch 재실행은 write 0이고 invalid epoch·key 조합은 started·child 호출 0이다. Temporary create·file sync·rename·directory sync fault와 retry에서 old 또는 new complete `project.json`만 허용한다. Help·doctor·history는 envelope option을 거부하고 state create·rotate 0이다.

`CommitSequenceStore`는 T03 schema·derived HMAC·retention high-water floor를 그대로 구현한다. Exclusive lock 안에서 next sequence file을 durable commit한 뒤에만 같은 sequence의 event와 evidence를 쓰며 allocation crash gap을 재사용하지 않는다. History는 UTC가 아니라 sequence로 fold하고 invalid·duplicate·rollback에서 exit 7, 추가 write·delete 0이다.

`history prune --incomplete`는 T07의 동일 `SandboxLease` parser와 HMAC tree-drained marker oracle을 호출해 runId·projectToken·lease generation·guardian identity를 join한다. Marker missing·HMAC mismatch·guardian crash·corrupt lease와 외부 guardian start 전임을 증명하지 못한 missing lease는 incomplete run을 영구 보존한다. Valid marker, `startedAtUtc < cutoffUtc`, completed evidence 부재가 모두 맞을 때만 whole incomplete bundle을 descriptor-relative로 삭제하고 cutoff equality를 보존한다. Sandbox quarantine은 별도 `mayQuarantineSandbox=validMarker+ageExpired`만 사용한다.

`run-e2e-fixture.sh`는 고정 fixture 이름 allowlist만 받고 validated `mktemp -d`의 owner-only project copy에서 actual CLI를 실행한 뒤 EXIT·INT·TERM cleanup과 원 checked-in fixture whole manifest 불변을 확인한다. Checked-in project에서 `.sentinel`을 직접 만들지 않는다.

- [ ] **단계 4: Python end-to-end 통과 확인**

실행: `scripts/uv.sh run pytest -q`

실행: `/usr/bin/bash scripts/run-e2e-fixture.sh python-pass check --format json`

실행: `/usr/bin/bash scripts/run-e2e-fixture.sh python-history history --repeated --format json`

기대: pass fixture exit 0, history network 호출 0, canary 0건, corrupt marker exit 7, local resolver state write 0, stable stdin key의 같은 epoch repeated와 exact next-epoch 분리·atomic rotation, child key byte 0, state·export·prune path-swap에서도 validated FD 밖 read·write·rename·delete 0. Incomplete run은 marker missing·guardian crash·cutoff equality를 보존하고 valid tree-drained marker+started-before-cutoff+completed 없음만 whole run 삭제하며 sandbox는 valid marker+cleanup-age-expired만 quarantine

- [ ] **단계 5: commit**

```bash
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py prepare-and-stage --repository . --task T08 --phase evidence --base-head <T08_BASE_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --output-root <workspace>/build/commit-inventory -- src scripts/run-e2e-fixture.sh tests README.md docs
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py commit-prepared --repository . --task T08 --phase evidence --prepared-receipt <PREPARED_RECEIPT> --prepared-receipt-sha256 <PREPARED_RECEIPT_SHA256> --base-head <T08_BASE_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --expected-message "feat: complete Python evidence and history commands (요구사항-06..08,28,29,42,45..54)"
```

### T09: SENTINEL_TS 설치·SPEC·config·scope·help·doctor

**충족 요구사항:** 요구사항-02, 요구사항-05, 요구사항-09, 요구사항-18, 요구사항-21, 요구사항-32, 요구사항-42, 요구사항-55

**파일:**

- 생성: `SENTINEL_TS/{.node-version,package.json,package-lock.json,tsconfig.json,spec-lock.json}`, `SENTINEL_TS/vendor/sentinel-spec/**`
- 검증: T01의 `toolchain.lock.json`, `scripts/{bootstrap-node,node,npm}.sh`
- 생성: `src/{cli.ts,orchestrator.ts,contracts/{loader.ts,models.ts},config/{models.ts,resolver.ts,scope.ts}}`
- 생성: `src/platform/{entropy.ts,file-ops.ts,clock.ts,process.ts,project-key.ts,hmac-sha256.ts}`
- 테스트: `test/unit/contract-loader.test.ts`, `config-resolver.test.ts`, `scope.test.ts`, `test/unit/platform/{facades,project-key,hmac-sha256}.test.ts`, `test/acceptance/help-doctor.test.ts`
- fixture: `test/fixtures/scope/{two-test-files,partial-test-selection,unclassified-tsx}/`
- 생성: `docs/contracts.md`
- 수정: `README.md`, `docs/index.md`, `docs/log.md`

**받는 것:** T04 bundle bytes, commit과 manifest digest

**주는 것:** TypeScript `VerifiedContract`, `ResolvedModule`, `ClassifiedScope`, side-effect 없는 help·doctor

`package.json`의 package version은 TypeScript runtime version의 단일 원본이며 exact `0.1.0-rc.1`로 시작한다. CLI·doctor·result의 `sentinel.version`과 clean-installed package metadata가 이 값과 같은지 test한다. `package-lock.json`의 값은 파생 사본일 뿐 별도 version 원본이 아니다.

`platform`의 여섯 production dependency boundary는 entropy, file·directory sync·rename·descriptor operation, evidence·retention용 `utcNow`, timeout·lock deadline용 process `monotonicNow`, lease용 `leaseBoottimeNanos`와 UTC instant·동기화 proof를 한 결과로 돌려주는 `sampleUtcWithSyncProof`, child process spawn·signal·reap, project-key 입력, HMAC-SHA-256 계산을 감싸고 orchestrator constructor로 받는다. TypeScript Clock의 lease method는 lock-verified Koffi libc `clock_gettime(CLOCK_BOOTTIME)`와 `adjtimex` bracket만 사용하고 `number`로 변환하지 않은 bigint·decimal string 경계를 유지한다. UTC wall clock은 monotonic deadline에 사용할 수 없고 process monotonic 값은 evidence timestamp나 lease에 사용할 수 없다. Default CLI는 OS implementation만 조립하며 option·config·environment로 test implementation을 선택할 수 없다. Unit·integration test implementation은 `test/**`에만 두고 T25가 release import graph와 artifact에서 0개임을 확인한다.

`ProjectKeyProvider`는 T02의 `--project-key-stdin` canonical envelope를 bounded read·validate·decode하고 opaque 32-byte key와 epoch를 orchestrator parent에만 준 뒤 stdin을 닫는다. Raw key를 string representation·exception·argv·environment로 만들지 않으며 child process facade는 provider 사용 여부와 무관하게 stdin을 `/dev/null`로 고정한다. Option이 없으면 quality command만 OS CSPRNG local-key 경로를 사용한다. Help·doctor·history는 provider를 호출하지 않는다.

`HmacSha256` production provider는 Node 표준 `node:crypto`만 사용하며 fingerprint, projectToken과 bootToken의 모든 MAC을 계산한다. Production direct-call 우회는 static inventory 0이고 provider failure는 외부 child 호출·cleanup·prune delete 0의 exit 7 `evidenceError`다.

TypeScript foundation Clock test는 production Clock 아래의 test-only Koffi syscall seam만 주입해 T03의 두 `CLOCK_MONOTONIC_RAW`, 두 fresh zero-filled `timex(modes=0)` adjtimex와 중간 `CLOCK_REALTIME`의 exact 다섯-call trace를 검사한다. Extra·separate UTC read, nonzero field·input reuse, `STA_NANO` 정규화, maxerror·span·uncertainty 산식, 각 error·status와 forward·backward step vector를 모두 거부하거나 unknown으로 만든다. UTC instant+uncertainty+proof는 한 immutable result이고 bigint를 `number`로 바꾸지 않는다. Default Clock의 우회 Koffi/libc call static inventory는 0이다.

- [ ] **단계 0: production module 없는 TypeScript test runner scaffold 고정**

T01의 pinned Node bootstrap으로 `.node-version`, `package.json`, `package-lock.json`, `tsconfig.json`을 먼저 만든다. Scaffold에는 exact test·typecheck dependencies, scripts와 discovery 설정만 두고 `src` production module·CLI behavior는 두지 않는다. `scripts/npm.sh ci`와 lock integrity 재검증이 성공해야 한다. 그 다음 실행 위치를 `SENTINEL_SPEC`으로 바꾸고 `scripts/uv.sh run python tools/vendor_spec.py --archive ../build/t04/SENTINEL_SPEC-0.1.0-rc.1.tar --receipt ../build/t04/SENTINEL_SPEC-0.1.0-rc.1.tar.sha256.json --source-tag spec-v0.1.0-rc.1 --destination ../SENTINEL_TS/vendor/sentinel-spec --lock-output ../SENTINEL_TS/spec-lock.json`을 실행한 뒤 `SENTINEL_TS`로 돌아온다. 이어 단계 1 test를 작성하며, 단계 2는 missing production module 때문에 RED여야 한다. Install·vendor failure나 test 0개는 RED 근거가 아니다.

- [ ] **단계 1: 실패 test 작성**

```typescript
it('does not touch the project for help', async () => {
  const project = await temporaryProject();
  const result = await runCli(['--help'], project.path);
  expect(result.exitCode).toBe(0);
  expect(await pathExists(join(project.path, '.sentinel'))).toBe(false);
});

it('rejects an unclassified tsx file', async () => {
  const project = await fixture('unclassified-tsx');
  await expect(resolveScope(project)).rejects.toMatchObject({ code: 'unclassifiedSource' });
});
```

- [ ] **단계 2: 실패 확인**

실행 위치: `SENTINEL_TS`

실행: `scripts/npm.sh ci && scripts/node.sh --tool vitest -- --run test/unit/contract-loader.test.ts test/unit/config-resolver.test.ts test/unit/scope.test.ts test/unit/platform/facades.test.ts test/unit/platform/project-key.test.ts test/unit/platform/hmac-sha256.test.ts test/acceptance/help-doctor.test.ts`

기대: `src/cli.ts`와 config module 부재로 실패

- [ ] **단계 3: package와 최소 foundation 구현**

`.node-version`과 `package.json` engine은 Node `22.23.1`을 고정하고 TypeScript `7.0.2`, Vitest `4.1.11`, `@vitest/coverage-v8` `4.1.11`, AJV `8.20.0`, Koffi `3.1.6`을 exact dependency로 잠근다. `package-lock.json`은 Koffi package integrity와 packaged Linux x64 native artifact exact set·digest를 함께 고정하고 foundation test가 `CLOCK_BOOTTIME`·`adjtimex` ABI probe를 실행한다.

```typescript
export interface ResolvedModule {
  readonly moduleId: string;
  readonly root: string;
  readonly language: 'typescript';
  readonly production: readonly string[];
  readonly testCommand: readonly string[];
  readonly coverageCommand: readonly string[];
}

export function selectModule(config: Config, requested?: string): ResolvedModule {
  const candidates = config.modules.filter((value) => value.language === 'typescript');
  if (!requested && candidates.length !== 1) throw usageError('moduleSelectionRequired');
  return requireExactModule(candidates, requested);
}
```

Scope는 `.ts`, `.tsx`, `.mts`, `.cts`를 native 발견하고 declaration, generated, test, vendor, build-output 분류를 증명한다. Native test root와 Vitest naming rule로 두 test file을 모두 inventory하며 configured command가 한 file이나 name pattern만 고른 fixture도 full verified-test scope를 유지한다. Unknown config key와 ambient backend override는 거부한다.

Foundation `doctor`는 pinned Node·TypeScript·Vitest·coverage·Koffi dependency lock, vendored SPEC checksum, resolved config와 scope를 읽기만 한다. Admission 전에는 `backendPending`을 반환하고 release-capable 성공으로 오인하지 않으며, T11이 Stryker·Vitest runner backend lock·artifact·version·adapter 검사를 추가한다. 두 단계 모두 test·coverage·mutation·state write는 0이다.

Resolver test는 CLI override, project config, SPEC default 순서와 실제 evidence config digest 변화를 확인한다. Test·coverage·prepare는 argv array만 허용하고 minimal child environment만 만든다. `localCacheDir`와 generated-output root가 protected source·test·config·VCS·state와 겹치면 실행 전에 실패한다.

- [ ] **단계 4: foundation test 통과 확인**

실행: `scripts/node.sh --tool vitest -- --run test/unit/contract-loader.test.ts test/unit/config-resolver.test.ts test/unit/scope.test.ts test/unit/platform/facades.test.ts test/unit/platform/project-key.test.ts test/unit/platform/hmac-sha256.test.ts test/acceptance/help-doctor.test.ts && scripts/node.sh --tool tsc -- --noEmit --project tsconfig.json`

기대: tampered SPEC exit 5, module ambiguity exit 3, help·doctor external call 0회, facade fault는 constructor injection으로만 도달하고 default CLI에서 test implementation 선택 경로 0개

- [ ] **단계 5: commit**

```bash
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py prepare-and-stage --repository . --task T09 --phase foundation --base-head <T09_BASE_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --output-root <workspace>/build/commit-inventory -- .node-version package.json package-lock.json tsconfig.json spec-lock.json vendor src test README.md docs
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py commit-prepared --repository . --task T09 --phase foundation --prepared-receipt <PREPARED_RECEIPT> --prepared-receipt-sha256 <PREPARED_RECEIPT_SHA256> --base-head <T09_BASE_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --expected-message "feat: add TypeScript contract and scope foundation (요구사항-02,05,09,18,21,32,42,55)"
```

### T10: SENTINEL_TS native TypeScript·TSX CRAP

**충족 요구사항:** 요구사항-10, 요구사항-11, 요구사항-13..요구사항-17, 요구사항-34

**파일:**

- 생성: `src/crap/{models.ts,formula.ts,analyzer.ts,coverage.ts,semantic-site.ts}`, `src/rendering/canonical-decimal.ts`
- 테스트: `test/unit/crap/{formula,analyzer,semantic-site}.test.ts`, `test/unit/rendering/canonical-decimal.test.ts`, `test/integration/crap/coverage.test.ts`, `test/acceptance/crap-command.test.ts`
- fixture: `test/fixtures/crap/{tsx-callbacks,same-line-arrows,overload-implementation,stale,exact-boundary,decision-matrix,stable-sort}/`
- 생성: `docs/architecture.md`
- 수정: `src/{cli.ts,orchestrator.ts}`, `docs/index.md`, `docs/log.md`

**받는 것:** T09 scope, T04 exact CRAP vectors

**주는 것:** Compiler API callable inventory, Istanbul range mapping, exact CRAP result와 `sentinel-ts crap`

- [ ] **단계 1: TSX callable·exact BigInt 실패 test 작성**

```typescript
it('keeps exact integer CRAP representation', () => {
  expect(calculateCrap(4, 3, 4)).toEqual({ numerator: 17n, denominator: 4n, pass: true });
});

it('inventories a TSX callback independently', async () => {
  const rows = await analyzeFixture('tsx-callbacks');
  expect(rows.map((row) => row.kind)).toContain('tsxCallback');
  expect(new Set(rows.map((row) => row.callableId)).size).toBe(rows.length);
});
```

- [ ] **단계 2: 실패 확인**

실행: `scripts/node.sh --tool vitest -- --run test/unit/crap test/unit/rendering/canonical-decimal.test.ts test/integration/crap test/acceptance/crap-command.test.ts`

기대: `src/crap` import 실패

- [ ] **단계 3: Compiler API analyzer와 exact gate 구현**

```typescript
function gcd(a: bigint, b: bigint): bigint {
  while (b !== 0n) [a, b] = [b, a % b];
  return a;
}

export function calculateCrap(cc: number, covered: number, total: number): ExactCrap {
  if (cc < 1 || covered < 0 || total < 0 || covered > total) throw dependencyError('invalidCoverageCounts');
  if (total === 0) return coverageUnknown('zeroExecutableUnits');
  const c = BigInt(cc);
  const t = BigInt(total);
  const hit = BigInt(covered);
  let denominator = t ** 3n;
  let numerator = c ** 2n * (t - hit) ** 3n + c * denominator;
  const divisor = gcd(numerator, denominator);
  numerator /= divisor;
  denominator /= divisor;
  return { numerator, denominator, pass: numerator <= 8n * denominator };
}
```

`canonical-decimal.ts`는 T02 `canonical-decimal-v1`을 bigint division으로 구현하고 `number`, `toFixed`, `Intl`과 locale formatter를 사용하지 않는다. CRAP·coverage와 뒤의 mutation kill-rate renderer가 이 함수 하나를 호출한다. Unit test는 vendored SPEC의 reduce, `1/3`, half-even down/up, carry, zero·integer와 큰 fraction golden bytes를 직접 소비한다. Row comparator도 T02 `crap-row-order-v1`의 exact cross-multiply, UTF-8 byte path·callable ID와 raw UTF-8 byte offset을 구현하고 JS UTF-16 default sort 대신 near-equal·한글·astral golden을 소비한다.

Analyzer는 function, method, getter, setter, constructor, expression, arrow, callback을 range로 구분한다. `overload-implementation`은 여러 signature declaration을 executable callable로 꾸며내지 않고 implementation ID 1개만 기대하며, 같은 이름의 다른 type member fixture는 containing type이 다른 ID 2개를 기대한다. `decision-matrix`는 branch, loop, catch, conditional, logical decision과 switch case의 syntax별 expected 증가값과 callable별 total CC를 고정하고 nested callback decision의 parent 중복 0을 검증한다. 고정 `@vitest/coverage-v8` 4.1.11의 Istanbul JSON `fnMap`·`statementMap`을 가장 안쪽 callable에만 연결하고 provider·report format version이 다르거나 same-line 독립성을 증명하지 못하면 unknown으로 만든다.

- [ ] **단계 4: TypeScript CRAP 통과 확인**

실행: `scripts/node.sh --tool vitest -- --run test/unit/crap test/unit/rendering/canonical-decimal.test.ts test/integration/crap test/acceptance/crap-command.test.ts && scripts/node.sh --tool tsc -- --noEmit --project tsconfig.json`

기대: TS·TSX callable 전부 inventory, 모든 TypeScript CC syntax의 exact count와 nested parent 중복 0, 기약분수·canonical decimal·8.0 exact boundary와 near-equal·한글·astral stable-sort vector 통과

- [ ] **단계 5: commit**

```bash
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py prepare-and-stage --repository . --task T10 --phase crap --base-head <T10_BASE_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --output-root <workspace>/build/commit-inventory -- src/crap src/rendering src/cli.ts src/orchestrator.ts test/unit/crap test/unit/rendering test/integration/crap test/acceptance/crap-command.test.ts test/fixtures/crap docs/architecture.md docs/index.md docs/log.md
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py commit-prepared --repository . --task T10 --phase crap --prepared-receipt <PREPARED_RECEIPT> --prepared-receipt-sha256 <PREPARED_RECEIPT_SHA256> --base-head <T10_BASE_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --expected-message "feat: implement native TypeScript CRAP gate (요구사항-10,11,13..17,34)"
```

### T11: SENTINEL_TS SafePath·Vitest runner·Stryker plan adapter·gate

**충족 요구사항:** 요구사항-04, 요구사항-20, 요구사항-22..요구사항-32, 요구사항-43

**파일:**

- 생성: `src/native/linux-fs.ts`
- 생성: `src/runner/{vitest-reporter.ts,test-inventory.ts}`, `src/workspace/{safe-path.ts,snapshot.ts,process-tree.ts,sandbox-lease.ts,guardian.ts,start-gate.ts}`
- 생성: `src/mutation/{protocol.ts,stryker-plan-reporter.ts,stryker-adapter.ts,normalizer.ts,gate.ts}`, `backend.lock.json`
- 테스트: `test/unit/mutation/{normalizer,gate}.test.ts`, `test/integration/{native-fs,snapshot,sandbox-lease,guardian,start-gate,vitest-reporter,stryker-admission}.test.ts`, `test/acceptance/mutation-command.test.ts`
- fixture: `test/fixtures/mutation/{all-killed,survivor,timeout,coverage-failure,partial-test-file,partial-test-id,plan-late,plan-duplicate,set-mismatch,failed-without-assertion,source-canary,all-states}/`
- 생성: `test/fixtures/commit/t11-files.json`
- 수정: `src/cli.ts`, `src/orchestrator.ts`, `test/acceptance/help-doctor.test.ts`
- 생성: `docs/backend.md`, `docs/operations.md`, `docs/lineage.md`
- 수정: `package.json`, `package-lock.json`, `docs/index.md`, `docs/log.md`

**받는 것:** T09 scope와 T04 runner·mutation vector, 단계 5부터 T10 coverage matcher

**주는 것:** Linux descriptor-relative snapshot, nonce Vitest assertion events, independent Stryker candidate plan과 killed-only result

- [ ] **단계 0: production adapter 없는 Stryker dependency 고정**

실행 위치 `SENTINEL_TS`에서 `scripts/npm.sh lock-add-exact --dev @stryker-mutator/core@10.0.0 @stryker-mutator/vitest-runner@10.0.0 && scripts/npm.sh ci`를 실행한다. 이어 lock-verified `@stryker-mutator/core@10.0.0` package tar digest, `package.json` bin mapping과 target file mode·SHA-256을 확인하고 `scripts/node.sh --tool stryker -- --version`을 실행한다. `.bin`, npm script와 `npm exec`의 package 자동 설치 경로는 사용하지 않는다. `package-lock.json`의 상단 고정 integrity와 모든 transitive exact integrity가 일치하고 출력은 exact `10.0.0`이어야 한다. Target missing·symlink swap·digest mismatch에서는 Node·network 호출이 0이어야 한다. 이 단계에는 reporter, adapter, filesystem과 gate production source를 만들지 않는다. 따라서 단계 2는 install 실패가 아니라 missing production behavior 때문에 RED여야 한다.

- [ ] **단계 1: Stryker 순환 증거와 native path 실패 test 작성**

```typescript
it('freezes the plan before any mutant result', () => {
  const reporter = new SentinelPlanReporter();
  reporter.onMutantTested!(rawResult('m1'));
  expect(() => reporter.finalize()).toThrowError(/planEventMissing/);
});

it('rejects final IDs that differ from the plan', () => {
  const reporter = plannedReporter(['m1', 'm2']);
  reporter.onMutationTestReportReady!(reportWithIds(['m1']), metrics());
  expect(() => reporter.finalize()).toThrowError(/candidateResultSetMismatch/);
});

it('does not trust a Stryker Failed result without a typed assertion', () => {
  expect(confirmKill(strykerFailed(), runnerRuntimeError())).toEqual({ status: 'runtimeError' });
});
```

Linux filesystem test는 Koffi로 호출한 libc `openat2` beneath·no-symlink·no-magic-link, `fstat` identity, `renameat2`, process-tree 종료와 edit-and-restore를 확인한다. Koffi package integrity, `supportedOS`의 kernel·glibc ABI와 syscall probe가 lock과 다르면 dependencyError다. Host libc file의 우연한 byte digest는 portability 계약으로 사용하지 않는다.

`SandboxLease`는 T03 `sandbox-lease-v1`, `sandbox-control-layout-v1`, guardian과 exact age policy를 byte 단위로 구현한다. Approved root에서 lease·fixed marker filename·relative leaf·owner·mode·device·inode를 Koffi descriptor로 검증하고 gate 뒤에만 backend를 실행한다. Lease age는 T09 Clock의 `leaseBoottimeNanos`와 `sampleUtcWithSyncProof`만 소비한다. Catch 가능한 terminal은 guardian의 authenticated tree-drained marker 뒤 정리한다. 다음 run은 valid marker와 age-expired가 모두 맞을 때만 no-replace quarantine·directory sync 뒤 descriptor-relative delete한다. Marker missing·guardian crash·foreign/duplicate leaf·HMAC/path identity 불명은 cross-boot에서도 영구 no-touch다. Explicit `--raw-dir`은 별도다.

TypeScript package의 first-party guardian은 T03 subreaper·Koffi pidfd·HMAC tree-drained 계약을 전부 구현한다. Controller EOF와 정상 drain에서 `setsid`·double-fork descendant가 adopted direct child가 될 때마다 pidfd TERM·KILL과 `waitid(P_PIDFD)`를 반복하고 ECHILD 뒤에만 marker를 durable commit한다. Numeric `kill`·`killpg`·`tgkill`은 0이다. Guardian SIGKILL·marker/HMAC 불명은 cross-boot와 age-expired에서도 영구 unknown·no-delete다.

Mutation 결과의 killed/in-scope fraction도 T10 reduce와 `canonical-decimal-v1` 하나로만 render한다. Gate는 decimal percentage가 아니라 exact count equality를 사용하고 0 denominator는 percentage를 만들지 않고 quality failure다.

`VitestTestInventory`는 classified test root·naming rule로 발견한 모든 test file을 explicit Vitest list/report argv로 수집해 canonical test ID inventory를 만든다. 각 native test file은 ID가 1개 이상이어야 하며 collection inventory와 두 fresh baseline의 started·terminal ID가 exact join해야 한다. Configured command가 한 file이나 name pattern만 고르거나 0·missing·extra·duplicate ID가 생기면 coverage·candidate·mutant 호출 0에서 baselineFailed다. Acceptance는 완전한 같은 selection baseline을 distinct nonce로 두 번 fresh 실행하고 failure·ID mismatch에서 coverage·candidate·mutant 호출 0을 확인한다. Prepare는 snapshot 내부 argv·minimal environment만 사용하고 모든 generated-output root의 protected overlap·symlink·hardlink·path swap을 거부한다.

`help-doctor.test.ts`는 T09의 `backendPending`을 admission 뒤 성공으로 바꾸고 Stryker·Vitest runner backend lock·artifact·version·adapter 각 변조가 dependencyError이며 test·coverage·mutation·state write는 0회임을 검증한다.

단계 1..4A에는 admission에 필요한 unit·integration test와 fixture만 만든다. 사람이 관리하는 `test/fixtures/commit/t11-files.json`은 `admission`과 `coverage-join` selector별 sorted concrete path array를 미리 고정하고 admission array는 자기 fixture path와 mutation command wiring을 바꾸는 `src/cli.ts`, `src/orchestrator.ts`를 모두 포함한다. Test가 각 selector를 task 책임과 actual changed set에 exact 대조한다. T10 coverage matcher가 필요한 `test/acceptance/mutation-command.test.ts`와 coverage-join fixture는 단계 4A의 clean-tree checkpoint 뒤 단계 4B에서 먼저 실패하도록 작성한다.

- [ ] **단계 2: 실패 확인**

실행: `scripts/node.sh --tool vitest -- --run test/unit/mutation test/integration/native-fs.test.ts test/integration/snapshot.test.ts test/integration/sandbox-lease.test.ts test/integration/guardian.test.ts test/integration/start-gate.test.ts test/integration/vitest-reporter.test.ts test/integration/stryker-admission.test.ts`

기대: reporter와 libc FFI adapter 부재로 실패

- [ ] **단계 3: 고정 libc FFI boundary와 두 개의 독립 Stryker 경계 구현**

```typescript
export class SentinelPlanReporter implements Reporter {
  private plan?: ReadonlyMap<string, Candidate>;
  private outcomeSeen = false;

  onMutationTestingPlanReady(event: MutationTestingPlanReadyEvent): void {
    if (this.plan || this.outcomeSeen) throw backendError('planEventOrderInvalid');
    this.plan = canonicalizePlans(event.mutantPlans);
  }

  onMutantTested(result: Readonly<MutantResult>): void {
    this.outcomeSeen = true;
    if (!this.plan) throw backendError('planEventMissing');
    recordRawOutcome(result);
  }
}
```

공식 plan reporter는 candidate inventory만 증명한다. Stryker `Failed`와 `failureMessage`는 assertion type을 증명하지 못하므로 killed 근거로 직접 쓰지 않는다. 고정 Vitest wrapper가 assertion class, test ID, execution nonce, original control과 same-mutant replay HMAC signature를 private event로 제공해야 한다. 이 event가 없거나 cache·retry 흔적이 있으면 `runtimeError` 또는 `backendError`다.

Package는 단계 0에서 고정한 `@stryker-mutator/core@10.0.0`, `@stryker-mutator/vitest-runner@10.0.0`, T09의 Vitest `4.1.11`·Koffi `3.1.6`과 native artifact를 그대로 사용한다. First-party C·C++ addon은 만들지 않고 TypeScript FFI wrapper 자체를 self-quality 범위에 포함한다. Adapter는 full classified production inventory를 exact `mutate` set으로 만들고 `excludedMutations=[]`, `coverageAnalysis=perTest`, `incremental=false`, `force=true`, `inPlace=false`, `ignoreStatic=false`를 생성한 폐쇄형 config로 강제한다. Stryker mutation glob 축소, `excludedMutations`, ignore comment, ignorer plugin, unknown option·plugin·environment override와 project `stryker.conf.*` 자동 load는 candidate 0, mutant 0에서 backendError다. Pinned Stryker schema의 inventory·coverage·execution-reducing field가 모두 effect table에 분류되고 bridge exclusion inventory가 source·config scan과 exact join해야 한다. JSON의 source·replacement는 공용 model 전에 폐기한다.

Admission test는 mock reporter가 아니라 고정 Stryker executable을 all-killed, survivor, timeout, coverage-failure tiny project 각각에 argv로 실행한다. Plan event의 candidate ID·operator·target inventory와 raw result set을 고정 raw fixture에 대조하고 normalizer의 canonical record를 expected canonical fixture와 byte 단위로 대조한다. Process exit 0이나 summary footer만 신뢰하거나 mock event만 normalize한 test는 admission 통과로 인정하지 않는다.

- [ ] **단계 4: TypeScript backend admission 통과 확인**

실행: `scripts/node.sh --tool vitest -- --run test/integration/vitest-reporter.test.ts test/integration/stryker-admission.test.ts && scripts/node.sh --tool tsc -- --noEmit --project tsconfig.json`

기대: 네 tiny project의 실제 Stryker plan·operator·raw result와 canonical normalized record가 고정 fixture와 정확히 일치함. Plan 누락·중복·지연·set mismatch는 exit 6이고 untyped Failed는 killed 금지, assertion type·nonce·control·replay가 모두 확인된 경우만 admission 통과

- [ ] **단계 4A: admission 결과를 독립 commit으로 고정**

Admission manifest는 단계 0..4A에서 실제 바뀐 전체를 담는다. Exact set은 `package.json`, `package-lock.json`, `src/native/linux-fs.ts`, `src/{runner,workspace,mutation}/**`, backend doctor와 mutation command wiring 갱신에 필요한 `src/{cli.ts,orchestrator.ts}`, `backend.lock.json`, unit·native FS·snapshot·lease·guardian·start-gate·Vitest reporter·Stryker admission test, 이때 존재하는 mutation fixture, `test/fixtures/commit/t11-files.json`, `test/acceptance/help-doctor.test.ts`, `docs/{backend,operations,lineage,index,log}.md`의 concrete file이다. T10 CRAP file, evidence file, 아직 만들지 않은 `test/acceptance/mutation-command.test.ts`와 `test/fixtures/mutation/coverage-join/**`은 제외한다. `materialize-exact --selector admission`으로 이 set을 `build/commit-inventory/T11/SENTINEL_TS/admission/stage.paths`에 만든 뒤 stage하고 cached NUL set·blob manifest를 비교한다.

```bash
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py materialize-exact --repository . --task T11 --phase admission --base-head <T10_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --source test/fixtures/commit/t11-files.json --selector admission --output <workspace>/build/commit-inventory/T11/SENTINEL_TS/admission/stage.paths
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py stage-exact --repository . --task T11 --phase admission --base-head <T10_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --manifest <workspace>/build/commit-inventory/T11/SENTINEL_TS/admission/stage.paths
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py commit-prepared --repository . --task T11 --phase admission --prepared-receipt <PREPARED_RECEIPT> --prepared-receipt-sha256 <PREPARED_RECEIPT_SHA256> --base-head <T10_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --expected-message "feat: admit locked TypeScript mutation backend (요구사항-04,20,22..32,43)"
test -z "$(/usr/bin/git status --short)"
```

- [ ] **단계 4B: T10 뒤 coverage join acceptance test RED 확인**

T10 commit과 clean-tree를 확인한 뒤 `test/acceptance/mutation-command.test.ts`와 `test/fixtures/mutation/coverage-join/**`을 처음 만든다. Fixture는 covered·uncovered callable, stale report, callable identity ambiguity와 full production inventory 마지막 file 누락을 포함한다.

실행: `scripts/node.sh --tool vitest -- --run test/acceptance/mutation-command.test.ts`

기대: admitted Stryker adapter는 존재하지만 T10 exact coverage identity와 mutation plan을 join하는 orchestration이 아직 없어 relevant case가 실패함

- [ ] **단계 5: T10 coverage join 뒤 전체 gate 통과 확인**

CLI·mutation orchestration에 T10 coverage matcher를 연결해 classified production inventory, callable identity, candidate target과 coverage report digest가 exact join한 경우만 backend를 시작한다. Coverage로 candidate를 줄이지 않고 mismatch·stale·unknown은 backend 호출 0에서 실패하게 하는 최소 구현만 추가한다.

실행: `scripts/node.sh --tool vitest -- --run test/unit/mutation test/integration/native-fs.test.ts test/integration/snapshot.test.ts test/integration/sandbox-lease.test.ts test/integration/guardian.test.ts test/integration/start-gate.test.ts test/integration/vitest-reporter.test.ts test/integration/stryker-admission.test.ts test/acceptance/mutation-command.test.ts test/acceptance/help-doctor.test.ts && scripts/node.sh --tool tsc -- --noEmit --project tsconfig.json`

기대: plan 누락·중복·지연·set mismatch exit 6, untyped Failed는 killed 금지, timeout·runtime·compile·ignored는 exit 2, typed assertion+control+replay all killed만 exit 0, source canary 불변. SIGKILL orphan은 valid HMAC tree-drained marker+age-expired일 때만 quarantine·delete하고 marker missing·guardian crash는 영구 no-touch다. PID reuse process에는 signal 0이며 공용 evidence·finding·history·export·default artifact·diagnostic raw canary 0, catchable 또는 valid-marker cleanup 뒤 sandbox raw 0이다.

- [ ] **단계 6: commit**

```bash
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py materialize-exact --repository . --task T11 --phase coverage-join --base-head <T11_ADMISSION_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --source test/fixtures/commit/t11-files.json --selector coverage-join --output <workspace>/build/commit-inventory/T11/SENTINEL_TS/coverage-join/stage.paths
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py stage-exact --repository . --task T11 --phase coverage-join --base-head <T11_ADMISSION_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --manifest <workspace>/build/commit-inventory/T11/SENTINEL_TS/coverage-join/stage.paths
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py commit-prepared --repository . --task T11 --phase coverage-join --prepared-receipt <PREPARED_RECEIPT> --prepared-receipt-sha256 <PREPARED_RECEIPT_SHA256> --base-head <T11_ADMISSION_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --expected-message "feat: connect TypeScript coverage to strict mutation gate (요구사항-04,20,22..32,43)"
```

### T12: SENTINEL_TS evidence·history·privacy와 전체 command

**충족 요구사항:** 요구사항-02, 요구사항-06..요구사항-08, 요구사항-20, 요구사항-28, 요구사항-29, 요구사항-32, 요구사항-42, 요구사항-45..요구사항-54

**파일:**

- 생성: `src/evidence/{models.ts,privacy.ts,fcntl-lock.ts,commit-sequence.ts,store.ts}`
- 생성: `src/history/{service.ts,retention.ts,export.ts,resolver.ts}`
- 생성: `scripts/run-e2e-fixture.sh`, `test/fixtures/projects/{typescript-pass,typescript-history}/**`
- 테스트: `test/unit/evidence/*`, `test/unit/history/*`, `test/integration/{atomic-commit,cross-process-lock,commit-sequence,project-key-rotation}.test.ts`, `test/acceptance/{check-history,privacy-canary}.test.ts`
- 생성: `docs/privacy.md`
- 수정: `src/{cli.ts,orchestrator.ts,native/linux-fs.ts}`, `README.md`, `docs/index.md`, `docs/operations.md`, `docs/log.md`

**받는 것:** T10 CRAP, T11 mutation과 `SandboxLease`, T03 evidence·sandbox-lease golden

**주는 것:** 완성된 `sentinel-ts` 5개 command와 POSIX-compatible immutable history

이 task의 completed와 incomplete prune은 T03 `retention-marker-first-v1`을 그대로 구현한다. 두 kind 모두 marker directory sync 전 selected bundle delete는 0이다. Completed는 각 marker의 `(commitSequence <= sequenceHighWaterAtCommit && committedAtUtc < cutoffUtc)` pair union만 적용하고 marker 뒤 더 큰 sequence run을 소급 숨기지 않는다. Incomplete는 marker의 sorted immutable selection subset만 resume하며 신규 eligible run과 선택 뒤 completed가 된 run을 삭제하지 않는다. 나머지도 stored started·lease·tree-drained digest와 HMAC join을 다시 증명한 경우만 descriptor-relative delete한다.

- [ ] **단계 1: lock·retention·privacy 실패 test 작성**

```typescript
it('keeps a completed run whose commit equals the cutoff', async () => {
  const view = await historyFixture('completed-at-cutoff');
  expect(view.runs).toHaveLength(1);
  expect(view.truncated).toBe(false);
});

it('cancels calculated pass when evidence commit fails', async () => {
  const result = await runFixture('directory-fsync-failure');
  expect(result).toMatchObject({ terminalStatus: 'evidenceError', exitCode: 7, certification: false });
});

it('never reuses a sequence after allocation sync crashes', async () => {
  const result = await sequenceFaultFixture('crash-after-sequence-sync');
  expect(result.nextCompletedSequence).toBe(result.crashedSequence + 1n);
});
```

- [ ] **단계 2: 실패 확인**

실행: `scripts/node.sh --tool vitest -- --run test/unit/evidence test/unit/history test/integration/atomic-commit.test.ts test/integration/cross-process-lock.test.ts test/integration/commit-sequence.test.ts test/integration/project-key-rotation.test.ts test/acceptance/check-history.test.ts test/acceptance/privacy-canary.test.ts`

기대: state store 부재로 실패

- [ ] **단계 3: fcntl store와 offline history 구현**

고정 Koffi adapter는 libc `fcntl`로 `commit.lock` byte 0 length 1에 `F_RDLCK` 또는 `F_WRLCK`를 적용하고 FD가 닫힐 때만 해제한다. Event와 evidence는 file sync, directory sync, same-directory atomic rename 순서를 지킨다.

T09 `ProjectKeyProvider` output은 T03 규칙대로 첫 quality run의 project state initialize 또는 exact next-epoch atomic rotation에만 적용한다. Same key·epoch 재실행은 write 0이고 invalid epoch·key 조합은 started·child 호출 0이다. Temporary create·file sync·rename·directory sync fault와 retry에서 old 또는 new complete `project.json`만 허용한다. Help·doctor·history는 envelope option을 거부하고 state create·rotate 0이다.

`CommitSequenceStore`는 T03 schema·derived HMAC·retention high-water floor를 그대로 구현한다. Exclusive lock 안에서 next sequence file을 durable commit한 뒤에만 같은 sequence의 event와 evidence를 쓰며 allocation crash gap을 재사용하지 않는다. History는 UTC가 아니라 sequence로 fold하고 invalid·duplicate·rollback에서 exit 7, 추가 write·delete 0이다.

`history prune --incomplete`는 T11의 동일 `SandboxLease` parser와 HMAC tree-drained marker oracle을 호출해 runId·projectToken·lease generation·guardian identity를 join한다. Marker missing·HMAC mismatch·guardian crash·corrupt lease와 외부 guardian start 전임을 증명하지 못한 missing lease는 incomplete run을 영구 보존한다. Valid marker, `startedAtUtc < cutoffUtc`, completed evidence 부재가 모두 맞을 때만 whole incomplete bundle을 descriptor-relative로 삭제하고 cutoff equality를 보존한다. Sandbox quarantine은 별도 `mayQuarantineSandbox=validMarker+ageExpired`만 사용한다.

Persistent evidence는 실제 resolved config 우선순위·digest, scope·target·mutation domain, Stryker exact identity·version·artifact, operator·exclusion inventory와 bridge·runner version을 privacy-safe field로 기록한다.

`run-e2e-fixture.sh`는 고정 fixture 이름 allowlist만 받고 validated `mktemp -d`의 owner-only project copy에서 actual CLI를 실행한 뒤 EXIT·INT·TERM cleanup과 원 checked-in fixture whole manifest 불변을 확인한다. Checked-in project에서 `.sentinel`을 직접 만들지 않는다.

```typescript
export async function commitRun(lock: PosixLock, draft: RunDraft): Promise<CompletedRun> {
  return lock.withExclusive(async () => {
    const prior = await readCompletedRuns(draft.stateRoot);
    const sequence = await allocateAndSyncNextSequence(draft.stateRoot, prior);
    const events = deriveEvents(prior, draft, sequence);
    await writeSyncedEvents(events);
    return atomicCommitEvidence(draft, events, sequence, clock.utcNow());
  });
}
```

- [ ] **단계 4: TypeScript end-to-end 통과 확인**

실행: `scripts/node.sh --tool tsc -- --project tsconfig.json && scripts/node.sh --tool vitest -- --run && scripts/node.sh --tool tsc -- --noEmit --project tsconfig.json`

실행: `/usr/bin/bash scripts/run-e2e-fixture.sh typescript-pass check --format json`

실행: `/usr/bin/bash scripts/run-e2e-fixture.sh typescript-history history --repeated --format json`

기대: 5개 command 계약, repeated history, retention equality, canary 0건, local JSONL write 0, stable stdin key의 같은 epoch repeated와 exact next-epoch 분리·atomic rotation, child key byte 0 통과. Incomplete run은 marker missing·guardian crash·cutoff equality를 보존하고 valid tree-drained marker+started-before-cutoff+completed 없음만 whole run 삭제하며 sandbox는 valid marker+cleanup-age-expired만 quarantine

- [ ] **단계 5: commit**

```bash
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py prepare-and-stage --repository . --task T12 --phase evidence --base-head <T12_BASE_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --output-root <workspace>/build/commit-inventory -- src scripts/run-e2e-fixture.sh test README.md docs
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py commit-prepared --repository . --task T12 --phase evidence --prepared-receipt <PREPARED_RECEIPT> --prepared-receipt-sha256 <PREPARED_RECEIPT_SHA256> --base-head <T12_BASE_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --expected-message "feat: complete TypeScript evidence and history commands (요구사항-06..08,28,29,42,45..54)"
```

### T13: SENTINEL_GO 설치·SPEC·config·scope·help·doctor

**충족 요구사항:** 요구사항-05, 요구사항-09, 요구사항-18, 요구사항-21, 요구사항-32, 요구사항-39, 요구사항-42, 요구사항-55

**파일:**

- 생성: `SENTINEL_GO/go.mod`, `go.sum`, `spec-lock.json`, `vendor/sentinel-spec/**`
- 검증: T01에서 online·offline mode까지 완성한 `toolchain.lock.json`, `scripts/{bootstrap-go,go}.sh`
- 생성: `tools/testinventory/main.go`, `tools/testinventory/main_test.go`, `test-inventory/foundation.json`
- 생성: `cmd/sentinel-go/main.go`, `internal/version/version.go`, `internal/cli/cli.go`, `internal/orchestrator/orchestrator.go`
- 생성: `internal/contracts/{loader.go,models.go}`, `internal/config/{models.go,resolver.go,scope.go}`
- 생성: `internal/platform/{entropy.go,fileops.go,clock.go,process.go,projectkey.go,hmacsha256.go}`
- 테스트: 각 package `_test.go`, `internal/version/version_test.go`, `internal/platform/*_test.go`, `testdata/{polyglot,unclassified}/`
- 생성: `docs/contracts.md`
- 수정: `README.md`, `docs/index.md`, `docs/log.md`

**받는 것:** T04 bundle bytes, commit과 manifest digest

**주는 것:** Go `VerifiedContract`, `ResolvedModule`, `ClassifiedScope`, side-effect 없는 help·doctor

`internal/platform`의 여섯 production dependency interface는 entropy, file·directory sync·rename·descriptor operation, evidence·retention용 `UtcNow`, timeout·lock deadline용 process `MonotonicNow`, lease용 `LeaseBoottimeNanos`와 UTC instant·동기화 proof를 한 결과로 돌려주는 `SampleUtcWithSyncProof`, child process spawn·signal·reap, project-key 입력, HMAC-SHA-256 계산을 감싸고 orchestrator constructor로 받는다. Go Clock의 lease method는 lock-verified `golang.org/x/sys/unix`의 `ClockGettime(CLOCK_BOOTTIME)`와 `Adjtimex` bracket만 쓰고 uint64·decimal string 경계를 유지한다. UTC wall clock은 monotonic deadline에 사용할 수 없고 process monotonic 값은 evidence timestamp나 lease에 사용할 수 없다. Default CLI는 OS implementation만 조립하며 flag·config·environment로 test implementation을 선택할 수 없다. Test implementation은 `_test.go` 또는 test-only internal package에만 두고 T25가 release import graph와 binary에서 0개임을 확인한다.

`ProjectKeyProvider`는 T02의 `--project-key-stdin` canonical envelope를 bounded read·validate·decode하고 opaque 32-byte key와 epoch를 orchestrator parent에만 준 뒤 stdin을 닫는다. Raw key를 string representation·error·argv·environment로 만들지 않으며 child process facade는 provider 사용 여부와 무관하게 stdin을 `/dev/null`로 고정한다. Flag가 없으면 quality command만 OS CSPRNG local-key 경로를 사용한다. Help·doctor·history는 provider를 호출하지 않는다.

`HmacSha256` production provider는 Go 표준 `crypto/hmac`·`crypto/sha256`만 사용하며 fingerprint, projectToken과 bootToken의 모든 MAC을 계산한다. Production direct-call 우회는 static inventory 0이고 provider failure는 외부 child 호출·cleanup·prune delete 0의 exit 7 `evidenceError`다.

Go foundation Clock test는 production Clock 아래 unexported test syscall interface만 주입해 T03의 두 `CLOCK_MONOTONIC_RAW`, 두 fresh zero-value `unix.Timex(Modes=0)` Adjtimex와 중간 `CLOCK_REALTIME`의 exact 다섯-call trace를 검사한다. Extra·separate UTC read, struct reuse·nonzero field, `STA_NANO` 정규화, maxerror·span·uncertainty 산식, 각 error·status와 forward·backward step vector를 모두 거부하거나 unknown으로 만든다. UTC instant+uncertainty+proof는 한 immutable value다. Production direct `unix.ClockGettime`·`Adjtimex`는 default adapter 밖 static inventory 0이다. `internal/version/version.go`의 release constant는 foundation에서 `0.1.0-rc.1`로 시작하고 CLI·doctor·result가 이 한 값을 소비하며 `version_test.go`가 세 출력의 equality를 고정한다.

- [ ] **단계 0: production package 없는 Go test runner scaffold 고정**

T01의 pinned Go bootstrap으로 `go.mod`, `go.sum`, `tools/testinventory/main.go`, `tools/testinventory/main_test.go`와 `test-inventory/foundation.json`을 먼저 만든다. 이 scaffold는 exact dependency와 test event verifier만 담고 `cmd/sentinel-go`·`internal` production package는 두지 않는다. 실행 위치 `SENTINEL_GO`에서 `/usr/bin/bash scripts/bootstrap-go.sh && scripts/go.sh mod download && scripts/go.sh mod verify && scripts/go.sh --offline test ./tools/testinventory -count=1`을 실행해 public checksum database를 허용한 첫 두 module command로 owner-only cache를 채우고 마지막 test는 network 0에서 성공시킨다. 이어 실행 위치 `SENTINEL_SPEC`에서 `scripts/uv.sh run python tools/vendor_spec.py --archive ../build/t04/SENTINEL_SPEC-0.1.0-rc.1.tar --receipt ../build/t04/SENTINEL_SPEC-0.1.0-rc.1.tar.sha256.json --source-tag spec-v0.1.0-rc.1 --destination ../SENTINEL_GO/vendor/sentinel-spec --lock-output ../SENTINEL_GO/spec-lock.json`을 실행하고 `SENTINEL_GO`로 돌아온다. 단계 1 test를 쓴 뒤 단계 2는 missing production package 때문에 RED여야 하며 module download·vendor failure나 test 0개는 RED 근거가 아니다.

- [ ] **단계 1: SPEC tamper와 native scope 실패 test 작성**

Foundation test와 함께 zero-test oracle을 먼저 만든다. `foundation.json`은 사람이 작성한 package·Test·Example·Fuzz ID와 layer를 담고, expected ID 0개·실제 started 0개·missing·extra·duplicate·terminal 누락을 모두 실패시키는 verifier test를 포함한다.

```go
func TestHelpDoesNotCreateState(t *testing.T) {
	project := t.TempDir()
	result := runCLI(t, project, "--help")
	if result.ExitCode != 0 { t.Fatalf("exit=%d", result.ExitCode) }
	if _, err := os.Stat(filepath.Join(project, ".sentinel")); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("help wrote state: %v", err)
	}
}

func TestScopeRejectsUnclassifiedGoSource(t *testing.T) {
	_, err := ResolveFixture("unclassified")
	assertCode(t, err, "unclassifiedSource")
}
```

- [ ] **단계 2: 실패 확인**

실행 위치: `SENTINEL_GO`

실행: `scripts/go.sh --offline test ./tools/testinventory ./internal/contracts ./internal/config ./internal/platform ./internal/cli -count=1`

기대: package 부재로 실패

- [ ] **단계 3: module과 foundation 구현**

`go.mod`는 `go 1.27.0`, `toolchain go1.27.1`과 `golang.org/x/sys v0.36.0` exact requirement를 고정한다. Foundation compile 전에 module zip·go.mod checksum을 `go.sum`과 public checksum database에 대조해 verified cache를 만들고, network를 끈 재실행에서 `ClockGettime(CLOCK_BOOTTIME)`·`Adjtimex` ABI probe와 platform test를 통과시킨다. `scripts/go.sh`는 online·offline 모두 launcher 전용 flag를 Go argv에서 제거하고 inherited environment를 지운 뒤 pinned `GOROOT`, verified owner-only `GOMODCACHE`·`GOCACHE`, `GOTOOLCHAIN=local`, `GOENV=off`, `GOWORK=off`와 exact empty `GOFLAGS`, `GOPRIVATE`, `GONOPROXY`, `GONOSUMDB`를 내부에서 고정한다. Populate profile은 `GOPROXY=https://proxy.golang.org`만 허용해 `direct` fallback을 없애고 `GOSUMDB=sum.golang.org`, `GOVCS=*:off`를 고정한다. Offline mode는 `GOPROXY=off`, `GOSUMDB=off`, `GOVCS=*:off`를 쓴다. Missing module이나 proxy miss는 VCS spawn·network fallback 없이 nonzero로 끝나며 wrapper test는 hostile user `go env -w` file, parent `go.work`, inherited `GOENV`·`GOWORK`·`GOFLAGS`·`GOVCS`, proxy 404·410과 loopback network canary가 child selection과 dependency graph을 바꾸지 못하고 child environment가 exact allowlist인지 확인한다.

```go
type ResolvedModule struct {
	ModuleID        string
	Root            string
	Language        string
	Production      []string
	TestCommand     []string
	CoverageCommand []string
}

func SelectModule(config Config, requested string) (ResolvedModule, error) {
	candidates := onlyLanguage(config.Modules, "go")
	if requested == "" && len(candidates) != 1 { return ResolvedModule{}, usageError("moduleSelectionRequired") }
	return requireExactModule(candidates, requested)
}
```

Scope는 `.go`와 `_test.go`를 native 발견하고 production, test, generated, vendor, build-output ownership을 exact 대조한다. Foundation `doctor`는 pinned Go runtime, `go.sum` dependency lock, vendored SPEC checksum, resolved config와 scope를 읽기만 한다. Admission 전에는 `backendPending`을 반환하고 release-capable 성공으로 오인하지 않으며 T15가 mutate4go archive·patch·companion·backend lock identity 검사를 추가한다. 두 단계 모두 test·coverage·mutation·state write는 0이다.

Resolver는 argv command, `prepareCommand`, environment name allowlist·secret reference, `localCacheDir`·generated-output root와 CLI override precedence를 T02 golden으로 검증한다. Ambient environment로 backend나 scope를 바꾸거나 protected root와 output을 겹치게 할 수 없다.

Test inventory verifier는 `_test.go`를 static parse해 runnable Test·Example·Fuzz ID를 만들고 pinned `go test -json -count=1`의 started·terminal event와 exact join한다. Manifest의 package·ID·layer와 missing·extra가 0이고 현재 task의 required layer count가 1 이상일 때만 성공한다. Human output이나 `go test` process exit 0만으로 성공하지 않는다.

- [ ] **단계 4: foundation 통과 확인**

실행: `scripts/go.sh --offline run ./tools/testinventory --manifest test-inventory/foundation.json && scripts/go.sh --offline test ./internal/contracts ./internal/config ./internal/platform ./internal/cli -count=1 && scripts/go.sh --offline vet ./...`

기대: tampered SPEC dependencyError, polyglot module exact 선택, help·doctor write 0, facade fault는 constructor injection으로만 도달하고 default binary에서 test implementation 선택 경로 0개

- [ ] **단계 5: commit**

```bash
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py prepare-and-stage --repository . --task T13 --phase foundation --base-head <T13_BASE_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --output-root <workspace>/build/commit-inventory -- go.mod go.sum spec-lock.json vendor cmd internal tools/testinventory test-inventory/foundation.json testdata README.md docs
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py commit-prepared --repository . --task T13 --phase foundation --prepared-receipt <PREPARED_RECEIPT> --prepared-receipt-sha256 <PREPARED_RECEIPT_SHA256> --base-head <T13_BASE_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --expected-message "feat: add Go contract and scope foundation (요구사항-05,09,18,21,32,39,42,55)"
```

### T14: SENTINEL_GO native CRAP

**충족 요구사항:** 요구사항-10, 요구사항-11, 요구사항-14..요구사항-17, 요구사항-34, 요구사항-39

**파일:**

- 생성: `internal/crap/{models.go,formula.go,analyzer.go,coverage.go,semantic_site.go}`, `internal/rendering/canonical_decimal.go`
- 생성: `test-inventory/crap.json`
- 테스트: 같은 package의 `_test.go`, `internal/rendering/canonical_decimal_test.go`, `testdata/crap/{function-literal,same-line,same-name-receivers,stale,exact-boundary,decision-matrix,stable-sort}/`
- 생성: `docs/architecture.md`
- 수정: `internal/cli/cli.go`, `internal/orchestrator/orchestrator.go`, `docs/index.md`, `docs/log.md`

**받는 것:** T13 scope, T04 CRAP vector, pinned `crap4go` corpus

**주는 것:** `go/ast` callable inventory, coverprofile mapping, exact Go CRAP result와 `sentinel-go crap`

- [ ] **단계 1: function literal과 exact fraction 실패 test 작성**

```go
func TestCalculateCrapUsesExactIntegers(t *testing.T) {
	got := Calculate(4, 3, 4)
	if got.Numerator.Cmp(big.NewInt(17)) != 0 || got.Denominator.Cmp(big.NewInt(4)) != 0 {
		t.Fatalf("got %s/%s", got.Numerator, got.Denominator)
	}
}

func TestFunctionLiteralIsIndependentCallable(t *testing.T) {
	rows := AnalyzeFixture(t, "function-literal")
	requireKinds(t, rows, "function", "functionLiteral")
}
```

- [ ] **단계 2: 실패 확인**

실행: `scripts/go.sh --offline test ./internal/crap ./internal/rendering ./internal/cli -count=1`

기대: `internal/crap` package 부재로 실패

- [ ] **단계 3: AST·coverprofile·gate 구현**

```go
func Calculate(cc, covered, total int64) (ExactCrap, error) {
	if cc < 1 || covered < 0 || total < 0 || covered > total { return ExactCrap{}, dependencyError("invalidCoverageCounts") }
	if total == 0 { return unknownCrap("zeroExecutableUnits"), nil }
	c, t, hit := big.NewInt(cc), big.NewInt(total), big.NewInt(covered)
	denominator := new(big.Int).Exp(t, big.NewInt(3), nil)
	missedCubed := new(big.Int).Exp(new(big.Int).Sub(t, hit), big.NewInt(3), nil)
	numerator := new(big.Int).Add(new(big.Int).Mul(new(big.Int).Mul(c, c), missedCubed), new(big.Int).Mul(c, denominator))
	return exactCrap(numerator, denominator), nil
}
```

`exactCrap`은 `big.Int.GCD`로 numerator·denominator를 나누고 zero는 `0/1`로 canonicalize한다. `internal/rendering`은 T02 `canonical-decimal-v1`을 `big.Int.QuoRem`으로 구현하며 `big.Float`, `float64`, format·locale rounding을 사용하지 않는다. CRAP·coverage와 뒤의 mutation kill-rate renderer가 이 함수 하나를 호출한다. Unit test는 vendored SPEC의 reduce, `1/3`, half-even down/up, carry, zero·integer와 큰 fraction golden bytes를 직접 소비한다. Row comparator도 T02 `crap-row-order-v1`의 exact cross-multiply, UTF-8 byte path·callable ID와 raw UTF-8 byte offset을 구현하고 near-equal·한글·astral golden을 소비한다.

`go/ast` analyzer는 function, method, function literal을 분리하고 child range coverage를 parent에서 제외한다. `same-name-receivers`는 receiver type이 다른 exact method ID 2개를 기대한다. `decision-matrix`는 `if`, loop, switch case, select communication clause, `&&`, `||`의 syntax별 expected 증가값과 callable별 total CC를 고정하고 nested literal decision의 parent 중복 0을 검증한다. Upstream text output은 사용하지 않고 pinned corpus의 기대 CC만 교차 검사한다.

- [ ] **단계 4: Go CRAP 통과 확인**

실행: `scripts/go.sh --offline run ./tools/testinventory --manifest test-inventory/crap.json`

실행: `scripts/go.sh --offline test ./internal/crap ./internal/rendering ./internal/cli -count=1`

기대: `crap.json`의 정적 package·Test·Example·Fuzz inventory와 실제 started·terminal event가 exact join하고 expected·실행 test가 0개가 아님. 기약분수·canonical decimal·exact boundary, function literal, 모든 Go CC syntax의 exact count와 nested parent 중복 0, coverage unknown, near-equal·한글·astral stable-sort vector 통과

- [ ] **단계 5: commit**

```bash
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py prepare-and-stage --repository . --task T14 --phase crap --base-head <T14_BASE_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --output-root <workspace>/build/commit-inventory -- internal/crap internal/rendering internal/cli internal/orchestrator test-inventory/crap.json testdata/crap docs/architecture.md docs/index.md docs/log.md
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py commit-prepared --repository . --task T14 --phase crap --prepared-receipt <PREPARED_RECEIPT> --prepared-receipt-sha256 <PREPARED_RECEIPT_SHA256> --base-head <T14_BASE_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --expected-message "feat: implement native Go CRAP gate (요구사항-10,11,14..17,34,39)"
```

### T15: SENTINEL_GO typed runner admission·snapshot·mutate4go bridge·gate

**충족 요구사항:** 요구사항-22..요구사항-32, 요구사항-39, 요구사항-43

**파일:**

- 생성: `internal/runner/{protocol.go,ast_wrapper.go,testmain_wrapper.go,event_pipe.go}`
- 생성: `internal/workspace/{safe_path.go,snapshot.go,process_tree.go,sandbox_lease.go,guardian.go,start_gate.go}`
- 생성: `internal/mutation/{protocol.go,mutate4go.go,normalizer.go,gate.go}`, `backend.lock.json`
- 검증: T13의 `go.mod`, `go.sum`에 이미 고정한 `golang.org/x/sys v0.36.0` exact requirement·checksum
- 생성: `third_party/mutate4go/**`, `third_party/mutate4go/cmd/sentinel-mutate4go-bridge/**`, `upstream/patches/{0001-machine-report-full-mode.patch,0002-typed-runner-argv-timeout.patch,0003-isolated-snapshot-coverage.patch}`
- 생성: `scripts/verify-upstream-patches.sh`, `internal/mutation/upstream_patch_verifier_test.go`, `testdata/upstream-patches/**`
- 생성: `test-inventory/runner-mutation.json`
- 생성: `testdata/commit/t15-files.json`
- 테스트: package `_test.go`, `testdata/runner/{fail,failnow,panic,exit,subtest,child-goroutine,fuzz,example,testmain}/`, `testdata/mutation/{all-killed,survivor,timeout,coverage-failure,all-states,multi-file}/`
- 수정: `internal/cli/cli.go`, `internal/orchestrator/orchestrator.go`
- 생성: `docs/backend.md`, `docs/operations.md`, `docs/lineage.md`
- 수정: `upstream/UPSTREAM.md`, `docs/index.md`, `docs/log.md`

**받는 것:** T13 scope, T14 coverage matcher, T04 runner·mutation vector, pristine mutate4go commit

**주는 것:** admission된 Go typed runner, immutable snapshot, complete candidate/outcome bridge와 killed-only result

- [ ] **단계 1: runner admission 반례를 먼저 작성**

```go
func TestExampleFailureNeedsCompleteTypedCombination(t *testing.T) {
	events := []Event{PrivateNormalReturn("ExampleBad"), OfficialFail("ExampleBad")}
	got := Classify(events)
	if got.Status == Killed { t.Fatal("missing normal m.Run terminal was accepted") }
}

func TestFailNowIsAssertionAndPanicIsRuntime(t *testing.T) {
	assertStatus(t, RunFixture("failnow"), AssertionFailure)
	assertStatus(t, RunFixture("panic"), RuntimeError)
}
```

Conformance table은 `t.Fail`, `FailNow`·Goexit, subtest, child goroutine, `testing.F`, fuzz seed, Example mismatch, `TestMain`, `os.Exit`, missing terminal을 각각 기대 상태로 고정한다.

단계 1..4A에는 runner test, `testdata/runner/**`와 사람이 관리하는 `testdata/commit/t15-files.json`을 만든다. 이 JSON은 `runner-admission`과 `mutation-admission` selector별 sorted concrete path array를 미리 고정하고 runner array는 자기 fixture path를 포함한다. Mutation array는 mutation command wiring을 바꾸는 `internal/cli/cli.go`와 `internal/orchestrator/orchestrator.go`를 모두 포함한다. Test가 각 selector와 task 책임·actual changed set을 exact 대조한다. Backend가 필요한 `testdata/mutation/**`와 mutation test는 단계 4A의 clean-tree checkpoint 뒤 단계 4B에서 먼저 실패하도록 작성한다. 그때 만드는 `multi-file`은 production 첫 file과 마지막 file에 각각 mutant 1개를 만들고 per-file candidate count·digest와 합산 plan 2개를 고정한다. Production inventory file 하나라도 bridge 호출·candidate plan에서 빠지거나 file별 digest join이 다르면 mutant 실행 0회에서 backendError다.

단계 4B에서 만드는 workspace test는 trusted root FD 아래 absolute·`..`·separator component, symlink·magic-link·hardlink, validation 직후 parent·leaf swap과 unsupported kernel·filesystem을 주입한다. Opened FD의 `Fstat` identity와 실제 rename·unlink target이 다르거나 검사 뒤 문자열 path를 다시 열면 실패한다.

`SandboxLease`는 T03 `sandbox-lease-v1`, `sandbox-control-layout-v1`, guardian과 exact age policy를 canonical JSON으로 구현한다. Approved root에서 lease·fixed marker filename·relative leaf·owner·mode·device·inode를 descriptor로 검증하고 gate 뒤에만 backend를 실행한다. Lease age는 T13 Clock의 `LeaseBoottimeNanos`와 `SampleUtcWithSyncProof`만 소비한다. Catch 가능한 terminal은 guardian의 authenticated tree-drained marker 뒤 정리한다. 다음 run은 valid marker와 age-expired가 모두 맞을 때만 `Renameat2(RENAME_NOREPLACE)` quarantine·directory sync 뒤 descriptor-relative delete한다. Marker missing·guardian crash·foreign/duplicate leaf·HMAC/path identity 불명은 cross-boot에서도 영구 no-touch다. Explicit raw output은 별도다.

Go package의 first-party guardian은 T03 subreaper·pinned `x/sys/unix` pidfd·HMAC tree-drained 계약을 전부 구현한다. Controller EOF와 정상 drain에서 `setsid`·double-fork descendant가 adopted direct child가 될 때마다 pidfd TERM·KILL과 `waitid(P_PIDFD)`를 반복하고 ECHILD 뒤에만 marker를 durable commit한다. Numeric `kill`·`killpg`·`tgkill`은 0이다. Guardian SIGKILL·marker/HMAC 불명은 cross-boot와 age-expired에서도 영구 unknown·no-delete다.

Mutation 결과의 killed/in-scope fraction도 T14 reduce와 `canonical-decimal-v1` 하나로만 render한다. Gate는 decimal percentage가 아니라 exact count equality를 사용하고 0 denominator는 percentage를 만들지 않고 quality failure다.

Acceptance는 distinct nonce의 같은 selection baseline을 두 번 `-count=1`로 실행하고 failure·ID mismatch에서 coverage·candidate·mutant 호출 0을 확인한다. Prepare는 snapshot 내부 argv·minimal environment만 사용하고 generated-output root의 protected overlap·symlink·hardlink·path swap을 거부한다.

CLI test는 T13의 `backendPending`을 admission 뒤 성공으로 바꾸고 mutate4go archive·patch·companion·backend lock identity 중 하나를 변조하면 dependencyError이며 test·coverage·mutation·state write는 0회임을 검증한다.

- [ ] **단계 2: runner spike 실패 확인**

실행: `scripts/go.sh --offline test ./internal/runner -run 'Test(FailNow|Example|Fuzz|TestMain|Child)' -count=1`

기대: runner package 부재로 실패

- [ ] **단계 3: snapshot-only AST wrapper와 event pipe 구현**

```go
type TestEvent struct {
	Nonce  string `json:"nonce"`
	TestID string `json:"testId"`
	Phase  string `json:"phase"`
	Kind   string `json:"kind"`
}

func IsExampleAssertion(events []TestEvent, testID string) bool {
	return has(events, testID, "privateNormalReturn") && has(events, testID, "officialFail") &&
		has(events, "TestMain", "mRunReturned") && !hasAny(events, "panic", "processAbort", "terminalMissing")
}
```

Wrapper는 original test source가 아니라 disposable snapshot의 AST만 변환한다. 수집된 모든 `Test*`, runnable `Example*`, `Fuzz*` seed와 `TestMain`이 start·terminal one-to-one을 만족해야 한다. 지원하지 않는 signature나 mode는 mutant 0회에서 dependencyError다.

- [ ] **단계 4: Go runner admission gate 통과 확인**

실행: `scripts/go.sh --offline run ./tools/testinventory --manifest test-inventory/runner-mutation.json --phase runner`

실행: `scripts/go.sh --offline test ./internal/runner -count=1`

기대: runner phase의 정적 package·Test·Example·Fuzz inventory와 실제 started·terminal event가 exact join하고 expected·실행 runner test가 0개가 아님. 모든 typed 반례 통과, `(cached)` event 0, human stdout parsing 0

이 단계가 실패하면 T15의 backend vendoring을 시작하지 않고 `SENTINEL_GO` release를 차단한다.

- [ ] **단계 4A: runner admission을 독립 commit으로 고정**

Runner spike와 fixture의 `runner-admission` selector만 `materialize-exact`로 `build/commit-inventory/T15/SENTINEL_GO/runner-admission/stage.paths`에 만든 뒤 stage한다. Cached NUL set이 이 allowlist 밖의 CRAP·backend bridge file을 보이면 중단한다.

```bash
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py materialize-exact --repository . --task T15 --phase runner-admission --base-head <T14_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --source testdata/commit/t15-files.json --selector runner-admission --output <workspace>/build/commit-inventory/T15/SENTINEL_GO/runner-admission/stage.paths
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py stage-exact --repository . --task T15 --phase runner-admission --base-head <T14_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --manifest <workspace>/build/commit-inventory/T15/SENTINEL_GO/runner-admission/stage.paths
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py commit-prepared --repository . --task T15 --phase runner-admission --prepared-receipt <PREPARED_RECEIPT> --prepared-receipt-sha256 <PREPARED_RECEIPT_SHA256> --base-head <T14_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --expected-message "feat: admit typed Go test runner (요구사항-22..32,39,43)"
test -z "$(/usr/bin/git status --short)"
```

- [ ] **단계 4B: T14 뒤 backend·workspace·patch verifier RED 확인**

T14 commit과 clean-tree를 확인한 뒤 `internal/workspace/*_test.go`, `internal/mutation/*_test.go`, `internal/cli/*mutation*_test.go`, `internal/mutation/upstream_patch_verifier_test.go`, `testdata/mutation/**`와 작은 synthetic `testdata/upstream-patches/**`를 처음 만든다. `multi-file` fixture는 production inventory의 첫 file과 마지막 file에 mutant를 하나씩 기대하고 coverage identity·candidate plan·raw outcome exact join을 고정한다. Patch verifier test는 아직 `scripts/verify-upstream-patches.sh`가 없어서 먼저 RED여야 하며, 단순 파일 부재 확인 뒤에도 다음 의미 반례가 차례로 RED가 되게 작성한다: pristine archive SHA-256 오류, patch 누락·추가·순서 변경·적용 실패, operator file 변경, 적용 결과의 path·type·mode·bytes 누락·추가·불일치. 각 반례에서는 backend와 production test process 실행이 0이어야 한다.

실행: `scripts/go.sh --offline run ./tools/testinventory --manifest test-inventory/runner-mutation.json --phase mutation`

실행: `scripts/go.sh --offline test ./internal/workspace ./internal/mutation ./internal/cli -count=1`

기대: mutation phase expected test ID는 존재하지만 workspace·backend bridge와 patch verifier가 아직 없어 올바른 이유로 실패함. External backend process와 source write는 0

- [ ] **단계 5: pristine backend vendoring과 최소 bridge patch**

실행 위치: `upstream/unclebob/mutate4go`

```bash
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/vendor_upstream.py --source . --expected-commit 9016c7adafc1c7e282b5e27768e732e477713af8 --whole-tree-baseline <workspace>/SENTINEL_SPEC/baselines/upstream-tree.json --expected-archive-sha256 4fae40e1568649edbeadc7f3a0a164b8a2d7ae0d464fb2d4d7ed006afee59215 --destination <workspace>/SENTINEL_GO/third_party/mutate4go
```

실행 위치를 `SENTINEL_GO`로 되돌린 뒤 아래 구현·검증·Git 명령을 수행한다.

Tool은 T01 whole-tree 불변을 먼저 검사하고 validated temporary tar file로 `git archive --format=tar HEAD`를 만든다. Archive digest와 member path·type·mode를 검사하고 path traversal·link escape 없이 non-existing destination에 추출한 뒤 canonical extracted manifest를 다시 확인하고 원자 게시한다. 재실행의 complete exact destination은 write 0으로 채택하고 partial·extra·missing·mismatch destination은 overwrite·delete·repair 없이 중단한다. Crash test는 rename 전·직후·receipt 직전 경계를 포함한다. 이후 새 저장소 안에서만 수정한다. Patch는 candidate plan, raw outcome enum, public machine-report command `cmd/sentinel-mutate4go-bridge`, argv process, typed runner event와 no-source-write full mode만 추가한다. Operator AST 코드는 byte digest로 고정하고 patch가 건드리면 test가 실패한다. Root adapter는 nested module의 `internal` package를 import하지 않고 고정 companion executable protocol만 사용한다.

먼저 synthetic fixture만 사용하는 `upstream_patch_verifier_test.go`를 다시 실행하면서 `scripts/verify-upstream-patches.sh`를 최소 구현해 GREEN으로 만든다. Verifier는 lock에 고정된 pristine archive SHA-256과 ordered exact patch filename·SHA-256을 확인하고, owner-only temporary directory에 archive를 안전 추출한 뒤 순서대로 patch를 적용한다. 적용 전·후 operator path set과 각 bytes digest가 같아야 한다. 마지막에는 재구성한 tree와 committed `third_party/mutate4go` 전체를 path·type·POSIX mode·file bytes 또는 symlink target 단위로 exact 비교한다. Missing·extra·reordered patch, wrong archive, apply failure, operator 변경과 resulting tree 불일치는 backend 실행 0에서 nonzero다. 이 synthetic oracle이 GREEN이 된 뒤에만 실제 pristine archive·세 patch·vendored tree를 같은 verifier로 검사한다.

T13에서 exact lock·checksum·offline cache 검증을 끝낸 `golang.org/x/sys v0.36.0`만 이 단계에서 재사용한다. `safe_path.go`는 trusted root directory FD에서 `unix.Openat2`의 beneath·no-symlink·no-magic-link, 의미가 동일한 component-by-component `unix.Openat(O_NOFOLLOW)`, opened object `unix.Fstat`, `unix.Renameat2(RENAME_NOREPLACE)`와 `unix.Unlinkat`만 사용한다. Kernel·filesystem이 의미를 증명하지 못하면 fallback write·delete 없이 dependencyError다. Snapshot·generated output·backend workspace는 이 FD-bound boundary만 사용하고 validation 뒤 `os.Open`, `os.Rename`, `os.Remove`로 문자열 path를 다시 열지 않는다.

Admission test는 mock adapter가 아니라 실제 `sentinel-mutate4go-bridge` executable을 all-killed, survivor, timeout, coverage-failure tiny project 각각에 argv로 실행한다. Executable이 먼저 내보낸 candidate ID·operator·source inventory와 raw outcome를 고정 raw fixture에 대조하고 root normalizer가 만든 canonical record를 expected canonical fixture와 byte 단위로 대조한다. Process exit 0이나 summary footer만 신뢰하거나 actual executable을 호출하지 않은 mock-only test는 admission 통과로 인정하지 않는다.

```go
type RawOutcome struct {
	CandidateID string
	Status      string
	DurationNS  int64
}

func StrictPass(plan CandidatePlan, records []MutantRecord) bool {
	return len(plan.Candidates) > 0 && exactIDSet(plan, records) && allKilled(records)
}
```

- [ ] **단계 6: bridge·snapshot·gate 통과 확인**

실행: `/usr/bin/bash scripts/verify-upstream-patches.sh mutate4go`

실행: `scripts/go.sh --offline run ./tools/testinventory --manifest test-inventory/runner-mutation.json`

실행: `scripts/go.sh --offline test ./internal/workspace ./internal/mutation ./internal/cli -count=1`

실행: `scripts/go.sh --offline -C third_party/mutate4go test ./... -count=1`

기대: full manifest의 runner·mutation 정적 inventory와 실제 started·terminal event가 exact join하고 각 필수 phase의 expected·실행 test가 0개가 아님. Root adapter와 nested backend module이 각각 통과하고 adapter가 고정 machine-report executable을 argv로 호출함. 네 tiny project의 actual executable candidate·operator·raw outcome와 canonical normalized record가 고정 fixture와 정확히 일치한다. Doctor는 admitted backend만 읽어 성공하고 변조 시 side effect 없이 실패한다. Timeout·panic·compile·pending·ignored·unknown은 killed가 되지 않고 source race와 process leak은 pass 취소, candidate/result exact set 일치. SIGKILL orphan은 valid HMAC tree-drained marker+age-expired일 때만 quarantine·delete하고 marker missing·guardian crash는 영구 no-touch다. PID reuse process에는 signal 0이며 공용 evidence·finding·history·export·default artifact·diagnostic raw canary 0, catchable 또는 valid-marker cleanup 뒤 sandbox raw 0이다. `multi-file`의 첫·마지막 file candidate가 모두 합산되고 하나를 생략하면 backendError

- [ ] **단계 7: commit**

```bash
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py materialize-exact --repository . --task T15 --phase mutation-admission --base-head <T15_RUNNER_ADMISSION_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --source testdata/commit/t15-files.json --selector mutation-admission --output <workspace>/build/commit-inventory/T15/SENTINEL_GO/mutation-admission/stage.paths
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py stage-exact --repository . --task T15 --phase mutation-admission --base-head <T15_RUNNER_ADMISSION_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --manifest <workspace>/build/commit-inventory/T15/SENTINEL_GO/mutation-admission/stage.paths
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py commit-prepared --repository . --task T15 --phase mutation-admission --prepared-receipt <PREPARED_RECEIPT> --prepared-receipt-sha256 <PREPARED_RECEIPT_SHA256> --base-head <T15_RUNNER_ADMISSION_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --expected-message "feat: add typed Go mutation bridge (요구사항-22..32,39,43)"
```

### T16: SENTINEL_GO evidence·history·privacy와 전체 command

**충족 요구사항:** 요구사항-06..요구사항-08, 요구사항-28, 요구사항-29, 요구사항-32, 요구사항-39, 요구사항-42, 요구사항-45..요구사항-54

**파일:**

- 생성: `internal/evidence/{models.go,privacy.go,lock.go,commit_sequence.go,store.go}`
- 생성: `internal/history/{service.go,retention.go,export.go,resolver.go}`
- 생성: `test-inventory/evidence-history.json`
- 생성: `scripts/run-e2e-fixture.sh`, `testdata/projects/{go-pass,go-history}/**`
- 테스트: package `_test.go`, `internal/evidence/commit_sequence_test.go`, `internal/evidence/project_key_rotation_test.go`, `testdata/history/**`, `testdata/privacy/**`
- 생성: `docs/privacy.md`
- 수정: `internal/cli/cli.go`, `internal/orchestrator/orchestrator.go`, `README.md`, `docs/index.md`, `docs/operations.md`, `docs/log.md`

**받는 것:** T14 CRAP, T15 mutation과 `SandboxLease`, T03 evidence·sandbox-lease golden

**주는 것:** 완성된 `sentinel-go` 5개 command와 Go native POSIX state store

이 task의 completed와 incomplete prune은 T03 `retention-marker-first-v1`을 그대로 구현한다. 두 kind 모두 marker directory sync 전 selected bundle delete는 0이다. Completed는 각 marker의 `(commitSequence <= sequenceHighWaterAtCommit && committedAtUtc < cutoffUtc)` pair union만 적용하고 marker 뒤 더 큰 sequence run을 소급 숨기지 않는다. Incomplete는 marker의 sorted immutable selection subset만 resume하며 신규 eligible run과 선택 뒤 completed가 된 run을 삭제하지 않는다. 나머지도 stored started·lease·tree-drained digest와 HMAC join을 다시 증명한 경우만 descriptor-relative delete한다.

- [ ] **단계 1: cross-process lock과 crash 실패 test 작성**

```go
func TestEvidenceRenameWithoutDirectorySyncIsNotCompleted(t *testing.T) {
	state := RunCrashFixture(t, "after-rename-before-dir-sync")
	if state.Certified { t.Fatal("unsynced evidence was certified") }
}

func TestCacheReplayDoesNotCreateFindingEvent(t *testing.T) {
	view := FoldFixture(t, "fresh-then-cache")
	if view.ObservationCount != 1 || view.Repeated { t.Fatalf("view=%+v", view) }
}
```

- [ ] **단계 2: 실패 확인**

실행: `scripts/go.sh --offline test ./internal/evidence ./internal/history ./internal/cli -count=1`

기대: evidence와 history package 부재로 실패

- [ ] **단계 3: fcntl·atomic commit·history 구현**

```go
func (s *Store) Commit(ctx context.Context, draft RunDraft) (CompletedRun, error) {
	return s.lock.WithExclusive(ctx, func() (CompletedRun, error) {
		prior := s.ReadCompleted()
		sequence, err := s.AllocateAndSyncNextSequence(prior)
		if err != nil { return CompletedRun{}, evidenceError(err) }
		events := DeriveEvents(prior, draft, sequence)
		if err := s.WriteAndSyncEvents(events); err != nil { return CompletedRun{}, evidenceError(err) }
		return s.CommitEvidence(draft, events, sequence, s.clock.UtcNow())
	})
}
```

`Store` constructor는 T13 `Clock`을 required dependency로 받고 evidence UTC는 `s.clock.UtcNow()`, timeout·lock deadline은 같은 facade의 process-monotonic method만 사용한다. T16 static negative test는 production evidence·history·lock package의 direct `time.Now`, `time.Since`, `time.Until`과 direct clock syscall을 0으로 고정한다. T15에서 exact lock하고 offline 검증한 `golang.org/x/sys v0.36.0`만 사용한다. `unix.FcntlFlock`은 byte 0 length 1을 사용한다. State create·read·commit, event manifest, export, raw output과 prune traversal·delete는 T15의 `safe_path.go` FD boundary만 사용하고 validation 뒤 `os.Open`, `os.Rename`, `os.Remove`로 문자열 path를 다시 열지 않는다. Persistent evidence는 실제 resolved config 우선순위·digest, scope·target·mutation domain, mutate4go commit·archive·patch identity, operator·exclusion inventory와 bridge·runner version을 privacy-safe field로 기록한다. History, retention, local resolver, privacy allowlist는 SPEC golden byte와 일치해야 한다.

T13 `ProjectKeyProvider` output은 T03 규칙대로 첫 quality run의 project state initialize 또는 exact next-epoch atomic rotation에만 적용한다. Same key·epoch 재실행은 write 0이고 invalid epoch·key 조합은 started·child 호출 0이다. Temporary create·file sync·rename·directory sync fault와 retry에서 old 또는 new complete `project.json`만 허용한다. Help·doctor·history는 envelope flag를 거부하고 state create·rotate 0이다.

`CommitSequenceStore`는 T03 schema·derived HMAC·retention high-water floor를 그대로 구현한다. Exclusive lock 안에서 next sequence file을 durable commit한 뒤에만 같은 sequence의 event와 evidence를 쓰며 allocation crash gap을 재사용하지 않는다. History는 UTC가 아니라 sequence로 fold하고 invalid·duplicate·rollback에서 exit 7, 추가 write·delete 0이다.

`history prune --incomplete`는 T15의 동일 `SandboxLease` parser와 HMAC tree-drained marker oracle을 호출해 runId·projectToken·lease generation·guardian identity를 join한다. Marker missing·HMAC mismatch·guardian crash·corrupt lease와 외부 guardian start 전임을 증명하지 못한 missing lease는 incomplete run을 영구 보존한다. Valid marker, `startedAtUtc < cutoffUtc`, completed evidence 부재가 모두 맞을 때만 whole incomplete bundle을 descriptor-relative로 삭제하고 cutoff equality를 보존한다. Sandbox quarantine은 별도 `mayQuarantineSandbox=validMarker+ageExpired`만 사용한다.

`run-e2e-fixture.sh`는 고정 fixture 이름 allowlist만 받고 validated `mktemp -d`의 owner-only project copy에서 actual CLI를 실행한 뒤 EXIT·INT·TERM cleanup과 원 checked-in fixture whole manifest 불변을 확인한다. Checked-in project에서 `.sentinel`을 직접 만들지 않는다.

- [ ] **단계 4: Go end-to-end 통과 확인**

실행: `scripts/go.sh --offline run ./tools/testinventory --manifest test-inventory/evidence-history.json`

실행: `scripts/go.sh --offline mod verify`

실행: `scripts/go.sh --offline test ./... -count=1`

실행: `/usr/bin/bash scripts/run-e2e-fixture.sh go-pass check --format json`

실행: `/usr/bin/bash scripts/run-e2e-fixture.sh go-history history --repeated --format json`

기대: 전체 정적 package·Test·Example·Fuzz inventory와 실제 started·terminal event가 exact join하고 unit·integration·acceptance의 expected·실행 test가 각각 1개 이상임. Cached 0, canary 0건, corrupt marker exit 7, local resolver network·write 0, stable stdin key의 같은 epoch repeated와 exact next-epoch 분리·atomic rotation, child key byte 0, state·export·prune path-swap에서도 validated FD 밖 read·write·rename·delete 0. Incomplete run은 marker missing·guardian crash·cutoff equality를 보존하고 valid tree-drained marker+started-before-cutoff+completed 없음만 whole run 삭제하며 sandbox는 valid marker+cleanup-age-expired만 quarantine

- [ ] **단계 5: commit**

```bash
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py prepare-and-stage --repository . --task T16 --phase evidence --base-head <T16_BASE_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --output-root <workspace>/build/commit-inventory -- internal scripts/run-e2e-fixture.sh test-inventory/evidence-history.json testdata README.md docs
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py commit-prepared --repository . --task T16 --phase evidence --prepared-receipt <PREPARED_RECEIPT> --prepared-receipt-sha256 <PREPARED_RECEIPT_SHA256> --base-head <T16_BASE_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --expected-message "feat: complete Go evidence and history commands (요구사항-06..08,28,29,42,45..54)"
```

### T17: SENTINEL_JAVA 설치·SPEC·config·scope·help·doctor

**충족 요구사항:** 요구사항-05, 요구사항-09, 요구사항-18, 요구사항-21, 요구사항-32, 요구사항-40, 요구사항-42, 요구사항-55

**파일:**

- 생성: `SENTINEL_JAVA/pom.xml`, `dependency-lock.json`, `scripts/verify-dependencies.sh`, `spec-lock.json`, `vendor/sentinel-spec/**`
- 검증: T01의 `toolchain.lock.json`, `scripts/{bootstrap-java,java,mvn}.sh`
- 생성: `src/main/java/io/github/hwainhwang/sentinel/{cli/SentinelCli.java,orchestrator/SentinelOrchestrator.java}`
- 생성: `src/main/java/io/github/hwainhwang/sentinel/{contracts/{ContractLoader,Models}.java,config/{ConfigModels,ConfigResolver,ScopeClassifier}.java}`
- 생성: `src/main/java/io/github/hwainhwang/sentinel/platform/{Entropy,FileOps,Clock,ProcessFacade,ProjectKeyProvider,HmacSha256,JnaNativeLoader}.java`
- 테스트: `tests/bootstrap/test_dependency_verifier.py`, `src/test/java/io/github/hwainhwang/sentinel/contracts/ContractLoaderTest.java`, `config/{ConfigResolverTest,ScopeClassifierTest}.java`, `platform/{PlatformFacadeTest,ProjectKeyProviderTest,HmacSha256Test,JnaNativeLoaderTest}.java`, `acceptance/HelpDoctorTest.java`, `src/test/resources/test-inventory/foundation.json`, `src/test/resources/fixtures/{polyglot,unclassified}/`
- 생성: `docs/contracts.md`
- 수정: `README.md`, `docs/index.md`, `docs/log.md`

**받는 것:** T04 bundle bytes, commit과 manifest digest, 고정 Java release profile

**주는 것:** Java `VerifiedContract`, `ResolvedModule`, `ClassifiedScope`, side-effect 없는 help·doctor와 재현 가능한 standalone build

`pom.xml`의 project version은 Java runtime version의 단일 원본이며 exact `0.1.0-rc.1`로 시작한다. CLI·doctor·result의 `sentinel.version`, clean-installed package metadata와 JAR `Implementation-Version`이 이 값과 같은지 test한다.

`platform`의 여섯 production dependency interface는 entropy, file·directory sync·rename·descriptor operation, evidence·retention용 `utcNow`, timeout·lock deadline용 process `monotonicNow`, lease용 `leaseBoottimeNanos`와 UTC instant·동기화 proof를 한 결과로 돌려주는 `sampleUtcWithSyncProof`, child process spawn·signal·reap, project-key 입력, HMAC-SHA-256 계산을 감싸고 orchestrator constructor로 받는다. Java Clock의 lease method는 lock-verified JNA libc `clock_gettime(CLOCK_BOOTTIME)`와 `adjtimex` bracket만 쓰고 unsigned decimal string 경계를 유지한다. UTC wall clock은 monotonic deadline에 사용할 수 없고 process monotonic 값은 evidence timestamp나 lease에 사용할 수 없다. Default CLI는 OS implementation만 조립하며 option·config·environment로 test implementation을 선택할 수 없다. Test implementation은 `src/test/**`에만 두고 T25가 release dependency graph와 JAR에서 0개임을 확인한다.

`ProjectKeyProvider`는 T02의 `--project-key-stdin` canonical envelope를 bounded read·validate·decode하고 opaque 32-byte key와 epoch를 orchestrator parent에만 준 뒤 stdin을 닫는다. Raw key를 string representation·exception·argv·environment로 만들지 않으며 child process facade는 provider 사용 여부와 무관하게 stdin을 `/dev/null`로 고정한다. Option이 없으면 quality command만 OS CSPRNG local-key 경로를 사용한다. Help·doctor·history는 provider를 호출하지 않는다.

`HmacSha256` production provider는 JDK `Mac`의 `HmacSHA256`만 사용하며 fingerprint, projectToken과 bootToken의 모든 MAC을 계산한다. Production direct-call 우회는 static inventory 0이고 provider failure는 외부 child 호출·cleanup·prune delete 0의 exit 7 `evidenceError`다.

Java foundation Clock test는 production Clock 아래 package-private JNA syscall interface만 주입해 T03의 두 `CLOCK_MONOTONIC_RAW`, 두 fresh zero-filled timex·modes 0 adjtimex와 중간 `CLOCK_REALTIME`의 exact 다섯-call trace를 검사한다. Extra·separate UTC read, memory reuse·nonzero field, `STA_NANO` 정규화, maxerror·span·uncertainty 산식, 각 error·status와 forward·backward step vector를 모두 거부하거나 unknown으로 만든다. UTC instant+uncertainty+proof는 한 immutable record다. Production direct JNA call은 default adapter 밖 static inventory 0이다.

`JnaNativeLoader`는 JNA class를 처음 참조하기 전에 dependency lock의 packaged Linux x86_64 `jnidispatch` resource byte를 owner-only validated temporary directory에 exclusive-create·file-sync·directory-sync하고 digest를 다시 확인한다. Launcher는 ambient `jna.boot.library.path`, `jna.library.path`, `JNA_TMPDIR`와 system lookup을 전달하지 않고 validated extraction directory만 `jna.boot.library.path`로 주며 `jna.nosys=true`, `jna.nounpack=true`를 고정한다. JNA 초기화 뒤에도 extracted file device·inode·mode·digest를 다시 확인하고 cleanup한다. System `jnidispatch`, world-writable extraction, digest mismatch와 preloaded JNA negative fixture는 Clock syscall 0에서 dependencyError다. T19 `LinuxFs`도 이 loader instance만 재사용한다.

- [ ] **단계 0A: dependency verifier 자체의 실패 test를 먼저 고정**

T01의 pinned JDK·Maven bootstrap으로 `pom.xml`, `dependency-lock.json`, `src/test/resources/test-inventory/foundation.json`과 system-Python bootstrap oracle `tests/bootstrap/test_dependency_verifier.py`를 먼저 만들되 `scripts/verify-dependencies.sh`와 `src/main` production class는 아직 만들지 않는다. `/usr/bin/python3 -I tests/bootstrap/test_dependency_verifier.py`를 실행해 missing verifier 때문에 RED인지 확인하고 process·network spawn 0을 기록한다. 이어 test-owned fake local repository와 fake transport를 사용해 missing·extra artifact, wrong size·digest·coordinate·repository, hostile user/global settings·proxy, unlisted plugin과 populate 중 unexpected request가 각각 RED가 되며 실제 Maven·network 호출은 0인 반례를 고정한다.

- [ ] **단계 0B: 최소 verifier를 구현하고 isolated repository를 채움**

`scripts/verify-dependencies.sh`만 최소 구현해 `/usr/bin/python3 -I tests/bootstrap/test_dependency_verifier.py`를 GREEN으로 만든 뒤에야 `/usr/bin/bash scripts/bootstrap-java.sh && /usr/bin/bash scripts/verify-dependencies.sh --populate && /usr/bin/bash scripts/verify-dependencies.sh && scripts/mvn.sh -o -B -ntp -DskipTests package`를 실행한다. `--populate`만 network를 허용해 owner-only synthetic home, empty user settings, digest-verified global settings와 exact `.toolchain/m2` repository를 lock의 exact set으로 채우며, 뒤 두 command는 network 0에서 성공해야 한다. 이어 `SENTINEL_SPEC`에서 `scripts/uv.sh run python tools/vendor_spec.py --archive ../build/t04/SENTINEL_SPEC-0.1.0-rc.1.tar --receipt ../build/t04/SENTINEL_SPEC-0.1.0-rc.1.tar.sha256.json --source-tag spec-v0.1.0-rc.1 --destination ../SENTINEL_JAVA/vendor/sentinel-spec --lock-output ../SENTINEL_JAVA/spec-lock.json`을 실행하고 `SENTINEL_JAVA`로 돌아온다. 단계 1 test를 작성한 뒤 단계 2가 missing production class 때문에 RED여야 한다. Dependency·vendor failure나 test 0개는 RED 근거가 아니다.

- [ ] **단계 1: standalone·SPEC·scope 실패 test 작성**

```java
@Test
void helpDoesNotCreateProjectState() {
    Path project = temporaryProject();
    ProcessResult result = runCli(project, "--help");
    assertEquals(0, result.exitCode());
    assertFalse(Files.exists(project.resolve(".sentinel")));
}

@Test
void javaModuleDoesNotClaimTypescriptSource() {
    ClassifiedScope scope = resolveFixture("polyglot", "service-java");
    assertEquals(Set.of("service/src/Main.java"), scope.production());
}
```

- [ ] **단계 2: 실패 확인**

실행 위치: `SENTINEL_JAVA`

실행: `/usr/bin/bash scripts/verify-dependencies.sh && scripts/mvn.sh -o -B -ntp -Dtest=io.github.hwainhwang.sentinel.contracts.ContractLoaderTest,io.github.hwainhwang.sentinel.config.ConfigResolverTest,io.github.hwainhwang.sentinel.config.ScopeClassifierTest,io.github.hwainhwang.sentinel.platform.PlatformFacadeTest,io.github.hwainhwang.sentinel.platform.ProjectKeyProviderTest,io.github.hwainhwang.sentinel.platform.HmacSha256Test,io.github.hwainhwang.sentinel.platform.JnaNativeLoaderTest -Dit.test=io.github.hwainhwang.sentinel.acceptance.HelpDoctorTest verify`

기대: Java production package 부재로 실패

- [ ] **단계 3: standalone Maven과 최소 foundation 구현**

`scripts/mvn.sh`는 T01의 Maven 3.9.16 distribution과 SHA-256, empty user settings, pinned global settings, synthetic user home, `.toolchain/m2`, project `.mvn` 부재와 sealed Java·Maven environment를 매 실행 전에 검증한다. `pom.xml`은 Temurin JDK 17.0.20.1+1 profile, JUnit 5.10.2, Surefire·Failsafe 3.2.5, Jackson BOM·databind 2.22.2, JNA 5.17.0과 Maven Shade Plugin 3.6.2를 exact version으로 잠그고 parent POM에 의존하지 않는다. `dependency-lock.json`은 dependency·transitive JAR·Maven plugin의 coordinate, source repository, size와 SHA-256을 모두 고정하며 JNA JAR와 packaged Linux x86_64 native dispatch artifact도 exact set으로 포함한다. Verifier는 isolated local repository를 채울 때와 offline build 전에 exact set·digest를 대조하고 extra·missing artifact를 거부한다. Foundation test는 JNA `CLOCK_BOOTTIME`·`adjtimex` ABI probe도 실행한다. Shade는 `SentinelCli` Main-Class, 고정 output timestamp와 stable file order로 `target/sentinel-java.jar`를 만든다. T25는 이 layout을 clean-install용으로 검증하고 backend companion JAR를 추가한다.

Surefire의 `failIfNoTests`·`failIfNoSpecifiedTests`와 Failsafe의 no-test failure를 켠다. Surefire include는 `contracts`, `config`, `platform`과 명시한 unit package의 `**/*Test.java`이고 integration·acceptance package를 제외한다. Failsafe는 `integration-test`와 `verify` goal에 exact binding하고 include를 `**/integration/**/*Test.java`, `**/acceptance/**/*Test.java`로 고정한다. `-Dit.test`가 없을 때도 이 include가 적용되며 unknown include·skip flag·profile override는 wrapper가 거부한다. T17 foundation inventory는 unit과 acceptance가 각각 1개 이상이고 integration은 exact 0임을 명시하며, T19가 첫 integration test를 추가한 commit부터 세 layer 모두 nonzero를 요구한다. 각 단계에서 사람이 고정한 expected test ID inventory와 실제 discovered·started·terminal ID를 exact 비교하고 누락·중복 또는 선언과 다른 count면 실패한다. CI evidence는 layer별 discovered·executed count를 남긴다. `-Dtest`와 `-Dit.test`는 package-qualified exact class allowlist로만 받고 POM include를 넓히거나 다른 layer를 선택하는 wildcard는 wrapper가 거부한다.

```java
public record ResolvedModule(
        String moduleId,
        Path root,
        String language,
        List<Path> production,
        List<String> testCommand,
        List<String> coverageCommand) {}
```

Scope는 `.java`와 module descriptor를 native 발견하고 production, verified test, generated, vendor, build-output 중 하나에 정확히 배정한다. Unknown config key, 빈 production, overlap과 언어가 다른 module 선택은 usageConfigError다. Foundation `doctor`는 pinned JDK·Maven, `dependency-lock.json`, vendored SPEC checksum, resolved config와 scope를 읽기만 한다. Admission 전에는 `backendPending`을 반환하고 release-capable 성공으로 오인하지 않으며 T19가 mutate4java archive·patch·companion·backend lock identity 검사를 추가한다. 두 단계 모두 Maven test·coverage·backend와 state write를 호출하지 않는다.

Config test는 CLI override, project config, SPEC default 순서, argv-only command, minimal child environment, environment contract digest, `localCacheDir`와 generated-output SafePath를 검증한다. Maven·JUnit ambient option과 parent environment가 sealed backend config를 바꾸지 못한다.

- [ ] **단계 4: foundation 통과 확인**

실행: `/usr/bin/bash scripts/verify-dependencies.sh && scripts/mvn.sh -o -B -ntp test && scripts/mvn.sh -o -B -ntp verify`

기대: standalone clean build, tampered SPEC exit 5, module ambiguity exit 3, help·doctor 외부 실행·write 0회, facade fault는 constructor injection으로만 도달하고 default JAR에서 test implementation 선택 경로 0개

- [ ] **단계 5: commit**

```bash
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py prepare-and-stage --repository . --task T17 --phase foundation --base-head <T17_BASE_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --output-root <workspace>/build/commit-inventory -- pom.xml dependency-lock.json scripts/verify-dependencies.sh spec-lock.json vendor src tests README.md docs
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py commit-prepared --repository . --task T17 --phase foundation --prepared-receipt <PREPARED_RECEIPT> --prepared-receipt-sha256 <PREPARED_RECEIPT_SHA256> --base-head <T17_BASE_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --expected-message "feat: add Java contract and scope foundation (요구사항-05,09,18,21,32,40,42,55)"
```

### T18: SENTINEL_JAVA native CRAP

**충족 요구사항:** 요구사항-10, 요구사항-11, 요구사항-14..요구사항-17, 요구사항-34, 요구사항-40

**파일:**

- 생성: `src/main/java/io/github/hwainhwang/sentinel/crap/{Models,ExactCrap,JavaAnalyzer,JacocoCoverage,SemanticSite}.java`, `src/main/java/io/github/hwainhwang/sentinel/rendering/CanonicalDecimal.java`
- 테스트: `src/test/java/io/github/hwainhwang/sentinel/crap/{ExactCrapTest,JavaAnalyzerTest,JacocoCoverageTest,SemanticSiteTest}.java`, `src/test/java/io/github/hwainhwang/sentinel/rendering/CanonicalDecimalTest.java`, `src/test/java/io/github/hwainhwang/sentinel/acceptance/CrapCommandTest.java`
- 생성: `src/test/resources/test-inventory/crap.json`
- fixture: `src/test/resources/fixtures/crap/{constructor-lambda,overload,same-line,stale,exact-boundary,decision-matrix,stable-sort}/`
- 생성: `docs/architecture.md`
- 수정: `pom.xml`, `dependency-lock.json`, `src/main/java/io/github/hwainhwang/sentinel/{cli/SentinelCli.java,orchestrator/SentinelOrchestrator.java}`, `docs/index.md`, `docs/log.md`

**받는 것:** T17 scope, T04 exact CRAP vector, pinned `crap4java` corpus

**주는 것:** JDK compiler tree callable inventory, JaCoCo mapping, exact Java CRAP result와 `sentinel-java crap`

- [ ] **단계 0: JaCoCo dependency lock과 offline cache 확장**

실행 위치: `SENTINEL_JAVA`. JaCoCo 0.8.12와 이 task의 exact transitive artifact·Maven plugin set을 `pom.xml`과 `dependency-lock.json`에 먼저 고정한다. `/usr/bin/bash scripts/verify-dependencies.sh --populate` 한 번만 network를 허용해 owner-only repository를 채운 뒤 `/usr/bin/bash scripts/verify-dependencies.sh`와 `scripts/mvn.sh -o -B -ntp -DskipTests package`를 실행한다. Extra·missing artifact나 offline download 시도는 단계 1로 진행하지 않고 dependency failure로 끝낸다.

- [ ] **단계 1: constructor·lambda·exact fraction 실패 test 작성**

```java
@Test
void exactCrapUsesBigIntegerFraction() {
    ExactCrap value = ExactCrap.calculate(4, 3, 4);
    assertEquals(BigInteger.valueOf(17), value.numerator());
    assertEquals(BigInteger.valueOf(4), value.denominator());
    assertTrue(value.passed());
}

@Test
void constructorsAndLambdasAreIndependentCallables() {
    Set<CallableKind> kinds = analyzeFixture("constructor-lambda").kinds();
    assertTrue(kinds.containsAll(Set.of(CONSTRUCTOR, LAMBDA)));
}
```

- [ ] **단계 2: 실패 확인**

실행: `/usr/bin/bash scripts/verify-dependencies.sh && scripts/mvn.sh -o -B -ntp -Dtest=io.github.hwainhwang.sentinel.crap.ExactCrapTest,io.github.hwainhwang.sentinel.crap.JavaAnalyzerTest,io.github.hwainhwang.sentinel.crap.JacocoCoverageTest,io.github.hwainhwang.sentinel.crap.SemanticSiteTest,io.github.hwainhwang.sentinel.rendering.CanonicalDecimalTest -Dit.test=io.github.hwainhwang.sentinel.acceptance.CrapCommandTest verify`

기대: `crap` package 부재로 실패

- [ ] **단계 3: compiler tree analyzer와 exact gate 구현**

`ExactCrap`은 `BigInteger.gcd`로 numerator·denominator를 나누고 zero를 `0/1`로 canonicalize한다. `CanonicalDecimal`은 T02 `canonical-decimal-v1`을 `BigInteger.divideAndRemainder`로 구현하고 `double`, `BigDecimal` context, `DecimalFormat`과 locale formatter를 쓰지 않는다. CRAP·coverage와 뒤의 mutation kill-rate renderer가 이 class 하나를 호출한다. Test는 vendored SPEC의 reduce, `1/3`, half-even down/up, carry, zero·integer와 큰 fraction golden bytes를 직접 소비한다. Row comparator도 T02 `crap-row-order-v1`의 exact cross-multiply, UTF-8 byte path·callable ID와 raw UTF-8 byte offset을 구현하고 near-equal·한글·astral golden을 소비한다.

JDK compiler tree API는 method, constructor, lambda를 source range와 JVM descriptor로 inventory하고 `overload` fixture의 same-name method descriptor ID 2개를 기대한다. `decision-matrix`는 branch, loop, catch, ternary, switch case, `&&`, `||`의 syntax별 expected 증가값과 callable별 total CC를 고정하고 nested lambda decision의 parent 중복 0을 검증한다. JaCoCo XML의 method·instruction counter를 classfile descriptor·line table과 exact join하고 synthetic lambda 연결이 모호하거나 같은 줄 독립 실행을 증명하지 못하면 coverageUnknown으로 실패한다. Reduced `BigInteger` numerator·denominator를 8배 비교해 반올림 없이 gate한다.

- [ ] **단계 4: Java CRAP 통과 확인**

실행: `/usr/bin/bash scripts/verify-dependencies.sh && scripts/mvn.sh -o -B -ntp -Dtest=io.github.hwainhwang.sentinel.crap.ExactCrapTest,io.github.hwainhwang.sentinel.crap.JavaAnalyzerTest,io.github.hwainhwang.sentinel.crap.JacocoCoverageTest,io.github.hwainhwang.sentinel.crap.SemanticSiteTest,io.github.hwainhwang.sentinel.rendering.CanonicalDecimalTest -Dit.test=io.github.hwainhwang.sentinel.acceptance.CrapCommandTest verify`

기대: method·constructor·lambda inventory, 모든 Java CC syntax의 exact count와 nested parent 중복 0, 기약분수·canonical decimal·exact 8.0 경계, stale·missing·ambiguous coverage 실패, near-equal·한글·astral stable-sort 통과

- [ ] **단계 5: commit**

```bash
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py prepare-and-stage --repository . --task T18 --phase crap --base-head <T18_BASE_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --output-root <workspace>/build/commit-inventory -- pom.xml dependency-lock.json src/main/java/io/github/hwainhwang/sentinel/crap src/main/java/io/github/hwainhwang/sentinel/rendering src/main/java/io/github/hwainhwang/sentinel/cli/SentinelCli.java src/main/java/io/github/hwainhwang/sentinel/orchestrator/SentinelOrchestrator.java src/test/java/io/github/hwainhwang/sentinel/crap src/test/java/io/github/hwainhwang/sentinel/rendering src/test/java/io/github/hwainhwang/sentinel/acceptance/CrapCommandTest.java src/test/resources/fixtures/crap src/test/resources/test-inventory/crap.json docs/architecture.md docs/index.md docs/log.md
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py commit-prepared --repository . --task T18 --phase crap --prepared-receipt <PREPARED_RECEIPT> --prepared-receipt-sha256 <PREPARED_RECEIPT_SHA256> --base-head <T18_BASE_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --expected-message "feat: implement native Java CRAP gate (요구사항-10,11,14..17,34,40)"
```

### T19: SENTINEL_JAVA snapshot·JUnit typed runner·mutate4java bridge·gate

**충족 요구사항:** 요구사항-22..요구사항-32, 요구사항-40, 요구사항-43

**파일:**

- 생성: `src/main/java/io/github/hwainhwang/sentinel/runner/{JunitEventListener,JunitProtocolVerifier}.java`
- 생성: `src/main/java/io/github/hwainhwang/sentinel/workspace/{LinuxFs,SafePath,Snapshot,ProcessTree,SandboxLease,Guardian,StartGate}.java`
- 생성: `src/main/java/io/github/hwainhwang/sentinel/mutation/{Protocol,Mutate4JavaAdapter,MutationNormalizer,MutationGate}.java`, `backend.lock.json`
- 생성: `third_party/mutate4java/**`, `upstream/patches/{0001-standalone-build.patch,0002-machine-report-candidate-inventory.patch,0003-junit-typed-runner-process-control.patch,0004-full-no-source-write.patch}`
- 생성: `scripts/verify-upstream-patches.sh`, `src/test/resources/test-inventory/runner-mutation.json`
- 테스트: `src/test/java/io/github/hwainhwang/sentinel/mutation/UpstreamPatchVerifierTest.java`, `src/test/resources/fixtures/upstream-patches/**`
- 생성: `src/test/resources/fixtures/commit/t19-files.json`
- 생성: VCS 밖 owner-only `build/t19/pristine-parent-failure.json`
- 테스트: runner·snapshot·`SandboxLeaseTest`·bridge·gate unit·integration·acceptance test와 `src/test/resources/fixtures/mutation/{all-killed,survivor,timeout,coverage-failure,all-states,multi-file}/**`
- 수정: `src/main/java/io/github/hwainhwang/sentinel/cli/SentinelCli.java`, `src/main/java/io/github/hwainhwang/sentinel/orchestrator/SentinelOrchestrator.java`, `src/test/java/io/github/hwainhwang/sentinel/acceptance/HelpDoctorTest.java`
- 생성: `docs/backend.md`, `docs/operations.md`, `docs/lineage.md`
- 수정: `pom.xml`, `dependency-lock.json`, `scripts/verify-dependencies.sh`, `upstream/UPSTREAM.md`, `docs/index.md`, `docs/log.md`

**받는 것:** T17 scope, T18 coverage matcher, T04 runner·mutation vector, pristine mutate4java commit

**주는 것:** descriptor-relative snapshot, nonce 기반 JUnit event, complete raw outcome bridge와 killed-only result

- [ ] **단계 1: standalone backend와 false-kill 반례 작성**

```java
@Test
void timeoutAndRuntimeErrorAreNeverKilled() {
    assertEquals(TIMED_OUT, normalize(raw("m1", "timeout")));
    assertEquals(RUNTIME_ERROR, normalize(raw("m2", "nonAssertionThrowable")));
}

@Test
void junitAssertionRequiresControlAndReplay() {
    RawOutcome outcome = assertionWithoutMatchingReplay("m1");
    assertNotEquals(KILLED, normalize(outcome));
}
```

Snapshot test는 symlink·hardlink·path swap·edit-and-restore·timeout·signal 뒤 original byte와 device·inode·mtime·ctime을 비교한다. 이 단계에서는 vendored backend가 아직 없으므로 pristine standalone failure를 주장하지 않는다. `runner-mutation.json`에 이 task의 expected test ID를 사람이 exact 등록한 뒤 runner가 누락·추가·중복을 거부하게 한다. 사람이 관리하는 `src/test/resources/fixtures/commit/t19-files.json`은 `mutation-admission` selector의 sorted concrete path array를 미리 고정하고 자기 path, mutation command wiring을 바꾸는 `src/main/java/io/github/hwainhwang/sentinel/cli/SentinelCli.java`와 `src/main/java/io/github/hwainhwang/sentinel/orchestrator/SentinelOrchestrator.java`를 모두 포함한다. Static test가 task 책임·actual changed set과 exact 대조한다.

`UpstreamPatchVerifierTest`는 작은 synthetic archive·patch·expected tree로 verifier 계약을 먼저 고정한다. `scripts/verify-upstream-patches.sh`가 아직 없어서 첫 실행은 RED여야 하고, 최소 file stub을 만든 뒤에도 pristine archive SHA-256 오류, patch 누락·추가·순서 변경·적용 실패, operator 변경, 적용 결과 path·type·mode·bytes 누락·추가·불일치가 각각 RED여야 한다. 모든 반례는 Maven backend와 project test process 실행 0을 함께 검증한다.

`SandboxLease`는 T03 `sandbox-lease-v1`, `sandbox-control-layout-v1`, guardian과 exact age policy를 canonical JSON으로 구현한다. Approved root에서 lease·fixed marker filename·relative leaf·owner·mode·device·inode를 JNA descriptor로 검증하고 gate 뒤에만 backend를 실행한다. Lease age는 T17 Clock의 `leaseBoottimeNanos`와 `sampleUtcWithSyncProof`만 소비한다. Catch 가능한 terminal은 guardian의 authenticated tree-drained marker 뒤 정리한다. 다음 run은 valid marker와 age-expired가 모두 맞을 때만 `renameat2(RENAME_NOREPLACE)` quarantine·directory sync 뒤 descriptor-relative delete한다. Marker missing·guardian crash·foreign/duplicate leaf·HMAC/path identity 불명은 cross-boot에서도 영구 no-touch다. Explicit raw output은 별도다.

Java package의 first-party guardian은 T03 subreaper·pinned JNA pidfd·HMAC tree-drained 계약을 전부 구현한다. Controller EOF와 정상 drain에서 `setsid`·double-fork descendant가 adopted direct child가 될 때마다 pidfd TERM·KILL과 `waitid(P_PIDFD)`를 반복하고 ECHILD 뒤에만 marker를 durable commit한다. Numeric `kill`·`killpg`·`tgkill`은 0이다. Guardian SIGKILL·marker/HMAC 불명은 cross-boot와 age-expired에서도 영구 unknown·no-delete다.

Mutation 결과의 killed/in-scope fraction도 T18 reduce와 `canonical-decimal-v1` 하나로만 render한다. Gate는 decimal percentage가 아니라 exact count equality를 사용하고 0 denominator는 percentage를 만들지 않고 quality failure다.

`multi-file`은 production 첫 file과 마지막 file에 각각 mutant 1개를 만들고 per-file candidate count·digest와 합산 plan 2개를 고정한다. Production inventory file 하나라도 bridge 호출·candidate plan에서 빠지거나 file별 digest join이 다르면 mutant 실행 0회에서 backendError다.

Acceptance는 Surefire rerun을 강제해 distinct nonce의 같은 test selection baseline을 두 번 실행하고 failure·ID mismatch에서 JaCoCo·candidate·mutant 호출 0을 확인한다. Prepare는 snapshot 내부 argv·minimal environment만 사용하고 generated-output root의 protected overlap·symlink·hardlink·path swap을 거부한다.

`HelpDoctorTest`는 T17의 `backendPending`을 admission 뒤 성공으로 바꾸고 mutate4java archive·patch·companion·backend lock identity 중 하나를 변조하면 dependencyError이며 test·coverage·mutation·state write는 0회임을 검증한다.

- [ ] **단계 2: 실패 확인**

실행: `/usr/bin/bash scripts/verify-dependencies.sh && scripts/mvn.sh -o -B -ntp verify`

기대: dependency resolution과 selector 대상 test source 존재 확인은 성공하고, test compile이 아직 없는 secure JDK filesystem·runner·bridge production type을 참조한 지점에서 실패함. 이 RED에서는 Surefire started·terminal inventory 성공을 주장하지 않고 단계 4 GREEN에서 처음 exact join한다. Dependency failure, selector 대상 test source 0개 또는 아직 존재하지 않는 vendored backend를 먼저 호출한 failure는 RED 근거가 아님

- [ ] **단계 3: pristine vendoring과 제한된 patch 적용**

실행 위치: `upstream/unclebob/mutate4java`

```bash
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/vendor_upstream.py --source . --expected-commit 7b05fdd71e8fe36327aff837806dfbff86af0572 --whole-tree-baseline <workspace>/SENTINEL_SPEC/baselines/upstream-tree.json --expected-archive-sha256 762c4b91ef592fbd07dace1189626013b3935c0fa41407242c52ebb1ffdeb34f --destination <workspace>/SENTINEL_JAVA/third_party/mutate4java
```

실행 위치를 `SENTINEL_JAVA`로 되돌린 뒤 아래 구현·검증·Git 명령을 수행한다.

Tool은 T01 whole-tree 불변을 먼저 검사하고 validated temporary tar file로 tracked archive를 만든다. Archive digest와 member path·type·mode를 검사하고 path traversal·link escape 없이 non-existing destination에 추출한 뒤 canonical extracted manifest를 다시 확인하고 원자 게시한다. 재실행의 complete exact destination은 write 0으로 채택하고 partial·extra·missing·mismatch destination은 overwrite·delete·repair 없이 중단한다. Crash test는 rename 전·직후·receipt 직전 경계를 포함한다. Pristine failure receipt가 아래 계약으로 성공적으로 고정된 뒤에만 새 repo에서 patch한다. Patch 1은 parent POM을 제거한 Java 17 standalone build, patch 2는 실행 전 candidate inventory와 raw outcome enum·machine report, patch 3은 `List<String>` argv와 JUnit Platform `TestExecutionListener`, timeout·process tree·nonce, patch 4는 full mode·fresh test·manifest/source write 금지만 담당한다. Mutation operator source digest가 바뀌면 검사가 실패한다.

먼저 synthetic `UpstreamPatchVerifierTest`를 다시 실행하면서 verifier를 최소 구현해 GREEN으로 만든다. Verifier는 lock에 고정된 pristine archive SHA-256과 ordered exact patch filename·SHA-256을 확인하고 owner-only temporary directory에 안전 추출한 뒤 순서대로 patch를 적용한다. 적용 전·후 operator path set과 각 bytes digest가 같아야 한다. 마지막에는 재구성한 tree와 committed `third_party/mutate4java` 전체를 path·type·POSIX mode·file bytes 또는 symlink target 단위로 exact 비교한다. Missing·extra·reordered patch, wrong archive, apply failure, operator 변경과 resulting tree 불일치는 backend 실행 0에서 nonzero다. Synthetic oracle이 GREEN이 된 뒤 아래 pristine-parent mode와 실제 archive·네 patch·vendored tree를 검증한다.

Patch 적용 전 `/usr/bin/bash scripts/verify-dependencies.sh && /usr/bin/bash scripts/verify-upstream-patches.sh pristine-parent --output <workspace>/build/t19/pristine-parent-failure.json`을 실행한다. Wrapper는 pinned Maven을 `-o -B -ntp -f third_party/mutate4java/pom.xml verify`로 실행하고 expected nonzero를 성공적으로 수집한다. Receipt exact fields는 `version="sentinel-pristine-parent-failure-v1"`, source commit, POM SHA-256, parent coordinates, resolved relative parent path, argv 배열, integer exit code, `diagnosticCode="nonResolvableParentPom"`, `networkCalls=0`, sorted operator source digest다. Raw stdout·stderr는 넣지 않는다. Exit가 0이거나 diagnostic·operator digest·network count가 다르면 wrapper가 nonzero로 끝나고 patch를 시작하지 않는다. 이 receipt는 단계 2의 production RED와 섞지 않는다.

Admission test는 mock adapter가 아니라 실제 standalone `mutate4java-bridge.jar`를 all-killed, survivor, timeout, coverage-failure tiny project 각각에 argv로 실행한다. Bridge의 선행 candidate ID·operator·source inventory와 raw outcome를 고정 raw fixture에 대조하고 root normalizer의 canonical record를 expected canonical fixture와 byte 단위로 대조한다. Process exit 0이나 summary footer만 신뢰하거나 actual executable을 호출하지 않은 mock-only test는 admission 통과로 인정하지 않는다.

`LinuxFs`는 T17에서 JNA 5.17.0·packaged dispatch digest·owner-only extraction을 검증한 `JnaNativeLoader`로만 pinned glibc syscall boundary를 호출한다. Trusted root directory FD에서 `openat2`의 beneath·no-symlink·no-magic-link, fallback 없는 `openat(O_NOFOLLOW)`, opened object `fstat`의 device·inode·link count·mode, `renameat2(RENAME_NOREPLACE)`, `unlinkat`, byte-range `fcntl`을 descriptor-relative로 제공한다. JNA JAR와 packaged Linux x86_64 native dispatch bytes는 `dependency-lock.json` digest와 일치해야 하고 owner-only temporary extraction root 밖 system JNA load를 금지한다. Kernel·glibc ABI와 syscall probe가 `supportedOS`에 맞지 않거나 `SecureDirectoryStream`만으로 대체되면 dependencyError다.

JUnit·OpenTest4J assertion type, original control pass, 같은 mutant의 fresh replay HMAC signature가 모두 맞을 때만 killed다. Discovery·engine error, 일반 throwable, timeout, nonzero process, up-to-date skip, nonce 누락은 killed가 아니다.

Patched backend companion에 필요한 dependency·transitive JAR·Maven plugin까지 `dependency-lock.json` exact set을 재생성한다. Coordinate, source repository, size와 SHA-256을 모두 검증한다. 변경 직후 `/usr/bin/bash scripts/verify-dependencies.sh --populate` 한 번만 network를 허용해 isolated local repository를 채운 뒤 verifier와 모든 Maven command를 offline으로 실행하며 extra·missing artifact를 거부한다.

- [ ] **단계 4: bridge·snapshot·gate 통과 확인**

실행: `/usr/bin/bash scripts/verify-upstream-patches.sh mutate4java`

실행: `/usr/bin/bash scripts/verify-dependencies.sh && scripts/mvn.sh -o -B -ntp test && scripts/mvn.sh -o -B -ntp verify`

기대: standalone build, 네 tiny project의 actual companion candidate·operator·raw outcome와 canonical normalized record가 고정 fixture와 정확히 일치, doctor admitted backend 성공과 변조의 무부작용 실패, candidate/result exact set, 9개 상태와 unknown 반례, source 불변, `/bin/sh -lc` 도달 0, all-killed 1개 이상만 exit 0. SIGKILL orphan은 valid HMAC tree-drained marker+age-expired일 때만 quarantine·delete하고 marker missing·guardian crash는 영구 no-touch다. PID reuse process에는 signal 0이며 공용 evidence·finding·history·export·default artifact·diagnostic raw canary 0, catchable 또는 valid-marker cleanup 뒤 sandbox raw 0이다. `multi-file`의 첫·마지막 file candidate가 모두 합산되고 하나를 생략하면 backendError

- [ ] **단계 5: commit**

```bash
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py materialize-exact --repository . --task T19 --phase mutation-admission --base-head <T18_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --source src/test/resources/fixtures/commit/t19-files.json --selector mutation-admission --output <workspace>/build/commit-inventory/T19/SENTINEL_JAVA/mutation-admission/stage.paths
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py stage-exact --repository . --task T19 --phase mutation-admission --base-head <T18_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --manifest <workspace>/build/commit-inventory/T19/SENTINEL_JAVA/mutation-admission/stage.paths
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py commit-prepared --repository . --task T19 --phase mutation-admission --prepared-receipt <PREPARED_RECEIPT> --prepared-receipt-sha256 <PREPARED_RECEIPT_SHA256> --base-head <T18_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --expected-message "feat: add typed Java mutation bridge (요구사항-22..32,40,43)"
```

### T20: SENTINEL_JAVA evidence·history·privacy와 전체 command

**충족 요구사항:** 요구사항-06..요구사항-08, 요구사항-28, 요구사항-29, 요구사항-32, 요구사항-40, 요구사항-42, 요구사항-45..요구사항-54

**파일:**

- 생성: `src/main/java/io/github/hwainhwang/sentinel/evidence/{Models,Privacy,PosixLock,CommitSequence,EvidenceStore}.java`
- 생성: `src/main/java/io/github/hwainhwang/sentinel/history/{HistoryService,Retention,Export,Resolver}.java`
- 생성: `scripts/run-e2e-fixture.sh`, `src/test/resources/fixtures/projects/{java-pass,java-history}/**`
- 테스트: `src/test/java/io/github/hwainhwang/sentinel/evidence/{EvidenceStoreTest,CommitSequenceTest,ProjectKeyRotationTest}.java`, `src/test/java/io/github/hwainhwang/sentinel/history/{HistoryServiceTest,RetentionTest,ExportTest,ResolverTest}.java`
- 테스트: `src/test/java/io/github/hwainhwang/sentinel/integration/{CrossProcessLockTest,CrashRecoveryTest}.java`, `src/test/java/io/github/hwainhwang/sentinel/acceptance/{CheckCommandTest,HistoryCommandTest,PrivacyTest}.java`, `src/test/resources/test-inventory/evidence-history.json`
- 생성: `docs/privacy.md`
- 수정: `src/main/java/io/github/hwainhwang/sentinel/{workspace/LinuxFs.java,cli/SentinelCli.java,orchestrator/SentinelOrchestrator.java}`, `README.md`, `docs/index.md`, `docs/operations.md`, `docs/log.md`

**받는 것:** T18 CRAP, T19 mutation과 `SandboxLease`, T03 evidence·sandbox-lease golden

**주는 것:** 완성된 `sentinel-java` 5개 command와 POSIX-compatible immutable history

이 task의 completed와 incomplete prune은 T03 `retention-marker-first-v1`을 그대로 구현한다. 두 kind 모두 marker directory sync 전 selected bundle delete는 0이다. Completed는 각 marker의 `(commitSequence <= sequenceHighWaterAtCommit && committedAtUtc < cutoffUtc)` pair union만 적용하고 marker 뒤 더 큰 sequence run을 소급 숨기지 않는다. Incomplete는 marker의 sorted immutable selection subset만 resume하며 신규 eligible run과 선택 뒤 completed가 된 run을 삭제하지 않는다. 나머지도 stored started·lease·tree-drained digest와 HMAC join을 다시 증명한 경우만 descriptor-relative delete한다.

- [ ] **단계 1: atomicity·lock·privacy 실패 test 작성**

```java
@Test
void evidenceFailureRevokesCalculatedPass() {
    RunResult result = runFixture("directory-fsync-failure");
    assertEquals(EVIDENCE_ERROR, result.terminalStatus());
    assertEquals(7, result.exitCode());
    assertFalse(result.certified());
}

@Test
void sequenceAllocationCrashLeavesAGap() {
    SequenceFaultResult result = sequenceFaultFixture("crash-after-sequence-sync");
    assertEquals(result.crashedSequence().add(ONE), result.nextCompletedSequence());
}
```

- [ ] **단계 2: 실패 확인**

실행: `/usr/bin/bash scripts/verify-dependencies.sh && scripts/mvn.sh -o -B -ntp verify`

기대: evidence·history package 부재로 실패

- [ ] **단계 3: 고정 JDK file-lock store와 offline history 구현**

Pinned JNA `LinuxFs`의 trusted root FD, `openat2`·`openat(O_NOFOLLOW)`, opened-object `fstat`, `renameat2`·`unlinkat`와 libc `fcntl`만 descriptor-relative SafePath·lock 근거로 사용한다. Python·TypeScript·Go lock과 pairwise 상호 운용 시험이 실패하면 Java release를 차단한다. Event·evidence는 file sync, directory sync, same-directory atomic rename 순서를 지킨다. Persistent evidence는 실제 resolved config 우선순위·digest, scope·target·mutation domain, mutate4java commit·archive·patch identity, operator·exclusion inventory와 bridge·runner version을 privacy-safe field로 기록한다. Retention cutoff equality는 보존하고 completed·incomplete 기준을 분리한다. 공용 bytes에는 HMAC fingerprint와 allowlist field만 남기며 local JSONL resolver는 network·state write 없이 현재 source 위치만 일시 출력한다.

T17 `ProjectKeyProvider` output은 T03 규칙대로 첫 quality run의 project state initialize 또는 exact next-epoch atomic rotation에만 적용한다. Same key·epoch 재실행은 write 0이고 invalid epoch·key 조합은 started·child 호출 0이다. Temporary create·file sync·rename·directory sync fault와 retry에서 old 또는 new complete `project.json`만 허용한다. Help·doctor·history는 envelope option을 거부하고 state create·rotate 0이다.

`CommitSequence`는 T03 schema·derived HMAC·retention high-water floor를 그대로 구현한다. `EvidenceStore`는 exclusive lock 안에서 next sequence file을 durable commit한 뒤에만 같은 sequence의 event와 evidence를 쓰며 allocation crash gap을 재사용하지 않는다. `HistoryService`는 UTC가 아니라 sequence로 fold하고 invalid·duplicate·rollback에서 exit 7, 추가 write·delete 0이다.

`history prune --incomplete`는 T19의 동일 `SandboxLease` parser와 HMAC tree-drained marker oracle을 호출해 runId·projectToken·lease generation·guardian identity를 join한다. Marker missing·HMAC mismatch·guardian crash·corrupt lease와 외부 guardian start 전임을 증명하지 못한 missing lease는 incomplete run을 영구 보존한다. Valid marker, `startedAtUtc < cutoffUtc`, completed evidence 부재가 모두 맞을 때만 whole incomplete bundle을 descriptor-relative로 삭제하고 cutoff equality를 보존한다. Sandbox quarantine은 별도 `mayQuarantineSandbox=validMarker+ageExpired`만 사용한다.

`run-e2e-fixture.sh`는 고정 fixture 이름 allowlist만 받고 validated `mktemp -d`의 owner-only project copy에서 actual CLI를 실행한 뒤 EXIT·INT·TERM cleanup과 원 checked-in fixture whole manifest 불변을 확인한다. Checked-in project에서 `.sentinel`을 직접 만들지 않는다.

- [ ] **단계 4: Java end-to-end 통과 확인**

실행: `/usr/bin/bash scripts/verify-dependencies.sh && scripts/mvn.sh -o -B -ntp verify`

실행: `/usr/bin/bash scripts/run-e2e-fixture.sh java-pass check --format json`

실행: `/usr/bin/bash scripts/run-e2e-fixture.sh java-history history --repeated --format json`

기대: 5개 command, repeated history, crash recovery, privacy canary 0건, corrupt marker exit 7, local resolver write 0, stable stdin key의 같은 epoch repeated와 exact next-epoch 분리·atomic rotation, child key byte 0. Incomplete run은 marker missing·guardian crash·cutoff equality를 보존하고 valid tree-drained marker+started-before-cutoff+completed 없음만 whole run 삭제하며 sandbox는 valid marker+cleanup-age-expired만 quarantine

- [ ] **단계 5: commit**

```bash
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py prepare-and-stage --repository . --task T20 --phase evidence --base-head <T20_BASE_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --output-root <workspace>/build/commit-inventory -- src scripts/run-e2e-fixture.sh README.md docs
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py commit-prepared --repository . --task T20 --phase evidence --prepared-receipt <PREPARED_RECEIPT> --prepared-receipt-sha256 <PREPARED_RECEIPT_SHA256> --base-head <T20_BASE_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --expected-message "feat: complete Java evidence and history commands (요구사항-06..08,28,29,42,45..54)"
```

### T21: SENTINEL_CLJ 설치·SPEC·config·scope·help·doctor

**충족 요구사항:** 요구사항-05, 요구사항-09, 요구사항-18, 요구사항-21, 요구사항-32, 요구사항-41, 요구사항-42, 요구사항-55

**파일:**

- 생성: `SENTINEL_CLJ/deps.edn`, `dependency-lock.json`, `scripts/verify-dependencies.sh`, `bin/sentinel-clj`, `resources/sentinel-version.edn`, `spec-lock.json`, `vendor/sentinel-spec/**`
- 검증: T01에서 resolver 없는 offline mode까지 완성한 `toolchain.lock.json`, `scripts/{bootstrap-clojure,clojure,java}.sh`
- 생성: `src/sentinel_clj/{cli.clj,orchestrator.clj,contracts/{loader.clj,models.clj},config/{models.clj,resolver.clj,scope.clj}}`
- 생성: `src/sentinel_clj/platform/{entropy,file_ops,clock,process,project_key,hmac_sha256,jna_native_loader}.clj`
- 테스트: `tests/bootstrap/test_dependency_verifier.py`, `test/sentinel_clj/test_runner.clj`, `contracts/loader_test.clj`, `config/{resolver_test,scope_test}.clj`, `platform/{facades_test,project_key_test,hmac_sha256_test,jna_native_loader_test}.clj`, `acceptance/help_doctor_test.clj`, `test/fixtures/test-inventory/foundation.edn`, `test/fixtures/{polyglot,unclassified}/`
- 생성: `docs/contracts.md`
- 수정: `README.md`, `docs/index.md`, `docs/log.md`

**받는 것:** T04 bundle bytes, commit과 manifest digest, 고정 Clojure release profile

**주는 것:** Clojure `VerifiedContract`, `ResolvedModule`, `ClassifiedScope`, side-effect 없는 help·doctor

`platform`의 여섯 production dependency protocol은 entropy, file·directory sync·rename·descriptor operation, evidence·retention용 `utc-now`, timeout·lock deadline용 process `monotonic-now`, lease용 `lease-boottime-nanos`와 UTC instant·동기화 proof를 한 결과로 돌려주는 `sample-utc-with-sync-proof`, child process spawn·signal·reap, project-key 입력, HMAC-SHA-256 계산을 감싸고 orchestrator constructor map으로 받는다. Clojure Clock의 lease method는 lock-verified JNA libc `clock_gettime(CLOCK_BOOTTIME)`와 `adjtimex` bracket만 쓰고 arbitrary integer·unsigned decimal string 경계를 유지한다. UTC wall clock은 monotonic deadline에 사용할 수 없고 process monotonic 값은 evidence timestamp나 lease에 사용할 수 없다. Default CLI는 OS implementation만 조립하며 option·config·environment로 test implementation을 선택할 수 없다. Test implementation은 `test/**`에만 두고 T25가 release dependency graph와 JAR에서 0개임을 확인한다.

`project-key-provider`는 T02의 `--project-key-stdin` canonical envelope를 bounded read·validate·decode하고 opaque 32-byte key와 epoch를 orchestrator parent에만 준 뒤 stdin을 닫는다. Raw key를 string representation·exception·argv·environment로 만들지 않으며 child process facade는 provider 사용 여부와 무관하게 stdin을 `/dev/null`로 고정한다. Option이 없으면 quality command만 OS CSPRNG local-key 경로를 사용한다. Help·doctor·history는 provider를 호출하지 않는다.

`hmac-sha256` production provider는 JDK `Mac`의 `HmacSHA256`만 사용하며 fingerprint, projectToken과 bootToken의 모든 MAC을 계산한다. Production direct-call 우회는 static inventory 0이고 provider failure는 외부 child 호출·cleanup·prune delete 0의 exit 7 `evidenceError`다.

Clojure foundation Clock test는 production Clock 아래 test-only JNA syscall protocol만 주입해 T03의 두 `CLOCK_MONOTONIC_RAW`, 두 fresh zero-filled timex·modes 0 adjtimex와 중간 `CLOCK_REALTIME`의 exact 다섯-call trace를 검사한다. Extra·separate UTC read, memory reuse·nonzero field, `STA_NANO` 정규화, maxerror·span·uncertainty 산식, 각 error·status와 forward·backward step vector를 모두 거부하거나 unknown으로 만든다. UTC instant+uncertainty+proof는 한 immutable map이다. Production direct JNA call은 default adapter namespace 밖 static inventory 0이다.

`jna-native-loader`는 JNA namespace를 처음 require하기 전에 dependency lock의 packaged Linux x86_64 `jnidispatch` resource byte를 owner-only validated temporary directory에 exclusive-create·file-sync·directory-sync하고 digest를 다시 확인한다. Launcher는 ambient `jna.boot.library.path`, `jna.library.path`, `JNA_TMPDIR`와 system lookup을 전달하지 않고 validated extraction directory만 `jna.boot.library.path`로 주며 `jna.nosys=true`, `jna.nounpack=true`를 고정한다. 초기화 뒤 extracted file identity·mode·digest를 다시 확인하고 cleanup한다. System dispatch, world-writable extraction, digest mismatch와 preloaded JNA fixture는 Clock syscall 0에서 dependencyError다. T23 `native-fs`도 이 loader만 재사용한다.

- [ ] **단계 0A: dependency verifier 자체의 실패 test를 먼저 고정**

T01의 pinned Clojure CLI·JDK bootstrap으로 `deps.edn`, `dependency-lock.json`, `test/sentinel_clj/test_runner.clj`, `test/fixtures/test-inventory/foundation.edn`과 system-Python bootstrap oracle `tests/bootstrap/test_dependency_verifier.py`를 먼저 만들되 `scripts/verify-dependencies.sh`와 `src/sentinel_clj` production namespace는 아직 만들지 않는다. `/usr/bin/python3 -I tests/bootstrap/test_dependency_verifier.py`를 실행해 missing verifier 때문에 RED인지 확인한다. Test-owned fake cache와 fake transport로 missing·extra·wrong digest·classpath reorder·path escape, hostile user `deps.edn`·Maven settings·Git config·proxy가 각각 RED이며 resolver·JVM·network spawn은 0인 반례를 고정한다.

- [ ] **단계 0B: 최소 verifier를 구현하고 isolated cache를 채움**

`scripts/verify-dependencies.sh`만 최소 구현해 bootstrap oracle을 GREEN으로 만든 뒤 `/usr/bin/bash scripts/bootstrap-clojure.sh && /usr/bin/bash scripts/verify-dependencies.sh --populate && /usr/bin/bash scripts/verify-dependencies.sh && scripts/clojure.sh --offline -M:test-runner-self`를 실행한다. `--populate`만 network와 pinned Clojure CLI dependency resolution을 허용한다. Populate launcher는 owner-only synthetic HOME·`CLJ_CONFIG`·Maven repository·Gitlibs directory와 empty settings를 고정하고 inherited Java·Clojure·Maven·Git·proxy environment를 제거한다. 각 allowlisted profile은 exact environment `JAVA_CMD=<PINNED_JAVA_ABSOLUTE_PATH>`, `HOME=<SYNTHETIC_HOME>`, `CLJ_CONFIG=<ISOLATED_CONFIG>`, `GITLIBS=<ISOLATED_GITLIBS>`, Maven repository override와 exact argv `<PINNED_CLOJURE_ABSOLUTE_PATH> -J-Duser.home=<SYNTHETIC_HOME> -Srepro -Sforce -A:<PROFILE> -Spath`로 한 번 계산한다. Install `deps.edn` digest와 pinned Java·Clojure executable을 먼저 검증한다. Stdout은 UTF-8 classpath 한 줄과 final LF 하나만 허용하고 stderr·추가 line·empty element·relative path를 거부한다. `dependency-lock.json.classpathProfiles`는 `test-runner-self`, `test`와 이후 승인된 profile별 exact alias-to-argv mapping과 ordered entry를 `repoPath` 또는 `mavenCache` relative path, kind, size·SHA-256으로 고정한다. V1 active profile은 Maven dependency만 허용하며 Git dependency, unused upstream alias와 tools.deps Git fetch count는 0이다. Populate가 계산한 classpath는 이 expected ordered set과 exact일 때만 채택한다. `scripts/clojure.sh --offline`은 launcher flag와 allowlisted `-M:test-runner-self|test`를 직접 해석하고 inherited Java·Clojure·Maven·Git·proxy environment를 지운다. 이어 lock의 각 entry를 owner-only isolated cache 또는 repository root FD 아래에서 다시 검증하고 pinned `scripts/java.sh -cp <VERIFIED_CLASSPATH> clojure.main -m sentinel-clj.test-runner <PROFILE_ARGS>`를 argv로 실행한다. Offline mode는 Clojure CLI, tools.deps resolver와 `-Soffline`을 전혀 호출하지 않는다. Wrong option order, PATH Java, stdout extra line, unknown profile·main option·classpath entry, missing·extra·digest mismatch와 path escape는 resolver·child JVM·network 호출 0에서 실패한다. 뒤 두 command는 network 0으로 zero expected-ID 거부·missing·extra·duplicate 감지를 통과해야 한다. 이어 `SENTINEL_SPEC`에서 `scripts/uv.sh run python tools/vendor_spec.py --archive ../build/t04/SENTINEL_SPEC-0.1.0-rc.1.tar --receipt ../build/t04/SENTINEL_SPEC-0.1.0-rc.1.tar.sha256.json --source-tag spec-v0.1.0-rc.1 --destination ../SENTINEL_CLJ/vendor/sentinel-spec --lock-output ../SENTINEL_CLJ/spec-lock.json`을 실행하고 `SENTINEL_CLJ`로 돌아온다. 단계 1 test와 nonempty foundation inventory를 함께 쓴 뒤 단계 2가 missing production namespace 때문에 RED여야 한다. Dependency·vendor failure나 test 0개는 RED 근거가 아니다.

- [ ] **단계 1: lock·scope·help 실패 test 작성**

```clojure
(deftest help-does-not-create-state
  (let [project (temporary-project)
        result (run-cli project "--help")]
    (is (zero? (:exit-code result)))
    (is (not (exists? (path project ".sentinel"))))))

(deftest scope-rejects-unclassified-clojure-source
  (is (= :unclassified-source (error-code #(resolve-fixture "unclassified")))))
```

- [ ] **단계 2: 실패 확인**

실행 위치: `SENTINEL_CLJ`

실행: `scripts/clojure.sh --offline -M:test`

기대: namespace 부재로 실패

- [ ] **단계 3: 고정 deps와 최소 foundation 구현**

CI bootstrap은 Clojure CLI 1.12.5.1664 archive digest를 검증하고 `deps.edn`은 Clojure 1.12.0, data.json 2.5.1, tools.reader 1.4.2, Cloverage 1.2.4와 JNA 5.17.0을 exact pin한다. `dependency-lock.json`은 active Maven dependency와 transitive JAR의 coordinate·source repository·size·SHA-256, profile별 ordered verified classpath를 고정하고 JNA JAR와 packaged Linux x86_64 native dispatch artifact를 exact set으로 포함한다. Verifier는 isolated cache를 채울 때와 offline 실행 전에 dependency set·digest·classpath order를 대조하고 extra·missing artifact를 거부하며 foundation test는 JNA `CLOCK_BOOTTIME`·`adjtimex` ABI probe도 실행한다. Wrapper negative test는 고정 CLI의 unsupported `-Soffline`을 호출하지 않는지, hostile user Maven settings·Git config·Java tool option·proxy, cache extra·missing JAR, classpath reorder·path escape와 unknown profile에서 resolver·JVM·network 호출이 0인지 확인한다. `resources/sentinel-version.edn`은 release version의 단일 runtime carrier이며 `0.1.0-rc.1`로 시작한다. CLI·doctor·result가 이 packaged resource만 읽고 test가 세 값의 equality를 고정한다. T25가 `build.clj`와 tools.build를 추가할 때 build 산출물 manifest까지 네 번째 값으로 join한다. `:test` alias는 populate-time classpath 계산 입력일 뿐 offline 실행은 그 alias를 재해석하지 않는다. Runner는 static expected namespace·test-var ID inventory를 고정하고 실제 load·started·terminal ID set과 exact 비교한 뒤 `clojure.test/run-tests`의 fail·error count를 process exit로 변환한다. Expected 0개, namespace·test 누락, duplicate와 layer별 실행 0개는 nonzero이고 CI evidence에 discovered·executed count를 남긴다. Scope는 `.clj`, `.cljc`를 native 발견한 뒤 production, test, generated, vendor, build-output을 정확히 분류한다. Foundation `doctor`는 pinned JDK·Clojure CLI·JNA, `dependency-lock.json`, vendored SPEC checksum, resolved config와 scope를 읽기만 한다. Admission 전에는 `backendPending`을 반환하고 release-capable 성공으로 오인하지 않으며 T23이 clj-mutate archive·patch·companion·backend lock identity 검사를 추가한다. 두 단계 모두 namespace require, test, coverage, backend와 state write를 실행하지 않는다.

Config test는 CLI override, project config, SPEC default 순서, argv-only command, minimal child environment, environment contract digest, `localCacheDir`와 generated-output SafePath를 검증한다. Java·Clojure ambient option과 project namespace는 config 해석 중 실행되지 않는다.

- [ ] **단계 4: foundation 통과 확인**

실행: `/usr/bin/bash scripts/verify-dependencies.sh && scripts/clojure.sh --offline -M:test`

기대: tampered SPEC exit 5, module ambiguity exit 3, help·doctor project code 실행·write 0회, facade fault는 constructor map injection으로만 도달하고 production namespace·CLI dependency graph에서 test implementation 선택 경로 0개

- [ ] **단계 5: commit**

```bash
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py prepare-and-stage --repository . --task T21 --phase foundation --base-head <T21_BASE_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --output-root <workspace>/build/commit-inventory -- deps.edn dependency-lock.json scripts/verify-dependencies.sh bin resources spec-lock.json vendor src test tests README.md docs
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py commit-prepared --repository . --task T21 --phase foundation --prepared-receipt <PREPARED_RECEIPT> --prepared-receipt-sha256 <PREPARED_RECEIPT_SHA256> --base-head <T21_BASE_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --expected-message "feat: add Clojure contract and scope foundation (요구사항-05,09,18,21,32,41,42,55)"
```

### T22: SENTINEL_CLJ native CRAP

**충족 요구사항:** 요구사항-10, 요구사항-11, 요구사항-14..요구사항-17, 요구사항-34, 요구사항-41

**파일:**

- 생성: `src/sentinel_clj/crap/{models,formula,analyzer,coverage,semantic_site}.clj`, `src/sentinel_clj/rendering/canonical_decimal.clj`
- 테스트: `test/sentinel_clj/crap/{formula_test,analyzer_test,coverage_test,semantic_site_test}.clj`, `test/sentinel_clj/rendering/canonical_decimal_test.clj`, `test/sentinel_clj/acceptance/crap_command_test.clj`, `test/fixtures/test-inventory/crap.edn`, `test/fixtures/crap/{anonymous-fn,multi-arity,same-line,tagged-literal,side-effect,stale,exact-boundary,decision-matrix,stable-sort}/`
- 수정: `test/sentinel_clj/test_runner.clj`
- 생성: `docs/architecture.md`
- 수정: `src/sentinel_clj/{cli,orchestrator}.clj`, `docs/index.md`, `docs/log.md`

**받는 것:** T21 scope, T04 exact CRAP vector, pinned `crap4clj` corpus

**주는 것:** safe reader callable inventory, Cloverage mapping, exact Clojure CRAP result와 `sentinel-clj crap`

- [ ] **단계 1: exact ratio·safe reader 실패 test 작성**

`crap.edn`에 이 task의 namespace·test-var expected ID를 exact 등록하고 `test_runner.clj`에는 `crap` selector만 먼저 연결한다. Expected inventory와 runner가 통과한 상태에서 production namespace 부재를 RED로 확인한다.

```clojure
(deftest exact-crap-keeps-ratio
  (is (= 17/4 (:raw (calculate-crap 4 3 4))))
  (is (true? (:pass (calculate-crap 4 3 4)))))

(deftest analysis-never-executes-project-code
  (let [marker (temporary-marker)]
    (analyze-fixture "side-effect" marker)
    (is (not (exists? marker)))))
```

- [ ] **단계 2: 실패 확인**

실행: `scripts/clojure.sh --offline -M:test --include-id crap`

기대: `sentinel-clj.crap` namespace 부재로 실패

- [ ] **단계 3: safe reader analyzer와 exact gate 구현**

Clojure ratio constructor가 만든 기약분수의 `numerator`·`denominator`를 wire에 쓰고 zero를 `0/1`로 고정한다. `canonical-decimal` namespace는 T02 `canonical-decimal-v1`을 arbitrary integer `quot`·`rem`으로 구현하고 `double`, `format`, Java decimal·locale formatter를 쓰지 않는다. CRAP·coverage와 뒤의 mutation kill-rate renderer가 이 함수 하나를 호출한다. Test는 vendored SPEC의 reduce, `1/3`, half-even down/up, carry, zero·integer와 큰 fraction golden bytes를 직접 소비한다. Row comparator도 T02 `crap-row-order-v1`의 exact cross-multiply, UTF-8 byte path·callable ID와 raw UTF-8 byte offset을 구현하고 near-equal·한글·astral golden을 소비한다.

Analyzer는 `*read-eval*=false`와 tools.reader만 사용하고 project `data_readers.clj`, unknown tag, namespace require, macro expansion, `eval`, source load를 실행하지 않는다. `defn`, `defn-`, method implementation, `fn`을 분리한다. `multi-arity`는 이름·arity signature가 다른 exact body ID 2개와 각 coverage ownership을 기대하고 다른 function과 합치지 않는다. `decision-matrix`는 `if`·`when` 계열, `and`, `or`, loop, catch와 `cond`·`case` 계열 multi-clause form의 syntax별 expected 증가값과 callable별 total CC를 고정하고 nested `fn` decision의 parent 중복 0을 검증한다. Config가 고정한 Cloverage form 또는 검증된 LCOV line basis만 사용하며 run 중 fallback하지 않는다. 동일 line의 독립 `fn` coverage가 모호하면 모두 coverageUnknown이다.

- [ ] **단계 4: Clojure CRAP 통과 확인**

실행: `scripts/clojure.sh --offline -M:test --include-id crap`

기대: anonymous `fn`, 모든 Clojure CC syntax의 exact count와 nested parent 중복 0, 기약분수·canonical decimal·exact 8.0, missing·stale·ambiguous coverage 실패, tagged literal·namespace side effect 0회, near-equal·한글·astral 정렬 결과가 반복 실행에서 byte 단위로 같음

- [ ] **단계 5: commit**

```bash
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py prepare-and-stage --repository . --task T22 --phase crap --base-head <T22_BASE_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --output-root <workspace>/build/commit-inventory -- src test docs
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py commit-prepared --repository . --task T22 --phase crap --prepared-receipt <PREPARED_RECEIPT> --prepared-receipt-sha256 <PREPARED_RECEIPT_SHA256> --base-head <T22_BASE_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --expected-message "feat: implement native Clojure CRAP gate (요구사항-10,11,14..17,34,41)"
```

### T23: SENTINEL_CLJ snapshot·clojure.test typed runner·clj-mutate bridge·gate

**충족 요구사항:** 요구사항-22..요구사항-32, 요구사항-41, 요구사항-43

**파일:**

- 생성: `src/sentinel_clj/runner/{clojure_test_reporter,protocol}.clj`
- 생성: `src/sentinel_clj/workspace/{native_fs,safe_path,snapshot,process_tree,sandbox_lease,guardian,start_gate}.clj`
- 생성: `src/sentinel_clj/mutation/{protocol,clj_mutate,normalizer,gate}.clj`, `backend.lock.json`
- 생성: `third_party/clj-mutate/**`, `upstream/patches/{0001-machine-report-full-mode.patch,0002-typed-clojure-test-runner.patch,0003-isolation-coverage-reader.patch}`
- 생성: `scripts/verify-upstream-patches.sh`, `test/fixtures/test-inventory/runner-mutation.edn`
- 테스트: `test/sentinel_clj/mutation/upstream_patch_verifier_test.clj`, `test/fixtures/upstream-patches/**`
- 생성: `test/fixtures/commit/t23-files.json`
- 테스트: runner·workspace·mutation unit·integration·acceptance namespace와 `test/fixtures/mutation/{all-killed,survivor,timeout,coverage-failure,all-states,multi-file}/**`
- 수정: `src/sentinel_clj/cli.clj`, `src/sentinel_clj/orchestrator.clj`, help·doctor test namespace, `test/sentinel_clj/test_runner.clj`
- 생성: `docs/backend.md`, `docs/operations.md`, `docs/lineage.md`
- 수정: `deps.edn`, `dependency-lock.json`, `scripts/verify-dependencies.sh`, `upstream/UPSTREAM.md`, `docs/index.md`, `docs/log.md`

**받는 것:** T21 scope, T22 coverage matcher, T04 runner·mutation vector, pristine clj-mutate commit

**주는 것:** copied snapshot, nonce 기반 clojure.test event, complete raw bridge와 killed-only result

- [ ] **단계 1: timeout·error·symlink false-kill 반례 작성**

```clojure
(deftest error-and-timeout-are-never-killed
  (is (= :runtime-error (normalize (raw-outcome :error))))
  (is (= :timed-out (normalize (raw-outcome :timeout)))))

(deftest fail-needs-fresh-control-and-replay
  (is (not= :killed (normalize (fail-without-matching-replay)))))
```

Workspace test는 worker 안 source·test symlink 0개, path swap·hardlink 거부, timeout·signal 뒤 original byte·metadata 불변을 확인한다. Coverage refresh가 실패한 fixture는 이전 report로 계속하지 않아야 한다.

단계 1에서 `runner-mutation.edn`에 이 task의 namespace·test-var expected ID를 사람이 exact 등록하고 `test_runner.clj`에는 `runner-mutation` selector만 연결한다. 사람이 관리하는 `test/fixtures/commit/t23-files.json`은 `mutation-admission` selector의 sorted concrete path array를 미리 고정하고 자기 path, mutation command wiring을 바꾸는 `src/sentinel_clj/cli.clj`와 `src/sentinel_clj/orchestrator.clj`를 모두 포함하며, data-only parser test가 task 책임·actual changed set과 exact 대조한다. Production namespace는 아직 만들지 않으므로 다음 RED는 test infrastructure가 아니라 실제 구현 부재에서 나야 한다.

`sandbox-lease` namespace는 T03 `sandbox-lease-v1`, `sandbox-control-layout-v1`, guardian과 exact age policy를 canonical JSON으로 구현한다. Approved root에서 lease·fixed marker filename·relative leaf·owner·mode·device·inode를 JNA descriptor로 검증하고 gate 뒤에만 backend를 실행한다. Lease age는 T21 Clock의 `lease-boottime-nanos`와 `sample-utc-with-sync-proof`만 소비한다. Catch 가능한 terminal은 guardian의 authenticated tree-drained marker 뒤 정리한다. 다음 run은 valid marker와 age-expired가 모두 맞을 때만 `renameat2(RENAME_NOREPLACE)` quarantine·directory sync 뒤 descriptor-relative delete한다. Marker missing·guardian crash·foreign/duplicate leaf·HMAC/path identity 불명은 cross-boot에서도 영구 no-touch다. Explicit raw output은 별도다.

Clojure package의 first-party guardian은 T03 subreaper·pinned JNA pidfd·HMAC tree-drained 계약을 전부 구현한다. Controller EOF와 정상 drain에서 `setsid`·double-fork descendant가 adopted direct child가 될 때마다 pidfd TERM·KILL과 `waitid(P_PIDFD)`를 반복하고 ECHILD 뒤에만 marker를 durable commit한다. Numeric `kill`·`killpg`·`tgkill`은 0이다. Guardian SIGKILL·marker/HMAC 불명은 cross-boot와 age-expired에서도 영구 unknown·no-delete다.

Mutation 결과의 killed/in-scope fraction도 T22 reduce와 `canonical-decimal-v1` 하나로만 render한다. Gate는 decimal percentage가 아니라 exact count equality를 사용하고 0 denominator는 percentage를 만들지 않고 quality failure다.

`multi-file`은 production 첫 file과 마지막 file에 각각 mutant 1개를 만들고 per-file candidate count·digest와 합산 plan 2개를 고정한다. Production inventory file 하나라도 bridge 호출·candidate plan에서 빠지거나 file별 digest join이 다르면 mutant 실행 0회에서 backendError다.

Acceptance는 distinct nonce의 같은 `clojure.test` selection baseline을 두 번 fresh 실행하고 failure·ID mismatch에서 Cloverage·candidate·mutant 호출 0을 확인한다. Prepare는 copied snapshot 내부 argv·minimal environment만 사용하고 generated-output root의 protected overlap·symlink·hardlink·path swap을 거부한다.

Help·doctor test는 T21의 `backendPending`을 admission 뒤 성공으로 바꾸고 clj-mutate archive·patch·companion·backend lock identity 중 하나를 변조하면 dependencyError이며 namespace require·test·coverage·mutation·state write는 0회임을 검증한다.

`upstream-patch-verifier-test`는 작은 synthetic archive·patch·expected tree로 verifier 계약을 먼저 고정한다. `scripts/verify-upstream-patches.sh`가 아직 없어서 첫 실행은 RED여야 하고, 최소 file stub을 만든 뒤에도 pristine archive SHA-256 오류, patch 누락·추가·순서 변경·적용 실패, mutation rule 변경, 적용 결과 path·type·mode·bytes 누락·추가·불일치가 각각 RED여야 한다. 모든 반례는 companion과 project test process 실행 0을 함께 검증한다.

- [ ] **단계 2: 실패 확인**

실행: `scripts/clojure.sh --offline -M:test --include-id runner-mutation`

기대: namespace와 JDK filesystem adapter 부재로 실패

- [ ] **단계 3: pristine vendoring과 제한된 patch 적용**

실행 위치: `upstream/unclebob/clj-mutate`

```bash
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/vendor_upstream.py --source . --expected-commit e27dd5df63c4efdd66438587d1c5f49e73661b69 --whole-tree-baseline <workspace>/SENTINEL_SPEC/baselines/upstream-tree.json --expected-archive-sha256 fcd0638e1b60a46779f28d778f542ad52858738bcde4b925cf1ce28db2eb5b5a --destination <workspace>/SENTINEL_CLJ/third_party/clj-mutate
```

실행 위치를 `SENTINEL_CLJ`로 되돌린 뒤 아래 구현·검증·Git 명령을 수행한다.

Tool은 T01 whole-tree 불변을 먼저 검사하고 validated temporary tar file로 tracked archive를 만든다. Archive digest와 member path·type·mode를 검사하고 path traversal·link escape 없이 non-existing destination에 추출한 뒤 canonical extracted manifest를 다시 확인하고 원자 게시한다. 재실행의 complete exact destination은 write 0으로 채택하고 partial·extra·missing·mismatch destination은 overwrite·delete·repair 없이 중단한다. Crash test는 rename 전·직후·receipt 직전 경계를 포함한다. 이후 새 repo에서만 patch한다. Patch 1은 실행 전 candidate inventory, versioned machine report, full mode와 manifest write 금지, patch 2는 argv vector, nonce가 있는 `clojure.test/report` adapter, timeout·runtime raw 상태와 control·replay, patch 3은 source·test byte copy, coverage refresh fail-closed, safe reader와 process tree cleanup만 담당한다. Mutation rule source digest가 바뀌면 검사가 실패한다.

먼저 synthetic `upstream-patch-verifier-test`를 다시 실행하면서 verifier를 최소 구현해 GREEN으로 만든다. Verifier는 lock에 고정된 pristine archive SHA-256과 ordered exact patch filename·SHA-256을 확인하고 owner-only temporary directory에 안전 추출한 뒤 순서대로 patch를 적용한다. 적용 전·후 mutation rule path set과 각 bytes digest가 같아야 한다. 마지막에는 재구성한 tree와 committed `third_party/clj-mutate` 전체를 path·type·POSIX mode·file bytes 또는 symlink target 단위로 exact 비교한다. Missing·extra·reordered patch, wrong archive, apply failure, mutation rule 변경과 resulting tree 불일치는 companion 실행 0에서 nonzero다. Synthetic oracle이 GREEN이 된 뒤에만 실제 pristine archive·세 patch·vendored tree를 같은 verifier로 검사한다.

Admission test는 mock adapter가 아니라 실제 `clj-mutate` companion entrypoint를 all-killed, survivor, timeout, coverage-failure tiny project 각각에 argv로 실행한다. Companion의 선행 candidate ID·operator·source inventory와 raw outcome를 고정 raw fixture에 대조하고 root normalizer의 canonical record를 expected canonical fixture와 byte 단위로 대조한다. Process exit 0이나 human summary만 신뢰하거나 actual companion을 호출하지 않은 mock-only test는 admission 통과로 인정하지 않는다.

`native-fs` namespace는 T21에서 JNA 5.17.0·packaged dispatch digest·owner-only extraction을 검증한 `jna-native-loader`로만 pinned glibc syscall boundary를 호출한다. Trusted root directory FD에서 `openat2`의 beneath·no-symlink·no-magic-link, fallback 없는 `openat(O_NOFOLLOW)`, opened object `fstat`의 device·inode·link count·mode, `renameat2(RENAME_NOREPLACE)`, `unlinkat`, byte-range `fcntl`을 descriptor-relative로 제공한다. JNA JAR와 packaged Linux x86_64 native dispatch bytes는 `dependency-lock.json` digest와 일치해야 하고 owner-only temporary extraction root 밖 system JNA load를 금지한다. Kernel·glibc ABI와 syscall probe가 `supportedOS`에 맞지 않거나 public JDK filesystem API만으로 대체되면 dependencyError다.

`:fail`이 typed assertion 근거이고 `:error`, runner exception, timeout, 일반 nonzero는 killed가 아니다. Strict mode는 Speclj human output, whitespace command split, cache와 이전 coverage에 의존하지 않는다.

Patched companion의 active classpath에 필요한 Maven dependency와 transitive JAR까지 `dependency-lock.json` exact set을 재생성한다. Upstream의 사용하지 않는 Git dependency alias는 vendored execution·report boundary와 active profile에서 제외하고 tools.deps Git fetch count를 0으로 검증한다. 변경 직후 단계 0B와 같은 sealed `-Srepro`, synthetic home·config·Maven repository 조건에서 `/usr/bin/bash scripts/verify-dependencies.sh --populate` 한 번만 network를 허용해 isolated cache를 채운다. 이후 coordinate·repository·size·SHA-256을 대조하고 모든 Clojure command를 `--offline`으로 실행하며 extra·missing artifact를 거부한다.

- [ ] **단계 4: bridge·snapshot·gate 통과 확인**

실행: `/usr/bin/bash scripts/verify-upstream-patches.sh clj-mutate`

실행: `/usr/bin/bash scripts/verify-dependencies.sh && scripts/clojure.sh --offline -M:test --include-id runner-mutation`

기대: 네 tiny project의 actual companion candidate·operator·raw outcome와 canonical normalized record가 고정 fixture와 정확히 일치, doctor admitted backend 성공과 변조의 무부작용 실패, candidate/result exact set, 9개 상태와 unknown, coverage refresh 실패, symlink 0, source 불변, all-killed 1개 이상만 exit 0. SIGKILL orphan은 valid HMAC tree-drained marker+age-expired일 때만 quarantine·delete하고 marker missing·guardian crash는 영구 no-touch다. PID reuse process에는 signal 0이며 공용 evidence·finding·history·export·default artifact·diagnostic raw canary 0, catchable 또는 valid-marker cleanup 뒤 sandbox raw 0이다. `multi-file`의 첫·마지막 file candidate가 모두 합산되고 하나를 생략하면 backendError

- [ ] **단계 5: commit**

```bash
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py materialize-exact --repository . --task T23 --phase mutation-admission --base-head <T22_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --source test/fixtures/commit/t23-files.json --selector mutation-admission --output <workspace>/build/commit-inventory/T23/SENTINEL_CLJ/mutation-admission/stage.paths
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py stage-exact --repository . --task T23 --phase mutation-admission --base-head <T22_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --manifest <workspace>/build/commit-inventory/T23/SENTINEL_CLJ/mutation-admission/stage.paths
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py commit-prepared --repository . --task T23 --phase mutation-admission --prepared-receipt <PREPARED_RECEIPT> --prepared-receipt-sha256 <PREPARED_RECEIPT_SHA256> --base-head <T22_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --expected-message "feat: add typed Clojure mutation bridge (요구사항-22..32,41,43)"
```

### T24: SENTINEL_CLJ evidence·history·privacy와 전체 command

**충족 요구사항:** 요구사항-06..요구사항-08, 요구사항-28, 요구사항-29, 요구사항-32, 요구사항-41, 요구사항-42, 요구사항-45..요구사항-54

**파일:**

- 생성: `src/sentinel_clj/evidence/{models,privacy,lock,commit_sequence,store}.clj`
- 생성: `src/sentinel_clj/history/{service,retention,export,resolver}.clj`
- 생성: `scripts/run-e2e-fixture.sh`, `test/fixtures/projects/{clojure-pass,clojure-history}/**`
- 테스트: evidence·history unit, `commit-sequence-test`, project-key-rotation, cross-process·crash integration, check·history·privacy acceptance namespace, `test/fixtures/test-inventory/evidence-history.edn`
- 생성: `docs/privacy.md`
- 수정: `test/sentinel_clj/test_runner.clj`, `src/sentinel_clj/workspace/native_fs.clj`, `src/sentinel_clj/{cli,orchestrator}.clj`, `README.md`, `docs/index.md`, `docs/operations.md`, `docs/log.md`

**받는 것:** T22 CRAP, T23 mutation과 `SandboxLease`, T03 evidence·sandbox-lease golden

**주는 것:** 완성된 `sentinel-clj` 5개 command와 POSIX-compatible immutable history

이 task의 completed와 incomplete prune은 T03 `retention-marker-first-v1`을 그대로 구현한다. 두 kind 모두 marker directory sync 전 selected bundle delete는 0이다. Completed는 각 marker의 `(commitSequence <= sequenceHighWaterAtCommit && committedAtUtc < cutoffUtc)` pair union만 적용하고 marker 뒤 더 큰 sequence run을 소급 숨기지 않는다. Incomplete는 marker의 sorted immutable selection subset만 resume하며 신규 eligible run과 선택 뒤 completed가 된 run을 삭제하지 않는다. 나머지도 stored started·lease·tree-drained digest와 HMAC join을 다시 증명한 경우만 descriptor-relative delete한다.

- [ ] **단계 1: concurrent commit·retention·privacy 실패 test 작성**

`evidence-history.edn`에 이 task의 namespace·test-var expected ID를 exact 등록하고 `test_runner.clj`에는 `evidence-history` selector만 먼저 연결한다. Test infrastructure 실패나 expected ID 0개는 production RED로 인정하지 않는다.

```clojure
(deftest cache-replay-does-not-increment-observation
  (let [view (fold-fixture "fresh-then-cache")]
    (is (= 1 (:observation-count view)))
    (is (false? (:repeated view)))))

(deftest sequence-allocation-crash-leaves-a-gap
  (let [result (sequence-fault-fixture "crash-after-sequence-sync")]
    (is (= (inc (:crashed-sequence result)) (:next-completed-sequence result)))))
```

- [ ] **단계 2: 실패 확인**

실행: `scripts/clojure.sh --offline -M:test --include-id evidence-history`

기대: evidence·history namespace 부재로 실패

- [ ] **단계 3: Clojure JDK interop store와 offline history 구현**

Clojure namespace가 pinned JNA의 trusted root FD, `openat2`·`openat(O_NOFOLLOW)`, opened-object `fstat`, `renameat2`·`unlinkat`와 libc `fcntl`을 호출하며 first-party Java·C source는 만들지 않는다. Python·TypeScript·Go lock과 pairwise 상호 운용 시험이 실패하면 Clojure release를 차단한다. Event와 evidence는 sync·atomic rename·directory sync 순서를 지키고, concurrent terminal commit은 lock 안에서 prior completed runs를 다시 읽는다. Persistent evidence는 실제 resolved config 우선순위·digest, scope·target·mutation domain, clj-mutate commit·archive·patch identity, operator·exclusion inventory와 bridge·runner version을 privacy-safe field로 기록한다. Retention marker와 completed·incomplete cutoff는 SPEC golden과 byte 단위로 일치한다. Public export와 default artifact에 raw report·path·symbol·source·environment value를 넣지 않는다.

T21 `project-key-provider` output은 T03 규칙대로 첫 quality run의 project state initialize 또는 exact next-epoch atomic rotation에만 적용한다. Same key·epoch 재실행은 write 0이고 invalid epoch·key 조합은 started·child 호출 0이다. Temporary create·file sync·rename·directory sync fault와 retry에서 old 또는 new complete `project.json`만 허용한다. Help·doctor·history는 envelope option을 거부하고 state create·rotate 0이다.

`commit-sequence` namespace는 T03 schema·derived HMAC·retention high-water floor를 그대로 구현한다. Store는 exclusive lock 안에서 next sequence file을 durable commit한 뒤에만 같은 sequence의 event와 evidence를 쓰며 allocation crash gap을 재사용하지 않는다. History는 UTC가 아니라 sequence로 fold하고 invalid·duplicate·rollback에서 exit 7, 추가 write·delete 0이다.

`history prune --incomplete`는 T23의 동일 `SandboxLease` parser와 HMAC tree-drained marker oracle을 호출해 runId·projectToken·lease generation·guardian identity를 join한다. Marker missing·HMAC mismatch·guardian crash·corrupt lease와 외부 guardian start 전임을 증명하지 못한 missing lease는 incomplete run을 영구 보존한다. Valid marker, `startedAtUtc < cutoffUtc`, completed evidence 부재가 모두 맞을 때만 whole incomplete bundle을 descriptor-relative로 삭제하고 cutoff equality를 보존한다. Sandbox quarantine은 별도 `mayQuarantineSandbox=validMarker+ageExpired`만 사용한다.

`run-e2e-fixture.sh`는 고정 fixture 이름 allowlist만 받고 validated `mktemp -d`의 owner-only project copy에서 actual CLI를 실행한 뒤 EXIT·INT·TERM cleanup과 원 checked-in fixture whole manifest 불변을 확인한다. Checked-in project에서 `.sentinel`을 직접 만들지 않는다.

- [ ] **단계 4: Clojure end-to-end 통과 확인**

실행: `scripts/clojure.sh --offline -M:test --include-id evidence-history`

실행: `/usr/bin/bash scripts/run-e2e-fixture.sh clojure-pass check --format json`

실행: `/usr/bin/bash scripts/run-e2e-fixture.sh clojure-history history --repeated --format json`

기대: 5개 command, offline repeated history, lock 경합, crash recovery, privacy canary 0건, local resolver write 0, stable stdin key의 같은 epoch repeated와 exact next-epoch 분리·atomic rotation, child key byte 0. Incomplete run은 marker missing·guardian crash·cutoff equality를 보존하고 valid tree-drained marker+started-before-cutoff+completed 없음만 whole run 삭제하며 sandbox는 valid marker+cleanup-age-expired만 quarantine

- [ ] **단계 4A: Clojure 전체 회귀 확인**

실행: `/usr/bin/bash scripts/verify-dependencies.sh && scripts/clojure.sh --offline -M:test`

기대: foundation, CRAP, runner·mutation, evidence·history 네 layer의 사람이 고정한 expected namespace·test-var ID가 실제 load·started·terminal ID와 정확히 같고 각 layer 실행 수가 1개 이상이다. Unit·integration·acceptance 전체가 통과하고 cache·resolver·network 호출은 0이다. 한 layer나 test ID가 누락·추가·중복되거나 실행 수가 0이면 commit 전에 nonzero로 실패한다.

- [ ] **단계 5: commit**

```bash
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py prepare-and-stage --repository . --task T24 --phase evidence --base-head <T24_BASE_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --output-root <workspace>/build/commit-inventory -- src scripts/run-e2e-fixture.sh test README.md docs
<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py commit-prepared --repository . --task T24 --phase evidence --prepared-receipt <PREPARED_RECEIPT> --prepared-receipt-sha256 <PREPARED_RECEIPT_SHA256> --base-head <T24_BASE_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --expected-message "feat: complete Clojure evidence and history commands (요구사항-06..08,28,29,42,45..54)"
```

### T25: 5개 runtime 공통 conformance와 polyglot acceptance

**충족 요구사항:** 요구사항-03..요구사항-08, 요구사항-19, 요구사항-20, 요구사항-32, 요구사항-33, 요구사항-38, 요구사항-42..요구사항-55

**파일:**

- 생성: `SENTINEL_SPEC/tools/run_cross_runtime.py`
- 생성: `tests/conftest.py`, `tests/{test_cross_runtime,test_text_json_equivalence,test_cross_runtime_lock,test_cross_runtime_sandbox_lease,test_state_contract_matrix,test_clean_install,test_polyglot_routing}.py`, `tests/contracts/{runtime-registry.schema.json,fault-harness-registry.schema.json,fault-harness-request.schema.json,fault-harness-response.schema.json,conformance-receipt.schema.json,t25-commit-seal.schema.json}`
- 생성: `SENTINEL_PY/tests/conformance/{test_contract.py,fault_harness.py}`, `tests/clean_install/test_clean_install.py`, `scripts/build-release.py`
- 생성: `SENTINEL_TS/test/conformance/{contract.test.ts,fault-harness.ts}`, `test/clean_install/clean-install.test.ts`, `scripts/build-release.mjs`
- 생성: `SENTINEL_GO/internal/conformance/conformance_test.go`, `internal/cleaninstall/clean_install_test.go`, `testdata/fault_harness/main.go`, `scripts/build-release.sh`
- 생성: `SENTINEL_JAVA/src/test/java/io/github/hwainhwang/sentinel/conformance/{ConformanceTest,FaultHarnessMain}.java`, `src/test/java/io/github/hwainhwang/sentinel/cleaninstall/CleanInstallTest.java`, `scripts/build-release.sh`
- 생성: `SENTINEL_CLJ/test/sentinel_clj/conformance/{contract_test,fault_harness}.clj`, `test/sentinel_clj/clean_install_test.clj`, `scripts/build-release.sh`
- 생성: `SENTINEL_GO/test-inventory/conformance.json`, `SENTINEL_JAVA/src/test/resources/test-inventory/conformance.json`, `SENTINEL_CLJ/test/fixtures/test-inventory/conformance.edn`
- 생성: VCS 밖 owner-only `build/t25/{attempt.lock,attempt-sequence.json}`, `build/t25/attempts/<20-digit-sequence>/{attempt,runtime-registry,fault-harness-registry,oci-executor-session,conformance-receipt,t25-commit-seal}.json`, `build/t25/attempts/<20-digit-sequence>/{artifacts,install,fault-harness,runtime-roots,project-workspaces,stage}/`
- 생성: `SENTINEL_GO/scripts/build-release.sh`, `SENTINEL_CLJ/build.clj`
- 수정: `SENTINEL_PY/{pyproject.toml,uv.lock}`, `SENTINEL_TS/{package.json,package-lock.json}`, `SENTINEL_JAVA/{pom.xml,dependency-lock.json}`, `SENTINEL_CLJ/{deps.edn,dependency-lock.json,bin/sentinel-clj}`
- 수정: 6개 `README.md`, 6개 `docs/log.md`

**받는 것:** T08, T12, T16, T20, T24의 완성 CLI와 T04에서 manifest에 고정한 SPEC RC, 여섯 project fixture, 공통 acceptance vector와 harness 계약, T01의 exact OCI executor lock

**주는 것:** 같은 입력이 5개 runtime에서 같은 schema·상태·exit·이력·lock 의미를 갖는다는 독립 검증, source tree 밖 clean install과 module별 polyglot routing을 봉인한 `conformance-receipt.json`

`run_cross_runtime.py new-attempt`는 `build/t25/attempt.lock`의 cross-process lock 안에서 `attempt-sequence.json`을 1 증가시키고 zero-padded 20자리의 새 `attempts/<sequence>/`를 mode `0700` no-replace로 만든다. Sequence file의 exact shape는 `{"version":"sentinel-t25-attempt-sequence-v1","lastAllocated":"<uint64>"}`다. 각 child repo의 source manifest는 `git ls-files -z --cached --others --exclude-standard`의 concrete path마다 repository-relative path, Git mode, working bytes SHA-256을 UTF-8 byte order로 canonical화한다. Special file, path escape, LF·NUL과 scan 중 변경은 거부한다. `attempt.json`은 `version="sentinel-t25-attempt-v1"`, sequence, absolute root, sorted six `{repository,head,sourceManifestSha256}`, SPEC manifest digest, clean-install executor lock digest, `parentT27AttemptSha256`과 canonical input SHA-256을 담고 file·directory sync한다. 독립 T25 실행은 parent field가 exact JSON null이고, T27이 요구한 fresh child 실행만 64 lowercase hex를 넣는다. 모든 object는 `additionalProperties=false`이고 canonical JSON+final LF다. Allocator는 high-water rollback·overflow·path escape·unknown field를 거부하고, durable write 뒤 stdout에 `{"version":"sentinel-attempt-allocation-v1","sequence":"<20 digits>","attemptRecord":"<absolute attempt.json>","attemptSha256":"<64 hex>"}` 한 줄만 쓴다. 이후 모든 command는 이 direct immutable path와 digest를 검증해 사용하며 recent/current pointer를 만들거나 다시 읽지 않는다. 이전 attempt는 수정·삭제·재사용하지 않고 partial failure 뒤에는 새 attempt를 할당한다.

두 registry는 `additionalProperties=false`인 canonical JSON이다. Runtime registry exact body는 `version="sentinel-runtime-registry-v1"`, attempt record digest, sorted six source `{repository,head}`, sorted five `{runtime,argv,artifactSha256,companionSha256,toolchainLockSha256}`와 `registryDigest`다. Fault registry는 `version="sentinel-fault-harness-registry-v1"`, attempt record digest, sorted five `{runtime,argv,sourceSha256}`, request·response schema digest와 `registryDigest`다. `argv`는 non-empty string array이며 `argv[0]`만 validated absolute executable이고 나머지는 NUL·newline이 없는 bounded literal argument다. Digest는 lowercase 64-hex다. `registryDigest`는 그 field를 제외한 canonical body digest다. Request와 response는 version·case ID·runtime·typed input 또는 typed outcome만 허용하고 production result를 직접 주입하는 field, raw secret, absolute project source path를 금지한다. 네 test-only schema는 T25 commit에 고정되며 T04 release manifest를 바꾸지 않는다.

- [ ] **단계 1: runtime 차이를 드러내는 실패 test 작성**

`test_cross_runtime.py`는 현실적인 small fixture를 5개 installed CLI argv로 실행해 canonical JSON을 schema·semantic oracle로 검증하고, 언어 고유 field를 제외한 terminal status, exit code, mutation counts, CRAP exact fraction, finding lifecycle을 비교한다. `test_text_json_equivalence.py`는 같은 actual run의 text와 JSON 핵심 수치를 비교한다. 실제 source에서 만들기 비현실적인 count `2^53-1`·`2^53`·`2^53+1`, 80-digit CRAP numerator·48-digit denominator와 극단 strict kill-rate fraction은 production registry CLI에 synthetic input option을 추가하지 않는다. 대신 별도 fault-harness registry의 test-source adapter가 canonical raw-result fixture를 각 runtime의 production parser, semantic gate와 text·JSON renderer에 직접 통과시킨다. `2^53-1`은 exact 통과하고 그 이상 count는 parse·gate 전에 같은 contract error여야 하며, 큰 fraction은 leading-zero 없는 string으로 같은 byte를 내고 text도 그 exact fraction에서만 계산한다. Adapter가 result를 직접 꾸미거나 production parser·gate·renderer를 우회하면 실패한다. TypeScript bigint serialization throw나 number precision loss도 실패다. `test_polyglot_routing.py`는 같은 Python·TypeScript 저장소에서 module별 production·test command가 섞이지 않는지 확인한다.

`tests/conftest.py`의 `pytest_addoption`은 `--runtime-registry`, `--fault-harness-registry`, `--registry-record` 세 absolute path option을 global `required=True` 없이 등록한다. 앞의 두 path를 함께 주는 mode와 immutable direct `attempt.json` 하나를 주는 mode는 상호 배타다. T02·T03·T04·T26처럼 T25 test를 선택하지 않은 기존 pytest command는 이 option 없이 그대로 실행돼야 한다. T25 test module만 공용 session fixture를 request하고 필요한 mode를 검사한다. Fixture는 registry 또는 attempt record가 current immutable attempt root 아래 current UID owner의 mode `0600`, link count 1인 non-symlink regular file인지 descriptor로 확인하고 canonical JSON을 읽는다. 각 registry의 `registryDigest`는 그 field를 제외한 canonical body SHA-256과 같아야 하며 expected entry set·absolute installed 또는 test-source argv·artifact/source digest를 모두 검증한 뒤 immutable parsed value를 test에 준다. Missing·relative·`..`·path swap, wrong owner·mode·type·digest와 extra entry는 runtime invocation 0에서 T25 fixture error다. Registry preflight RED와 semantic conformance characterization은 단계 2에서 별도 selector·receipt로 실행해 한 결과가 다른 결과를 가리지 못하게 한다.

`test_state_contract_matrix.py`는 두 실행층으로 다음을 먼저 실패시킨다. 외부에서 결정적으로 만들 수 있는 정상·오류·signal·동시성·path attack은 T25 registry의 실제 설치 CLI subprocess를 사용한다. CSPRNG·HMAC 실패, file·directory sync와 rename 경계 실패, descriptor 검증 직후 swap, clock 경계, project-key 입력과 child spawn 실패처럼 외부 process에서 안정적으로 만들 수 없는 내부 fault는 각 runtime의 실제 CLI entry를 in-process로 호출하되 production `Entropy`, `HmacSha256`, `FileOps`, `Clock`, `ProjectKeyProvider`, `Process` dependency boundary에 test implementation을 constructor로 주입한다. 이 boundary는 T05·T09·T13·T17·T21에서 production path의 모든 해당 operation을 통과시키고 기본 implementation만 OS·표준 crypto를 호출한다. CLI option·environment·config로 test implementation을 고르는 경로는 없으며 test implementation은 test source root에만 존재한다. Packaging test는 release asset·runtime import graph·registry에 test implementation 이름과 byte digest가 0개인지 확인한다. In-process fault case도 parser·orchestrator·gate·evidence production code를 그대로 실행해야 하며 결과 객체를 직접 만든 mock-only test는 인정하지 않는다.

- `--help`는 project 유무와 관계없이 project 탐색·source/history read·write, child process, test·coverage·backend와 network 호출이 모두 0이다. 실행 전후 protected project whole-tree manifest도 같고 stdout·exit 0만 생긴다.
- exit 0..8을 각각 실제 CLI로 만들고 precedence를 검증한다. `crap`, `mutation`, `check` 세 품질 command 각각이 새 runId를 만들고, `check`의 CRAP·mutation component는 그 한 runId 안에 있어야 한다. 각 command에 적용 가능한 success, qualityFailed, baselineFailed, toolError, backendError, evidenceError, cancelled와 catch 불가능 crash의 started-only를 직접 실행한다. Project를 찾기 전 usageConfigError는 state·evidence write 0이고 project start 뒤 catch 가능한 terminal·cancelled는 같은 runId의 terminal bundle이어야 한다.
- malformed·missing·stale·ambiguous coverage와 parser invariant의 서로 다른 종료 코드
- 빈 production, 일부 file만 명시한 축소 glob, production을 test·generated·vendor로 오분류한 config, overlap·unclassified source는 test·coverage·candidate·mutant 실행 0에서 usageConfigError다.
- output·coverage·raw·export·prune·`localCacheDir` target 각각에 symlink, hardlink, descriptor 확인 뒤 path swap과 protected-path overlap을 주입한다. `--output`과 export의 기존 regular file, `--raw-dir`의 기존 directory·file, 모든 temporary target의 기존 path는 type·내용과 무관하게 create·write·rename 0으로 거부하고 기존 bytes를 보존한다. Non-existing target의 absence check 직후 attacker가 같은 이름을 만드는 race에서도 final publish는 validated parent FD의 `renameat2(RENAME_NOREPLACE)`로 `EEXIST`를 받고 attacker bytes·identity를 보존한다. Coverage report만 선언된 generated-output root 안에서 validated prior regular file을 atomic replacement할 수 있으며 그 밖의 output과 섞지 않는다. 실제 open·rename·delete가 validated descriptor identity를 벗어나면 실패하고, atomic rename·directory sync 의미를 증명하지 못한 filesystem에서는 외부 command·write·delete 0의 dependencyError다.
- distinct nonce baseline 2회 중 하나의 failure·test ID mismatch에서 coverage·candidate·mutant 실행 0
- Native test root에 file 2개·test ID 2개 이상이 있는 fixture에서 configured command가 file 하나 또는 ID 하나만 선택하면 baselineFailed이고 coverage·candidate·mutant 실행은 0이다. Python pytest와 TypeScript Vitest는 native file inventory·full collection·started·terminal exact join을, Go는 static Test·Example·Fuzz inventory를, Java·Clojure는 fixed expected ID inventory를 사용하며 0·missing·extra·duplicate를 모두 거부한다.
- 각 runtime의 `prepareCommand` 뒤 disposable snapshot에서 native source discovery와 scope classification을 다시 실행한다. 선언된 generated root 안 file만 늘어난 경우는 허용하지만 새 production 또는 unclassified `.py`, `.ts`·`.tsx`, `.go`, `.java`, `.clj`·`.cljc`가 생기거나 pre/post production inventory exact join이 깨지면 baseline 전에 terminal bundle을 남기는 `toolError` exit 1이고 candidate·mutant 실행은 0이다. `started.json` 뒤 실패를 evidence 없는 `usageConfigError`로 낮추면 실패한다.
- candidate와 fresh coverage join에서 count 0은 uncovered, mapping 누락·모호함·backend raw coverage 충돌은 backendError이며 후자의 mutant 실행은 0이다.
- `doctor`의 runtime·dependency·vendored SPEC checksum·backend artifact·version·config·scope mismatch 진단은 test·coverage·mutation·state write가 모두 0이다. 실행 전후 protected source·test·config와 기존 `.sentinel` tree의 path·type·mode·content manifest도 byte 단위로 같다.
- Go test inventory는 `_test.go`를 정적으로 분석한 package와 runnable Test·Example·Fuzz exact ID set을 사람이 작성한 manifest와 대조하고, pinned `go test -json -count=1`의 started·terminal ID set과 다시 exact join한다. Unit·integration·acceptance는 expected와 실제 실행이 각각 1개 이상이어야 하며 0개·누락·추가·중복·terminal 누락이 하나라도 있으면 해당 runtime conformance를 실패시킨다.
- `check`는 CRAP이 qualityFailed여도 mutation을 실행해 같은 runId의 두 component 결과를 보존한다. Shared config invalid와 cancelled만 아직 시작하지 않은 component를 중단하며 fail-fast 구현은 거부한다.
- CLI override > project config > SPEC default와 evidence config digest 변화를 검증한다. 같은 environment 이름·source의 resolved secret value만 바꿔도 raw value는 어느 byte에도 남지 않으면서 keyed config·context digest가 바뀌어야 하고 ambient environment override는 0이다.
- HMAC project-key injection 변수와 raw key canary를 prepare·test·coverage·candidate generation·mutation backend spy child 각각의 captured argv, environment와 stdin에서 찾으면 0건이어야 한다. 이 internal key 변수는 project child environment allowlist와 environment-contract digest canonical input에도 없어야 하며, spy 결과가 하나라도 누락되면 test를 통과시키지 않는다.
- 다섯 runtime fault harness가 real guardian과 gate-wrapper child로 T03 `sandbox-start-gate-v1`을 실행한다. Guardian의 `PR_SET_CHILD_SUBREAPER`, `pipe2(O_CLOEXEC)` 뒤 designated read FD만 `posix_spawn dup2` 또는 동등한 explicit pass-fd로 wrapper에 남고 guardian write end·원 read end·다른 copy는 상속 0인지 syscall trace로 검사한다. Guardian·wrapper identity 전달, lease write, file sync, directory sync, controller ACK와 guardian GO write·write-end close 전후 각 경계에서 controller SIGKILL, guardian SIGKILL 또는 production facade fault를 주입한다. ACK 전 controller crash는 guardian이 command socket EOF를 보고 GO 없이 wrapper를 reap해야 한다. GO 전 모든 case는 wrapper가 EOF-only·wrong·short·extra·read error·timeout을 success로 보지 않고 60초 이내 self-exit하며 sandbox open·chdir, test·coverage·backend spy invocation이 0이다. 별도 helper process에 write FD를 고의로 leak하면 EOF가 오지 않아 timeout 실패하고 backend는 실행 0이어야 한다. GO가 관찰된 case는 그 전에 exact durable lease가 있어야 하며 wrapper는 정확히 `0x47` 뒤 EOF를 확인하고 gate FD를 닫은 뒤에만 backend를 exec한다. GO 없이 backend가 실행되거나 durable lease 전 GO가 trace에 나타나면 해당 runtime release를 차단한다.
- backend version·artifact·bridge patch·raw state-map·coverage matcher·operator inventory·exclusion·scope 변경이 backend lock, evidence digest와 compatibility partition을 바꾸고 무단 제외는 strict 실패
- Pinned mutmut 또는 선택 Cosmic Ray와 Stryker schema에서 inventory·coverage·execution을 줄일 수 있는 field를 하나씩 활성화하는 table을 실제 CLI preflight에 넣는다. Python의 only/path/do-not-mutate·regex·pragma·covered-lines channel과 TypeScript의 mutate glob·excluded mutation·ignore comment·ignorer plugin을 포함하며, native backend config 자동 load, unknown option·plugin·environment override와 unclassified schema key는 candidate·mutant 실행 0에서 backendError다. Bridge가 보고한 exclusion inventory와 source·resolved config scan이 exact join하지 않아도 실패한다.
- Go·Java·Clojure `multi-file`의 production 첫·마지막 file candidate가 한 plan에 모두 있고 per-file count·digest 합계가 맞아야 한다. 한 file을 건너뛰면 backendError이고 partial score를 만들지 않는다.
- 서로 다른 runId와 같은 correlationId의 fail·fix·pass 3회, started-only incomplete와 lifecycle 4상태
- 같은 findingToken에 occurrence·context·family가 exactly once이고 missing·duplicate·token collision은 evidenceError
- 5개 runtime 각각에서 fingerprint value가 같아도 kind가 occurrence·context로 다르거나 version이 v1·v2로 다르면 별도 repeated key다. 각 partition의 observationCount는 1, `repeated=false`이고 kind+version+value가 모두 같은 completed fresh run만 count를 합친다.
- 5개 runtime 모두 whitespace·line insert, anonymous node reorder와 backend ID renumber 뒤 occurrence가 유지된다. Backend version·config 변경은 context만 바꾸고, defect kind·operator category 변경은 family와 해당 occurrence를 바꾸며, duplicate descriptor는 `identityAmbiguous`와 fingerprint 0개로 fail-closed한다. 같은 language·finding class·defect kind·operator category를 서로 다른 project key·module·path·runId로 만들면 family는 같고 occurrence·context만 달라야 하며 family canonical input에 project 식별값이 있으면 실패한다.
- 5개 runtime은 `sentinel-fingerprint-json-v1` logical input의 key permutation, quote·slash·backslash·NUL·newline, Korean·astral scalar, composed·decomposed Unicode를 expected canonical UTF-8 hex와 synthetic-key HMAC/SHA-256 expected hex에 대조한다. Composed·decomposed를 normalize하거나 `/`를 escape하고, map iteration·locale에 따라 key order가 바뀌거나 invalid surrogate·UTF-8·duplicate key를 받아들이면 실패한다. Canonical input byte와 digest가 모든 runtime에서 exact 같아야 한다.
- 실제 failure 분류는 CRAP 초과 `projectCode`, survived·uncovered `projectTest`, deterministic baseline·timeout ambiguity `projectCodeOrTest`, malformed backend `backend`, SENTINEL invariant `sentinel`, dependency·config·flaky `environment`로 일치해야 한다. Stack·message 문자열 추측으로 분류하면 실패한다.
- 같은 occurrence의 두 runtime process가 동시에 terminal commit하면 exclusive lock 안 재조회 결과 event는 정확히 detected 1개와 persisted 1개이고 event prefix·manifest가 불변이어야 한다.
- Long-running spy test·mutation child가 terminal 전 대기하는 동안 plain history shared read가 bounded time 안 끝나고 두 번째 quality process도 자기 started와 외부 품질 작업까지 진행해야 한다. Project-wide exclusive lock을 command 전체 동안 잡아 직렬화하는 구현은 실패한다. 별도 process가 commit byte-range lock을 잡은 상태에서 acquire deadline을 넘기면 무한 대기하지 않고 exit 7 evidenceError이며 partial terminal write는 0이다.
- 5개 runtime의 injected Clock에서 `utcNow`를 timeout 도중 과거·미래로 jump시키고 `monotonicNow`만 정상 진행시킨다. Test·mutant·process cleanup과 fcntl acquire deadline은 monotonic budget 안에서 bounded 종료하며 UTC jump로 짧아지거나 늘어나지 않아야 한다. 반대로 evidence timestamp와 retention `committedAtUtc`·`startedAtUtc` cutoff는 injected UTC만 사용하고 monotonic 값을 직렬화하면 실패한다. Production timeout·lock code가 Clock facade 밖의 wall·monotonic API를 직접 호출하는 경로도 static inventory 0이어야 한다.
- 빈 state에서 같은 runtime·동일 입력의 두 process와 5개 runtime의 모든 pair를 각각 동시에 시작한다. `project.json` exclusive-create winner는 정확히 1개이고 loser는 winner bytes를 descriptor로 다시 읽어 같은 project identity·key epoch를 사용해야 한다. 같은 runtime·동일 입력일 때만 module·occurrence token도 같아야 한다. 서로 다른 runtime pair는 winner key와 자기 language·module·semantic site canonical input으로 다시 계산한 각자의 expected token과 일치해야 한다. Partial temporary file은 0개이며 loser가 자기 project identity를 덮어쓰면 evidenceError다.
- 5개 runtime 각각 OS CSPRNG로 exact 128-bit project identifier, 256-bit fingerprint HMAC key와 별도 256-bit cleanupLeaseKey를 만들고 fresh project root 두 곳에서 세 값이 project 내부에서도 서로 다르며 두 project 사이에서도 모두 달라야 한다. Constant, time·PID seed와 일반 PRNG는 금지한다. Entropy source가 세 draw 각각에서 실패하는 경우를 주입하면 test·coverage·candidate·backend 호출 0, exit 7 evidenceError이고 partial `project.json`은 0개다. Fingerprint key를 exact next epoch로 rotate한 뒤에는 project identifier와 cleanupLeaseKey byte, projectToken이 이전과 같고 fingerprint key·epoch만 달라야 한다. 이 생성·회전 불변식은 T08·T12·T16·T20·T24의 각 runtime evidence acceptance에서도 동일하게 고정한다.
- Local·partial, cancelled, incomplete·corrupt, baseline·dependency·backend·tool·evidence error와 backend domain·operator·scope가 non-comparable한 run은 기존 active finding을 resolved로 바꾸지 않고 event prefix·active 상태가 그대로여야 한다. CRAP analyzer semantic version·coverage basis와 mutation backend version·raw-state-map·coverage-matcher·operator inventory·exclusion·scope 차원을 하나씩만 바꾼 fresh run도 각각 새 compatibility partition이며 이전 active finding을 resolved로 바꾸지 않는다.
- 기존 active production site가 이후 test·generated·vendor·build-output 또는 unclassified로 재분류되면 이전 finding은 active로 유지되고 새 privacy-safe `scopeRegression` event가 기록된다. 단순 config invalid로 old finding을 resolved 처리하거나 event 없이 숨기면 실패한다.
- `--local --reuse` cache replay observation 0, default local 보존 0, strict cache read 0을 검증한다. Cache result는 `observationSource=cache`, 정확한 fresh `sourceRunId`, source result digest와 cache-key identity를 모두 가져야 한다. Source는 `observationSource=fresh`인 completed·successful local run이고 exact key·scope·digest와 join해야 한다. Provenance field missing·mismatch, incomplete·non-success source, cache replay를 다시 source로 삼는 경우와 key·scope·digest mismatch는 replay를 거부한다. Source·test·config·backend·operator·runtime·SPEC digest 각 key 차원을 하나씩 바꾸면 miss이고, tampered manifest는 거부한다. Backend가 original cache를 직접 read·write하면 canary가 실패하며 verified cache copy는 disposable snapshot 안에서만 사용한다. Atomic cache update crash 뒤 기존 cache byte는 불변이다.
- `--local --scope changed`의 `certification:false`, 기존 strict evidence byte·active finding 불변
- raw report default 0, `--raw-dir` opt-in owner-only, common state·export·artifact에 raw byte 0
- `--local-details --format jsonl`은 privacy-safe token을 현재 locator로만 풀고 stdout 각 line이 local-detail schema JSON object여야 한다. 5개 runtime 모두 source·test·config·`.sentinel`·output whole manifest가 실행 전후 같고 source 원문 출력, child process, network와 state·artifact write는 0이다.
- `history --export`는 network 0, allowlist-only다. Existing target은 regular file·directory·symlink를 모두 owner-only temporary create 이전에 거부하고 write·rename 0, old bytes 불변이다. Non-existing target에만 owner-only temporary exclusive-create·write·file-sync, validated parent FD의 `renameat2(RENAME_NOREPLACE)`, parent-directory sync 각 failure와 crash를 주입한다. 사전 absence 확인과 final rename 사이에 attacker가 target regular file·directory·symlink를 만드는 race는 `EEXIST`로 실패하고 attacker bytes·identity, 기존 quality evidence·판정은 불변이다. Rename 전 실패는 target 부재 또는 attacker target을 유지하고, rename 뒤 directory sync 실패·crash는 target 부재 또는 완전한 새 canonical export 중 하나만 허용하며 partial·mixed bytes는 0이다. 위험한 rollback overwrite를 하지 않는다.
- 일반 `crap`·`mutation`·`check`·`history` 조회는 cutoff가 지난 retained bundle도 자동 삭제하지 않는다. State가 없는 project의 plain `history`는 `.sentinel` 생성 0이고, existing state에서는 실행 전후 whole path·type·mode·owner·content manifest가 같다. Child process와 network 호출도 0이다. `history prune`은 `--confirm`이 없으면 marker·write·delete 0이고 project나 CI가 명시한 confirm 실행만 삭제를 시작한다.
- `history prune --before`는 ASCII `YYYY-MM-DD`만 받아 해당 날짜 UTC 00:00:00의 exclusive cutoff로 해석한다. Time component, timezone·offset, locale date, invalid calendar date와 trailing byte는 usageConfigError이며 marker·write·delete·mutation 0이다. Completed·incomplete UTC equality, marker 경합과 retained bundle 불변을 검증한다. Completed와 incomplete 각각 retention marker의 owner-only temporary create·file-sync·same-directory rename·directory sync 각 경계에 crash를 주입하며 marker directory sync 전 selected bundle delete는 0이어야 한다. Durable completed marker 뒤 delete crash는 일부 physical bundle이 남아도 같은 pair windows·`historyLowerBound` 안내값·`truncated=true`·logical result를 내고 resume가 남은 pair-eligible bundle만 지운다. Completed fixture는 high-water `H`에 대한 sequence `H-1/H/H+1` × UTC `before/equal/after` 9조합에서 `H-1/before`, `H/before`만 제외하는지 확인한다. 또한 `marker durable -> UTC rollback -> H보다 큰 sequence의 terminal commit인데 committedAtUtc는 cutoff 전` 순서에서 새 run을 보존하고, cutoff와 high-water가 서로 교차하는 여러 marker도 각 pair predicate의 union으로만 fold한다. Max cutoff 단독 filter로 새 run을 숨기거나 지우면 실패한다. Durable incomplete marker는 sorted immutable selection의 아직 존재하는 subset만 처리한다. Marker 뒤 새 started-only run이 cutoff를 만족해도 이 marker로는 delete 0이고, selected run이 뒤에 completed가 되면 보존한다. 나머지 selected run도 completed 부재, stored started·lease generation·lease digest·tree-drained digest와 HMAC join을 다시 증명하기 전 delete가 0이다. Fully written marker도 schema, filename·canonical content digest·HMAC, cutoffUtc·kind·selection count·selection digest·sequenceHighWaterAtCommit이 corrupt하면 `history`와 prune은 exit 7, delete·mutation 0으로 fail-closed한다. Guardian crash·tree-drained marker missing·HMAC mismatch에서는 삭제 0이다. 실제 fixture는 marker durable 직후 신규 eligible run 생성과 selected run terminal commit을 각각 barrier로 주입해 selection 밖 삭제와 completed 전환 삭제가 모두 0인지 확인한다.
- 같은 finding의 completed fresh run 3개 중 첫 run만 prune한 뒤 retained bundle로 history를 다시 fold하면 observationCount 2, firstObservedAt·firstRetainedObservation은 두 번째 run, latestObservedAt은 세 번째 run이어야 한다. 삭제 runId와 occurrence·context record는 출력 0이고 `historyLowerBound`는 effective cutoff, `truncated=true`여야 한다. Derived index를 제거한 뒤 retained append-only bundle에서 commitSequence 순으로 재생성한 bytes가 같은 결과여야 하며 stale index가 삭제 run을 계속 count하거나 UTC로 순서를 바꾸면 실패한다.
- `started.json`의 exclusive-create·file-sync·run-directory sync 각 지점에 crash를 주입하고 directory sync까지 durable 완료되기 전 test·coverage·candidate·backend 호출이 0인지 검증한다. 이어서 Event exclusive-create·file-sync·events-directory sync, evidence temporary file-sync·rename·run-directory sync 각 지점에도 crash를 주입한다. Event manifest filename의 absolute·`..`·separator·duplicate, manifest와 directory의 missing·extra event, digest·mode 변조와 validated descriptor 확인 직후 entry swap을 실제 read path에 주입한다. Lexical child name과 descriptor-bound identity, manifest exact file set을 모두 증명하지 못하면 state 밖 read 0, completed·certified 승격 0, `history` exit 7로 fail-closed한다.
- permissive umask에서도 `.sentinel/state-v1`, `project.json`, `commit.lock`, started·event·evidence file, retention marker와 `localCacheDir` root·manifest·entry가 현재 owner 전용 mode로 생성된다. 기존 group/world-writable 또는 다른 owner의 state·cache, symlink·hardlink가 있으면 backend·cache copy·write 전에 evidenceError로 fail-closed한다. State와 cache root 및 각 component의 검사 직후 parent·component path swap을 주입해 validated descriptor 밖 read·create·rename·delete가 0인지 확인한다.
- 다섯 clean package의 dependency metadata·runtime import·load·실행 graph에 SwarmForge, 코딩 하네스 또는 sibling SENTINEL runtime package가 0개다. SENTINEL 사이 공유 입력은 vendored SPEC과 해당 언어의 승인 backend만 허용하고, 그 밖의 Koffi·coverage·Vitest·Jackson·JUnit 같은 일반 dependency는 해당 저장소 lock allowlist와 exact artifact digest에 일치해야 한다. README와 `harness-integration.md`의 설명 문자열은 dependency로 오판하지 않는다.

`test_cross_runtime_lock.py`는 같은 `commit.lock`과 `.sentinel/state-v1`을 대상으로 production registry의 실제 설치 CLI 5개로 모든 pairwise shared·exclusive 조합과 all-runtime simultaneous fail·pass terminal commit·history read·prune을 실행한다. Default OS Clock만 쓰며 test injection option은 없다. Barrier는 subprocess 시작과 lock 경쟁만 제어한다. 자연 UTC 값과 관계없이 lock 획득 순서의 distinct commitSequence가 생기고 lifecycle latest/current와 derived index 삭제 뒤 fold가 sequence 순서로 byte-identical인지 확인한다. 한 runtime이라도 상호 배제, crash release 또는 allocation-before-evidence 순서를 어기면 해당 runtime release를 차단한다.

`test_cross_runtime_sandbox_lease.py`는 producer 5개 × consumer 5개의 25조합을 모두 별도 owner-only project에서 실행한다. Driver는 producer spawn 전 `prctl(PR_SET_CHILD_SUBREAPER, 1)`을 설정해 fault 뒤 남은 fixture를 자기 아래로 회수한다. 각 producer는 runtime registry의 실제 설치 CLI로 long-running approved test command가 있는 `mutation`을 시작한다. Test는 durable `started.json`, sandbox lease file·directory sync와 child start-gate 해제 뒤 guardian·wrapper identity가 실제 `/proc` 값과 일치할 때까지 descriptor-safe read로 기다린다. 각 consumer의 실제 설치 CLI가 next `mutation`과 `history prune --incomplete --before DATE --confirm`을 차례로 실행한다. A는 driver가 guardian pidfd에 SIGSTOP을 보낸 뒤 controller를 SIGKILL해 EOF drain을 barrier에 세운다. Guardian과 leased child가 live이고 tree-drained marker가 없으므로 DATE를 producer 다음 UTC 날짜로 두어도 sandbox·incomplete bundle을 보존한다. 판정 뒤 driver가 guardian pidfd에 SIGCONT를 보내 drain을 끝낸다. B는 fresh producer의 controller를 SIGKILL한 뒤 guardian이 entire tree를 pidfd로 종료·reap하고 durable HMAC marker를 남겨 exit할 때까지 기다린 dead-young 상태에서 DATE를 producer `startedAtUtc`의 전날 UTC 날짜로 두어 sandbox와 incomplete bundle을 모두 보존한다. C는 별도 fresh 25조합에서 controller kill 뒤 guardian exit와 valid marker를 기다리고 producer 다음 UTC 날짜를 사용해 young sandbox는 보존하되 incomplete bundle만 marker-first로 삭제한다.

각 producer backend helper는 공백과 `)`가 든 process name의 child를 exit시켜 parent가 아직 wait하지 않은 actual `Z`를 만들고 동시에 `setsid` 뒤 double-fork한 long-lived descendant를 둔다. Guardian이 drain 전인 동안 각 consumer의 production oracle은 exact zombie를 dead·no-signal, long-lived descendant를 live로 판정한다. Controller SIGKILL 뒤 guardian은 command EOF를 받고 session을 벗어난 double-fork descendant까지 adopted direct child로 pidfd 종료하며, 모든 zombie를 `waitid(P_PIDFD)`로 reap하고 ECHILD 뒤 marker를 durable commit한다. Driver는 `/proc` disappearance까지 확인한다. 별도 D 25조합은 GO 뒤 guardian을 marker 전 SIGKILL하고 driver가 나머지 process를 reap한다. Process가 실제로 0이고 injected age가 만료되어도 marker가 없으므로 모든 consumer가 sandbox·incomplete delete 0이어야 한다. Cutoff equality는 실제 날짜 CLI로 꾸미지 않고 아래 injected Clock matrix에서만 검증한다. Producer가 쓴 canonical lease·tree-drained marker를 consumer가 byte 그대로 읽지 못하거나 `/proc` state를 last-`)` 기준으로 parse하지 못하면 실패한다.

24시간·7일을 실제로 기다릴 수 없는 age, boot mismatch, PID reuse, path-swap, UTC jump와 durable-write crash case는 별도 `fault-harness-registry.json`의 test-source command를 호출한다. Python harness는 production parser·Store·orchestrator를 import하고, TypeScript harness는 source test runner로 production entry를 호출하며, Go는 `testdata/fault_harness/main.go`를 VCS 밖 test binary로 build하고, Java는 test classpath의 `FaultHarnessMain`, Clojure는 test alias의 `fault-harness` namespace를 실행한다. 이 다섯 harness만 test-only `Clock`, `Process`, `FileOps`, `HmacSha256` implementation을 constructor로 주입하고 공통 request·response schema를 사용한다. 완성 결과를 직접 반환하는 mock은 금지하며 parser, HMAC, commit-sequence allocator·history fold, guardian marker oracle, quarantine·prune orchestrator와 evidence code는 실제 production path 그대로다. Producer 5개가 같은·backward UTC의 fail·pass evidence, allocation crash gap, HMAC tamper, valid old high-water replay, retained evidence·retention marker보다 작은 high-water, duplicate·missing·zero·overflow sequence, event-evidence mismatch와 crossed retention-window bytes를 각각 만들고 consumer 5개가 모두 읽어 같은 fold 또는 exit 7·write/delete 0을 내는 25조합을 실행한다. Marker durable 뒤 UTC rollback과 더 큰 sequence terminal commit도 옛 marker로 숨기거나 삭제하지 않는다. Sequence fault는 production registry CLI에 injection option을 추가하지 않고 이 test-source wrapper만 production Store constructor를 호출해 만든다. 이 matrix는 같은 lease·tree-drained marker 25조합에 대해 same-boot boottime 직전·equality·초과·backward·syscall failure, cross-boot creation/current `adjtimex` synchronized·unsynchronized·unavailable·`TIME_ERROR`·`STA_UNSYNC`·UTC rollback, guardian live·drained·SIGKILL, marker create·file-sync·directory-sync crash, wrong HMAC·guardian identity·lease generation, exact zombie `Z`·dead `X`, 공백·괄호가 든 `comm`, malformed stat·read disappearance, reused PID no-signal, numeric `2^53-1`·`2^53`·`2^53+1`과 field별 zero·overflow도 포함한다. Syscall trace에서 numeric `kill`·`killpg`·`tgkill`은 0이고 PID reuse canary는 살아 있어야 한다. Fingerprint key E1→E2 회전 뒤 identifier·cleanupLeaseKey·projectToken과 old marker join이 유지되어야 한다. HMAC failure·token mismatch는 no-touch다. Valid marker+age-expired sandbox만 no-replace quarantine할 수 있고, incomplete run은 sandbox age와 무관하게 valid marker+started-before-cutoff+completed 없음에서만 prune한다. Guardian crash나 marker 부재는 cross-boot synchronized 7일 초과에서도 영구 no-delete다. Cutoff·age equality는 모두 보존한다.

Quarantine rename 전·후와 directory sync, descriptor 확인 뒤 path swap, quarantine 성공 뒤 recursive delete의 각 경계에 crash를 주입하고 restart가 exact lease generation·device·inode의 existing quarantine만 이어가도록 한다. 다른 path·generation은 delete 0이다. Catch 가능한 종료와 dead+expired cleanup 뒤에는 sandbox와 default raw report canary가 0개여야 한다. Live·unknown orphan 내부 raw는 owner-only sandbox 안에서만 임시 허용되고 공용 evidence·finding·history·export·diagnostic·기본 artifact에는 모든 시점 raw canary가 0개여야 한다. `fault-harness-registry.json`은 runtime registry와 분리된 owner-only test record이고 test source path·argv·digest만 담는다. Test-only adapter의 이름과 byte digest는 release asset·production runtime import graph·production `runtime-registry.json`에서 0개여야 하며 T29 release build 전에 fault registry와 test binary를 폐기한다.

- [ ] **단계 2A: registry preflight RED 확인**

실행 위치: `SENTINEL_SPEC`

실행: `scripts/uv.sh run pytest tests/test_cross_runtime.py -q -k registry_preflight --runtime-registry <workspace>/build/t25/missing-runtime-registry.json --fault-harness-registry <workspace>/build/t25/missing-fault-harness-registry.json`

기대: unknown option이나 collection error가 아니라 missing registry semantic error로 실패하고 runtime·fault command 호출은 0

- [ ] **단계 2B: 실제 pre-T25 runtime 의미 characterization**

`test_cross_runtime.py::test_pre_t25_runtime_semantics`는 아직 없는 production driver나 T25 build script를 호출하지 않는다. Test-owned temporary directory에서 T08·T12·T16·T20·T24의 existing repo-local entrypoint를 absolute argv로 직접 실행하고 invocation `{runtime,argv0Digest,exit,stdoutDigest,stderrDigest}`를 남긴다. 다섯 runtime을 모두 호출하지 못하면 assertion 전에 실패 사유를 분리해 RED 근거로 인정하지 않는다.

실행: `scripts/uv.sh run pytest tests/test_cross_runtime.py::test_pre_t25_runtime_semantics -q`

기대: T08·T12·T16·T20·T24의 실제 완성된 repo-local CLI를 runtime별 1회 이상 실행한 invocation receipt가 남음. 이미 의미가 일치하면 통과를 그대로 기록하고, 차이가 있으면 exact field·exit 차이로 실패한다. 인위적인 missing adapter를 요구하지 않으며 registry·dependency·test 0개 failure는 characterization 결과가 아님

- [ ] **단계 3: conformance driver와 최소 adapter 구현**

Driver의 `prepare`와 `prepare-fault-harnesses`는 required absolute `--attempt-record`와 matching `--attempt-sha256`을 받아 immutable `attempt.json` digest·owner·mode·starting HEAD·source manifest를 먼저 검증한다. Raw build root option은 받지 않으며 T25와 T27이 같은 verifier에 자기 direct attempt record를 넘긴다. 다섯 `scripts/build-release.*`를 explicit argv로 호출해 `<attempt-root>/artifacts/`에 artifact를 만들고 `<attempt-root>/install/`에 격리 설치한다. 이어 canonical `<attempt-root>/runtime-registry.json`에 위 고정 schema로 Python·TypeScript·Go·Java·Clojure absolute executable argv와 identity를 기록한다. `prepare-fault-harnesses`는 다섯 test source를 각 고정 wrapper로 compile·typecheck하고 `<attempt-root>/fault-harness/` argv·source digest를 `<attempt-root>/fault-harness-registry.json`에 기록한다. OCI session, runtime root와 writable fixture copy도 각각 `<attempt-root>/oci-executor-session.json`, `<attempt-root>/runtime-roots/`, `<attempt-root>/project-workspaces/` 아래만 쓴다. 두 registry는 canonical JSON+final LF, mode `0600`으로 file·directory sync하며 한번 게시한 path를 다시 열어 쓰지 않는다. Cross-runtime test는 immutable attempt record에서 두 registry path·digest를 해석하고 각 argv를 exact 사용하며 shell, PATH, environment executable 추측을 금지한다. Registry path·digest·owner mode·entry set이 다르면 호출 0에서 실패한다. Production registry에는 installed argv만 들어가며 fault adapter나 test-only package를 넣지 않는다. Fault registry command는 release build·clean-install·self-quality 입력으로 쓸 수 없다. Fixture는 모든 9개 mutation 상태, unknown, 0 mutant, exact CRAP 8.0·초과, coverage 오류 taxonomy, 두 baseline, config·path safety, cache·partial, lifecycle·retention·privacy를 포함한다. Runtime 고유 raw report는 비교 전에 공용 model로 들어오지 못한다.

Clean-install driver는 container 동작 전에 T01의 `clean-install-executor.lock.json`을 읽고 `verify_oci_executor.py`로 owner-only `<build-root>/oci-executor-session.json`을 만든다. 모든 OCI 호출은 이 session record의 absolute `/usr/bin/docker --config <validated-empty-dir> --host unix:///run/docker.sock` argv prefix를 `shell=False`로 사용한다. Parent의 `DOCKER_HOST`, `DOCKER_CONTEXT`, `DOCKER_CONFIG`, TLS·proxy와 credential-helper environment는 전달하지 않고, 호출 전후 client binary digest, canonical socket device·inode·owner·group·mode, client·server version·commit·API·OS·arch를 session과 다시 대조한다. 한 값이라도 바뀌거나 context·remote endpoint·ambient credential file이 관여하면 image pull 전 또는 다음 OCI 호출 전에 실패한다.

Driver는 full OCI reference `docker.io/library/ubuntu@sha256:1e0a86e57d247923571b75e0aaf48a1449cf8c543d51fb3e07a4a7d7bfa79316`을 Linux amd64로 pull한다. Lock과 대조할 값은 requested full reference·manifest digest·OS·architecture다. Driver는 그 content-addressed raw manifest를 읽어 config descriptor digest를 추출하고, inspect의 `RepoDigests`가 requested manifest를 포함하며 image ID·config digest가 그 descriptor와 내부 일치하는지 확인한다. Config JSON의 OS·architecture도 lock과 manifest platform에 일치해야 한다. 이 검증 뒤 inspect한 image ID만 create한다. Created container inspect에서 network `none`, read-only root filesystem, capability drop all, no-new-privileges, explicit readonly mounts·tmpfs와 sealed environment가 요청값과 같은지 재검증한 뒤 start한다. `prepare`는 T01의 `.toolchain`을 source repo에서 직접 mount하지 않고 installed tree·version·ABI를 `toolchain.lock.json`에 재검증한 뒤 VCS 밖 `<build-root>/runtime-roots/<treeDigest>/`로 원자 copy한다. Writable fixture copy는 `<build-root>/project-workspaces/<invocationId>/` 아래만 만들고 이 둘을 포함한 모든 driver-created path는 validated build root descriptor에서만 파생한다. Container에는 build output, read-only golden fixture corpus, lock에서 미리 검증한 offline dependency store와 해당 language의 lock-verified runtime root만 read-only mount하고 source tree·sibling repo는 mount하지 않는다. Container 안에서도 runtime executable tree·version·ABI digest를 lock과 다시 대조한다.

각 quality command 전에 driver는 read-only corpus의 exact manifest를 검사하고 선택한 고정 fixture를 descriptor-safe 방식으로 owner-only tmpfs project workspace에 복사해 그 writable copy를 `projectRoot`로 넘긴다. Copy 직후 source·test·config를 read-only로 바꾸고 `.sentinel`과 config에 선언한 generated-output·raw-output directory만 별도 owner-only writable path로 허용한다. 실행 뒤 copied source·test·config manifest와 원 read-only corpus manifest가 모두 불변이고 writable change inventory가 `.sentinel`과 해당 command의 declared output allowlist에만 있는지 검사한다. 원 checked-in corpus나 read-only mount에 `.sentinel`이 생기면 실패한다. Network, ambient environment, extra capability와 그 밖의 writable root를 끄고 필요한 temporary path만 tmpfs로 준다. Known source·sibling absolute path negative probe가 보이거나 container·namespace 생성 자체가 실패하면 clean-install은 실패다. 이 경계 안에서 설치·실행하므로 같은 UID의 일반 temporary directory만 쓰는 검사는 인정하지 않는다. Artifact layout은 Python wheel, TypeScript `npm pack` tarball, Go `bin/sentinel-go`와 `libexec/sentinel-mutate4go`, Java `bin/sentinel-java`·`lib/sentinel-java-all.jar`·`libexec/mutate4java-bridge.jar`, Clojure `bin/sentinel-clj`·`lib/sentinel-clj.jar`·`libexec/clj-mutate-bridge.jar`로 고정한다. 각 설치본으로 help·doctor·crap·mutation·check·history fixture를 실행하고 backend companion digest와 source tree access 0을 확인한다.

Python은 PEP 517 wheel과 console script, TypeScript는 package `bin`과 production dependency를 pack한다. Go의 patched nested module은 public bridge command `cmd/sentinel-mutate4go-bridge`를 `libexec/sentinel-mutate4go`로 build하고 main adapter는 sibling digest를 확인해 argv로 실행한다. Java는 Jackson BOM·databind 2.22.2와 Maven Shade Plugin 3.6.2를 exact pin해 executable all-JAR를 만들고 patched backend bridge JAR를 분리한다. Clojure는 tools.build 0.10.14를 exact pin해 main·backend companion uberjar를 만들며 launcher는 자기 설치 directory를 기준으로 jar를 찾고 호출자의 current project directory를 보존한다.

Packaging dependency를 추가하거나 build metadata를 바꾼 뒤 Python은 `uv.lock`, TypeScript는 `package-lock.json`, Java·Clojure는 `dependency-lock.json`을 exact artifact set으로 재생성한다. Network 허용 cache-fill은 Python `scripts/uv.sh sync --locked`, TypeScript `scripts/npm.sh ci`, Java `/usr/bin/bash scripts/verify-dependencies.sh --populate`, Clojure `/usr/bin/bash scripts/verify-dependencies.sh --populate`를 이 순서로 각 owning repo에서 한 번 실행하는 단계뿐이다. 그 즉시 Python `scripts/uv.sh sync --locked --offline`, TypeScript `scripts/npm.sh ci --offline`, Java·Clojure `/usr/bin/bash scripts/verify-dependencies.sh`, Go `scripts/go.sh --offline mod verify`를 통과시킨다. Go의 `go.mod`·`go.sum`은 T25 시작 digest와 같아야 한다. 이후 network를 끈 isolated cache/store에서 unit·integration·acceptance와 두 번의 deterministic build를 실행한다. Extra·missing dependency, lock에 없는 plugin이나 runtime download가 하나라도 보이면 clean-install과 release build를 중단한다.

- [ ] **단계 4: 전체 conformance 통과 확인**

실행 위치: `SENTINEL_SPEC`

실행: `scripts/uv.sh run python tools/run_cross_runtime.py new-attempt --workspace <workspace> --attempt-root <workspace>/build/t25`

기대: stdout 한 줄의 `<T25_ATTEMPT_RECORD>`와 `<T25_ATTEMPT_SHA256>`을 사람이 복사해 아래 모든 angle-bracket에 그대로 대입함

실행: `scripts/uv.sh run python tools/run_cross_runtime.py prepare --workspace <workspace> --attempt-record <T25_ATTEMPT_RECORD> --attempt-sha256 <T25_ATTEMPT_SHA256> --executor-lock clean-install-executor.lock.json --reproducible-builds 2`

실행: `scripts/uv.sh run python tools/run_cross_runtime.py prepare-fault-harnesses --workspace <workspace> --attempt-record <T25_ATTEMPT_RECORD> --attempt-sha256 <T25_ATTEMPT_SHA256>`

실행: `scripts/uv.sh run python tools/run_cross_runtime.py verify --workspace <workspace> --attempt-record <T25_ATTEMPT_RECORD> --attempt-sha256 <T25_ATTEMPT_SHA256>`

기대: stdout 한 줄의 `<T25_CONFORMANCE_RECEIPT>` absolute path와 `<T25_CONFORMANCE_RECEIPT_SHA256>` whole-file SHA-256을 단계 5에 그대로 고정

`verify`는 shell string 없이 repository별 `cwd`와 argv array로 SPEC의 `tests/test_oci_executor.py`, 일곱 cross-runtime test file 전체, Python 전체 pytest, TypeScript typecheck와 전체 Vitest, Go `test ./... -count=1`과 `vet ./...`, Java dependency verifier와 full Maven verify, Clojure dependency verifier와 full `-M:test`를 모두 실행한다. 각 언어의 conformance·clean-install inventory가 expected·started·terminal exact join이고 두 deterministic build digest가 같아야 한다. 중간 selector만 통과한 결과는 final success가 아니다.

`verify`는 Git index·branch·commit과 stage list를 만들거나 읽지 않는다. 마지막 성공에서만 `conformance-receipt.schema.json`으로 검증한 `conformance-receipt.json`을 no-replace·file sync·directory sync한다. Exact body는 version, sequence, attempt SHA-256, `parentT27AttemptSha256`, sorted six `{repository,startingHead,sourceManifestSha256}`, runtime·fault registry digest, executor lock digest, OCI session digest, 두 build artifact manifest digest, ordered command receipt `{id,cwdRepository,argvSha256,exit,stdoutSha256,stderrSha256,testInventorySha256}`, `allPassed=true`와 자기 field를 제외한 receipt SHA-256이다. 모든 exit가 0이고 source manifest가 attempt와 같고 test inventory가 exact join일 때만 생성한다. 이 분리 덕분에 T27 또는 T29의 다른 정확한 changed set에서도 fresh conformance receipt를 만들 수 있지만, 그 receipt가 T25 commit 권한을 주지는 않는다.

기대: 각 runtime conformance와 clean-install expected test ID·실제 started·terminal set이 exact join하고 두 layer 모두 1개 이상이다. Schema·semantic·text·exit 0..8·gate·scope·check orchestration·classification·fingerprint·cache·partial·history·privacy·POSIX lock 의미가 5개 runtime에서 일치하고, 격리된 5개 clean install이 전 command를 실행하며, polyglot fixture의 Python·TypeScript inventory가 서로 교집합 0

- [ ] **단계 5: 저장소별 commit**

각 owning child repo 안에서만 T25의 전체 변경을 다음 exact allowlist로 commit한다.

- SPEC: `tools/run_cross_runtime.py`, `tests/conftest.py`, `tests/contracts/runtime-registry.schema.json`, `tests/contracts/fault-harness-registry.schema.json`, `tests/contracts/fault-harness-request.schema.json`, `tests/contracts/fault-harness-response.schema.json`, `tests/contracts/conformance-receipt.schema.json`, `tests/contracts/t25-commit-seal.schema.json`, `tests/test_cross_runtime.py`, `tests/test_text_json_equivalence.py`, `tests/test_cross_runtime_lock.py`, `tests/test_cross_runtime_sandbox_lease.py`, `tests/test_state_contract_matrix.py`, `tests/test_clean_install.py`, `tests/test_polyglot_routing.py`, `README.md`, `docs/log.md`
- Python: `tests/conformance/test_contract.py`, `tests/conformance/fault_harness.py`, `tests/clean_install/test_clean_install.py`, `scripts/build-release.py`, `pyproject.toml`, `uv.lock`, `README.md`, `docs/log.md`
- TypeScript: `test/conformance/contract.test.ts`, `test/conformance/fault-harness.ts`, `test/clean_install/clean-install.test.ts`, `scripts/build-release.mjs`, `package.json`, `package-lock.json`, `README.md`, `docs/log.md`
- Go: `internal/conformance/conformance_test.go`, `internal/cleaninstall/clean_install_test.go`, `testdata/fault_harness/main.go`, `test-inventory/conformance.json`, `scripts/build-release.sh`, `README.md`, `docs/log.md`
- Java: `src/test/java/io/github/hwainhwang/sentinel/conformance/ConformanceTest.java`, `src/test/java/io/github/hwainhwang/sentinel/conformance/FaultHarnessMain.java`, `src/test/java/io/github/hwainhwang/sentinel/cleaninstall/CleanInstallTest.java`, `src/test/resources/test-inventory/conformance.json`, `scripts/build-release.sh`, `pom.xml`, `dependency-lock.json`, `README.md`, `docs/log.md`
- Clojure: `test/sentinel_clj/conformance/contract_test.clj`, `test/sentinel_clj/conformance/fault_harness.clj`, `test/sentinel_clj/clean_install_test.clj`, `test/fixtures/test-inventory/conformance.edn`, `scripts/build-release.sh`, `deps.edn`, `dependency-lock.json`, `build.clj`, `bin/sentinel-clj`, `README.md`, `docs/log.md`

Conformance receipt가 성공한 같은 T25 attempt에서만 `prepare-commit-stage-lists`를 한 번 실행한다. 이 command는 `parentT27AttemptSha256`가 null인지, 여섯 current source manifest와 단계 5의 사람이 작성한 exact allowlist가 같은지 먼저 확인한다. 그 뒤 각 repository의 concrete path-only NUL `stage/<repository>.paths`, 별도 sorted path·mode·blob digest와 expected resulting tree를 만들고 `t25-commit-seal.schema.json`으로 검증한 `t25-commit-seal.json`에 starting HEAD, conformance receipt digest, path-list·blob-manifest digest와 exact message를 no-replace 봉인한다. SPEC의 T04 `VERSION`, `schemas/**`, `contracts/**`, `golden/**`, `manifest.json`과 Go의 `go.mod`·`go.sum`이 달라지거나 VCS 밖 registry·artifact·install·fault-harness·runtime-root·project-workspace가 source 또는 stage에 있으면 중단한다.

실행: `scripts/uv.sh run python tools/run_cross_runtime.py prepare-commit-stage-lists --attempt-record <T25_ATTEMPT_RECORD> --attempt-sha256 <T25_ATTEMPT_SHA256> --conformance-receipt <T25_CONFORMANCE_RECEIPT> --conformance-receipt-sha256 <T25_CONFORMANCE_RECEIPT_SHA256>`

기대: stdout 한 줄의 `<T25_COMMIT_SEAL>` absolute path와 `<T25_COMMIT_SEAL_SHA256>` whole-file SHA-256을 아래 두 command에 그대로 고정

실행: `scripts/uv.sh run python tools/run_cross_runtime.py resume-commits --attempt-record <T25_ATTEMPT_RECORD> --attempt-sha256 <T25_ATTEMPT_SHA256> --commit-seal <T25_COMMIT_SEAL> --commit-seal-sha256 <T25_COMMIT_SEAL_SHA256>`

실행: `scripts/uv.sh run python tools/run_cross_runtime.py verify-committed --attempt-record <T25_ATTEMPT_RECORD> --attempt-sha256 <T25_ATTEMPT_SHA256> --commit-seal <T25_COMMIT_SEAL> --commit-seal-sha256 <T25_COMMIT_SEAL_SHA256>`

`resume-commits`는 canonical six-repository 순서로 각 owning child를 cwd로 삼고 T01 `commit_inventory.py stage-exact`와 `commit-prepared`의 같은 library boundary를 호출한다. 각 stage receipt path·whole-file SHA-256을 commit command에 직접 넘기며 commit message는 exact `test: add cross-runtime conformance (요구사항-03..08,19,20,32,33,38,42..55)`다. Repository 상태는 starting HEAD·empty index·sealed working set, 같은 HEAD·exact staged set, exact expected single child·clean tree 세 가지뿐이다. Partial index, 다른 parent·message·path·mode·blob·tree에서는 남은 Git mutation 0으로 중단한다. Root workspace에서는 Git을 실행하지 않는다. Terminal rerun은 Git과 receipt mutation 0이다.

### T26: 6개 README와 OKF v0.2 지식 문서 완성

**충족 요구사항:** 요구사항-36, 요구사항-37, 공통규칙-10

**파일:**

- 생성: `SENTINEL_SPEC/tools/lint_okf.py`, `tests/test_documentation.py`
- 생성: `SENTINEL_PY/scripts/lint_docs.py`, `tests/unit/test_documentation.py`
- 생성: `SENTINEL_TS/scripts/lint-docs.mjs`, `test/unit/documentation.test.ts`
- 생성: `SENTINEL_GO/tools/lintdocs/{main.go,main_test.go}`, `SENTINEL_GO/test-inventory/documentation.json`
- 생성: `SENTINEL_JAVA/src/test/java/io/github/hwainhwang/sentinel/documentation/DocumentationTest.java`, `SENTINEL_JAVA/src/test/resources/test-inventory/documentation.json`
- 생성: `SENTINEL_CLJ/test/sentinel_clj/documentation_test.clj`, `SENTINEL_CLJ/test/fixtures/test-inventory/documentation.edn`
- 수정: `SENTINEL_CLJ/test/sentinel_clj/test_runner.clj`
- 수정: 6개 `README.md`, `docs/index.md`, `docs/log.md`
- 수정: 실재 책임이 있는 저장소의 `docs/{architecture,contracts,backend,operations,privacy,lineage}.md`
- 생성: VCS 밖 owner-only `build/t26/stage/<repository>.paths`, `build/commit-inventory/T26/<repository>/docs/{blobs,receipt,committed}.json`

**받는 것:** T25에서 실제로 굳어진 CLI·contract·backend·운영 경계

**주는 것:** 빈 개념·깨진 링크가 없는 6개 OKF v0.2 bundle과 사용자가 바로 실행할 수 있는 README

- [ ] **단계 1: 문서 lint adapter 계약의 실패 test 작성**

검사는 모든 knowledge 문서의 frontmatter, stable ID, title, status, owner, 한 파일 한 개념, `docs/index.md` 양방향 link, append-only `docs/log.md`, 빈 파일·고아 문서·깨진 상대 link를 거부한다. README 검사는 install, 5개 command, 지원 범위, 결과·exit, native CRAP 책임, backend 책임, Robert Martin에서 이어받은 부분과 SENTINEL 확장, privacy·history, SwarmForge 비종속 사용 예를 요구한다. 먼저 test-owned temporary OKF bundle 표를 만들어 valid, field missing, orphan, broken link, sibling escape를 adapter에 넣는다. SPEC test는 SPEC root 하나만 받고 sibling path를 탐색하지 않는다. 다섯 runtime adapter도 자기 repository root 하나만 받고 같은 malformed fixture 표를 각 언어 test로 검증한다. Go는 `test-inventory/documentation.json`, Java는 `src/test/resources/test-inventory/documentation.json`과 Maven selector registration, Clojure는 `test/fixtures/test-inventory/documentation.edn`과 `test_runner.clj` selector registration을 test 작성과 동시에 infrastructure로 먼저 갱신한다. Adapter production은 만들지 않아 단계 2의 의도된 missing adapter RED를 유지한다.

- [ ] **단계 2: 실패 확인**

실행 위치: `SENTINEL_SPEC`

실행: `scripts/uv.sh run pytest tests/test_documentation.py -q -k adapter_contract`

실행 위치와 명령: Python `scripts/uv.sh run pytest tests/unit/test_documentation.py -q -k adapter_contract`, TypeScript `scripts/node.sh --tool vitest -- --run test/unit/documentation.test.ts -t adapter-contract`, Go `scripts/go.sh --offline test ./tools/lintdocs -run TestAdapterContract -count=1`, Java `/usr/bin/bash scripts/verify-dependencies.sh && scripts/mvn.sh -o -B -ntp -Dtest=io.github.hwainhwang.sentinel.documentation.DocumentationTest#adapterContract test`, Clojure `/usr/bin/bash scripts/verify-dependencies.sh && scripts/clojure.sh --offline -M:test --include-id documentation-adapter-contract`

기대: 각 명령은 lint adapter 부재로 실패하고 test runner·dependency·test discovery는 성공함

- [ ] **단계 3: 여섯 독립 lint adapter 구현과 repository RED 확인**

각 adapter는 명시적으로 받은 자기 repository root 하나를 descriptor-safe read-only traversal하고 repository 밖·sibling·network 접근을 거부한다. 같은 canonical rule ID와 sorted result schema를 구현하고, symlink·hardlink·non-UTF-8·duplicate stable ID도 fail-closed한다. Go·Java·Clojure는 단계 1에서 이미 등록한 task inventory를 그대로 사용한다. 단계 2의 selector가 전부 통과한 뒤 각 repository의 test file 전체를 실행한다.

실행: 단계 2의 여섯 selector를 다시 실행한 뒤, SPEC `scripts/uv.sh run pytest tests/test_documentation.py -q`, Python `scripts/uv.sh run pytest tests/unit/test_documentation.py -q`, TypeScript `scripts/node.sh --tool vitest -- --run test/unit/documentation.test.ts`, Go `scripts/go.sh --offline test ./tools/lintdocs -count=1`, Java `/usr/bin/bash scripts/verify-dependencies.sh && scripts/mvn.sh -o -B -ntp -Dtest=io.github.hwainhwang.sentinel.documentation.DocumentationTest test`, Clojure `/usr/bin/bash scripts/verify-dependencies.sh && scripts/clojure.sh --offline -M:test --include-id documentation`

기대: adapter contract selector는 통과하지만 repository bundle 검사는 아직 채워지지 않은 README section 또는 OKF field 때문에 실패함. Missing adapter·dependency, test 0개 또는 sibling 접근은 이 RED 근거로 인정하지 않음

- [ ] **단계 4: 실제 구현에 맞는 문서만 작성**

각 저장소의 `docs/index.md`는 존재하는 문서만 연결하고 `docs/log.md`에는 Creation과 주요 계약 변경을 시간순으로 남긴다. Backend repo는 원본 URL·commit·가져온 operator 범위·bridge patch·달라진 책임을 lineage에 기록한다. SPEC에는 backend별 raw 형식을 공통 계약으로 승격하지 않는다. 실행 경로가 없는 미래 기능 문서는 만들지 않는다.

- [ ] **단계 5: 6개 독립 bundle 통과 확인**

실행: `scripts/uv.sh run pytest tests/test_documentation.py -q`

실행: Python `scripts/uv.sh run pytest tests/unit/test_documentation.py -q`, TypeScript `scripts/node.sh --tool vitest -- --run test/unit/documentation.test.ts`, Go `scripts/go.sh --offline test ./tools/lintdocs -count=1`, Java `/usr/bin/bash scripts/verify-dependencies.sh && scripts/mvn.sh -o -B -ntp -Dtest=io.github.hwainhwang.sentinel.documentation.DocumentationTest test`, Clojure `/usr/bin/bash scripts/verify-dependencies.sh && scripts/clojure.sh --offline -M:test --include-id documentation`

기대: SPEC은 SPEC 문서만, 각 runtime은 자기 README·OKF v0.2·link·lineage만 독립 검증해 모두 통과. Global Python, sibling checkout과 network 사용 0

- [ ] **단계 6: 저장소별 exact commit**

각 owning child repo 안에서 다음 exact set만 T01 `commit_inventory.py stage-exact`로 stage하고 path·mode·blob·resulting tree를 receipt와 비교한다.

- SPEC: `tools/lint_okf.py`, `tests/test_documentation.py`, `README.md`, `docs/index.md`, `docs/log.md`, `docs/architecture.md`, `docs/contracts.md`, `docs/privacy.md`
- Python: `scripts/lint_docs.py`, `tests/unit/test_documentation.py`, `README.md`, `docs/index.md`, `docs/log.md`, `docs/architecture.md`, `docs/contracts.md`, `docs/backend.md`, `docs/operations.md`, `docs/privacy.md`, `docs/lineage.md`
- TypeScript: `scripts/lint-docs.mjs`, `test/unit/documentation.test.ts`와 Python 행과 같은 9개 README·docs path
- Go: `tools/lintdocs/main.go`, `tools/lintdocs/main_test.go`, `test-inventory/documentation.json`과 Python 행과 같은 9개 README·docs path
- Java: `src/test/java/io/github/hwainhwang/sentinel/documentation/DocumentationTest.java`, `src/test/resources/test-inventory/documentation.json`과 Python 행과 같은 9개 README·docs path
- Clojure: `test/sentinel_clj/documentation_test.clj`, `test/sentinel_clj/test_runner.clj`, `test/fixtures/test-inventory/documentation.edn`과 Python 행과 같은 9개 README·docs path

여기서 “Python 행과 같은”은 경로 문자열 `README.md`, `docs/index.md`, `docs/log.md`, `docs/architecture.md`, `docs/contracts.md`, `docs/backend.md`, `docs/operations.md`, `docs/privacy.md`, `docs/lineage.md`의 exact set을 뜻하며 glob으로 확장하지 않는다. 각 행을 concrete path로 펼쳐 UTF-8 byte order, 각 path 뒤 trailing NUL 한 개이고 final LF가 없는 `build/t26/stage/<repository>.paths`로 먼저 file·directory sync한다. Empty·absolute·dot component·LF·NUL·leading colon·duplicate와 해당 행 밖 path는 거부한다.

실행 위치: 각 `SENTINEL_*` owning child repository. `<T25_REPOSITORY_HEAD>`에는 그 repository의 T25 exact commit SHA를 넣는다.

실행: `<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py stage-exact --repository . --task T26 --phase docs --base-head <T25_REPOSITORY_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --manifest <workspace>/build/t26/stage/<CURRENT_REPOSITORY>.paths`

실행: `<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py commit-prepared --repository . --task T26 --phase docs --prepared-receipt <PREPARED_RECEIPT> --prepared-receipt-sha256 <PREPARED_RECEIPT_SHA256> --base-head <T25_REPOSITORY_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --expected-message "docs: complete SENTINEL knowledge bundle (요구사항-36,37)"`

각 commit은 T25 exact child HEAD의 single child이고 changed path·mode·blob과 resulting tree가 prepared receipt와 같아야 한다. Partial resume은 T25 HEAD·empty index·exact working set 또는 같은 HEAD·exact staged receipt이면 `stage-exact`가 채택하고, expected single child commit·clean tree이면 `commit-prepared`가 durable completion을 채택한다. 그 밖의 HEAD, partial index, 다른 message·path·mode·blob·tree에서는 모든 남은 Git mutation을 0으로 중단한다. Commit 뒤 status가 clean이어야 한다. 문서만 바뀐 저장소도 단계 6의 자기 명령을 실행한다. T28 SPEC CI에는 SPEC 명령만, 각 runtime CI에는 해당 runtime 명령만 넣고 sibling credential 없이 실행한다.

### T27: 5개 실행 저장소의 self CRAP·fresh strict mutation

**충족 요구사항:** 요구사항-33..요구사항-35, 요구사항-44, 공통규칙-03, 공통규칙-08

**파일:**

- 생성: 5개 실행 저장소 root의 `sentinel.config.json`, `self-quality-oracle.json`, `self-quality-commit.json`
- 생성: `SENTINEL_PY/tests/self_quality/test_self_quality.py`, `SENTINEL_PY/tests/fixtures/self_quality/{inventory,mutation-negative}.json`
- 생성: `SENTINEL_TS/test/self_quality/self-quality.test.ts`, `SENTINEL_TS/test/fixtures/self_quality/{inventory,mutation-negative}.json`
- 생성: `SENTINEL_GO/internal/selfquality/self_quality_test.go`, `SENTINEL_GO/testdata/self_quality/{inventory,mutation-negative}.json`, `SENTINEL_GO/{self-quality-modules.json,upstream/bridge-owned-files.json,test-inventory/self-quality.json}`
- 생성: `SENTINEL_JAVA/src/test/java/io/github/hwainhwang/sentinel/selfquality/SelfQualityTest.java`, `SENTINEL_JAVA/src/test/resources/fixtures/self-quality/{inventory,mutation-negative}.json`, `SENTINEL_JAVA/{self-quality-modules.json,upstream/bridge-owned-files.json}`, `SENTINEL_JAVA/src/test/resources/test-inventory/self-quality.json`
- 생성: `SENTINEL_CLJ/test/sentinel_clj/self_quality_test.clj`, `SENTINEL_CLJ/test/fixtures/self-quality/{inventory,mutation-negative}.edn`, `SENTINEL_CLJ/{self-quality-modules.json,upstream/bridge-owned-files.json}`, `SENTINEL_CLJ/test/fixtures/test-inventory/self-quality.edn`
- 수정: `SENTINEL_CLJ/test/sentinel_clj/test_runner.clj`
- 생성: `SENTINEL_SPEC/self-quality-matrix.json`, `SENTINEL_SPEC/tools/run_self_quality.py`, `SENTINEL_SPEC/tests/test_self_quality_driver.py`
- 생성: `SENTINEL_SPEC/tests/contracts/{self-quality-attempt,self-quality-matrix,self-quality-oracle,self-quality-inventory,self-quality-mutation-negative,self-quality-modules,bridge-owned-files,self-quality-commit,self-quality-receipt,t25-join-receipt,self-quality-seal}.schema.json`
- 생성: VCS 밖 owner-only `build/t27/{attempt.lock,attempt-sequence.json}`, `build/t27/attempts/<20-digit-sequence>/{attempt,runtime-registry,t25-join-receipt,self-quality-receipt,oci-executor-session,seal}.json`, `build/t27/attempts/<20-digit-sequence>/{artifacts,install,runtime-roots,project-workspaces,stage}/`
- 수정: production code와 test·lock은 fresh gate에서 발견된 실제 mutant·CRAP 초과를 줄이는 최소 범위만 변경
- 수정: 각 `docs/log.md`

**받는 것:** T25 conformance, T26 문서 bundle, 5개 완성 CLI

**주는 것:** 각 도구의 main과 배포되는 first-party backend bridge production 전체가 CRAP raw 8.0 이하·N/A 0·fresh in-scope mutant 1개 이상·전부 killed로 통과한 독립 증거

`run_self_quality.py new-attempt`는 `build/t27/attempt.lock`의 cross-process exclusive lock 안에서 durable `attempt-sequence.json`을 1 증가시킨다. Sequence exact shape는 `{"version":"sentinel-t27-attempt-sequence-v1","lastAllocated":"<uint64>"}`이고 existing attempt directory high-water보다 작을 수 없다. Overflow와 rollback을 거부하고 zero-padded 20자리 sequence의 새 `attempts/<sequence>/`를 no-replace mode `0700`으로 만든다. `attempt.json` exact body는 `version="sentinel-t27-attempt-v1"`, sequence, absolute root, sorted six `{repository,absoluteRoot,startingHead,sourceManifestSha256}`, matrix blob digest와 `executorLockSha256`다. `attemptSha256`은 파일 안에 넣지 않고 canonical file 전체의 외부 SHA-256으로만 다룬다. T25 receipt는 iteration attempt의 입력이 아니며 final seal 때 현재 source manifest와 exact join한다. 모든 JSON은 `additionalProperties=false`, canonical JSON+final LF다. Allocator는 durable write 뒤 stdout에 `{"version":"sentinel-attempt-allocation-v1","sequence":"<20 digits>","attemptRecord":"<absolute attempt.json>","attemptSha256":"<64 hex>"}` 한 줄만 쓴다. 이후 command는 이 direct path·digest만 사용하고 current pointer를 만들거나 재조회하지 않는다. 이전 attempt directory, registry, artifact, install, receipt와 stage list는 수정·삭제·재사용하지 않는다. `run_cross_runtime.py --attempt-record`는 immutable record와 directory ownership·mode·starting HEAD·source manifest·executor lock을 검증한 뒤 해당 unique root만 채운다.

- [ ] **단계 1: 독립 oracle·commit SSoT와 실패하는 driver test 작성**

사람이 작성한 `self-quality-oracle.json`과 언어별 fixture에 independent inventory와 직접 계산 oracle을 먼저 고정한다. Sentinel 출력으로 expected fixture를 자동 생성하는 command는 만들지 않는다. Python·TypeScript 외부 package와 Go·Java·Clojure의 byte-identical unmodified upstream file은 dependency·vendor로 분류하고 lock·admission으로 검증한다. Go·Java·Clojure patch가 추가하거나 한 줄이라도 수정한 file은 전체 file을 `bridge-owned-files.json`의 first-party `backend-bridge` module에 넣는다. Patch hunk와 manifest가 다르거나 main·bridge 어느 production file도 분류되지 않으면 실패한다. Self gate는 module별 source inventory 누락, CRAP 8 초과, coverageUnknown, 0 mutant, non-killed 상태와 무단 제외를 모두 거부한다.

Runtime의 `self-quality-commit.json` schema는 exact object `{"version":1,"paths":[{"path":"...","reason":"..."}]}`이다. `paths`는 UTF-8 byte order로 정렬하며 path는 repository-relative existing regular file, reason은 1..256 Unicode scalar의 한 줄 문자열이다. Directory·glob·절대 path, duplicate, `.git`, `.sentinel`, `build`, receipt·artifact·registry는 거부한다. 고정 생성물과 `docs/log.md`를 먼저 기록하고 이후 실제 수정 production·test·lock file을 이유와 함께 추가한다. Driver는 manifest 자체, working-tree 전체 changed set, staged set과 commit changed set을 이 SSoT에서 파생한 exact path array와 비교한다.

열한 개 schema는 JSON Schema draft 2020-12, `additionalProperties=false`, sorted unique array, bounded string과 lowercase digest를 강제한다. Clojure inventory와 mutation-negative EDN은 safe reader로 data-only logical object를 만든 뒤 같은 canonical JSON model과 schema로 검증한다. Count와 fraction integer는 모두 leading-zero 없는 nonnegative decimal string으로 기록한다. 최소 exact field는 다음과 같다.

|schema|필수 root와 nested field|
|---|---|
|attempt|`version`, `sequence`, `root`, `repositories[{repository,absoluteRoot,startingHead,sourceManifestSha256}]`, `matrixSha256`, `executorLockSha256`; whole-file `attemptSha256`은 file 밖 allocation record에만 존재|
|matrix|`version`, `repositories[{repository,configPath}]`, `modules[{moduleId,runtime,productionManifestSha256}]`|
|oracle|`version`, `moduleResults[{moduleId,callables[{callableId,complexity,coveredUnits,totalUnits,coverageBasis,crapNumerator,crapDenominator}],mutationCounts}]`|
|inventory|`version`, `moduleId`, `productionPaths`, `testPaths`, `callableIds`, `sourceManifestSha256`|
|mutation-negative|`version`, `cases[{caseId,rawState,expectedNormalizedState,expectedExit,expectedFailureCode}]`; normalized 값은 공통 9개 상태 또는 unknown raw용 JSON null만 허용. Stryker `NoCoverage` raw는 `uncovered`, unknown raw는 null·`backendError`이며 normalized record를 만들지 않음|
|modules|`version`, `modules[{moduleId,kind,productionManifestSha256}]`|
|bridge-owned-files|`version`, `upstreamCommit`, `patchSha256`, `modules[{moduleId,files[{path,sha256}]}]`|
|commit|`version`, `paths[{path,reason}]`|
|t25-join-receipt|`version`, `t27AttemptPath`, `t27AttemptSha256`, `t25AttemptPath`, `t25AttemptSha256`, `t25ReceiptPath`, `t25ReceiptSha256`, `parentT27AttemptSha256`, `repositories[{repository,t27SourceManifestSha256,t25SourceManifestSha256}]`, `joined=true`; whole-file digest는 file 밖 command output에만 존재|
|receipt|`version`, `attemptSha256`, `matrixSha256`, `runtimeRegistrySha256`, `executorLockSha256`, `ociExecutorSessionSha256`, `t25JoinReceiptSha256`의 iteration JSON null 또는 final lowercase digest, `sources`, 두 `buildArtifactManifestSha256`, `modules[{moduleId,resultSha256,callableCount,coverageUnknownCount,maxCrapNumerator,maxCrapDenominator,mutationCounts,unauthorizedExclusionCount,passed}]`, `sourceUnchanged`, `allPassed`; mutationCounts는 공통 9개 상태 exact key set이고 whole-file receipt SHA-256은 file 밖 command output에만 존재|
|seal|`version`, `sequence`, `attemptPath`, `attemptSha256`, `matrixSha256`, `runtimeRegistrySha256`, `executorLockSha256`, `ociExecutorSessionSha256`, `selfQualityReceiptSha256`, `t25JoinReceiptPath`, `t25JoinReceiptSha256`, `t25ReceiptPath`, `t25ReceiptSha256`, `repositories[{repository,startingHead,sourceManifestSha256,stageListSha256,pathCount,stagedBlobManifestSha256,expectedCommitTreeManifestSha256,commitMessage}]`; whole-file seal SHA-256은 file 밖 command output에만 존재|

각 `sentinel.config.json`은 design 2.4 routing SSoT다. Python·TypeScript는 first-party main module 하나, Go·Java·Clojure는 main과 `*-bridge` 두 module을 선언하고 language, relative root, exhaustive production·test inventory, non-empty argv test·coverage·prepare command, coverage report, generated output과 backend selection을 exact schema로 채운다. Committed `self-quality-matrix.json`은 workspace-relative child repository path, 다섯 runtime registry key·repo-relative config path와 8개 module ID·expected production inventory digest만 sorted exact set으로 가지며 machine-specific absolute root와 starting HEAD를 금지한다. New-attempt가 이를 현재 workspace에 descriptor-safe resolve해 absolute roots·six starting HEAD·matrix blob digest를 immutable `attempt.json`에 넣는다. Driver는 module마다 oracle callable ID set, independent inventory callable ID set과 actual result callable ID set의 missing·extra·duplicate를 exact 비교한다. Set이 같아야 각 callable의 complexity, coveredUnits, totalUnits, coverageBasis와 reduced CRAP numerator·denominator를 row-by-row 비교하며 한 callable이나 coverage unit이 빠져도 module을 실패시킨다. Driver는 각 original repo를 owner-only `<attempt-root>/project-workspaces/<repository>/`에 byte·mode 보존 snapshot한 뒤 production·test·config manifest를 원본과 join한다. Installed registry argv는 `check --project <snapshot> --config <snapshot>/sentinel.config.json --module <id> --strict --format json`을 `shell=False`로 실행하고 `.sentinel`, cache와 output은 snapshot 내부 승인된 writable root에만 만든다. 실행 후 snapshot의 protected manifest와 original manifest를 다시 비교한다. Original repository에 state·cache·output을 만들거나 repo-local bin, source dist, PATH와 sibling import를 추측하면 실패한다.

- [ ] **단계 2: driver production 부재 RED 확인**

실행 위치: `SENTINEL_SPEC`

실행: `scripts/uv.sh run pytest tests/test_self_quality_driver.py -q`

기대: test collection과 fixture parse는 성공하고 `tools/run_self_quality.py` production entry 부재 때문에 실패함. Dependency failure나 test 0개는 RED 근거가 아님

- [ ] **단계 3: attempt allocator·driver 최소 구현과 unit GREEN**

Driver는 attempt allocation·record 검증, matrix/config/oracle parse, runtime registry identity join, eight-module invocation, result semantic gate, source three-way identity, privacy scan과 stage/commit verifier를 구현한다. `run`은 T27 attempt의 executor lock digest와 `run_cross_runtime.py prepare`가 같은 attempt 안에 no-replace 기록한 OCI session의 binary·socket·image identity를 다시 검증한다. Iteration `--record-result`는 `t25JoinReceiptSha256=null`을 요구한다. Final `--require-pass --fresh`는 `--t25-join-receipt` path와 `--t25-join-receipt-sha256`을 필수로 받고 attempt·parent·여섯 source digest를 실행 전 다시 join하며, 다르면 module invocation 0이다. 여덟 module과 두 build가 모두 끝난 뒤에만 OCI 두 digest와 join digest를 포함한 `self-quality-receipt.json`을 만들고 canonical file 전체 SHA-256을 path와 함께 stdout으로 반환한다. File 내부에 자기 digest field를 넣지 않는다. Negative fixtures는 fake result를 성공으로 주입하지 않고 real parser·semantic gate를 호출한다. Stryker `NoCoverage`는 `uncovered`로 normalize하고 unknown raw는 record를 만들지 않은 채 전체 `backendError`로 끝낸다. Go·Java·Clojure task-specific test inventory와 Clojure runner inventory도 여기서 연결한다.

실행: `scripts/uv.sh run pytest tests/test_self_quality_driver.py -q`

기대: rollback·path swap·attempt reuse·registry mismatch·CRAP 초과·0 mutant·survivor·Stryker NoCoverage→uncovered·unknown raw→backendError·timeout·compile/runtime error·pending·ignored·toolError·unauthorized exclusion·source mutation 반례와 valid synthetic case가 모두 통과함

- [ ] **단계 4: unique attempt에서 최초 actual self gate RED 확인**

실행 위치: `SENTINEL_SPEC`

실행: `scripts/uv.sh run python tools/run_self_quality.py new-attempt --workspace <workspace> --attempt-root <workspace>/build/t27`

기대: stdout의 `<T27_ATTEMPT_RECORD>`와 `<T27_ATTEMPT_SHA256>`을 아래 iteration 세 command에 그대로 대입함

실행: `scripts/uv.sh run python tools/run_cross_runtime.py prepare --workspace <workspace> --attempt-record <T27_ATTEMPT_RECORD> --attempt-sha256 <T27_ATTEMPT_SHA256> --executor-lock clean-install-executor.lock.json --reproducible-builds 1`

실행: `scripts/uv.sh run python tools/run_self_quality.py run --attempt-record <T27_ATTEMPT_RECORD> --attempt-sha256 <T27_ATTEMPT_SHA256> --matrix self-quality-matrix.json --record-result`

기대: 여덟 module의 actual gate 결과를 pass·fail 어느 쪽이든 unique receipt에 durable 기록함. 하나라도 실패하면 단계 5로 가고, 최초 실행부터 모두 통과하면 인위적 실패를 만들지 않고 단계 6으로 간다. 기본 JSON은 privacy-safe HMAC callable·mutant token과 defect kind만 담고, 현재 위치는 명시적 local-details resolver로만 확인함

- [ ] **단계 5: 매번 새 attempt로 최소 test·code 개선 반복**

각 실패는 먼저 killing test 또는 작은 behavior-preserving refactor로 해결한다. Equivalent·invalid mutant를 ignore해서 통과시키지 않는다. Backend operator 문제면 backend finding과 재현 fixture를 만든 뒤 operator 의미를 임의 변경하지 않고 T07·T11·T15·T19·T23 admission으로 돌아간다. Timeout budget 확대만으로 killed를 만들지 않는다. Production·test·lock을 바꿀 때마다 단계 4의 세 command를 다시 실행하되 첫 command가 다음 sequence와 fresh root를 만들게 한다. Driver는 이전 registry·artifact·install·receipt path가 새 attempt에 나타나면 실행 전 실패한다.

- [ ] **단계 6: fresh self quality 최종 통과 확인**

먼저 아래 여섯 묶음을 각 owning child repo에서 전부 실행한다. 하나라도 실패하면 final attempt를 할당하지 않는다.

- SPEC: `scripts/uv.sh sync --locked --offline && scripts/uv.sh run pytest -q`
- Python: `scripts/uv.sh sync --locked --offline && scripts/uv.sh run pytest -q`
- TypeScript: `scripts/npm.sh ci --offline && scripts/node.sh --tool tsc -- --noEmit --project tsconfig.json && scripts/node.sh --tool vitest -- --run`
- Go: `scripts/go.sh --offline mod verify && scripts/go.sh --offline test ./... -count=1 && scripts/go.sh --offline vet ./...`
- Java: `/usr/bin/bash scripts/verify-dependencies.sh && scripts/mvn.sh -o -B -ntp verify`
- Clojure: `/usr/bin/bash scripts/verify-dependencies.sh && scripts/clojure.sh --offline -M:test`

여섯 suite가 통과하면 현재 source manifest를 봉인하는 final T27 attempt를 먼저 할당한다. 그 다음 같은 source에서 fresh T25 attempt를 새 sequence로 할당하되 `parentT27AttemptSha256`을 final T27 digest로 넣어 두 attempt의 계보를 고정한다. 두 번 build, fault harness와 전체 verify를 다시 실행하고 새 `conformance-receipt.json`을 만든다. 이 receipt의 parent digest와 sorted six `sourceManifestSha256`가 final T27 attempt의 digest·여섯 값과 exact join해야 한다. 이어 같은 T27 attempt에서 두 번 build·격리 설치와 fresh self gate를 실행한다. 검사 대상 bridge가 자신을 backend로 재귀 호출하지 않게 같은 candidate build의 별도 read-only companion identity를 registry에서 고정한다. 어느 경계에서든 source manifest가 바뀌면 다음 invocation과 receipt write는 0이다.

실행 위치: `SENTINEL_SPEC`

실행: `scripts/uv.sh run python tools/run_self_quality.py new-attempt --workspace <workspace> --attempt-root <workspace>/build/t27`

기대: stdout의 direct `<FINAL_T27_ATTEMPT_RECORD>`와 `<FINAL_T27_ATTEMPT_SHA256>`을 이후 모든 T27 command에 고정

실행: `scripts/uv.sh run python tools/run_cross_runtime.py new-attempt --workspace <workspace> --attempt-root <workspace>/build/t25 --parent-t27-attempt-sha256 <FINAL_T27_ATTEMPT_SHA256>`

기대: stdout의 direct `<FINAL_T25_ATTEMPT_RECORD>`와 `<FINAL_T25_ATTEMPT_SHA256>`을 아래 T25 command에 고정

실행: `scripts/uv.sh run python tools/run_cross_runtime.py prepare --workspace <workspace> --attempt-record <FINAL_T25_ATTEMPT_RECORD> --attempt-sha256 <FINAL_T25_ATTEMPT_SHA256> --executor-lock clean-install-executor.lock.json --reproducible-builds 2`

실행: `scripts/uv.sh run python tools/run_cross_runtime.py prepare-fault-harnesses --workspace <workspace> --attempt-record <FINAL_T25_ATTEMPT_RECORD> --attempt-sha256 <FINAL_T25_ATTEMPT_SHA256>`

실행: `scripts/uv.sh run python tools/run_cross_runtime.py verify --workspace <workspace> --attempt-record <FINAL_T25_ATTEMPT_RECORD> --attempt-sha256 <FINAL_T25_ATTEMPT_SHA256>`

기대: verify stdout의 `<FINAL_T25_CONFORMANCE_RECEIPT>` absolute path와 `<FINAL_T25_CONFORMANCE_RECEIPT_SHA256>` whole-file digest를 다음 join과 seal에 그대로 대입

실행: `scripts/uv.sh run python tools/run_self_quality.py join-t25 --attempt-record <FINAL_T27_ATTEMPT_RECORD> --attempt-sha256 <FINAL_T27_ATTEMPT_SHA256> --t25-receipt <FINAL_T25_CONFORMANCE_RECEIPT> --t25-receipt-sha256 <FINAL_T25_CONFORMANCE_RECEIPT_SHA256>`

기대: T25 receipt의 `parentT27AttemptSha256`이 `<FINAL_T27_ATTEMPT_SHA256>`과 같고, T25 attempt sequence가 이전 T25 receipt보다 크며, 여섯 source manifest가 T27 attempt와 exact인 경우만 `t25-join-receipt.schema.json`으로 검증한 receipt를 no-replace 생성함. Stdout의 `<FINAL_T25_JOIN_RECEIPT>` absolute path와 `<FINAL_T25_JOIN_RECEIPT_SHA256>` whole-file digest를 아래 run과 seal에 고정. Parent가 null·다른 digest이거나 같은 source의 과거 receipt면 self-quality 실행 0

실행: `scripts/uv.sh run python tools/run_cross_runtime.py prepare --workspace <workspace> --attempt-record <FINAL_T27_ATTEMPT_RECORD> --attempt-sha256 <FINAL_T27_ATTEMPT_SHA256> --executor-lock clean-install-executor.lock.json --reproducible-builds 2`

실행: `scripts/uv.sh run python tools/run_self_quality.py run --attempt-record <FINAL_T27_ATTEMPT_RECORD> --attempt-sha256 <FINAL_T27_ATTEMPT_SHA256> --matrix self-quality-matrix.json --t25-join-receipt <FINAL_T25_JOIN_RECEIPT> --t25-join-receipt-sha256 <FINAL_T25_JOIN_RECEIPT_SHA256> --require-pass --fresh`

기대: stdout 한 줄의 `<FINAL_T27_SELF_QUALITY_RECEIPT>` absolute path와 `<FINAL_T27_SELF_QUALITY_RECEIPT_SHA256>` whole-file digest를 seal에 그대로 대입

실행: `scripts/uv.sh run pytest tests/test_self_quality_driver.py -q`

기대: 모든 first-party production callable exact CRAP `<= 8`, coverageUnknown 0, 8개 module 각각 in-scope mutant `>= 1`, `killed == inScope`, survived·uncovered·timedOut·compileError·runtimeError·pending·ignored·toolError와 무단 제외 0, unknown raw 0, 두 build byte-identical, original과 snapshot source 불변

- [ ] **단계 7: 저장소별 exact commit**

Self-quality result와 `.sentinel`은 commit하지 않는다. Fixed set은 다음과 같고 runtime은 `self-quality-commit.json`의 path+reason set에 실제 개선 file을 더한다.

- SPEC: `self-quality-matrix.json`, `tools/run_self_quality.py`, `tests/test_self_quality_driver.py`, `tests/contracts/{self-quality-attempt,self-quality-matrix,self-quality-oracle,self-quality-inventory,self-quality-mutation-negative,self-quality-modules,bridge-owned-files,self-quality-commit,self-quality-receipt,t25-join-receipt,self-quality-seal}.schema.json`, `docs/log.md`
- Python: `sentinel.config.json`, `self-quality-oracle.json`, `self-quality-commit.json`, `tests/self_quality/test_self_quality.py`, `tests/fixtures/self_quality/inventory.json`, `tests/fixtures/self_quality/mutation-negative.json`, `docs/log.md`
- TypeScript: `sentinel.config.json`, `self-quality-oracle.json`, `self-quality-commit.json`, `test/self_quality/self-quality.test.ts`, `test/fixtures/self_quality/inventory.json`, `test/fixtures/self_quality/mutation-negative.json`, `docs/log.md`
- Go: `sentinel.config.json`, `self-quality-oracle.json`, `self-quality-commit.json`, `self-quality-modules.json`, `upstream/bridge-owned-files.json`, `internal/selfquality/self_quality_test.go`, `testdata/self_quality/inventory.json`, `testdata/self_quality/mutation-negative.json`, `test-inventory/self-quality.json`, `docs/log.md`
- Java: `sentinel.config.json`, `self-quality-oracle.json`, `self-quality-commit.json`, `self-quality-modules.json`, `upstream/bridge-owned-files.json`, `src/test/java/io/github/hwainhwang/sentinel/selfquality/SelfQualityTest.java`, `src/test/resources/fixtures/self-quality/inventory.json`, `src/test/resources/fixtures/self-quality/mutation-negative.json`, `src/test/resources/test-inventory/self-quality.json`, `docs/log.md`
- Clojure: `sentinel.config.json`, `self-quality-oracle.json`, `self-quality-commit.json`, `self-quality-modules.json`, `upstream/bridge-owned-files.json`, `test/sentinel_clj/self_quality_test.clj`, `test/sentinel_clj/test_runner.clj`, `test/fixtures/self-quality/inventory.edn`, `test/fixtures/self-quality/mutation-negative.edn`, `test/fixtures/test-inventory/self-quality.edn`, `docs/log.md`

실행 위치: `SENTINEL_SPEC`

실행: `scripts/uv.sh run python tools/run_self_quality.py prepare-stage-lists --attempt-record <FINAL_T27_ATTEMPT_RECORD> --attempt-sha256 <FINAL_T27_ATTEMPT_SHA256> --matrix self-quality-matrix.json`

기대: Git mutation 0. Final attempt의 `stage/`에 six repository `.paths`를 no-replace 생성함. 각 file은 UTF-8 byte order의 nonempty repo-relative literal path마다 trailing NUL 한 개를 붙인 bytes이고 final LF는 없음. Empty·absolute·`.`·`..` component·NUL·LF·leading colon pathspec magic·duplicate, seal source에 없는 path와 fixed set 또는 runtime SSoT 밖 path는 실패

실행: `scripts/uv.sh run python tools/run_self_quality.py seal --attempt-record <FINAL_T27_ATTEMPT_RECORD> --attempt-sha256 <FINAL_T27_ATTEMPT_SHA256> --matrix self-quality-matrix.json --self-quality-receipt <FINAL_T27_SELF_QUALITY_RECEIPT> --self-quality-receipt-sha256 <FINAL_T27_SELF_QUALITY_RECEIPT_SHA256> --t25-join-receipt <FINAL_T25_JOIN_RECEIPT> --t25-join-receipt-sha256 <FINAL_T25_JOIN_RECEIPT_SHA256> --t25-receipt <FINAL_T25_CONFORMANCE_RECEIPT> --t25-receipt-sha256 <FINAL_T25_CONFORMANCE_RECEIPT_SHA256>`

기대: `seal.json`이 sequence, immutable attempt·registry·self-quality receipt·fresh T25 receipt·T25 join receipt, executor lock·OCI session, six source manifest·stage-list·staged-blob manifest·expected commit-tree manifest·commit message를 canonical no-replace로 고정함. Join receipt가 T25 receipt와 T27 attempt의 parent digest 및 six source digest를 exact 연결하고, self-quality receipt의 join·executor lock·OCI session digest가 argument·attempt·실제 file과 같아야 함. Seal file 내부에는 자기 digest를 넣지 않고 canonical whole-file SHA-256을 stdout으로만 반환함. 이후 attempt 내부 write는 0

Seal command는 stdout에 absolute `<FINAL_T27_SEAL>` path와 `<FINAL_T27_SEAL_SHA256>` whole-file digest를 한 줄로 반환한다. Commit driver는 canonical repository 순서 `SENTINEL_SPEC`, `SENTINEL_PY`, `SENTINEL_TS`, `SENTINEL_GO`, `SENTINEL_JAVA`, `SENTINEL_CLJ`를 사용한다. 매 repository 직전 read-only cohort 검사가 상태를 세 가지 중 하나로만 분류한다.

- A `uncommitted`: HEAD가 sealed attempt starting HEAD, index empty, working changed set·bytes가 sealed source와 exact다.
- B `staged`: HEAD가 starting HEAD, cached path·mode·blob bytes가 sealed stage·staged-blob manifest와 exact하고 unstaged·untracked change가 0이다.
- C `committed`: HEAD가 starting HEAD의 exact single child, parent·message·changed path·blob과 resulting tree manifest가 seal과 exact하고 worktree가 clean하다.

그 밖의 HEAD, partial index, merge commit, byte·mode·message 차이가 하나라도 있으면 모든 남은 Git mutation은 0이다. A만 해당 owning child repository를 `cwd`로 T01 `commit_inventory.py stage-exact` library boundary에 sealed absolute path, task T27, repository별 phase와 starting HEAD를 넘긴다. Driver는 cached path·mode·blob·tree가 T27 seal과 T01 prepared receipt 양쪽에 exact일 때만 B로 전이한다. B만 같은 T01 boundary의 `commit-prepared`에 prepared receipt path·whole-file SHA-256, starting HEAD와 exact message `test: enforce self quality gate (요구사항-33..35,44)`를 넘겨 원자 commit·검증·completion을 수행한 뒤 C로 전이한다. C는 건너뛴다. Raw `/usr/bin/git add`나 porcelain commit을 driver가 직접 호출하지 않는다. 이 검사를 repository마다 다시 수행하므로 stage 뒤 crash와 일부 commit 뒤 restart를 같은 command로 이어간다.

실행 위치: `SENTINEL_SPEC`

실행: `scripts/uv.sh run python tools/run_self_quality.py verify-commit-cohort --attempt-record <FINAL_T27_ATTEMPT_RECORD> --attempt-sha256 <FINAL_T27_ATTEMPT_SHA256> --seal <FINAL_T27_SEAL> --seal-sha256 <FINAL_T27_SEAL_SHA256> --matrix self-quality-matrix.json`

실행: `scripts/uv.sh run python tools/run_self_quality.py resume-commits --attempt-record <FINAL_T27_ATTEMPT_RECORD> --attempt-sha256 <FINAL_T27_ATTEMPT_SHA256> --seal <FINAL_T27_SEAL> --seal-sha256 <FINAL_T27_SEAL_SHA256> --matrix self-quality-matrix.json`

실행: `scripts/uv.sh run python tools/run_self_quality.py verify-committed --attempt-record <FINAL_T27_ATTEMPT_RECORD> --attempt-sha256 <FINAL_T27_ATTEMPT_SHA256> --seal <FINAL_T27_SEAL> --seal-sha256 <FINAL_T27_SEAL_SHA256> --matrix self-quality-matrix.json`

기대: 각 new commit이 single-parent이고 parent가 sealed attempt starting HEAD, changed path·mode·blob과 resulting tree manifest가 seal과 exact하며 six worktree가 clean함. Final T25·T27 receipt의 source digests가 각 commit의 corresponding blobs와 일치하고 terminal `resume-commits` 재실행은 Git mutation 0

### T28: 6개 private GitHub repo·CI·deploy key·branch protection

**충족 요구사항:** 요구사항-01, 요구사항-02, 요구사항-33, 요구사항-35, 요구사항-39..요구사항-44, 요구사항-52, 요구사항-53, 공통규칙-01, 공통규칙-05..공통규칙-07

**파일:**

- 생성: 6개 저장소 `.github/workflows/ci.yml`
- 생성: 각 저장소 `scripts/verify_release_inputs.*`와 privacy artifact allowlist 검사, 5개 실행 저장소 `ci-runtime.lock.json`, `.github/approval-signers.json`, repo-local JavaScript action `.github/actions/{approval-verifier,ci-project-key-launcher,spec-deploy-key-checkout}/{action.yml,index.js}`
- 생성: approval verifier의 실제 Node entrypoint를 호출하는 Python `tests/ci/test_approval_verifier.py`, TypeScript `test/ci/approval-verifier.test.ts`, Go `internal/ci/approval_verifier_test.go`, Java `src/test/java/io/github/hwainhwang/sentinel/ci/ApprovalVerifierTest.java`, Clojure `test/sentinel_clj/ci_approval_verifier_test.clj`
- 생성: `SENTINEL_SPEC/tools/{credential_launcher,private_repo_orchestrator}.py`, `tests/{test_credential_launcher,test_private_repo_orchestrator}.py`, `tests/fixtures/private-repo-api/{repository-pages.jsonl,branch-protection.jsonl,secrets.jsonl,workflow-runs.jsonl,crash-matrix.json,t28-commit-files.json}`
- 수정: `SENTINEL_SPEC/tools/github_api_transport.py`, `tests/test_github_api_transport.py`, `pyproject.toml`, `uv.lock`
- 생성: VCS 밖 owner-only `build/private-repo/{plan.json,create-ledger.json,operator-credential-profile.json,ssh-session-record.json}`, `build/private-repo/approvals/<repository-id>-<main-sha>.json`, `build/private-repo/stage/<repository>.paths`
- 수정: 6개 `README.md`, 5개 runtime `docs/operations.md`, 6개 `docs/log.md`
- 외부 상태: `hwain-ai/SENTINEL_*` private repo 6개, read-only deploy key 5개, runtime별 HMAC secret, branch protection

**받는 것:** T27의 모든 local gate 통과 commit

**주는 것:** 충돌 없이 만든 private remotes, reproducible clean CI와 최소 권한 cross-repo SPEC 접근

GitHub 운영 계약은 다음 선택으로 고정한다.

1. GitHub CLI를 사용하지 않는다. T01의 no-redirect CPython transport가 control, secret, Actions와 release REST의 유일한 HTTP client다.
2. `hwain-ai` 개인 private repository를 유지한다. 이 범위에서는 GitHub Environment required reviewer를 강제할 수 없으므로 Environment는 selected branch `main`과 secret 보관만 담당한다. Workflow dispatch 직전에 별도 local typed approval receipt를 요구한다. Enterprise organization으로 이전하면 required reviewer를 추가할 수 있지만 v1 scope는 바꾸지 않는다.
3. Raw key bytes는 GitHub secret에 직접 넣지 않는다. Deploy private key와 32-byte HMAC을 먼저 base64url-no-padding ASCII secret value로 바꾸고 repo-local action이 strict decode한다. GitHub API의 `encrypted_value`는 이 ASCII value를 sealed-box 암호화한 ciphertext의 standard Base64 ORIGINAL alphabet과 padding 형식이다.

Secret 이름과 값 계약은 exact하다.

|용도|이름|값 wire 형식|
|---|---|---|
|SPEC deploy private key|`SENTINEL_SPEC_DEPLOY_KEY_B64`|canonical OpenSSH private bytes와 final LF를 base64url-no-padding한 ASCII|
|active stable project key E2|`SENTINEL_PROJECT_HMAC_E2`|32 raw byte를 base64url-no-padding한 exact 43 ASCII|
|temporary project key E1|`SENTINEL_PROJECT_HMAC_E1_<INTENT>`|`INTENT`는 16 random byte의 uppercase 32-hex, 값은 exact 43 ASCII|

T28 시작 전에 SPEC은 PyNaCl 1.6.2 wheel과 transitive CFFI artifact를 `uv.lock`에 exact digest로 추가하고 offline 재설치를 확인한다. Transport는 GitHub public-key endpoint의 key ID와 32-byte public key를 typed parse하고 PyNaCl sealed box로 위 ASCII secret value를 암호화한다. Ciphertext는 standard Base64 ORIGINAL alphabet과 required padding으로 canonical encode하며 `encrypted_value`에 그 문자열만 넣는다. Raw secret과 내부 base64url value는 request body에 들어가지 않는다. Fixture는 base64url inner value와 standard Base64 ciphertext를 서로 바꾸면 실패한다.

각 `ci.yml`은 top-level `name: sentinel-ci`, exact `run-name: sentinel-provision-${{ inputs.intent_id }}`와 required job의 `jobs.required.name: sentinel-ci / required`를 고정한다. Push·PR에서 empty intent로 생긴 display title은 완료 근거로 쓰지 않고 workflow dispatch에서만 nonempty 128-bit intent와 exact title을 요구한다. Initial secretless bootstrap check-run의 `name`이 literal `sentinel-ci / required`인지 API로 확인한다. Branch protection exact payload는 `required_status_checks={strict:true,checks:[{context:"sentinel-ci / required",app_id:<BOOTSTRAP_APP_ID>}]}`, `enforce_admins=true`, `required_pull_request_reviews={dismiss_stale_reviews:true,require_code_owner_reviews:false,required_approving_review_count:0,require_last_push_approval:false}`, `restrictions=null`, `required_linear_history=true`, `allow_force_pushes=false`, `allow_deletions=false`, `block_creations=false`, `required_conversation_resolution=true`, `lock_branch=false`, `allow_fork_syncing=false`다. `BOOTSTRAP_APP_ID`는 그 exact initial check-run의 unique check suite app ID를 durable plan에 고정하고 모든 readback에서 check-run name·context·app ID가 같은지 확인한다. 한 명뿐인 owner가 자기 PR을 승인할 수 없으므로 required approval count 1은 사용하지 않는다.

- [ ] **단계 1: remote·key·CI 상태기 실패 test 작성**

Orchestrator의 모든 GitHub REST 호출은 T01 lock과 `github_api_transport.py` blob digest를 먼저 검증하고 `Accept: application/vnd.github+json`, `X-GitHub-Api-Version: 2026-03-10`을 고정한다. Secret write도 같은 transport가 repository ID-bound Environment public-key GET, local sealed-box encryption, encrypted-secret PUT을 순서대로 수행한다. Write 직전과 직후 public key·key ID가 같은지 재조회하고 secret metadata의 environment·exact name·updated receipt를 확인한다. Production transport는 redirect 0이고 fake endpoint·test CA를 받지 않는다. Test-only profile만 loopback fake TLS를 사용해 endpoint, method, repository·environment·secret identity, header, sealed ciphertext field와 extra request 0을 검사한다. Deploy·HMAC plaintext canary는 HTTP request body, response, trace, log, temporary file, argv, environment, ledger와 artifact에 0건이어야 한다.

Operator token plaintext의 live 범위는 credential launcher가 `/dev/tty`에서 bounded-read해 여는 FD 3의 kernel pipe, orchestrator byte buffer와 transport의 각 허용 request `Authorization` header다. Python process memory와 kernel buffer의 완전한 zeroization은 보장하지 않고 best-effort overwrite와 process 종료에 의존한다. Token은 request body·response, child environment, redaction 뒤 trace·environment dump·log·temporary file·argv·ledger·cache·artifact에 영속되지 않아야 한다. Header는 trace 전에 redact하고 예상 endpoint request 수와 실제 Authorization header 수가 같아야 한다.

Transport·Git·SSH environment는 inherited environment를 지우고 command별 exact key·value allowlist로 새로 만든다. Transport credential은 FD 3으로만 받고 environment에는 넣지 않는다. Git에는 `GIT_CONFIG_NOSYSTEM=1`, `GIT_CONFIG_GLOBAL=/dev/null`, owner-only empty `HOME`, `GIT_TERMINAL_PROMPT=0`, 검증된 `GIT_SSH`, `GIT_SSH_VARIANT=ssh`, `SENTINEL_SSH_CONFIG`, exact expected repository·service, credential launcher가 만든 validated `SSH_AUTH_SOCK`와 fresh `GIT_TRACE2_EVENT`만 전달한다. Wrapper는 config path를 확정한 뒤 `exec -c`로 SSH environment를 비운다. Inherited `GIT_SSH_COMMAND`, loader, proxy, CA, locale, runtime startup/config, askpass와 ambient GitHub credential은 제거한다. Operation별 origin·SNI·redirect, TLS, trust-store, wrapper와 GitHub host-key policy를 호출 직전에 재검증하며 하나라도 다르면 GitHub/Git/SSH external call은 0이다.

Operator authentication은 ambient credential이 아니라 `credential_launcher.py`가 제공한다. `enroll --profile ../build/private-repo/operator-credential-profile.json`은 `/dev/tty`에서 operator SSH private key의 no-symlink absolute path를 받아 owner·mode `0600`·link count 1·public fingerprint와 GitHub registered fingerprint를 검증하고 profile에는 path identity digest와 public fingerprint만 저장한다. `run --profile ... -- <orchestrator argv>`는 매번 token과 같은 SSH key absolute path를 `/dev/tty`에서 다시 prompt한다. Opened descriptor의 current path identity digest·owner·mode·link count·public fingerprint를 profile과 다시 맞춘 뒤 pinned `ssh-agent`를 empty environment에서 띄우고 `ssh-add`에는 private key descriptor를 직접 전달한다. Token은 FD 3 pipe로만 준다. Orchestrator에는 validated agent socket과 non-secret session receipt만 전달하며 private key path·bytes·token은 argv·environment·plan·ledger에 넣지 않는다. Git은 exact SSH remote와 `IdentityAgent <validated-socket>`, `IdentityFile none`, `IdentitiesOnly yes`, pinned host key, proxy·forwarding·system config 0의 owner-only config만 쓴다. Launcher cleanup은 agent 종료와 socket absence를 확인하지만 process memory zeroization은 주장하지 않는다.

Accepted API credential은 classic personal access token 하나이며 `X-OAuth-Scopes`를 comma trim·중복 거부 뒤 순서와 무관한 set으로 parse한 결과가 exact `{repo, read:public_key, read:user}`여야 한다. `read:user`는 private profile data인 account plan을 mutation 없이 읽기 위한 최소 추가 scope다. Raw header 문자열의 순서는 신뢰하지 않는다. `admin:org`, `delete_repo`, `workflow`, package scope와 그 밖의 extra scope는 거부한다. 첫 repository create 전에 mutation-free preflight가 `/user`, 전체 `/user/keys`, API version, rate-limit와 token scope를 stable read하고 login·numeric ID, operator SSH fingerprint와 endpoint별 required permission matrix를 plan에 봉인한다. 같은 authenticated `/user`의 account plan을 typed parse해 personal private repository에서 protected branch와 Environment secret을 지원하는 GitHub Pro 이상인지 확인한다. Plan field가 missing·unknown·Free이거나 capability를 증명할 수 없으면 repository create를 포함한 external mutation은 0이다. 이후 existing repository는 API의 `permissions.admin=true`와 private invariant를 확인한다. 이 preflight로 증명할 수 없는 create 이후 권한은 각 첫 mutation의 intent와 post-readback으로 확인하며 실패한 external state를 자동 삭제하지 않는다.

각 child repository의 local·worktree config는 opened `.git/config` identity 아래 stage별 exact allowlist만 허용한다. `include.*`, `includeIf.*`, `url.*.insteadOf`, `url.*.pushInsteadOf`, `remote.*.pushurl`, `http.*`, `credential.*`, `core.sshCommand`, `core.hooksPath`, `protocol.*`, `submodule.*`, `alias.*`, `objects/info/alternates`와 replacement object가 하나라도 있으면 Git·network mutation 0이다. Inherited `GIT_PROXY_COMMAND`, `GIT_SSH`, `GIT_SSH_COMMAND`, `GIT_SSH_VARIANT`, `GIT_ASKPASS`, `GIT_COMMON_DIR`, `GIT_OBJECT_DIRECTORY`, `GIT_REPLACE_REF_BASE`와 external diff·filter environment를 제거하고 검증된 wrapper replacement만 넣는다. Orchestrator는 validated owner-only empty hooks directory를 만들고 config를 검사한 뒤에도 `/usr/bin/git -c core.hooksPath=<validated-empty-hooks> -c protocol.allow=never -c protocol.ssh.allow=always -c protocol.version=0`과 exact `GIT_SSH` wrapper만 호출한다. Exact repository object directory 밖의 alternate·namespace와 default `.git/hooks`의 executable도 허용하지 않는다. 첫 network read는 owner-only fresh `GIT_TRACE2_EVENT` descriptor에 기록해 actual child executable·argv·protocol·host가 `/usr/bin/git`, validated wrapper, `/usr/bin/ssh -F <validated-config>`의 exact SSH 경로이고 helper·proxy·hook·alternate·protocol-v2 extra argv가 0인지 검증한다. Trace raw bytes와 path는 ledger에 넣지 않고 검증 receipt digest만 fsync한 뒤 descriptor-relative로 지운다.

공통 `assertPrivateRepositoryInvariant`는 매 existing-repository 외부 변경 직전·직후와 모든 resume entry에서 transport로 `/user`의 login `hwain-ai`·numeric ID `166008093`, repository owner login·numeric ID, ledger의 exact repository ID와 `visibility=private`, `private=true`를 typed JSON으로 재조회한다. Pre 또는 resume mismatch이면 해당 호출을 포함한 external mutation은 0이다. 외부 성공 뒤 post readback에서 race·mismatch가 처음 보이면 uncertain receipt를 fsync하고 이후·보상 mutation 0으로 중단한다. Create 직전에는 exact name의 404 absence와 durable intent를 확인하고 `POST /user/repos`의 typed body `{"name":"<EXACT_NAME>","private":true,"description":"sentinel-intent:<INTENT_ID>","auto_init":false}`만 보낸다. Create response numeric repository ID를 fsync하기 전에는 다른 external mutation을 하지 않는다. 이미 존재하지만 현재 ledger·intent로 소유권을 증명하지 못한 repo는 덮어쓰거나 delete하지 않는다. Create 성공 뒤 crash는 owner·name·private·empty·description marker를 모두 재조회해 exact repo만 복구한다. ID를 fsync한 뒤 description을 정상값으로 바꾸고 exact SSH remote를 owning child repo에서 `/usr/bin/git remote add origin`으로만 추가한다.

`/user/keys`, deploy keys, Environment policy·secret, Actions runs·jobs와 release·asset처럼 set 전체를 판정하는 모든 collection은 공통 typed pagination reader만 사용한다. 첫 request는 exact endpoint에 `per_page=100&page=1`을 명시하고, RFC Link의 유일한 `rel=next`가 있을 때만 같은 `https://api.github.com`, 같은 repository ID-bound endpoint·filter, 다음 leading-zero-free page와 `per_page=100`인지 확인해 따른다. Cross-origin, endpoint·filter 변경, duplicate relation·URL·page, cycle, backward·skipped page, malformed Link, 1000 page 초과와 중간 non-200은 partial set을 반환하지 않고 실패한다. 모든 page item의 stable ID 중복을 거부하고 final page에 next가 없을 때만 canonical 전체-set digest를 만든다. 외부 mutation 전후에는 두 번 연속 같은 전체-set digest를 얻어야 하며 다르면 bounded retry 뒤 fail-closed한다. Single-object GET으로 collection absence나 uniqueness를 대신하지 않는다.

첫 push 전에 repository ID, clean local HEAD인 intended SHA, remote refs가 비었다는 관측과 unique intent를 `pushIntent`로 먼저 fsync한다. Resume이 `pushIntent`이면 같은 repository ID·private visibility·intent와 local intended SHA를 재확인한다. Remote refs가 여전히 비었으면 같은 push를 실행하고, remote에 `refs/heads/main` 하나만 있으며 exact intended SHA이고 tag·다른 branch가 0개면 push 외부 성공 뒤 ledger fsync가 끊긴 것으로 채택해 `mainPushed`로 전이한다. 그 밖의 ref나 SHA가 있으면 force push·delete·새 branch 생성 없이 중단한다. `mainPushed` 뒤 resume만 ledger의 `lastPushedSha`가 `origin/main`과 같고 remote SHA가 clean local HEAD의 ancestor일 때 fast-forward로 허용하며 force push와 history 교체를 거부한다. 그 밖의 existing repo는 사용자 확인 전 건드리지 않는다. Workflow lint와 local runner는 잘못된 SPEC digest, backend digest, artifact canary, `.sentinel/**` upload, read-write deploy key를 실패시킨다.

Workflow는 top-level exact `permissions: {actions: read, contents: read}`, 모든 third-party `uses:`의 full commit SHA pin, checkout `persist-credentials: false`를 요구한다. `actions: read`는 dispatch preflight가 current run ID·attempt·title·SHA의 uniqueness를 읽는 데만 쓰고 write permission은 0이다. `pull_request_target`, fork, candidate·PR·unprotected ref의 long-lived secret 접근을 모두 금지한다. 정상 PR과 candidate check는 vendored SPEC byte 비교와 local CSPRNG key로 secretless gate를 실행하며 Environment 요청, Environment secret context 참조, remote SPEC checkout과 secret-bearing action invocation이 0이다. Deploy key와 stable project key는 exact `sentinel-protected-main` Environment secret으로 두고 Environment deployment branch policy는 `main` 하나, tag·다른 branch policy와 required reviewer는 0개로 readback한다.

Secret-bearing `workflow_dispatch`는 `preflight`와 `quality-with-secrets` 두 job으로 나눈다. `preflight`는 Environment와 Environment secret 참조가 0이며 `event=workflow_dispatch`, `ref=refs/heads/main`, `github.sha=inputs.expected_sha`, numeric repository·workflow·run ID, committed workflow·세 action blob digest와 unique intent ID를 확인한다. `.github/approval-signers.json`은 enrolled operator Ed25519 public key text·native-computed fingerprint 하나와 signature namespace `sentinel-provision-v1`만 가지며 protected main의 T28 commit에 고정된다. Repo-local `approval-verifier`는 bounded base64url payload·signature를 strict decode하고 canonical payload, Ed25519 signature와 signer fingerprint를 실제 Node entrypoint에서 검증한다. 이어 short-lived `GITHUB_TOKEN`의 read-only Actions API로 current run이 exact workflow ID·head SHA·display title·intent에서 유일하고 `run_attempt=1`인지 확인한다. Prior 또는 concurrent replay로 같은 identity가 둘 이상이면 실패한다. `quality-with-secrets`는 `needs: preflight`, `if: needs.preflight.result == 'success'`일 때만 main-only Environment를 요청하고 exact `github.sha`를 detached checkout한다. Push·PR·tag event에서는 이 job condition이 false다. 따라서 dispatch 뒤 main ref가 전진하거나 unsigned·replayed input이면 secret job은 실행되지 않는다.

사람이 local TTY에 exact `APPROVE <repositoryId> <mainSha> <workflowBlobSha256> <intentId>`를 입력한다. Credential launcher는 exact object `{"version":"sentinel-provision-approval-v1","repositoryId":"<decimal>","mainSha":"<40hex>","workflowBlobSha256":"<64hex>","intentId":"<32hex>","signerFingerprint":"SHA256:<base64>"}`의 canonical JSON+final LF를 enrolled operator Ed25519 key와 namespace `sentinel-provision-v1`으로 agent-backed 서명한다. Receipt는 canonical payload·phrase digest·signature·public fingerprint를 담고 raw token·private key는 없다. Dispatch 전 repository ID, main ref, workflow blob, approval receipt digest, signature digest, random 128-bit lowercase hex intent와 expected run title `sentinel-provision-<INTENT>`를 `dispatchIntent`로 먼저 fsync한다. Exact POST body는 `{"ref":"main","inputs":{"expected_sha":"<MAIN_SHA>","expected_workflow_digest":"<SHA256>","approval_payload_b64":"<BASE64URL_CANONICAL_PAYLOAD>","approval_signature_b64":"<BASE64URL_SIGNATURE>","intent_id":"<INTENT>"}}`다. 단순 receipt digest나 임의 64-hex는 입력 계약이 아니다. HTTP 200 response의 numeric `workflow_run_id`, same-origin API `run_url`만 typed parse한 뒤 그 ID를 GET해 event·head branch·head SHA·workflow path, `run_attempt=1`, `display_title=sentinel-provision-<INTENT>`와 committed workflow digest를 검증하고 `dispatched` receipt를 fsync한다. POST 성공 뒤 receipt 전에 crash하면 full pagination에서 exact title·event·SHA·workflow ID·created window의 유일한 run만 채택하며 0개·2개 이상이면 재-dispatch하지 않고 중단한다. PR/tag policy는 fake fixture와 API readback으로 검증하고 T29 전 실제 PR·tag probe를 만들지 않는다. Initial push 때 activation variable은 absent이고 secret-bearing job은 0이다.

Fake GitHub API fixture는 repo create, branch-only Environment, deploy-key 등록, base64url secret 주입, activation variable, push, signed workflow dispatch, CI와 full branch-protection payload의 외부 성공 직후·ledger fsync 직후 crash를 각각 주입한다. 모든 phase에서 identity·private flag·API header·public key ID·sealed-box ciphertext·secret name·approval payload·signature·workflow identity·required check와 app ID·remote history divergence를 검증한다. 다섯 language-native approval test는 actual Node action entrypoint에 valid signature, digest-only, wrong signer·namespace·payload·SHA·intent, noncanonical base64url, duplicate run과 `run_attempt=2`를 넣어 secret job start 0을 확인한다. Collection은 pagination duplicate·cycle·partial read·race를 fail-closed한다. Token은 FD 3와 허용 Authorization header에만 나타나고 body·response·child environment·trace·log·file·argv·ledger·cache·artifact에는 0건이어야 한다. Environment·Git fixture는 loader, proxy, CA, locale, runtime startup, ambient Git·SSH·credential 변수를 주입해 transport·Git·SSH call 0을 확인한다. CI fixture는 `/proc/swaps` non-empty이면 secret generation·secret job·`/dev/shm` write가 0인지 먼저 검사한다. Swap 0일 때만 exact tmpfs leaf lifecycle과 crash cleanup을 시험한다. Successful run·job receipt는 exact `status="completed" AND conclusion="success"`; failure·cancelled·timed_out·action_required는 각 terminal conclusion으로 별도 기록하며 success로 채택하지 않는다. Pre·resume mismatch에서는 current·later external mutation 0, post mismatch에서는 후속·보상 mutation 0이다.

PAT 삭제 뒤 deploy key만 사라지고 secret metadata는 유지된 repair 정상·crash, API에 fingerprint field가 없는 응답의 local 이중 계산, secret 변경·duplicate key·wrong public key의 repair 거부도 같은 fake GitHub fixture에서 검증한다. `credentialRepaired` 뒤 old approval·run 재사용, unsigned repair dispatch, 새 key와 다른 action-derived fingerprint·SPEC checkout SHA·E2 receipt를 각각 주입하면 `continuityVerified` 전이와 T29 external mutation이 0이어야 한다.

- [ ] **단계 2: 상태기 RED와 clean CI 실패 확인**

실행 위치: `SENTINEL_SPEC`

실행: `scripts/uv.sh run pytest tests/test_private_repo_orchestrator.py -q`

기대: orchestrator module 부재로 실패

SPEC은 fresh pinned OCI environment에서 schema meta-validation, semantic oracle, 모든 golden, manifest·breaking-version, OKF·README command를 실행한다. 5개 runtime은 이 단계에서 workflow lint, exact command body, pinned OCI·runtime lock, vendored SPEC digest와 local unit·integration·acceptance·clean-install·conformance·self-quality를 실행한다. 아직 private remote와 deploy key가 없으므로 remote SPEC checkout·key cleanup의 성공을 이 단계에서 주장하지 않으며 단계 4에서 실제 검증한다. 현재 machine의 global package나 sibling checkout을 참조하면 실패해야 한다. 이 단계는 source를 stage하거나 commit하지 않고 local 검증만 수행한다. Exact commit은 단계 3에서 repository마다 한 번만 만든다.

- [ ] **단계 3: 상태기 GREEN과 local CI 고정**

`private_repo_orchestrator.py`는 shell 문자열 없이 absolute locked Git argv와 typed transport만 사용한다. Repository phase는 `intentRecorded -> repoCreated -> repoIdentified -> pushIntent -> mainPushed -> ciVerified -> protectionIntent -> protected`이고 runtime credential phase는 `environmentIntent -> environmentCreated -> environmentPolicyVerified -> materialIntent -> keyMaterialReady -> publicKeyRegistered -> deploySecretInstalled -> hmacSecretInstalled -> activationIntent -> activated -> dispatchIntent -> dispatched -> continuityVerified`다. 검증된 PAT-deletion 복구만 `continuityVerified -> credentialRepairIntent -> credentialRepaired -> repairDispatchIntent -> repairDispatched -> continuityVerified` side transition을 허용한다. 여섯 secretless bootstrap receipt, full protection readback과 exact workflow identity가 durable하기 전에는 첫 `environmentIntent`도 기록하지 않는다. Phase record는 owner·repository ID, environment ID·branch policy, activation receipt, canonical public key·locally computed fingerprint, deploy-key ID, secret metadata digest, epoch, intended·pushed commit, signed approval과 workflow run identity, pre·post invariant만 저장한다. Raw private key·HMAC·token·path는 저장하지 않는다. Protection, Environment branch policy, secret, activation, dispatch 또는 repair API 성공 뒤 ledger fsync가 끊기면 durable intent와 exact remote readback이 유일하게 일치할 때만 채택하고 extra policy·secret·rule·run 또는 모호한 identity에서는 update·delete·재-dispatch 0으로 중단한다.

실행: `scripts/uv.sh run pytest tests/test_private_repo_orchestrator.py -q`

기대: 모든 fake API crash·resume과 잘못된 identity 반례 통과, raw key canary가 test output·ledger·cache·artifact에서 0건

Workflow·orchestrator·test를 아래 exact allowlist로 각각 single-parent commit하고 그 parent가 T27 sealed final HEAD인지, `git diff-tree --no-commit-id --name-only -r -z`가 exact set인지, 여섯 tree가 clean인지 확인한다.

- SPEC: `.github/workflows/ci.yml`, `scripts/verify_release_inputs.py`, `tools/github_api_transport.py`, `tools/credential_launcher.py`, `tools/private_repo_orchestrator.py`, `tests/test_github_api_transport.py`, `tests/test_credential_launcher.py`, `tests/test_private_repo_orchestrator.py`, `tests/fixtures/private-repo-api/repository-pages.jsonl`, `branch-protection.jsonl`, `secrets.jsonl`, `workflow-runs.jsonl`, `crash-matrix.json`, `t28-commit-files.json`, `pyproject.toml`, `uv.lock`, `README.md`, `docs/log.md`
- 각 runtime: `.github/workflows/ci.yml`, `.github/approval-signers.json`, `.github/actions/approval-verifier/action.yml`, `.github/actions/approval-verifier/index.js`, `.github/actions/ci-project-key-launcher/action.yml`, `.github/actions/ci-project-key-launcher/index.js`, `.github/actions/spec-deploy-key-checkout/action.yml`, `.github/actions/spec-deploy-key-checkout/index.js`, 위 언어별 approval verifier test, 해당 `scripts/verify_release_inputs.*`, `ci-runtime.lock.json`, `README.md`, `docs/operations.md`, `docs/log.md`

사람이 관리하는 `t28-commit-files.json`은 여섯 repository key마다 위 brace와 “해당” 표현을 concrete repo-relative regular-file path로 하나씩 펼친 sorted exact array다. SPEC array는 이 fixture 자체도 포함하며 test가 task file 책임, actual changed set, 여섯 array의 missing·extra·duplicate와 glob·directory entry 0을 검사한다. Canonical repository 순서로 각 owning child를 `cwd`로 삼고 T01 `materialize-exact --task T28 --phase private-ci --base-head <T27_SEALED_REPOSITORY_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256> --source <SPEC_ROOT>/tests/fixtures/private-repo-api/t28-commit-files.json --selector <CURRENT_REPOSITORY> --output <STAGE_PATH>`로 UTF-8 byte order, path마다 trailing NUL 한 개의 `build/private-repo/stage/<repository>.paths`를 file·directory sync한다. T01 frozen registry가 이 source의 SPEC-relative path, 미리 승인한 canonical SHA-256과 여섯 selector array를 이미 고정한다. Launcher는 runtime cwd와 무관하게 exact SPEC source bytes를 registry와 대조하므로 runtime working tree가 source authority가 되지 않는다. 이어 T01 `stage-exact --task T28 --phase private-ci --base-head <T27_SEALED_REPOSITORY_HEAD> --predecessor-receipt <PREDECESSOR_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <PREDECESSOR_COMMITTED_RECEIPT_SHA256>`만 real index를 바꾸고 path·mode·blob·resulting tree receipt를 재검증한다. T01 `commit-prepared`에 그 prepared receipt path·whole-file SHA-256, 같은 base와 exact message `chore: add locked private CI gates`를 넘겨 원자 commit과 completion marker를 만든다. Resume은 T27 sealed HEAD·empty index·exact working set, 같은 HEAD·exact staged receipt, 그 HEAD의 exact single child commit·clean tree 세 상태만 각각 stage, commit, durable completion 채택으로 진행한다. 그 밖의 HEAD, partial index, 다른 path·mode·blob·tree·message에서는 현재와 남은 repository의 Git mutation 및 모든 GitHub external mutation을 0으로 중단한다. SPEC commit을 먼저 검증한 뒤 runtime을 처리하며 root workspace에서는 Git을 실행하지 않는다.

그 뒤에만 final local HEAD 6개, workflow blob SHA, JavaScript action digest와 orchestrator test digest를 plan input으로 읽는다. Dirty tree, unrelated T27 이후 commit 또는 identity mismatch면 plan 생성은 실패한다.

실행: `scripts/uv.sh run python tools/credential_launcher.py enroll --profile ../build/private-repo/operator-credential-profile.json`

실행: `scripts/uv.sh run python tools/credential_launcher.py run --profile ../build/private-repo/operator-credential-profile.json --ssh-session-record ../build/private-repo/ssh-session-record.json -- <workspace>/SENTINEL_SPEC/scripts/uv.sh run python tools/private_repo_orchestrator.py plan --owner hwain-ai --owner-id 166008093 --github-token-fd 3 --ledger ../build/private-repo/create-ledger.json --output ../build/private-repo/plan.json`

기대: external mutation 0, authenticated account plan이 personal private repository의 branch protection·Environment secret을 지원하는 GitHub Pro 이상이고, operator token bounded-FD preflight와 SSH FD·path·local·registered public fingerprint가 일치함. 여섯 T28 `committed.json`, exact final HEAD·workflow·JavaScript action digest, name·intended transition과 secret 0 bootstrap 순서를 담은 owner-only canonical plan을 file·directory sync와 no-replace rename으로 생성. Existing output은 byte-identical digest일 때만 채택한다. `apply`·`resume`·`verify`는 매 entry에서 clean tree, commit receipt, account plan, operator credential identity와 이 digest를 다시 계산하며 stale plan이면 GitHub·Git mutation 0으로 실패

- [ ] **단계 4: private repo와 최소 권한 credential 구성**

실행: `scripts/uv.sh run python tools/credential_launcher.py run --profile ../build/private-repo/operator-credential-profile.json --ssh-session-record ../build/private-repo/ssh-session-record.json -- <workspace>/SENTINEL_SPEC/scripts/uv.sh run python tools/private_repo_orchestrator.py apply --github-token-fd 3 --plan ../build/private-repo/plan.json --ledger ../build/private-repo/create-ledger.json`

Apply는 secret 0 bootstrap을 먼저 끝낸다. Repo create 뒤 Environment·repository secret·deploy key 목록과 `SENTINEL_SECRET_CI_ENABLED` variable이 모두 absent임을 API로 확인한다. `SENTINEL_SPEC`의 repository ID·clean local HEAD·empty remote refs를 `pushIntent`로 fsync하고 그 exact SHA만 `main`에 먼저 push한다. Push 직후 exact ref set과 default branch를 재조회하고 vendored input만 쓰는 secretless exact-SHA bootstrap CI를 통과시켜 `ciVerified`로 만든다. 그 뒤 5개 runtime도 같은 `pushIntent -> mainPushed -> ciVerified` 절차로 push하되 initial workflow는 vendored SPEC과 local CSPRNG key만 사용하고 Environment 요청·remote private SPEC checkout·secret context가 0이다. 따라서 runtime의 첫 CI가 아직 없는 private SPEC commit이나 credential에 의존하지 않는다.

여섯 secretless CI가 성공한 다음에만 위 full branch-protection payload를 `protectionIntent`로 fsync하고 typed API로 exact readback한다. Bootstrap run에서 얻은 check context와 App ID가 유일하지 않거나 payload field 하나라도 다르면 secret write 0이다. Local allowlist receipt, protected `origin/main` SHA, remote workflow blob·approval signer file과 세 local action digest가 같은 commit인지 확인한 뒤 repository phase를 `protected`로 만든다. 다섯 runtime 각각에 `environmentIntent`를 fsync하고 `sentinel-protected-main` Environment와 deployment branch policy `type=branch,name=main` 하나를 만든다. Required reviewer와 tag·다른 branch policy는 0개여야 한다. 개인 private repo 기능 한계 때문에 사람 승인은 GitHub pending deployment가 아니라 위 signed local approval receipt가 담당한다.

그 뒤에만 key 작업을 시작한다. 먼저 `/proc/swaps` header 외 entry가 0인지 검사하며 하나라도 있으면 secret generation·Environment secret write·secret job dispatch는 0이다. Swap 0일 때만 existing `/dev/shm`의 tmpfs·owner·mode·mount identity를 검증하고 runtime·epoch별 owner-only leaf를 `mkdirat` no-replace로 만든다. `/usr/bin/ssh-keygen`으로 각 runtime 전용 Ed25519 pair를 만들고 public key는 SPEC repo의 read-only deploy key로 등록한다. Canonical private key bytes는 final LF를 검증한 뒤 base64url-no-padding ASCII `SENTINEL_SPEC_DEPLOY_KEY_B64`로, 32-byte HMAC E2는 exact 43 ASCII `SENTINEL_PROJECT_HMAC_E2`로 sealed-box 암호화해 Environment API에 전송한다. CI action은 strict alphabet·length·canonical round-trip을 검증하고 deploy key를 decode해 file로 쓰지 않고 `ssh-add -` stdin에 pipe한다. Raw HMAC만 project-key launcher의 close-on-exec stdin envelope에 넣는다. Catch 가능한 종료에는 key file과 leaf를 descriptor-relative 제거·sync하고, SIGKILL 뒤 잔여가 없다고 가정하지 않는다.

Public key 등록 전에 runtime repository ID·canonical OpenSSH public key text·public fingerprint·key epoch, derivable unique deploy-key title과 두 target Environment secret의 pre-write metadata receipt를 `keyMaterialReady`로 fsync한다. Public key text는 비밀이 아니며 repair에 필요한 exact byte로 ledger에 남기고 private key는 남기지 않는다. GitHub deploy-key API에는 fingerprint field가 없으므로 response와 list readback에서는 exact `id`, canonical `key`, `title`, `verified`, `read_only`만 typed parse한다. 그 canonical `key` bytes의 fingerprint를 pinned `/usr/bin/ssh-keygen -lf <PUBLIC_KEY_FD_PATH> -E sha256`와 별도 native Ed25519 OpenSSH parser로 각각 계산하고 두 값과 ledger 값이 같은 경우에만 등록 뒤 SPEC repository ID·deploy-key ID·key digest·read-only 값을 `publicKeyRegistered`로 fsync한다. Runtime Environment deploy-secret write receipt를 `deploySecretInstalled`, stable E2 HMAC-secret write receipt를 `hmacSecretInstalled`로 각각 fsync한다. Resume은 다시 검증한 `/dev/shm` root FD 아래 entry, durable ledger intent와 typed remote inventory를 대조해 세 갈래로만 처리한다. `absent`는 workspace, exact title·canonical public key의 remote deploy key와 target Environment secret metadata가 모두 없고 target repository ID·Environment·secret names가 ledger와 같은 경우다. 새 generation·epoch를 만들 수 있지만 다른 remote resource는 건드리지 않는다. `exact-owned`는 존재하는 local workspace·remote deploy key·target secret metadata가 각각 ledger의 owner·mode·link count·marker·mount ID·device·inode·generation, unique title·canonical key·locally computed fingerprint·ID, pre-write 또는 post-write receipt와 모두 일치하고 unexpected duplicate가 0인 경우다. Verified reboot·power loss로 tmpfs generation이 사라진 remote-only 상태도 durable `keyMaterialReady`의 exact remote identity가 유일하면 여기에 포함한다. Exact local entry는 opened directory FD 아래 descriptor-relative cleanup과 parent directory sync를 끝내고, exact remote orphan은 invariant pre·post check 사이에서 ID로 revoke한 뒤 새 generation·epoch의 deploy key와 HMAC secret으로 rotate한다. Secret API 성공 뒤 ledger fsync가 끊겨 remote secret 값을 읽어 확인할 수 없는 경우도 exact repository ID·Environment·secret name·durable intent, pre-write 대비 metadata transition과 public key·key ID를 확인한 뒤 새 epoch로 overwrite하고 그 receipt만 채택한다. `ambiguous`는 path swap, duplicate entry·key, owner·identity·title·locally computed fingerprint·public key·key ID·receipt mismatch, unreadable state와 그 밖의 모든 경우이며 local unlink, remote revoke·overwrite와 새 secret 발급을 0으로 하고 중단한다.

Deploy key를 만든 classic PAT를 삭제하면 GitHub가 그 deploy key도 제거할 수 있다. 대응은 PAT 영구 보존, GitHub App으로 생성 주체 이전, 동일 public key의 검증된 재등록 세 가지다. V1은 새 권한 체계를 추가하지 않는 세 번째를 사용한다. T28 `resume`에서 ledger의 exact deploy-key ID만 사라졌고 두 번의 stable full-list readback으로 같은 title·canonical public key의 duplicate가 0이며, target Environment와 `SENTINEL_SPEC_DEPLOY_KEY_B64` secret metadata가 마지막 성공 receipt에서 바뀌지 않았고 protected-main 성공 증거가 존재할 때만 `credentialRepairIntent`를 먼저 fsync한다. 새로 입력받은 exact-scope PAT로 ledger의 canonical public key를 SPEC read-only deploy key로 다시 POST한다. API에서 새 key ID·canonical `key`·`read_only=true`·`verified`를 재조회하고 pinned ssh-keygen과 native parser가 같은 fingerprint를 계산해야 `credentialRepaired` receipt를 쓴다. Secret overwrite, HMAC 변경과 private key 재생성은 0이다. POST 성공 뒤 crash는 intent와 unique exact public key readback만 채택한다. 이어 새 intent를 포함한 signed local approval을 만들고 current main SHA에 `repairDispatchIntent`를 먼저 fsync한 뒤 protected-main workflow를 새 run ID로 dispatch한다. Job의 deploy action이 Environment private key에서 public fingerprint를 memory-only로 유도해 expected fingerprint와 맞추고 exact private SPEC commit checkout에 성공하며, active E2를 같은 fresh state에서 두 번 실행해 `repeated=true`를 만들어야 한다. Orchestrator가 새 deploy-key ID·key digest, action-derived fingerprint, SPEC checkout SHA, E2 receipt와 run·required job의 `status=completed`·`conclusion=success`를 한 `repairDispatched` receipt로 exact join한 뒤에만 `continuityVerified`로 돌아간다. 과거 CI·approval receipt 재사용은 실패한다. Secret metadata 변경·missing, duplicate·wrong public key, 기존 key가 아직 존재, receipt 불일치에서는 repair·delete·overwrite 0으로 중단한다. T29은 missing key 또는 repair 후 fresh continuity receipt 부재를 발견하면 자체 repair를 하지 않고 external release mutation 0으로 중단해 T28 `resume`을 먼저 요구한다. GitHub App 전환은 별도 보안 설계로 남긴다.

다섯 runtime이 `hmacSecretInstalled`이고 credential workspace cleanup receipt까지 durable한 뒤에만 repository Actions variable의 absent baseline과 exact intended value를 `activationIntent`로 fsync한다. Pinned-header API로 `SENTINEL_SECRET_CI_ENABLED=true`를 설정하고 exact repository ID·name·value를 재조회해 `activated`로 전이한다. Variable이 initial push 전에 존재하거나 secret·Environment 준비 전 true이고, extra·wrong value 또는 post-readback mismatch이면 secret job dispatch와 후속 mutation은 0이다.

실행: `scripts/uv.sh run python tools/credential_launcher.py run --profile ../build/private-repo/operator-credential-profile.json --ssh-session-record ../build/private-repo/ssh-session-record.json -- <workspace>/SENTINEL_SPEC/scripts/uv.sh run python tools/private_repo_orchestrator.py resume --github-token-fd 3 --plan ../build/private-repo/plan.json --ledger ../build/private-repo/create-ledger.json`

기대: crash가 있으면 exact durable phase와 remote state에서만 이어가고, terminal ledger이면 external mutation 0의 idempotent verify로 종료. 실패 시 이미 만든 repo·protection·Environment를 delete하거나 remote를 바꾸지 않으며 exact intendedSha·lastPushedSha를 보존

- [ ] **단계 5: 실제 CI·HMAC continuity·protection 통과 확인**

`SENTINEL_SPEC/.github/workflows/ci.yml`은 schema meta-validation, semantic oracle, golden, manifest digest, breaking-version, SPEC 자체 OKF·README와 `tests/test_private_repo_orchestrator.py`를 secretless로 실행한다. Workflow lint는 이 exact test command가 빠지거나 축약되면 실패시킨다. SPEC workflow는 E2·deploy secret과 `sentinel-protected-main` Environment를 요청하지 않는다. SPEC에는 runtime bootstrap·backend admission·self CRAP·self mutation을 요구하지 않는다. `test_cross_runtime*`는 T25와 T29의 clean local release orchestrator gate이며 default SPEC CI가 private sibling credential 없이 실행한다고 주장하지 않는다.

5개 runtime `ci.yml`의 protected-main path는 exact runtime bootstrap, locked install, unit·integration·acceptance·clean-install·conformance, Environment의 read-only deploy credential로 고정 SPEC checkout·vendored byte 비교, backend admission, self CRAP, fresh self mutation, privacy canary, OKF·README를 실행한다. Secret 설치 뒤 credential launcher가 repository마다 local typed approval phrase를 받아 receipt를 먼저 fsync하고, pinned numeric workflow ID에 exact `ref="main"` dispatch를 serialized로 요청한다. API가 반환한 run의 event·head branch·head SHA·workflow path/blob·attempt를 receipt와 대조한 다음만 성공 근거로 쓴다. Normal PR·candidate job은 Environment request와 secret launcher가 0이다. PR·tag rejection은 fixture와 policy readback으로 검증해 T29 resource를 미리 만들지 않는다. 각 job은 pinned Ubuntu OCI digest와 `ci-runtime.lock.json`을 검증하고 runtime checkout 뒤 deploy key가 file·agent·Git config에 남지 않는지 확인한다.

Stable E2 secret은 protected `main` exact-SHA provisioning CI 전용이다. Job은 먼저 `/proc/swaps`가 empty인지, existing `/dev/shm`이 expected tmpfs인지 검증하고 아니면 secret-bearing action 전에 실패한다. Repo-local `ci-project-key-launcher`는 `SENTINEL_PROJECT_HMAC_E2`의 exact 43-byte base64url input을 strict decode·canonical round-trip해 32 raw byte로 만들고 close-on-exec pipe의 project-key envelope로 quality CLI에 연속 두 번 준다. `spec-deploy-key-checkout`도 deploy secret을 decode해 canonical OpenSSH bytes와 final LF를 확인하고 private-key file 없이 `ssh-add -`에 pipe한다. Workflow/job env, generated `run` script, argv, Git config·file, cache·artifact에는 raw key를 넣지 않는다. 첫 run은 state initialize, 둘째는 same-key·same-epoch 결과와 `repeated=true`를 증명한다. Buffer overwrite는 best-effort이며 process memory zeroization은 주장하지 않는다. Raw HMAC file의 유일한 예외는 exact owner-only `/dev/shm` project state이고 job 뒤 descriptor-relative cleanup과 readable inventory scan을 요구한다.

Success·failure·cancelled·timeout과 catch 가능한 signal 모두에서 pipe와 state lock을 닫고 buffer overwrite를 best-effort로 시도한 뒤 process tree를 reap한다. `/dev/shm` state와 leaf를 descriptor-relative로 지우고 bounded readable inventory·logs·cache·artifact의 raw-key canary 0을 확인한다. Inventory 밖이나 권한 때문에 읽을 수 없는 filesystem absence는 주장하지 않는다. SIGKILL·restart에서는 durable cleanup identity가 exact인 orphan만 정리하고 ambiguous identity는 다음 secret job과 release를 차단한다. Orchestrator는 repository·run ID·job ID·workflow blob·commit SHA·runner type을 재조회한다. 성공 근거는 run과 모든 required job의 `status="completed" AND conclusion="success"`뿐이다. 다른 terminal conclusion은 cleanup receipt를 남겨도 quality success가 아니다. GitHub-hosted fresh VM 폐기는 검증된 API evidence가 아니라 보안 가정으로 기록한다.

E1→E2 rotation은 T25 fault matrix와 one-time protected-main provisioning acceptance에서만 실행한다. Orchestrator는 exact main SHA·workflow digest의 local approval receipt 뒤 temporary exact-name E1과 stable E2를 설치하고 `ref="main"` dispatch를 요청한다. Job token은 secret 관리 권한이 없고 cleanup을 맡지 않는다. Success·failure·cancelled·timeout·orchestrator crash resume 모두에서 exact repository ID·Environment·E1 name·durable intent가 일치할 때만 transport로 E1을 DELETE하고 GET 404를 확인하며 E2는 유지한다. Cleanup ambiguity나 다음 E2 receipt·epoch mismatch는 CI·release를 중단한다. Protected-main approval receipt, exact run identity, two-pass E2 result, deploy agent cleanup과 E1 absence가 모두 durable한 뒤에만 `continuityVerified`로 전이한다.

Artifact upload는 새로 만든 redacted result exact path만 허용하고 `.sentinel/**`, key, raw report, snapshot은 수집하지 않는다. 각 repo에서 default branch, full required-check protection payload, initial secretless bootstrap과 protected-main provisioning run의 exact commit·workflow identity·`status="completed"`·`conclusion="success"`를 구분해 기록한다. Environment ID, exact branch-only policy, reviewer 0개와 secret metadata도 다시 읽는다. Required check context·app ID·workflow digest가 다르면 release를 완료 처리하지 않는다.

- [ ] **단계 6: remote commit·CI identity 기록**

각 child repo에서 local HEAD, `origin/main`, exact workflow blob·run ID·status·conclusion, visibility, default branch, deploy-key read-only, full PR·check protection, Environment branch policy·reviewer 0개, local approval과 credential phase를 owner-only evidence에 기록한다. Source 변경은 하지 않으며 public evidence에는 private URL이나 key material을 넣지 않는다. 최종 `scripts/uv.sh run pytest tests/test_private_repo_orchestrator.py -q`를 다시 실행한다.

실행: `scripts/uv.sh run python tools/credential_launcher.py run --profile ../build/private-repo/operator-credential-profile.json --ssh-session-record ../build/private-repo/ssh-session-record.json -- <workspace>/SENTINEL_SPEC/scripts/uv.sh run python tools/private_repo_orchestrator.py verify --github-token-fd 3 --plan ../build/private-repo/plan.json --ledger ../build/private-repo/create-ledger.json --require-repository-phase protected --require-credential-phase continuityVerified`

기대: 6개 repository record가 모두 `protected`, full protection과 pinned check name·app ID가 exact, 5개 credential record가 `continuityVerified`, Environment는 main branch policy·reviewer 0개, activation variable은 true다. Current deploy key API의 canonical key에서 두 local verifier가 계산한 fingerprint가 ledger와 같고 read-only이며, PAT 삭제 repair를 거쳤다면 `credentialRepairIntent -> credentialRepaired -> repairDispatchIntent -> repairDispatched -> continuityVerified`가 새 deploy-key ID와 fresh protected-main run으로 exact join한다. Signed local approval, protected-main E2 continuity, swap-0 preflight, `/dev/shm` cleanup, readable inventory raw-key 0과 workflow `status="completed" AND conclusion="success"` receipt가 존재한다. 이어 같은 `resume`을 다시 실행했을 때 GitHub·Git·ledger mutation 0

### T29: SENTINEL_SPEC 1.0.0과 5개 runtime 1.0.0 release

**충족 요구사항:** 요구사항-01, 요구사항-02, 요구사항-33..요구사항-44, 요구사항-52, 요구사항-53, 공통규칙-01..공통규칙-10

**파일:**

- 생성: `SENTINEL_SPEC/tools/{release_orchestrator,release_asset_transport}.py`, `tests/{test_release_orchestrator,test_release_asset_transport}.py`, `tests/fixtures/release-api/{candidate.jsonl,release.jsonl,asset.jsonl,crash-matrix.json,t29-commit-files.json}`
- 검증: T25가 만든 5개 runtime `scripts/build-release.*`
- 수정: `SENTINEL_SPEC/VERSION`, `manifest.json`, `.github/workflows/ci.yml`, `README.md`, `docs/log.md`
- 수정: 6개 저장소 `scripts/verify_release_inputs.*`
- 수정: 5개 `spec-lock.json`, `vendor/sentinel-spec/**`, `README.md`, `docs/log.md`
- 수정: `SENTINEL_PY/pyproject.toml`, `uv.lock`
- 수정: `SENTINEL_TS/package.json`, `package-lock.json`
- 수정: `SENTINEL_GO/internal/version/version.go`
- 수정: `SENTINEL_JAVA/pom.xml`
- 수정: `SENTINEL_CLJ/resources/sentinel-version.edn`
- 생성: VCS 밖 owner-only `build/release-attempts/<ATTEMPT_ID>/{plan,ledger}.json`, `checkouts/<repositoryId>/{a,b}/`, `builds/<repositoryId>/{a,b}/`, `assets/<repositoryId>/`, `downloads/<repositoryId>/{draft-a,draft-b,published}/`, `receipts/`, `stage/<repository>.paths`
- 외부 상태: SPEC `spec-v1.0.0`, runtime `v1.0.0` annotated tag와 private GitHub release

**받는 것:** T28에서 성공한 private CI와 보호된 `main`

**주는 것:** 동일 SPEC digest를 쓰는 6개 private 1.0.0 release와 재검증 가능한 완료 증거

- [ ] **단계 1: release 상태기 RED test 작성**

Release checker는 candidate와 final 두 mode를 가진다. T28의 locked tool·command별 exact environment allowlist, direct GitHub TLS·system CA policy와 operator credential preflight를 같은 SSoT로 적용해 `/usr/bin/git`, `/usr/bin/ssh`, pinned CPython과 `github_api_transport.py`의 T01 digest를 먼저 확인한다. GitHub CLI는 설치하거나 실행하지 않는다. 모든 inherited environment를 지우고 T28 allowlist만 재구성하므로 `LD_*`, proxy, custom CA, locale, runtime startup/config, ambient GitHub·Git·SSH 변수와 `PATH`는 release child에도 0이다. Forced exact SSH remote와 strict pinned host-key·operator identity config만 쓴다. Control JSON은 `Accept: application/vnd.github+json`, upload request는 asset 표의 exact media type 또는 `SHA256SUMS.json`의 `application/json`, private binary download는 `Accept: application/octet-stream`으로 분리하고 control·upload request에는 `X-GitHub-Api-Version: 2026-03-10`을 명시한다. Binary·digest, operation별 API header·origin·SNI·redirect, TLS peer·CA, operator FD·public fingerprint, remote protocol 또는 config가 다르면 GitHub/Git/SSH external call 자체가 0이다.

공통으로 dirty tree, repository ID 불일치, 보호되지 않은 main, local·remote main 불일치, release 대상 exact commit SHA·workflow identity의 required CI non-success, privacy canary와 release asset allowlist 위반을 모두 거부한다. T28의 `assertPrivateRepositoryInvariant`를 매 branch push·PR create/merge·tag push·immutable-policy 변경·draft create·asset upload·publish 전후와 모든 resume entry에서 실행해 authenticated `/user` login `hwain-ai`·numeric ID `166008093`, repository owner login·numeric ID, ledger의 exact repository ID, `visibility=private`, `private=true`를 재조회한다. Pre·resume mismatch이면 해당 호출을 포함한 external mutation은 0이다. Post mismatch이면 uncertain receipt를 남기고 이후·보상 mutation과 다른 resource 수정·삭제는 0이다. SPEC branch는 VERSION·manifest·schema·golden digest를 검사하고, 5개 runtime branch만 SPEC lock·backend lock·operator digest를 검사한다. Candidate mode는 protected PR의 branch SHA·PR number·merge SHA와 main exact-SHA CI를 요구한다. Final mode의 release 결합 값은 release ID와 `tag_name`뿐이며 commit 증거는 local annotated tag object, Git ref API의 remote annotated tag object와 peeled commit SHA만 사용한다. 기존 tag가 있으면 GitHub가 무시하는 release `target_commitish`는 request에서 생략하고 response에 있어도 gate·ledger 근거로 사용하지 않는다. Branch의 단순 latest run은 release 근거가 아니다.

Fake GitHub API와 temporary Git fixture는 candidate 준비의 `candidateIntent -> branchPushed -> prCreated -> prMerged -> mainCiVerified -> candidate`와 release의 `candidate -> built -> localTagIntent -> localTagVerified -> tagPushIntent -> tagged -> draftCreateIntent -> draftCreated -> assetsVerified -> downloadsVerified -> publishIntent -> publishedVerified` 전이마다 외부 성공 직후와 ledger fsync 직후에 crash를 주입한다. Runtime cohort gate의 `runtimeBranchesReady -> preMergeT25Verified -> runtimeMergesComplete -> sixMainT25Verified`도 각 receipt fsync 경계에서 끊는다. Dirty·uncommitted tool implementation, stale candidate HEAD·orchestrator·test·workflow digest, incomplete runtime tuple, T25 이전 merge, per-branch T25의 전체 gate 오인, final six-main tuple mismatch와 runtime `candidate` 조기 전이는 모두 실패한다. 모든 pre·post·resume 지점에서 잘못된 user·owner·repository ID·private flag, API header, PR·CI·tag·release·asset identity, draft name·body intent marker·prerelease·author·immutable flag, 누락·추가 asset, immutable-policy false·404, download semantic·runtime command 실패, API timeout과 일부 repository만 published된 경우를 검증한다. T28의 credential·environment 반례도 plan·apply·resume·verify 각각에서 GitHub/Git/SSH external call 0을 요구한다. Pre·resume mismatch 뒤 mutation, post mismatch 뒤 force push, tag 이동·삭제, release delete·asset overwrite는 실패다. `starter` asset 정리만 아래의 exact owned 보상 전이에서 허용한다.

실행 위치: `SENTINEL_SPEC`

실행: `scripts/uv.sh run pytest tests/test_release_orchestrator.py tests/test_release_asset_transport.py -q`

기대: release orchestrator module 부재로 실패

- [ ] **단계 2: release 상태기 구현과 GREEN 확인**

`release_orchestrator.py`는 shell 문자열 대신 T01 lock과 T28 격리 profile을 검증한 absolute argv와 typed GitHub JSON response를 사용한다. `release_asset_transport.py`는 pinned repo-local CPython의 표준 `http.client`·`ssl`만 사용하고 system proxy loader나 automatic redirect를 쓰지 않는다. Validated trust-store로 minimum TLS 1.2·hostname verification을 켜고 T01의 control·upload·single-download-redirect state machine을 직접 적용한다. Upload는 validated regular-file descriptor의 exact size만 stream하고 201 JSON identity를 요구한다. Download는 owner-only no-replace descriptor로 stream·file sync·directory sync하고 expected size·SHA-256을 확인하며, signed Location과 query는 loggable object로 변환하지 않고 redirect request에 Authorization을 전달하지 않는다. `test_release_asset_transport.py`는 200·302 정상, 301·303·307·308·second redirect, wrong host·SNI·path·asset ID, credential forwarding, short·long body, digest mismatch, existing output과 exception·trace·ledger URL leakage를 모두 검사한다.

각 repository record에는 owner login·numeric ID, repository ID·private visibility receipt, candidate intent·branch SHA, PR identity, merged main SHA, exact workflow SHA·run ID·status·conclusion, intended tag, build command·`SOURCE_DATE_EPOCH`, asset allowlist·digest, annotated tag object·peeled SHA, immutable-policy receipt, draft name·body digest·unique intent marker·author ID·prerelease·immutable flag, release ID, downloaded semantic·6-command receipt와 phase를 둔다. GitHub asset digest는 exact `sha256:<64 lowercase hex>` 형식만 허용하고 state는 `uploaded`만 성공으로 인정한다. Global cohort record에는 다섯 pre-merge branch SHA·artifact digest·SPEC SHA tuple과 T25 receipt, 다섯 merged main SHA·SPEC SHA tuple과 final T25 receipt를 둔다. Raw credential, token, private URL과 secret path는 ledger에 기록하지 않는다. Candidate와 release phase는 owner-only temporary file sync, atomic rename, ledger directory sync 뒤에만 바꾼다. 모든 외부 변경과 resume은 identity·private invariant의 pre·post receipt가 있어야 한다. SPEC merge 전에는 clean local HEAD가 plan의 exact tool candidate HEAD여야 하고, merge 뒤에는 local·remote main, PR merge SHA, orchestrator·transport·test·workflow blob digest가 plan과 byte-identical해야 한다. 그 밖은 stale plan으로 external mutation 0이다.

Candidate resume은 repository ID와 unique intent를 먼저 확인한다. Branch push 뒤 ledger fsync 전이면 exact branch name·SHA를, PR create 뒤면 exact repository·base main·head branch SHA의 유일한 open 또는 merged PR을 채택한다. PR merge 뒤 fsync 전이면 remote main이 그 PR의 merge commit과 같고 GitHub API의 merged flag·merge SHA가 일치할 때 그 typed receipt를 T01 `adopt-merged-main`에 전달한다. 이 transaction이 local main ref와 HEAD symref를 함께 바꾼 뒤에만 main exact-SHA CI를 이어간다. SPEC은 main CI 뒤 fsync 전 exact workflow SHA·run ID·success를 재조회해 `candidate`로 전이한다. Runtime은 같은 재조회로 `mainCiVerified`까지만 회복하며, 다섯 merged SHA와 SPEC SHA의 final six-main T25 receipt가 exact일 때만 cohort를 `sixMainT25Verified`로 fsync하고 다섯 runtime을 함께 `candidate`로 전이한다. Remote main이 다른 commit으로 전진했거나 PR·cohort identity가 모호하면 reset·force push·새 PR 생성 없이 중단한다.

Resume은 phase와 실제 원격 상태를 양방향 대조하고 entry invariant를 먼저 통과한다. Immutable enable 전 baseline GET과 `immutablePolicyIntent`가 durable하면 baseline 404 뒤 현재 GET 200·`enabled=true`인 exact repository ID만 PUT 성공 뒤 fsync가 끊긴 것으로 채택한다. Baseline부터 enabled였고 receipt가 없으면 같은 idempotent PUT 뒤 HTTP 204와 GET readback을 다시 얻는다. Intent가 없거나 identity가 다르면 mutation 0이다. `localTagIntent` 뒤 local tag만 있으면 exact annotated object·candidate target·tagger·message를 채택해 `localTagVerified`로 전이하고, `tagPushIntent` 뒤 remote tag가 없으면 exact local object를 push한다. Remote tag만 관측되면 Git ref API의 annotated tag object ID·peeled candidate SHA를 확인하고 fresh temporary ref로 fetch한 object bytes가 intended local tag object와 같을 때만 local ref를 no-force 생성해 `tagged`로 회복한다. Local·remote가 모두 있으면 tag object ID와 peeled SHA가 각각 같아야 한다. 어느 경우든 release absence와 durable matching intent가 필요하다. `draftCreateIntent` 뒤 끊겼다면 별도 repository invariant가 exact이고 same release-list pre-state에서 exact `tag_name`, `name`, body digest와 `sentinel-intent:<ATTEMPT_ID>:<INTENT>` marker, `draft=true`, `prerelease=false`, `author.id=166008093`, `immutable=false`, asset 0개인 release가 정확히 하나일 때만 채택한다. Marker가 없거나 다른 draft가 하나라도 섞이면 create 재시도·채택·수정·삭제 0이다. Release response의 repository ID나 `target_commitish`는 요구하지 않는다. Existing asset은 fresh owner-only directory로 다시 받아 name·size·`state=uploaded`·digest가 allowlist와 같을 때만 채택하고 semantic·runtime receipt 없이는 `downloadsVerified`가 될 수 없다. `publishIntent` 뒤 끊겼다면 exact repository invariant·release ID·tag_name·name·body marker·asset set, `draft=false`, `prerelease=false`, `author.id=166008093`, `immutable=true`, policy `enabled=true`를 재조회하고 downloaded bytes를 다시 검증할 때만 `publishedVerified`로 회복한다. 모호하거나 다른 값은 원격 상태를 고치지 않고 중단한다.

실행: `scripts/uv.sh run pytest tests/test_release_orchestrator.py -q`

기대: 모든 crash·resume과 identity 반례 통과, release ledger와 test output에 secret·private URL·project source canary 0건

- [ ] **단계 3: SPEC candidate를 보호 PR로 main에 반영**

먼저 local-only `allocate --version 1.0.0 --attempt-root ../build/release-attempts`가 OS CSPRNG 128-bit lowercase hex `ATTEMPT_ID`와 별도 128-bit `INTENT`를 만들고 `build/release-attempts/<ATTEMPT_ID>/`를 owner-only no-replace로 생성한다. 이것은 아직 commit되지 않은 `release_orchestrator.py`에 허용하는 유일한 실행 mode다. 단계 2의 fake transport test가 이 mode의 network·Git process·Git ref mutation이 0이고, repository 밖에서는 지정한 attempt directory만 만드는지 먼저 증명해야 한다. Allocation은 candidate attempt receipt path와 whole-file SHA-256을 출력하며, T01 `commit-prepared`가 이 둘을 다시 검증한다. Plan과 ledger는 이 immutable attempt directory 안에서만 생성하며 mutable `current` pointer를 두지 않는다. Root directory의 owner·mode `0700`·link count·device·inode와 attempt ID를 plan에 봉인하고 모든 resume에서 descriptor-relative로 재검증한다. 실패한 attempt는 유지한다. 새 attempt로 바꾸는 `supersede`는 여섯 local·remote tag와 모든 remote release·asset이 없다는 두 번의 stable readback이 있을 때만 허용한다. 이전 ledger에는 replacement attempt ID·plan digest, 새 plan에는 predecessor ID·ledger digest를 각각 no-replace 기록해 양방향 join한다. 어느 repository에든 tag가 하나라도 생긴 뒤에는 supersede, re-plan, tag 이동·삭제, release·asset 삭제가 모두 금지되며 같은 attempt를 resume하거나 사람이 상태를 조사해야 한다.

Allocation 뒤 clean `origin/main`에서 unique intent를 포함한 `release/spec-v1.0.0-candidate-<INTENT>` ref를 T01 원자 commit tool로 만든다. 사람이 관리하는 `tests/fixtures/release-api/t29-commit-files.json`의 `spec-candidate` selector는 자기 path, `tools/release_orchestrator.py`, `tools/release_asset_transport.py`, `tests/test_release_orchestrator.py`, `tests/test_release_asset_transport.py`, `tests/fixtures/release-api/{candidate.jsonl,release.jsonl,asset.jsonl,crash-matrix.json}`, SPEC `scripts/verify_release_inputs.py`, `VERSION`, `manifest.json`, `.github/workflows/ci.yml`, `README.md`, `docs/log.md`를 sorted concrete path로 미리 고정한다. T01 frozen registry에는 이 source path·canonical SHA-256과 selector array가 T29 첫 RED 전에 이미 들어 있다. `materialize-exact`와 `stage-exact`가 만든 exact index를 `commit-prepared --target-ref`가 base `main`의 child commit으로 만들면서 candidate ref 생성과 `HEAD` 전환을 한 transaction으로 처리한다. CI exact command에 두 release test를 추가하고 workflow lint가 누락·축약을 거부하게 한다. Schema·golden·manifest·breaking-version·private-repo orchestrator test와 두 release test를 committed candidate HEAD에서 fresh 실행하고 tree가 clean인지 확인한다. 아직 branch push·PR·merge는 하지 않는다.

실행: `scripts/uv.sh run python tools/release_orchestrator.py allocate --version 1.0.0 --attempt-root ../build/release-attempts`

실행: `<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py materialize-exact --repository . --task T29 --phase spec-candidate --base-head <T28_SPEC_HEAD> --predecessor-receipt <T28_SPEC_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <T28_SPEC_COMMITTED_RECEIPT_SHA256> --source tests/fixtures/release-api/t29-commit-files.json --selector spec-candidate --output ../build/release-attempts/<ATTEMPT_ID>/stage/SENTINEL_SPEC.paths`

실행: `<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py stage-exact --repository . --task T29 --phase spec-candidate --base-head <T28_SPEC_HEAD> --predecessor-receipt <T28_SPEC_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <T28_SPEC_COMMITTED_RECEIPT_SHA256> --manifest ../build/release-attempts/<ATTEMPT_ID>/stage/SENTINEL_SPEC.paths`

실행: `<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py commit-prepared --repository . --task T29 --phase spec-candidate --base-head <T28_SPEC_HEAD> --predecessor-receipt <T28_SPEC_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <T28_SPEC_COMMITTED_RECEIPT_SHA256> --prepared-receipt <PREPARED_RECEIPT> --prepared-receipt-sha256 <PREPARED_RECEIPT_SHA256> --candidate-attempt <CANDIDATE_ATTEMPT_RECEIPT> --candidate-attempt-sha256 <CANDIDATE_ATTEMPT_RECEIPT_SHA256> --target-ref refs/heads/release/spec-v1.0.0-candidate-<INTENT> --expected-message "release: prepare SENTINEL_SPEC 1.0.0 candidate"`

실행: `scripts/uv.sh run pytest tests/test_schemas.py tests/test_config_safety.py tests/test_result_semantics.py tests/test_golden_vectors.py tests/test_manifest.py tests/test_breaking_version.py tests/test_vendor_spec.py tests/test_private_repo_orchestrator.py tests/test_release_orchestrator.py tests/test_release_asset_transport.py -q`

실행: `scripts/uv.sh run python tools/credential_launcher.py run --profile ../build/private-repo/operator-credential-profile.json --ssh-session-record ../build/private-repo/ssh-session-record.json -- <workspace>/SENTINEL_SPEC/scripts/uv.sh run python tools/release_orchestrator.py plan --version 1.0.0 --tool-candidate-head HEAD --tool-candidate-receipt <SPEC_CANDIDATE_COMMITTED_RECEIPT> --tool-candidate-receipt-sha256 <SPEC_CANDIDATE_COMMITTED_RECEIPT_SHA256> --github-token-fd 3 --private-repo-ledger ../build/private-repo/create-ledger.json --attempt ../build/release-attempts/<ATTEMPT_ID>`

기대: allocation 뒤 SPEC candidate commit과 branch가 exact receipt로 생성되고 HEAD가 그 branch를 가리킨다. 그 다음 plan command의 external mutation은 0이며, exact clean committed SPEC tool candidate HEAD·completion receipt·release orchestrator/test/workflow blob digest, 여섯 current protected-main base SHA·repository ID, SPEC-first candidate와 5개 runtime candidate, immutable-policy·download·publish·`publishedVerified` transition을 담은 owner-only canonical `plan.json`을 file·directory sync와 no-replace rename으로 생성한다. Existing output은 byte-identical digest일 때만 채택하고 dirty implementation, uncommitted file 또는 digest mismatch에서는 plan 생성에 실패한다.

SPEC candidate·PR·post-merge main CI는 모두 long-lived secret과 GitHub Environment 요청이 0인 contract-only workflow다. Protected PR merge request는 exact head SHA와 `merge_method="squash"`, canonical title·commit message를 사용한다. Response SHA가 base commit의 single-parent child이고 tree가 candidate branch tree와 같으며 remote main과 같은지 검증한다. 그 exact SHA에서 schema·golden·manifest·orchestrator gate가 성공한 exact workflow SHA·run ID만 SPEC release evidence로 기록한다. SPEC에는 quality CLI, E1·E2, repeated finding과 deploy-key continuity를 요구하지 않는다.

실행: `scripts/uv.sh run python tools/credential_launcher.py run --profile ../build/private-repo/operator-credential-profile.json --ssh-session-record ../build/private-repo/ssh-session-record.json -- <workspace>/SENTINEL_SPEC/scripts/uv.sh run python tools/release_orchestrator.py apply --github-token-fd 3 --attempt ../build/release-attempts/<ATTEMPT_ID> --through spec-candidate`

기대: `apply`가 clean tree와 exact tool candidate HEAD·blob digest를 먼저 재검증한 뒤 candidate branch push, exact head PR과 정상 merge를 수행한다. Remote merge receipt가 durable해진 뒤 T01 `adopt-merged-main`이 candidate tree와 같은 single-parent squash merge만 받아 local main ref와 HEAD를 한 transaction으로 복귀시키고, 그 후 protected-main exact-SHA CI를 수행한다. SPEC record만 `candidate`, runtime 5개는 `candidateIntent` 이전 또는 그 exact durable state, tag·release·asset mutation 0이다. Stale plan이면 GitHub·Git mutation 0이다.

아직 `spec-v1.0.0` tag나 release를 만들지 않는다. Runtime 호환 검증이 실패하면 같은 protected PR 절차의 후속 candidate로 고치고 ledger가 새 main SHA를 가리키게 할 수 있으므로 잘못된 immutable 1.0 release가 남지 않는다.

- [ ] **단계 4: 5개 runtime candidate를 보호 PR로 main에 반영**

각 runtime은 ledger의 exact SPEC merged main commit archive를 clean checkout으로 받고 manifest와 모든 file digest를 검증한 뒤 vendor한다. `spec-lock.json`을 같은 SPEC version·merged commit·intended tag·manifest digest로 갱신하고 runtime version, `scripts/verify_release_inputs.*`와 문서를 unique `release/v1.0.0-candidate-<INTENT>` branch에서 exact allowlist로 commit한다. Vendored bytes를 수동 편집하지 않는다.

Runtime version carrier는 Python `pyproject.toml`의 project version, TypeScript `package.json`의 package version, Go `internal/version/version.go`의 release constant, Java `pom.xml`의 project version, Clojure `resources/sentinel-version.edn`으로 하나씩 고정하고 모두 `1.0.0`으로 바꾼다. Python `uv.lock`과 TypeScript `package-lock.json`은 authoritative carrier에서 재생성되는 package-manager 사본일 뿐 별도 version SoT가 아니다. Java JAR의 `Implementation-Version`도 Maven build가 `pom.xml`에서 생성한다. 각 `scripts/verify_release_inputs.*`는 source carrier, installed package metadata, `doctor`의 SENTINEL version, actual quality result의 `sentinel.version`과 release asset manifest가 모두 같은지 검사한다. 다른 hard-coded version 선언, 누락, `latest`와 carrier 불일치는 candidate commit 전에 실패한다.

Runtime candidate commit allowlist는 다음과 같다. `vendor/sentinel-spec/**`의 concrete path set은 검증된 SPEC `manifest.json`에서만 만들고 extra·missing path를 거부한다.

- Python: `spec-lock.json`, `vendor/sentinel-spec/**`, `pyproject.toml`, `uv.lock`, `scripts/verify_release_inputs.py`, `README.md`, `docs/log.md`
- TypeScript: `spec-lock.json`, `vendor/sentinel-spec/**`, `package.json`, `package-lock.json`, `scripts/verify_release_inputs.mjs`, `README.md`, `docs/log.md`
- Go: `spec-lock.json`, `vendor/sentinel-spec/**`, `internal/version/version.go`, `scripts/verify_release_inputs.sh`, `README.md`, `docs/log.md`
- Java: `spec-lock.json`, `vendor/sentinel-spec/**`, `pom.xml`, `scripts/verify_release_inputs.sh`, `README.md`, `docs/log.md`
- Clojure: `spec-lock.json`, `vendor/sentinel-spec/**`, `resources/sentinel-version.edn`, `scripts/verify_release_inputs.sh`, `README.md`, `docs/log.md`

각 runtime의 변경을 만든 뒤 다음 세 명령을 해당 owning child repository에서 실행한다. `<CURRENT_REPOSITORY>`는 `SENTINEL_PY`, `SENTINEL_TS`, `SENTINEL_GO`, `SENTINEL_JAVA`, `SENTINEL_CLJ` 중 현재 하나이고, selector는 위 allowlist와 verified SPEC manifest에서 나온 concrete vendor path만 담는다.

실행: `<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py materialize-exact --repository . --task T29 --phase runtime-candidate --base-head <T28_RUNTIME_HEAD> --predecessor-receipt <T28_RUNTIME_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <T28_RUNTIME_COMMITTED_RECEIPT_SHA256> --source <workspace>/SENTINEL_SPEC/tests/fixtures/release-api/t29-commit-files.json --selector <CURRENT_REPOSITORY> --output <workspace>/build/release-attempts/<ATTEMPT_ID>/stage/<CURRENT_REPOSITORY>.paths`

실행: `<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py stage-exact --repository . --task T29 --phase runtime-candidate --base-head <T28_RUNTIME_HEAD> --predecessor-receipt <T28_RUNTIME_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <T28_RUNTIME_COMMITTED_RECEIPT_SHA256> --manifest <workspace>/build/release-attempts/<ATTEMPT_ID>/stage/<CURRENT_REPOSITORY>.paths`

실행: `<workspace>/SENTINEL_SPEC/scripts/run-spec-python.sh <workspace>/SENTINEL_SPEC/tools/commit_inventory.py commit-prepared --repository . --task T29 --phase runtime-candidate --base-head <T28_RUNTIME_HEAD> --predecessor-receipt <T28_RUNTIME_COMMITTED_RECEIPT> --predecessor-receipt-sha256 <T28_RUNTIME_COMMITTED_RECEIPT_SHA256> --prepared-receipt <PREPARED_RECEIPT> --prepared-receipt-sha256 <PREPARED_RECEIPT_SHA256> --candidate-attempt <CANDIDATE_ATTEMPT_RECEIPT> --candidate-attempt-sha256 <CANDIDATE_ATTEMPT_RECEIPT_SHA256> --target-ref refs/heads/release/v1.0.0-candidate-<INTENT> --expected-message "release: prepare <CURRENT_REPOSITORY> 1.0.0 candidate"`

기대: 각 runtime의 base main은 그대로이고 새 candidate ref와 HEAD 전환만 원자적으로 생긴다. Candidate completion receipt가 path·mode·blob·parent·tree·message·attempt intent를 고정하며, 다른 변경이나 partial index가 있으면 Git과 GitHub mutation 0으로 실패한다.

Orchestrator는 각 owning child repository를 `cwd`로 사용해 brace와 vendored manifest를 concrete path로 펼친 뒤 attempt의 `stage/<repository>.paths`에 UTF-8 byte order·trailing NUL로 no-replace 저장한다. Literal pathspec·NUL mode로 stage하고 cached path·mode·blob bytes와 commit changed path가 해당 allowlist와 같은지 검사한다. Resume은 base main HEAD·index empty·exact working set인 `uncommitted`, base의 exact single child candidate commit·clean tree인 `committed`만 허용하고 partial index·다른 HEAD는 Git mutation 0으로 중단한다. 다른 source, test, workflow, state, build output이 섞이면 branch push 0에서 실패한다.

먼저 각 branch에서 unit·integration·acceptance·clean-install·conformance·backend admission·self CRAP·self mutation의 독립 local gate를 통과시킨 뒤 exact branch SHA만 push한다. 그 SHA의 secretless CI가 성공하면 base `main`·exact head SHA의 PR을 만들되 merge하지 않는다. T25가 설치할 registry-compatible candidate artifact를 각 exact branch SHA에서 VCS 밖 owner-only no-replace path에 결정적으로 만들고 digest를 ledger에 fsync한다. 이 시점에는 어느 PR도 merge하지 않으며 branch별로 T25를 따로 실행하지 않는다. 다섯 exact branch SHA·artifact와 SPEC merged SHA·manifest가 모두 준비된 하나의 immutable tuple을 fsync해 cohort를 `runtimeBranchesReady`로 전이한다. 그 exact tuple에 대해 T25 전체 cross-runtime matrix를 한 번 실행하고 성공 receipt를 fsync해 `preMergeT25Verified`로 전이한다.

그 tuple이 성공한 뒤에만 T28에서 readback한 required-check `strict=true` 아래 서로 다른 다섯 repository의 exact head SHA protected PR을 protection 우회 없이 `merge_method="squash"`로 merge한다. 각 response merge SHA가 previous main의 single-parent child이고 tree가 PR head tree와 같으며 remote main과 같은지 확인한다. 이어 repository별 typed remote merge receipt를 T01 `adopt-merged-main --repository . --candidate-ref refs/heads/release/v1.0.0-candidate-<INTENT> --candidate-head <CANDIDATE_HEAD> --old-main <T28_RUNTIME_HEAD> --remote-merge-receipt <REMOTE_MERGE_RECEIPT> --remote-merge-receipt-sha256 <REMOTE_MERGE_RECEIPT_SHA256>`에 전달해 local main ref와 HEAD symref를 한 transaction으로 바꾼다. Candidate ref는 감사용으로 그대로 남긴다. 각 resulting main SHA의 secret-bearing CI는 main-only Environment, reviewer 0개와 T28 local typed approval receipt를 통과한 뒤 active stable E2를 trusted stdin launcher로 받는다. Fresh ephemeral state 하나에서 같은 commit·fixture·config를 두 번 실행하고 두 번째 `repeated=true`를 증명해야 한다. 다섯 merge와 exact-main-SHA CI가 모두 끝나면 각 main SHA의 registry-compatible artifact를 fresh VCS 밖 no-replace path에 다시 만들고 SHA·digest receipt를 fsync해 cohort를 `runtimeMergesComplete`로 전이한다. 그 final six-main SHA·artifact tuple로 T25 전체 matrix를 다시 통과시켜 `sixMainT25Verified`를 fsync한 뒤에만 각 runtime phase를 `candidate`로 만든다. Pre-merge 5-SHA tuple 또는 post-merge six-main tuple이 다르면 이미 merge한 main을 reset하지 않고 후속 protected candidate PR부터 다시 시작한다.

각 runtime의 정상 candidate·PR CI는 long-lived secret 접근과 `sentinel-protected-main` Environment 요청이 0이다. PR·candidate의 Environment 차단은 T28 fake fixture와 branch-policy readback으로 증명하며 실제 negative probe resource는 만들지 않는다. Protected-main exact-SHA CI는 `APPROVE <repositoryId> <mainSha> <workflowBlobSha256>` local TTY 입력으로 만든 owner-only receipt를 요구한다. 이는 단일 운영자의 수동 중단점이며 독립 승인이 아니라는 tradeoff를 기록한다. Failure·cancelled·timeout 때 protected-main JavaScript action이 pipe를 닫고 descriptor cleanup을 끝냈는지 확인하되 process memory·runner `INPUT_*` zeroization은 best-effort이고 release 증거로 세지 않는다. Raw key는 environment dump·generated script·argv·HTTP trace·cache·artifact·log와 T28의 exact in-job `/dev/shm` leaf `project.json` 밖 file에 0건이어야 한다. Job 종료·restart 뒤에는 T28의 verified owner-controlled readable inventory scan 0건과 run·required job 각각의 `status="completed" AND conclusion="success"` API receipt를 요구한다. GitHub-hosted fresh-VM isolation은 보안 가정으로 기록하며 inaccessible filesystem 전체의 absence를 주장하지 않는다. 다섯 runtime이 모두 같은 SPEC merged SHA·manifest를 가리키고 final six-main T25 receipt가 생기기 전에는 어느 tag도 만들지 않는다.

실행: `scripts/uv.sh run python tools/credential_launcher.py run --profile ../build/private-repo/operator-credential-profile.json --ssh-session-record ../build/private-repo/ssh-session-record.json -- <workspace>/SENTINEL_SPEC/scripts/uv.sh run python tools/release_orchestrator.py resume --github-token-fd 3 --attempt ../build/release-attempts/<ATTEMPT_ID> --through candidates`

기대: SPEC과 5개 runtime record가 모두 `candidate`, 같은 SPEC merged SHA·manifest를 참조하며 tag·release mutation 0

- [ ] **단계 5: 6개 deterministic asset과 release readiness 고정**

각 저장소 exact candidate SHA를 attempt의 `checkouts/<repositoryId>/{a,b}` clean detached checkout 두 개에 받고 pinned OCI·offline dependency input으로 같은 build를 두 번 실행한다. 5개 runtime의 `SOURCE_DATE_EPOCH`는 해당 candidate commit의 committer timestamp를 `/usr/bin/git show -s --format=%ct <SHA>`로 읽은 leading-zero 없는 decimal이며 plan에 봉인한 뒤 두 build에 같은 값으로 전달한다. SPEC은 T04 계약의 fixed mtime `1788307200`을 그대로 사용한다. 현재 시각이나 filesystem mtime은 사용하지 않는다. Build argv는 다음 exact 값이다.

|저장소|build argv|canonical asset 이름|content type|
|---|---|---|---|
|SPEC|`scripts/uv.sh run python tools/build_manifest.py --index --check manifest.json --archive-output <OUT> --receipt-output <RECEIPT>`|`sentinel-spec-1.0.0-<12hex>.tar`|`application/x-tar`|
|PY|`scripts/uv.sh run python scripts/build-release.py --output-directory <OUT_DIR>`|`sentinel_py-1.0.0-py3-none-any.whl`|`application/zip`|
|TS|`scripts/node.sh scripts/build-release.mjs --output-directory <OUT_DIR>`|`sentinel-ts-1.0.0.tgz`|`application/gzip`|
|GO|`/usr/bin/bash scripts/build-release.sh --output-directory <OUT_DIR>`|`sentinel-go-1.0.0-linux-amd64-<12hex>.tar.gz`|`application/gzip`|
|JAVA|`/usr/bin/bash scripts/build-release.sh --output-directory <OUT_DIR>`|`sentinel-java-1.0.0-linux-amd64-<12hex>.tar.gz`|`application/gzip`|
|CLJ|`/usr/bin/bash scripts/build-release.sh --output-directory <OUT_DIR>`|`sentinel-clj-1.0.0-linux-amd64-<12hex>.tar.gz`|`application/gzip`|

`<12hex>`는 완성된 asset byte SHA-256 앞 12자리다. Digest 이름을 쓰는 archive는 두 unique provisional build path에서 먼저 만들고 byte equality와 전체 digest를 계산한 다음에만 canonical hash-name으로 no-replace 게시한다. Python wheel과 npm tarball은 생태계 canonical filename을 유지하고 전체 digest는 `SHA256SUMS.json`에서 고정한다. 이 manifest 이름만 asset digest를 이름에 넣지 않는 명시적 예외다. 각 repository의 remote allowlist는 canonical asset 하나와 `SHA256SUMS.json` 두 파일뿐이다. Manifest는 schema version, repository ID, tag, candidate SHA, runtime `SOURCE_DATE_EPOCH` 또는 SPEC fixed mtime, asset name·size·`sha256:<64 lowercase hex>`·content type을 canonical JSON으로 기록하고 자기 자신은 포함하지 않는다.

SPEC tar는 T04와 같은 bare member layout으로 concrete distributable SSoT의 `VERSION`, `schemas/**`, `contracts/**`, `golden/**`와 staged `manifest.json`만 가진다. README와 enclosing root directory는 넣지 않는다. TypeScript tgz는 single root `package/`와 package manifest가 선언한 production file set만 가진다. Go archive는 single root `sentinel-go-1.0.0/` 아래 `bin/`과 `libexec/`만 가진다. Java·Clojure archive는 각각 single root `sentinel-<language>-1.0.0/` 아래 `bin/`, `lib/`, `libexec/`만 가진다. Directory mode는 `0755`, executable launcher는 `0755`, 나머지 regular file은 `0644`다. Python wheel은 wheel `RECORD`와 package allowlist를 검증한다. 모든 archive는 정렬된 member, 고정 timestamp·uid·gid·uname·gname을 사용하고 absolute·`..` path, duplicate, symlink, hardlink, device와 extra member를 거부한다.

두 build의 asset 이름·mode·bytes·SHA-256이 같아야 한다. Asset, build receipt와 `SHA256SUMS.json`은 source tree가 아니라 attempt의 `assets/<repositoryId>/`에 validated directory FD, same-filesystem no-replace atomic rename, file·directory sync로 게시한다. Existing file은 descriptor로 byte identity를 확인한 경우만 채택하고 overwrite·delete하지 않는다. Source tree는 계속 clean이어야 하며 project source canary, mutant replacement, snapshot, raw report와 `.sentinel` state byte는 asset·manifest 전체에서 0이어야 한다. SENTINEL package 자체의 정상 source·문서 문자열은 금지값으로 오판하지 않는다. Clean-install까지 통과하면 phase를 `built`로 fsync한다.

6개 모두 local HEAD·`origin/main`, exact-SHA CI, deterministic asset과 SPEC·backend lock이 일치한 뒤에만 tag 단계로 간다. `scripts/verify_release_inputs.*`는 이 조건과 privacy scan을 실제로 실행하며 test fixture로 우회할 수 없다. 첫 tag 전에 repository별 invariant와 immutable endpoint baseline GET을 수행하고 repository ID·baseline status·unique intent를 `immutablePolicyIntent`로 먼저 fsync한다. 그 다음 T01 transport로 request body 없는 `PUT /repos/hwain-ai/<NAME>/immutable-releases`를 보내 HTTP 204를 요구하고, 같은 endpoint GET의 HTTP 200·`enabled=true`를 typed parse해 receipt를 남긴다. Intent 없는 current 200, conflict, 404 또는 readback 불일치는 tag·draft·publish mutation 0으로 중단한다. 첫 publish 직전에도 여섯 endpoint가 모두 enabled인지 다시 확인한다.

- [ ] **단계 6: 상태기로 tag·private release·다운로드 재검증**

SPEC에는 exact merged main SHA를 가리키는 annotated `spec-v1.0.0`, 5개 runtime에는 각각 annotated `v1.0.0`을 만든다. Porcelain `git tag`를 직접 실행하지 않는다. 각 owning repository에서 T01 `tag-prepared --repository . --task T29 --phase release-tag --committed-receipt <MERGED_MAIN_ADOPTION_RECEIPT> --committed-receipt-sha256 <MERGED_MAIN_ADOPTION_RECEIPT_SHA256> --tag-ref refs/tags/<TAG> --expected-message "<EXACT_MESSAGE>"`만 실행한다. `<TAG>`는 SPEC `spec-v1.0.0` 또는 runtime `v1.0.0`이고 `<EXACT_MESSAGE>`는 SPEC `SENTINEL_SPEC 1.0.0` 또는 runtime `<REPOSITORY_NAME> 1.0.0`이다. Tool은 tagger identity를 고정값으로, `taggerEpoch`를 merged-main adoption receipt의 sealed commit timestamp로 정하며 현재 시각이나 SPEC archive mtime을 쓰지 않는다. Tag object 생성 전 durable `localTagIntent`를 쓰고, exact annotated object의 target·tagger·epoch·message 검증 뒤 stdout으로 tag receipt path·whole-file SHA-256을 출력한다. Orchestrator는 이 receipt를 검증한 뒤에만 repository phase를 `localTagVerified`로 fsync한다.

그 repository의 remote tag absence와 local tag object ID·peeled candidate SHA를 `tagPushIntent`로 fsync한 뒤 `/usr/bin/git push origin refs/tags/<TAG>:refs/tags/<TAG>`로 exact 한 tag만 push한다. Git ref API와 fetch한 remote object bytes로 annotated tag object ID·content와 peeled target을 다시 확인한 뒤 repository phase를 `tagged`로 fsync한다. 이 네 상태를 repository마다 끝낸 후 다음 repository로 가며, 자동 lightweight tag·force·delete는 없다. 여섯 repository가 모두 `tagged`가 되기 전에는 첫 release를 만들지 않는다.

`/usr/bin/git cat-file tag <TAG_OBJECT_OID>`의 exact object를 parser로 읽고 header 뒤 human release-note body를 제한한다. Body 끝에는 비밀이 아닌 exact `sentinel-intent:<ATTEMPT_ID>:<INTENT>` 한 줄을 붙이며 전체를 최대 65536 UTF-8 byte로 제한해 privacy canary를 검사한다. 별도 repository invariant를 통과한 뒤 repository ID, release-list stable pre-state digest, tag name, exact release name, complete body digest·intent marker, expected author ID `166008093`, `prerelease=false`, expected draft `immutable=false`와 asset absence를 `draftCreateIntent`로 먼저 fsync한다. 이어 canonical JSON `{tag_name,name,body,draft:true,prerelease:false}`를 bounded request body로 T01 transport의 `POST /repos/hwain-ai/<NAME>/releases`에 전달한다. Existing tag에서 무시되는 `target_commitish`는 보내지 않는다. Pinned control header, remote annotated tag·peeled target과 별도 repository invariant를 재검증하고 response의 release ID·`tag_name`·exact `name`·body digest·marker·`draft=true`·`prerelease=false`·`author.id=166008093`·`immutable=false`·asset 0만 typed parse해 `draftCreated`로 전이한다. Release response에 repository ID가 있다고 가정하지 않는다.

Upload 전에 canonical asset, `SHA256SUMS.json` 순서의 exact 2-item allowlist 전체를 repository ID·draft release ID·name·size·local digest·content type·uploader ID `166008093`와 함께 fsync한다. 각 item마다 별도 `uploadIntent`를 fsync한 뒤 `release_asset_transport.upload`로 `uploads.github.com`에 올리고 201 response와 stable list-assets readback의 asset ID·name·size·`state=uploaded`·digest를 item receipt로 기록한다. Checksum manifest 자체의 local digest와 API digest도 join한다. Glob, overwrite와 automatic redirect는 금지한다. Exact remote 2-item set이 allowlist와 같으면 `assetsVerified`로 전이한다. Resume 시 기존 `uploaded` asset을 새 owner-only directory에 받아 digest까지 같으면 건너뛰고, 다르면 delete·overwrite하지 않고 중단한다.

Upload가 502·422를 반환하거나 성공 뒤 receipt 전에 끊겼을 때만 list-assets를 다시 읽는다. Exact `uploadIntent`와 같은 repository·draft release·name·uploader이고 `state=starter`, `size=0`, digest absent인 asset이 정확히 하나면 그 asset ID의 `starterCleanupIntent`를 먼저 fsync한다. 이후 transport로 exact asset ID를 한 번 DELETE하고 list absence를 재확인해 cleanup receipt를 fsync한 뒤 bounded retry한다. Cleanup 성공과 receipt 사이 crash는 같은 exact starter의 404·list absence만 채택한다. 둘 이상, `uploaded` asset, 다른 uploader·name·size·digest·release, published release 또는 durable intent 부재에서는 delete·retry 0으로 중단한다. Release 자체, `uploaded` asset과 tag는 어떤 경우에도 보상 삭제하지 않는다.

Publish 전에 별도 repository invariant를 통과하고 release API에서 여섯 draft가 여전히 exact release ID·`tag_name`·name·body digest·intent marker·`draft=true`·`prerelease=false`·`author.id=166008093`·`immutable=false`이며 asset set에 누락·추가가 없는지 재조회한다. Commit identity는 release `target_commitish`가 아니라 remote annotated tag object ID·peeled candidate SHA로 다시 확인한다. SPEC draft asset과 `SHA256SUMS.json`은 서로 다른 fresh owner-only download directory에 asset ID별 `release_asset_transport.download`로 받고 name·size·SHA-256을 canonical allowlist와 대조한다. Browser URL과 unvalidated redirect는 사용하지 않는다. Archive member path·mode·중복·link 안전성, manifest와 전체 file digest, schema meta-validation과 모든 golden semantic oracle을 검증하고, 검증한 바로 그 downloaded SPEC archive bytes와 digest만 runtime 검증 input으로 고정한다.

그 다음 5개 runtime draft asset과 각 `SHA256SUMS.json`도 서로 다른 fresh owner-only directory에 다운로드해 name·size·SHA-256과 archive·package 안전성을 검증한다. 각 downloaded runtime artifact를 T25의 pinned Linux amd64 OCI에서 network·sibling checkout·host package 없이 clean-install하고, 앞에서 검증한 exact downloaded SPEC bytes를 read-only semantic oracle로, T25 canonical synthetic project fixture를 read-only input으로 고정한다. Runtime에 vendored된 SPEC bytes·lock도 그 downloaded SPEC와 exact 같아야 한다. 설치한 exact entrypoint에 `--help`, `doctor`, `crap`, `mutation`, `check`, `history` 여섯 invocation을 실제 실행한다. `crap`·`mutation`·`check`만 fresh owner-only state에 local ephemeral CSPRNG project-key stdin envelope를 받고, `--help`·`doctor`·`history`는 envelope 없이 실행해 T03의 option restriction도 지킨다. 각 invocation exit·schema·semantic golden, source immutability와 privacy canary를 모두 검사한다. SPEC부터 시작한 여섯 download digest·semantic·runtime receipt가 durable ledger에 fsync된 뒤에만 각 repository를 `downloadsVerified`로 전이한다. Upload 전 local file 검증, digest-only download, invocation 일부 생략 또는 publish 뒤 검증은 완료가 아니다.

여섯 repo가 모두 `downloadsVerified`이고 immutable-policy GET readback이 모두 `enabled=true`인 뒤에만 별도 repository invariant와 remote annotated tag object ID·peeled candidate SHA를 다시 확인한다. Exact repository ID·release ID·tag object ID·peeled SHA, name·body marker·author·prerelease digest, asset-set digest, fresh download·semantic receipt digest, immutable-policy receipt와 current draft state digest를 `publishIntent`로 먼저 fsync한다. 그 뒤 exact release ID에 canonical JSON `{draft:false}`를 PATCH해 publish한다. Publish 직후 별도 repository invariant와 release·Git ref·asset API를 다시 읽어 exact release ID·`tag_name`·name·body digest·intent marker·`prerelease=false`·`author.id=166008093`·annotated tag object·peeled target, `draft=false`, `immutable=true`, asset name·ID·size·`state=uploaded`·digest와 policy `enabled=true`를 검증한다. Fresh directory로 asset 두 개를 다시 다운로드해 ledger bytes와 SHA-256을 대조하고 SPEC semantic 또는 runtime 여섯 invocation을 다시 실행한 receipt를 fsync한 뒤에만 `publishedVerified`로 전이한다. Publish 도중 중단되면 matching `publishIntent`가 있는 이미 published exact immutable release만 수정·삭제 없이 read-only 검증으로 회복하며 같은 attempt의 남은 draft만 이어간다. API 실패로 일부만 published되어도 delete·retag하지 않는다. 하나라도 다르면 전체 release를 중단하고 그대로 보존한다.

GitHub가 immutable release publish에 붙이는 자동 release attestation은 GitHub server가 관리하는 부가 metadata로만 취급한다. SENTINEL은 이를 생성·수정·삭제·검증하지 않고 완료 gate나 provenance 근거로 사용하지 않는다. 완료 근거는 이 계획이 직접 고정한 candidate SHA·annotated tag object·immutable policy·asset ID·size·digest, fresh download와 semantic receipt뿐이다.

실행: `scripts/uv.sh run python tools/credential_launcher.py run --profile ../build/private-repo/operator-credential-profile.json --ssh-session-record ../build/private-repo/ssh-session-record.json -- <workspace>/SENTINEL_SPEC/scripts/uv.sh run python tools/release_orchestrator.py resume --github-token-fd 3 --attempt ../build/release-attempts/<ATTEMPT_ID> --through publishedVerified`

기대: interrupt가 있으면 exact durable phase에서만 이어가고 6개 record가 `candidate -> built -> localTagIntent -> localTagVerified -> tagPushIntent -> tagged -> draftCreateIntent -> draftCreated -> assetsVerified -> downloadsVerified -> publishIntent -> publishedVerified` 순서를 모두 증명함. Terminal record의 재실행은 GitHub·Git·asset·ledger mutation 0

- [ ] **단계 7: 최종 불변·privacy 감사**

실행: `scripts/uv.sh run pytest tests/test_release_orchestrator.py -q`

실행: `scripts/uv.sh run python tools/credential_launcher.py run --profile ../build/private-repo/operator-credential-profile.json --ssh-session-record ../build/private-repo/ssh-session-record.json -- <workspace>/SENTINEL_SPEC/scripts/uv.sh run python tools/release_orchestrator.py verify --github-token-fd 3 --attempt ../build/release-attempts/<ATTEMPT_ID> --require-phase publishedVerified`

기존 upstream 7개 child repository에서 고정 HEAD를 확인하고 `SENTINEL_SPEC/tools/verify_upstream_tree.py`로 T01의 `.git/**` 제외 whole-tree path·mode·content digest와 세 tracked archive digest를 재검증한다. 이어 `SENTINEL_SPEC/tools/verify_upstream_git_metadata.py`로 repository별 `.git` object/ref/config metadata digest와 고정 HEAD를 재검증한다. 이 baseline에 포함된 SwarmForge는 여기서 working tree와 Git metadata 불변을 증명한다. 6개 remote마다 authenticated login `hwain-ai`·numeric ID `166008093`, owner, repository ID와 private visibility를 확인한다. 또한 default branch `main`, required PR·check protection과 `strict=true`, SPEC exact-SHA secretless CI, 5개 runtime activation variable, main-only Environment·reviewer 0개·local approval receipt, protected-main exact-SHA CI의 stable E2 2회 결과·`repeated=true`, annotated tag peeled target, immutable-policy `enabled=true`, release `draft=false`·`immutable=true`, asset allowlist·`state=uploaded`·digest, fresh download semantic·6-invocation receipt와 ledger `publishedVerified`를 재조회한다. 시작 baseline이 없는 application repository 전체가 불변이라고 주장하지 않는다. 그 범위의 완료 증거는 release orchestrator의 audited path-access trace에서 application path access 0, absolute Git executor trace에서 application path를 `cwd`·`--git-dir`·`--work-tree`·argument로 사용한 호출 0인 데 한정한다. 하나라도 다르면 1.0.0 전체 완료를 선언하지 않는다. 같은 verify와 terminal resume을 다시 실행해 external mutation 0도 확인한다.

## 요구사항 역방향 추적

모든 요구사항은 아직 실행 전이므로 상태는 `진행 중`이다. 아래 표는 각 task header의 `충족 요구사항`과 같은 직접 기여 작업을 가리킨다.

|요구사항|계획 작업|상태|
|---|---|---|
|요구사항-01|T05, T08, T28, T29|진행 중|
|요구사항-02|T09, T12, T28, T29|진행 중|
|요구사항-03|T07, T25|진행 중|
|요구사항-04|T11, T25|진행 중|
|요구사항-05|T05, T09, T13, T17, T21, T25|진행 중|
|요구사항-06|T02, T08, T12, T16, T20, T24, T25|진행 중|
|요구사항-07|T02, T04, T08, T12, T16, T20, T24, T25|진행 중|
|요구사항-08|T02, T04, T08, T12, T16, T20, T24, T25|진행 중|
|요구사항-09|T02, T05, T09, T13, T17, T21|진행 중|
|요구사항-10|T02, T06, T10, T14, T18, T22|진행 중|
|요구사항-11|T02, T06, T10, T14, T18, T22|진행 중|
|요구사항-12|T06|진행 중|
|요구사항-13|T10|진행 중|
|요구사항-14|T06, T10, T14, T18, T22|진행 중|
|요구사항-15|T06, T10, T14, T18, T22|진행 중|
|요구사항-16|T02, T06, T10, T14, T18, T22|진행 중|
|요구사항-17|T06, T10, T14, T18, T22|진행 중|
|요구사항-18|T05, T09, T13, T17, T21|진행 중|
|요구사항-19|T07, T08, T25|진행 중|
|요구사항-20|T11, T12, T25|진행 중|
|요구사항-21|T02, T05, T09, T13, T17, T21|진행 중|
|요구사항-22|T07, T11, T15, T19, T23|진행 중|
|요구사항-23|T07, T11, T15, T19, T23|진행 중|
|요구사항-24|T07, T11, T15, T19, T23|진행 중|
|요구사항-25|T07, T11, T15, T19, T23|진행 중|
|요구사항-26|T02, T07, T11, T15, T19, T23|진행 중|
|요구사항-27|T07, T11, T15, T19, T23|진행 중|
|요구사항-28|T07, T08, T11, T12, T15, T16, T19, T20, T23, T24|진행 중|
|요구사항-29|T07, T08, T11, T12, T15, T16, T19, T20, T23, T24|진행 중|
|요구사항-30|T02, T07, T11, T15, T19, T23|진행 중|
|요구사항-31|T02, T07, T11, T15, T19, T23|진행 중|
|요구사항-32|T05, T07, T08, T09, T11, T12, T13, T15, T16, T17, T19, T20, T21, T23, T24, T25|진행 중|
|요구사항-33|T04, T25, T27..T29|진행 중|
|요구사항-34|T06, T10, T14, T18, T22, T27, T29|진행 중|
|요구사항-35|T27..T29|진행 중|
|요구사항-36|T26, T29|진행 중|
|요구사항-37|T26, T29|진행 중|
|요구사항-38|T02..T04, T25, T29|진행 중|
|요구사항-39|T13..T16, T28, T29|진행 중|
|요구사항-40|T17..T20, T28, T29|진행 중|
|요구사항-41|T21..T24, T28, T29|진행 중|
|요구사항-42|T02, T05, T08, T09, T12, T13, T16, T17, T20, T21, T24, T25, T28, T29|진행 중|
|요구사항-43|T02, T07, T11, T15, T19, T23, T25, T28, T29|진행 중|
|요구사항-44|T04, T25, T27..T29|진행 중|
|요구사항-45|T03, T08, T12, T16, T20, T24, T25|진행 중|
|요구사항-46|T03, T08, T12, T16, T20, T24, T25|진행 중|
|요구사항-47|T03, T08, T12, T16, T20, T24, T25|진행 중|
|요구사항-48|T03, T08, T12, T16, T20, T24, T25|진행 중|
|요구사항-49|T03, T04, T08, T12, T16, T20, T24, T25|진행 중|
|요구사항-50|T03, T08, T12, T16, T20, T24, T25|진행 중|
|요구사항-51|T03, T08, T12, T16, T20, T24, T25|진행 중|
|요구사항-52|T03, T08, T12, T16, T20, T24, T25, T28, T29|진행 중|
|요구사항-53|T03, T08, T12, T16, T20, T24, T25, T28, T29|진행 중|
|요구사항-54|T03, T04, T08, T12, T16, T20, T24, T25|진행 중|
|요구사항-55|T05, T09, T13, T17, T21, T25|진행 중|

## 공통규칙 추적

|공통규칙|계획 작업|검증|
|---|---|---|
|공통규칙-01|T01, T28, T29|6개 local·private remote·release 존재|
|공통규칙-02|T02, T07, T11, T15, T19, T23|backend lock 하나, runtime fallback 0, operator 보존|
|공통규칙-03|T02, T06, T10, T14, T18, T22, T27|CRAP raw 8.0 이하와 killed-only|
|공통규칙-04|T02, T05, T09, T13, T17, T21, T25|독립 CLI와 harness integration fixture|
|공통규칙-05|T28, T29|`hwain-ai` private visibility 재조회|
|공통규칙-06|T01, T15, T19, T23, T29|7개 upstream 고정 HEAD와 `.git/**` 제외 whole-tree digest 일치|
|공통규칙-07|T01, T25..T29|Git top-level이 각 child repo와 같음|
|공통규칙-08|T01..T29|각 production 단계의 실패 test 선행 기록|
|공통규칙-09|T07, T11, T15, T19, T23, T27|three-way source identity와 no-source-write|
|공통규칙-10|T01, T26, T29|6개 OKF v0.2 bundle lint|

## 3~5수 실행 시뮬레이션과 회복점

|현재 선택|다음 단계|그다음 결과|6개월 뒤 모습|실패 시 회복점|
|---|---|---|---|---|
|SPEC RC를 먼저 고정|5개 runtime이 같은 golden을 소비|언어별 구현 차이를 conformance에서 조기 발견|backend를 바꿔도 공용 schema는 안정|T02..T04만 새 RC로 올리고 runtime lock 갱신|
|위험 backend admission 선행|거짓 killed를 release 전에 차단|Python 대체 backend 또는 언어별 release 차단이 명확|bridge upgrade가 독립 compatibility 작업이 됨|마지막 통과 pin 유지, 해당 admission task로 복귀|
|outer snapshot과 descriptor-relative path|원본 source 직접 write 금지|동시 편집·중단에도 원본 보존|큰 repo에서 copy 비용이 드러남|`WorkspaceProvider`만 reflink·copy-on-write로 교체|
|project-local immutable history|중앙 서버 없이 반복 결함 확인|privacy와 offline 사용 유지|run 수 증가로 scan 비용 발생|bundle에서 재생성 가능한 derived index 추가|
|private 6-repo release|언어별 독립 설치·권한 분리|SPEC deploy-key 운영 필요|release orchestration 반복 비용 증가|공개 interface를 유지한 mirror automation을 별도 제품으로 추가|

SwarmForge 실제 연결을 지금 포함하면 여섯 release의 실패와 하네스 integration 실패가 섞여 회복 지점이 사라진다. 따라서 T29 뒤에 별도 spec·design·plan으로 연결하고, 그때 module routing과 CLI exit만 소비한다.

## 자기 검토

- 요구사항-01..요구사항-55: 55개 모두 task와 역방향 연결, 미할당 0개
- 공통규칙-01..공통규칙-10: 10개 모두 구현·검증 작업 연결
- 설계 interface 13개: 다섯 runtime의 같은 의미로 고정
- Backend false-pass: assertion type, nonce, original control, replay, candidate/result exact set, 9개 상태와 unknown 반례 포함
- Source safety: descriptor-relative path, snapshot byte copy, three-way identity, process-tree cleanup 포함
- Evidence·privacy: atomic commit, cross-runtime POSIX lock, HMAC fingerprint, allowlist export, raw report 기본 제외 포함
- Release: clean install, private visibility, read-only deploy key, protected main, CI·tag·HEAD equality 포함
- 범위 밖 유지: 실제 SwarmForge·application 수정, 공개 registry, 중앙 HUB, 자체 mutation engine는 작업에 포함하지 않음
- 빈 placeholder와 미래 기능 문서: 생성하지 않음

## 변경이력

- 2026-09-02 | 실행계획 최초 작성 | 변경: 승인된 55개 요구사항과 10개 공통규칙을 SPEC, Python, TypeScript, Go, Java, Clojure, cross-runtime, release의 T01..T29로 분해 | 검증: 요구사항·공통규칙 역방향 추적과 wave dependency 대조
- 2026-09-02 | Backend 계약 감사 반영 | 변경: backend-lock schema, exact runtime·runner profile, Stryker typed assertion, Go runner admission, Java standalone·JUnit bridge, Clojure safe reader·copied snapshot을 완료조건에 추가 | 검증: 고정 upstream source 감사와 false-kill·source 오염 반례 대조
- 2026-09-03 | 실행·복구 계약 최종 보강 | 변경: 공통 temporary-index commit inventory, Python backend 격리 선택과 fast-forward 채택, immutable attempt·T25/T27 seal, GitHub direct REST·main-only 승인·exact-SHA CI, deterministic asset·annotated tag·immutable release 상태기를 구체화 | 검증: 55개 task 역추적, NUL path·single-parent commit, crash resume, secret FD·swap 0, fresh download semantic gate를 문서와 반례별 교차 대조
