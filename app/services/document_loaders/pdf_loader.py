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

                    # 1. Skip table extraction - pdfplumber often misidentifies formatted text as tables
                    # We'll rely on text extraction with font metadata instead
                    
                    # 2. Extract words with formatting metadata
                    words = page.extract_words(extra_attrs=["fontname", "size"])
                    if not words:
                        continue

                    # Analyze fonts to find "Body" font (most common)
                    font_stats = {}
                    for w in words:
                        key = (w["fontname"], round(w["size"], 1))
                        font_stats[key] = font_stats.get(key, 0) + len(w["text"])
                    
                    if not font_stats:
                        body_font = None
                        logger.warning("No font stats collected.")
                    else:
                        # Body font is the one with the most characters
                        body_font = max(font_stats.items(), key=lambda x: x[1])[0]
                        logger.warning(f"Detected body font: {body_font} (stats: {len(font_stats)} variants)")
                        print(f"DEBUG: Body Font: {body_font}")

                    # Group words into lines/blocks based on vertical position and formatting
                    current_line = []
                    current_line_headings = []  # Track which words are headings
                    last_top = -1
                    
                    for word in words:
                        # Determine if this word is a heading/bold text
                        w_font = (word["fontname"], round(word["size"], 1))
                        
                        if body_font:
                            has_bold_in_name = "bold" in word["fontname"].lower()
                            size_diff = w_font[1] - body_font[1]
                            is_larger = size_diff > 0.1
                            is_heading = has_bold_in_name or is_larger
                        else:
                            is_heading = False

                        # If vertical position changed significantly, it's a new line
                        if last_top != -1 and abs(word["top"] - last_top) > 3:
                            # Process the completed line
                            if current_line:
                                line_text = " ".join(w["text"] for w in current_line)
                                
                                # Determine block type by majority vote
                                heading_count = sum(current_line_headings)
                                is_heading_line = heading_count > len(current_line_headings) / 2
                                
                                b_type = BlockType.HEADING if is_heading_line else BlockType.TEXT
                                
                                # Try to merge with previous block if same type
                                if doc.blocks and doc.blocks[-1].type == b_type and doc.blocks[-1].metadata.get("page") == page_idx + 1:
                                    doc.blocks[-1].content += " " + line_text
                                else:
                                    doc.blocks.append(Block(
                                        type=b_type,
                                        content=line_text,
                                        metadata={"page": page_idx + 1, "is_header": is_heading_line},
                                        original_index=len(doc.blocks)
                                    ))
                                
                                raw_text_parts.append(line_text)
                            
                            # Start new line
                            current_line = [word]
                            current_line_headings = [is_heading]
                        else:
                            current_line.append(word)
                            current_line_headings.append(is_heading)
                        
                        last_top = word["top"]

                    # Handle last line
                    if current_line:
                        line_text = " ".join(w["text"] for w in current_line)
                        heading_count = sum(current_line_headings)
                        is_heading_line = heading_count > len(current_line_headings) / 2
                        
                        b_type = BlockType.HEADING if is_heading_line else BlockType.TEXT
                        
                        # Try to merge with previous block if same type
                        if doc.blocks and doc.blocks[-1].type == b_type and doc.blocks[-1].metadata.get("page") == page_idx + 1:
                            doc.blocks[-1].content += " " + line_text
                        else:
                            doc.blocks.append(Block(
                                type=b_type,
                                content=line_text,
                                metadata={"page": page_idx + 1, "is_header": is_heading_line},
                                original_index=len(doc.blocks)
                            ))
                        
                        raw_text_parts.append(line_text)

                doc.raw_text = "\n".join(raw_text_parts)
                logger.info(f"Extracted {len(doc.blocks)} blocks from PDF (with formatting detection)")

        except Exception as e:
            logger.error(f"Error loading PDF: {e}")
            raise ValueError(f"Failed to parse PDF file: {str(e)}")

        return doc
