from typing import Dict, Any, List
import json
from enum import Enum
from pydantic import BaseModel
from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response
import yaml

# Import our schemas
from app.api.webhook_schemas import (
    IncomingWebhookRequest,
    ChatResponseGeneratedPayload,
    ChatEscalatedPayload,
    DocumentUploadedPayload,
    DocumentIndexedPayload,
    DocumentFailedPayload,
    ClassificationCompletedPayload
)

router = APIRouter()

def _pydantic_schema_to_asyncapi_message(model: BaseModel, name: str, title: str, summary: str):
    """
    Convert a Pydantic model to an AsyncAPI message definition.
    Using Pydantic's .model_json_schema() (v2) or .schema() (v1).
    """
    # Assuming Pydantic v2
    json_schema = model.model_json_schema()
    
    # Clean up schema for AsyncAPI (remove $defs if self-contained or handle refs)
    # For simplicity, we embed the properties directly if possible, or keep as is.
    
    return {
        "name": name,
        "title": title,
        "summary": summary,
        "contentType": "application/json",
        "payload": json_schema
    }

def generate_asyncapi_spec():
    """
    Dynamically generates the AsyncAPI 3.0.0 specification from Pydantic models.
    """
    
    # 1. Base Info
    spec = {
        "asyncapi": "3.0.0",
        "info": {
            "title": "Support RAG Webhooks API",
            "version": "1.0.0",
            "description": "Event-driven architecture for Support RAG system (Auto-generated).",
            "contact": {
                "name": "Support Team",
                "email": "support@example.com"
            }
        },
        "servers": {
            "production": {
                "host": "api.support-rag.com",
                "protocol": "https",
                "description": "Production server"
            }
        },
        "components": {
            "securitySchemes": {
                "webhookSignature": {
                    "type": "http",
                    "scheme": "x-hub-signature",
                    "description": "HMAC-SHA256 signature of the request body. Header: X-Webhook-Signature"
                }
            },
            "messages": {},
            "schemas": {} # If we wanted to use refs
        },
        "channels": {}
    }

    # 2. Incoming Channels (Endpoints we expose)
    
    # Incoming Message
    spec["components"]["messages"]["MessageReceived"] = _pydantic_schema_to_asyncapi_message(
        IncomingWebhookRequest, 
        "message.received", 
        "Message Received", 
        "External user message"
    )
    
    spec["channels"]["incoming/message"] = {
        "address": "/api/v1/webhooks/incoming/message",
        "messages": {
            "receiveMessage": {
                "$ref": "#/components/messages/MessageReceived"
            }
        },
        "description": "Endpoint for external systems to send chat messages."
    }

    # 3. Outgoing Channels (Events we fire)
    # We group them into logical channels for the subscriber, or one big channel "webhook/out"
    
    # Chat Events
    spec["components"]["messages"]["ChatResponseGenerated"] = _pydantic_schema_to_asyncapi_message(
        ChatResponseGeneratedPayload, "chat.response.generated", "Chat Response Generated", "RAG pipeline response"
    )
    spec["components"]["messages"]["ChatEscalated"] = _pydantic_schema_to_asyncapi_message(
        ChatEscalatedPayload, "chat.escalated", "Chat Escalated", "Session escalation event"
    )
    
    spec["channels"]["webhook/out/chat"] = {
        "address": "{webhookUrl}",
        "messages": {
            "chatGenerated": {"$ref": "#/components/messages/ChatResponseGenerated"},
            "chatEscalated": {"$ref": "#/components/messages/ChatEscalated"}
        },
        "parameters": {
            "webhookUrl": {"description": "Subscriber URL"}
        },
        "description": "Events related to chat sessions."
    }

    # Knowledge Events
    spec["components"]["messages"]["DocumentUploaded"] = _pydantic_schema_to_asyncapi_message(
        DocumentUploadedPayload, "knowledge.document.uploaded", "Document Uploaded", "File upload success"
    )
    spec["components"]["messages"]["DocumentIndexed"] = _pydantic_schema_to_asyncapi_message(
        DocumentIndexedPayload, "knowledge.document.indexed", "Document Indexed", "Indexing success"
    )
    spec["components"]["messages"]["DocumentFailed"] = _pydantic_schema_to_asyncapi_message(
        DocumentFailedPayload, "knowledge.document.failed", "Document Failed", "Processing failure"
    )

    spec["channels"]["webhook/out/knowledge"] = {
        "address": "{webhookUrl}",
        "messages": {
            "docUploaded": {"$ref": "#/components/messages/DocumentUploaded"},
            "docIndexed": {"$ref": "#/components/messages/DocumentIndexed"},
            "docFailed": {"$ref": "#/components/messages/DocumentFailed"}
        },
        "parameters": {
            "webhookUrl": {"description": "Subscriber URL"}
        },
        "description": "Events related to document ingestion."
    }
    
    # Analysis Events
    spec["components"]["messages"]["ClassificationCompleted"] = _pydantic_schema_to_asyncapi_message(
        ClassificationCompletedPayload, "analysis.classification.completed", "Classification Completed", "Auto-classification finished"
    )
    
    spec["channels"]["webhook/out/analysis"] = {
        "address": "{webhookUrl}",
        "messages": {
            "classificationCompleted": {"$ref": "#/components/messages/ClassificationCompleted"}
        },
        "parameters": {
            "webhookUrl": {"description": "Subscriber URL"}
        },
        "description": "Events related to automated analysis."
    }

    return spec

@router.get("/asyncapi.json")
async def get_asyncapi_json():
    """Return the auto-generated AsyncAPI spec as JSON."""
    return JSONResponse(content=generate_asyncapi_spec())

@router.get("/asyncapi.yaml")
async def get_asyncapi_yaml():
    """Return the auto-generated AsyncAPI spec as YAML."""
    spec = generate_asyncapi_spec()
    # Use sort_keys=False to preserve order if using Python 3.7+ dicts
    yaml_content = yaml.dump(spec, sort_keys=False, default_flow_style=False)
    return Response(content=yaml_content, media_type="application/x-yaml")
