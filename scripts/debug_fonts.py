
import pdfplumber
import sys

def inspect_pdf_fonts(pdf_path):
    print(f"--- Inspecting fonts in {pdf_path} ---")
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            print(f"\nPage {i+1}:")
            words = page.extract_words(extra_attrs=["fontname", "size", "top"])
            
            # Group by line for readability
            current_top = -1
            current_line = []
            
            for word in words:
                if current_top != -1 and abs(word["top"] - current_top) > 3:
                    # Print previous line analysis
                    line_text = " ".join(w["text"] for w in current_line)
                    font_names = set(w["fontname"] for w in current_line)
                    is_bold_check = any("bold" in f.lower() or "black" in f.lower() or "semibold" in f.lower() for f in font_names)
                    
                    if len(line_text) > 5:
                        print(f"Text: '{line_text[:50]}...'")
                        print(f"  Fonts: {font_names}")
                        print(f"  Sizes: {set(w['size'] for w in current_line)}")
                        print("-" * 20)
                    
                    current_line = []
                
                current_line.append(word)
                current_top = word["top"]
            
            # Last line
            if current_line:
                line_text = " ".join(w["text"] for w in current_line)
                font_names = set(w["fontname"] for w in current_line)
                if "Если аккаунт можно" in line_text or "Профиль на" in line_text:
                    print(f"Text: '{line_text[:50]}...'")
                    print(f"  Fonts: {font_names}")

if __name__ == "__main__":
    sys.stdout = open("debug_log_utf8.txt", "w", encoding="utf-8")
    inspect_pdf_fonts("TS-Блокировка аккаунта.-060126-185504.pdf")
    sys.stdout.close()
