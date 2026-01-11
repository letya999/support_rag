
import asyncio
import logging
from app.services.document_loaders.pdf_loader import PDFLoader
from app.services.structure_detectors.document_structure_analyzer import DocumentStructureAnalyzer
from app.services.document_loaders.models import BlockType

# Configure logging
logging.basicConfig(level=logging.INFO)

async def check_pdf(file_path):
    print(f"--- Checking {file_path} ---")
    loader = PDFLoader()
    try:
        doc = loader.load(file_path)
    except Exception as e:
        print(f"Error loading PDF: {e}")
        return

    print(f"Total Blocks: {len(doc.blocks)}")
    
    unique_types = set(b.type for b in doc.blocks)
    print(f"Block Types Found: {unique_types}")

    for i, b in enumerate(doc.blocks):
        print(f"Block {i}: Type={b.type}, Content={b.content[:50]}...")
        if b.type == BlockType.HEADING:
             print(f"   -> HEADING CONFIRMED: {b.content}")

    analyzer = DocumentStructureAnalyzer()
    structure = analyzer.analyze(doc)
    print(f"Detected Structure: {structure.detected_format} (Confidence: {structure.confidence})")
    print(f"Notes: {structure.notes}")

    if structure.detected_format == "table":
        from app.services.qa_extractors.table_extractor import TableQAExtractor
        extractor = TableQAExtractor()
    else:
        from app.services.qa_extractors.section_extractor import SectionQAExtractor
        extractor = SectionQAExtractor()

    print(f"Using Extractor: {type(extractor).__name__}")
    try:
        pairs = extractor.extract(doc.blocks, structure)
        print(f"Extracted Pairs: {len(pairs)}")
        for i, p in enumerate(pairs):
            print(f"Pair {i}: Q='{p.question}' A='{p.answer}'")
    except Exception as e:
        print(f"Extraction Error: {e}")

if __name__ == "__main__":
    file_path = "c:\\Users\\User\\a_projects\\support_rag\\TS-Блокировка аккаунта.-060126-185504.pdf"
    asyncio.run(check_pdf(file_path))
