from fastapi import APIRouter
from app.api.v1 import chat, ingestion, analysis, taxonomy, channels, history, cache, config, system, dataset, chunks, webhooks

api_router = APIRouter()

api_router.include_router(chat.router)
api_router.include_router(ingestion.router)
api_router.include_router(analysis.router)
api_router.include_router(taxonomy.router)
api_router.include_router(channels.router)
api_router.include_router(history.router)
api_router.include_router(dataset.router)
api_router.include_router(cache.router)
api_router.include_router(config.router)
api_router.include_router(system.router)
api_router.include_router(chunks.router)
api_router.include_router(webhooks.router)


