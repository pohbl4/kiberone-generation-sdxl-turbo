from fastapi import HTTPException, status


def error_response(code: str, message: str, http_status: int) -> HTTPException:
    return HTTPException(status_code=http_status, detail={"error": {"code": code, "message": message}})


def unauthorized() -> HTTPException:
    return error_response("UNAUTHORIZED", "Требуется авторизация", status.HTTP_401_UNAUTHORIZED)
