# AGENTS.md

## Overview

This repository contains a FastAPI backend application.

The primary goals are:

- Keep the backend simple and maintainable.
- Prefer small, focused modules over large files.
- Use async I/O consistently.
- Keep API routes thin.
- Separate API, business logic, database access, and external services.
- Reuse existing utilities and services instead of duplicating logic.
- Prefer clear, boring code over unnecessary abstractions.

---

# Project Structure

Follow this general structure:

```text
app/
├── main.py
├── config.py
├── dependencies.py
│
├── api/
│   ├── router.py
│   └── routes/
│       ├── auth.py
│       ├── users.py
│       └── ...
│
├── models/
│   ├── documents/
│   └── schemas/
│
├── services/
│   ├── auth.py
│   ├── users.py
│   └── ...
│
├── repositories/
│   ├── users.py
│   └── ...
│
├── core/
│   ├── security.py
│   ├── exceptions.py
│   └── ...
│
├── utils/
│   └── ...
│
└── workers/
    └── ...
```

Do not create directories simply to follow this structure. If a feature is small, keep it simple.

---

# General Rules

## 1. Keep files small

Avoid creating large files containing unrelated functionality.

Prefer:

```text
services/
├── auth.py
├── users.py
└── payments.py
```

instead of:

```text
services.py
```

A file should generally have one clear responsibility.

Do not split extremely small logic into unnecessary files just for the sake of abstraction.

---

## 2. Reuse existing code

Before creating a new:

- utility
- dependency
- database helper
- service
- exception
- validation function
- configuration helper

search the existing project first.

Do not duplicate functionality that already exists.

---

## 3. Keep route handlers thin

Routes should primarily handle:

1. Request validation
2. Authentication/authorization
3. Calling application/service logic
4. Returning the response

Avoid putting substantial business logic directly inside route handlers.

Bad:

```python
@router.post("/users")
async def create_user(data: UserCreate):
    user = await User.find_one(User.email == data.email)

    if user:
        raise HTTPException(400, "User already exists")

    user = User(
        email=data.email,
        username=data.username,
    )

    await user.insert()

    # Lots of additional business logic...
    return user
```

Prefer:

```python
@router.post("/users", response_model=UserResponse)
async def create_user(data: UserCreate):
    return await user_service.create_user(data)
```

---

# FastAPI

## Routing

Use `APIRouter` for feature-specific routes.

```python
router = APIRouter(
    prefix="/users",
    tags=["users"],
)
```

Register routers centrally.

Avoid putting all endpoints in `main.py`.

---

## Dependency Injection

Use FastAPI dependencies for:

- Authentication
- Authorization
- Database/session dependencies
- Request-scoped resources
- Shared request validation

Example:

```python
@router.get("/me")
async def get_me(
    current_user: User = Depends(get_current_user),
):
    return current_user
```

Do not manually recreate dependency logic inside every endpoint.

---

# Async Programming

Use `async`/`await` for I/O-bound operations.

Prefer:

```python
user = await User.get(user_id)
```

over synchronous database/network operations inside async routes.

External I/O includes:

- MongoDB
- HTTP APIs
- Redis
- Cloud storage
- LLM APIs
- File operations where async APIs are available

Do not introduce blocking operations into async request handlers.

If a synchronous CPU-heavy operation is unavoidable, consider moving it to:

- a worker
- a background task
- a process/thread pool

depending on the workload.

---

# Pydantic

Use Pydantic models for API input and output.

Example:

```python
class UserCreate(BaseModel):
    email: EmailStr
    username: str
```

Use separate schemas when input and output requirements differ.

For example:

```text
schemas/
├── user_create.py
├── user_update.py
└── user_response.py
```

Do not expose database documents directly when doing so would leak internal fields.

---

# Database

The project uses MongoDB with Beanie.

Database models should represent persisted data.

Keep database-specific operations out of API routes whenever possible.

Example:

```python
class UserDocument(Document):
    email: str
    username: str
```

Use repositories/services when database logic becomes non-trivial.

Simple queries may remain close to the service layer.

Avoid creating repositories for every single CRUD operation unless they provide real value.

---

# Beanie / MongoDB

Prefer Beanie's async APIs:

```python
user = await UserDocument.find_one(
    UserDocument.email == email
)
```

For updates, make the operation explicit and easy to understand.

Avoid unnecessary MongoDB queries.

If multiple pieces of information can be retrieved with one query, prefer the single query.

Consider indexes for fields frequently used for:

- Lookups
- Filtering
- Sorting
- Uniqueness

Example:

```python
class Settings:
    indexes = [
        "email",
    ]
```

Do not add indexes without understanding the query pattern.

---

# Transactions

Use database transactions only when atomicity is actually required.

Do not introduce transactions for simple independent operations.

When a workflow involves multiple writes that must succeed or fail together, use an appropriate MongoDB transaction/session strategy.

---

# Configuration

Keep environment-specific configuration in environment variables.

Do not hardcode:

- API keys
- Passwords
- JWT secrets
- Database credentials
- Cloudinary credentials
- LLM API keys
- Production URLs

Use a central settings/configuration module.

Example:

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    mongodb_url: str
    jwt_secret: str

    model_config = {
        "env_file": ".env",
    }
```

Never commit `.env` files containing secrets.

---

# Authentication

Authentication logic should be centralized.

Do not implement JWT/token validation separately inside each endpoint.

Prefer:

```text
core/
└── security.py

dependencies.py
└── get_current_user()
```

Endpoints should consume the authenticated user rather than manually decoding tokens.

---

# Authorization

Authentication answers:

> Who is this user?

Authorization answers:

> Is this user allowed to perform this operation?

Keep these concepts separate.

For example:

```python
current_user = Depends(get_current_user)
```

followed by appropriate authorization checks.

Never trust user-provided:

- `owner_id`
- `user_id`
- `role`
- `is_admin`

when those values should come from the authenticated identity.

---

# Error Handling

Use meaningful HTTP status codes.

Common examples:

```text
400 Bad Request
401 Unauthorized
403 Forbidden
404 Not Found
409 Conflict
422 Validation Error
429 Too Many Requests
500 Internal Server Error
```

Do not expose internal stack traces, database errors, API keys, or sensitive implementation details to clients.

Bad:

```python
except Exception as e:
    raise HTTPException(500, str(e))
```

Prefer logging the internal exception and returning a safe message.

---

# Logging

Use structured logging where possible.

Logs should provide enough context to debug production issues.

Include useful identifiers such as:

- request ID
- user ID when appropriate
- job ID
- operation name

Do not log:

- passwords
- JWTs
- API keys
- secrets
- sensitive user data

Avoid excessive logging inside frequently executed loops.

---

# External APIs

External API calls should be isolated from route handlers.

Prefer:

```text
services/
├── llm.py
├── cloudinary.py
└── external_api.py
```

instead of calling external APIs directly from routes.

Always consider:

- timeout
- retry behavior
- rate limits
- error handling
- fallback behavior
- response validation

Do not retry indefinitely.

---

# LLM / AI Integrations

When working with LLM APIs:

- Validate model responses.
- Prefer structured output when supported.
- Never assume the model returned valid JSON.
- Handle missing or malformed responses.
- Implement explicit timeout/error handling.
- Keep prompts separate from route handlers.
- Keep provider-specific code isolated.

Prefer:

```text
agent/
├── prompts.py
├── schemas.py
├── tools/
├── services/
└── agent.py
```

rather than putting the entire AI workflow inside an API route.

---

# Background Jobs

Long-running operations should not block normal API requests.

Examples:

- Image processing
- Embedding generation
- Large AI requests
- Batch processing
- External synchronization

Use the project's worker/queue system when appropriate.

A request should generally:

1. Validate input
2. Create a job
3. Queue the job
4. Return a job/status identifier

The worker performs the expensive operation.

---

# File Uploads

Do not load unnecessarily large files entirely into memory.

Validate:

- File type
- File size
- File extension where relevant
- Content type where relevant

Do not trust client-provided MIME types blindly.

For uploaded images, validate/process the actual image before passing it to downstream services.

---

# API Design

Use consistent REST-style routes.

Prefer:

```text
GET    /users/{id}
POST   /users
PATCH  /users/{id}
DELETE /users/{id}
```

Use nouns for resources.

Avoid unnecessary verbs:

```text
/getUser
/createUser
/deleteUser
```

For actions that are genuinely not CRUD operations, action-style endpoints are acceptable.

---

# Response Models

Define response models for public API endpoints.

Example:

```python
@router.get(
    "/me",
    response_model=UserResponse,
)
async def get_me(...):
    ...
```

Do not accidentally expose internal database fields.

---

# Validation

Validate data at the API boundary.

Use Pydantic for:

- Type validation
- Required fields
- String constraints
- Enum values
- Nested structures
- Request schemas

Business rules that require database/external state should remain in the service layer.

---

# Type Hints

Use type hints consistently.

Prefer:

```python
async def get_user(user_id: PydanticObjectId) -> UserDocument | None:
    ...
```

over:

```python
async def get_user(user_id):
    ...
```

Avoid `Any` unless it is genuinely required.

Use explicit types for service and utility functions.

---

# Exception Strategy

Create application-specific exceptions when they make error handling clearer.

Example:

```python
class UserNotFoundError(Exception):
    pass
```

Translate domain/application exceptions into HTTP responses at the API boundary.

Do not spread `HTTPException` throughout lower-level services unless the service is explicitly API-specific.

Prefer:

```text
Route
  ↓
Service
  ↓
Repository / Database
```

rather than making every layer aware of HTTP.

---

# Testing

Tests should focus on behavior rather than implementation details.

Recommended structure:

```text
tests/
├── api/
├── services/
├── repositories/
└── conftest.py
```

Test important cases:

- Successful requests
- Validation errors
- Authentication failures
- Authorization failures
- Missing resources
- Duplicate resources
- External API failures
- Database failures
- Edge cases

Do not write tests only for the happy path.

---

# Code Style

Prefer readable code over clever code.

Good:

```python
if not user:
    raise UserNotFoundError()

return user
```

Avoid unnecessarily compressed code:

```python
return user if user else raise_error()
```

Use descriptive names.

Bad:

```python
d = get_data()
x = process(d)
```

Good:

```python
wardrobe_items = get_wardrobe_items()
recommendations = generate_recommendations(wardrobe_items)
```

---

# Imports

Keep imports organized.

Prefer:

```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.services.users import user_service
from app.models.users import UserDocument
```

Avoid circular imports.

If circular dependencies appear, reconsider the module boundaries rather than adding complicated import workarounds.

---

# Database Object IDs

When using MongoDB/Beanie IDs, validate and convert IDs at the boundary where appropriate.

Do not silently accept malformed IDs and allow them to propagate deep into the application.

---

# Performance

Do not optimize prematurely.

First make the implementation:

1. Correct
2. Simple
3. Observable
4. Maintainable

Then optimize based on actual bottlenecks.

Common things to check when performance matters:

- Number of database queries
- Missing indexes
- N+1 queries
- Large API responses
- Blocking operations
- External API latency
- Excessive serialization
- Unnecessary LLM calls

---

# Security

Never trust client input.

Always verify:

- Authentication
- Ownership
- Authorization
- Resource existence

For user-owned resources, prefer deriving ownership from the authenticated user:

```python
current_user.id
```

instead of:

```python
request.owner_id
```

Never allow a client to modify another user's resource simply by changing an ID.

---

# Git

Make focused commits.

Good:

```text
feat: add wardrobe item search
fix: handle missing image URL
refactor: extract user service
test: add wardrobe ownership tests
```

Avoid commits containing unrelated changes.

Do not commit:

- `.env`
- secrets
- generated files
- local databases
- temporary debugging files

---

# Dependency Management

Use the project's existing package manager.

Before adding a dependency:

1. Check whether the functionality already exists.
2. Check whether the standard library can solve the problem.
3. Check whether an existing dependency already provides it.
4. Add a new dependency only when it provides meaningful value.

Do not add dependencies for trivial functionality.

---

# API Versioning

If API versioning is used, keep versions explicit:

```text
/api/v1/...
```

Do not introduce versioning inconsistently across endpoints.

---

# Documentation

Document non-obvious behavior.

Do not add comments that simply restate the code.

Bad:

```python
# Get the user
user = await get_user(user_id)
```

Good:

```python
# User ownership is intentionally checked here because admins
# and regular users have different access rules.
```

Document:

- Complex business rules
- External API limitations
- Non-obvious workarounds
- Important architectural decisions
- Background job lifecycle/state machines

---

# Before Changing Code

Before implementing a feature:

1. Understand the existing architecture.
2. Find related routes.
3. Find related models/schemas.
4. Find existing services/utilities.
5. Check how errors are handled.
6. Check how authentication is implemented.
7. Follow existing conventions.

Do not introduce a new pattern when an established project pattern already exists.

---

# Before Creating a New File

Ask:

- Does this responsibility already have a module?
- Can this logic naturally belong to an existing service?
- Is the new file actually making the code easier to understand?

Avoid unnecessary fragmentation.

---

# Before Committing

Run the project's available:

- Formatter
- Linter
- Type checker
- Unit tests
- Integration tests

At minimum verify:

```text
✓ Application starts
✓ Imports work
✓ Relevant tests pass
✓ No secrets were added
✓ API response models are correct
✓ Authentication/authorization still works
```

---

# Important Principle

The backend should follow this general flow:

```text
HTTP Request
     │
     ▼
FastAPI Router
     │
     ▼
Validation / Dependencies
     │
     ▼
Service / Application Logic
     │
     ├──────────────► External APIs
     │
     ├──────────────► Workers / Queues
     │
     ▼
Database / Repository
     │
     ▼
Response Schema
     │
     ▼
HTTP Response
```

Keep responsibilities separated, but **do not over-engineer**.

The preferred implementation is the simplest implementation that is:

- Correct
- Secure
- Testable
- Maintainable
- Consistent with the existing project
