import pypdf
import os

filepath = "tax db/main taxlaw.pdf"

print(f"Reading {filepath}...")
reader = pypdf.PdfReader(filepath)
full_text = ""

for i, page in enumerate(reader.pages):
    text = page.extract_text()
    if text:
        full_text += text + "\n"

with open("pdf_law_headers.txt", "w", encoding="utf-8") as f:
    f.write(f"Total characters extracted: {len(full_text)}\n")

    # Search for all "Article 1 (Purpose)"
    # Usually "제1조(목적)"
    key = "제1조(목적)"
    
    start_idx = 0
    count = 0
    
    while True:
        idx = full_text.find(key, start_idx)
        if idx == -1: break
        
        # Capture 200 chars BEFORE and 100 AFTER
        pre_context = full_text[max(0, idx-200):idx].replace("\n", " ")
        post_context = full_text[idx:idx+100].replace("\n", " ")
        
        f.write(f"\n[Found '제1조(목적)' at {idx}]\n")
        f.write(f"PRE: ...{pre_context}\n")
        f.write(f"POST: {post_context}...\n")
        
        start_idx = idx + 1
        count += 1
        if count > 50: break # Safety limit

    print("Scan complete.")
