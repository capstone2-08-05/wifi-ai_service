# 가구·장애물 (baseline preview, 최소 모델)

## 목적

교수님 피드백에 맞춰 **“가구 배치를 바꾸면 Wi-Fi 품질이 달라질 수 있다”**는 설명을 **코드로 연결**하기 위한 **최소** 규칙이다.  
물리적으로 완전한 3D 산란 모델이 아니라, **2D floorplan preview**에서 쓸 수 있는 **단순 clutter**이다.

## Scene `objects[]` (선택)

`Scene.from_dict`는 이미 `objects` 배열을 허용한다. 아래 형태의 항목만 baseline이 **추가 감쇠**로 해석한다.

### 지원 형식: `footprint_m` 직사각형 + `attenuation_db`

```json
{
  "id": "desk_01",
  "kind": "furniture_preview",
  "footprint_m": {
    "min_x": 1.0,
    "max_x": 2.2,
    "min_y": 0.5,
    "max_y": 1.0
  },
  "attenuation_db": 3.0
}
```

- **의미**: 수신 격자점 \((x,y)\)가 `footprint_m` **안에 있으면** 해당 항목의 `attenuation_db`를 **합산**해 RSSI에서 뺀다 (발 위치 clutter).
- `kind`가 없어도 `footprint_m` + `attenuation_db`가 있으면 동일하게 처리한다.
- **합산 상한**: `BaselineRfSimulator` 내부에서 과도한 중첩을 막기 위해 **가구 clutter 합은 상한(예: 25 dB)** 으로 캡한다.

## Sionna RT

가구를 **3D 메시**로 넣는 것은 별도 작업이다. 현재 PoC는 **방 기하 + 내부 precise 엔진**에 집중한다.  
서비스 메시지상으로는 **“preview는 2D 객체 규칙, precise는 Sionna 내부 검증”**으로 구분한다.

## 한계

- AP–가구–수신 사이의 **그림자 방향**은 모델링하지 않는다 (preview 한계).  
- 정밀도가 필요하면 **Sionna 쪽 기하**를 확장하는 별도 스프린트로 다룬다.
