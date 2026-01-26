# MCP Implementation Fix Plan v2

## Context
You are an autonomous AI development agent fixing and completing the MCP (Model Context Protocol) server embedded in the chompchat-backend Django application. The tools are implemented but need fixes to work correctly with GPT/Claude for restaurant ordering.

**Scope**: PICKUP orders only (no delivery in v1)
**Library**: [django-mcp](https://github.com/kitespark/django-mcp)

## Key Principles
- **Database Only** - MCP tools MUST only return restaurants/menus from our database, never hallucinate
- **Match SMS Bot Patterns** - Use the same menu format as `Menu.build_menu_text()` for consistency
- **Explain Modifiers to LLM** - Include min_selections/max_selections constraints in tool responses
- **Async First** - All tools use `async def` with `sync_to_async` for ORM calls
- **Reuse Existing Logic** - Leverage `llm_functions/ordering.py` patterns where applicable

---

## Implementation Checklist

### Phase 1: Location Tools Fixes
- [ ] Fix `list_locations` - Ensure it ONLY returns locations from database
  - Add clear docstring warning LLM not to suggest restaurants outside the list
  - Return `pickup_active=True` locations only
  - Include timezone-aware open/closed status
- [ ] Fix `get_location` - Return full location details
  - Include `weekly_hours` formatted for human reading
  - Return `can_place_order()` status (respects order_cutoff)
- [ ] Fix `check_location_accepting_orders` - Use `location.can_place_order()`
  - This is more accurate than just checking open hours

### Phase 2: Menu Tools Fixes (Critical)
- [ ] Fix `list_menu_items` to match SMS bot format
  - Use `Menu.build_menu_text()` as reference for structure
  - Return items with `modifier_list_ids` (not just `has_modifiers` bool)
  - Include category information
- [ ] Fix `get_item_modifiers` - MUST explain constraints to LLM
  - Include `min_selections` and `max_selections` per modifier list
  - Add explanation text: "Customer must select between {min} and {max} options from this list"
  - Flag required modifier lists (min_selections >= 1)
- [ ] Add `get_full_menu` tool - Returns complete menu in LLM-friendly format
  - Follows `build_menu_text()` pattern: categories → modifier lists → items
  - JSON structure matching SMS bot format:
    ```json
    {
      "categories": [{"category_id": 1, "name": "Appetizers"}, ...],
      "modifier_lists": [
        {
          "modifier_list_id": 1,
          "name": "Size",
          "min_selections": 1,
          "max_selections": 1,
          "modifiers": [{"modifier_id": 1, "name": "Small", "price_adjustment": -2.00}, ...]
        }
      ],
      "items": [
        {
          "item_id": 1,
          "name": "Pizza",
          "description": "...",
          "price": 15.99,
          "modifier_list_ids": [1, 2],
          "category_ids": [1]
        }
      ]
    }
    ```
- [ ] Fix `search_menu` - Return same structure as `list_menu_items`

### Phase 3: Order Tools Fixes
- [ ] Fix `create_order` - Verify location accepts orders before creating
  - Use `location.can_place_order(is_demo=False)` for validation
  - Auto-set `fulfillment_type=FulfillmentType.PICKUP`
  - Call `order.assign_code()` to generate human-readable code
- [ ] Fix `add_line_item` - Match `llm_functions/ordering.py:add_order_line_item()`
  - Use `OrderLineItem.create_from_ids()` which validates modifiers
  - Return validation errors clearly (min/max modifier violations)
  - Handle `handle_update=True` to cancel stale payments
- [ ] Fix `update_line_item` - Document limitation
  - Each OrderLineItem represents quantity=1 in this codebase
  - To change quantity: add/remove line items
  - Modifiers can be updated by replacing them
- [ ] Fix `remove_line_item` - Match `llm_functions/ordering.py:remove_order_line_item()`
  - Call `order.handle_order_update_cancellations()` after removal
- [ ] Fix `set_tip` - Use `order.set_restaurant_tip(tip_cents, handle_update=True)`
  - Convert dollars to cents before calling
- [ ] Fix `get_order_summary` - Include all order details
  - Use `order.to_dict()` and `order.as_reference_for_llm()` patterns
  - Include `ready_for_payment` status with `order.ready_for_payment()`
  - List missing requirements (e.g., "customer_phone", "items")
- [ ] Fix `get_order_status` - Include payment status
  - Check `order.is_frozen` for paid status
  - Include `order.get_active_payment()` info

### Phase 4: Payment Tools Fixes
- [ ] Fix `set_customer_info` - Properly link Diner to Order
  - Create/get PhoneNumber object
  - Create/get User and Profile
  - Create/get Diner with phone_number
  - Update `order.diner` to the new Diner
- [ ] Fix `create_payment_link` - Use existing payment flow
  - Check `order.ready_for_payment()` first
  - Use `order.get_chompchat_payment_link()` (creates Stripe JIT)
  - Handle demo mode with `MCP_DEMO_MODE` setting
- [ ] Fix `get_payment_status` - Check multiple payment states
  - Use `order.get_active_payment()`
  - Check `order.is_frozen` for completion status
  - Return payment provider info

### Phase 5: LLM Context Improvements
- [ ] Add tool descriptions that guide LLM behavior
  - Warn against hallucinating restaurants
  - Explain modifier selection rules
  - Document order flow: create → add items → set customer info → pay
- [ ] Add `get_ordering_instructions` tool (optional)
  - Returns step-by-step ordering flow for LLM
  - Explains how modifiers work (required vs optional)

### Phase 6: Testing & Validation
- [ ] Test with MCP Inspector: `python manage.py mcp_inspector`
- [ ] Test complete order flow:
  1. `list_locations` → choose location
  2. `get_full_menu` or `list_menu_items` → browse menu
  3. `get_item_modifiers` → understand requirements
  4. `create_order` → start order
  5. `add_line_item` → add items with modifiers
  6. `get_order_summary` → review order
  7. `set_customer_info` → provide phone
  8. `create_payment_link` → get payment URL
  9. `get_payment_status` → verify payment
- [ ] Test error cases:
  - Invalid location_id
  - Location closed
  - Missing required modifiers
  - Invalid modifier combinations (min/max violations)
  - Order without items
  - Payment without customer phone

---

## Key Code References

### Alignment with Existing LLM Functions

**CRITICAL**: MCP tools must align with existing `llm_functions/` patterns:

```python
# From ordering.py - Tips use CENTS, not dollars
order.set_restaurant_tip(tip_amount_cents, handle_update=True)

# From fulfillment.py - Always cancel stale payments after changes
order.handle_order_update_cancellations()

# From ordering.py - Use validated line item creation
OrderLineItem.create_from_ids(order, item_id, modifier_ids, handle_update=True)
```

**From `text_waiter.txt` framing:**
- "Be careful when one or more modifications are required for an item"
- "Always use integer IDs for function calls"
- "Do not suggest items or types of cuisine that are not on the menu"

**From `payments.json`:**
- Payment is ONLINE ONLY - no cash option
- Use `order.get_chompchat_payment_link()` for URLs
- Links persist throughout conversation

### Menu Format (from `restaurant/models/menus.py:build_menu_text`)
```python
# Categories first
{"category_id": 1, "name": "Appetizers"}

# Modifier lists with constraints
{
  "modifier_list_id": 1,
  "name": "Size",
  "min_selections": 1,  # REQUIRED - customer must pick at least 1
  "max_selections": 1,  # Can only pick 1
  "modifiers": [
    {"modifier_id": 10, "name": "Small", "price_adjustment": -2.00},
    {"modifier_id": 11, "name": "Large", "price_adjustment": 3.00}
  ]
}

# Items with modifier list references
{
  "item_id": 1,
  "name": "Pizza",
  "price": 15.99,
  "modifier_list_ids": [1, 2],  # References to modifier lists above
  "category_ids": [1]
}
```

### Order Line Item Creation (from `restaurant/models/orders.py`)
```python
# Use this for proper validation:
OrderLineItem.create_from_ids(
    order=order,
    item_id=item_id,
    modifier_ids=modifier_ids,  # List of modifier IDs
    handle_update=True  # Cancels stale payments
)
# Raises OrderLineItemCreationError with clear messages
```

### LLM Functions to Match (from `restaurant/llm_functions/ordering.py`)
| LLM Function | MCP Tool Equivalent |
|--------------|---------------------|
| `add_order_line_item` | `add_line_item` |
| `remove_order_line_item` | `remove_line_item` |
| `get_order` | `get_order_summary` |
| `get_available_modifiers` | `get_item_modifiers` |
| `set_restaurant_tip` | `set_tip` |
| `get_payment_link` | `create_payment_link` |

### Location Validation
```python
# Check if location accepts orders (respects hours + cutoff)
location.can_place_order(cutoff_window=None, is_demo=False)

# Check order readiness
order.ready_for_payment()  # Returns (bool, message)
```

---

## Files to Modify

| File | Changes |
|------|---------|
| `restaurant/mcp/location_tools.py` | Fix docstrings, use `can_place_order()` |
| `restaurant/mcp/menu_tools.py` | Match `build_menu_text()` format, explain modifiers |
| `restaurant/mcp/order_tools.py` | Use `OrderLineItem.create_from_ids()`, proper validation |
| `restaurant/mcp/payment_tools.py` | Fix Diner linking, use `get_chompchat_payment_link()` |

---

## Testing Commands

All commands run from the **monorepo root**: `D:\Codes\ChompChat\chompchat`

```bash
# Start the backend services (Django + Celery + Postgres + Redis)
make backend
# Or: make dev-backend

# View logs
make l-backend          # All backend logs
make l-django           # Django only

# Get a bash shell inside the container
make bash-backend

# Get a Django shell
make sh-backend

# Run tests
make t-backend                              # All unit + API tests
make test-file                              # Prompts for specific file

# Inside the container (after `make bash-backend`):
pytest tests/unit/ -v                       # Unit tests
pytest tests/unit/test_mcp_*.py -v          # MCP tests specifically
python manage.py mcp_inspector              # MCP Inspector (interactive)

# Database access
make db-backend         # psql shell

# Restart services
make r-backend          # Restart Django + Celery
make r-django           # Restart just Django
```

### MCP Inspector Testing (inside container)
```bash
# First, start the backend: make backend
# Then get a shell: make bash-backend
# Run the inspector:
python manage.py mcp_inspector
```

---

## Status Reporting

At the end of your response, include:

```
---MCP_STATUS---
STATUS: IN_PROGRESS | COMPLETE | BLOCKED
PHASE: 1 | 2 | 3 | 4 | 5 | 6
TOOLS_FIXED: <number>/16
TESTS_STATUS: PASSING | FAILING | NOT_RUN
EXIT_SIGNAL: false | true
RECOMMENDATION: <one line summary of what to do next>
---END_MCP_STATUS---
```

### Exit Criteria
Set `EXIT_SIGNAL: true` when:
1. All checklist items marked [x]
2. MCP Inspector tests pass
3. Complete order flow works end-to-end
4. No error cases fail silently

---

## Critical Bugs to Fix

1. **Location hallucination**: LLM may suggest restaurants not in database
   - Fix: Strong docstrings warning LLM + validation in tools

2. **Modifier constraints ignored**: LLM doesn't know min/max requirements
   - Fix: Include constraints in `get_item_modifiers` response with explanation

3. **Menu format mismatch**: MCP returns different format than SMS bot
   - Fix: Match `build_menu_text()` JSON structure

4. **Diner not linked**: `set_customer_info` may not properly update order
   - Fix: Ensure `order.diner` is updated with phone-linked Diner

5. **Payment link creation**: May fail silently
   - Fix: Check `ready_for_payment()` first, return clear errors
