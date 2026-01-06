"""Debug script to see what blocks are extracted from PDF."""

import sys
from pathlib import Path

# Add project root to sys.path
project_root = str(Path(__file__).parent.parent)
sys.path.append(project_root)

from app.services.document_loaders import LoaderFactory

def debug_pdf_blocks(pdf_path: str):
    print(f"=== Analyzing PDF: {pdf_path} ===\n")
    
    # Load document
    loader = LoaderFactory.get_loader(pdf_path)
    document = loader.load(pdf_path)
    
    print(f"Total blocks: {len(document.blocks)}\n")
    
    # Show all blocks with details
    for i, block in enumerate(document.blocks):
        print(f"Block {i}:")
        print(f"  Type: {block.type.value}")
        print(f"  Metadata: {block.metadata}")
        
        if block.type.value == "table":
            print(f"  Content (table): {len(block.content)} rows")
            for row_idx, row in enumerate(block.content[:3]):  # First 3 rows
                print(f"    Row {row_idx}: {row}")
        else:
            content_str = str(block.content)
            if len(content_str) > 200:
                print(f"  Content: {content_str[:200]}...")
            else:
                print(f"  Content: {content_str}")
        print()

if __name__ == "__main__":
    file_to_check = "TS-Блокировка аккаунта.-060126-185504.pdf"
    
    if len(sys.argv) > 1:
        file_to_check = sys.argv[1]
        
    debug_pdf_blocks(file_to_check)
