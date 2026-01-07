#!/usr/bin/env python3
"""
Product-Centric Synthetic Q&A Generator

Generates realistic, comprehensive FAQ from scratch based on:
- Product/service description
- Target audience
- Industry type
- Feature list

This enables creating synthetic datasets for ANY product without existing FAQ.

Usage:
    # Generate 500 pairs for a SaaS product
    python generate_qa_from_product.py \
        --product-name "CloudDrive Pro" \
        --description "Cloud storage service with AI-powered file organization" \
        --features "file sync,sharing,encryption,mobile app,API" \
        --industry "SaaS" \
        --count 500 \
        --output datasets/qa_clouddrive_500.json

    # Generate for e-commerce platform
    python generate_qa_from_product.py \
        --product-name "ShopHub" \
        --description "All-in-one e-commerce platform for small businesses" \
        --features "inventory management,payment processing,shipping integration,analytics" \
        --industry "E-commerce" \
        --count 300 \
        --output datasets/qa_shophub_300.json

    # Using config file
    python generate_qa_from_product.py \
        --config-file product_config.yaml \
        --count 1000 \
        --output datasets/qa_generated.json
"""

import json
import argparse
import asyncio
import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ProductCentricQAGenerator:
    """Generate FAQ for any product/service from description."""

    # Industry-specific question categories
    INDUSTRY_CATEGORIES = {
        "SaaS": [
            ("Getting Started", ["onboarding", "installation", "setup", "trial", "free_tier"]),
            ("Account & Auth", ["password", "login", "account_security", "profile", "email_change"]),
            ("Features & Usage", ["feature_overview", "tutorial", "best_practices", "limitations", "shortcuts"]),
            ("Plans & Pricing", ["pricing", "upgrade", "downgrade", "subscription", "refund"]),
            ("Integration", ["api", "webhooks", "third_party", "export", "import"]),
            ("Technical Support", ["errors", "performance", "bugs", "compatibility", "troubleshooting"]),
        ],
        "E-commerce": [
            ("Shopping", ["browsing", "search", "filters", "wishlist", "recommendations"]),
            ("Orders", ["placing_order", "payment", "order_tracking", "modification", "cancellation"]),
            ("Shipping & Delivery", ["shipping_methods", "tracking", "international", "costs", "speed"]),
            ("Returns & Refunds", ["return_process", "refund_status", "damaged_items", "exchanges", "policy"]),
            ("Account", ["registration", "profile", "addresses", "payment_methods", "order_history"]),
            ("Promotions", ["coupons", "discounts", "loyalty", "sales", "special_offers"]),
        ],
        "Fintech": [
            ("Account Setup", ["registration", "verification", "kyc", "documents", "security"]),
            ("Banking", ["transfers", "deposits", "withdrawals", "fees", "limits"]),
            ("Investing", ["trading", "portfolio", "risk", "diversification", "reports"]),
            ("Security", ["authentication", "fraud_protection", "privacy", "encryption", "alerts"]),
            ("Cards & Payments", ["card_ordering", "payment", "merchant_support", "limits", "international"]),
            ("Technical", ["app_issues", "web_access", "sync", "notifications", "performance"]),
        ],
        "Social Media": [
            ("Getting Started", ["account_creation", "profile_setup", "verification", "mobile_app", "desktop"]),
            ("Content", ["posting", "editing", "deleting", "privacy", "scheduling"]),
            ("Engagement", ["comments", "likes", "sharing", "messaging", "notifications"]),
            ("Features", ["stories", "live", "groups", "pages", "ads"]),
            ("Community Guidelines", ["rules", "moderation", "reporting", "bans", "appeals"]),
            ("Technical", ["bugs", "performance", "app_crashes", "sync_issues", "support"]),
        ],
        "Marketplace": [
            ("Selling", ["listing", "pricing", "inventory", "shipping_setup", "analytics"]),
            ("Buying", ["browsing", "purchase", "payment", "reviews", "returns"]),
            ("Account", ["registration", "verification", "payout", "tax", "disputes"]),
            ("Communication", ["messaging", "ratings", "feedback", "reputation", "trust"]),
            ("Technical", ["app_features", "mobile_app", "integration", "api", "automation"]),
            ("Policies", ["terms", "fees", "prohibited_items", "disputes", "appeals"]),
        ],
        "Generic": [
            ("Getting Started", ["registration", "setup", "tutorial", "first_steps", "help"]),
            ("Account", ["profile", "settings", "password", "security", "preferences"]),
            ("Features", ["how_to", "usage", "best_practices", "tips", "limitations"]),
            ("Support", ["contact", "help", "issues", "feedback", "bugs"]),
            ("Billing", ["pricing", "payment", "refund", "invoices", "plans"]),
            ("Technical", ["errors", "performance", "compatibility", "troubleshooting", "api"]),
        ],
    }

    def __init__(self, product_name: str, description: str, industry: str = "Generic"):
        """Initialize generator for a specific product."""
        try:
            from app.integrations.llm import get_llm
            self.llm = get_llm(model="gpt-4o-mini", temperature=0.8)
            logger.info("✓ Initialized OpenAI LLM")
        except (ImportError, ModuleNotFoundError):
            # Fallback: use direct OpenAI import
            try:
                from langchain_openai import ChatOpenAI
                import os
                api_key = os.getenv("OPENAI_API_KEY")
                if not api_key:
                    raise ValueError("OPENAI_API_KEY environment variable not set")
                self.llm = ChatOpenAI(api_key=api_key, model="gpt-4o-mini", temperature=0.8)
                logger.info("✓ Initialized OpenAI LLM (direct)")
            except ImportError as e:
                logger.error(f"Could not import LLM: {e}")
                raise

        self.product_name = product_name
        self.description = description
        self.industry = industry if industry in self.INDUSTRY_CATEGORIES else "Generic"
        self.categories = self.INDUSTRY_CATEGORIES[self.industry]

    async def generate_qa_for_category(
        self,
        category: str,
        intents: List[str],
        num_pairs: int = 5
    ) -> List[Dict[str, Any]]:
        """Generate Q&A pairs for a specific category."""

        prompt = f"""Generate {num_pairs} realistic support Q&A pairs for a {self.industry} product.

Product: {self.product_name}
Description: {self.description}
Category: {category}
Related intents: {', '.join(intents)}

For each Q&A pair, ensure:
1. Questions are natural, realistic user questions
2. Answers are helpful, 2-3 sentences, specific to the product
3. Variety in question phrasing (why, how, can I, where, what)
4. Realistic scenarios and edge cases

Generate as JSON array:
[
  {{"question": "...", "answer": "...", "intent": "...", "difficulty": "easy|medium|hard"}},
  ...
]

Only return the JSON array, no other text."""

        try:
            response = self.llm.invoke(prompt)
            content = response.content.strip()

            # Extract JSON
            if content.startswith("```"):
                content = content[content.find("["):content.rfind("]")+1]

            qa_pairs = json.loads(content)

            # Add metadata
            for pair in qa_pairs:
                pair['metadata'] = {
                    'category': category,
                    'intent': pair.pop('intent', 'general'),
                    'difficulty': pair.pop('difficulty', 'medium'),
                    'product': self.product_name,
                    'confidence_score': 0.85,
                    'requires_handoff': False,
                    'tags': [category.lower().replace(' ', '_'), self.industry.lower()],
                    'source_document': f'{self.product_name}_generated.json',
                    'generated_at': datetime.now().isoformat(),
                }

            logger.info(f"✓ Generated {len(qa_pairs)} pairs for {category}")
            return qa_pairs

        except Exception as e:
            logger.error(f"Failed to generate for {category}: {e}")
            return []

    async def generate_full_dataset(self, num_pairs: int = 500) -> List[Dict[str, Any]]:
        """Generate complete FAQ dataset."""
        all_pairs = []

        # Calculate pairs per category
        pairs_per_category = max(1, num_pairs // len(self.categories))

        logger.info(f"Generating {num_pairs} Q&A pairs for {self.product_name}")
        logger.info(f"  Industry: {self.industry}")
        logger.info(f"  ~{pairs_per_category} pairs per category")
        logger.info("")

        for idx, (category, intents) in enumerate(self.categories, 1):
            logger.info(f"[{idx}/{len(self.categories)}] {category}...")

            pairs = await self.generate_qa_for_category(
                category=category,
                intents=intents,
                num_pairs=pairs_per_category
            )
            all_pairs.extend(pairs)

        logger.info(f"\n✓ Generated {len(all_pairs)} total Q&A pairs")
        return all_pairs

    @staticmethod
    async def generate_from_config(config_file: str, num_pairs: int = 500) -> List[Dict[str, Any]]:
        """Generate dataset from YAML config file."""
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)

        generator = ProductCentricQAGenerator(
            product_name=config.get('product_name'),
            description=config.get('description'),
            industry=config.get('industry', 'Generic')
        )

        return await generator.generate_full_dataset(num_pairs=num_pairs)

    def save_dataset(self, qa_pairs: List[Dict[str, Any]], output_file: str) -> None:
        """Save dataset to file."""
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(qa_pairs, f, indent=2, ensure_ascii=False)
        logger.info(f"✓ Saved to {output_file}")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate synthetic FAQ from product description",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  SaaS product:
    python generate_qa_from_product.py \\
        --product-name "CloudDrive Pro" \\
        --description "Cloud storage service with AI-powered file organization" \\
        --industry "SaaS" \\
        --count 500

  E-commerce platform:
    python generate_qa_from_product.py \\
        --product-name "ShopHub" \\
        --description "All-in-one e-commerce platform for small businesses" \\
        --industry "E-commerce" \\
        --count 300

  Fintech app:
    python generate_qa_from_product.py \\
        --product-name "PayFlow" \\
        --description "Digital payment and money management app" \\
        --industry "Fintech" \\
        --count 400

Industries: SaaS, E-commerce, Fintech, Social Media, Marketplace, Generic
        """
    )

    parser.add_argument("--product-name", help="Name of the product/service")
    parser.add_argument("--description", help="Product description")
    parser.add_argument("--features", help="Comma-separated list of features")
    parser.add_argument("--industry", default="Generic",
                       choices=["SaaS", "E-commerce", "Fintech", "Social Media", "Marketplace", "Generic"],
                       help="Industry type for category templates")
    parser.add_argument("--count", type=int, default=500,
                       help="Number of Q&A pairs to generate")
    parser.add_argument("--output", required=True, help="Output file path")
    parser.add_argument("--config-file", help="YAML config file (alternative to command-line args)")

    args = parser.parse_args()

    print("\n🚀 Generating Product-Centric FAQ")

    if args.config_file:
        # Load from config
        qa_pairs = asyncio.run(
            ProductCentricQAGenerator.generate_from_config(
                config_file=args.config_file,
                num_pairs=args.count
            )
        )
    else:
        # Generate from CLI args
        if not args.product_name or not args.description:
            parser.error("Either --config-file or both --product-name and --description required")

        generator = ProductCentricQAGenerator(
            product_name=args.product_name,
            description=args.description,
            industry=args.industry
        )

        print(f"   Product: {args.product_name}")
        print(f"   Description: {args.description}")
        if args.features:
            print(f"   Features: {args.features}")
        print(f"   Industry: {args.industry}")
        print(f"   Target pairs: {args.count}\n")

        qa_pairs = asyncio.run(generator.generate_full_dataset(num_pairs=args.count))
        generator.save_dataset(qa_pairs, args.output)

    print(f"\n✨ Complete! Generated {len(qa_pairs)} Q&A pairs\n")


if __name__ == "__main__":
    main()
