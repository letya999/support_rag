"""PDF document loader using pdfplumber."""

import logging
from typing import List

import pdfplumber

from .base_loader import BaseDocumentLoader
from .models import DocumentContent, DocumentFormat, Block, BlockType

logger = logging.getLogger(__name__)


class PDFLoader(BaseDocumentLoader):
    """Loader for PDF documents."""

    def load(self, file_path: str) -> DocumentContent:
        """Load PDF and extract blocks (tables, text, lists).

        Args:
            file_path: Path to PDF file

        Returns:
            DocumentContent with extracted blocks
        """
        path = self._validate_file(file_path, ".pdf", self.max_file_size_mb)

        logger.info(f"Loading PDF: {path.name}")

        doc = DocumentContent(
            file_name=path.name,
            file_type=DocumentFormat.PDF,
            blocks=[],
            raw_text=""
        )

        try:
            with pdfplumber.open(path) as pdf:
                raw_text_parts = []

                for page_idx, page in enumerate(pdf.pages):
                    logger.debug(f"Processing PDF page {page_idx + 1}/{len(pdf.pages)}")
                    
                    page_blocks = []

                    # 1. Extract tables
                    tables = page.find_tables()
                    table_rects = []
                    
                    if tables:
                        logger.info(f"Page {page_idx+1}: Found {len(tables)} tables")
                        for i, table in enumerate(tables):
                            table_data = table.extract()
                            if not table_data or len(table_data) < 2:
                                continue
                            
                            # Clean table data
                            def _clean_rows(data):
                                for row in data:
                                    yield [(cell or "").strip() for cell in row]
                            clean_table = list(_clean_rows(table_data))
                            
                            # Use top position for sorting
                            top_pos = table.bbox[1]
                            
                            page_blocks.append(Block(
                                type=BlockType.TABLE,
                                content=clean_table,
                                metadata={
                                    "page": page_idx + 1, 
                                    "table_index": i, 
                                    "top": top_pos
                                },
                                original_index=0 # Will update later
                            ))
                            
                            table_rects.append(table.bbox)

                    # 2. Extract words (filtering out tables)
                    if table_rects:
                        # Optimization: Sort tables by X coordinate used for early exit
                        table_rects.sort(key=lambda t: t[0])

                        def not_inside_tables(obj):
                            """Check if object is inside any identified table."""
                            # Use object center to check inclusion
                            x0 = obj.get("x0", 0)
                            top = obj.get("top", 0)
                            x1 = obj.get("x1", 0)
                            bottom = obj.get("bottom", 0)
                            
                            cx = (x0 + x1) / 2
                            cy = (top + bottom) / 2
                            
                            for (tx0, ttop, tx1, tbottom) in table_rects:
                                # Optimization: Early exit if table is to the right
                                if cx < tx0:
                                    break
                                if tx0 <= cx <= tx1 and ttop <= cy <= tbottom:
                                    return False
                            return True

                        page_for_text = page.filter(not_inside_tables)
                    else:
                        page_for_text = page
                    
                    words = page_for_text.extract_words(extra_attrs=["fontname", "size", "top"])
                    
                    # Analyze fonts on the filtered page
                    font_stats = {}
                    for w in words:
                        key = (w["fontname"], round(w["size"], 1))
                        font_stats[key] = font_stats.get(key, 0) + len(w["text"])
                    
                    body_font = None
                    if font_stats:
                        body_font = max(font_stats.items(), key=lambda x: x[1])[0]

                    # Group words into lines/blocks
                    current_line = []
                    current_line_headings = []
                    last_top = -1
                    
                    for word in words:
                        # Determine if heading
                        w_font = (word["fontname"], round(word["size"], 1))
                        is_heading = False
                        if body_font:
                             has_bold = "bold" in word["fontname"].lower()
                             is_larger = (w_font[1] - body_font[1]) > 0.1
                             is_heading = has_bold or is_larger

                        # Verify line break
                        if last_top != -1 and abs(word["top"] - last_top) > 3:
                            # Process completed line
                            if current_line:
                                line_text = " ".join(w["text"] for w in current_line)
                                is_heading_line = sum(current_line_headings) > len(current_line_headings) / 2
                                b_type = BlockType.HEADING if is_heading_line else BlockType.TEXT
                                
                                # Use top of the first word as block position
                                block_top = current_line[0]["top"]

                                # Merge with previous block if same type AND contiguous (small vertical gap)
                                # Only merge if we haven't inserted a table in between (checked via sorting later, 
                                # but here we are only processing text. Merging text blocks is fine).
                                # However, since we sort purely by 'top' later, merging here simplifies things.
                                
                                # Actually, don't merge across large gaps.
                                if page_blocks and page_blocks[-1].type == b_type and \
                                   page_blocks[-1].metadata.get("page") == page_idx + 1 and \
                                   page_blocks[-1].type != BlockType.TABLE:
                                    # Use list accumulation for O(1) append
                                    if isinstance(page_blocks[-1].content, list):
                                        page_blocks[-1].content.append(line_text)
                                    else:
                                        page_blocks[-1].content = [page_blocks[-1].content, line_text]
                                    # Don't update top, keep original top
                                else:
                                    page_blocks.append(Block(
                                        type=b_type,
                                        content=line_text,
                                        metadata={
                                            "page": page_idx + 1, 
                                            "is_header": is_heading_line,
                                            "top": block_top
                                        },
                                        original_index=0
                                    ))

                            current_line = [word]
                            current_line_headings = [is_heading]
                        else:
                            current_line.append(word)
                            current_line_headings.append(is_heading)
                        
                        last_top = word["top"]

                    # Handle last line
                    if current_line:
                        line_text = " ".join(w["text"] for w in current_line)
                        is_heading_line = sum(current_line_headings) > len(current_line_headings) / 2
                        b_type = BlockType.HEADING if is_heading_line else BlockType.TEXT
                        block_top = current_line[0]["top"]

                        if page_blocks and page_blocks[-1].type == b_type and \
                           page_blocks[-1].metadata.get("page") == page_idx + 1 and \
                           page_blocks[-1].type != BlockType.TABLE:
                            if isinstance(page_blocks[-1].content, list):
                                page_blocks[-1].content.append(line_text)
                            else:
                                page_blocks[-1].content = [page_blocks[-1].content, line_text]
                        else:
                            page_blocks.append(Block(
                                type=b_type,
                                content=line_text,
                                metadata={
                                    "page": page_idx + 1, 
                                    "is_header": is_heading_line,
                                    "top": block_top
                                },
                                original_index=0
                            ))

                    # Sort extracted blocks (tables + text) by vertical position
                    page_blocks.sort(key=lambda b: b.metadata.get("top", 0) or 0)
                    
                    # Add to document
                    for pb in page_blocks:
                        pb.original_index = len(doc.blocks)
                        
                        # Finalize content: join accumulated text lists
                        if isinstance(pb.content, list) and pb.type != BlockType.TABLE:
                            pb.content = " ".join(pb.content)
                        
                        doc.blocks.append(pb)
                        
                        # Update raw text
                        if isinstance(pb.content, str):
                            raw_text_parts.append(pb.content)
                        elif isinstance(pb.content, list):
                            # Stringify table for raw_text
                            table_str = "\n".join(" | ".join(cell) for cell in pb.content)
                            raw_text_parts.append(table_str)

                doc.raw_text = "\n".join(raw_text_parts)
                logger.info(f"Extracted {len(doc.blocks)} blocks from PDF (text + tables)")

        except Exception as e:
            logger.error(f"Error loading PDF: {e}")
            raise ValueError(f"Failed to parse PDF file: {str(e)}")

        return doc
