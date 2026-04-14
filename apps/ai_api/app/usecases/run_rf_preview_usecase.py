from app.presentation.requests.rf_request_dto import RfRunRequestDto


def run_rf_preview_usecase(body: RfRunRequestDto, runner):
    return runner(body)
