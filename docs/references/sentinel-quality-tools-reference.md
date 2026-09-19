# 사용하는 외부 도구

SENTINEL은 언어별 검사기로 복잡도·커버리지·변이 결과를 수집합니다. 각 도구의 버전과 파일 지문은 해당 언어 저장소의 잠금 파일을 따릅니다.

| 언어 | 도구 | 역할 |
|---|---|---|
| Python | [Python ast](https://docs.python.org/3/library/ast.html) | 함수와 제어 흐름 구문 분석 |
| Python | [coverage.py](https://coverage.readthedocs.io/en/latest/commands/cmd_json.html) | 테스트가 실행한 코드의 커버리지 수집 |
| Python | [mutmut](https://github.com/boxed/mutmut) | 변이 생성과 테스트 실행 |
| TypeScript | [TypeScript Compiler API](https://github.com/microsoft/TypeScript/wiki/Using-the-Compiler-API) | 함수와 소스 위치 분석 |
| TypeScript | [Vitest](https://vitest.dev/guide/reporters) | 테스트 실행과 결과 수집 |
| TypeScript | [StrykerJS](https://stryker-mutator.io/docs/stryker-js/introduction/) | 변이 생성과 테스트 실행 |
| Java | [JDK compiler tree API](https://docs.oracle.com/en/java/javase/17/docs/api/jdk.compiler/com/sun/source/tree/package-summary.html) | 메서드·생성자·람다 분석 |
| Java | [JaCoCo](https://www.jacoco.org/jacoco/trunk/doc/report-mojo.html) | 메서드와 명령어 커버리지 수집 |
| Java | [JUnit Platform TestExecutionListener](https://docs.junit.org/5.10.2/api/org.junit.platform.launcher/org/junit/platform/launcher/TestExecutionListener.html) | 테스트의 단언 실패와 실행 오류 구분 |
| Java | [mutate4java](https://github.com/unclebob/mutate4java) | 변이 생성과 실행. SENTINEL 어댑터가 빌드·테스트 결과를 수집 |

SENTINEL은 테스트의 단언(assert) 실패로 발견한 변이를 `killed`로 셉니다. 예외로 끝난 변이는 `runtimeError`로 구분하므로 원본 도구가 표시하는 탐지율과 다를 수 있습니다. 상태와 계산 방식은 [결과 해석](../results.md)을 참고하세요.

통합 실행기 `0.4.0`은 Python·TypeScript 어댑터 `0.1.4`, Java 어댑터 `0.1.5`와 연결합니다. 설치 상태 확인 명령은 `version`입니다. 이 번호는 외부 변이 도구 자체의 버전과 별개입니다. [승인 목록](../../src/sentinel/admission.json)은 어댑터 파일 지문과 검증한 소스 커밋·CI 실행을 함께 기록합니다.

언어별 설치·잠금 파일·라이선스 고지는 해당 저장소에서 확인합니다.

- [Python 검사기](https://github.com/hwain-ai/SENTINEL_PY)
- [TypeScript 검사기](https://github.com/hwain-ai/SENTINEL_TS)
- [Java 검사기](https://github.com/hwain-ai/SENTINEL_JAVA)
- [공통 결과·설정 계약](https://github.com/hwain-ai/SENTINEL_SPEC): [JSON Schema 2020-12](https://json-schema.org/draft/2020-12) 형식의 스키마와 검사 규칙
