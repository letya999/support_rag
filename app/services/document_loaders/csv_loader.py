"""CSV document loader with auto-detection of delimiter and encoding."""

import logging
from io import StringIO
from pathlib import Path

import chardet
import pandas as pd

from .base_loader import BaseDocumentLoader
from .models import DocumentContent, DocumentFormat, Block, BlockType

logger = logging.getLogger(__name__)


class CSVLoader(BaseDocumentLoader):
    """Loader for CSV documents with smart delimiter and encoding detection."""

    def load(self, file_path: str) -> DocumentContent:
        """Load CSV with auto-detection of delimiter and encoding.

        Args:
            file_path: Path to CSV file

        Returns:
            DocumentContent with extracted blocks
        """
        path = self._validate_file(file_path, ".csv", self.max_file_size_mb)

        logger.info(f"Loading CSV: {path.name}")

        doc = DocumentContent(
            file_name=path.name,
            file_type=DocumentFormat.CSV,
            blocks=[],
            raw_text=""
        )

        try:
            # Detect encoding
            with open(path, "rb") as f:
                raw_data = f.read()
            encoding = chardet.detect(raw_data)["encoding"] or "utf-8"
            logger.debug(f"Detected encoding: {encoding}")

            # Read CSV content
            with open(path, "r", encoding=encoding) as f:
                content = f.read()

            # Detect delimiter
            delimiter = self._detect_delimiter(content)
            logger.debug(f"Detected delimiter: {repr(delimiter)}")

            # Parse CSV
            df = pd.read_csv(StringIO(content), delimiter=delimiter, dtype=str)
            df = df.fillna("")  # Replace NaN with empty strings

            logger.info(f"Parsed CSV: {len(df)} rows, {len(df.columns)} columns")

            # Create table block
            table_data = [df.columns.tolist()] + df.values.tolist()

            block = Block(
                type=BlockType.TABLE,
                content=table_data,
                metadata={"type": "csv_table", "rows": len(df), "columns": len(df.columns)},
                original_index=0
            )
            doc.blocks.append(block)

            # Also create raw text representation
            raw_text_parts = []
            for idx, row in df.iterrows():
                row_text = " | ".join(f"{col}: {val}" for col, val in row.items())
                raw_text_parts.append(row_text)

            doc.raw_text = "\n".join(raw_text_parts)

            logger.info(f"Extracted 1 table block from CSV ({len(doc.raw_text)} chars)")

        except Exception as e:
            logger.error(f"Error loading CSV: {e}")
            raise ValueError(f"Failed to parse CSV file: {str(e)}")

        return doc

    @staticmethod
    def _detect_delimiter(content: str) -> str:
        """Auto-detect CSV delimiter using csv.Sniffer."""
        try:
            import csv
            # Check valid delimiters
            delimiters = [",", ";", "\t", "|"]
            # Sample first lines (enough to capture multiple rows, but limit size)
            sample = content[:min(len(content), 4096)]
            dialect = csv.Sniffer().sniff(sample, delimiters=delimiters)
            return dialect.delimiter
        except Exception as e:
            logger.debug(f"Sniffer failed: {e}. Defaulting to comma.")
            return ","
