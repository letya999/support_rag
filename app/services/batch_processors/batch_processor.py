"""Batch processor for handling multiple documents."""

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import List

from app.services.document_loaders import BatchResult, DocumentContent, FileError, LoaderFactory, ProcessedQAPair
from app.services.metadata_generators import KeywordMapper, MetadataEnricher, MetadataNormalizer
from app.services.qa_extractors import ExtractorFactory
from app.services.qa_validators import ConfidenceScorer, DuplicateDetector, FormatValidator, SemanticValidator
from app.services.structure_detectors import DocumentStructureAnalyzer
from app.services.text_processors import TextCleaner

logger = logging.getLogger(__name__)


class DocumentBatchProcessor:
    """Processes batches of documents (up to 5) to extract and validate Q&A pairs."""

    def __init__(self, max_files: int = 5, max_file_size_mb: int = 50):
        """Initialize batch processor.

        Args:
            max_files: Maximum files in a batch
            max_file_size_mb: Maximum file size in MB
        """
        self.max_files = max_files
        self.max_file_size_mb = max_file_size_mb
        self.text_cleaner = TextCleaner()
        self.structure_analyzer = DocumentStructureAnalyzer()

    async def process_batch(
        self,
        file_paths: List[str],
        auto_confirm: bool = False,
        confidence_threshold: float = 0.6,
        skip_duplicates: bool = True
    ) -> BatchResult:
        """Process a batch of documents.

        Args:
            file_paths: List of paths to document files (max 5)
            auto_confirm: If True, don't require confirmation
            confidence_threshold: Minimum confidence to include pair
            skip_duplicates: If True, remove duplicate pairs

        Returns:
            BatchResult with processed Q&A pairs
        """
        start_time = time.time()
        logger.info(f"Starting batch processing of {len(file_paths)} files")

        # Validate input
        if len(file_paths) > self.max_files:
            logger.error(f"Too many files: {len(file_paths)} > {self.max_files}")
            return BatchResult(
                total_files=len(file_paths),
                processed_files=0,
                failed_files=[FileError(
                    file_name="batch",
                    error_type="invalid_batch",
                    error_message=f"Too many files ({len(file_paths)} > {self.max_files})"
                )],
                qa_pairs=[],
                warnings=[f"Batch limited to {self.max_files} files"],
                processing_time_sec=0
            )

        result = BatchResult(
            total_files=len(file_paths),
            processed_files=0,
            failed_files=[],
            qa_pairs=[],
            warnings=[],
            processing_time_sec=0
        )

        # Process each file
        for file_path in file_paths:
            try:
                logger.info(f"Processing file: {file_path}")

                # Load document
                loader = LoaderFactory.get_loader(file_path, self.max_file_size_mb)
                document = loader.load(file_path)
                logger.info(f"Loaded document: {len(document.blocks)} blocks")

                # Analyze structure
                structure = self.structure_analyzer.analyze(document)
                logger.info(f"Detected structure: {structure.detected_format}")

                # Extract Q&A pairs
                extractor = ExtractorFactory.get_extractor(structure)
                raw_pairs = extractor.extract(document.blocks, structure)
                logger.info(f"Extracted {len(raw_pairs)} raw pairs")

                # Validate and process pairs
                for raw_pair in raw_pairs:
                    # Clean text
                    question = self.text_cleaner.clean_text(raw_pair.question)
                    answer = self.text_cleaner.clean_text(raw_pair.answer)

                    # Format validation
                    format_result = FormatValidator.validate(raw_pair)
                    if not format_result.is_valid:
                        logger.debug(f"Format validation failed: {format_result.errors}")
                        continue

                    # Semantic validation
                    semantic_result = SemanticValidator.validate(raw_pair)
                    if semantic_result.warnings:
                        logger.debug(f"Semantic warnings: {semantic_result.warnings}")

                    # Score confidence
                    confidence = ConfidenceScorer.score_pair(raw_pair, structure)

                    if confidence < confidence_threshold:
                        logger.debug(
                            f"Confidence below threshold: {confidence:.2f} < {confidence_threshold}"
                        )
                        continue

                    # Enrich metadata
                    metadata = MetadataEnricher.enrich(
                        raw_pair,
                        source_document=Path(file_path).name,
                        existing_metadata=raw_pair.metadata
                    )

                    # Normalize metadata
                    metadata = MetadataNormalizer.normalize(metadata)

                    # Create processed pair
                    processed_pair = ProcessedQAPair(
                        question=question,
                        answer=answer,
                        metadata=metadata,
                        confidence_score=confidence,
                        extraction_method=raw_pair.extraction_method
                    )

                    result.qa_pairs.append(processed_pair)

                result.processed_files += 1
                logger.info(f"Successfully processed {file_path}")

            except FileNotFoundError as e:
                logger.error(f"File not found: {file_path}")
                result.failed_files.append(FileError(
                    file_name=Path(file_path).name,
                    error_type="file_not_found",
                    error_message=str(e)
                ))

            except ValueError as e:
                logger.error(f"Invalid file format: {file_path} - {e}")
                result.failed_files.append(FileError(
                    file_name=Path(file_path).name,
                    error_type="unsupported_format",
                    error_message=str(e)
                ))

            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}", exc_info=True)
                result.failed_files.append(FileError(
                    file_name=Path(file_path).name,
                    error_type="processing_error",
                    error_message=str(e),
                    traceback=str(e)
                ))

        # Remove duplicates if requested
        if skip_duplicates and result.qa_pairs:
            original_count = len(result.qa_pairs)
            result.qa_pairs = DuplicateDetector.remove_duplicates(result.qa_pairs)
            duplicates_removed = original_count - len(result.qa_pairs)
            if duplicates_removed > 0:
                result.warnings.append(f"Removed {duplicates_removed} duplicate pairs")

        # Calculate processing time
        result.processing_time_sec = time.time() - start_time

        logger.info(
            f"Batch complete: {result.processed_files}/{result.total_files} files processed, "
            f"{len(result.qa_pairs)} Q&A pairs extracted in {result.processing_time_sec:.2f}s"
        )

        return result
