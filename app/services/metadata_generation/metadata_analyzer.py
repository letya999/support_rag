"""
Metadata Analyzer Service.
Facade for metadata generation orchestration used in batch processing and ingestion.
Wrapper around app.services.metadata_generation.analyzer.HybridMetadataAnalyzer.
"""
from typing import List, Dict, Optional
from app.services.metadata_generation.analyzer import HybridMetadataAnalyzer
from app.services.metadata_generation.models import MetadataConfig, AnalysisResult

class MetadataAnalyzerService:
    """
    Service for analyzing content to generate metadata (categories, intents, handoff scoring).
    Primarily used for data ingestion and backfill processes.
    """
    def __init__(self, config: Optional[MetadataConfig] = None):
        self._analyzer = HybridMetadataAnalyzer(config)

    async def initialize(self):
        """Initialize underlying models and classifiers."""
        await self._analyzer.initialize()

    async def analyze_batch(
        self, 
        qa_pairs: List[Dict[str, str]], 
        analysis_id: str
    ) -> AnalysisResult:
        """
        Analyze a batch of Q&A pairs to generate metadata.
        
        Args:
            qa_pairs: List of {"question": "...", "answer": "..."}
            analysis_id: Tracking ID
            
        Returns:
            AnalysisResult containing metadata and statistics.
        """
        return await self._analyzer.analyze_batch(qa_pairs, analysis_id)
