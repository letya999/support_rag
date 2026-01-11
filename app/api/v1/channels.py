from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, Field
from typing import Optional
from app.api.v1.models import Envelope, MetaResponse
from app.services.channel_service import channel_service
import logging

router = APIRouter(tags=["Channels"])
logger = logging.getLogger(__name__)

# Models
class ChannelMessageRequest(BaseModel):
    channel: str = Field("telegram", description="Channel name (e.g. telegram)")
    user_id: str = Field(..., description="Target user ID (external ID)")
    message: str = Field(..., description="Message content")

class ChannelMessageUpdate(BaseModel):
    message: str = Field(..., description="New message content")
    user_id: str = Field(..., description="Target user ID (required for Telegram edit)")

class MessageResponse(BaseModel):
    message_id: str
    status: str

# Endpoints

@router.post("/channels/messages", response_model=Envelope[MessageResponse])
async def send_channel_message(request: Request, body: ChannelMessageRequest):
    """
    Send a message to a channel (bypassing RAG).
    """
    trace_id = getattr(request.state, "trace_id", None)
    
    try:
        result = await channel_service.send_message(body.channel, body.user_id, body.message)
        
        # Telegram returns 'result': {'message_id': ...}
        msg_id = str(result.get("result", {}).get("message_id", "unknown"))
        
        return Envelope(
            data=MessageResponse(message_id=msg_id, status="sent"),
            meta=MetaResponse(trace_id=trace_id)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/channels/messages/{message_id}", response_model=Envelope[MessageResponse])
async def edit_channel_message(request: Request, message_id: str, body: ChannelMessageUpdate):
    """
    Edit a message in a channel.
    """
    trace_id = getattr(request.state, "trace_id", None)
    
    try:
        # Note: Telegram requires chat_id (user_id) to edit a message effectively
        # We assume body.channel defaults to telegram or we might need it in path/body
        channel = "telegram" 
        
        result = await channel_service.edit_message(channel, body.user_id, message_id, body.message)
        
        return Envelope(
            data=MessageResponse(message_id=message_id, status="edited"),
            meta=MetaResponse(trace_id=trace_id)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/channels/messages/{message_id}", response_model=Envelope[MessageResponse])
async def delete_channel_message(request: Request, message_id: str, user_id: str):
    """
    Delete a message in a channel.
    """
    trace_id = getattr(request.state, "trace_id", None)
    
    try:
        channel = "telegram"
        await channel_service.delete_message(channel, user_id, message_id)
        
        return Envelope(
            data=MessageResponse(message_id=message_id, status="deleted"),
            meta=MetaResponse(trace_id=trace_id)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
