"""
A quick network awareness tool
Shows your IP, interfaces, and who else is on your network.
macOS-focused (ifconfig / ipconfig / arp).
"""
import subprocess
import re
import sys

# Colours and Font options for terminal output
GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RED    = "\033[91m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

SEPARATOR = "-" * 50

def run(cmd: list[str]) -> str:
    """
    Run a terminal command and return its output as a string.
    """
    try:
        return subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""

def get_interfaces() -> list[str]:
    """
    Pull active interface names from ifconfig.
    """
    output = run(["ifconfig"])
    return re.findall(r"^(\w+):", output, re.MULTILINE)

def get_my_ipv4(interface: str) -> str | None:
    """
    Try ipconfig getifaddr for a given interface.
    """
    result = run(["ipconfig", "getifaddr", interface]).strip()
    return result if result else None

def get_my_mac_address(interface: str) -> str:
    """
    Pull MAC address for a given interface from ifconfig.
    """
    output = run(["ifconfig", interface])
    match = re.search(r"ether ([\w:]+)", output)
    return match.group(1) if match else "n/a"

def get_my_interfaces_and_ips() -> list[tuple[str, str]]:
    """
    Return list of (interface, ipv4) for all interfaces with a routable IPv4 address.
    """
    interfaces_and_ips = []
    for interface in get_interfaces():
        ipv4 = get_my_ipv4(interface)
        if ipv4 and not ipv4.startswith("127."):
            interfaces_and_ips.append((interface, ipv4))
    return interfaces_and_ips

def parse_arp() -> dict[str, dict]:
    """
    Parse `arp -a` - returns dict keyed by IPv4 with mac address.

    example output: { "192.168.1.1": { "mac": "aa:bb:cc:dd:ee:ff" } }
    """
    output = run(["arp", "-a"])
    devices = {}

    for line in output.splitlines():
        if "incomplete" in line or "permanent" in line:
            continue
        match = re.search(r"\((\d+\.\d+\.\d+\.\d+)\)\s+at\s+([\w:]+)", line)
        if match:
            ipv4, mac = match.group(1), match.group(2)
            devices[ipv4] = {"mac": mac, "ipv6": []}
    return devices

def parse_ndp() -> dict[str, list[str]]:
    """
    Parse `ndp -a` (Neighbor Discovery Protocol) is the macOS equivalent of arp for IPv6.
    Returns dict of MAC -> list of IPv6 addresses.

    example output: { "aa:bb:cc:dd:ee:ff": ["fe80::1"] }
    """
    output = run(["ndp", "-a"])
    mac_to_ipv6 = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        ipv6 = parts[0].split("%")[0]  # strip interface suffix e.g. fe80::1%en0
        mac  = parts[1]
        if not re.match(r"[\w:]{17}", mac):
            continue
        if not re.match(r"[0-9a-fA-F:]+", ipv6):
            continue
        mac_to_ipv6.setdefault(mac, []).append(ipv6)
    return mac_to_ipv6


def main():
    print("\nSCANNING NETWORK...\n")

    my_interfaces = get_my_interfaces_and_ips()
    if not my_interfaces:
        print("Could not determine your IPv4 address. Are you connected?")
        sys.exit(1)

    # Use the first interface and IP (typically the primary one) for scanning
    interface, my_ipv4 = my_interfaces[0]
    my_mac_addr = get_my_mac_address(interface)
    devices_map = parse_arp()
    mac_to_ipv6 = parse_ndp()

    # Inject yourself into the device map (ARP won't include your own machine)
    devices_map[my_ipv4] = {
                            "mac": my_mac_addr,
                            "ipv6": mac_to_ipv6.get(my_mac_addr, []),
                            }
    my_ipv6_addresses = devices_map[my_ipv4].get("ipv6", [])

    # 1. Identify your own IP
    print(SEPARATOR)
    print(f"\n{BOLD}{GREEN}>>> YOUR IP ADDRESS{RESET}\n")
    print(f"Interface : {interface}")
    print(f"IPv4      : {my_ipv4}")
    print(f"MAC       : {my_mac_addr}")
    print(f"IPv6      : {'\n            '.join(my_ipv6_addresses) if my_ipv6_addresses else 'N/A'}\n")
    print(SEPARATOR)

    # 2. Get everyone on the network
    all_devices = {ip: info for ip, info in devices_map.items()}

    print(f"\n{BOLD}{GREEN}>>> LOCAL NETWORK - ({len(all_devices)} device(s)){RESET}\n")

    if not all_devices:
        print("No other devices found.")
    else:
        for ipv4, info in all_devices.items():
            print(f"  {CYAN}IPv4{RESET} : {ipv4}")
            print(f"  {CYAN}MAC {RESET} : {info['mac']}")
            ipv6_addresses = info["ipv6"]
            print(f"  {CYAN}IPv6{RESET} : {'\n         '.join(ipv6_addresses) if ipv6_addresses else 'N/A'}")
            print()

    print(f"{SEPARATOR}\n")
    print (f"TOTAL DEVICES FOUND: {len(devices_map)}\n")
    print(f"\nSCANNING COMPLETE\n")
    print(f"{SEPARATOR}\n")

if __name__ == "__main__":
    main()