from typing import Dict, Any, List
from datetime import datetime
from app.nodes.retrieval.evaluator import RetrievalEvaluator
from app.nodes.generation.evaluator import GenerationEvaluator
from app.dataset.loader import load_ground_truth_dataset
from app.pipeline.graph import rag_graph
from app.observability.langfuse_client import get_langfuse_client

class PipelineEvaluator:
    def __init__(self):
        self.retrieval_evaluator = RetrievalEvaluator()
        self.generation_evaluator = GenerationEvaluator()
        
    async def run_evaluation(self, dataset_path: Optional[str] = None, run_name: str = None):
        """
        Run End-to-End Pipeline Evaluation.
        """
        if not run_name:
            run_name = f"e2e-eval-{datetime.now().strftime('%Y%m%d-%H%M')}"
            
        items = load_ground_truth_dataset(dataset_path)
        langfuse = get_langfuse_client()
        
        results = []
        
        print(f"Starting E2E Evaluation: {run_name}")
        
        for i, item in enumerate(items):
            # Run Pipeline
            # Trace should be handled by callbacks in graph if configured, 
            # OR we wrap it here if we want a specific eval trace.
            # "PipelineEvaluator создаёт trace на каждый evaluation run"
            
            trace = None
            if langfuse:
                trace = langfuse.trace(
                    name="e2e_evaluation",
                    input={"question": item.question},
                    metadata={"run_name": run_name}
                )
            
            # Using trace as parent if possible? LangGraph callbacks usually create their own root if not passed.
            # Currently we just invoke. LangGraph callbacks will log to Langfuse.
            # If we want to group under this trace, we might need to pass callbacks with this trace.
            
            # For this refactor, let's just invoke and separate scoring logic
            response = await rag_graph.ainvoke({"question": item.question})
            
            # Extract outputs
            retrieved_docs = response.get("docs", [])
            generated_answer = response.get("answer", "")
            
            # Calculate Scores
            ret_metrics = self.retrieval_evaluator.calculate_metrics(
                item.expected_chunk_answer, 
                retrieved_docs
            )
            
            # Log scores to trace
            if trace:
                trace.update(output={"answer": generated_answer, "docs": retrieved_docs})
                
                for k, v in ret_metrics.items():
                    trace.score(name=f"retrieval_{k}", value=v)
                    
            results.append({
                "question": item.question,
                "retrieval_metrics": ret_metrics,
                "answer": generated_answer
            })
            
        return {"run_name": run_name, "results": results}

pipeline_evaluator = PipelineEvaluator()
