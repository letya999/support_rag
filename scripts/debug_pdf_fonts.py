"""Debug script to analyze font information in PDF."""

import sys
from pathlib import Path
import pdfplumber

# Add project root to sys.path
project_root = str(Path(__file__).parent.parent)
sys.path.append(project_root)

def debug_pdf_fonts(pdf_path: str):
    print(f"=== Analyzing PDF Fonts: {pdf_path} ===\n")
    
    with pdfplumber.open(pdf_path) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            print(f"\n--- Page {page_idx + 1} ---")
            
            # Extract words with font info
            words = page.extract_words(extra_attrs=["fontname", "size"])
            
            if not words:
                print("No words found")
                continue
            
            # Group by font
            font_groups = {}
            for w in words:
                key = (w["fontname"], round(w["size"], 1))
                if key not in font_groups:
                    font_groups[key] = []
                font_groups[key].append(w["text"])
            
            print(f"\nFound {len(font_groups)} different font styles:")
            for (font_name, size), texts in sorted(font_groups.items(), key=lambda x: -x[0][1]):
                sample = " ".join(texts[:10])
                if len(sample) > 100:
                    sample = sample[:100] + "..."
                print(f"\n  Font: {font_name}")
                print(f"  Size: {size}")
                print(f"  Word count: {len(texts)}")
                print(f"  Sample: {sample}")

if __name__ == "__main__":
    file_to_check = "TS-Блокировка аккаунта.-060126-185504.pdf"
    
    if len(sys.argv) > 1:
        file_to_check = sys.argv[1]
        
    debug_pdf_fonts(file_to_check)
