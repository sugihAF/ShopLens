# ShopLens Implementation Fix Plan

## Context
ShopLens is an AI-powered product review intelligence platform that helps users make purchasing decisions. The system should:
1. Gather product reviews from YouTube and tech blogs when user asks about a product
2. Store scraped data in the database to avoid re-scraping
3. Answer questions based ONLY on scraped data (no AI hallucination)
4. Suggest where to buy products from marketplaces (Amazon, eBay)
5. **ALL AI functionality MUST go through function calls** - never use LLM's knowledge base

**Current State**: Basic infrastructure exists but critical flows are broken or incomplete.

---

## Key Principles
- **Function Call Only** - Every AI action must be a tool call, never direct LLM response from knowledge
- **Database First** - Check database before scraping to avoid duplicate work and reduce costs
- **No Hallucination** - AI must only cite data from scraped reviews, never make up information
- **Source Attribution** - Always show which reviewer/source said what
- **Async First** - All operations use `async def` with proper async database calls

---

## Implementation Checklist

### Phase 1: Core Function Fixes - Auto-Scrape Flow (CRITICAL)

The current system only searches the database. When a product isn't found, it should automatically scrape reviews.

- [ ] Add `gather_product_reviews` function
  - This is the MAIN function called when user asks about a product
  - Flow: Check DB -> If not found, search YouTube + blogs -> Scrape top results -> Return data
  - Parameters: `product_name: str, force_refresh: bool = False`
  - Returns: Product info with review summaries from scraped sources
  ```python
  # Pseudo-code flow:
  1. Search database for product
  2. If found AND has reviews AND not force_refresh:
     - Return existing data (cost-free)
  3. If not found OR force_refresh:
     - Call search_youtube_reviews(product_name) -> get top 3-5 URLs
     - Call search_blog_reviews(product_name) -> get top 3-5 URLs
     - Ingest each URL (in parallel if possible)
     - Return aggregated review data
  ```

- [ ] Add `search_youtube_reviews` function
  - Uses Gemini with Google Search grounding to find YouTube review URLs
  - Parameters: `product_name: str, limit: int = 5`
  - Returns: List of YouTube URLs for tech reviews
  - Filter for reputable tech channels (MKBHD, Linus, Dave2D, etc.)

- [ ] Add `search_blog_reviews` function
  - Uses Firecrawl's search/map feature OR Gemini search grounding
  - Parameters: `product_name: str, limit: int = 5`
  - Returns: List of blog URLs from reputable tech sites (The Verge, Tom's Guide, etc.)

- [ ] Fix `search_products` to trigger auto-scrape
  - Current: Only searches database
  - Fix: If no results found, offer to gather reviews automatically
  - Return message: "No data found for {product}. Would you like me to search for reviews?"

### Phase 2: Marketplace Integration (CRITICAL)

Current `find_marketplace_listings` only reads from database - needs actual scraping.

- [ ] Add `scrape_marketplace_listings` function
  - Uses Firecrawl to scrape Amazon/eBay search results
  - Parameters: `product_name: str, marketplaces: list[str] = ["amazon", "ebay"]`
  - Returns: List of listings with:
    - `title`, `price`, `url`, `seller_name`, `seller_rating`, `review_count`, `availability`
  - Save results to `MarketplaceListing` table

- [ ] Fix `find_marketplace_listings` to scrape if empty
  - Current: Returns "No listings found" when DB is empty
  - Fix: Trigger scrape when no listings exist, then return results
  ```python
  # Flow:
  1. Query DB for existing listings
  2. If empty OR stale (last_checked > 24h):
     - Call scrape_marketplace_listings()
     - Store results in DB
  3. Return listings sorted by: best_seller, best_reviewed, cheapest
  ```

- [ ] Update `MarketplaceListing` model
  - Add `seller_name: str`
  - Add `seller_rating: float`
  - Add `review_count: int`
  - Add `is_best_seller: bool`
  - Ensure `last_checked_at` is used for cache invalidation

- [ ] Implement marketplace scraping service
  - File: `services/marketplace_scraper.py`
  - Use Firecrawl to scrape Amazon search: `site:amazon.com {product_name}`
  - Use Firecrawl to scrape eBay search: `site:ebay.com {product_name}`
  - Parse results using Gemini for structured extraction

### Phase 3: System Prompt & Function Call Enforcement

- [ ] Update `SYSTEM_PROMPT` in `chat_service.py`
  - Add strict instruction: "NEVER answer product questions from your training data"
  - Add: "ALWAYS call a function when user asks about products, reviews, or purchases"
  - Add: "If you don't have data, say so - never make up information"
  ```python
  SYSTEM_PROMPT = """You are ShopLens, an AI assistant that helps users research products.

  CRITICAL RULES:
  1. NEVER answer product questions from your training data - ALWAYS use function calls
  2. When user asks about a product, call gather_product_reviews() FIRST
  3. Only provide information that comes from function call results
  4. Always cite the source (reviewer name, channel) for every claim
  5. If no data is available, honestly say "I don't have review data for this product yet"
  6. When user asks where to buy, call find_marketplace_listings()

  ## Available Actions:
  - gather_product_reviews: Search and collect reviews for a product
  - search_products: Find products in our database
  - get_product_reviews: Get existing reviews for a known product
  - find_marketplace_listings: Find where to buy with prices
  - compare_products: Compare multiple products side-by-side

  ## Response Guidelines:
  - Cite sources: "According to MKBHD..." or "The Verge's review mentions..."
  - Be objective: Present multiple viewpoints
  - Use bullet points for pros/cons
  - Include ratings when available
  """
  ```

- [ ] Add function call validation in `process_message()`
  - Log warning if AI responds without any function calls for product queries
  - Track function call rate for monitoring

### Phase 4: Review Ingestion Improvements

- [ ] Fix YouTube scraper to handle rate limits
  - Add retry logic with exponential backoff
  - Add rate limiting (max 10 requests/minute to Gemini)

- [ ] Improve blog scraper reliability
  - Handle Firecrawl errors gracefully
  - Add fallback: If Firecrawl fails, try Gemini with Google Search grounding

- [ ] Add batch ingestion support
  - Allow ingesting multiple URLs in parallel
  - Use `asyncio.gather()` with error handling

- [ ] Add review quality scoring
  - Score based on: content length, opinion count, has ratings
  - Prefer higher-quality reviews for consensus

### Phase 5: Data Caching & Freshness

- [ ] Add cache check to all scraping functions
  ```python
  async def should_refresh_data(product_id: int, max_age_hours: int = 168) -> bool:
      """Check if product data is stale (default: 1 week)"""
      product = await product_crud.get(db, id=product_id)
      if not product or not product.updated_at:
          return True
      age = datetime.utcnow() - product.updated_at
      return age.total_seconds() > max_age_hours * 3600
  ```

- [ ] Add `force_refresh` parameter to key functions
  - `gather_product_reviews(product_name, force_refresh=False)`
  - `find_marketplace_listings(product_id, force_refresh=False)`

- [ ] Implement cache invalidation
  - Marketplace prices: Refresh if > 24 hours old
  - Reviews: Refresh if > 7 days old
  - Product specs: Refresh if > 30 days old

### Phase 6: Answer Quality & Source Attribution

- [ ] Fix `_extract_sources()` in `chat_service.py`
  - Currently returns empty list
  - Should extract reviewer names and URLs from function results
  - Format: `{"reviewer": "MKBHD", "platform": "YouTube", "url": "..."}`

- [ ] Add opinion aggregation for answers
  - When answering about a product aspect, aggregate opinions from multiple reviewers
  - Show agreement/disagreement: "3 out of 4 reviewers agree the camera is excellent"

- [ ] Implement consensus calculation
  - Fix `consensus_crud.calculate_consensus()` to actually compute consensus
  - Run after new reviews are ingested
  - Store in `Consensus` table

### Phase 7: New Function Declarations

Add these to `FUNCTION_DECLARATIONS` in `registry.py`:

- [ ] `gather_product_reviews`
  ```python
  {
      "name": "gather_product_reviews",
      "description": "Search for and collect product reviews from YouTube and tech blogs. Use this when a user asks about a product and we need to gather review data. This will search for reviews, scrape them, and store them in our database.",
      "parameters": {
          "type": "object",
          "properties": {
              "product_name": {
                  "type": "string",
                  "description": "The product name to search reviews for (e.g., 'iPhone 15 Pro', 'Samsung Galaxy S24')"
              },
              "force_refresh": {
                  "type": "boolean",
                  "description": "If true, fetch new reviews even if we have existing data"
              }
          },
          "required": ["product_name"]
      }
  }
  ```

- [ ] `search_youtube_reviews`
  ```python
  {
      "name": "search_youtube_reviews",
      "description": "Search YouTube for product review videos. Returns URLs of relevant tech review videos.",
      "parameters": {
          "type": "object",
          "properties": {
              "product_name": {"type": "string", "description": "Product to search for"},
              "limit": {"type": "integer", "description": "Max results (default 5)"}
          },
          "required": ["product_name"]
      }
  }
  ```

- [ ] `search_blog_reviews`
  ```python
  {
      "name": "search_blog_reviews",
      "description": "Search for tech blog reviews of a product. Returns URLs from reputable tech sites.",
      "parameters": {
          "type": "object",
          "properties": {
              "product_name": {"type": "string", "description": "Product to search for"},
              "limit": {"type": "integer", "description": "Max results (default 5)"}
          },
          "required": ["product_name"]
      }
  }
  ```

- [ ] `scrape_marketplace_listings`
  ```python
  {
      "name": "scrape_marketplace_listings",
      "description": "Scrape current prices and availability from Amazon and eBay. Use when user asks where to buy a product.",
      "parameters": {
          "type": "object",
          "properties": {
              "product_name": {"type": "string", "description": "Product to search for"},
              "marketplaces": {
                  "type": "array",
                  "items": {"type": "string"},
                  "description": "Marketplaces to search (amazon, ebay)"
              }
          },
          "required": ["product_name"]
      }
  }
  ```

---

## Files to Create/Modify

| File | Action | Changes |
|------|--------|---------|
| `functions/registry.py` | Modify | Add 4 new function declarations |
| `functions/gather.py` | Create | Implement `gather_product_reviews`, `search_youtube_reviews`, `search_blog_reviews` |
| `functions/marketplace.py` | Modify | Add `scrape_marketplace_listings`, fix `find_marketplace_listings` |
| `services/marketplace_scraper.py` | Create | Firecrawl-based marketplace scraping |
| `services/youtube_scraper.py` | Modify | Add `search_for_reviews()` method |
| `services/firecrawl_service.py` | Modify | Add `search_blog_reviews()` method |
| `services/chat_service.py` | Modify | Update system prompt, fix source extraction |
| `crud/consensus.py` | Modify | Implement `calculate_consensus()` |
| `models/marketplace.py` | Modify | Add seller fields |

---

## Testing Checklist

### Unit Tests
- [ ] Test `gather_product_reviews` with new product (triggers scrape)
- [ ] Test `gather_product_reviews` with existing product (uses cache)
- [ ] Test `search_youtube_reviews` returns valid YouTube URLs
- [ ] Test `search_blog_reviews` returns valid blog URLs
- [ ] Test `scrape_marketplace_listings` extracts correct data
- [ ] Test cache invalidation logic

### Integration Tests
- [ ] Full flow: User asks about iPhone 15 -> Reviews scraped -> Answer provided
- [ ] Full flow: User asks where to buy -> Marketplace scraped -> Listings shown
- [ ] Test that AI never answers from training data (mock function to fail and verify no answer)

### Manual Testing Flow
```
1. User: "Tell me about the Sony WH-1000XM5"
   Expected: AI calls gather_product_reviews() -> scrapes YouTube/blogs -> returns summary

2. User: "What do reviewers say about the battery?"
   Expected: AI uses stored review data, cites specific reviewers

3. User: "Where can I buy this?"
   Expected: AI calls find_marketplace_listings() -> scrapes Amazon/eBay -> shows prices

4. User: "Compare it to AirPods Max"
   Expected: AI gathers reviews for AirPods Max if needed, then compares
```

---

## Critical Bugs to Fix

### Bug 1: No Auto-Scrape on Product Query
- **Current**: `search_products` only searches DB, returns "not found" if empty
- **Expected**: Should trigger review gathering when product not found
- **Impact**: Core feature broken - users get no data for new products

### Bug 2: Marketplace Returns Empty
- **Current**: `find_marketplace_listings` only reads DB (always empty initially)
- **Expected**: Should scrape Amazon/eBay when no data exists
- **Impact**: "Where to buy" feature completely non-functional

### Bug 3: AI Can Hallucinate
- **Current**: System prompt doesn't strongly enforce function-call-only behavior
- **Expected**: AI should NEVER answer product questions from training data
- **Impact**: Users may get inaccurate information not from actual reviews

### Bug 4: Sources Not Extracted
- **Current**: `_extract_sources()` returns empty list
- **Expected**: Should show which reviewers/sources provided the information
- **Impact**: No source attribution, users can't verify claims

### Bug 5: Consensus Not Calculated
- **Current**: `Consensus` table exists but never populated
- **Expected**: Should aggregate opinions after reviews are ingested
- **Impact**: "What do reviewers agree on" feature doesn't work

---

## Implementation Priority

### Priority 1 (Must Have - Core Flow)
1. `gather_product_reviews` function (enables main feature)
2. `scrape_marketplace_listings` function (enables purchase feature)
3. System prompt fix (prevents hallucination)

### Priority 2 (Should Have - Quality)
4. Source extraction fix
5. Consensus calculation
6. Cache invalidation

### Priority 3 (Nice to Have - Polish)
7. Batch ingestion
8. Quality scoring
9. Error handling improvements

---

## Commands for Testing

All commands run from: `D:\Codes\ShopLens`

```bash
# Start development stack
docker-compose -f docker-compose.dev.yml up --build

# Run tests
cd app/api
pytest tests/ -v

# Run specific test file
pytest tests/test_functions.py -v

# Check logs
docker-compose -f docker-compose.dev.yml logs -f api
```

---

## Status Reporting

After each implementation session, update:

```
---SHOPLENS_STATUS---
STATUS: IN_PROGRESS | COMPLETE | BLOCKED
PHASE: 1 | 2 | 3 | 4 | 5 | 6 | 7
FEATURES_WORKING: <number>/10
TESTS_STATUS: PASSING | FAILING | NOT_RUN
RECOMMENDATION: <one line summary>
---END_STATUS---
```

### Exit Criteria
Set STATUS to COMPLETE when:
1. User can ask about any product and get real review data
2. User can ask where to buy and get real marketplace listings
3. AI never answers from training data (verified by testing)
4. All sources are properly attributed
5. Tests pass

---

## API Cost Considerations

### Per-Request Costs
- YouTube scrape: ~1 Gemini API call
- Blog scrape: 1 Firecrawl call + 1 Gemini call
- Marketplace scrape: 2 Firecrawl calls + 1 Gemini call
- Chat response: 1+ Gemini calls

### Cost Reduction Strategies
- **Cache aggressively**: Check DB before any scrape
- **Batch operations**: Scrape multiple URLs in one session
- **Limit results**: Default to 3-5 reviews, not 10+
- **TTL on marketplace**: Prices change daily, reviews don't

---

## Architecture Diagram

```
User Message
    ↓
ChatService.process_message()
    ↓
Gemini with Function Declarations
    ↓
[Function Call Decision]
    ├── gather_product_reviews()
    │       ├── Check DB (cache)
    │       ├── search_youtube_reviews() → ingest_youtube_review()
    │       └── search_blog_reviews() → ingest_blog_review()
    │       ↓
    │   Store in: Product, Review, Opinion, Reviewer
    │
    ├── find_marketplace_listings()
    │       ├── Check DB (cache)
    │       └── scrape_marketplace_listings()
    │       ↓
    │   Store in: MarketplaceListing
    │
    └── [Other functions: compare, search, get_details]
    ↓
Function Result → Gemini
    ↓
Text Response (citing sources)
    ↓
User
```
