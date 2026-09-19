---
name: fix
description: SENTINEL의 CRAP·mutation 기준에 도달할 때까지 요구사항에 맞게 코드·테스트를 수정하고 재검사한다. 기본 sentinel 스킬과 같은 동작이다.
---

# 기준 통과까지 수정

[공통 반복 수정 절차](../sentinel/references/repair.md)를 따른다. 기본 `sentinel`과 같은 동작을 명시적으로 요청하는 스킬이다. 기존 기준과 요청한 검사 범위를 유지하고, 점수만 확인하라는 추가 제한이 있으면 [check](../check/SKILL.md)로 처리한다.
