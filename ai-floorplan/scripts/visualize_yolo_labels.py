from pathlib import Path
import cv2

CLASS_NAMES = {
    0: "door",
    1: "window",
    2: "bathroom",
    3: "stairs",
}

split = "train"  # train or val
image_dir = Path(f"data/yolo/images/{split}")
label_dir = Path(f"data/yolo/labels/{split}")
save_dir = Path(f"data/yolo/preview/{split}")
save_dir.mkdir(parents=True, exist_ok=True)

image_files = list(image_dir.glob("*.png"))[:30]  # 앞 30개만 확인

for img_path in image_files:
    label_path = label_dir / f"{img_path.stem}.txt"

    img = cv2.imread(str(img_path))
    if img is None:
        continue

    h, w = img.shape[:2]

    if label_path.exists():
        lines = label_path.read_text(encoding="utf-8").strip().splitlines()
        for line in lines:
            parts = line.strip().split()
            if len(parts) != 5:
                continue

            cls_id = int(parts[0])
            cx, cy, bw, bh = map(float, parts[1:])

            x1 = int((cx - bw / 2) * w)
            y1 = int((cy - bh / 2) * h)
            x2 = int((cx + bw / 2) * w)
            y2 = int((cy + bh / 2) * h)

            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(
                img,
                CLASS_NAMES.get(cls_id, str(cls_id)),
                (x1, max(20, y1 - 5)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 0, 255),
                2
            )

    out_path = save_dir / img_path.name
    cv2.imwrite(str(out_path), img)

print(f"saved previews to: {save_dir}")