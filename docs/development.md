# 개발 안내

SENTINEL의 코드나 문서를 수정한 뒤 확인하는 절차입니다. 오류 제보와 수정안 제출 방법은 [기여 안내](contributing.md)를 참고하세요.

문서만 고친다면 코드 테스트인 2번을 건너뛰고, **3. 관련 문서 수정하기**와 **4. 문서 검사하기**를 확인하세요. GitHub 화면에서만 수정했다면 PR에 검사 명령을 실행하지 않았다고 적어 주세요. PR은 원본 저장소에 변경을 반영해 달라는 요청입니다.

## 1. 코드를 수정할 준비

Git과 Python 3.9 이상이 필요합니다. Git은 파일 변경 이력을 관리하는 도구입니다. GitHub의 자동 테스트는 Python 3.12를 사용하므로, 개발 환경도 3.12로 맞추면 차이를 줄일 수 있습니다.

전체 테스트는 Linux에서 실행하세요. Windows에서는 WSL2 Ubuntu 터미널을 사용합니다. WSL2는 Windows 안에서 Linux를 실행하는 기능입니다. macOS의 검사 범위는 아래 **7. GitHub에서 실행하는 검사**에 정리했습니다.

먼저 GitHub에서 저장소를 Fork해 본인 계정에 복사합니다. 아래 `YOUR-ACCOUNT`를 본인의 GitHub 계정 이름으로 바꿔 터미널에서 실행하세요.

```sh
# 본인 계정에 복사한 저장소를 컴퓨터로 내려받습니다.
git clone https://github.com/YOUR-ACCOUNT/SENTINEL.git
# 내려받은 폴더로 이동합니다. 이후 명령은 이 폴더에서 실행합니다.
cd SENTINEL
# 수정 내용을 따로 기록할 작업 공간인 브랜치를 만듭니다. 이름은 예시입니다.
git switch -c fix-contribution
```

주로 수정하는 파일은 다음 위치에 있습니다.

| 하려는 일 | 열어 볼 위치 |
| --- | --- |
| 명령 처리나 검사 결과 집계 수정 | [src/sentinel/](../src/sentinel/) |
| 수정한 동작을 확인하는 테스트 추가 | [tests/](../tests/) |
| 설치 방법이나 사용 예시 수정 | [README.md](../README.md), [README.en.md](../README.en.md) |
| 검사 결과의 뜻이나 명령 옵션 설명 수정 | [결과 해석](results.md), [명령 참고](references/sentinel-cli-reference.md) |
| 코딩 에이전트가 SENTINEL을 사용하는 절차 수정 | [plugins/sentinel/](../plugins/sentinel/) |

## 2. 코드를 고친 뒤 테스트하기

수정한 동작을 확인하는 테스트를 `tests/`에 추가하거나 고친 뒤 다음 명령을 실행합니다. 이 명령은 SENTINEL 실행기, 즉 명령을 받아 언어별 검사 도구를 실행하고 결과를 모으는 프로그램을 테스트합니다. 별도 Python 패키지 설치는 필요하지 않습니다.

```sh
# src의 코드를 불러와 tests 아래의 테스트를 모두 실행합니다.
PYTHONPATH=src python3 -B -m unittest discover -s tests -v
```

`PYTHONPATH=src`는 검사할 코드를 `src`에서 찾으라는 설정입니다. `unittest`는 Python에 포함된 테스트 도구이며, `-B`는 Python이 실행 중 만드는 캐시 파일을 남기지 않게 합니다. `discover -s tests`는 `tests` 폴더에서 테스트를 찾고, `-v`는 각 테스트 이름과 결과를 표시합니다.

마지막에 `OK`가 나오면 테스트가 통과한 것입니다. `FAILED`나 `ERROR`가 나오면 출력된 테스트 이름과 오류 내용을 확인해 원인을 고친 뒤 다시 실행하세요.

이 명령의 통과만으로 실제 Python·TypeScript·Java 검사 도구의 설치와 실행까지 확인한 것은 아닙니다. 실제 도구를 사용하는 검사는 아래 **7. GitHub에서 실행하는 검사**를 참고하세요.

## 3. 관련 문서 수정하기

명령이나 출력이 바뀌었다면 사용자가 복사할 예시도 함께 고칩니다. 예를 들어 명령 옵션을 추가했다면 옵션 설명과 실행 예시를, 결과 항목을 추가했다면 출력 예시와 그 항목의 뜻을 수정합니다.

| 바뀐 내용 | 확인할 문서 |
| --- | --- |
| 설치·실행 명령, 판정 방식 | [한국어 README](../README.md), [명령 참고](references/sentinel-cli-reference.md) |
| 검사 결과의 항목이나 출력 형식 | [결과 해석](results.md)의 출력 예시와 설명 |
| 한국어 README | [영문 README](../README.en.md)의 같은 부분 |
| 에이전트가 따라 읽는 지침인 스킬의 역할이나 사용 절차 | 해당 [스킬 파일](../plugins/sentinel/skills/)과 [README](../README.md) |
| 문서 검사나 GitHub 자동 검사 절차 | 이 개발 안내 |

한국어 README를 기준으로 영문판도 수정합니다. 명령·출력 예시·기준값은 두 언어에서 같아야 합니다. 영문판에서 한국어 문서로 연결할 때는 링크에 한국어 문서임을 표시하세요.

README에는 사용자가 에이전트에 입력할 요청과 에이전트가 실행할 명령을 구분해서 적습니다. 긴 옵션 설명은 명령 참고 문서에 두고 README에서 연결합니다.

## 4. 문서 검사하기

아래 명령은 `README.md`가 있는 저장소 최상위 폴더에서 실행합니다. 문서 검사는 Windows PowerShell에서도 실행할 수 있으며, 그때는 `python3`를 `py -3`로 바꾸세요.

```sh
# 문서 목록, 파일 존재 여부, 저장소 안의 파일 링크를 검사합니다.
python3 scripts/docs_lint.py --check
# 마지막 커밋 이후 변경한 코드에 맞춰 관련 문서도 수정했는지 검사합니다.
python3 scripts/docs_lint.py --base HEAD
```

`HEAD`는 현재 브랜치의 마지막 커밋, 즉 Git에 저장한 마지막 변경 기록입니다. 두 번째 명령은 그 기록과 현재 파일을 비교하므로 아직 커밋하지 않은 수정과 새 파일도 확인합니다.

검사가 통과하면 `docs-lint: passed`가 나옵니다. 실패했다면 출력된 파일 경로를 확인하세요.

| 출력에 포함된 문구 | 해야 할 일 |
| --- | --- |
| `Document is not indexed` | 새 문서를 아래 설명에 따라 문서 목록에 등록합니다. |
| `docs/index.md is stale` | 아래의 `--write-index` 명령으로 문서 목록 화면을 다시 만듭니다. |
| `broken local link` | 링크 대상 파일이 있는지 확인하고, 링크 경로나 파일 위치를 고칩니다. |
| `update at least one related document` | 함께 출력된 문서를 열어 바뀐 동작의 설명과 예시를 수정합니다. |

검사기는 **관련 문서를 수정했는지와 연결한 파일이 있는지** 확인합니다. 설명이 코드와 맞는지, 웹 링크가 열리는지, 링크가 문서 안의 올바른 제목으로 이동하는지는 사람이 확인해야 합니다. 문서 목록 재생성이나 공백 변경만으로는 관련 문서를 수정한 것으로 인정하지 않습니다.

### 문서를 추가하거나 옮겼다면

[manifest.json](manifest.json)은 문서 경로·요약과 코드별로 갱신할 문서를 기록한 파일입니다. `documents`에서 새 문서를 등록하거나 기존 경로를 고칩니다. 문서를 삭제했다면 해당 항목과 그 문서를 가리키는 `rules`의 경로도 수정하세요.

```sh
# manifest.json에 적힌 내용으로 docs/index.md를 다시 만듭니다.
python3 scripts/docs_lint.py --write-index
# 새로 만든 목록과 실제 파일·링크가 일치하는지 확인합니다.
python3 scripts/docs_lint.py --check
```

`docs/index.md`는 위 명령이 만드는 문서 목록입니다. 목록의 설명을 고칠 때도 `manifest.json`을 먼저 수정하세요.

<details>
<summary>코드와 문서를 연결하는 검사 규칙을 수정할 때</summary>

`manifest.json`의 `rules`에는 다음 항목이 있습니다.

| 항목 | 뜻 |
| --- | --- |
| `id` | 검사 실패 메시지에 표시할 규칙 이름 |
| `sources` | 변경 여부를 확인할 코드·설정의 경로 |
| `documents` | 위 파일이 바뀌었을 때 함께 수정할 문서의 경로 |

예를 들어 `readme-english`는 한국어 README가 바뀌면 영문 README도 수정했는지 확인합니다. 한 규칙에 문서가 여러 개 있으면 그중 하나 이상의 본문을 수정해야 합니다. 변경한 파일이 여러 규칙에 해당하면 각 규칙을 모두 충족해야 합니다.

경로는 저장소 최상위 폴더를 기준으로 적습니다. `*`는 한 단계의 파일·폴더 이름을, `**`는 그 아래 경로 전체를 포함합니다. 예를 들어 `src/sentinel/**`는 그 폴더 아래의 모든 파일을 가리킵니다. 새 코드가 기존 규칙에 포함되지 않으면 `sources`를 보완하거나 규칙을 추가하세요.

검사기는 코드의 의미를 읽지 않습니다. 주석만 수정했어도 경로가 규칙에 해당하면 관련 문서의 변경을 요구합니다. 출력된 문서에서 해당 코드의 설명을 확인하고 필요한 설명을 보완하세요. 제3자 문서의 검사 제외 경로는 `ignoreDocuments`에 기록합니다.

설치·초기 설정 절차는 [공통 설치 안내](../plugins/sentinel/skills/sentinel/references/setup.md)에 모읍니다. 설치 방법이나 기본 기준이 바뀌면 `start-context` 규칙에 연결된 `start` 스킬도 수정합니다. 스킬의 역할 변경은 `skill-usage` 규칙으로 README에 연결됩니다.

공개한 실험 원문은 [docs/evidence/](evidence/)에 보관합니다. 원문 PDF를 교체했다면 [실험 설명](evidence/quality-goals-study.md)의 출처 페이지·관측값과 README의 실험 설명도 확인하세요.

문서 검사 코드는 [scripts/docs_lint.py](../scripts/docs_lint.py)에 있습니다. 검사 동작을 바꿀 때는 [tests/test_docs_lint.py](../tests/test_docs_lint.py)의 테스트를 실행하고, 같은 스크립트를 사용하는 다른 SENTINEL 저장소에도 변경을 반영합니다. 각 저장소는 자체 스크립트로 문서를 검사하므로, 문서 검사를 위해 다른 저장소를 내려받을 필요는 없습니다.

</details>

## 5. 수정안 제출 전 확인하기

여러 번 커밋했다면 마지막 커밋 이후의 변경만 검사해서는 앞선 수정이 빠집니다. 작업 브랜치 전체를 확인하려면 다음 명령을 실행하세요.

```sh
# origin/main과 현재 파일을 비교해, 브랜치에서 바꾼 내용의 문서 갱신을 확인합니다.
python3 scripts/docs_lint.py --base origin/main
```

`origin/main`은 내 컴퓨터에 기록된 원격 저장소의 `main` 브랜치입니다. 위 준비 절차대로 Fork를 내려받았다면 본인 계정의 저장소를 가리킵니다. GitHub의 PR 검사는 원본 저장소의 대상 브랜치를 기준으로 다시 비교합니다.

수정안에는 문제 상황, 고친 내용, 실행한 검사와 결과를 적어 주세요. 실행하지 못한 검사가 있다면 그 이유도 적습니다. 커밋은 변경을 Git에 저장하는 작업이고, push는 그 커밋을 GitHub로 보내는 작업입니다. 수정한 문서도 코드와 함께 커밋한 뒤 본인 저장소의 작업 브랜치를 push하고, 원본 저장소로 PR을 보냅니다.

## 6. push 전에 문서 검사를 자동으로 실행하기

Git 훅은 Git 작업 전후에 실행하는 스크립트입니다. 이 저장소의 `pre-push` 훅은 커밋을 GitHub로 보내기 전에 문서를 검사합니다. 사용하려면 저장소마다 한 번 설정합니다.

```sh
# 이 저장소에서 사용할 훅 폴더를 지정합니다. 다른 저장소의 설정은 바꾸지 않습니다.
git config --local core.hooksPath .githooks
```

이미 `core.hooksPath`나 `.git/hooks/pre-push`를 사용하고 있다면 위 설정을 덮어쓰지 말고, 기존 훅에 [.githooks/pre-push](../.githooks/pre-push)의 검사 호출을 합치세요.

이후 push할 때 검사가 실패하면 전송이 멈춥니다. 검사는 **보낼 커밋에 저장된 파일**을 읽으므로, 컴퓨터에서만 문서를 고치고 커밋하지 않았다면 여전히 실패합니다. 새 브랜치와 여러 브랜치를 한꺼번에 push할 때도 검사하며, 브랜치를 삭제하는 push는 건너뜁니다.

## 7. GitHub에서 실행하는 검사

GitHub Actions는 저장소에 올린 코드와 문서를 자동으로 검사하는 기능입니다. 실행 결과는 PR의 검사 목록이나 저장소의 Actions 탭에서 확인합니다.

| 검사 | 실행하는 내용 |
| --- | --- |
| [문서 검사](../.github/workflows/docs.yml) | 브랜치 push와 PR에 포함된 문서 목록·링크·관련 문서 갱신 여부 확인 |
| [Linux 테스트](../.github/workflows/ci.yml) | 전체 실행기 테스트, 플러그인 설정, 사용할 언어 도구의 승인 목록 확인 |
| [macOS 테스트](../.github/workflows/ci.yml) | Intel·Apple Silicon에서 지원 명령과 설치 충돌 테스트, 실제 언어 도구 설치·검사 |

[verify_native.py](../scripts/verify_native.py)는 승인된 Python·TypeScript·Java 도구를 내려받아 `setup`(설치), `plan`(대상 확인), `version`(설치 상태 확인)을 실행합니다. 이어서 파일·함수 검사, 결함을 놓치는 테스트의 기준 미달, 테스트를 복원한 뒤 전체 재검사를 확인합니다. 이 검사는 외부 도구 설치와 실행을 포함합니다. 실험용 Go·OCI 실행 경로는 Linux 전용입니다.

<details>
<summary>문서 검사의 비교 기준과 병합 제한을 설정할 때</summary>

문서 검사는 일반 브랜치 push에서는 이전 원격 커밋과 제출 커밋을 비교합니다. PR과 새 브랜치에서는 대상 브랜치 또는 기본 브랜치와의 공통 조상부터 비교합니다. 공통 조상은 두 브랜치가 갈라지기 전 마지막으로 공유한 커밋입니다.

비교할 이력이 없으면 검사에 실패합니다. 기본 브랜치를 처음 만드는 경우에만 전체 파일을 새 문서와 대조합니다. 브랜치 삭제와 태그 push에는 이 문서 검사를 실행하지 않습니다.

로컬 훅을 우회하면 push 자체는 가능합니다. 검사에 실패한 PR의 병합도 막으려면 저장소 규칙에서 `docs / docs`를 필수 검사로 지정해야 합니다. 병합은 PR의 변경을 대상 브랜치에 반영하는 작업입니다.

</details>
