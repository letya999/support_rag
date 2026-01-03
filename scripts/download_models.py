import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sentence_transformers import SentenceTransformer, CrossEncoder
from transformers import MarianMTModel, MarianTokenizer

def download_models():
    print("Pre-downloading models to cache...")
    
    # 1. Embedding model
    embed_model = "intfloat/multilingual-e5-small"
    print(f"Downloading {embed_model}...")
    SentenceTransformer(embed_model)
    
    # 2. Reranker model
    rerank_model = "BAAI/bge-reranker-v2-m3"
    print(f"Downloading {rerank_model}...")
    # CrossEncoder(rerank_model) # This might be slow/large
    # Let's use the transformers way to be sure everything is cached correctly for CrossEncoder
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    AutoTokenizer.from_pretrained(rerank_model)
    AutoModelForSequenceClassification.from_pretrained(rerank_model)

    # 3. Translation models
    translation_models = [
        "Helsinki-NLP/opus-mt-ru-en",
        "Helsinki-NLP/opus-mt-en-ru"
    ]
    for model_name in translation_models:
        print(f"Downloading {model_name}...")
        MarianTokenizer.from_pretrained(model_name)
        MarianMTModel.from_pretrained(model_name)
    
    print("All models downloaded successfully!")

if __name__ == "__main__":
    download_models()
