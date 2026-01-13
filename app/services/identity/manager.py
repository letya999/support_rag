import uuid
import json
from typing import Dict, Any, Optional, Union
from app.storage.repositories.identity_repository import IdentityRepository
from app.logging_config import logger

class IdentityManager:
    """
    Business logic for User Identification.
    Orchestrates the resolution of external IDs to internal User IDs using IdentityRepository.
    Provides universal methods for different input channels (Web, Telegram, API).
    """

    @staticmethod
    async def resolve_identity(
        channel: str, 
        identifier: Optional[str], 
        metadata_payload: Any = None
    ) -> str:
        """
        Universal entry point for resolving identity from any source.
        
        Args:
            channel: The source type (e.g., 'telegram', 'device_fingerprint').
            identifier: The external ID value (e.g., TG ID, Hash).
            metadata_payload: Raw metadata. Can be a Dict or a JSON string (common in headers).
            
        Returns:
            str: The resolved internal user_id (UUID) or 'anonymous'.
        """
        if not identifier:
            return "anonymous"

        # Normalize metadata
        final_metadata = {}
        if isinstance(metadata_payload, dict):
            final_metadata = metadata_payload
        elif isinstance(metadata_payload, str) and metadata_payload.strip():
            try:
                # Attempt to parse JSON string (e.g. from HTTP headers)
                final_metadata = json.loads(metadata_payload)
            except (json.JSONDecodeError, TypeError):
                # Fallback: store raw string if needed, or just ignore malformed JSON
                final_metadata = {"raw_metadata_error": "malformed_json", "raw_content": metadata_payload}

        return await IdentityManager._get_or_create_user_internal(channel, identifier, final_metadata)

    @staticmethod
    async def _get_or_create_user_internal(
        identity_type: str, 
        identity_value: str, 
        metadata: Dict[str, Any]
    ) -> str:
        """
        Internal logic to lookup or create the user in DB based on identity.

        Args:
            identity_type: Type of identity (e.g. 'telegram')
            identity_value: External ID value
            metadata: Metadata to store/merge

        Returns:
            str: Resolved internal user_id
        """
        # 1. Try to find existing
        existing = await IdentityRepository.get_identity(identity_type, identity_value)

        if existing:
            user_id = existing['user_id']
            
            # Merge logic
            current_metadata = existing['metadata'] or {}
            current_metadata.update(metadata)
            
            # Persist updates
            await IdentityRepository.update_identity_metadata(identity_type, identity_value, current_metadata)
            return user_id
        
        # 2. Create new user if not found
        new_user_id = str(uuid.uuid4())
        logger.info("Creating new user identity", extra={"identity_type": identity_type, "user_id": new_user_id})
        
        # Best guess for name
        guessed_name = metadata.get('first_name') or metadata.get('name') or metadata.get('username')
        
        await IdentityRepository.create_new_user_with_identity(
            user_id=new_user_id,
            name=guessed_name,
            identity_type=identity_type,
            identity_value=identity_value,
            metadata=metadata
        )
        
        return new_user_id
