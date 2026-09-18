#!/usr/bin/env python3
"""
Cognee Lifecycle & Diagnostic Manager for JARVIS-OS.

Usage:
    python scripts/cognee_manager.py status
    python scripts/cognee_manager.py up
    python scripts/cognee_manager.py down
    python scripts/cognee_manager.py test
    python scripts/cognee_manager.py remember "Jarvis OS runs on Omarchy Linux with Hyprland"
    python scripts/cognee_manager.py recall "What OS does Jarvis run on?"
"""

import sys
import os
import time
import subprocess
import argparse
import json

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from memory.python.cognee_bridge import cognee_bridge, CogneeBridge


COMPOSE_FILE = os.path.join(PROJECT_ROOT, "docker-compose.cognee.yml")


def cmd_up():
    print(f"[Cognee Manager] 🚀 Launching Cognee services using {COMPOSE_FILE}...")
    res = subprocess.run(["docker", "compose", "-f", COMPOSE_FILE, "up", "-d"], cwd=PROJECT_ROOT)
    if res.returncode == 0:
        print("[Cognee Manager] ⏳ Waiting for Cognee API to become healthy...")
        for _ in range(25):
            time.sleep(1)
            if cognee_bridge.is_available(force=True):
                print(f"[Cognee Manager] 🟢 Cognee API is online and healthy at {cognee_bridge.api_url}!")
                print(f"[Cognee Manager] 🔌 Cognee MCP endpoint: {cognee_bridge.mcp_url}")
                return
        print("[Cognee Manager] ⚠️ Cognee container started, but health check is taking longer than expected.")
    else:
        print(f"[Cognee Manager] ❌ docker compose up failed with code {res.returncode}")


def cmd_down():
    print(f"[Cognee Manager] 🛑 Stopping Cognee services...")
    subprocess.run(["docker", "compose", "-f", COMPOSE_FILE, "down"], cwd=PROJECT_ROOT)
    print("[Cognee Manager] ⚪ Cognee services stopped.")


def cmd_status():
    st = cognee_bridge.status()
    print("=" * 60)
    print("  🧠 JARVIS-OS COGNEE UNIVERSAL MEMORY STATUS")
    print("=" * 60)
    print(f"• Enabled:          {st['enabled']}")
    print(f"• Connected:        {'🟢 ONLINE' if st['connected'] else '🔴 OFFLINE'}")
    print(f"• REST API:         {st['api_url']}")
    print(f"• MCP Server:       {st['mcp_url']}")
    print(f"• Default Dataset:  {st['default_dataset']}")
    print(f"• Service Runtime:  {st['service_type']}")
    print("=" * 60)

    # Check Docker containers
    try:
        ps_res = subprocess.run(
            ["docker", "compose", "-f", COMPOSE_FILE, "ps", "--format", "table {{.Name}}\t{{.Status}}\t{{.Ports}}"],
            capture_output=True, text=True, cwd=PROJECT_ROOT
        )
        if ps_res.returncode == 0 and ps_res.stdout.strip():
            print("\nDocker Containers:")
            print(ps_res.stdout.strip())
    except Exception:
        pass


def cmd_test():
    print("[Cognee Manager] 🧪 Running Cognee Universal Memory test suite...")
    st = cognee_bridge.status()
    if not st["connected"]:
        print(f"❌ Cognee API is not reachable at {st['api_url']}.")
        print("Run 'python scripts/cognee_manager.py up' first.")
        sys.exit(1)

    print("1. Testing memory ingestion (`remember`)...")
    test_fact = f"User preference verified at {time.strftime('%Y-%m-%d %H:%M:%S')}: Prefers high-fidelity audio and dark HUD."
    rem_res = cognee_bridge.remember(test_fact, dataset_name="jarvis_test_dataset")
    print(f"   Result: {rem_res}")

    print("2. Testing memory retrieval (`recall`)...")
    recall_res = cognee_bridge.recall("What is user audio preference?", dataset_name="jarvis_test_dataset")
    print(f"   Result: {recall_res}")

    print("✅ Cognee Universal Memory test suite completed successfully!")


def cmd_sync_vault():
    print("[Cognee Manager] 🔄 Synchronizing Obsidian Vault to Cognee Knowledge Graph...")
    res = cognee_bridge.sync_vault()
    if res.get("success"):
        print(f"✅ Successfully queued {res['files_synced']} vault files to dataset '{res['dataset']}' and triggered cognify!")
    else:
        print(f"❌ Vault synchronization failed: {res}")


def main():
    parser = argparse.ArgumentParser(description="Cognee Universal Memory Manager for JARVIS-OS")
    subparsers = parser.add_subparsers(dest="action", help="Command to run")

    subparsers.add_parser("up", help="Start Cognee & Cognee-MCP containers")
    subparsers.add_parser("down", help="Stop Cognee & Cognee-MCP containers")
    subparsers.add_parser("status", help="Check status of Cognee services")
    subparsers.add_parser("test", help="Test memory remember and recall operations")
    subparsers.add_parser("sync-vault", help="Sync Obsidian Vault Markdown files into Cognee")

    rem_p = subparsers.add_parser("remember", help="Store a memory in Cognee")
    rem_p.add_argument("text", type=str, help="Text to remember")
    rem_p.add_argument("--dataset", type=str, default=None, help="Dataset name")

    rec_p = subparsers.add_parser("recall", help="Search memory in Cognee")
    rec_p.add_argument("query", type=str, help="Query to search")
    rec_p.add_argument("--dataset", type=str, default=None, help="Dataset name")

    args = parser.parse_args()

    if args.action == "up":
        cmd_up()
    elif args.action == "down":
        cmd_down()
    elif args.action == "status" or not args.action:
        cmd_status()
    elif args.action == "test":
        cmd_test()
    elif args.action == "sync-vault":
        cmd_sync_vault()
    elif args.action == "remember":
        res = cognee_bridge.remember(args.text, dataset_name=args.dataset)
        print(json.dumps(res, indent=2))
    elif args.action == "recall":
        res = cognee_bridge.recall(args.query, dataset_name=args.dataset)
        print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
