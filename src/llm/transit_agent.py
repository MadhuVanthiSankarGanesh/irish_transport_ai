from langchain_community.vectorstores import Chroma
from langchain_ollama import OllamaLLM, OllamaEmbeddings
from langchain.chains import RetrievalQA

VECTOR_PATH = r"E:\irish_transport_ai\data\vector_db"

print("Loading embeddings (Ollama)...")

embeddings = OllamaEmbeddings(model="nomic-embed-text")

print("Loading vector database...")

db = Chroma(
    persist_directory=VECTOR_PATH,
    embedding_function=embeddings
)

retriever = db.as_retriever(search_kwargs={"k":5})

print("Loading LLM from Ollama...")

llm = OllamaLLM(model="mistral")

qa_chain = RetrievalQA.from_chain_type(
    llm=llm,
    retriever=retriever
)

print("\nTransit AI Agent Ready\n")

while True:

    query = input("Ask Transit Planner > ")

    if query.lower() in ["exit", "quit"]:
        break

    response = qa_chain.invoke({"query": query})

    print("\nAI Analysis:\n")
    print(response["result"])