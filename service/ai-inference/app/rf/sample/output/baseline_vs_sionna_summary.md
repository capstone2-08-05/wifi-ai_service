# Baseline vs Sionna (golden)

- 생성 시각: 2026-04-11T18:07:18.114011+00:00
- 조건: 동일 `golden_fixtures` AP (2,2) m, z=2.5 m, 5 GHz (baseline은 벽 없음 / Sionna는 메시 방)

## 한 줄 해석

Sionna 측이 아직 실행되지 않았거나 오류라 수치 비교는 불가; baseline만으로 RF 파이프라인은 동작함을 시연할 수 있다.

## 지표

| 항목 | Baseline | Sionna |
|------|----------|--------|
| mean (dBm) | -24.327 | (실패: `No module named 'sionna'`) |
| min | -29.031 | — |
| max | 0.000 | — |

Sionna 열은 `sionna.status != ok` 이면 비움. `SIONNA_RUNBOOK.md` 참고.


## 상세

- Baseline `metrics`: JSON `baseline.metrics`
- Sionna: JSON `sionna` 블록
