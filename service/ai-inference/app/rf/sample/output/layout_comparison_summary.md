# RF 레이아웃 비교 요약 (baseline)

## 실험 목적

동일한 실내 씬에서 AP 배치 전략만 바꿔 baseline RF 모델로 strongest RSSI를 비교한다. 단일 수동 배치 대비 휴리스틱 후보(top-1, top-2)가 평균·최저 RSSI와 커버리지·데드존에 어떤 영향을 주는지 정량적으로 보여 주기 위한 실험이다.

## 비교한 layout

- **manual**: 사용자(발표)가 고정한 단일 AP 배치
- **candidate_top1**: 휴리스틱 후보 1위만 반영한 단일 AP
- **candidate_top2**: 휴리스틱 상위 2개 후보를 반영한 2AP 배치

- scene: `C:\Users\soohyun\Desktop\wifi-ai_service\service\ai-inference\app\rf\sample\rf_scene_input_complex.json`
- config: `C:\Users\soohyun\Desktop\wifi-ai_service\service\ai-inference\app\rf\sample\sim_config_complex.json` (grid 0.25 m)

## 핵심 수치

| layout | mean RSSI (dBm) | min RSSI (dBm) | ≥-67 | ≥-70 | dead<-75 | wall loss μ (dB) | serving (counts) |
|--------|-----------------|----------------|------|------|----------|------------------|------------------|
| manual | -60.44 | -75.30 | 0.798 | 0.871 | 0.004 | 2.542 | ap_001=1617 |
| candidate_top1 | -57.64 | -72.37 | 0.950 | 0.977 | 0.000 | 2.613 | ap_001=1617 |
| candidate_top2 | -52.11 | -65.28 | 1.000 | 1.000 | 0.000 | 0.876 | ap_001=836, ap_002=781 |

## 한 줄 해석

후보 기반 2AP 배치에서 평균 RSSI가 단일 AP 대비 약 8.33 dB 개선되었다. 최저 RSSI는 약 10.02 dB 개선되어 약한 구간이 완화되었다. 평균 벽 손실은 다중 AP·서빙 구역 분담으로 상대적으로 완화된 것으로 나타난다. top-1 대비 top-2는 평균 RSSI 차이 5.53 dB.
