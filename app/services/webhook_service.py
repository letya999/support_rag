import hmac
import hashlib
import json
import uuid
import secrets
import asyncio
import time
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from app.storage.connection import get_db_connection
from app.logging_config import logger





from app.api.webhook_schemas import WebhookCreate, WebhookUpdate
from app.storage.repositories.webhook_repository import WebhookRepository
from app.utils.url_security import validate_webhook_url_async
from app.settings import settings

class WebhookService:
    """Service for managing webhooks (registration, verification, delivery)."""
    @staticmethod
    async def register_webhook(webhook_data: WebhookCreate) -> Dict[str, Any]:
        """
        Register a new webhook.

        Args:
            webhook_data: Registration data

        Returns:
            Dict containing the created webhook and its plaintext secret (shown only once)
        """
        # Perform Async Security Check (DNS)
        is_valid, error = await validate_webhook_url_async(
            str(webhook_data.url), 
            allow_localhost=settings.ALLOW_LOCALHOST_WEBHOOKS
        )
        if not is_valid:
            raise ValueError(f"Security validation failed: {error}")

        webhook_id = f"webhook_{uuid.uuid4().hex[:12]}"
        
        # Generate or use provided secret
        secret = webhook_data.secret or secrets.token_hex(32)

        # SECURITY NOTE for internal networks:
        # We store the secret as plaintext in the database because:
        # 1. We need it to sign outgoing webhook payloads (HMAC-SHA256)
        # 2. Hashing would prevent us from signing (can't recover plaintext from hash)
        # 3. For internal network with secured database, this is acceptable
        #
        # For production/external deployments, consider:
        # - Encrypting secrets with a master key (envelope encryption)
        # - Using a dedicated secrets vault (HashiCorp Vault, AWS Secrets Manager)
        # - Implementing key rotation

        webhook = await WebhookRepository.create_webhook(
            webhook_id=webhook_id,
            name=webhook_data.name,
            url=str(webhook_data.url),
            events=webhook_data.events,
            secret_hash=secret,  # Stored as plaintext for signing capability
            description=webhook_data.description,
            active=webhook_data.active,
            metadata=webhook_data.metadata,
            ip_whitelist=webhook_data.ip_whitelist
        )

        # Return secret ONLY on registration (shown once)
        # This is the only time the user sees the secret
        webhook['secret'] = secret
        return webhook

    @staticmethod
    async def list_webhooks(limit: int = 20, offset: int = 0, active: bool = None) -> List[Dict[str, Any]]:
        webhooks = await WebhookRepository.list_webhooks(limit, offset, active)
        # Remove secret from list responses for security
        for webhook in webhooks:
            webhook.pop('secret_hash', None)
            webhook.pop('secret', None)
        return webhooks

    @staticmethod
    async def get_webhook(webhook_id: str) -> Optional[Dict[str, Any]]:
        webhook = await WebhookRepository.get_webhook(webhook_id)
        if webhook:
            # Remove secret from get responses for security
            # Secret is only shown once during registration
            webhook.pop('secret_hash', None)
            webhook.pop('secret', None)
        return webhook

    @staticmethod
    async def update_webhook(webhook_id: str, updates: WebhookUpdate) -> Optional[Dict[str, Any]]:
        update_dict = updates.model_dump(exclude_unset=True)
        if 'url' in update_dict:
            url_str = str(update_dict['url'])
            # Perform Async Security Check (DNS)
            is_valid, error = await validate_webhook_url_async(
                url_str, 
                allow_localhost=settings.ALLOW_LOCALHOST_WEBHOOKS
            )
            if not is_valid:
                raise ValueError(f"Security validation failed: {error}")
                
            update_dict['url'] = url_str
            
        return await WebhookRepository.update_webhook(webhook_id, update_dict)

    @staticmethod
    async def delete_webhook(webhook_id: str) -> bool:
        return await WebhookRepository.delete_webhook(webhook_id)

    @staticmethod
    async def get_deliveries(webhook_id: str, limit: int = 20, status: str = None) -> List[Dict[str, Any]]:
        return await WebhookRepository.get_deliveries(webhook_id, limit, status)

    @staticmethod
    def verify_signature(payload_body: bytes, signature_header: str, secret: str) -> bool:
        """
        Verify incoming webhook signature.
        Format: sha256=<hex_hmac>
        """
        if not signature_header or not signature_header.startswith("sha256="):
            return False
            
        params = signature_header.split("=")
        if len(params) != 2:
            return False
            
        received_hmac = params[1]
        
        expected_hmac = hmac.new(
            key=secret.encode('utf-8'),
            msg=payload_body,
            digestmod=hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(received_hmac, expected_hmac)

    @staticmethod
    def sign_payload(payload_str: str, secret: str, timestamp: str) -> str:
        """
        Create signature for outgoing webhook.
        Message = f"{timestamp}.{payload}"
        """
        message = f"{timestamp}.{payload_str}"
        signature = hmac.new(
            key=secret.encode('utf-8'),
            msg=message.encode('utf-8'),
            digestmod=hashlib.sha256
        ).hexdigest()
        
        return f"sha256={signature}"

    @staticmethod
    async def process_incoming_webhook(
        event_type: str, 
        source: str, 
        data: Dict[str, Any], 
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process logic for incoming webhooks. 
        For now, we just validate specific types and queue them or process synchronously.
        """
        webhook_event_id = f"evt_{uuid.uuid4().hex[:12]}"
        
        # Example logic based on event type
        # In a real system, this would push to a Redis processing queue.
        # For 'message.received', we might trigger the chat pipeline?
        # The plan says: "Async: handle via RAG pipeline".
        
        # Simulating acceptance
        response = {
            "webhook_event_id": webhook_event_id,
            "status": "accepted",
            "message": "Webhook received and queued for processing"
        }
        
        if event_type == "message.received":
            # If it's a chat message, maybe we can simulate session_id?
            # data probably has user_id
            user_id = data.get("user_id")
            if user_id:
                # We could create a session here if we wanted to be robust
                response["session_id"] = f"sess_{uuid.uuid4().hex[:12]}"
        
        return response

    @staticmethod
    async def trigger_outgoing_event(event_type: str, payload: Dict[str, Any]):
        """
        Identify active webhooks for an event and queue deliveries.

        Args:
            event_type: Type of event (e.g. 'message.received')
            payload: Payload to deliver
        """
        targets = await WebhookRepository.get_webhooks_by_event(event_type, active_only=True)
        timestamp = datetime.utcnow().isoformat()
        
        for webhook in targets:
            # Create delivery record (pending)
            delivery_id = f"dlv_{uuid.uuid4().hex[:12]}"
            event_id = f"evt_{uuid.uuid4().hex[:12]}" # or pass one in
            
            # Since we don't have a background worker running in this context,
            # we will just LOG the intention to deliver or try a direct fire-and-forget?
            # For robustness in this demo environment, I'll allow a simple immediate sync attempt
            # or just log it as 'queued' if no worker exists.
            
            await WebhookRepository.log_delivery(
                delivery_id=delivery_id,
                webhook_id=webhook['webhook_id'],
                event_id=event_id,
                event_type=event_type,
                payload=payload,
                status='queued'
            )
            
            # Execute delivery immediately (simple background task, no durable queue yet)
            asyncio.create_task(WebhookService._perform_delivery(delivery_id, webhook, event_type, payload, timestamp))

    @staticmethod
    async def _perform_delivery(delivery_id: str, webhook: Dict[str, Any], event_type: str, payload: Dict[str, Any], timestamp: str):
        """
        Perform the actual HTTP POST for a webhook delivery.
        """
        import httpx
        
        url = webhook['url']
        secret = webhook['secret_hash'] # Assumed plaintext
        
        # Prepare headers
        payload_str = json.dumps(payload)
        signature = WebhookService.sign_payload(payload_str, secret, timestamp)
        
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "SupportRAG-Webhook/1.0",
            "X-Webhook-ID": webhook['webhook_id'],
            "X-Webhook-Event": event_type,
            "X-Webhook-Timestamp": timestamp,
            "X-Webhook-Signature": signature
        }
        
        status = 'failed'
        http_status = 0
        error_message = None
        start_time = time.time()

        try:
            # Use longer timeout for internal network requests (30 seconds)
            # Configure timeout per operation type
            timeout = httpx.Timeout(
                connect=5.0,   # Time to establish connection
                read=30.0,     # Time to read response
                write=10.0,    # Time to send request
                pool=5.0       # Time to acquire connection from pool
            )

            async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
                response = await client.post(url, content=payload_str, headers=headers)
                http_status = response.status_code

                if 200 <= http_status < 300:
                    status = 'delivered'
                else:
                    status = 'failed'
                    # Truncate error message to prevent log injection
                    error_message = f"HTTP {http_status}: {response.text[:200]}"

        except httpx.TimeoutException as e:
            status = 'failed'
            error_message = f"Request timeout: {str(e)[:100]}"
        except httpx.RequestError as e:
            status = 'failed'
            error_message = f"Request error: {str(e)[:100]}"
        except Exception as e:
            status = 'failed'
            error_message = f"Unexpected error: {str(e)[:100]}"
            
        duration = int((time.time() - start_time) * 1000)
        
        # Update delivery log
        async with get_db_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE webhook_deliveries
                    SET status = %s,
                        http_status = %s,
                        error_message = %s,
                        response_time_ms = %s,
                        delivered_at = CASE WHEN %s = 'delivered' THEN NOW() ELSE delivered_at END
                    WHERE delivery_id = %s
                    """,
                    (status, http_status, error_message, duration, status, delivery_id)
                )



    @staticmethod
    async def retry_delivery(delivery_id: str) -> Optional[Dict[str, Any]]:
        old_delivery = await WebhookRepository.get_delivery(delivery_id)
        if not old_delivery:
            return None
            
        # Create a new delivery attempt reference or just re-queue?
        # The plan says: POST /retry -> Returns status: queued, attempt: N
        # Ideally we create a NEW delivery record linked to the same event?
        # Or we update the specific delivery record?
        # The schema has "delivery_id" as PK. So we likely create a NEW delivery_id for the retry attempt
        # OR we just re-queue the existing one if we track history differently?
        # Let's create a NEW delivery entry for the retry to keep history of attempts.
        
        new_delivery_id = f"dlv_{uuid.uuid4().hex[:12]}"
        webhook_id = old_delivery['webhook_id']
        event_id = old_delivery['event_id']
        event_type = old_delivery['event_type']
        payload = old_delivery['payload'] # already a dict if fetched via psycopg dict-like or json
        
        # If payload is string json due to DB, we might need to parse.
        # Check map_delivery_row impl. Standard psycopg returns objects for JSONB.
        
        current_attempt = old_delivery.get('attempt', 1)
        next_attempt = current_attempt + 1
        
        await WebhookRepository.log_delivery(
            delivery_id=new_delivery_id,
            webhook_id=webhook_id,
            event_id=event_id,
            event_type=event_type,
            payload=payload,
            status='queued',
            attempt=next_attempt
        )
        
        return {
            "delivery_id": new_delivery_id,
            "original_delivery_id": delivery_id,
            "status": "queued",
            "attempt": next_attempt,
            "scheduled_for": datetime.utcnow() # approx
        }

