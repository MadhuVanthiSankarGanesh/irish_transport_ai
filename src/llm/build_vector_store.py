import json
import os
import re
from langchain_community.vectorstores import Chroma
from langchain_ollama import OllamaEmbeddings

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
INPUT_PATH = os.path.join(PROJECT_ROOT, "data", "processed", "transit_knowledge_base.json")
VECTOR_PATH = os.path.join(PROJECT_ROOT, "data", "vector_db")


class SimpleHashEmbeddings:
    """Torch-free fallback embeddings using token hashing."""

    def __init__(self, dim=256):
        self.dim = dim
        self.token_pattern = re.compile(r"[A-Za-z0-9_]+")

    def _embed_text(self, text):
        vec = [0.0] * self.dim
        tokens = self.token_pattern.findall((text or "").lower())
        if not tokens:
            return vec
        for token in tokens:
            idx = hash(token) % self.dim
            vec[idx] += 1.0
        norm = sum(x * x for x in vec) ** 0.5
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec

    def embed_documents(self, texts):
        return [self._embed_text(t) for t in texts]

    def embed_query(self, text):
        return self._embed_text(text)


print("Loading documents...")

with open(INPUT_PATH) as f:
    docs = json.load(f)

texts = [d["text"] for d in docs]

print("Total documents:", len(texts))

print("Loading embedding model...")

try:
    embedding_model = OllamaEmbeddings(model="nomic-embed-text")
    print("Using Ollama embeddings model: nomic-embed-text")
except Exception as exc:
    print(f"Falling back to SimpleHashEmbeddings due to embedding backend error: {exc}")
    embedding_model = SimpleHashEmbeddings(dim=256)

print("Creating vector database...")

# Keep per-upsert writes below Chroma's max batch size.
batch_size = int(os.environ.get("CHROMA_BATCH_SIZE", "5000"))
db = Chroma(
    embedding_function=embedding_model,
    persist_directory=VECTOR_PATH
)

for start in range(0, len(texts), batch_size):
    end = min(start + batch_size, len(texts))
    print(f"Adding texts {start + 1}-{end} / {len(texts)}")
    db.add_texts(texts[start:end])

if hasattr(db, "persist"):
    db.persist()

print("Vector database created at:")
print(VECTOR_PATH)
