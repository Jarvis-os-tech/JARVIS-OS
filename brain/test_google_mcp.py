#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from google_mcp_service import dispatch, is_authenticated
import asyncio

async def test():
    print("Authenticated?", is_authenticated())
    # Test a simple tool that doesn't require network maybe? Actually we can test listing labels if authenticated
    if is_authenticated():
        result = await dispatch("gmail_list_labels", {})
        print("Gmail labels result:", result)
    else:
        print("Not authenticated; please run OAuth setup.")

if __name__ == "__main__":
    asyncio.run(test())