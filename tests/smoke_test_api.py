#!/usr/bin/env python3
"""
API Smoke Test Suite
Verifies that a running instance of the Textbook Generator FastAPI server is healthy
and that the end-to-end flow works under live HTTP traffic.

Usage:
1. Start the server:
   uv run --with uvicorn --with fastapi --with pydantic-ai-slim --with sqlalchemy uvicorn textbook_generator.main:app --host 127.0.0.1 --port 8000 --reload
2. Run smoke tests:
   uv run --with httpx python tests/smoke_test_api.py
"""

import os
import sys
import time
import httpx

# Configure target host
API_HOST = os.environ.get("API_HOST", "http://127.0.0.1:8000")
print(f"=== Starting API Smoke Tests targeting: {API_HOST} ===")

# Create client
client = httpx.Client(timeout=10.0)

# --- Test 1: Connectivity Health Check ---
try:
    print("Checking connection to server...")
    res = client.get(f"{API_HOST}/api/books")
    if res.status_code == 200:
        print("✓ Server is ONLINE and responding.")
    else:
        print(f"✗ Server responded with status code: {res.status_code}")
        sys.exit(1)
except httpx.ConnectError:
    print(f"✗ Connection failed to: {API_HOST}")
    print("\n[ERROR] The Textbook Generator server is not running.")
    print("Please start the server first in a separate terminal:")
    print("  uv run --with uvicorn --with fastapi --with pydantic-ai-slim --with sqlalchemy uvicorn textbook_generator.main:app --host 127.0.0.1 --port 8000 --reload")
    sys.exit(1)

# --- Test 2: Seed Curricular Standards ---
print("\nTesting Curricular Standards seeding...")
res_seed = client.post(f"{API_HOST}/api/admin/requirements/populate")
if res_seed.status_code == 200:
    data = res_seed.json()
    print(f"✓ Database requirements seeded: {data.get('message')} (Added: {data.get('inserted')})")
else:
    print(f"✗ Seeding failed: {res_seed.status_code} - {res_seed.text}")
    sys.exit(1)

# --- Test 3: Create Textbook Project ---
print("\nCreating new textbook project...")
payload = {
    "title": "Aventura de Palabras (Smoke Test)",
    "subject": "Español",
    "grade": 1
}
res_create = client.post(f"{API_HOST}/api/books", json=payload)
if res_create.status_code == 200:
    book = res_create.json()
    book_id = book.get("id")
    print(f"✓ Textbook created. ID: {book_id}, Title: '{book.get('title')}', Status: {book.get('status')}")
else:
    print(f"✗ Failed to create textbook: {res_create.status_code} - {res_create.text}")
    sys.exit(1)

# --- Test 4: Polling Background Generation ---
print("\nWaiting for background agent pipeline execution...")
generated = False
# Poll up to 15 seconds to give time for outline & sequence skeleton creation
for i in range(1, 16):
    res_status = client.get(f"{API_HOST}/api/books/{book_id}")
    if res_status.status_code == 200:
        book_status = res_status.json().get("status")
        print(f"  [Poll {i}/15] Textbook state: {book_status}")
        
        # If status moved beyond DRAFT to GENERATING/PENDING_REVIEW, it proves background task started
        if book_status in ("GENERATING", "PENDING_REVIEW", "APPROVED"):
            generated = True
            print(f"✓ Background pipeline confirmed active. Textbook is now: {book_status}")
            break
    else:
        print(f"✗ Failed to poll status: {res_status.status_code}")
        sys.exit(1)
    time.sleep(1)

if not generated:
    print("✗ Pipeline timeout: Book remained in DRAFT state. Check server logs.")
    sys.exit(1)

# --- Test 5: Verify Review Queue (HITL) ---
print("\nChecking Human-in-the-Loop review queue...")
res_reviews = client.get(f"{API_HOST}/api/reviews")
if res_reviews.status_code == 200:
    reviews = res_reviews.json()
    print(f"✓ Review queue queried. Pending items: {len(reviews)}")
    
    # If using mock mode, background tasks will populate sequences quickly, 
    # and some sequences (number 2/5) will immediately score 0.80 and land in the review queue.
    # If an item is present, we test the approval endpoint.
    if len(reviews) > 0:
        target_seq = reviews[0]
        seq_id = target_seq.get("id")
        print(f"  Testing approval on Sequence ID {seq_id}: '{target_seq.get('title')}'")
        
        res_approve = client.post(
            f"{API_HOST}/api/reviews/{seq_id}",
            json={"approve": True, "feedback": "Approved by smoke test"}
        )
        if res_approve.status_code == 200:
            approved_seq = res_approve.json()
            print(f"✓ Sequence approved successfully. Status: {approved_seq.get('status')}")
        else:
            print(f"✗ Sequence approval failed: {res_approve.status_code} - {res_approve.text}")
            sys.exit(1)
else:
    print(f"✗ Failed to query review queue: {res_reviews.status_code}")
    sys.exit(1)

print("\n🎉 ALL API SMOKE TESTS COMPLETED SUCCESSFULLY!")
sys.exit(0)
