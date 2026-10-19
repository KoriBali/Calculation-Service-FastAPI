from fastapi.responses import JSONResponse


def success_response(data=None, status_code=200, unique_code=None):
    """Envelope sukses yang dibaca gateway: {success, data, unique_code?}."""
    response = {
        "success": True,
        "data": data,
    }
    if unique_code:
        response["unique_code"] = unique_code

    return JSONResponse(response, status_code=status_code)


def error_response(message="Terjadi Kesalahan", errors=None, status_code=400):
    """Envelope error: {success: false, message, errors?}."""
    response = {
        "success": False,
        "message": message,
    }
    if errors:
        response["errors"] = errors

    return JSONResponse(response, status_code=status_code)
