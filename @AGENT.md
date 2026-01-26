# ShopLens Agent Build Instructions

## Project Overview
ShopLens is an AI-powered product review intelligence platform using:
- **Backend**: FastAPI (Python 3.11) with async SQLAlchemy
- **Database**: PostgreSQL (asyncpg driver)
- **Cache**: Redis
- **Vector DB**: Qdrant (for semantic search)
- **AI**: Google Gemini 3 with function calling
- **Scraping**: Firecrawl for blogs, Gemini Search Grounding for YouTube

## Project Structure
```
D:\Codes\ShopLens\
├── app/
│   ├── api/                    # FastAPI backend
│   │   ├── app/
│   │   │   ├── api/v1/endpoints/   # HTTP endpoints
│   │   │   ├── core/               # Config, security, logging
│   │   │   ├── crud/               # Database operations
│   │   │   ├── db/                 # Database session
│   │   │   ├── functions/          # Gemini function implementations
│   │   │   ├── models/             # SQLAlchemy models
│   │   │   ├── schemas/            # Pydantic schemas
│   │   │   ├── services/           # Business logic (scrapers, chat)
│   │   │   └── main.py
│   │   ├── tests/                  # Test files
│   │   ├── alembic/                # Database migrations
│   │   └── requirements.txt
│   └── web/                    # Frontend (nginx static)
├── docker-compose.yml
├── docker-compose.dev.yml
└── .ralph/                     # Ralph configuration
```

---

## Environment Setup

### Required Environment Variables
Create `app/api/.env`:
```env
# Required
GEMINI_API_KEY=your_gemini_api_key
FIRECRAWL_API_KEY=your_firecrawl_api_key
SECRET_KEY=your_jwt_secret_key

# Database (Docker sets these automatically)
DATABASE_URL=postgresql+asyncpg://user:pass@db:5432/shoplens

# Optional
DEBUG=true
LOG_LEVEL=DEBUG
LLM_MODEL=gemini-2.0-flash
```

---

## Running the Project

### Option 1: Docker (Recommended)
```bash
# Start development stack with hot reload
docker-compose -f docker-compose.dev.yml up --build

# View logs
docker-compose -f docker-compose.dev.yml logs -f api

# Get shell inside container
docker-compose -f docker-compose.dev.yml exec api bash
```

### Option 2: Local Development
```bash
cd app/api

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## Running Tests

### CRITICAL: Ralph Testing Instructions

Ralph MUST run tests to verify implementations. Use these methods:

#### Method 1: Docker (Preferred)
```bash
# Run all tests inside container
docker-compose -f docker-compose.dev.yml exec api pytest tests/ -v

# Run specific test file
docker-compose -f docker-compose.dev.yml exec api pytest tests/test_functions.py -v

# Run with coverage
docker-compose -f docker-compose.dev.yml exec api pytest tests/ --cov=app --cov-report=term-missing
```

#### Method 2: Local (if Docker not available)
```bash
cd app/api
pytest tests/ -v
pytest tests/test_functions.py -v
pytest tests/ --cov=app --cov-report=term-missing
```

#### Method 3: Create Test Script (if permission issues)
If you cannot run tests directly, create a test script:

```bash
# Create test runner script
cat > run_tests.sh << 'EOF'
#!/bin/bash
cd /app/api
pytest tests/ -v --tb=short
EOF
chmod +x run_tests.sh

# Then run it
./run_tests.sh
```

#### Method 4: Python Direct Execution
```bash
cd app/api
python -m pytest tests/ -v
```

### Test Structure
```
tests/
├── conftest.py          # Fixtures (db_session, client)
├── test_health.py       # Health endpoint tests
├── test_functions.py    # Function registry tests
├── test_gather.py       # (Create) gather_product_reviews tests
├── test_marketplace.py  # (Create) marketplace scraping tests
└── test_chat.py         # (Create) chat service tests
```

---

## Database Operations

### Run Migrations
```bash
cd app/api

# Generate new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

### Access Database
```bash
# Docker
docker-compose -f docker-compose.dev.yml exec db psql -U shoplens -d shoplens

# Direct
psql -h localhost -U shoplens -d shoplens
```

---

## Key Files to Modify

| File | Purpose |
|------|---------|
| `app/functions/registry.py` | Function declarations for Gemini |
| `app/functions/gather.py` | NEW: Product review gathering |
| `app/functions/marketplace.py` | Marketplace listing functions |
| `app/services/chat_service.py` | Chat orchestration, system prompt |
| `app/services/youtube_scraper.py` | YouTube review scraping |
| `app/services/firecrawl_service.py` | Blog scraping |
| `app/services/marketplace_scraper.py` | NEW: Amazon/eBay scraping |

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/chat` | POST | Main chat endpoint with function calling |
| `/api/v1/chat/conversations` | GET | List user conversations |
| `/api/v1/ingest/youtube` | POST | Ingest YouTube review |
| `/api/v1/ingest/blog` | POST | Ingest blog review |
| `/api/v1/health` | GET | Health check |
| `/api/v1/auth/register` | POST | User registration |
| `/api/v1/auth/login` | POST | User login |

---

## Testing Individual Functions

### Test Function Directly (Python REPL)
```python
# Start Python shell
cd app/api
python

# Test function
import asyncio
from app.db.session import AsyncSessionLocal
from app.functions.gather import gather_product_reviews

async def test():
    async with AsyncSessionLocal() as db:
        result = await gather_product_reviews(db, {"product_name": "iPhone 15 Pro"})
        print(result)

asyncio.run(test())
```

### Test via API (curl)
```bash
# Test chat endpoint
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Tell me about the iPhone 15 Pro"}'

# Test health
curl http://localhost:8000/api/v1/health
```

---

## Code Quality

```bash
cd app/api

# Linting
ruff check .

# Formatting
black .
isort .

# Type checking
mypy app/
```

---

## Feature Completion Checklist

Before marking ANY feature as complete, verify:

- [ ] Function implemented and registered in registry.py
- [ ] Unit tests written in tests/ directory
- [ ] All tests pass: `pytest tests/ -v`
- [ ] Code coverage >= 85%: `pytest --cov=app tests/`
- [ ] Function tested manually via Python REPL or API
- [ ] Expected results documented in test output
- [ ] Changes committed with conventional commit message
- [ ] .ralph/@fix_plan.md task marked as complete

---

## Troubleshooting

### Docker Issues
```bash
# Rebuild from scratch
docker-compose -f docker-compose.dev.yml down -v
docker-compose -f docker-compose.dev.yml up --build

# Check container logs
docker-compose -f docker-compose.dev.yml logs api
```

### Database Issues
```bash
# Reset database
docker-compose -f docker-compose.dev.yml exec api alembic downgrade base
docker-compose -f docker-compose.dev.yml exec api alembic upgrade head
```

### Permission Issues
If you encounter permission issues running commands:
1. Try running with explicit python: `python -m pytest`
2. Create shell scripts and run them
3. Use Docker exec to run inside container

### API Key Issues
- Verify `.env` file exists in `app/api/`
- Check keys are properly set: `echo $GEMINI_API_KEY`
- Restart containers after changing env vars

---

## Key Learnings
- Gemini 3 requires `thought_signature` preservation in function calls
- Firecrawl has 50KB content limit - truncate large pages
- Use `sync_to_async` when calling sync code from async functions
- SQLite used for tests, PostgreSQL for production
- Always use `async with AsyncSessionLocal()` for DB operations

---

## Exit Criteria for Ralph

Set EXIT_SIGNAL: true ONLY when ALL of these are verified:

1. **All functions work**: Each tool returns expected results when tested
2. **Full flow works**: User can ask about product -> get reviews -> ask where to buy -> get listings
3. **No hallucination**: AI only responds from function call data
4. **Tests pass**: `pytest tests/ -v` shows all tests passing
5. **Integration tested**: Manual test of full conversation flow documented

