from app.presentation.requests.inference_request_dto import InferenceUploadRequestDto
from app.presentation.responses.inference_response_dto import build_unet_response


def run_unet_usecase(req: InferenceUploadRequestDto, runner):
    prob_map_path, metrics = runner(req.file_id, req.image_bytes, req.filename)
    return build_unet_response(req.file_id, prob_map_path, metrics)


__all__ = ["run_unet_usecase"]
