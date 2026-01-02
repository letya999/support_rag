from pydantic import BaseModel

class PipelineConfig(BaseModel):
    max_retries: int = 3
    
pipeline_config = PipelineConfig()
