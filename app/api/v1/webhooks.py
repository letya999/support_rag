from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Request, Response, BackgroundTasks, Body, Header, Query
from app.services.webhook_service import WebhookService
from app.api.webhook_schemas import (
    WebhookCreate, WebhookResponse, WebhookResponseFull, WebhookUpdate,
    WebhookDeliveryResponse, WebhookSecretResponse,
    IncomingWebhookResponse, IncomingWebhookRequest
)
from app.api.v1.limiter import critical_limiter, standard_limiter

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

# --- Management Endpoints ---

@router.post("/register", response_model=WebhookResponseFull, status_code=201, dependencies=[Depends(critical_limiter)])
async def register_webhook(webhook: WebhookCreate):
    result = await WebhookService.register_webhook(webhook)
    # response model expects secret_hash, but we might want to return the plain secret once
    # For compatibility, let's map 'secret' to 'secret_hash' in response or just use the dict
    return result

@router.get("", response_model=List[WebhookResponse])
async def list_webhooks(
    limit: int = 20, 
    offset: int = 0, 
    active: Optional[bool] = None
):
    return await WebhookService.list_webhooks(limit, offset, active)

@router.get("/{webhook_id}", response_model=WebhookResponse)
async def get_webhook(webhook_id: str):
    webhook = await WebhookService.get_webhook(webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return webhook

@router.patch("/{webhook_id}", response_model=WebhookResponse)
async def update_webhook(webhook_id: str, updates: WebhookUpdate):
    webhook = await WebhookService.update_webhook(webhook_id, updates)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return webhook

@router.delete("/{webhook_id}")
async def delete_webhook(webhook_id: str):
    success = await WebhookService.delete_webhook(webhook_id)
    if not success:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return {"status": "deleted", "webhook_id": webhook_id}

@router.get("/{webhook_id}/deliveries", response_model=List[WebhookDeliveryResponse])
async def get_webhook_deliveries(
    webhook_id: str,
    limit: int = 20,
    status: Optional[str] = None
):
    # check if webhook exists first?
    return await WebhookService.get_deliveries(webhook_id, limit, status)

# --- Incoming Webhooks ---

@router.post("/incoming/message", status_code=202)
async def incoming_message(
    request: Request,
    x_webhook_signature: str = Header(None, alias="X-Webhook-Signature"),
    x_webhook_id: str = Header(None, alias="X-Webhook-ID")
):
    # Verify signature if ID is provided and we can find the secret
    # If generic, maybe we have a system-wide secret? 
    # For now, if x_webhook_id is provided, we try to verify.
    if x_webhook_id:
        webhook = await WebhookService.get_webhook(x_webhook_id)
        if webhook:
            body = await request.body()
            secret = webhook.get("secret_hash") # Using stored secret
            if secret and not WebhookService.verify_signature(body, x_webhook_signature, secret):
                 raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Assuming payload matches structure, otherwise validation error manually?
    # Or strict typing? Let's use loose parsing for flexibility as per plan
    
    event_type = payload.get("event_type", "message.received")
    
    result = await WebhookService.process_incoming_webhook(
        event_type=event_type,
        source=payload.get("source", "unknown"),
        data=payload.get("data", {}),
        metadata=payload.get("metadata", {})
    )
    
    return {"data": result}

@router.post("/incoming/document", status_code=202)
async def incoming_document(request: Request):
    # Similar logic, just different event type assumption
    try:
        payload = await request.json()
    except:
        raise HTTPException(status_code=400, detail="Invalid JSON")
        
    result = await WebhookService.process_incoming_webhook(
        event_type="document.upload",
        source=payload.get("source", "unknown"),
        data=payload.get("data", {}),
        metadata=payload.get("metadata", {})
    )
    return {"data": result}

@router.post("/incoming/event", status_code=202)
async def incoming_event(request: Request):
    try:
        payload = await request.json()
    except:
        raise HTTPException(status_code=400, detail="Invalid JSON")
        
    result = await WebhookService.process_incoming_webhook(
        event_type="custom.event",
        source=payload.get("source", "unknown"),
        data=payload.get("data", {}),
        metadata=payload.get("metadata", {})
    )
    return {"data": result}

@router.post("/deliveries/{delivery_id}/retry")
async def retry_delivery(delivery_id: str):
    result = await WebhookService.retry_delivery(delivery_id)
    if not result:
        raise HTTPException(status_code=404, detail="Delivery not found")
    return {"data": result}

