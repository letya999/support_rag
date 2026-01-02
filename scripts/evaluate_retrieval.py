import os
import sys

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import json
import nest_asyncio
from datetime import datetime
from datasets import Dataset
from ragas import evaluate
from ragas.llms import llm_factory
from ragas.embeddings import OpenAIEmbeddings
# Reverting to ragas.metrics as these classes were proven to work in testing
from ragas.metrics import LLMContextPrecisionWithReference, LLMContextRecall
from openai import OpenAI
from langfuse import Langfuse

from app.embeddings import get_embedding
from app.search import search_documents

nest_asyncio.apply()

langfuse = Langfuse()
DATASET_NAME = "support-qa-dataset"

def load_test_data(file_path: str):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File {file_path} not found.")
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def sync_dataset_to_langfuse(test_data):
    """Создаёт датасет в Langfuse если его нет"""
    try:
        langfuse.get_dataset(DATASET_NAME)
        print(f"✅ Dataset '{DATASET_NAME}' already exists in Langfuse.")
    except Exception:
        print(f"📦 Creating dataset '{DATASET_NAME}' in Langfuse...")
        langfuse.create_dataset(name=DATASET_NAME)
        for item in test_data:
            langfuse.create_dataset_item(
                dataset_name=DATASET_NAME,
                input={"question": item["question"]},
                expected_output={"answer": item["answer"]}
            )
        print(f"✅ Uploaded {len(test_data)} items to Langfuse dataset.")

async def run_evaluation():
    print("🚀 Starting retrieval evaluation...")
    
    # 1. Загрузка данных
    try:
        test_data = load_test_data("eval_dataset.json")
        sync_dataset_to_langfuse(test_data)
    except Exception as e:
        print(f"❌ Error loading/syncing data: {e}")
        return
    
    # 2. Получаем датасет из Langfuse
    dataset = langfuse.get_dataset(DATASET_NAME)
    run_name = f"ragas-baseline-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    print(f"📊 Running evaluation '{run_name}' on {len(dataset.items)} items...")
    
    # 3. Собираем данные для Ragas + создаём traces в Langfuse
    questions = []
    contexts = []
    ground_truths = []
    trace_ids = []
    
    for item in dataset.items:
        # Обрабатываем оба формата (старый: строка, новый: dict)
        if isinstance(item.input, dict):
            question = item.input.get("question", item.input.get("text", str(item.input)))
        else:
            question = str(item.input)
        
        if isinstance(item.expected_output, dict):
            expected_answer = item.expected_output.get("answer", item.expected_output.get("text", str(item.expected_output)))
        else:
            expected_answer = str(item.expected_output)
        
        print(f"Processing: {question[:50]}...")
        
        # Создаём trace через item.run() - автоматически связывает с dataset
        with item.run(
            run_name=run_name,
            run_metadata={"eval_type": "retrieval_only", "step": "retrieval"}
        ) as trace:
            try:
                # Выполняем retrieval
                emb = await get_embedding(question)
                results = await search_documents(emb, top_k=3)
                retrieved_contexts = [r["content"] for r in results]
                
                # Обновляем trace с результатами
                trace.update(
                    input={"question": question},
                    output={"contexts": retrieved_contexts}
                )
                
                # Сохраняем для Ragas
                questions.append(question)
                contexts.append(retrieved_contexts)
                ground_truths.append(expected_answer)
                trace_ids.append(trace.trace_id)
                
            except Exception as e:
                print(f"⚠️ Error: {e}")
                continue
    
    if not questions:
        print("❌ No data processed successfully.")
        return
    
    # 4. Запускаем Ragas evaluation
    print(f"\n📊 Running Ragas metrics on {len(questions)} samples...")
    
    try:
        openai_client = OpenAI()
        llm = llm_factory("gpt-4o-mini", client=openai_client)
        
        metrics = [
            LLMContextPrecisionWithReference(llm=llm),
            LLMContextRecall(llm=llm),
        ]
        
        ragas_dataset = Dataset.from_dict({
            "user_input": questions,
            "retrieved_contexts": contexts,
            "reference": ground_truths
        })
        
        result = evaluate(
            dataset=ragas_dataset,
            metrics=metrics,
        )
        
        print("\n✅ Evaluation Results:")
        print(result)
        
        # 5. Получаем DataFrame и записываем скоры в Langfuse
        df = result.to_pandas()
        print("\n📊 Detailed Results:")
        print(df.head())
        
        # 6. Записываем скоры для каждого trace
        print(f"\n📈 Recording scores in Langfuse...")
        
        for i, trace_id in enumerate(trace_ids):
            for metric in metrics:
                metric_name = metric.name
                if metric_name in df.columns:
                    score_value = df.iloc[i][metric_name]
                    if score_value is not None:
                        langfuse.create_score(
                            trace_id=trace_id,
                            name=metric_name,
                            value=float(score_value),
                        )
            print(f"  → Scored trace {i+1}/{len(trace_ids)}")
        
        # 7. Записываем средние скоры для всего run
        for metric in metrics:
            metric_name = metric.name
            if metric_name in df.columns:
                avg_score = df[metric_name].mean()
                print(f"  📊 {metric_name}: {avg_score:.4f}")
        
        langfuse.flush()
        print(f"\n✅ Done! Check Langfuse dataset '{DATASET_NAME}' → run '{run_name}'")
        
    except Exception as e:
        import traceback
        print(f"❌ Error during evaluation: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    import asyncio
    asyncio.run(run_evaluation())