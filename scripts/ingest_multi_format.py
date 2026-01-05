#!/usr/bin/env python3
"""Multi-format document ingestion script.

Ingests Q&A documents in multiple formats (PDF, DOCX, CSV, Markdown) into
PostgreSQL and Qdrant vector store.

Usage:
    python ingest_multi_format.py --files data.pdf catalog.csv faq.docx
    python ingest_multi_format.py --dir ./documents --confidence-threshold 0.7
    python ingest_multi_format.py --files data.pdf --auto-confirm --output results.json
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.batch_processors import DocumentBatchProcessor
from app.services.ingestion import DocumentIngestionService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Ingest Q&A documents in multiple formats (PDF, DOCX, CSV, MD)"
    )

    # Input options
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--files",
        nargs="+",
        help="List of document files to ingest (max 5)"
    )
    input_group.add_argument(
        "--dir",
        type=str,
        help="Directory containing documents to ingest"
    )

    # Processing options
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.6,
        help="Minimum confidence score for Q&A pairs (0.0-1.0, default: 0.6)"
    )
    parser.add_argument(
        "--skip-duplicates",
        action="store_true",
        default=True,
        help="Remove duplicate Q&A pairs (default: True)"
    )
    parser.add_argument(
        "--auto-confirm",
        action="store_true",
        default=False,
        help="Automatically confirm and ingest pairs without prompting"
    )

    # Output options
    parser.add_argument(
        "--output",
        type=str,
        help="Save extracted Q&A pairs to JSON file"
    )
    parser.add_argument(
        "--report",
        action="store_true",
        default=False,
        help="Generate HTML report of ingestion results"
    )

    # Logging options
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)"
    )

    args = parser.parse_args()

    # Set logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    # Collect file paths
    file_paths = []

    if args.files:
        file_paths = args.files
    elif args.dir:
        dir_path = Path(args.dir)
        if not dir_path.is_dir():
            logger.error(f"Directory not found: {args.dir}")
            return 1

        # Find supported file types
        supported_extensions = {".pdf", ".docx", ".csv", ".md"}
        for ext in supported_extensions:
            file_paths.extend(dir_path.glob(f"*{ext}"))
            file_paths.extend(dir_path.glob(f"*{ext.upper()}"))

        file_paths = list(set(str(p) for p in file_paths))

    if not file_paths:
        logger.error("No document files found")
        return 1

    logger.info(f"Found {len(file_paths)} files to process")

    # Process batch
    processor = DocumentBatchProcessor()

    logger.info("Starting batch processing...")
    print("\n" + "=" * 80)
    print("DOCUMENT INGESTION PIPELINE")
    print("=" * 80 + "\n")

    result = await processor.process_batch(
        file_paths[:5],  # Limit to 5 files
        auto_confirm=args.auto_confirm,
        confidence_threshold=args.confidence_threshold,
        skip_duplicates=args.skip_duplicates
    )

    # Print summary
    print("\n" + "-" * 80)
    print("PROCESSING SUMMARY")
    print("-" * 80)
    print(f"Total files: {result.total_files}")
    print(f"Processed files: {result.processed_files}")
    print(f"Failed files: {len(result.failed_files)}")
    print(f"Q&A pairs extracted: {len(result.qa_pairs)}")
    print(f"Average confidence: {result.summary.get('average_confidence', 0):.2%}")
    print(f"Processing time: {result.processing_time_sec:.2f}s")

    if result.warnings:
        print("\nWarnings:")
        for warning in result.warnings:
            print(f"  - {warning}")

    if result.failed_files:
        print("\nFailed files:")
        for failed in result.failed_files:
            print(f"  - {failed.file_name}: {failed.error_message}")

    print("-" * 80 + "\n")

    # Save output if requested
    if args.output:
        output_path = Path(args.output)
        output_data = {
            "extraction_date": datetime.utcnow().isoformat(),
            "total_files": result.total_files,
            "processed_files": result.processed_files,
            "qa_pairs": [p.to_dict() for p in result.qa_pairs],
            "summary": result.summary,
            "warnings": result.warnings
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved results to: {output_path}")
        print(f"Results saved to: {output_path}\n")

    # Confirm before ingestion
    if not args.auto_confirm and result.qa_pairs:
        print(f"Found {len(result.qa_pairs)} Q&A pairs to ingest.")
        response = input("Do you want to ingest these pairs into the database? (yes/no): ").strip().lower()

        if response not in ["yes", "y"]:
            logger.info("Ingestion cancelled by user")
            print("Ingestion cancelled.\n")
            return 0

    # Ingest to database
    if result.qa_pairs:
        logger.info(f"Ingesting {len(result.qa_pairs)} Q&A pairs...")
        print("Ingesting Q&A pairs into database...\n")

        try:
            ingest_result = await DocumentIngestionService.ingest_pairs(
                result.qa_pairs,
                recreate_collection=False
            )

            logger.info(f"Ingestion complete: {ingest_result['ingested_count']} pairs")
            print(f"✓ Successfully ingested {ingest_result['ingested_count']} Q&A pairs")

        except Exception as e:
            logger.error(f"Error during ingestion: {e}")
            print(f"✗ Error during ingestion: {e}")
            return 1

    else:
        logger.warning("No Q&A pairs to ingest")
        print("No Q&A pairs to ingest.\n")

    print("=" * 80)
    print("INGESTION COMPLETE")
    print("=" * 80 + "\n")

    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    exit_code = asyncio.run(main())
    sys.exit(exit_code)
