# ShopLens Fix Plan

## Exit Criteria (MUST ALL BE TRUE TO SET EXIT_SIGNAL: true)
- [ ] All Phase 1-7 tasks marked complete
- [ ] Each function tool tested and returns expected results
- [ ] Full user flow works: Ask product -> Get reviews -> Ask where to buy -> Get listings
- [ ] AI never responds from training data (only from function call results)
- [ ] All tests pass with `pytest tests/ -v`
- [ ] Manual flow test documented with actual output

---

## Phase 1: Core Function - Auto-Scrape Flow (HIGH PRIORITY)

### 1.1 Create `gather_product_reviews` function
- [ ] Create `app/api/app/functions/gather.py`
- [ ] Implement `gather_product_reviews(product_name, force_refresh=False)`
  - Check DB first for existing product/reviews
  - If not found, call search_youtube_reviews + search_blog_reviews
  - Ingest top results and return aggregated data
- [ ] Add function declaration to `registry.py`
- [ ] **TEST**: Call with "iPhone 15 Pro" - should scrape and return review data

### 1.2 Create `search_youtube_reviews` function
- [ ] Implement in `gather.py`
- [ ] Use Gemini with Google Search grounding to find YouTube review URLs
- [ ] Filter for tech channels (MKBHD, Linus Tech Tips, Dave2D, etc.)
- [ ] Return list of YouTube URLs
- [ ] **TEST**: Call with "Sony WH-1000XM5" - should return 3-5 valid YouTube URLs

### 1.3 Create `search_blog_reviews` function
- [ ] Implement in `gather.py`
- [ ] Use Gemini with Google Search to find tech blog reviews
- [ ] Target: The Verge, Tom's Guide, CNET, TechRadar, etc.
- [ ] Return list of blog URLs
- [ ] **TEST**: Call with "MacBook Pro M3" - should return 3-5 valid blog URLs

### 1.4 Update `search_products` to suggest auto-scrape
- [ ] Modify `functions/products.py`
- [ ] If no results found, return message suggesting to gather reviews
- [ ] **TEST**: Search for non-existent product - should suggest gathering reviews

---

## Phase 2: Marketplace Integration (HIGH PRIORITY)

### 2.1 Create marketplace scraper service
- [ ] Create `app/api/app/services/marketplace_scraper.py`
- [ ] Implement `scrape_amazon_listings(product_name)` using Firecrawl
- [ ] Implement `scrape_ebay_listings(product_name)` using Firecrawl
- [ ] Parse results with Gemini for structured extraction
- [ ] **TEST**: Scrape "AirPods Pro" from Amazon - should return price, seller, URL

### 2.2 Create `scrape_marketplace_listings` function
- [ ] Add to `functions/marketplace.py`
- [ ] Call marketplace_scraper service
- [ ] Store results in MarketplaceListing table
- [ ] Add function declaration to `registry.py`
- [ ] **TEST**: Call function - should scrape and store listings

### 2.3 Fix `find_marketplace_listings` to auto-scrape
- [ ] Modify existing function in `functions/marketplace.py`
- [ ] If DB empty or stale (>24h), trigger scrape first
- [ ] Return listings sorted by: best_seller, best_reviewed, cheapest
- [ ] **TEST**: Call for product with no listings - should scrape then return data

### 2.4 Update MarketplaceListing model
- [ ] Add `seller_name: str` field
- [ ] Add `seller_rating: float` field
- [ ] Add `review_count: int` field
- [ ] Add `is_best_seller: bool` field
- [ ] Create Alembic migration
- [ ] **TEST**: Run migration successfully

---

## Phase 3: System Prompt & Anti-Hallucination (HIGH PRIORITY)

### 3.1 Update system prompt in chat_service.py
- [ ] Add CRITICAL rule: "NEVER answer from training data"
- [ ] Add: "ALWAYS call gather_product_reviews when user asks about a product"
- [ ] Add: "Only cite information from function call results"
- [ ] Add: "If no data, say 'I don't have review data for this product yet'"
- [ ] **TEST**: Ask about obscure product without calling function - AI should refuse

### 3.2 Add function call validation
- [ ] Log warning if AI responds to product query without function calls
- [ ] Track function call rate per conversation
- [ ] **TEST**: Verify logs show warnings for responses without function calls

---

## Phase 4: Review Ingestion Improvements (MEDIUM PRIORITY)

### 4.1 Add rate limiting to YouTube scraper
- [ ] Add retry logic with exponential backoff
- [ ] Limit to 10 requests/minute to Gemini
- [ ] **TEST**: Rapid calls should be rate limited

### 4.2 Improve blog scraper reliability
- [ ] Handle Firecrawl errors gracefully
- [ ] Add fallback to Gemini search if Firecrawl fails
- [ ] **TEST**: Simulate Firecrawl failure - should use fallback

### 4.3 Add batch ingestion support
- [ ] Use `asyncio.gather()` for parallel ingestion
- [ ] Handle individual failures without stopping batch
- [ ] **TEST**: Ingest 5 URLs - should complete even if 1 fails

---

## Phase 5: Caching & Freshness (MEDIUM PRIORITY)

### 5.1 Add cache freshness checking
- [ ] Implement `should_refresh_data(product_id, max_age_hours)` helper
- [ ] Default TTLs: Reviews=168h (7 days), Marketplace=24h
- [ ] **TEST**: Old data should trigger refresh, new data should not

### 5.2 Add force_refresh parameter to key functions
- [ ] `gather_product_reviews(product_name, force_refresh=False)`
- [ ] `find_marketplace_listings(product_id, force_refresh=False)`
- [ ] **TEST**: force_refresh=True should always scrape new data

---

## Phase 6: Answer Quality (MEDIUM PRIORITY)

### 6.1 Fix source extraction in chat_service.py
- [ ] Implement `_extract_sources()` to return actual sources
- [ ] Extract reviewer names and URLs from function results
- [ ] **TEST**: Response should include source attribution

### 6.2 Implement consensus calculation
- [ ] Fix `consensus_crud.calculate_consensus()`
- [ ] Run after new reviews are ingested
- [ ] Store aggregated opinions in Consensus table
- [ ] **TEST**: After ingesting reviews, consensus should be calculated

---

## Phase 7: Function Declarations (HIGH PRIORITY)

### 7.1 Add new function declarations to registry.py
- [ ] `gather_product_reviews` declaration
- [ ] `search_youtube_reviews` declaration
- [ ] `search_blog_reviews` declaration
- [ ] `scrape_marketplace_listings` declaration
- [ ] **TEST**: All 4 new functions appear in FUNCTION_DECLARATIONS

---

## Integration Testing Checklist

### Full Flow Test 1: New Product Query
```
Input: "Tell me about the Google Pixel 8 Pro"
Expected:
1. AI calls gather_product_reviews("Google Pixel 8 Pro")
2. Function searches YouTube and blogs
3. Function ingests top reviews
4. AI responds with summary citing actual reviewers
```
- [ ] Test passes with expected behavior

### Full Flow Test 2: Where to Buy
```
Input: "Where can I buy the Samsung Galaxy S24?"
Expected:
1. AI calls find_marketplace_listings() or scrape_marketplace_listings()
2. Function scrapes Amazon and eBay
3. AI responds with price options and links
```
- [ ] Test passes with expected behavior

### Full Flow Test 3: No Hallucination
```
Input: "What's the battery life of the iPhone 15 Pro Max?"
Expected:
1. AI calls a function to get review data
2. AI ONLY cites information from function results
3. AI does NOT use training data to answer
```
- [ ] Test passes with expected behavior

### Full Flow Test 4: Cached Data
```
Input: Ask about same product twice
Expected:
1. First call: Scrapes and stores data
2. Second call: Uses cached data (no new scraping)
```
- [ ] Test passes with expected behavior

---

## Completed Tasks
- [x] Initial codebase analysis
- [x] Created fixing_plan.md

---

## Notes
- Focus on Phase 1-3 first (core functionality)
- Test each function individually before integration
- Update this file after completing each task
- Commit working changes frequently

---

## Blocking Issues
(Document any blockers here)

