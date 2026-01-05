"""Q&A extractor for table-based documents."""

import logging
from typing import List

from app.services.document_loaders import Block, BlockType, DocumentStructure, RawQAPair

from .base_extractor import BaseQAExtractor

logger = logging.getLogger(__name__)


class TableQAExtractor(BaseQAExtractor):
    """Extracts Q&A pairs from table format documents."""

    def extract(self, blocks: List[Block], structure: DocumentStructure) -> List[RawQAPair]:
        """Extract Q&A pairs from table blocks.

        Args:
            blocks: List of document blocks
            structure: Document structure with column mapping

        Returns:
            List of extracted Q&A pairs
        """
        pairs = []
        table_blocks = [b for b in blocks if b.type == BlockType.TABLE]

        if not table_blocks:
            logger.warning("No table blocks found")
            return pairs

        column_mapping = structure.column_mapping

        for table_block in table_blocks:
            if not isinstance(table_block.content, list):
                continue

            table = table_block.content

            if len(table) < 2:
                continue

            # Skip header row
            for row_idx, row in enumerate(table[1:], start=1):
                try:
                    # Extract columns based on mapping
                    question = None
                    answer = None
                    metadata_text = None

                    for col_idx, col_role in column_mapping.items():
                        if col_idx >= len(row):
                            continue

                        cell_content = str(row[col_idx] or "").strip()

                        if col_role == "question":
                            question = cell_content
                        elif col_role == "answer":
                            answer = cell_content
                        elif col_role == "metadata":
                            metadata_text = cell_content

                    if not question or not answer:
                        continue

                    if not self._is_valid_qa_pair(question, answer):
                        logger.debug(
                            f"Skipping invalid pair from table row {row_idx}: "
                            f"q_len={len(question)}, a_len={len(answer)}"
                        )
                        continue

                    question = self._clean_text(question)
                    answer = self._clean_text(answer)

                    pair = RawQAPair(
                        question=question,
                        answer=answer,
                        source_block_ids=[table_block.original_index],
                        extraction_method="table_row_extraction",
                        confidence=0.85,
                        metadata={"source_row": row_idx} if metadata_text else {},
                    )
                    pairs.append(pair)

                except Exception as e:
                    logger.debug(f"Error extracting from table row {row_idx}: {e}")
                    continue

        logger.info(f"Extracted {len(pairs)} Q&A pairs from {len(table_blocks)} table(s)")
        return pairs
