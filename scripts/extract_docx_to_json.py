import sys
import json
import logging
from pathlib import Path

# Add project root to sys.path
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from app.services.document_loaders.docx_loader import DOCXLoader
from app.services.structure_detectors.document_structure_analyzer import DocumentStructureAnalyzer
from app.services.qa_extractors.table_extractor import TableQAExtractor
from app.services.qa_extractors.section_extractor import SectionQAExtractor
from app.services.qa_extractors.faq_extractor import FAQExtractor
from app.services.qa_extractors.list_extractor import ListQAExtractor # Assuming this exists or I'll implement a fallback
from app.services.metadata_generators.metadata_enricher import MetadataEnricher

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_docx_to_json(file_path: str):
    """
    Extracts Q&A pairs from a DOCX file with auto-detection of structure.
    """
    abs_path = Path(file_path).resolve()
    if not abs_path.exists():
        logger.error(f"File not found: {abs_path}")
        return

    logger.info(f"Loading file: {abs_path}")

    # 1. Load the DOCX document
    loader = DOCXLoader()
    try:
        doc = loader.load(str(abs_path))
    except Exception as e:
        logger.error(f"Failed to load DOCX: {e}")
        return
    
    if not doc.blocks:
        logger.warning("No blocks extracted from DOCX.")
        return []

    # 2. Analyze structure
    analyzer = DocumentStructureAnalyzer()
    structure = analyzer.analyze(doc)
    
    logger.info(f"Detected structure: {structure.detected_format}")

    # 3. Select Extractor
    if structure.detected_format == "table":
        logger.info("Using TableQAExtractor")
        extractor = TableQAExtractor()
    elif structure.detected_format == "sections":
        logger.info("Using SectionQAExtractor")
        extractor = SectionQAExtractor()
    elif structure.detected_format == "faq":
        logger.info("Using FAQExtractor")
        extractor = FAQExtractor()
    elif structure.detected_format == "list":
        # Check if ListQAExtractor exists, otherwise fallback to FAQ or Section
        try:
             from app.services.qa_extractors.list_extractor import ListQAExtractor
             logger.info("Using ListQAExtractor")
             extractor = ListQAExtractor()
        except ImportError:
             logger.warning("ListQAExtractor not found, falling back to FAQExtractor")
             extractor = FAQExtractor()
    else:
        logger.warning(f"Unknown format '{structure.detected_format}', defaulting to SectionQAExtractor/Heuristics")
        # If unknown, try SectionQAExtractor as it is robust for heading+text, or FAQ as fallback
        extractor = SectionQAExtractor()

    # 4. Extract Pairs
    raw_pairs = extractor.extract(doc.blocks, structure)
    
    # Fallback: if no pairs found with chosen extractor, try simple heuristic (FAQExtractor fallback)
    if not raw_pairs and structure.detected_format != "faq":
         logger.info("No pairs found with primary extractor, trying fallback FAQ extraction...")
         fallback_extractor = FAQExtractor()
         raw_pairs = fallback_extractor.extract(doc.blocks, structure)

    # 5. Enrich metadata
    data = []
    for pair in raw_pairs:
        enriched_metadata = MetadataEnricher.enrich(
            pair, 
            source_document=abs_path.name,
            existing_metadata=pair.metadata
        )
        
        data.append({
            "question": pair.question,
            "answer": pair.answer,
            "metadata": enriched_metadata
        })

    logger.info(f"Successfully extracted {len(data)} pairs.")
    return data

if __name__ == "__main__":
    target_file = "blokirovka_accounta.docx"
    
    if len(sys.argv) > 1:
        target_file = sys.argv[1]

    result = extract_docx_to_json(target_file)
    
    if result:
         print(json.dumps(result, ensure_ascii=False, indent=2))
