from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse

async def validation_exception_handler(request: Request, exc):
    return JSONResponse(
        status_code=422,
        content={"message": "Validation Error", "details": str(exc)},
    )

class RAGException(Exception):
    def __init__(self, message: str):
        self.message = message
