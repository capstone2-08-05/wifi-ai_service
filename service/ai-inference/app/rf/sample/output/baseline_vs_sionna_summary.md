# Baseline vs Sionna — 발표용 최종본 (golden)

- 생성 시각(UTC): 2026-04-13T10:59:43.203213+00:00
- 조건: 동일 `golden_fixtures` — AP (2, 2) m, z = 2.5 m, 5 GHz, 그리드 해상도 1 m
- Sionna 수치 출처: **frozen_snapshot** (`live_run` = 이번 RadioMap 재실행, `frozen_snapshot` = `sionna_poc_frozen.json` 에 저장된 PoC 성공값)

## 한 줄

**Baseline = 빠른 미리보기 · Sionna = 정밀 검증 · 같은 입력 축에서 둘 다 동작**

수치 우열이 아니라 역할 차이: 제품 UX는 preview, 내부/연구는 precise로 같은 DTO·씬 축을 공유한다.

## 해석 (한 줄)

같은 입력 축(golden)에서 Baseline은 빠른 preview, Sionna는 precise 검증이다. 수치 1:1 일치는 목표가 아니며, 제품은 2D heatmap 중심이다.

## 역할 비교 (preview vs precise)

- **사용자에게 보이는 주 화면**: preview — 2D floorplan + heatmap 중심, 빠른 반복 / precise — 동일 제품 축에서 내부 검증(레이트레이싱·3D 기하)
- **목적**: preview — 배치·재질·개구·가구 배치 변화를 즉시 시각화 / precise — 동일 입력 축에서 정밀 RSS/경로 특성 참고
- **수치 일치**: preview — preview용 단순 모델 / precise — 1:1 일치는 목표 아님 (역할이 다름)


## 복잡 씬에 대한 판단

복잡 씬(`rf_scene_input_complex.json`)은 Baseline preview 데모용. Sionna PoC 메시는 단순 방 고정이라 **이 씬과의 동시 비교는 하지 않음**.

## 지표 표 (동일 golden 입력 축)

| 항목 | Baseline (preview) | Sionna (precise) |
|------|-------------------|------------------|
| mean (dBm) | -24.327 | -32.4371455905851 |
| min (dBm) | -29.031 | -33.92560450370227 |
| max (dBm) | 0.000 | -30.604882062204794 |


## 슬라이드용 표 (복사용)

| 구분 | Baseline (preview) | Sionna (precise) |
|------|-------------------|------------------|
| 역할 | 빠른 2D heatmap | 레이트레이싱 RadioMap |
| RSSI mean (dBm) | -24.33 | -32.44 |
| RSSI min (dBm) | -29.03 | -33.93 |
| RSSI max (dBm) | 0.0 | -30.6 |


## 상세

- 전체 JSON: `baseline_vs_sionna_summary.json` 의 `baseline`, `sionna`, `presentation`, `complex_baseline_preview`
- Sionna PoC 스냅샷: `sionna_poc_frozen.json` (라이브 실행 성공 시 갱신; 실패 시 발표용으로 동일 파일 fallback)

## 발표 캡처 참고 (Baseline heatmap 예시)

- 단일 AP: `sample/output/presentation_final/01_manual_single_ap/strongest_rssi_heatmap.png`
- 2 AP 후보: `sample/output/presentation_final/02_auto_candidate_2ap/strongest_rssi_heatmap.png`
- 복잡 씬 Baseline: `sample/output/pipeline_complex_demo/strongest_rssi_heatmap.png`

(Sionna는 RadioMap 수치·내부 검증 위주; 슬라이드에는 위 **역할 표**와 golden 수치 표를 권장.)
