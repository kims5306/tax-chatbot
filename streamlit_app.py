import streamlit as st
import chromadb
from chromadb.utils import embedding_functions
from sentence_transformers import SentenceTransformer
import google.generativeai as genai
import os
from dotenv import load_dotenv

# Compatibility fix for Streamlit Cloud (Linux) + ChromaDB
try:
    __import__('pysqlite3')
    import sys
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass


# Load params
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CHROMA_DB_DIR = "chroma_db"
COLLECTION_NAME = "tax_laws"

# Page Config with proper title and layout
st.set_page_config(
    page_title="SeMu-Bot (Tax AI)", 
    page_icon="⚖️",
    layout="wide"
)

# Custom CSS for cleaner UI
st.markdown("""
<style>
    .stChatMessage {
        background-color: #f0f2f6; 
        border-radius: 10px;
        padding: 10px;
        margin-bottom: 5px;
    }
    .user-message {
        background-color: #e8f0fe;
    }
    h1 {
        font-family: 'Helvetica', sans-serif;
        color: #333;
    }
    .stDeployButton {display:none;}
</style>
""", unsafe_allow_html=True)

# Application Title
col1, col2 = st.columns([1, 5])
with col1:
    st.image("https://cdn-icons-png.flaticon.com/512/2645/2645897.png", width=60) # Placeholder Tax Icon
with col2:
    st.title("AI Tax Accountant")
    st.caption("국세청 판례, 예규 및 세무 법령 기반 지능형 챗봇 (Powered by Gemini)")

# Sidebar for Settings & References
with st.sidebar:
    st.header("⚙️ Settings")
    if st.button("🗑️ 대화 기록 지우기"):
        st.session_state.messages = []
        st.rerun()
    
    st.markdown("---")
    st.markdown("### 📚 Data Sources")
    st.caption("- main taxlaw.pdf (Internal Law)")
    st.caption("- National Law API (Precedents)")
    st.markdown("---")
    st.info("💡 질문 예시:\n- 부가가치세 신고 기간은?\n- 법인세 손금산입 요건은?\n- 업무무관가지급금이란?")

if not GEMINI_API_KEY:
    st.error("❌ GEMINI_API_KEY is missing in .env")
    st.stop()

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)

# Initialize Resources (Cached)
@st.cache_resource
def get_chroma_collection():
    client = chromadb.PersistentClient(path=CHROMA_DB_DIR)
    model_name = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    
    class LocalHuggingFaceEmbedding(chromadb.EmbeddingFunction):
        def __init__(self, model_name):
            self.model = SentenceTransformer(model_name)
        def __call__(self, input):
            return self.model.encode(input).tolist()
            
    embedding_fn = LocalHuggingFaceEmbedding(model_name)
    
    try:
        col = client.get_collection(name=COLLECTION_NAME, embedding_function=embedding_fn)
    except Exception:
        col = None
    return col

collection = get_chroma_collection()

if collection is None:
    st.warning("⚠️ No database found. Please run ingest.py locally first.")

# Chat Logic
if "messages" not in st.session_state:
    st.session_state["messages"] = [{"role": "assistant", "content": "안녕하세요! 세무 법령 및 판례에 대해 무엇이든 물어보세요."}]

# Display Chat History
for msg in st.session_state.messages:
    if msg["role"] == "user":
        st.chat_message("user").write(msg["content"])
    else:
        st.chat_message("assistant").write(msg["content"])

# User Input
if prompt := st.chat_input("질문을 입력하세요..."):
    # 1. User Message
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)
    
    # 2. RAG Retrieval
    context_text = ""
    references = []
    
    if collection:
        results = collection.query(
            query_texts=[prompt],
            n_results=4  # Increased context
        )
        
        if results['documents']:
            for i, doc in enumerate(results['documents'][0]):
                meta = results['metadatas'][0][i]
                # Format context for LLM
                context_text += f"[Document {i+1}]\nTitle: {meta.get('case_name')}\nContent: {doc}\n\n"
                references.append(meta)

    # 3. Gemini Generation (Dynamic Model Selection)
    available_models = []
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name)
    except Exception as e:
        available_models = []

    # Prefer Flash -> Pro -> Default
    model_name = "gemini-1.5-flash" # Fallback
    for m in available_models:
        if "flash" in m:
            model_name = m
            break
        elif "pro" in m and "1.5" in m:
            model_name = m
    
    # Clean up model name (remove 'models/' prefix if present for the client, though library handles both)
    if model_name.startswith("models/"):
        model_name = model_name.replace("models/", "")
        
    model = genai.GenerativeModel(model_name)
    
    system_prompt = f"""
    당신은 한국의 유능한 세무 전문 AI 변호사입니다.
    사용자의 질문에 대해 아래 제공된 [참고 자료]를 바탕으로 정확하고 상세하게 답변하세요.
    
    [답변 가이드]
    1. **근거 중심**: 반드시 아래 제공된 법령이나 판례를 인용하여 답변하세요.
    2. **구조화**: 답변은 읽기 편하게 불렛 포인트나 번호를 매겨 정리하세요.
    3. **출처 표기**: 답변 중간중간에 (참고: 법인세법 제XX조) 처럼 출처를 명시하세요.
    4. 관련 자료가 없으면 솔직하게 "제공된 데이터베이스 내에서 관련 내용을 찾을 수 없습니다."라고 말하고 일반적인 지식을 덧붙이세요.
    
    [참고 자료]
    {context_text}
    """
    
    full_prompt = f"{system_prompt}\n\n사용자 질문: {prompt}"
    
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        with st.spinner("법령 분석 및 답변 작성 중..."):
            try:
                response = model.generate_content(full_prompt)
                answer = response.text
                message_placeholder.markdown(answer)
                
                # Append to history
                st.session_state.messages.append({"role": "assistant", "content": answer})
                
                # Show References in Expander (Clean UI)
                if references:
                    with st.expander("📚 참고한 법령/판례 리스트 보기"):
                        for ref in references:
                            st.markdown(f"**[{ref.get('type', '법령')}] {ref.get('case_name')}**")
                            # st.caption(ref.get('filename')) # Optional
                    
            except Exception as e:
                st.error(f"Error generating response: {e}")
                
                # Debug: List available models
                try:
                    st.warning("🔍 Debug: Available Models for this API Key:")
                    available_models = []
                    for m in genai.list_models():
                        if 'generateContent' in m.supported_generation_methods:
                            available_models.append(m.name)
                    st.code(available_models)
                    st.info("If the list is empty, check your API Key permissions.")
                except Exception as debug_err:
                    st.error(f"Debug failed: {debug_err}")
