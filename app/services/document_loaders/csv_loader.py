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
        """Auto-detect CSV delimiter.

        Args:
            content: CSV file content

        Returns:
            Detected delimiter character
        """
        # Common delimiters to check
        delimiters = [",", ";", "\t", "|", " "]
        lines = content.split("\n")[:10]  # Check first 10 lines

        delimiter_counts = {d: [] for d in delimiters}

        for line in lines:
            if not line.strip():
                continue
            for d in delimiters:
                delimiter_counts[d].append(line.count(d))

        # Find delimiter with most consistent count
        best_delimiter = ","
        best_consistency = -1

        for d in delimiters:
            if not delimiter_counts[d]:
                continue

            counts = delimiter_counts[d]
            avg_count = sum(counts) / len(counts)

            if avg_count < 1:
                continue

            # Calculate consistency (lower variance is better)
            variance = sum((c - avg_count) ** 2 for c in counts) / len(counts)
            consistency = avg_count / (1 + variance)

            if consistency > best_consistency:
                best_consistency = consistency
                best_delimiter = d

        return best_delimiter
