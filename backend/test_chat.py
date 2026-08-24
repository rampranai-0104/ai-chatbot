import asyncio
import httpx
import json

async def run_test(name, msg, search):
    print(f"\n--- {name} ---")
    req = {
        "session_id": f"test_{name.replace(' ', '_')}",
        "message": msg,
        "web_search": search
    }
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            # We will use 8001 since the user's backend is on 8001, but wait, if it's user's backend, it might not have the new prompt!
            # Let's try 8001 first. If it fails, we fall back to nothing.
            async with client.stream("POST", "http://localhost:8001/chat", json=req) as response:
                async for line in response.aiter_lines():
                    if line:
                        # Print only the token values to see the actual markdown output
                        if line.startswith("data: "):
                            data = json.loads(line[6:])
                            if data["type"] == "token":
                                print(data["value"], end="", flush=True)
                            elif data["type"] == "status":
                                print(f"\n[{data['value']}]")
                            elif data["type"] == "error":
                                print(f"\n[ERROR: {data['value']}]")
                print("\n")
    except Exception as e:
        print(f"\n[FAILED: {e}]")

async def test_all():
    await run_test("Test 1: Binary tree", "What is a binary tree?", False)
    await run_test("Test 2: AI developments", "What are the latest AI developments?", True)
    await run_test("Test 3: Comparison", "Compare React, Vue, and Angular.", False)
    await run_test("Test 4: News", "Give me today's major technology news in a table.", True)
    await run_test("Test 5: Code", "Write a Python binary search implementation.", False)

if __name__ == "__main__":
    asyncio.run(test_all())
