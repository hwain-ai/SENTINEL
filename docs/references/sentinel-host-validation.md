# SENTINEL 호스트·WSL 실제 검증

검증일: 2026-09-16. 지원 범위는 Python·TypeScript·Java다. 설치 상태, 스킬 발견, 실제 명령 호출, 품질 판정을 각각 구분한다. 이 기록은 작은 검증 프로젝트의 결과이며 모든 사용자 프로젝트·빌드 방식의 지원을 보장하지 않는다.

## 환경과 준비

- Windows 호스트에서 WSL2 Ubuntu x86_64의 CLI를 호출했다. 커널은 `5.15.167.4-microsoft-standard-WSL2`, CLI용 Python은 3.12.3이다.
- 검증 루트는 WSL의 `~/.local/share/sentinel-validation-20260916`이다. CLI는 `cli-venv/bin/sentinel`, 공통 설치 폴더는 `tools`, 검증 프로젝트는 `fixtures`에 둔다.
- 언어 저장소는 WSL에서 LF 줄바꿈으로 준비했다. 잠금 파일에 따른 공식 bootstrap으로 각 SDK·검사기를 설치했다. CLI의 가상환경은 언어 검사기의 고정 SDK와 분리했다.
- Linux의 `renameat2`가 통합 설치에 필요하다. 네이티브 Windows·macOS의 통합 설치 성공을 주장하지 않는다. 언어별 여러 플랫폼 CI와 통합 제품 지원은 별개다.
- 초기 고정 어댑터는 Python 0.1.1, TypeScript 0.1.1, Java 0.1.2였다. 미검사 결과 전달을 보완한 Python·TypeScript 0.1.2, Java 0.1.3은 각각의 실제 CI 성공을 근거로 승인했다. 새 승인 목록은 이 세 버전만 포함한다.

## 실제 호스트

|호스트|설치·발견|실제 호출|현재 판정|
|---|---|---|---|
|Codex CLI 0.154.0-alpha.6.2|로컬 마켓플레이스 등록, sentinel@sentinel 설치·활성화, 새 세션에서 설치된 SKILL.md 읽기 확인|WSL doctor, 승인 전 실험 실행, 새 승인 버전 세 언어의 기본 check와 check --changed 실제 실행|기본 3회 passed/0·certified=true, 변경 없음 3회 noChanges/0·certified=false. 실험 실행의 전체 종료6·certified=false도 구분했다. 원본 파일의 전후 지문·크기·권한 동일.|
|Claude Code 2.1.273|로컬 마켓플레이스 등록, 사용자 범위 설치·활성화, 새 프로세스에서 sentinel:sentinel 스킬·명령 발견 확인|Windows 재로그인 뒤 WSL doctor, 새 승인 버전 세 언어의 기본 check와 check --changed 실제 실행|기본 3회 passed/0·certified=true, 변경 없음 3회 noChanges/0·certified=false. 도구 호출 거부 0, 원본 파일 전후 지문·크기·권한 동일. WSL의 별도 Claude 로그인은 필요하지 않았다.|

이전 TypeScript 호스트 호출은 도구 재설치와 겹친 시점에 qualityFailed/2를 반환했다. 새 버전의 분리 실행은 통과했다. 동시 재설치가 원인이라는 판단은 추정이며 당시 내부 로그가 없어 확정하지 않는다.

호스트 시험은 임시 플러그인 경로를 주입하는 방식이 아니라 실제 설치된 플러그인을 사용했다. Codex의 첫 WSL 호출은 권한 오류로 검사 전에 거부됐고 정상 승인 절차 뒤 동일 명령이 실행됐다. Claude의 이전 401 기록은 보존했다. 재로그인 뒤 첫 시험은 허용된 명령 접두사와 실제 호출의 차이로 거부됐고, 신뢰한 SENTINEL 명령만 좁게 허용한 재시험에서 실행됐다. 호스트에 검사 대상·신뢰한 CLI·도구 경로를 명시했으며 설치를 다시 시키지 않았다.

## 기존 승인 버전의 실제 언어 시험

각 언어에 통과하는 작은 소스·테스트와 품질 기준에 미달하는 약한 테스트를 준비했다. 실제 CRAP·변이 검사기를 실행했고 모의 검사기로 대체하지 않았다.

|사례|Python|TypeScript|Java|의미|
|---|---|---|---|---|
|성공|passed / 0|passed / 0|passed / 0|실제 검사, certified=true|
|품질 실패|qualityFailed / 2|qualityFailed / 2|qualityFailed / 2|테스트가 있어도 품질 기준에 미달하면 실패|
|변경 없음|noChanges / 0|noChanges / 0|noChanges / 0|실행 생략, certified=false|
|도구 누락|dependencyError / 5|dependencyError / 5|dependencyError / 5|도구를 실행하기 전에 거부|
|생산 코드 변경분|passed / 0|passed / 0|passed / 0|변경분 실제 검사|
|취소|cancelled / 8|cancelled / 8|cancelled / 8|취소 뒤 남은 자식 프로세스 0|

18사례 모두 원본 파일의 전후 지문이 같았다. Java는 별도 결과에서 성공 예제의 변이 1개가 killed, 약한 테스트 예제의 변이 1개가 survived임을 확인했다. Python의 첫 예제는 `src`를 패키지명으로 import하여 mutmut이 거부했다. 정상적인 src 배치로 예제만 고친 뒤 위 결과를 얻었으며 제품 오류로 기록하지 않는다.

추가로 README만 바뀐 세 사례에서는 실제 검사 증거가 0인데 기존 어댑터가 passed를 응답해 certified=true가 되는 결함을 재현했다. 이 결함을 고친 새 어댑터에서는 README-only가 모두 noChanges로 전달되는 것을 실제로 확인했다.

## 새 어댑터의 실제 재검증

승인 전에는 새 버전으로 세 언어의 7사례씩, 총 21사례를 실험 실행했다. 성공·품질 실패·변경 없음·도구 누락·생산 변경분·README-only·실행 중 취소를 포함한다. 당시 새 버전은 공식 승인 목록에 없었으므로 **실험 성공을 정식 인증으로 세지 않았다.** 정상 모듈의 종료 코드는 0이어도 실험 실행의 전체 종료 코드는 6이며 certified=false였다. 승인 전 기본 check가 새 버전을 backendNotAdmitted/6으로 거부하는 세 사례도 확인했다.

README-only와 변경 없음은 모두 noChanges다. 실제 품질 실패는 qualityFailed/2, 도구 누락은 dependencyError/5, 취소는 cancelled/8이다. 모든 사례에서 원본 파일을 보존했다. Python·TypeScript 런처의 준비 오류가 정상 품질 결과 없이 종료 2를 반환하면 어댑터는 backendError/6으로 구분한다.

늦은 취소는 Python mutmut·TypeScript Stryker·Java 변이 명령의 시작을 확인한 뒤 요청했다. TypeScript·Java는 반환 직후 남은 자식이 0이었다. Python은 반환 직후 한 프로세스가 관측됐고 약 1.1초 뒤 종료되어 5초 이내 0을 확인했다. 즉시 모든 자식이 사라진다고 보장하지 않으며, 이 지연과 이전 관측도 증거에 보존한다.

기존 어댑터 승인을 계속 허용하면 구버전에서 미검사 인증이 다시 발생할 수 있다. 새 버전의 CI 성공을 확인한 뒤 최신 세 버전만 승인 목록에 남기고 기존 승인 6항목은 해제했다. 기존 설치 파일과 Git 이력은 삭제하지 않았다. 사용자는 새 승인 목록을 포함한 CLI와 새 언어 도구를 함께 갱신해야 한다. setup은 기존 소스 폴더를 자동 갱신하지 않으므로 [갱신 절차](../../README.md#승인된-도구-버전-갱신)를 따른다.

정식 승인 뒤 CLI를 재설치하고 같은 21사례를 기본 모드로 재실행했다. 아래 결과는 세 언어 모두 같았다. 원본 파일은 21/21 보존됐고, 여섯 성공·실패 예제의 Git 작업 트리도 깨끗했다.

|기본 모드 사례|모듈 결과 / 전체 종료|certified|
|---|---|---|
|성공|passed / 0|true|
|품질 실패|qualityFailed / 2|false|
|변경 없음|noChanges / 0|false|
|README만 변경|noChanges / 0|false|
|도구 누락|dependencyError / 5|false|
|생산 코드 변경분|passed / 0|true|
|실제 검사 시작 뒤 취소|cancelled / 8|false|

최종 기본 실행의 Python 취소는 반환 직후 자식 1개가 남았으나 1.325초 뒤 0이었다. TypeScript·Java는 즉시 0이었다. 보존한 구버전 세 묶음은 모두 backendNotAdmitted/6, certified=false로 거부됐고 새 검사 증거가 생기지 않았다. CLI에 포함된 승인 목록과 저장소 목록의 SHA-256도 일치했다.

## main 게시와 CI 근거

2026-09-16 사용자의 명시적 main 게시 승인 후 아래 기능 수정 커밋을 게시했다. 언어별 CI는 Ubuntu x64·ARM64, macOS ARM64·Intel 네 플랫폼 모두 성공했다. 이는 언어 검사기 시험이며 macOS 통합 설치 지원을 뜻하지 않는다. 최종 승인 목록과 이 검증 기록은 기능 수정 커밋의 후속 변경이다.

|저장소|커밋|성공한 CI|확인|
|---|---|---|---|
|SENTINEL_PY|af4bf1d|[35075096625](https://github.com/hwain-ai/SENTINEL_PY/actions/runs/35075096625)|플랫폼별 전체 441개(어댑터 6개 포함), 어댑터 별도 재실행도 통과|
|SENTINEL_TS|167f6c3|[35075112436](https://github.com/hwain-ai/SENTINEL_TS/actions/runs/35075112436)|플랫폼별 전체 180개와 어댑터 6개|
|SENTINEL_JAVA|1f168eb|[35075132335](https://github.com/hwain-ai/SENTINEL_JAVA/actions/runs/35075132335)|플랫폼별 전체 274개·어댑터 3개·자체 CRAP·변이 검사|
|SENTINEL_SPEC|5b43ae4|[35075150410](https://github.com/hwain-ai/SENTINEL_SPEC/actions/runs/35075150410)|계약 시험 125개|
|SENTINEL|6a2b4a8|[35075170925](https://github.com/hwain-ai/SENTINEL/actions/runs/35075170925)|전체 341개·플러그인 형식·승인 목록 검증|

공식 `scripts/admission.py`가 세 언어 커밋의 버전·실행 파일 지문·성공한 CI를 직접 읽어 새 목록을 작성했고, lint와 GitHub 대조 verify도 통과했다. 이전 CI 결과를 새 파일 지문에 재사용하지 않았다.

## 다중 언어 설정과 회귀

Python·TypeScript·Java를 별도 폴더에 둔 실제 WSL 프로젝트에서 `--module-root`로 setup → plan → doctor → setup 재실행을 확인했다. 공백·한글이 있는 프로젝트 경로에서도 종료 0이고 재설정 전후 workspace 지문이 같았다. 기본 '.'를 모든 언어에 덮어쓰던 결함은 제거했다.

최종 독립 검토에서 공통 회귀 83개, 기존 성공 상태 변환 5개, Python 어댑터 6개, TypeScript 6개, Java 3개로 총 103개가 통과했다. 설치 중 workspace 편집은 보존하고 충돌로 종료한다. 이동한 폴더는 명시적 매핑 뒤 최종 경로를 검증한다. 실제 Python 런타임 부재를 품질 실패로 오인하지 않는 것도 별도 재현했다.

SENTINEL_SPEC의 기존 계약 시험은 125개 통과했다. 초기 SENTINEL 전체 331개 시험은 이 WSL 환경에서 실패 14·오류 35였다. 대부분 선택적 내용 고정·격리 코드가 요구하는 `fchmodat2`를 오래된 WSL 커널이 제공하지 않는 문제였고, 취소 시험 일부는 커널 대기 채널 이름이 `anon_pipe_write` 대신 `pipe_write`여서 실패했다. 이 WSL 환경의 전체 시험이 통과했다고 보고하지 않는다. 기본 세 언어 경로의 실제 취소 시험 및 위 GitHub Linux CI의 전체 341개 통과와 구분한다.

## 증거와 검증 한계

로컬 작업 공간의 `validation-runtime-20260916/baseline-evidence/summary.json`에 초기 18사례의 상태·시간·원본 보존을 기록했다. 언어별 matrix 파일, engine-evidence, docs-only-original-adapters.json과 다중 언어 setup 결과를 함께 보관한다. `validation-2026-09-16/hosts`에는 두 실제 호스트의 구조화된 실행 기록과 답변이 있다. 새 어댑터의 실험 21사례는 experimental-summary.json, 승인 전 기본 거부는 new-adapters-before-admission.json에 별도로 기록했다. 최종 기본 21사례와 구버전 거부는 `validation-runtime-20260916/evidence/final-matrix-verification.json`, `summary.json`, `retired-adapters-rejected.json`에, 소스·승인 지문은 final-source-audit.json에 있다. CI 근거는 `validation-2026-09-16/ci-results.json`에 저장했다. 인증 토큰은 증거에 포함하지 않는다.

두 호스트의 최종 기본 검사와 변경 없음 검사는 각각 `codex-check-approved-summary.json`, `claude-check-approved-summary.json`에 기록했다. 호스트별 실제 결과 6개와 원본 보존을 확인했다. main 게시·언어 CI·새 버전 승인·기본 21사례·두 호스트의 실제 호출까지 요청된 검증을 완료했다. 이전 자동 승인 검토에서 main 게시가 보류된 기록은 사용자의 명시적 게시 승인으로 해소됐다. 기록을 갱신할 때 실패를 지우고 성공만 남기지 않는다.

남은 확장 검증은 더 큰 실제 사용자 프로젝트와 다른 Linux CPU·커널 조합이다. 현재 WSL 커널의 전체 시험 실패와 Python 취소 시 짧은 정리 지연은 위에 명시한 한계로 남는다. macOS·네이티브 Windows의 통합 설치 성공이나 운영 환경의 보안 격리는 이번 결과로 주장하지 않는다.
