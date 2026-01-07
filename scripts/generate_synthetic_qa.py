#!/usr/bin/env python3
"""
Synthetic Q&A Dataset Generator for RAG Testing

Generates realistic Q&A pairs with metadata for testing RAG pipeline at scale.
Supports generating large datasets with controlled variation and quality.

Usage:
    # Generate 1000 pairs in single file
    python generate_synthetic_qa.py --count 1000 --output datasets/qa_synthetic_1000.json

    # Generate 12 files with 100 pairs each
    python generate_synthetic_qa.py --count 100 --num-files 12 --output-dir datasets/synthetic_batch

    # Generate with specific categories
    python generate_synthetic_qa.py --count 500 --categories billing account technical --seed 42
"""

import json
import argparse
import random
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
import os


class SyntheticQAGenerator:
    """Generate synthetic but realistic Q&A pairs for RAG testing."""

    # Support categories and related intents
    CATEGORIES = {
        "Account": {
            "intents": ["reset_password", "login_help", "account_security", "profile_update", "email_change"],
            "questions": [
                "How do I reset my password?",
                "I forgot my password, what should I do?",
                "How can I reset my account password?",
                "What's the process to change my password?",
                "I can't remember my password, how do I recover it?",
                "How do I secure my account?",
                "How can I enable two-factor authentication?",
                "What are the security features available?",
                "How do I update my profile information?",
                "How can I change my email address?",
                "How do I update my account details?",
                "What information can I update in my account?",
            ],
            "answers": [
                "To reset your password, click the 'Forgot Password' link on the login page, enter your email address, and follow the instructions sent to your email. You'll receive a temporary password reset link that expires in 24 hours.",
                "You can secure your account by enabling two-factor authentication in your security settings. We also recommend using a strong, unique password and updating it regularly.",
                "To update your profile, go to Settings > Profile Information. You can change your name, profile picture, and other personal details. Click 'Save Changes' when finished.",
                "Visit Settings > Email & Contact to change your email address. You'll need to verify the new email address by clicking a confirmation link we'll send you.",
                "Account security is important to us. Enable 2FA, use a strong password, monitor login activity, and never share your credentials with anyone.",
            ]
        },
        "Billing": {
            "intents": ["invoice_help", "payment_issue", "refund_request", "subscription_help", "upgrade_plan"],
            "questions": [
                "How do I view my invoices?",
                "Where can I find my billing history?",
                "How do I update my payment method?",
                "What payment methods are accepted?",
                "Can I get a refund?",
                "How do I request a refund?",
                "What is your refund policy?",
                "How do I upgrade my subscription?",
                "How do I downgrade my plan?",
                "Can I pause my subscription?",
                "How do I cancel my subscription?",
                "Are there any hidden fees?",
                "When will I be charged?",
                "Can I change my billing cycle?",
            ],
            "answers": [
                "You can view all your invoices in Settings > Billing > Invoice History. Invoices are generated on the first day of each billing cycle and are available as PDF downloads.",
                "We accept all major credit cards (Visa, Mastercard, American Express), PayPal, and bank transfers for enterprise customers. You can update your payment method in Settings > Billing > Payment Methods.",
                "Our refund policy allows refunds within 30 days of purchase for unused services. Contact our support team with your order details to initiate a refund.",
                "To upgrade your plan, go to Settings > Subscription > Plans and select your desired plan. The upgrade takes effect immediately, and we'll prorate the charges based on your current billing cycle.",
                "You can downgrade to a lower plan from Settings > Subscription. Downgrades take effect at the end of your current billing cycle. No refund is issued for the difference.",
                "Yes, you can pause your subscription for up to 3 months from Settings > Subscription > Pause Subscription. Your data will be preserved, and you can resume anytime.",
                "To cancel, go to Settings > Subscription > Cancel Subscription. We'll provide a summary of your final charges. Your access continues until the end of your billing period.",
                "We don't charge any hidden fees. All costs are clearly displayed before checkout. Your invoice shows an itemized breakdown of all charges.",
                "Billing typically occurs on the same day each month. You'll receive an invoice via email before payment is processed.",
            ]
        },
        "Technical": {
            "intents": ["api_help", "integration_support", "error_troubleshooting", "performance_issue", "compatibility"],
            "questions": [
                "How do I use the API?",
                "Where is the API documentation?",
                "What are the API rate limits?",
                "How do I authenticate with the API?",
                "What authentication methods are supported?",
                "How do I troubleshoot API errors?",
                "Why am I getting a 401 error?",
                "What does a 429 error mean?",
                "How do I improve performance?",
                "Why is my application slow?",
                "Is there SDK support for my language?",
                "Do you support webhooks?",
                "How do I set up webhooks?",
            ],
            "answers": [
                "Our API documentation is available at docs.example.com/api. We provide REST and GraphQL endpoints with comprehensive guides and code examples for popular languages.",
                "API rate limits are 1,000 requests per minute for standard accounts and 10,000 for enterprise. Use exponential backoff when hitting limits. Premium accounts can request higher limits.",
                "Authenticate using API keys. Include your key in the Authorization header: 'Authorization: Bearer YOUR_API_KEY'. Keys can be created in Settings > API Keys.",
                "A 401 error means your API key is invalid, expired, or missing. Check that you're using the correct key and it's included in the Authorization header.",
                "A 429 error indicates rate limiting. Wait before retrying. We recommend implementing exponential backoff (2s, 4s, 8s) between retries.",
                "We provide SDKs for Python, JavaScript, Java, Go, and Ruby. Check our GitHub repository for official SDKs and community-maintained libraries.",
                "Yes, we support webhooks for real-time event notifications. Configure webhooks in Settings > Webhooks. All webhook deliveries include retry logic with exponential backoff.",
                "Performance depends on your query complexity and data size. Use caching, optimize queries, and consider upgrading to a higher-tier plan with better resources.",
            ]
        },
        "Features": {
            "intents": ["feature_tutorial", "feature_limitation", "feature_request", "feature_availability"],
            "questions": [
                "How do I export data?",
                "Can I import data from other platforms?",
                "What export formats are supported?",
                "How do I create reports?",
                "Can I schedule automated reports?",
                "What integrations are available?",
                "Can I customize the dashboard?",
                "How do I set up alerts?",
                "What's the difference between plans?",
                "Can I add team members?",
                "How do I manage permissions?",
            ],
            "answers": [
                "Export data from Settings > Data > Export. We support CSV, JSON, and Excel formats. Exports are generated within 24 hours and sent to your registered email.",
                "Yes, we support importing from CSV, JSON, and direct API connections. Use the Import Wizard in Settings > Data > Import to get started.",
                "You can create custom reports from the Reports section. Select metrics, time periods, and visualization types. Reports can be scheduled daily, weekly, or monthly.",
                "Integrations are available for Slack, Zapier, Salesforce, HubSpot, and more. Connect integrations in Settings > Integrations using OAuth or API keys.",
                "Yes, you can fully customize your dashboard. Add, remove, and rearrange widgets. Click 'Customize' on your dashboard to enter edit mode.",
                "Alerts notify you of important events via email or Slack. Configure alert rules in Settings > Alerts. You can set thresholds for various metrics.",
                "Team members can be added in Settings > Team. Assign roles (Admin, Editor, Viewer) to control permissions. Enterprise plans support advanced permission management.",
            ]
        },
        "Getting Started": {
            "intents": ["onboarding_help", "first_steps", "setup_guide", "documentation"],
            "questions": [
                "How do I get started?",
                "Is there a tutorial for new users?",
                "How do I set up my first project?",
                "What are the system requirements?",
                "Where can I find documentation?",
                "Are there video tutorials?",
                "Is there a free trial available?",
                "How long is the trial period?",
                "How do I contact support?",
                "What's your support response time?",
            ],
            "answers": [
                "Welcome! Start with our Getting Started guide at example.com/docs/getting-started. It covers account creation, project setup, and key features.",
                "Yes, we have interactive tutorials in the app. On your first login, you'll be guided through creating your first project. You can replay tutorials anytime from Help > Tutorials.",
                "Create a project from your dashboard. Click 'New Project', enter a name and description, select your industry, and configure your preferences.",
                "Our service works on any modern browser (Chrome, Firefox, Safari, Edge). No software installation required. Check docs for API client requirements.",
                "Full documentation is at docs.example.com, including API reference, tutorials, FAQs, and best practices guides.",
                "Yes! Check our YouTube channel for video tutorials, webinars, and product updates. Subscribe for the latest content.",
                "Yes, we offer a free trial with full feature access for 14 days. No credit card required to sign up.",
                "Our free trial lasts 14 days. You'll have access to all features. Before your trial ends, you can upgrade to a paid plan to continue using your projects.",
                "Contact us through the Help > Contact Support section in your dashboard. You can also email support@example.com or chat with us during business hours.",
                "We aim to respond to all support requests within 2 business hours during business hours (Mon-Fri, 9AM-6PM UTC). Premium support includes 1-hour response times.",
            ]
        }
    }

    CLARIFYING_QUESTIONS_TEMPLATES = {
        "reset_password": [
            "Do you have access to the email associated with your account?",
            "Are you trying to reset your password on the web app or mobile?",
        ],
        "login_help": [
            "Are you seeing any specific error messages?",
            "Have you recently changed your password?",
        ],
        "payment_issue": [
            "What error message did you receive?",
            "Which payment method did you try?",
        ],
        "api_help": [
            "Which programming language are you using?",
            "Are you using REST or GraphQL?",
        ],
        "export_data": [
            "What format would you like for export?",
            "How much data are you planning to export?",
        ],
    }

    def __init__(self, seed: int = None):
        """Initialize generator with optional random seed."""
        if seed is not None:
            random.seed(seed)

    def generate_qa_pair(self, category: str, index: int) -> Dict[str, Any]:
        """Generate a single Q&A pair with metadata."""
        if category not in self.CATEGORIES:
            raise ValueError(f"Invalid category: {category}")

        cat_data = self.CATEGORIES[category]

        # Select random question, answer, and intent
        question = random.choice(cat_data["questions"])
        answer = random.choice(cat_data["answers"])
        intent = random.choice(cat_data["intents"])

        # Add variation to question (paraphrase with slight changes)
        question = self._add_question_variation(question, index)

        # Get clarifying questions for this intent
        clarifying = self.CLARIFYING_QUESTIONS_TEMPLATES.get(intent, [])
        clarifying_questions = random.sample(clarifying, min(2, len(clarifying))) if clarifying else []

        return {
            "question": question,
            "answer": answer,
            "metadata": {
                "category": category,
                "intent": intent,
                "requires_handoff": random.choice([False, False, False, True]),  # 25% need handoff
                "confidence_threshold": round(random.uniform(0.7, 0.95), 2),
                "clarifying_questions": clarifying_questions,
            }
        }

    def _add_question_variation(self, question: str, index: int) -> str:
        """Add slight variations to questions for more realistic datasets."""
        variations = [
            lambda q: q,  # Keep original
            lambda q: q.replace("How do I", "What's the way to"),
            lambda q: q.replace("How do I", "Can you help me"),
            lambda q: q.replace("?", " please?"),
            lambda q: f"I need help with: {q[0].lower() + q[1:]}",
            lambda q: q.replace("How can I", "What's the process to"),
            lambda q: f"{q[:-1]} exactly?",
        ]

        variation = variations[index % len(variations)]
        return variation(question)

    def _generate_tags(self) -> List[str]:
        """Generate random tags for Q&A pair."""
        all_tags = [
            "common_question", "user_reported", "high_traffic",
            "seasonal", "urgent", "faq", "documented",
            "beta_feature", "enterprise_only", "api_related"
        ]
        return random.sample(all_tags, random.randint(1, 3))

    def generate_dataset(
        self,
        count: int = 1000,
        categories: List[str] = None
    ) -> List[Dict[str, Any]]:
        """Generate complete Q&A dataset."""
        if categories is None:
            categories = list(self.CATEGORIES.keys())
        else:
            # Validate categories
            invalid = set(categories) - set(self.CATEGORIES.keys())
            if invalid:
                raise ValueError(f"Invalid categories: {invalid}")

        dataset = []
        for i in range(count):
            category = random.choice(categories)
            qa_pair = self.generate_qa_pair(category, i)
            dataset.append(qa_pair)

        return dataset

    def save_dataset(self, dataset: List[Dict[str, Any]], filepath: str):
        """Save dataset to JSON file."""
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(dataset, f, indent=2, ensure_ascii=False)

        print(f"✓ Saved {len(dataset)} Q&A pairs to {filepath}")

    def generate_evaluation_dataset(
        self,
        qa_dataset: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate evaluation/ground-truth dataset with expected answers and chunks."""
        evaluation = []

        for qa in qa_dataset:
            eval_entry = {
                "question": qa["question"],
                "expected_chunks": [qa["answer"]],
                "expected_answer": qa["answer"][:200] + "..." if len(qa["answer"]) > 200 else qa["answer"],
                "expected_intent": qa["metadata"]["intent"],
                "expected_category": qa["metadata"]["category"],
                "expected_action": "auto_reply" if not qa["metadata"]["requires_handoff"] else "handoff",
                "confidence_score": qa["metadata"]["confidence_threshold"],
                "difficulty": self._estimate_difficulty(qa["question"]),
            }
            evaluation.append(eval_entry)

        return evaluation

    def _estimate_difficulty(self, question: str) -> str:
        """Estimate question difficulty based on length and complexity."""
        words = len(question.split())
        if words < 5:
            return "easy"
        elif words < 15:
            return "medium"
        else:
            return "hard"


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate synthetic Q&A datasets for RAG testing"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=100,
        help="Number of Q&A pairs per file (default: 100)"
    )
    parser.add_argument(
        "--num-files",
        type=int,
        default=1,
        help="Number of files to generate (default: 1)"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output file path (used when num-files=1)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="datasets/synthetic",
        help="Output directory for multiple files (default: datasets/synthetic)"
    )
    parser.add_argument(
        "--categories",
        nargs="+",
        default=None,
        help="Categories to include (default: all). Options: Account, Billing, Technical, Features, Getting Started"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility"
    )
    parser.add_argument(
        "--include-eval",
        action="store_true",
        help="Generate evaluation dataset alongside main dataset"
    )

    args = parser.parse_args()

    # Initialize generator
    generator = SyntheticQAGenerator(seed=args.seed)

    print(f"🚀 Generating synthetic Q&A dataset")
    print(f"   Categories: {args.categories or 'all'}")
    print(f"   Total pairs: {args.count * args.num_files}")
    print()

    if args.num_files == 1 and args.output:
        # Single file output
        dataset = generator.generate_dataset(args.count, args.categories)
        generator.save_dataset(dataset, args.output)

        if args.include_eval:
            eval_dataset = generator.generate_evaluation_dataset(dataset)
            eval_path = args.output.replace(".json", "_eval.json")
            generator.save_dataset(eval_dataset, eval_path)
            print(f"✓ Saved {len(eval_dataset)} evaluation entries to {eval_path}")
    else:
        # Multiple files output
        Path(args.output_dir).mkdir(parents=True, exist_ok=True)

        for file_num in range(args.num_files):
            dataset = generator.generate_dataset(args.count, args.categories)
            filename = f"qa_synthetic_batch_{file_num + 1:03d}_{args.count}_pairs.json"
            filepath = os.path.join(args.output_dir, filename)
            generator.save_dataset(dataset, filepath)

            if args.include_eval:
                eval_dataset = generator.generate_evaluation_dataset(dataset)
                eval_filename = filename.replace(".json", "_eval.json")
                eval_filepath = os.path.join(args.output_dir, eval_filename)
                generator.save_dataset(eval_dataset, eval_filepath)

    print()
    print("✨ Dataset generation complete!")


if __name__ == "__main__":
    main()
