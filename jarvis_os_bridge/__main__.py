"""CLI entry point for JARVIS OS Deep Integration Bridge."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys

from .bluetooth_control import BluetoothController
from .device_watcher import DeviceWatcher
from .network_control import NetworkController
from .service import run_daemon


async def _cli_status() -> None:
    net = NetworkController()
    bt = BluetoothController()
    udev_watcher = DeviceWatcher()

    net_status = await net.get_status()
    bt_status = await bt.get_status()
    usb_devs = udev_watcher.list_usb_devices()

    await net.close()
    await bt.close()

    print("=== Network Status ===")
    print(f"  Connected:    {net_status.get('connected')}")
    print(f"  State:        {net_status.get('state')}")
    print(f"  Connectivity: {net_status.get('connectivity')}")
    print(f"  IP Addresses: {', '.join(net_status.get('ip_addresses', []))}")
    wifi = net_status.get("wifi")
    if wifi:
        print(f"  WiFi SSID:    {wifi.get('ssid')} ({wifi.get('signal_percent')}% signal on {wifi.get('interface')})")

    print("\n=== Bluetooth Status ===")
    print(f"  Adapter:      {bt_status.get('adapter')}")
    print(f"  Powered:      {bt_status.get('powered')}")
    print(f"  Discovering:  {bt_status.get('discovering')}")
    devs = bt_status.get("devices", [])
    print(f"  Known Devices ({len(devs)}):")
    for d in devs:
        conn = "Connected" if d.get("connected") else "Disconnected"
        paired = "Paired" if d.get("paired") else "Unpaired"
        print(f"    - {d.get('name')} [{d.get('address')}] ({conn}, {paired})")

    print(f"\n=== Removable USB Devices ({len(usb_devs)}) ===")
    for u in usb_devs:
        mount = f"mounted at {u['mount_point']}" if u.get("mounted") else "unmounted"
        print(f"    - {u.get('label')} [{u.get('node')}] ({u.get('fs_type')}, {mount})")


async def _cli_wifi_scan() -> None:
    net = NetworkController()
    print("Scanning available WiFi networks...")
    aps = await net.scan_wifi(rescan=True)
    await net.close()
    print(f"Found {len(aps)} networks:")
    for ap in aps:
        print(f"  {ap['ssid']:<30} {ap['signal_percent']:>3}%  {ap['security']:<10} {ap['band']}")


async def _cli_bt_scan(timeout: float = 6.0) -> None:
    bt = BluetoothController()
    print(f"Scanning for Bluetooth devices ({timeout}s)...")
    devs = await bt.scan_devices(timeout=timeout)
    await bt.close()
    print(f"Found {len(devs)} devices:")
    for d in devs:
        print(f"  {d.get('name', 'Unknown'):<30} [{d.get('address')}]")


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS OS Deep Integration Bridge")
    parser.add_argument("command", nargs="?", default="run", choices=["run", "status", "wifi-scan", "bt-scan", "usb-list"])
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose debug logging")
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    if args.command == "run":
        try:
            asyncio.run(run_daemon())
        except KeyboardInterrupt:
            return 0
    elif args.command == "status":
        asyncio.run(_cli_status())
    elif args.command == "wifi-scan":
        asyncio.run(_cli_wifi_scan())
    elif args.command == "bt-scan":
        asyncio.run(_cli_bt_scan())
    elif args.command == "usb-list":
        watcher = DeviceWatcher()
        devs = watcher.list_usb_devices()
        print(json.dumps(devs, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
