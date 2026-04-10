from pathlib import Path
from collections import Counter

CLASS_NAMES = {
    0: "door",
    1: "window",
    2: "sofa",
    3: "bed",
    4: "sink",
    5: "toilet",
    6: "stairs",
}

label_root = Path("data/yolo/labels")

counter = Counter()
empty_files = 0
total_files = 0

for split in ["train", "val"]:
    split_dir = label_root / split
    if not split_dir.exists():
        continue

    for txt_file in split_dir.glob("*.txt"):
        total_files += 1
        lines = txt_file.read_text(encoding="utf-8").strip().splitlines()

        if len(lines) == 0:
            empty_files += 1
            continue

        for line in lines:
            parts = line.strip().split()
            if len(parts) < 5:
                continue
            cls_id = int(parts[0])
            counter[cls_id] += 1

print("=== Class Counts ===")
for cls_id, count in sorted(counter.items()):
    print(f"{cls_id} ({CLASS_NAMES.get(cls_id, 'unknown')}): {count}")

print()
print(f"total label files: {total_files}")
print(f"empty label files: {empty_files}")