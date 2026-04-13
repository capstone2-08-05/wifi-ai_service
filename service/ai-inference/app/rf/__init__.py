"""RF preview / Baseline / Sionna 어댑터.

디렉터리 구조 (요약):

- ``dto/`` — 백엔드 합의 DTO (floorplan 스키마)
- ``adapters/`` — Baseline·Sionna 엔진별 변환
- ``conversion/`` — 씬 그래프·DTO → RF canonical dict
- ``models/`` — ``rf_models`` (Scene, ApLayout, …)
- ``materials/`` — 재질 매핑·프로파일
- ``rules/`` — objects[] 장애물 규칙
- ``simulation/`` — Baseline 시뮬레이터
- ``persistence/`` — JSON 프로토타입 저장
- ``layout/`` — AP 후보·레이아웃 빌드
- ``services/`` — ``run_rf`` 등 API 진입
- ``fixtures/`` — golden 씬 등
- ``scripts/`` — CLI 데모·샘플 export
- ``sionna_poc/`` — Sionna RT PoC
- ``tests/``, ``sample/``, ``docs/``
"""
