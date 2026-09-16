---
type: external-reference
updated: 2026-09-02
status: active
owner: Codex
---

# SENTINEL 외부 도구 참고 범위

이 문서는 SENTINEL v1이 사용하는 외부 도구의 공식 자료와 사용 범위만 안내한다. 실제 version·artifact·patch identity는 각 release의 lock과 manifest가 소유한다.

## Python

- [Python ast](https://docs.python.org/3/library/ast.html): callable과 제어 흐름 구문 분석에만 사용한다. (요구사항-10, 요구사항-12, 요구사항-18)
- [coverage.py JSON report](https://coverage.readthedocs.io/en/latest/commands/cmd_json.html): fresh coverage 원본 형식으로 사용한다. (요구사항-10, 요구사항-14, 요구사항-15)
- [mutmut](https://github.com/boxed/mutmut): v1 Python mutation backend 입장 시험 대상이다. SENTINEL이 candidate 완전성·typed assertion·엄격한 gate를 별도로 검증한다. (공통규칙-02, 요구사항-03, 요구사항-19, 요구사항-43)
- [Cosmic Ray](https://cosmic-ray.readthedocs.io/): mutmut 입장 시험이 실패한 release에서만 승인 가능한 단일 대체 backend 후보다. (공통규칙-02, 요구사항-03, 요구사항-19, 요구사항-43)

## TypeScript

- [TypeScript Compiler API](https://github.com/microsoft/TypeScript/wiki/Using-the-Compiler-API): TypeScript·TSX callable과 source range 분석에 사용한다. (요구사항-10, 요구사항-13, 요구사항-18)
- [Vitest](https://vitest.dev/guide/reporters): nonce가 있는 typed test event adapter의 runner 경계로 사용한다. (요구사항-04, 요구사항-22, 요구사항-25, 요구사항-26, 요구사항-43)
- [StrykerJS](https://stryker-mutator.io/docs/stryker-js/introduction/): mutation candidate plan과 raw result backend로 사용한다. Stryker 자체 score나 `Failed` 이름만으로 killed를 확정하지 않는다. (공통규칙-02, 요구사항-04, 요구사항-20, 요구사항-26, 요구사항-43)

## Java

- [JDK compiler tree API](https://docs.oracle.com/en/java/javase/17/docs/api/jdk.compiler/com/sun/source/tree/package-summary.html): method, constructor, lambda inventory에 사용한다. (요구사항-10, 요구사항-18, 요구사항-40)
- [JaCoCo report](https://www.jacoco.org/jacoco/trunk/doc/report-mojo.html): fresh method·instruction coverage 원본에 사용한다. (요구사항-10, 요구사항-14, 요구사항-15, 요구사항-40)
- [JUnit Platform TestExecutionListener](https://docs.junit.org/5.10.2/api/org.junit.platform.launcher/org/junit/platform/launcher/TestExecutionListener.html): assertion과 runner failure를 분리하는 typed event 경계다. (요구사항-22, 요구사항-25, 요구사항-26, 요구사항-40, 요구사항-43)
- [crap4java](https://github.com/unclebob/crap4java): CRAP corpus 비교 자료로만 사용한다. (공통규칙-06, 요구사항-36)
- [mutate4java](https://github.com/unclebob/mutate4java): 향후 SENTINEL_JAVA에 고정 commit을 vendor한 뒤 operator를 보존하고 standalone build·execution·typed runner·machine-report 경계만 patch할 예정이다. 현재 구현 완료 상태를 뜻하지 않는다. (공통규칙-02, 공통규칙-06, 요구사항-40, 요구사항-43)

## 공통 계약과 저장소

- [JSON Schema 2020-12](https://json-schema.org/draft/2020-12): versioned config·result·evidence·lock 계약에 사용한다. (요구사항-07, 요구사항-38, 요구사항-43, 요구사항-44)
- [GitHub deploy keys](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/managing-deploy-keys): 실행 저장소별 `SENTINEL_SPEC` read-only 접근에 사용한다. (요구사항-33, 요구사항-35, 요구사항-38, 요구사항-44)
- [SwarmForge](https://github.com/unclebob/swarm-forge): v1 구현 대상이 아니라 향후 독립 CLI 연결 대상이다. (공통규칙-04, 요구사항-05)

## 변경이력

|날짜|변경|연결 계약|
|---|---|---|
|2026-09-02|coverage.py JSON 공식 문서 URL을 교정하고 모든 참고자료에 추적 ID를 추가했다. Robert mutation backend은 향후 vendor·patch 예정임을 명확히 했다.|공통규칙-02, 공통규칙-06, 요구사항-03, 요구사항-04, 요구사항-40, 요구사항-43|
