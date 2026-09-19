# 문서 안내

각 문서의 내용과 함께 확인할 코드·설정 경로입니다.

`docs/manifest.json`을 수정한 뒤 `python scripts/docs_lint.py --write-index`로 이 목록을 갱신합니다.
코드 변경에 필요한 문서는 `python scripts/docs_lint.py --base HEAD`로 확인합니다.
Python 명령은 환경에 맞게 Windows에서 `py -3`, Linux에서 `python3`로 바꿀 수 있습니다.
검사는 관련 문서의 실제 변경 여부를 확인하며, 설명이 정확한지는 사람이 검토해야 합니다.

| 문서 | 내용 | 관련 코드·설정 |
| --- | --- | --- |
| [README.en.md](../README.en.md) | 영문 설치·스킬 사용 가이드, 실행 명령과 JSON 결과 해석 | `README.md` |
| [README.md](../README.md) | 수정 기본 모드, 목적별 스킬, JSON 해석과 실험 PDF | `docs/evidence/*.pdf`, `plugins/sentinel/skills/*/SKILL.md`, `plugins/sentinel/skills/sentinel/references/*.md`, `pyproject.toml`, `src/sentinel/bundle.py`, `src/sentinel/cli.py`, `src/sentinel/diagnostics.py`, `src/sentinel/gate.py`, `src/sentinel/protocol.py`, `src/sentinel/setup.py` |
| [docs/contributing.md](contributing.md) | 문서 색인·소스 연결표 관리, diff 검사와 push 훅 사용 | `.githooks/**`, `.github/workflows/**`, `docs/manifest.json`, `scripts/docs_lint.py`, `scripts/verify_native.py`, `scripts/verify_repository.sh`, `tests/test_docs_lint.py` |
| [docs/evidence/quality-goals-study.md](evidence/quality-goals-study.md) | 54회 실험의 그룹별 목표·관측값과 원문 PDF 안내 | `docs/evidence/*.pdf` |
| [docs/references/sentinel-cli-reference.md](references/sentinel-cli-reference.md) | CLI 옵션, 설정 파일, 도구 승인과 종료 상태 | `scripts/admission.py`, `src/sentinel/**`, `src/sentinel/admission.json`, `src/sentinel/admission.py` |
| [docs/references/sentinel-quality-tools-reference.md](references/sentinel-quality-tools-reference.md) | 언어별 검사 도구와 측정 방식 | `src/sentinel/admission.json`, `src/sentinel/setup.py` |
| [docs/results.md](results.md) | 검사 범위, 명령 성공과 품질 합격의 구분, 점수·위치와 JSON 조각별 해설 | `src/sentinel/cli.py`, `src/sentinel/diagnostics.py`, `src/sentinel/gate.py`, `src/sentinel/protocol.py` |
| [plugins/sentinel/README.md](../plugins/sentinel/README.md) | Claude Code·Codex 플러그인의 설치 경로와 역할 | `.agents/plugins/*.json`, `.claude-plugin/*.json`, `plugins/sentinel/.claude-plugin/*.json`, `plugins/sentinel/.codex-plugin/*.json` |
| [plugins/sentinel/skills/check/SKILL.md](../plugins/sentinel/skills/check/SKILL.md) | check의 점수 측정·결과 보고 전용 동작 | 직접 관리하는 안내 문서 |
| [plugins/sentinel/skills/sentinel/SKILL.md](../plugins/sentinel/skills/sentinel/SKILL.md) | 수정 기본 모드와 check·start·version·update 스킬 선택 | `.agents/plugins/*.json`, `.claude-plugin/*.json`, `plugins/sentinel/.claude-plugin/*.json`, `plugins/sentinel/.codex-plugin/*.json`, `src/sentinel/cli.py`, `src/sentinel/selection.py` |
| [plugins/sentinel/skills/sentinel/references/measurement.md](../plugins/sentinel/skills/sentinel/references/measurement.md) | 공통 검사 범위 선택과 JSON 점수·위치 해석 | 직접 관리하는 안내 문서 |
| [plugins/sentinel/skills/sentinel/references/repair.md](../plugins/sentinel/skills/sentinel/references/repair.md) | 기준과 원래 범위를 유지하는 반복 수정 절차 | 직접 관리하는 안내 문서 |
| [plugins/sentinel/skills/sentinel/references/setup.md](../plugins/sentinel/skills/sentinel/references/setup.md) | 첫 호출 설치 안내, Linux·macOS 준비와 Windows WSL 호출 | `pyproject.toml`, `src/sentinel/bundle.py`, `src/sentinel/setup.py` |
| [plugins/sentinel/skills/sentinel/references/update.md](../plugins/sentinel/skills/sentinel/references/update.md) | 호스트 플러그인·실행기·승인된 언어 도구 갱신 순서 | 직접 관리하는 안내 문서 |
| [plugins/sentinel/skills/start/SKILL.md](../plugins/sentinel/skills/start/SKILL.md) | start 호출의 설치·초기 설정과 준비 완료 판정 | `plugins/sentinel/skills/sentinel/references/setup.md`, `src/sentinel/gate.py`, `src/sentinel/setup.py` |
| [plugins/sentinel/skills/update/SKILL.md](../plugins/sentinel/skills/update/SKILL.md) | 현재 설치한 SENTINEL 구성요소의 공식 배포판 갱신 | 직접 관리하는 안내 문서 |
| [plugins/sentinel/skills/version/SKILL.md](../plugins/sentinel/skills/version/SKILL.md) | 플러그인·실행기·언어 도구 버전과 설치 상태 확인 | 직접 관리하는 안내 문서 |
