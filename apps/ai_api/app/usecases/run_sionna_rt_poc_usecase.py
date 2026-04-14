from __future__ import annotations

from typing import Any

from app.presentation.requests.rf_request_dto import SionnaRtPocRequestDto


def run_sionna_rt_poc_usecase(body: SionnaRtPocRequestDto, runner) -> dict[str, Any]:
    return runner(body)
