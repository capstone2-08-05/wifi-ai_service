from app.presentation.requests.inference_request_dto import InferenceUploadRequestDto
from packages.contracts.inference import UnetInferenceResponse


def run_unet_usecase(req: InferenceUploadRequestDto, runner) -> UnetInferenceResponse:
    prob_map_path, metrics = runner(req.file_id, req.image_bytes, req.filename)
    return UnetInferenceResponse(
        status="ok",
        task="unet",
        fileId=req.file_id,
        output={
            "wallProbNpyPath": prob_map_path,
            "wallProbOverlayPath": metrics["overlayPath"],
        },
        metrics=metrics,
    )


__all__ = ["run_unet_usecase"]
