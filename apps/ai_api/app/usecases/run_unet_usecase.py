from app.presentation.requests.inference_request_dto import InferenceUploadRequestDto
from packages.contracts.inference import UnetInferenceResponse


def run_unet_usecase(req: InferenceUploadRequestDto, runner) -> UnetInferenceResponse:
    """U-Net 추론 + floorplan priors (OCR/line) 같이 반환.

    runner 시그니처: (file_id, image_bytes, filename) → (prob_npy_path, metrics, priors_dict)
    priors_dict = {"ocrPriors": list, "linePriors": list, "roiTransform": dict | None}
    """
    prob_map_path, metrics, priors = runner(req.file_id, req.image_bytes, req.filename)
    return UnetInferenceResponse(
        status="ok",
        task="unet",
        fileId=req.file_id,
        output={
            "wallProbNpyPath": prob_map_path,
            "wallProbOverlayPath": metrics["overlayPath"],
            # 사전 분석 priors — 백엔드가 자체 OCR/line 검출 대신 이걸 사용 (Phase 1d).
            "ocrPriors": priors.get("ocrPriors") or [],
            "linePriors": priors.get("linePriors") or [],
            "roiTransform": priors.get("roiTransform"),
        },
        metrics=metrics,
    )


__all__ = ["run_unet_usecase"]
