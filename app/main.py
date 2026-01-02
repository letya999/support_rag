from fastapi import FastAPI
from app.config.settings import settings
from app.api.routes import router
from app.api.exceptions import validation_exception_handler
from fastapi.exceptions import RequestValidationError

app = FastAPI(title=settings.APP_NAME)

app.include_router(router)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

@app.get("/")
async def root():
    return {"message": "Support RAG Pipeline API is running"}
