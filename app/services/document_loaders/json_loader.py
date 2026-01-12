import json
import logging
from typing import List

from .base_loader import BaseDocumentLoader
from .models import DocumentContent, DocumentFormat, Block, BlockType

logger = logging.getLogger(__name__)


class JSONLoader(BaseDocumentLoader):
    """Loader for JSON files."""

    def load(self, file_path: str) -> DocumentContent:
        """Load JSON file and return content.
        
        For JSON files, we load the entire content as a single TEXT block
        containing the raw JSON string. The extractor will be responsible
        for parsing the JSON structure.
        """
        path = self._validate_file(file_path, ".json", self.max_file_size_mb)
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
                
            # Quick validation that it is valid JSON
            try:
                data = json.loads(content)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON content: {e}")

            # Create a single block with the raw JSON
            # We use TEXT type because it's a string representation
            blocks = [
                Block(
                    type=BlockType.TEXT,
                    content=content,
                    metadata={"source": "json_loader"},
                    original_index=0
                )
            ]
            
            return DocumentContent(
                file_name=path.name,
                file_type=DocumentFormat.JSON,
                blocks=blocks,
                raw_text=content
            )
            
        except Exception as e:
            logger.error(f"Error loading JSON file {file_path}: {e}")
            raise ValueError(f"Failed to load JSON file: {e}")
