import json
import logging
from typing import List, Any, Dict

from app.services.document_loaders import Block, BlockType, DocumentStructure, RawQAPair
from .base_extractor import BaseQAExtractor

logger = logging.getLogger(__name__)


class JSONQAExtractor(BaseQAExtractor):
    """Extracts Q&A pairs from JSON format."""

    def extract(self, blocks: List[Block], structure: DocumentStructure) -> List[RawQAPair]:
        """Extract Q&A pairs from parsed JSON.
        
        Expects a single TEXT block containing the raw JSON string.
        """
        pairs = []
        
        for block in blocks:
            # We only expect TEXT blocks for JSON from our JSONLoader
            if block.type != BlockType.TEXT:
                continue
                
            try:
                content = block.content
                if not isinstance(content, str):
                    continue
                
                # Attempt to parse
                try:
                    data = json.loads(content)
                except json.JSONDecodeError:
                    # If this block isn't JSON, skip it
                    continue
                    
                if not isinstance(data, list):
                    logger.warning("JSON content is not a list. Expected list of Q&A objects.")
                    continue
                    
                for i, item in enumerate(data):
                    if not isinstance(item, dict):
                        continue
                        
                    question = item.get("question")
                    answer = item.get("answer")
                    
                    if not question or not answer:
                        continue
                        
                    # Metadata handling
                    metadata = item.get("metadata", {})
                    if not isinstance(metadata, dict):
                        metadata = {}

                    # Allow extending metadata with other fields if necessary
                    # For now, just pass it through
                        
                    pair = RawQAPair(
                        question=str(question),
                        answer=str(answer),
                        source_block_ids=[block.original_index],
                        extraction_method="json_direct",
                        confidence=1.0, 
                        metadata=metadata
                    )
                    pairs.append(pair)
                    
            except Exception as e:
                logger.error(f"Error extracting from JSON block: {e}")
                
        logger.info(f"Extracted {len(pairs)} Q&A pairs from JSON")
        return pairs
