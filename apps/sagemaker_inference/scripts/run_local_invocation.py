"""로컬 컨테이너 (또는 dev process) 에 /invocations 요청을 쏘는 smoke 테스트.

사용 예:
  # 1. 컨테이너 띄우기
  docker run --rm -p 8080:8080 \
      -e AWS_REGION=ap-northeast-2 \
      -v ~/.aws:/root/.aws:ro \
      ai-inference:dev

  # 2. 다른 터미널에서:
  python scripts/run_local_invocation.py \
      --source s3://my-bucket/projects/p/source.png \
      --output-prefix s3://my-bucket/ai-jobs/local-test/output/
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
import uuid


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default="http://localhost:8080")
    parser.add_argument("--source", required=True, help="s3:// URI of source image")
    parser.add_argument("--output-prefix", required=True, help="s3:// prefix ending with /")
    parser.add_argument("--job-id", default=None)
    parser.add_argument("--project-id", default=None)
    parser.add_argument("--floor-id", default=None)
    args = parser.parse_args()

    job_id = args.job_id or f"local-{uuid.uuid4().hex[:8]}"
    output_prefix = args.output_prefix
    if not output_prefix.endswith("/"):
        output_prefix += "/"

    input_payload = {
        "schema_version": "1.0",
        "job_id": job_id,
        "project_id": args.project_id,
        "floor_id": args.floor_id,
        "source_image_s3_uri": args.source,
        "output_prefix": output_prefix,
        "tasks": {"wall_segmentation": True, "object_detection": True},
        "metadata": {"requested_by": "run_local_invocation.py"},
    }

    print("--- /ping ---")
    try:
        with urllib.request.urlopen(f"{args.endpoint}/ping", timeout=5) as resp:
            print(f"  status={resp.status}")
    except Exception as exc:
        print(f"  /ping failed: {exc}")
        return 2

    print(f"--- /invocations  (job_id={job_id}) ---")
    body = json.dumps(input_payload).encode("utf-8")
    req = urllib.request.Request(
        f"{args.endpoint}/invocations",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            payload = json.loads(resp.read().decode("utf-8"))
            print(f"  status={resp.status} elapsed={elapsed_ms}ms")
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            return 0
    except urllib.error.HTTPError as exc:
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        print(f"  status={exc.code} elapsed={elapsed_ms}ms")
        try:
            err_body = json.loads(exc.read().decode("utf-8"))
            print(json.dumps(err_body, indent=2, ensure_ascii=False))
        except Exception:
            pass
        print(
            f"  also check S3: {output_prefix}failure.json "
            "(container should have written application-level failure detail there)"
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
