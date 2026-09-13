---
type: validation-reference
updated: 2026-09-13
status: current
owner: Claude Code (사용자 승인 하에 작성)
related:
  - docs/exec-plans/active/2026-09-sentinel-unified-entry.md
  - https://github.com/hwain-hwang/SENTINEL_PY/blob/main/docs/sentinel-python-native-validation.md
  - https://github.com/hwain-hwang/SENTINEL_TS/blob/main/docs/sentinel-typescript-native-validation.md
---

# SENTINEL 과 원본 변이 도구의 결과 비교

한마디 요약: Python·TypeScript·Java 세 언어 모두에서 "SENTINEL 의 killed + runtimeError" 가 "원본 도구의 killed" 와 같다. TypeScript 에서 처음 발견된 예외 2개는 SENTINEL 의 결함이었고, 2026-09-13 에 고쳐 재검사한 뒤에는 변이 81개가 전부 일치한다.

이 문서는 2026-09-13 에 공개 프로젝트 3개를 SENTINEL 과 원본 도구로 각각 돌려 얻은 숫자를 사람이 읽기 쉽게 정리한 것이다. 세부 실행 조건은 언어별 검증 기록에 있고, 이 문서는 "숫자가 왜 다르게 보이는가" 에 답한다.

## 용어

- 변이 검사(mutation testing): 소스 코드를 일부러 조금씩 망가뜨린 사본(변이, mutant)을 만들고, 테스트가 그 사본에서 실패하는지 보는 검사. 테스트가 잘 짜여 있으면 망가진 코드를 잡아낸다.
- killed: 테스트가 실패해서 변이를 잡아냈다는 뜻. 좋은 결과.
- survived: 테스트가 모두 통과해서 변이를 못 잡았다는 뜻. 그 코드 동작을 확인하는 테스트가 없다는 신호.
- uncovered: 변이가 들어간 줄을 실행하는 테스트가 아예 없어서 실행조차 안 한 변이. Stryker 는 NoCoverage, mutmut 은 종료 코드 33 으로 표시한다.
- runtimeError: SENTINEL 에만 있는 상태. 테스트가 실패하긴 했는데 "단언(assert) 실패" 가 아니라 예외(TypeError, NullPointerException 등)로 죽은 변이.
- kill 비율: killed 를 전체 변이 수로 나눈 값. SENTINEL 의 기본 기준은 100% 이고, runtimeError 와 survived 와 uncovered 는 모두 분자에 들어가지 않는다.
- CRAP: 함수 하나의 복잡도와 테스트가 안 건드린 비율을 곱한 점수. 기본 상한 8. 변이 검사와는 별개의 판정이라 이 문서의 비교 대상이 아니다.

## 숫자가 다른 이유는 규칙 하나다

SENTINEL 은 변이를 잡은 테스트 실패가 "단언 실패" 일 때만 killed 로 센다. 예외로 죽은 변이는 runtimeError 로 따로 센다. 원본 도구(mutmut, Stryker, mutate4java)는 이 둘을 구분하지 않고 모두 killed 로 센다. 그래서 다음 식이 성립한다.

원본 도구의 killed = SENTINEL 의 killed + SENTINEL 의 runtimeError

SENTINEL 이 이렇게 하는 의도는 "테스트가 그 동작을 단언으로 확인했다" 는 근거가 있는 것만 통과 증거로 쓰고, 근거가 약한 결과(우연히 예외가 난 것)를 통과로 처리하지 않는 것이다. 대가는 kill 비율이 원본 도구보다 낮게 나오고, 기준 100% 를 맞추기가 더 어렵다는 점이다. 이 판정 방식이 지나치게 엄격한지는 사용자가 정할 문제이며, 이 문서는 두 숫자가 같은 실행을 다르게 센 것이지 다른 실행이 아니라는 점만 확인한다.

실제로 어떤 변이가 어느 쪽으로 가는지 세 언어에서 손으로 넣어 확인했다.

|언어|변이 내용|테스트가 실패한 방식|SENTINEL 분류|
|---|---|---|---|
|Java|`this.missingOptions = missingOptions` 를 `= null` 로|NullPointerException 으로 3개 테스트가 ERROR|runtimeError|
|Java|`missingOptions.size() == 1` 을 `!= 1` 로|메시지 비교 단언이 2개 테스트에서 FAILURE|killed|
|TypeScript|`separators ?? STR_SPLITTERS` 를 `separators && STR_SPLITTERS` 로|첫 실패가 `TypeError: Cannot read properties of undefined` (9건), 단언 실패 2건은 그 뒤|runtimeError|
|Python|원본 mutmut 이 killed 로 둔 567개 중 표본 20개를 다시 실행|AssertionError 4개, `pytest.raises` 의 DID NOT RAISE 1개, TypeError·AttributeError 15개|앞 5개는 killed, 뒤 15개는 runtimeError 에 해당|

Python 에서 runtimeError 가 유난히 많은(346개) 이유는 mutmut 3 이 함수 인자를 None 으로 바꾸는 변이를 많이 만들고, 그런 변이는 대부분 TypeError 로 죽기 때문이다.

## 언어별 대조 표

세 표 모두 같은 사본, 같은 고정 도구(검사기가 잠가 둔 버전), 같은 테스트 선택으로 돌렸다. 시간은 같은 EC2 에서 다른 시험과 CPU 를 나눠 쓴 상태의 값이라 참고용이다.

### Python: ItsDangerous 2.2.0

commit 096c8d42545d3b68ea21a4f890fb2b2d8979c0bd, 생산 파일 8개, 테스트 297개. 원본 도구는 mutmut 3.7.0.

|상태|SENTINEL 엄격 검사|원본 mutmut 직접 실행|확인|
|---|---|---|---|
|전체 변이|567|567|같음|
|killed|72|418|72 + 346 = 418|
|runtimeError|346|(killed 에 포함)|위와 같음|
|survived|121|121|같음|
|uncovered|28|28|같음|
|kill 비율|72/567 = 12.70%|418/567 = 73.72%|세는 규칙이 다름|
|판정·소요|기준 미달, 종료 2, 3,421초|종료 0, 256초|-|

### TypeScript: unjs/scule v1.3.0

commit 90d28593c8426d16beb5dadf3af8d341b6fee107, 생산 파일 2개(364줄), 테스트 63개. 원본 도구는 Stryker 10.0.0 + Vitest 4.1.11.

|상태|SENTINEL 검사|원본 Stryker 직접 실행|확인|
|---|---|---|---|
|전체 변이|81|81|같음. 변이 id 81개를 하나씩 대조해 상태가 모두 일치|
|killed|74|75|74 + 1 = 75|
|runtimeError|1|(killed 에 포함)|-|
|survived|5|5|같음|
|uncovered|1|1|같음|
|kill 비율|74/81 = 91.36%|75/81 = 92.59%|세는 규칙이 다름|
|판정·소요|기준 미달, 종료 2, 115초|종료 0, 35초|-|

위 값은 아래 결함을 고친 뒤의 재검사 결과다. 고치기 전 첫 검사는 killed 72·survived 7 이었다.

### Java: Apache Commons CLI 1.10.0

commit 04581158dbebe688518a6d384cf7b611a074ef7a, 테스트 968개(그중 @Disabled 61개). 전체 파일 36개를 다 검사하면 변이 1개마다 전체 테스트를 한 번(약 35~45초) 돌려야 해서 중단했고, 주석 한 줄을 고친 MissingOptionException.java 하나만 변경분 모드로 검사했다. 원본 도구는 mutate4java(commit 7b05fdd)를 같은 파일에 단독 실행했다.

|상태|SENTINEL 변경분 검사|원본 mutate4java 직접 실행|확인|
|---|---|---|---|
|전체 변이|10|10|같음|
|killed|5|10|5 + 5 = 10|
|runtimeError|5|(killed 에 포함)|null 치환 5개가 예외로 죽음|
|survived|0|0|같음|
|uncovered|0|0|같음|
|kill 비율|5/10 = 50%|10/10 = 100%|-|
|판정·소요|기준 미달, 종료 2, 663초(CRAP 포함)|종료 0, 396초|-|

## TypeScript 에서 처음 맞지 않았던 변이 2개는 SENTINEL 의 결함이었다(수정 완료)

첫 검사에서 SENTINEL 이 survived 로 둔 7개 중 2개를 원본 Stryker 는 killed 로 판정했다. 둘 다 src/index.ts 의 모듈 최상위 정규식 상수를 바꾸는 변이다.

|변이 id|위치|바꾼 내용|손으로 넣고 테스트한 결과|
|---|---|---|---|
|0|12행 `const NUMBER_CHAR_RE = /\d/`|`/\D/` 로|63개 중 18개 실패|
|79|173행 단어 목록 정규식|앞의 `^` 앵커 제거|63개 중 1개 실패|

실제로는 테스트가 실패하므로 원본 Stryker 의 killed 가 맞고, SENTINEL 의 survived 는 틀렸다. 두 변이의 공통점은 Stryker 가 "static" 으로 표시한 변이라는 점이다. static 변이는 함수 안이 아니라 모듈을 읽어 들이는 시점에 한 번 평가되는 코드(최상위 상수)에 들어가므로, 테스트가 소스를 import 하기 전에 변이가 켜져 있어야 관찰할 수 있다.

원인은 Stryker 코드에서 확인했다. Stryker 의 계획기는 "테스트 필터가 있으면 변이를 runtime(테스트 시작 직전)에 켜고, 없으면 static(import 전)에 켠다" 고 정한다. SENTINEL 은 닫힌 설정에서 테스트 파일 목록(`testFiles`)을 명시하는데, 그러면 Stryker 는 모든 변이에 그 목록을 테스트 필터로 붙이므로 static 변이도 runtime 으로 켜졌다. 결과적으로 최상위 상수는 이미 원본 값으로 평가된 뒤였고 테스트는 통과했다. 직접 실행에서는 `testFiles` 를 주지 않아 static 으로 켜졌다.

수정은 SENTINEL 의 실행기(stryker-proof-runner.ts)에서 했다. Stryker 는 static 변이에만 "환경을 새로 띄워라(reloadEnvironment)" 표시를 붙이므로, 그 표시가 있는 요청은 활성화 시점을 static 으로 바꿔 Stryker 의 Vitest 실행기에 넘긴다. 고친 뒤 unjs/scule 을 다시 검사하면 두 변이가 killed 가 되고, 변이 81개의 상태가 직접 Stryker 결과와 전부 일치한다(SENTINEL_TS 커밋 dcbcf3e, 자체 시험 180개 통과).

고치기 전의 영향은 보수적인 방향이었다. 잡을 수 있는 변이를 "못 잡음" 으로 두어 기준을 더 통과하기 어렵게 만들었을 뿐, 통과해서는 안 될 프로젝트를 통과시키지는 않았다.

## 직접 확인하는 방법

아래 명령은 실제로 사용한 것과 같은 형태이며, 프로젝트 경로만 자기 환경으로 바꾸면 된다. 검사기 저장소(SENTINEL_PY, SENTINEL_TS, SENTINEL_JAVA)의 잠긴 도구를 그대로 쓰므로 새로 설치할 것은 없다.

Python: 프로젝트 사본의 setup.cfg 끝에 아래 블록을 붙이고, 검사기의 고정 venv 로 mutmut 을 돌린 뒤 `mutants/**/*.py.meta` 의 `exit_code_by_key` 를 읽는다(1 = killed, 0 = survived, 33 = uncovered).

```
[mutmut]
source_paths =
    src/패키지/파일1.py
    src/패키지/파일2.py
pytest_add_cli_args_test_selection =
    tests
also_copy =
    (mutants 를 뺀 최상위 항목 전부)
mutate_only_covered_lines = false
use_git_change_detection = false
```

```bash
# PYTHONPATH 에 소스·프로젝트·의존성 폴더를 순서대로 둔다. --max-children 1 은 작업자 1개.
PYTHONPATH="$COPY/src:$COPY:$COPY/.sentinel-deps" \
  SENTINEL_PY/.toolchain/venv/bin/python3 -m mutmut run --max-children 1
```

TypeScript: 프로젝트 사본의 node_modules 를 검사기의 잠긴 node_modules 항목별 링크로 채우고, 아래 설정으로 Stryker 를 돌린 뒤 reports/mutation.json 의 변이별 status 를 읽는다. `tsconfigFile` 을 없는 파일로 두는 이유는 검사기와 같은 조건(잠긴 트리에 typescript 패키지가 없음)으로 맞추기 위해서다.

```json
{
  "mutate": ["src/**/*.ts"],
  "testRunner": "vitest",
  "coverageAnalysis": "perTest",
  "reporters": ["json", "progress"],
  "jsonReporter": {"fileName": "reports/mutation.json"},
  "concurrency": 2,
  "tsconfigFile": ".stryker-none.json"
}
```

```bash
# 검사기의 고정 Node 로 잠긴 Stryker 를 실행한다.
SENTINEL_TS/.toolchain/node-v22.23.1-linux-x64/bin/node \
  node_modules/@stryker-mutator/core/bin/stryker.js run
```

Java: 프로젝트 사본에서 잠긴 mutate4java jar 를 파일 하나에 단독 실행한다. `--test-command` 로 검사기와 같은 오프라인 Maven 저장소를 쓰게 하고, `--mutate-all` 은 모든 변이 실행, `--max-workers 1` 은 작업자 1개다. 결과는 표준 출력의 `Summary: N killed, M survived` 줄과 변이별 KILLED/SURVIVED 줄이다.

```bash
SENTINEL_JAVA/.toolchain/jdk-17.0.20.1+1/bin/java \
  -cp SENTINEL_JAVA/.toolchain/backends/mutate4java-7b05fdd.jar mutate4java.cli.Main \
  src/main/java/패키지/파일.java --mutate-all --max-workers 1 --verbose \
  --test-command "mvn -o -B -ntp -Dmaven.repo.local=$PROJECT/.sentinel-m2 test"
```

SENTINEL 쪽 숫자는 `sentinel check --experimental --format json` 결과의 각 언어 도구 출력에서 읽는다. 통합 명령의 결과 JSON 은 모듈별 상태와 종료 코드만 담고 집계는 언어 도구의 출력·증거 파일에 있다.

## 한계

- 변이별 기록: Python 과 Java 의 SENTINEL 결과는 집계(개수)만 남기고 변이별 상태를 남기지 않는다. TypeScript 는 변이 id 와 상태만 남긴다. 그래서 변이 단위 대조는 원본 도구 쪽 기록(mutmut meta 파일, Stryker JSON 보고서, mutate4java 출력)을 기준으로 했다.
- Java 시간: SENTINEL 도 원본 도구도 변이 1개마다 전체 테스트를 한 번 돌리므로, 큰 프로젝트는 변경분 모드(`check --changed`)만 실용적이다.
- TypeScript 의존성: 검사기는 대상 테스트를 검사기의 잠긴 node_modules 만으로 실행한다. 소스가 devDependency 를 직접 import 하는 프로젝트(unjs/pathe 는 zeptomatch 를 import)는 아직 검사할 수 없다.
- 여기서 쓴 사본과 원시 결과는 세션 임시 폴더에 있어 보존되지 않는다. 숫자와 재현 명령만 이 문서에 남긴다.

## 변경이력

- 2026-09-13 | 최초 작성 | 변경: 세 언어의 SENTINEL 결과와 원본 도구 결과를 한 규칙(killed + runtimeError = 원본 killed)으로 정리하고, 손으로 넣어 확인한 변이 예시, TypeScript static 변이 2개 미탐지 결함, 재현 명령을 기록 | 검증: Python 567·TypeScript 81·Java 10개 변이의 집계 대조, TypeScript 는 변이 id 81개 전부 대조, 예시 변이 4개는 직접 테스트 실행으로 실패 종류 확인.
- 2026-09-13 | TypeScript static 변이 결함 수정 반영 | 변경: 원인(Stryker 가 테스트 필터 유무로 활성화 시점을 정함)과 수정(reloadEnvironment 요청을 static 활성화로 위임), 재검사 결과(killed 74·survived 5)로 표와 결함 절을 갱신 | 검증: 재검사에서 변이 81개 상태가 직접 Stryker 와 전부 일치, SENTINEL_TS 자체 시험 180개 통과.
