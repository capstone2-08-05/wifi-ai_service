import re
import shutil
import argparse
import xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image


CLASS_MAP = {
    "Door": 0,
    "Window": 1,
    "Bathroom": 2,
    "Stairs": 3,
}


def strip_ns(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def parse_points(points_str: str):
    nums = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", points_str)
    nums = [float(x) for x in nums]
    pts = []
    for i in range(0, len(nums) - 1, 2):
        pts.append((nums[i], nums[i + 1]))
    return pts


def bbox_from_points(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def normalize_yolo_bbox(xmin, ymin, xmax, ymax, w, h):
    xmin = clamp(xmin, 0, w)
    xmax = clamp(xmax, 0, w)
    ymin = clamp(ymin, 0, h)
    ymax = clamp(ymax, 0, h)

    bw = xmax - xmin
    bh = ymax - ymin
    if bw <= 1 or bh <= 1:
        return None

    cx = (xmin + xmax) / 2.0 / w
    cy = (ymin + ymax) / 2.0 / h
    nw = bw / w
    nh = bh / h
    return cx, cy, nw, nh


def iter_with_parents(root):
    stack = [(root, [])]
    while stack:
        node, parents = stack.pop()
        yield node, parents
        children = list(node)
        for ch in reversed(children):
            stack.append((ch, parents + [node]))


def get_class_tokens(elem):
    cls = elem.attrib.get("class", "")
    return cls.lower().replace("-", " ").replace("_", " ").split()


def is_group(elem):
    return strip_ns(elem.tag) == "g"


def is_bath_space_group(elem):
    if not is_group(elem):
        return False
    tokens = get_class_tokens(elem)
    return "space" in tokens and "bath" in tokens


def is_door_group(elem):
    if not is_group(elem):
        return False
    tokens = get_class_tokens(elem)
    return "door" in tokens


def is_window_group(elem):
    if not is_group(elem):
        return False
    tokens = get_class_tokens(elem)
    return "window" in tokens


def is_stairs_group(elem):
    if not is_group(elem):
        return False
    tokens = get_class_tokens(elem)
    return "stairs" in tokens


def get_direct_polygon_bbox_from_group(elem):
    all_points = []

    for child in elem:
        if strip_ns(child.tag) == "polygon":
            pts = parse_points(child.attrib.get("points", ""))
            if len(pts) >= 2:
                all_points.extend(pts)

    if len(all_points) >= 2:
        return bbox_from_points(all_points)

    return None


def get_stairs_flight_bbox(elem):
    all_points = []

    for child in elem:
        if strip_ns(child.tag) != "g":
            continue

        child_tokens = get_class_tokens(child)
        if "flight" not in child_tokens:
            continue

        for gc in child:
            if strip_ns(gc.tag) == "polygon":
                pts = parse_points(gc.attrib.get("points", ""))
                if len(pts) >= 2:
                    all_points.extend(pts)

    if len(all_points) >= 2:
        return bbox_from_points(all_points)

    return None


def collect_boxes(svg_path):
    tree = ET.parse(svg_path)
    root = tree.getroot()

    results = []

    for elem, parents in iter_with_parents(root):
        # bathroom: Space Bath / Space Bath Shower 등
        if is_bath_space_group(elem):
            bbox = get_direct_polygon_bbox_from_group(elem)
            if bbox is not None:
                xmin, ymin, xmax, ymax = bbox
                if xmax > xmin and ymax > ymin:
                    results.append(
                        (CLASS_MAP["Bathroom"], xmin, ymin, xmax, ymax, "Bathroom")
                    )
            continue

        # stairs: Stairs -> Flight -> polygon
        if is_stairs_group(elem):
            bbox = get_stairs_flight_bbox(elem)
            if bbox is not None:
                xmin, ymin, xmax, ymax = bbox
                if xmax > xmin and ymax > ymin:
                    results.append(
                        (CLASS_MAP["Stairs"], xmin, ymin, xmax, ymax, "Stairs")
                    )
            continue

        # door: Door 그룹의 직계 polygon
        if is_door_group(elem):
            bbox = get_direct_polygon_bbox_from_group(elem)
            if bbox is not None:
                xmin, ymin, xmax, ymax = bbox
                if xmax > xmin and ymax > ymin:
                    results.append(
                        (CLASS_MAP["Door"], xmin, ymin, xmax, ymax, "Door")
                    )
            continue

        # window: Window 그룹의 직계 polygon
        if is_window_group(elem):
            bbox = get_direct_polygon_bbox_from_group(elem)
            if bbox is not None:
                xmin, ymin, xmax, ymax = bbox
                if xmax > xmin and ymax > ymin:
                    results.append(
                        (CLASS_MAP["Window"], xmin, ymin, xmax, ymax, "Window")
                    )
            continue

    return results


def read_split_file(txt_path):
    items = []
    with open(txt_path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if s:
                items.append(s)
    return items


def find_sample_dir(dataset_root: Path, rel: str):
    p = dataset_root / rel
    if p.exists():
        return p

    p2 = dataset_root / rel.strip("/\\")
    if p2.exists():
        return p2

    return None


def find_image_and_svg(sample_dir: Path):
    img_candidates = [
        sample_dir / "F1_scaled.png",
        sample_dir / "F1_original.png",
    ]
    svg_candidates = [
        sample_dir / "model.svg",
    ]

    img_path = next((p for p in img_candidates if p.exists()), None)
    svg_path = next((p for p in svg_candidates if p.exists()), None)

    if img_path is None:
        pngs = list(sample_dir.glob("*.png"))
        if pngs:
            img_path = pngs[0]

    if svg_path is None:
        svgs = list(sample_dir.glob("*.svg"))
        if svgs:
            svg_path = svgs[0]

    return img_path, svg_path


def ensure_dirs(out_root: Path):
    (out_root / "images" / "train").mkdir(parents=True, exist_ok=True)
    (out_root / "images" / "val").mkdir(parents=True, exist_ok=True)
    (out_root / "labels" / "train").mkdir(parents=True, exist_ok=True)
    (out_root / "labels" / "val").mkdir(parents=True, exist_ok=True)


def convert_split(dataset_root: Path, split_txt: Path, split_name: str, out_root: Path):
    sample_list = read_split_file(split_txt)

    saved = 0
    skipped = 0
    empty_label_count = 0

    for idx, rel in enumerate(sample_list):
        sample_dir = find_sample_dir(dataset_root, rel)
        if sample_dir is None:
            skipped += 1
            continue

        img_path, svg_path = find_image_and_svg(sample_dir)
        if img_path is None or svg_path is None:
            skipped += 1
            continue

        with Image.open(img_path) as im:
            w, h = im.size

        boxes = collect_boxes(svg_path)
        yolo_lines = []

        for cls_id, xmin, ymin, xmax, ymax, cls_name in boxes:
            norm = normalize_yolo_bbox(xmin, ymin, xmax, ymax, w, h)
            if norm is None:
                continue
            cx, cy, bw, bh = norm
            yolo_lines.append(f"{cls_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")

        if len(yolo_lines) == 0:
            empty_label_count += 1

        stem = f"{sample_dir.name}_{idx:05d}"

        out_img = out_root / "images" / split_name / f"{stem}.png"
        out_lbl = out_root / "labels" / split_name / f"{stem}.txt"

        shutil.copy2(img_path, out_img)

        with open(out_lbl, "w", encoding="utf-8") as f:
            f.write("\n".join(yolo_lines))

        saved += 1

    print(f"[{split_name}] saved={saved}, skipped={skipped}, empty_labels={empty_label_count}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset_root", type=str, required=True, help="CubiCasa root path")
    parser.add_argument("--train_txt", type=str, required=True, help="train.txt path")
    parser.add_argument("--val_txt", type=str, required=True, help="val.txt path")
    parser.add_argument("--out_root", type=str, default="data/yolo", help="output root path")
    args = parser.parse_args()

    dataset_root = Path(args.dataset_root)
    out_root = Path(args.out_root)

    ensure_dirs(out_root)

    convert_split(dataset_root, Path(args.train_txt), "train", out_root)
    convert_split(dataset_root, Path(args.val_txt), "val", out_root)

    print(f"Done. YOLO dataset saved to: {out_root.resolve()}")


if __name__ == "__main__":
    main()