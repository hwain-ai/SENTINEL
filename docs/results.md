# 검사 결과 읽기

SENTINEL은 검사한 범위, CRAP 점수, 변이 탐지율과 측정 근거를 반환한다. 에이전트는 이 결과를 보고 코드나 테스트를 수정한다. SENTINEL 자체는 LLM으로 원인을 추측하거나 수정안을 만들지 않는다.

## 검사 범위

```sh
sentinel check --file src/pricing.py --function calculate_discount --tests tests/test_pricing.py
```

| 입력 | 의미 |
|---|---|
| `check` | 품질 검사 실행 |
| `--file` | 점수를 측정할 기능 파일. 여러 파일이면 옵션을 반복한다. |
| `--function` | 파일 하나 안에서 선택할 함수 이름. `()`를 붙이지 않는다. 생략하면 파일 전체를 측정한다. |
| `--tests` | 실행할 테스트 파일. 여러 파일이면 옵션을 반복한다. 생략하면 설정된 테스트 묶음을 실행한다. |
| `--format json` | 구조화된 결과 출력. 기본값이므로 생략할 수 있다. |
| `--format text` | 사람이 읽는 텍스트 요약으로 출력한다. |

경로는 프로젝트 루트 기준이다. `details.scope.files`, `functions`, `tests`, `testSelection`에서 실제 선택을 확인한다. `functions: []`는 특정 함수로 좁히지 않았다는 뜻이다. 파일·함수·테스트를 선택한 검사는 변경 여부와 관계없이 실행한다.

다른 선택 옵션 없이 `--all`을 사용하면 프로젝트 설정에 포함된 기능 코드와 테스트 전체를 검사한다. 저장소 안의 모든 파일을 뜻하지 않는다. `--tests`를 함께 지정하면 실행할 테스트는 그 파일들로 좁아진다. `--changed`는 Git에서 변경된 기능 코드를 대상으로 한다. 테스트만 고쳤다면 같은 `--file`·`--function`으로 다시 검사한다. `--all`, `--changed`, `--file`은 함께 쓰지 않는다.

프로젝트의 소스·테스트 분류와 자세한 옵션은 [CLI 참고](references/sentinel-cli-reference.md)에 있다.

## 점수와 개수

| 필드 | 의미 |
|---|---|
| `crap.functions[].score` | 함수의 복잡도와 테스트 실행 범위로 계산한 CRAP 점수. 낮을수록 좋다. |
| `crap.files[].maxScore` | 해당 파일 안의 함수 점수 중 최댓값. 평균이 아니다. |
| `crap.limit` | 허용하는 CRAP 상한. 기본값은 `8`. |
| `mutation.inScope` | 점수 계산에 포함한 변이 개수. 테스트 파일이나 테스트 함수의 개수가 아니다. |
| `mutation.counts.killed` | 테스트가 발견한 변이 개수. 파일·함수별 묶음에서는 `killed`로 제공한다. |
| `mutation.score` | `killed / inScope × 100`으로 계산한 탐지율. 높을수록 좋다. |
| `mutation.minimum` | 요구하는 최소 탐지율. 기본값은 `90`. |

변이는 원래 코드의 연산자나 값을 일부러 바꾼 코드다. 예를 들어 `value + 1`을 `value - 1`로 바꾸고 테스트가 이 차이를 발견하는지 확인한다. `inScope: 2`, `killed: 2`이면 변이 두 개를 모두 발견했으므로 `score: "100"`이다. 실제 제품 결함 두 개를 찾았다는 뜻은 아니다.

분모에는 해당 범위의 모든 변이 상태가 포함된다. 실행되지 않은 변이와 실행 오류를 분모에서 빼서 점수를 높이지 않는다. 변이가 없으면 `score`는 `null`이다. 파일·함수별 묶음은 `pass: null`, `reason: "zeroMutants"`를 표시하고, 전체 mutation 판정은 통과하지 않는다. 미측정을 0점이나 100점으로 해석하지 않는다.

## 명령 종료 결과, 검사 범위와 품질 판정

아래 JSON은 필요한 필드만 발췌한 예시다.

```json
{
  "exitCode": 0,
  "selection": "partial",
  "results": [{ "status": "passed" }]
}
```

명령은 종료 코드 0으로 끝났고 선택한 범위의 품질 검사가 통과했다. `partial`이므로 전체 코드의 통과로 확대하지 않는다. 파일·함수·테스트·변경분 또는 일부 모듈·언어를 선택하면 `partial`이다. 변경분이 모든 모듈에 있어도 `--changed`는 부분 검사다. 모듈·언어 옵션만 사용했고 그 결과가 설정된 모든 모듈을 포함한다면 `allConfigured`다.

```json
{
  "exitCode": 0,
  "selection": "allConfigured",
  "results": [{ "status": "passed" }]
}
```

설정된 전체 범위에서 모든 모듈 결과가 `passed`라면 그 범위가 통과했다. 설정에서 제외한 파일까지 검사했다는 뜻은 아니다.

```json
{
  "exitCode": 0,
  "selection": "partial",
  "results": [{ "status": "noChanges" }]
}
```

검사할 변경 기능 코드가 없어 건너뛴 경우다. 종료 0이어도 실제 품질 검사를 통과한 결과가 아니다.

```json
{
  "exitCode": 2,
  "selection": "partial",
  "results": [{ "status": "qualityFailed" }]
}
```

측정 결과가 품질 기준에 미달했다. 검사기 고장을 뜻하지는 않는다. 아래의 `details`는 `results[].details`를 줄여 쓴 표기다.

| 위치 | 판단하는 내용 |
|---|---|
| `details.crap.pass` | CRAP 검사 기준 충족 여부 |
| `details.mutation.functions[].pass` | 그 함수의 변이 탐지율이 기준을 충족했는지 여부 |
| `details.mutation.files[].pass` | 그 파일의 변이 탐지율이 기준을 충족했는지 여부 |
| `details.mutation.pass` | 전체 mutation 기준 충족 여부. 점수 외에 허용되지 않은 제외도 확인한다. |
| 최상위 `exitCode` | 명령 종료 코드. 종료 0이어도 noChanges는 미검사. |
| `results[].status` | 모듈별 검사 통과·기준 미달·미검사·실행 오류 구분 |
| 최상위 `selection` | 전체 설정 범위(`allConfigured`) 또는 선택·변경분 범위(`partial`) |

최상위 성공 불리언은 없다. 명령 종료 결과는 `exitCode`, 품질 판정은 `results[].status`, 점수와 근거는 `results[].details`로 읽는다. 내부 CRAP·mutation의 `pass`는 해당 품질 기준 충족 여부다.

| 결과 | 해석 |
|---|---|
| `status: "passed"` | 해당 모듈의 검사 범위가 품질 기준을 통과했다. |
| `status: "qualityFailed"` | 측정 결과가 나왔으나 품질 기준에 미달했다. |
| `status: "noChanges"`, `exitCode: 0` | 검사할 변경 기능 코드가 없어 건너뛰었다. 실제 검사 통과가 아니다. |
| `status: "baselineFailed"` | 원래 코드의 테스트부터 실패했다. 먼저 그 실패를 해결한다. |
| `status: "toolError"` 또는 `"backendError"` | 검사 도구 실행에 문제가 생겼다. 제공된 `diagnostic`을 확인한다. |
| `status: "backendNotAdmitted"` | 도구가 승인 목록에 없어 기본 검사를 실행하지 않았다. |
| `status: "cancelled"` | 검사가 취소되었다. |

`plan`과 `doctor`의 종료 0은 각각 범위 확인·설치 확인의 성공이다. `admitted`는 사용한 도구의 승인 여부다. `--experimental`은 모든 품질 결과가 `passed`여도 종료 6을 반환한다.

## 출력 예시

아래는 두 함수가 있는 검증용 Python 파일의 측정 사례를 현재 출력 형식으로 표시한 것이다. `add_one`은 테스트가 실행했고 `unrelated`는 실행하지 않았다.

```text
SENTINEL check: exit 2, selection=partial
python [python]: qualityFailed (exit 2), not admitted
  CRAP max=2 (limit=8)
  mutation=50% (2/4, minimum=90%)
  src/subject.py:4 unrelated: CRAP=2
  src/subject.py:1 add_one: CRAP=1
  src/subject.py add_one: mutation=100% (2/2)
  src/subject.py unrelated: mutation=0% (0/2)
  src/subject.py:5 uncovered [subject.x_unrelated__mutmut_1]
  src/subject.py:5 uncovered [subject.x_unrelated__mutmut_2]
```

CRAP은 두 함수 모두 상한 8 이하로 통과했다. mutation은 `add_one` 100%, `unrelated` 0%로 전체 50%다. 검사기는 `unrelated`의 5번째 줄이 테스트에서 실행되지 않았다고 보고했다. 이 사례는 승인 전 도구 묶음으로 검증했으므로 `not admitted`도 표시된다.

JSON의 `details.mutation.mutants`에는 다음과 같은 근거가 담긴다. 아래는 기록 하나에서 주요 필드만 발췌한 것이다.

```json
{
  "file": "src/subject.py",
  "function": "unrelated",
  "line": 5,
  "column": 12,
  "original": "value * 2",
  "replacement": "value / 2",
  "status": "uncovered"
}
```

`file`과 `function`은 코드 위치, `line`과 `column`은 줄·열 번호, `original`과 `replacement`는 원본·변이 표현식이다. 언어 도구가 제공한 필드만 출력하므로 모든 기록에 같은 위치 정보가 있지는 않다.

`killed`는 테스트가 변이를 발견했다는 뜻이다. `survived`는 변이 실행 후에도 테스트가 통과한 경우, `uncovered`는 해당 위치를 테스트가 실행하지 않은 경우다. `compileError`, `runtimeError`, `toolError` 같은 오류를 탐지 성공으로 합산하지 않는다. 텍스트는 미탐지·오류 기록을 최대 20개까지 보여주며, 전체 기록은 `--format json`으로 확인한다.

에이전트는 미실행 위치를 실행하는 테스트와 기대 결과를 확인하는 검증을 보강한다. 특정 테스트가 반드시 부족하다고 단정하거나, 이 점수를 제품의 모든 요구사항 충족 여부로 확대하지 않는다.

## stdout과 종료 코드

JSON 안의 `exitCode`까지 포함한 JSON 전체가 표준 출력(stdout)이다. 프로세스의 실제 종료 코드는 별도로 전달하며, 일반적인 완료 결과에서는 JSON의 `exitCode`와 같다. 오류 메시지는 표준 오류(stderr)로 전달한다. 잘못된 입력 등 JSON 생성 전 실패에서는 stderr와 종료 코드만 나올 수 있다.

## 출력 형식 변경

통합 CLI·플러그인 0.2.0은 `sentinel-workspace-result-v2`(plan·doctor·check)와 `sentinel-setup-result-v2`(setup)를 사용한다. v1의 최상위 `pass`와 `certified`를 제거했고 대체 성공 불리언은 추가하지 않았다. 기존 호출자는 `exitCode`·`selection`·`results`로 읽도록 수정한다. 내부 CRAP·mutation의 `pass`와 언어 어댑터 프로토콜은 유지한다.
