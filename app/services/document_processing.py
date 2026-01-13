from pathlib import Path
from typing import List, Dict, Any, Union
from app.logging_config import logger

from app.services.document_loaders.loader_factory import LoaderFactory
from app.services.document_loaders.models import DocumentFormat
from app.services.document_loaders import ProcessedQAPair
from app.services.qa_extractors.table_extractor import TableQAExtractor
from app.services.qa_extractors.section_extractor import SectionQAExtractor
from app.services.qa_extractors.faq_extractor import FAQExtractor
from app.services.qa_extractors.json_extractor import JSONQAExtractor
from app.services.structure_detectors.document_structure_analyzer import DocumentStructureAnalyzer, DocumentStructure
from app.services.metadata_generators.metadata_enricher import MetadataEnricher

class DocumentProcessingService:
    """
    Orchestrates the conversion of raw files into structured Q&A pairs (ProcessedQAPair).
    Uses Loader -> Analyzer -> Extractor -> Checker/Enricher pipeline.
    """

    @staticmethod
    async def process_file(file_path: str, original_filename: str = None) -> List[ProcessedQAPair]:
        """
        Process a file path into Q&A pairs using the full processing pipeline.

        Args:
            file_path: Path to the local file
            original_filename: Original filename (optional, for metadata)

        Returns:
            List of ProcessedQAPair objects
        """
        path_obj = Path(file_path)
        display_name = original_filename if original_filename else path_obj.name
        logger.info("Processing file", extra={"filename": display_name})

        # 1. Load Document Content (Blocks)
        loader = LoaderFactory.get_loader(file_path)
        doc = loader.load(file_path)
        
        if not doc.blocks:
            # Special case: CSVLoader makes one big block, but let's check.
            # If doc.blocks is empty but raw_text is present, might be raw text.
            # But loaders should produce blocks.
            logger.warning("No blocks returned from loader.")
            return []

        # 2. Analyze Structure & Choose Extractor
        # If it's CSV, we know it's a Table.
        # If DOCX/PDF, we analyzer.
        # 2. Analyze Structure & Choose Extractor
        analyzer = DocumentStructureAnalyzer()
        structure = analyzer.analyze(doc)
        
        # Special handling for CSV: If analyzer failed to detect table (e.g. strict headers), force it with default mapping
        if doc.file_type == DocumentFormat.CSV and structure.detected_format != "table":
             logger.warning("CSV analyzed but table structure not detected/confident. Forcing table extraction with default mapping.")
             
             # Fallback mapping: Col 0 -> Question, Col 1 -> Answer
             mapping = {}
             if doc.blocks and doc.blocks[0].type == BlockType.TABLE:
                 header = doc.blocks[0].content[0]
                 if len(header) >= 2:
                     mapping = {0: "question", 1: "answer"}
                     
             structure = DocumentStructure(
                 detected_format="table",
                 confidence=0.8, 
                 column_mapping=mapping,
                 notes=["Forced CSV table structure with default mapping"]
             )
             
        logger.info("Structure detection finished", extra={"format": structure.detected_format, "filename": display_name})
        
        extractor = None
        if doc.file_type == DocumentFormat.JSON:
            extractor = JSONQAExtractor()
        elif structure.detected_format == "table":
            extractor = TableQAExtractor()
        elif structure.detected_format == "sections":
            extractor = SectionQAExtractor()
        elif structure.detected_format == "faq":
            extractor = FAQExtractor()
        elif structure.detected_format == "list":
                # Import locally to avoid circulars if any
                try:
                    from app.services.qa_extractors.list_extractor import ListQAExtractor
                    extractor = ListQAExtractor()
                except ImportError:
                    extractor = FAQExtractor()
        else:
                # Fallback
                extractor = SectionQAExtractor()

        # 3. Extract Raw Pairs
        raw_pairs = extractor.extract(doc.blocks, structure)
        
        # 4. Enrich Metadata -> ProcessedQAPair
        processed_pairs = []
        for pair in raw_pairs:
            # Enrich returns dict
            enriched_meta = MetadataEnricher.enrich(
                pair,
                source_document=display_name,
                existing_metadata=pair.metadata
            )
            
            processed_pairs.append(ProcessedQAPair(
                question=pair.question,
                answer=pair.answer,
                metadata=enriched_meta
            ))
            
        logger.info("File processing complete", extra={"pairs_extracted": len(processed_pairs), "filename": display_name})
        return processed_pairs
