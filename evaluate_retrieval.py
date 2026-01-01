from dotenv import load_dotenv
load_dotenv()

import os
import json
import nest_asyncio
from datasets import Dataset
from ragas import evaluate
from ragas.llms import llm_factory
from ragas.embeddings import OpenAIEmbeddings
from ragas.metrics.collections import LLMContextPrecisionWithReference, LLMContextRecall
from openai import OpenAI
from langfuse import Langfuse

from app.utils import get_embedding, search_documents

nest_asyncio.apply()

langfuse = Langfuse()
DATASET_NAME = "support-qa-dataset"

def load_test_data(file_path: str):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File {file_path} not found.")
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def sync_dataset_to_langfuse(test_data):
    try:
        langfuse.get_dataset(DATASET_NAME)
        print(f"✅ Dataset '{DATASET_NAME}' already exists in Langfuse.")
    except Exception:
        print(f"📦 Creating dataset '{DATASET_NAME}' in Langfuse...")
        langfuse.create_dataset(name=DATASET_NAME)
        for item in test_data:
            langfuse.create_dataset_item(
                dataset_name=DATASET_NAME,
                input=item["question"],
                expected_output=item["answer"]
            )
        print(f"✅ Uploaded {len(test_data)} items to Langfuse dataset.")

def run_evaluation():
    print("🚀 Starting retrieval evaluation...")
    
    try:
        test_data = load_test_data("eval_dataset.json")
        sync_dataset_to_langfuse(test_data)
    except Exception as e:
        print(f"❌ Error loading/syncing data: {e}")
        return
    
    questions = []
    contexts = []
    ground_truths = []
    
    for item in test_data:
        q = item["question"]
        gt = item["answer"]
        
        print(f"Processing: {q}")
        
        try:
            emb = get_embedding(q)
            results = search_documents(emb, top_k=3)
            retrieved_contexts = [r["content"] for r in results]
            
            questions.append(q)
            contexts.append(retrieved_contexts)
            ground_truths.append(gt)
        except Exception as e:
            print(f"⚠️ Error processing item '{q}': {e}")
            continue
    
    if not questions:
        print("❌ No data processed successfully.")
        return

    # Dataset для Ragas - retrieval only (без response)
    dataset = Dataset.from_dict({
        "user_input": questions,           # Ragas 0.2 использует user_input
        "retrieved_contexts": contexts,    # Ragas 0.2 использует retrieved_contexts
        "reference": ground_truths         # ground_truth → reference
    })
    
    print("📊 Running Ragas retrieval metrics...")
    
    try:
        # Новый API Ragas 0.2
        openai_client = OpenAI()
        llm = llm_factory("gpt-4o-mini", client=openai_client)
        embeddings = OpenAIEmbeddings(model="text-embedding-3-small", client=openai_client)
        
        metrics = [
            LLMContextPrecisionWithReference(llm=llm),
            LLMContextRecall(llm=llm),
        ]
        
        # Запуск оценки
        result = evaluate(
            dataset=dataset,
            metrics=metrics,
        )
        
        print("\n✅ Evaluation Results:")
        print(result)
        
        # Получение DataFrame с результатами
        df = result.to_pandas()
        print("\n📊 Detailed Results:")
        print(df.head())
        
        # Логирование в Langfuse
        print(f"\n📈 Recording scores in Langfuse...")
        
        for metric in metrics:
            metric_name = metric.name
            if metric_name in df.columns:
                avg_score = df[metric_name].mean()
                langfuse.create_score(
                    name=f"baseline-{metric_name}",
                    value=float(avg_score),
                    comment=f"Baseline run, {len(questions)} samples"
                )
                print(f"  → {metric_name}: {avg_score:.4f}")
        
        langfuse.flush()
        print("\n✅ Done! Metrics recorded in Langfuse.")
        
    except Exception as e:
        import traceback
        print(f"❌ Error during evaluation: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    run_evaluation()