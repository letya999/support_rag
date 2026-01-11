from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import time
import uuid
import logging
from app.api.v1.models import ErrorEnvelope, ErrorResponseModel, ErrorDetails

logger = logging.getLogger(__name__)

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = str(uuid.uuid4())
        
        # Add trace_id to request state for access in endpoints/handlers
        request.state.trace_id = request_id
        
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

async def global_exception_handler(request: Request, exc: Exception):
    trace_id = getattr(request.state, "trace_id", str(uuid.uuid4()))
    logger.error(f"Global exception: {exc}", exc_info=True)
    
    error_response = ErrorResponseModel(
        code="INTERNAL_SERVER_ERROR",
        message="An unexpected error occurred.",
        trace_id=trace_id
    )
    return JSONResponse(
        status_code=500,
        content=ErrorEnvelope(error=error_response).model_dump()
    )

from fastapi.exceptions import RequestValidationError

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    trace_id = getattr(request.state, "trace_id", str(uuid.uuid4()))
    details = []
    
    for error in exc.errors():
        field = ".".join(str(x) for x in error["loc"])
        reason = error["msg"]
        details.append(ErrorDetails(field=field, reason=reason))

    error_response = ErrorResponseModel(
        code="VALIDATION_ERROR",
        message="Invalid input data",
        details=details,
        trace_id=trace_id
    )
    return JSONResponse(
        status_code=422,
        content=ErrorEnvelope(error=error_response).model_dump()
    )
