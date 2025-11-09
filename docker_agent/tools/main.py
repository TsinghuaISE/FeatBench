"""
Main entry point for data transformation tool

This module provides the command-line interface and main function
for the data transformation pipeline.
"""

import argparse
import sys
from pathlib import Path
from .data_transformer import DataTransformer


def main():
    """Main entry point for data transformation"""
    parser = argparse.ArgumentParser(
        description="Transform raw analysis data into agent-facing JSON format"
    )
    parser.add_argument(
        "input_path",
        type=str,
        help="Path to input JSON file (e.g., final_analysis_results.json)"
    )
    parser.add_argument(
        "output_path",
        type=str,
        help="Path to output JSON file (e.g., featbench_v1_0.json)"
    )
    parser.add_argument(
        "--no-deduplicate",
        action="store_true",
        help="Disable deduplication by instance_id"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Configure logging
    import logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    logger = logging.getLogger(__name__)

    # Validate input file exists
    if not Path(args.input_path).exists():
        logger.error(f"Input file not found: {args.input_path}")
        sys.exit(1)

    # Run transformation
    try:
        transformer = DataTransformer()
        transformer.transform(
            input_path=args.input_path,
            output_path=args.output_path,
            deduplicate=not args.no_deduplicate
        )
        print(f"\n✅ Transformation completed successfully!")
        print(f"   Output: {args.output_path}")
    except Exception as e:
        logger.error(f"Transformation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()