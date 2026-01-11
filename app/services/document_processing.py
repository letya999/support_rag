from pathlib import Path
from typing import List, Dict, Any, Union
import logging

from app.services.document_loaders.loader_factory import LoaderFactory
from app.services.document_loaders.models import DocumentFormat
from app.services.document_loaders import ProcessedQAPair
from app.services.qa_extractors.table_extractor import TableQAExtractor
from app.services.qa_extractors.section_extractor import SectionQAExtractor
from app.services.qa_extractors.faq_extractor import FAQExtractor
from app.services.structure_detectors.document_structure_analyzer import DocumentStructureAnalyzer, DocumentStructure
from app.services.metadata_generators.metadata_enricher import MetadataEnricher

logger = logging.getLogger(__name__)

class DocumentProcessingService:
    """
    Orchestrates the conversion of raw files into structured Q&A pairs (ProcessedQAPair).
    Uses Loader -> Analyzer -> Extractor -> Checker/Enricher pipeline.
    """

    @staticmethod
    async def process_file(file_path: str) -> List[ProcessedQAPair]:
        """
        Process a file path into Q&A pairs.
        """
        path_obj = Path(file_path)
        logger.info(f"Processing file: {path_obj.name}")

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
        extractor = None
        
        if doc.file_type == DocumentFormat.CSV:
            # Explicitly use Table extractor for CSV if it produced a Table Block
            # CSVLoader produces BlockType.TABLE
            extractor = TableQAExtractor()
            # Structure required for generic extractor interface usually?
            # Creating dummy structure
            structure = DocumentStructure(detected_format="table", confidence=1.0)
            
        else:
            # Run Analyzer for unstructured
            analyzer = DocumentStructureAnalyzer()
            structure = analyzer.analyze(doc)
            logger.info(f"Detected structure: {structure.detected_format}")
            
            if structure.detected_format == "table":
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
                source_document=path_obj.name,
                existing_metadata=pair.metadata
            )
            
            processed_pairs.append(ProcessedQAPair(
                question=pair.question,
                answer=pair.answer,
                metadata=enriched_meta
            ))
            
        logger.info(f"Extracted {len(processed_pairs)} pairs from {path_obj.name}")
        return processed_pairs
