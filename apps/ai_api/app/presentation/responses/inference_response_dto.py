from packages.contracts.inference import UnetInferenceResponse, YoloInferenceResponse


def build_unet_response(file_id: str, prob_map_path: str, metrics: dict) -> UnetInferenceResponse:
    return UnetInferenceResponse(
        status="ok",
        task="unet",
        fileId=file_id,
        output={
            "wallProbNpyPath": prob_map_path,
            "wallProbOverlayPath": metrics["overlayPath"],
        },
        metrics=metrics,
    )


def build_yolo_response(
    file_id: str,
    detections: list[dict],
    preview_path: str,
    metrics: dict,
) -> YoloInferenceResponse:
    return YoloInferenceResponse(
        status="ok",
        task="yolo",
        fileId=file_id,
        output={"detections": detections, "previewPath": preview_path},
        metrics=metrics,
    )
