# SENTINEL 플러그인

Claude Code·Codex에서 **SENTINEL로 프로젝트 검사를 요청할 수 있게 하는 공통 사용 지침**입니다. 실제 검사는 별도로 설치한 SENTINEL 실행기가 수행합니다.

## 처음 사용하는 분

**[저장소 README의 단계별 사용 가이드](../../README.md#사용-가이드)를 먼저 따르세요.** 한 곳에서 설치부터 첫 검사까지 안내합니다.

| 순서 | 사용자가 할 일 |
|---|---|
| 1 | [사용할 환경과 플러그인 준비](../../README.md#1-사용할-환경과-플러그인-준비) |
| 2 | [`/sentinel:start` 또는 `$sentinel:start`로 설치·초기 설정](../../README.md#2-첫-사용-준비) |
| 3 | [원하는 검사 또는 수정·재검사 요청](../../README.md#3-에이전트에게-검사-요청) |

플러그인 설치에는 저장소를 직접 복제할 필요가 없습니다. 호스트가 GitHub에서 설치 목록과 플러그인을 가져옵니다. 이 폴더만 설치해도 실행기·언어 SDK가 함께 설치되는 것은 아닙니다.

이미 실행기와 프로젝트 설정이 있다면 새 대화에서 SENTINEL 스킬을 사용하고, **신뢰할 실행 파일·프로젝트의 절대 경로**를 알려 주세요. 별도 도구 폴더를 사용했다면 그 경로도 지정합니다. Windows에서는 WSL 배포판 이름과 Linux 경로를 전달합니다. 실제 요청문은 위 3단계에 있습니다.

플러그인 `0.3.1`은 설치·초기 설정용 [start](skills/start/SKILL.md)와 검사·수정 요청용 [sentinel](skills/sentinel/SKILL.md) 스킬을 제공합니다. `start`는 `setup`·`plan`·`doctor`로 준비 상태를 확인하고 끝냅니다. 실제 품질 검사와 코드 수정은 별도로 요청합니다.

## 무엇을 실행하나요?

| 요청 | 사용 명령 | 의미 |
|---|---|---|
| 검사 범위 확인 | `plan` | 등록된 대상을 읽음 |
| 설치 상태 진단 | `doctor` | 설치 파일의 버전·지문·승인 여부 확인 |
| 프로젝트 최초 설정 | `setup` | 필요한 언어 도구 준비와 설정 파일 생성 |
| 기본 품질 검사 | `check` | 승인된 검사기로 선택 범위 검사 |
| 함수와 테스트 선택 | `check --file src/pricing.py --function calculate_discount --tests tests/test_pricing.py` | 지정한 기능 함수와 테스트 검사. 함수명에는 괄호를 붙이지 않음 |
| 변경 코드 검사 | `check --changed` | 변경된 생산 코드 범위 검사 |

설명만 요청하면 명령을 실행하지 않습니다. 실행기가 없으면 첫 호출에서 필요한 정보와 설치 동의를 확인한 뒤 공식 실행기와 언어 도구를 준비합니다. 이미 준비된 실행기를 통한 언어 SDK 설치는 `setup`으로 수행합니다. 플러그인의 정확한 호출 규칙은 [SKILL.md](skills/sentinel/SKILL.md)에 있습니다.

`doctor`의 `ready`는 설치 상태 확인입니다. `results[].status`의 `passed`는 검사한 범위의 품질 통과, `noChanges`는 미검사입니다. `selection`은 전체 설정 범위(`allConfigured`)와 선택·변경분 범위(`partial`)를 구분합니다. [README의 JSON 결과 해석](../../README.md#json-결과-읽기)에서 예시를 확인하세요.

`exitCode`는 명령 종료 코드, `selection`은 검사 범위, `results[].status`는 품질 판정입니다. `mutation.pass`는 변이 점수의 기준 충족 여부입니다. `inScope`는 점수 계산 대상 변이 수이며 테스트 수가 아닙니다. [JSON 조각별 결과 해석](../../docs/results.md)을 참고하세요.

## 플러그인 소스 구성

- `.codex-plugin/plugin.json`: Codex용 설정
- `.claude-plugin/plugin.json`: Claude Code용 설정
- `skills/start/SKILL.md`: 두 호스트가 함께 사용하는 설치·초기 설정 지침
- `skills/sentinel/SKILL.md`: 두 호스트가 함께 사용하는 검사·수정 지침

두 설정은 같은 `./skills/`를 사용합니다. 저장소 루트의 `.agents/plugins/marketplace.json`과 `.claude-plugin/marketplace.json`이 이 폴더를 가리킵니다. 로컬 소스를 마켓플레이스로 등록할 때는 이 폴더 자체가 아닌 **SENTINEL 저장소 루트**를 지정합니다.

플러그인은 사용 지침을 제공합니다. 첫 호출에서 에이전트가 실행기와 언어 도구를 준비하고, "통과할 때까지" 요청에는 기준을 유지하며 수정·재검사를 반복합니다. Linux·macOS에서는 직접 실행하고 Windows에서는 WSL을 사용합니다.

## 소스 검증

Ubuntu/Linux의 SENTINEL 저장소 루트에서 호출 규칙을 시험합니다.

```bash
# python3 = Python 실행기; -B = 캐시 파일 생성 금지; -m unittest = 테스트 실행
# discover = 테스트 찾기; -s tests = 검색 폴더; -p = 파일 이름; -v = 상세 결과
python3 -B -m unittest discover -s tests -p test_host_plugin.py -v
```

이 테스트는 플러그인 설정과 문서의 호출 예시를 확인합니다. 실제 호스트 설치·활성화나 프로젝트 품질 검사는 별도로 실행해야 합니다. 문서를 수정할 때는 [개발 안내](../../docs/contributing.md)의 문서 검사도 실행하세요.
