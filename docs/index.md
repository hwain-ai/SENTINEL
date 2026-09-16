# SENTINEL 문서

통합 실행기와 세 언어 검사기를 아우르는 기획·설계·실행 계획·참고 문서입니다. 언어별 검증 기록은 각 언어 저장소의 docs 에 있습니다.

## 기획과 설계

* [제품 명세: 통합 진입점](product-specs/2026-09-sentinel-unified-entry.md) - 한 명령으로 여러 언어를 검사하는 플러그인의 요구
* [설계: 통합 진입점](design-docs/2026-09-sentinel-unified-entry.md) - 실행기·도구 묶음 규약·호스트 플러그인 구조
* [실행 계획: 통합 진입점](exec-plans/active/2026-09-sentinel-unified-entry.md) - 언어별 진행 상태, 현재 진행 순서, 날짜별 변경이력
* [제품 명세: 네이티브 품질 도구](product-specs/2026-08-native-quality-tools.md) - 2026-08 원안의 요구
* [설계: 네이티브 품질 도구](design-docs/2026-08-native-quality-tools.md) - 2026-08 원안의 설계
* [실행 계획: 네이티브 품질 도구](exec-plans/active/2026-08-native-quality-tools.md) - 2026-08 원안의 진행 기록

## 참고

* [호스트·WSL 실제 검증](references/sentinel-host-validation.md) - 두 호스트 설치·실제 호출, 세 언어 시험 결과와 남은 항목

* [원본 변이 도구와의 결과 비교](references/sentinel-original-tool-comparison.md) - mutmut·Stryker·mutate4java 와 숫자가 다른 이유와 세 언어 대조 표
* [실행기 개발자 참고](references/sentinel-execution-api.md) - 내부 함수, 격리 설정, 과거 시험 이력
* [네이티브 연결 경계](references/sentinel-native-connection-boundary.md) - 언어 검사기를 실행기에 연결할 때의 경계
* [외부 도구 참고 범위](references/sentinel-quality-tools-reference.md) - 언어별 외부 CRAP·변이 도구의 공식 자료와 사용 범위
* [방향성·단순화 검토](references/sentinel-direction-review.md) - 한 명령·언어별 독립 설치 방향의 검토와 언어별 순차 연결 결정

## 언어별 검증 기록(각 저장소)

* [Python](https://github.com/hwain-ai/SENTINEL_PY/blob/main/docs/sentinel-python-native-validation.md)
* [TypeScript](https://github.com/hwain-ai/SENTINEL_TS/blob/main/docs/sentinel-typescript-native-validation.md)
* [Java 상용 후보 검토](https://github.com/hwain-ai/SENTINEL_JAVA/blob/main/docs/sentinel-java-commercial-candidates.md)
