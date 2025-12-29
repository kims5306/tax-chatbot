import os
import requests
import xmltodict
import json
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

LAW_API_USER_ID = os.getenv("LAW_API_USER_ID")
LAW_API_KEY = os.getenv("LAW_API_KEY")

DATA_DIR = "data/precedents"

def fetch_list(target, query, page=1):
    """Generic fetch list function"""
    base_url = "https://www.law.go.kr/DRF/lawSearch.do"
    params = {
        "OC": LAW_API_USER_ID or LAW_API_KEY, # Use whichever is set
        "target": target,
        "type": "XML",
        "query": query,
        "page": page
    }
    
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = xmltodict.parse(response.content)
        
        # Root key depends on target
        # prec -> PrecSearch
        # expc -> ExpcSearch
        # adjud -> AdjudSearch
        # hunjae -> HunjaeSearch
        root_key = f"{target.capitalize()}Search"
        if target == 'hunjae': root_key = "HunjaeSearch"
        
        result = data.get(root_key, {})
        if not result:
            return []
            
        items = result.get(target, [])
        if isinstance(items, dict):
            items = [items]
            
        print(f"[{target}] '{query}': Found {len(items)} items.")
        return items
    except Exception as e:
        print(f"Error fetching list for {target}: {e}")
        try:
            print(f"Server Response (First 500 chars): {response.content.decode('utf-8')[:500]}")
        except:
            pass
        return []

def fetch_detail(target, doc_id):
    """Generic fetch detail function"""
    base_url = "https://www.law.go.kr/DRF/lawService.do"
    params = {
        "OC": LAW_API_USER_ID or LAW_API_KEY,
        "target": target,
        "type": "XML",
        "ID": doc_id
    }
    
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = xmltodict.parse(response.content)
        return data
    except Exception as e:
        print(f"Error fetching detail {doc_id}: {e}")
        return None

def save_document(target, data):
    """Saves document with target prefix"""
    if not data: return
    
    # Root key is one of XxxService
    keys = list(data.keys())
    if not keys: return
    root_key = keys[0]
    content = data[root_key]
    
    # Try different ID keys
    doc_id = content.get('판례일련번호') or content.get('행정심판일련번호') or content.get('법령해석일련번호') or content.get('헌재결정일련번호') or "unknown"
    
    # Try different Title keys
    title = content.get('사건명') or content.get('안건명') or content.get('심판사건명') or "unknown_title"
    # Sanitize title
    title = str(title).replace("/", "_").replace("\\", "_")
    
    filename = f"{target}_{doc_id}_{title}.json"
    # Remove invalid chars
    filename = "".join(x for x in filename if x.isalnum() or x in "._- ")
    filepath = os.path.join(DATA_DIR, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print(f"Saved: {filename}")

def main():
    if not LAW_API_USER_ID:
        print("Warning: LAW_API_USER_ID is not set. API calls might fail if key is required.")
        
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # Define targets
    TARGETS = {
        "prec": "판례",
        "expc": "법령해석례",
        "adjud": "행정심판례",
        "hunjae": "헌재결정례"
    }
    
    # Keywords
    keywords = ["법인세", "소득세", "부가가치세"]
    
    for target_code, target_name in TARGETS.items():
        print(f"\n--- Fetching {target_name} ({target_code}) ---")
        for keyword in keywords:
            # Fetch list
            search_items = fetch_list(target_code, keyword)
            
            # Fetch details for top 5 items
            count = 0
            for item in search_items:
                if count >= 5: break
                
                # Extract ID from List Item
                doc_id = item.get('판례일련번호') or item.get('행정심판일련번호') or item.get('법령해석일련번호') or item.get('헌재결정일련번호')
                
                if doc_id:
                    detail = fetch_detail(target_code, doc_id)
                    if detail:
                        save_document(target_code, detail)
                        count += 1
                    else:
                        print(f"  [!] Detail skipped/failed for ID: {doc_id}")
                    
                    time.sleep(0.2) # Rate limit aggressive fetching


if __name__ == "__main__":
    main()
