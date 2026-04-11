# Baseline vs Sionna (golden)

- 생성 시각: 2026-04-11T19:36:28.188061+00:00
- 조건: 동일 `golden_fixtures` AP (2,2) m, z=2.5 m, 5 GHz (baseline은 벽 없음 / Sionna는 메시 방)

## 한 줄 해석

Baseline은 경로손실+벽손실(2D) 추정이고 Sionna는 3D 레이트레이싱 RSS로 같은 AP 위치라도 맵 값이 다르다; PoC 목적은 ‘동일 입력 축에서 두 엔진이 모두 산출된다’는 점이다.

## 지표

| 항목 | Baseline | Sionna RSS (dBm) |
|------|----------|------------------|
| mean | -24.327 | -32.43714564682152 |
| min | -29.031 | -33.92560450370227 |
| max | 0.000 | -30.604882062204794 |


## 상세

- Baseline `metrics`: JSON `baseline.metrics`
- Sionna: JSON `sionna` 블록
