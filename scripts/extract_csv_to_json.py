import sys
import json
import logging
from pathlib import Path

# Add project root to sys.path to ensure 'app' imports work
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from app.services.document_loaders.csv_loader import CSVLoader
from app.services.document_loaders.models import DocumentStructure
from app.services.qa_extractors.table_extractor import TableQAExtractor
from app.services.metadata_generators.metadata_enricher import MetadataEnricher

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_csv_to_json(file_path: str):
    """
    Extracts Q&A pairs from a CSV file using app.services tools.
    """
    abs_path = Path(file_path).resolve()
    if not abs_path.exists():
        logger.error(f"File not found: {abs_path}")
        return

    logger.info(f"Loading file: {abs_path}")

    # 1. Load the CSV document
    loader = CSVLoader()
    try:
        doc = loader.load(str(abs_path))
    except Exception as e:
        logger.error(f"Failed to load CSV: {e}")
        return

    # 2. Define the structure for extraction
    # Assuming standard format: Column 0 = Question, Column 1 = Answer
    structure = DocumentStructure(
        detected_format="table",
        confidence=1.0,
        column_mapping={0: "question", 1: "answer"}
    )

    # 3. Extract Q&A pairs using TableQAExtractor
    extractor = TableQAExtractor()
    raw_pairs = extractor.extract(doc.blocks, structure)

    # 4. Enrich metadata and format result
    data = []
    for pair in raw_pairs:
        # Use MetadataEnricher to populate metadata like 'category', 'intent', etc.
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
    # Default to the file user mentioned if no argument provided
    target_file = "blokirovka_accounta.csv"
    
    if len(sys.argv) > 1:
        target_file = sys.argv[1]

    result = extract_csv_to_json(target_file)
    
    if result:
        # Output JSON to stdout so it can be redirected or piped
        print(json.dumps(result, ensure_ascii=False, indent=2))
