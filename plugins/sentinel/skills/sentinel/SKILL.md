---
name: sentinel
description: 기본 SENTINEL 요청은 CRAP·mutation 기준을 통과할 때까지 코드·테스트 수정과 재검사를 수행한다. 점수만 확인하려면 check, 설치는 start, 버전 확인은 version, 배포판 갱신은 update를 사용한다.
---

# SENTINEL 기본 실행

기본 호출은 **요청한 범위가 기존 CRAP·mutation 기준을 통과할 때까지 수정·재검사**하는 작업이다. [반복 수정 절차](references/repair.md)를 따른다. 파일·함수를 지정하지 않았다면 현재 프로젝트의 설정된 전체 범위를 대상으로 한다. 현재 프로젝트를 확인할 수 없을 때만 경로를 묻는다.

사용자가 명시한 작업 제한이 기본 동작보다 우선한다.

실행기 0.4.0 이상을 사용한다. 설치 상태 확인 명령은 `sentinel version`이다.

| 요청 | 사용할 지침 |
|---|---|
| 기본 호출, 통과할 때까지 수정 | [fix와 공통 절차](references/repair.md) |
| check, 점수만, 수정하지 말고 확인 | [check](../check/SKILL.md) |
| 설치·초기 설정만 | [start](../start/SKILL.md) |
| 버전·설치 상태만 | [version](../version/SKILL.md) |
| 공식 배포판을 최신으로 적용 | [update](../update/SKILL.md) |
| 제작자가 원본 도구 버전을 올리는 개발 작업 | [upgrade-tools](../upgrade-tools/SKILL.md) |

사용법이나 개념 설명만 요청했다면 설치·검사·수정을 실행하지 않는다. SENTINEL 실행기는 측정값과 JSON을 반환하며, 요구사항 확인과 코드·테스트 수정은 이 스킬을 수행하는 코딩 에이전트가 담당한다.
