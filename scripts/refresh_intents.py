#!/usr/bin/env python3
"""
Скрипт для автогенерации реестра интентов и категорий из базы данных.
Wrapper around RegistryGenerator service.
"""

import sys
import os
import asyncio
import argparse

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.metadata_generation.registry_generator import RegistryGenerator, DEFAULT_REGISTRY_PATH
from app.settings import settings

def main():
    parser = argparse.ArgumentParser(
        description="Refresh the intents registry from database metadata.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=DEFAULT_REGISTRY_PATH,
        help=f"Output path for the registry YAML file (default: {DEFAULT_REGISTRY_PATH})"
    )
    
    args = parser.parse_args()
    
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    print(f"🔄 Refreshing registry -> {args.output}")
    success = asyncio.run(RegistryGenerator.refresh_intents(args.output))
    
    if success:
        print("✅ Registry refreshed successfully.")
        sys.exit(0)
    else:
        print("❌ Registry refresh failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
