# Product-Based FAQ Generation Guide

Complete guide to generating synthetic, realistic FAQ datasets from scratch for ANY product/service without existing documentation.

## Quick Start: Three Simple Steps

### Step 1: Set Your OpenAI API Key
```bash
export OPENAI_API_KEY="sk-..."
```

### Step 2: Run Generator
```bash
python scripts/generate_qa_from_product.py \
    --product-name "YourProduct" \
    --description "Your product description" \
    --industry "SaaS" \
    --count 500 \
    --output datasets/qa_your_product.json
```

### Step 3: Use Generated FAQ
```bash
# Ingest into your RAG
python scripts/ingest.py --file datasets/qa_your_product.json

# Test retrieval
python evaluate_retrieval.py --qa-file datasets/qa_your_product.json
```

## Supported Industries

### 1. **SaaS** (Software as a Service)
Products: Cloud storage, project management, CRM, analytics platforms, etc.

**Auto-Generated Categories:**
- Getting Started (onboarding, installation, setup, trial, free tier)
- Account & Auth (password, login, security, profile, email)
- Features & Usage (tutorials, best practices, limitations)
- Plans & Pricing (pricing, upgrade, subscription, refund)
- Integration (API, webhooks, third-party apps)
- Technical Support (errors, performance, bugs)

**Example:**
```bash
python scripts/generate_qa_from_product.py \
    --product-name "CloudDrive Pro" \
    --description "Enterprise cloud storage platform with real-time collaboration, version control, and AI-powered file organization" \
    --industry "SaaS" \
    --count 500 \
    --output datasets/qa_clouddrive.json
```

### 2. **E-commerce**
Products: Online stores, marketplaces, shopping platforms, etc.

**Auto-Generated Categories:**
- Shopping (browsing, search, filters, wishlists)
- Orders (placing orders, payment, modification)
- Shipping & Delivery (methods, tracking, costs)
- Returns & Refunds (return process, damaged items)
- Account (registration, profile, addresses)
- Promotions (coupons, discounts, loyalty)

**Example:**
```bash
python scripts/generate_qa_from_product.py \
    --product-name "ShopHub" \
    --description "All-in-one e-commerce platform for small businesses with inventory management, payment processing, and shipping integration" \
    --industry "E-commerce" \
    --count 300 \
    --output datasets/qa_shophub.json
```

### 3. **Fintech** (Financial Technology)
Products: Payment apps, investment platforms, digital banks, etc.

**Auto-Generated Categories:**
- Account Setup (registration, verification, KYC)
- Banking (transfers, deposits, withdrawals)
- Investing (trading, portfolio, diversification)
- Security (authentication, fraud protection, privacy)
- Cards & Payments (card ordering, payment limits)
- Technical (app issues, sync, performance)

**Example:**
```bash
python scripts/generate_qa_from_product.py \
    --product-name "PayFlow" \
    --description "Digital payment and personal finance management application with budgeting, investing, and peer-to-peer transfers" \
    --industry "Fintech" \
    --count 400 \
    --output datasets/qa_payflow.json
```

### 4. **Social Media**
Products: Social networks, community platforms, content sharing apps, etc.

**Auto-Generated Categories:**
- Getting Started (account creation, profile setup, mobile app)
- Content (posting, editing, privacy, scheduling)
- Engagement (comments, likes, sharing, messaging)
- Features (stories, live streaming, groups)
- Community Guidelines (rules, moderation, reporting)
- Technical (bugs, performance, sync issues)

**Example:**
```bash
python scripts/generate_qa_from_product.py \
    --product-name "CommunityHub" \
    --description "Social platform for niche communities with content sharing, live streaming, and group messaging" \
    --industry "Social Media" \
    --count 600 \
    --output datasets/qa_community.json
```

### 5. **Marketplace**
Products: Peer-to-peer platforms, seller networks, auction sites, etc.

**Auto-Generated Categories:**
- Selling (listing, pricing, inventory, shipping)
- Buying (browsing, purchase, payment, returns)
- Account (registration, verification, payout, tax)
- Communication (messaging, ratings, feedback)
- Technical (app features, API, automation)
- Policies (terms, fees, prohibited items, disputes)

**Example:**
```bash
python scripts/generate_qa_from_product.py \
    --product-name "CraftMarket" \
    --description "Peer-to-peer marketplace for handmade and artisan goods with dispute resolution and seller support" \
    --industry "Marketplace" \
    --count 400 \
    --output datasets/qa_craftmarket.json
```

### 6. **Generic**
For products that don't fit above categories.

**Auto-Generated Categories:**
- Getting Started (registration, setup, tutorial)
- Account (profile, settings, security)
- Features (how-to, usage, best practices)
- Support (contact, help, feedback)
- Billing (pricing, payment, invoices)
- Technical (errors, performance, API)

---

## Command Reference

### Basic Usage
```bash
python scripts/generate_qa_from_product.py \
    --product-name "ProductName" \
    --description "Product description" \
    --industry "SaaS|E-commerce|Fintech|Social Media|Marketplace|Generic" \
    --count 500 \
    --output datasets/qa_output.json
```

### With Features List
```bash
python scripts/generate_qa_from_product.py \
    --product-name "MyApp" \
    --description "My awesome product" \
    --features "feature1,feature2,feature3" \
    --industry "SaaS" \
    --count 300 \
    --output datasets/qa_myapp.json
```

### Using YAML Config File
```bash
python scripts/generate_qa_from_product.py \
    --config-file config/my_product_config.yaml \
    --count 1000 \
    --output datasets/qa_from_config.json
```

---

## YAML Config Format

Create a `product_config.yaml`:

```yaml
product_name: "CloudDrive Pro"
description: "Enterprise cloud storage platform with real-time collaboration, version control, and AI-powered file organization"
industry: "SaaS"
features:
  - File synchronization
  - Real-time collaboration
  - Version history
  - Advanced search
  - API access
  - Mobile apps
  - End-to-end encryption
```

Then run:
```bash
python scripts/generate_qa_from_product.py \
    --config-file product_config.yaml \
    --count 500 \
    --output datasets/qa_generated.json
```

---

## Output Format

Generated Q&A pairs include comprehensive metadata:

```json
{
  "question": "How do I share files with my team in real-time?",
  "answer": "In CloudDrive Pro, you can share folders or individual files by right-clicking and selecting 'Share'. Enter your team member's email, set permissions (view/edit), and they'll get instant access with real-time sync enabled.",
  "metadata": {
    "category": "Features & Usage",
    "intent": "feature_tutorial",
    "difficulty": "easy",
    "product": "CloudDrive Pro",
    "confidence_score": 0.85,
    "requires_handoff": false,
    "tags": ["features_usage", "saas"],
    "source_document": "CloudDrive Pro_generated.json",
    "generated_at": "2026-01-07T12:27:06.802358"
  }
}
```

---

## Generation Strategy & Quality

### How Generation Works

1. **Category Selection**: Based on industry type, generator selects relevant Q&A categories
2. **Prompt Engineering**: For each category, LLM generates realistic Q&A pairs
3. **Variation**: Questions are phrased naturally (why, how, can I, where, what)
4. **Metadata**: Automatically classifies difficulty and tags

### Quality Tips

**For Better Results:**
1. **Be specific in description**: More details → better Q&A
   - ❌ Bad: "Cloud storage app"
   - ✅ Good: "Enterprise cloud storage with real-time collaboration, version control, and advanced sharing controls"

2. **List key features**: Helps generate relevant FAQs
   ```bash
   --features "file_sync,collaboration,version_history,sharing,encryption"
   ```

3. **Choose correct industry**: Determines category templates
   - SaaS for tools and platforms
   - E-commerce for shopping
   - Fintech for payments and banking
   - Marketplace for peer-to-peer platforms

4. **Start with reasonable count**:
   - 100-300: Quick testing
   - 300-800: Production datasets
   - 1000+: Comprehensive evaluation

---

## Workflow Examples

### Example 1: New SaaS Product
```bash
# 1. Generate initial FAQ (300 pairs)
python scripts/generate_qa_from_product.py \
    --product-name "DataViz" \
    --description "Real-time data visualization platform for business analytics with interactive dashboards" \
    --industry "SaaS" \
    --count 300 \
    --output datasets/qa_dataviz_300.json

# 2. Ingest into vector store
python scripts/ingest.py --file datasets/qa_dataviz_300.json

# 3. Test RAG quality
python evaluate_retrieval.py --qa-file datasets/qa_dataviz_300.json

# 4. If quality is good, generate more (600 total)
python scripts/generate_qa_from_product.py \
    --product-name "DataViz" \
    --description "Real-time data visualization platform for business analytics with interactive dashboards" \
    --industry "SaaS" \
    --count 600 \
    --output datasets/qa_dataviz_600.json
```

### Example 2: E-commerce Platform
```bash
# Generate comprehensive FAQ for online store
python scripts/generate_qa_from_product.py \
    --product-name "ShopHub" \
    --description "All-in-one e-commerce platform with inventory, payments, shipping integration, and customer analytics" \
    --industry "E-commerce" \
    --features "inventory,payments,shipping,analytics,marketing" \
    --count 500 \
    --output datasets/qa_shophub_500.json

# Ingest and test
python scripts/ingest.py --file datasets/qa_shophub_500.json
python evaluate_retrieval.py --qa-file datasets/qa_shophub_500.json
```

### Example 3: Multiple Datasets for Comparison
```bash
# Generate 3 different scales to measure RAG scalability
python scripts/generate_qa_from_product.py \
    --product-name "MyApp" \
    --description "My product" \
    --industry "SaaS" \
    --count 100 \
    --output datasets/qa_myapp_100.json

python scripts/generate_qa_from_product.py \
    --product-name "MyApp" \
    --description "My product" \
    --industry "SaaS" \
    --count 500 \
    --output datasets/qa_myapp_500.json

python scripts/generate_qa_from_product.py \
    --product-name "MyApp" \
    --description "My product" \
    --industry "SaaS" \
    --count 1000 \
    --output datasets/qa_myapp_1000.json

# Compare metrics across scales
echo "Testing scalability..."
for file in datasets/qa_myapp_*.json; do
    echo "Testing $file..."
    python evaluate_retrieval.py --qa-file "$file"
done
```

---

## Cost & Time Estimates

| Scale | Categories | Approx. Time | API Cost |
|-------|-----------|-------------|----------|
| 100 pairs | 4-5 | 2-3 min | $0.05 |
| 300 pairs | 6 | 5-8 min | $0.15 |
| 500 pairs | 6 | 8-12 min | $0.25 |
| 1000 pairs | 6 | 15-25 min | $0.50 |

**Note:** Times vary based on OpenAI API latency. First run may be slower.

---

## Customizing Categories

If you want custom categories for your product, you can modify the `INDUSTRY_CATEGORIES` dict in `scripts/generate_qa_from_product.py`:

```python
INDUSTRY_CATEGORIES = {
    "MyIndustry": [
        ("Custom Category 1", ["intent1", "intent2", "intent3"]),
        ("Custom Category 2", ["intent4", "intent5"]),
        ...
    ]
}
```

Then use:
```bash
python scripts/generate_qa_from_product.py \
    --product-name "MyProduct" \
    --description "Description" \
    --industry "MyIndustry" \
    --count 500 \
    --output datasets/qa_custom.json
```

---

## Combining with Other Generators

You can mix datasets from different generators:

```python
import json

# Load from template generator
with open("datasets/qa_synthetic_100.json") as f:
    template_qa = json.load(f)

# Load from product generator
with open("datasets/qa_myproduct_300.json") as f:
    product_qa = json.load(f)

# Combine
combined = template_qa + product_qa

with open("datasets/qa_combined_400.json", "w") as f:
    json.dump(combined, f)

# Ingest combined dataset
# python scripts/ingest.py --file datasets/qa_combined_400.json
```

---

## Troubleshooting

### "OPENAI_API_KEY not set"
```bash
export OPENAI_API_KEY="sk-..."
```

### "Request timeout / Rate limit"
- Try smaller count first (100-200 pairs)
- Wait 30 seconds and retry
- Use better API key tier if available

### "Quality of generated questions is poor"
- Make your product description more detailed
- Include specific features
- Try smaller count first to check quality
- Review and manually curate if needed

### "Generation takes too long"
- Start with smaller count (100-200)
- Increase gradually to larger batches
- Consider using template-based generator for quick testing

---

## Next Steps

1. **Describe your product**: Write clear description and features
2. **Generate initial FAQ**: Start with 300-500 pairs
3. **Ingest into RAG**: Test with your pipeline
4. **Measure quality**: Use Ragas evaluation
5. **Iterate**: Adjust description or count based on results
6. **Scale up**: Generate larger datasets when satisfied

See other guides for ingestion, evaluation, and RAG testing best practices.
