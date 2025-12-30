import pypdf

filepath = "tax db/main taxlaw.pdf"
reader = pypdf.PdfReader(filepath)
full_text = ""

# Read first 50 pages (approx 50k - 100k chars)
for i, page in enumerate(reader.pages):
    if i > 50: break
    extracted = page.extract_text()
    if extracted:
        full_text += extracted + "\n"

with open("pdf_head.txt", "w", encoding="utf-8") as f:
    f.write(full_text)
    print(f"Dumped {len(full_text)} chars to pdf_head.txt")
