# 검사 결과 읽기

SENTINEL은 검사한 범위, CRAP 점수, 변이 탐지율과 측정 근거를 반환한다. 에이전트는 이 결과를 보고 코드나 테스트를 수정한다. SENTINEL 자체는 LLM으로 원인을 추측하거나 수정안을 만들지 않는다.

## 검사 범위

```sh
sentinel check --file src/pricing.py --function calculate_discount --tests tests/test_pricing.py --format json
```

| 입력 | 의미 |
|---|---|
| `check` | 품질 검사 실행 |
| `--file` | 점수를 측정할 기능 파일. 여러 파일이면 옵션을 반복한다. |
| `--function` | 파일 하나 안에서 선택할 함수 이름. `()`를 붙이지 않는다. 생략하면 파일 전체를 측정한다. |
| `--tests` | 실행할 테스트 파일. 여러 파일이면 옵션을 반복한다. 생략하면 설정된 테스트 묶음을 실행한다. |
| `--format json` | 구조화된 결과 출력. 생략하면 텍스트를 출력한다. |

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

## `pass`, `status`, `certified`의 차이

| 위치 | 판단하는 내용 |
|---|---|
| `details.crap.pass` | CRAP 검사 기준 충족 여부 |
| `details.mutation.functions[].pass` | 그 함수의 변이 탐지율이 기준을 충족했는지 여부 |
| `details.mutation.files[].pass` | 그 파일의 변이 탐지율이 기준을 충족했는지 여부 |
| `details.mutation.pass` | 전체 mutation 기준 충족 여부. 점수 외에 허용되지 않은 제외도 확인한다. |
| 최상위 `pass` | 명령 전체의 최종 성공 여부. `exitCode`가 `0`일 때만 `true`. |
| `results[].status` | 모듈별 검사 통과·기준 미달·미검사·실행 오류 구분 |
| 최상위 `certified` | 승인된 도구로 설정된 전체 범위를 실제 검사해 통과했는지 여부 |

최상위 `pass`는 검사기가 정상 작동했는지만 나타내는 값이 아니다. 검사를 정상적으로 마쳐도 품질 기준에 미달하면 `false`다. 실행 오류나 취소, 승인 조건 미충족도 `false`가 된다.

| 결과 | 해석 |
|---|---|
| `status: "passed"` | 해당 모듈의 검사 범위가 품질 기준을 통과했다. |
| `status: "qualityFailed"` | 측정 결과가 나왔으나 품질 기준에 미달했다. |
| `status: "noChanges"`, `pass: true` | 검사할 변경 기능 코드가 없어 건너뛰었다. 실제 검사 통과가 아니다. |
| `status: "baselineFailed"` | 원래 코드의 테스트부터 실패했다. 먼저 그 실패를 해결한다. |
| `status: "toolError"` 또는 `"backendError"` | 검사 도구 실행에 문제가 생겼다. 제공된 `diagnostic`을 확인한다. |
| `status: "backendNotAdmitted"` | 도구가 승인 목록에 없어 기본 검사를 실행하지 않았다. |
| `status: "cancelled"` | 검사가 취소되었다. |

`plan`과 `doctor`의 성공도 품질 검사를 실행했다는 뜻은 아니다. `--file`, `--function`, `--tests`, `--changed` 또는 일부 모듈·언어를 선택한 결과는 `certified: false`다. 실험 모드에서도 전체 인증을 발급하지 않는다. `admitted`는 사용한 도구의 승인 여부로, 코드 점수와는 별도다.

## 출력 예시

아래는 두 함수가 있는 검증용 Python 파일의 측정 사례다. `add_one`은 테스트가 실행했고 `unrelated`는 실행하지 않았다. 텍스트 출력은 다음과 같다.

```text
SENTINEL check: exit 2, certified=false
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
