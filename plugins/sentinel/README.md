# SENTINEL 호스트 플러그인 소스

이 폴더는 Codex와 Claude Code가 같은 SENTINEL 스킬을 찾도록 준비한 플러그인 소스다. 스킬은 검사 요청을 처리하는 지침이다. 저장소 루트의 `.claude-plugin/marketplace.json`(Claude Code)과 `.agents/plugins/marketplace.json`(Codex)이 이 폴더를 가리키므로, 저장소 자체를 마켓플레이스로 등록해 설치한다. 이 묶음만으로 품질을 인증하지 않는다.

## 구성

- `.codex-plugin/plugin.json`: Codex용 플러그인 설정
- `.claude-plugin/plugin.json`: Claude Code용 플러그인 설정
- `skills/sentinel/SKILL.md`: 두 호스트가 함께 사용하는 검사 지침

두 설정은 모두 같은 `./skills/` 폴더를 가리킨다. 별도 연결 프로그램·서버·자동 실행 훅·언어 개발 도구·검사 엔진은 포함하지 않는다.

## 전제 조건과 경계

사용자가 선택한, 이미 설치되어 신뢰할 수 있는 SENTINEL 0.1.0 실행 파일과 검사할 프로젝트 경로가 필요하다. 이 폴더는 Python 설치 묶음과 별개다. 폴더 전체를 복사해도 플러그인 파일만 전달되며 SENTINEL 명령과 언어 도구는 함께 설치되지 않는다.

플러그인 자체를 만드는 데 컨테이너는 필요하지 않다. 검사 실행의 격리와 시작·종료·정리는 공통 SENTINEL 실행기가 담당한다. 플러그인은 기본 `check`의 거부를 우회하거나 언어별 검사 엔진을 직접 실행하지 않는다.

언어 SDK와 도구 묶음이 없을 때 스킬이 실행할 수 있는 설치 경로는 `sentinel setup` 하나뿐이며, 실행 전에 언어와 기준값(CRAP 상한, 변이 최소 kill 비율)을 사용자에게 확인한다. setup의 동작은 [저장소 README](../../README.md#첫-실행-설정)에 있다.

## 소스 검증

SENTINEL 저장소 루트에서 호출 규칙을 시험한다.

```bash
# python3 = Python 실행기; -B = 캐시 파일 생성 금지; -m unittest = 테스트 실행
# discover = 테스트 찾기; -s tests = 검색 폴더; -p = 파일 이름; -v = 상세 결과
python3 -B -m unittest discover -s tests -p test_host_plugin.py -v
```

아래 두 변수에 로컬 Codex의 플러그인·스킬 제작 지침 폴더를 각각 지정한 뒤 파일 구조를 검사한다.

```bash
# python3 = Python 실행기; PLUGIN_CREATOR_SKILL = 플러그인 제작 지침 폴더
# validate_plugin.py = 플러그인 구조 검사; plugins/sentinel = 검사할 플러그인
python3 "$PLUGIN_CREATOR_SKILL/scripts/validate_plugin.py" plugins/sentinel
# SKILL_CREATOR_SKILL = 스킬 제작 지침 폴더; quick_validate.py = 스킬 구조 검사
# plugins/sentinel/skills/sentinel = 검사할 지침 폴더
python3 "$SKILL_CREATOR_SKILL/scripts/quick_validate.py" plugins/sentinel/skills/sentinel
```

위 검사는 소스 구조만 확인한다. 실제 호스트 설치·활성화나 프로젝트 품질 검사를 대신하지 않는다.
