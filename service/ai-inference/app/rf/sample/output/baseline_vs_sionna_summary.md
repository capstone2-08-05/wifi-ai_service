# Baseline vs Sionna (golden)

- 생성 시각: 2026-04-13T07:59:08.929102+00:00
- 조건: 동일 `golden_fixtures` AP (2,2) m, z=2.5 m, 5 GHz
- 역할: **Baseline** = 2D floorplan **preview** / **Sionna** = **내부 precise** 검증 (UI는 2D heatmap 중심, 3D는 전면 아님)

## 한 줄 해석

사용자에게 보이는 것은 2D floorplan heatmap 중심이다. Baseline은 재질·개구·(선택)가구 clutter를 반영한 빠른 preview이고, Sionna는 내부 정밀 검증용 precise 엔진으로 같은 축에서 RSS를 비교한다. 수치 1:1 일치는 목표가 아니다.

## 지표

| 항목 | Baseline | Sionna RSS (dBm) |
|------|----------|------------------|
| mean | -24.327 | -32.4371455905851 |
| min | -29.031 | -33.92560450370227 |
| max | 0.000 | -30.604882062204794 |


## 상세

- Baseline `metrics`: JSON `baseline.metrics`
- Sionna: JSON `sionna` 블록
