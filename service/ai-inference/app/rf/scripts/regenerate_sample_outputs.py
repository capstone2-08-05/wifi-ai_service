"""
샘플 산출물을 한 번에 재생성한다.

  # service/ai-inference 에서
  python app/rf/scripts/regenerate_sample_outputs.py

개별 스크립트(demo_rf_pipeline, finalize_presentation, …)를 같은 순서로 연속 실행한다.
Sionna가 없으면 비교 단계만 ``--skip-sionna`` 로 건너뛴다.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_AI = Path(__file__).resolve().parents[3]
_SCRIPTS = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(description="RF 샘플 output 일괄 재생성")
    parser.add_argument(
        "--skip-sionna",
        action="store_true",
        help="compare_baseline_vs_sionna 에 --skip-sionna 전달 (sionna 미설치 시)",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="한 단계가 실패해도 다음 단계 실행",
    )
    args = parser.parse_args()

    steps: list[tuple[str, list[str]]] = [
        ("demo_rf_pipeline.py", []),
        ("finalize_presentation.py", []),
        ("layout_comparator.py", []),
        (
            "compare_baseline_vs_sionna.py",
            ["--skip-sionna"] if args.skip_sionna else [],
        ),
    ]

    for name, extra in steps:
        script = _SCRIPTS / name
        cmd = [sys.executable, str(script), *extra]
        print(f"\n=== {name} ===", flush=True)
        try:
            subprocess.run(cmd, cwd=_AI, check=True)
        except subprocess.CalledProcessError as e:
            print(f"[실패] {name} (exit {e.returncode})", file=sys.stderr)
            if not args.continue_on_error:
                raise SystemExit(e.returncode) from e

    print("\n[완료] regenerate_sample_outputs 전체 종료", flush=True)


if __name__ == "__main__":
    main()
