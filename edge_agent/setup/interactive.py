"""
EdgeErgo — Interactive Workstation Setup & Central Server Connectivity Verifier.

Implements the required startup workflow:
  1. Displays EdgeErgo branded welcome banner.
  2. Interactively asks for Central Server IP or URL (with auto-formatting to http://<IP>:8000).
  3. Interactively asks for Workstation Name (defaulting to system hostname or saved name).
  4. Validates inputs and tests connectivity via GET /api/v1/health (5-second timeout).
  5. Displays verified connection status on success.
  6. In case of failure, provides a troubleshooting checklist and interactive retry/change/exit options.
  7. Persists verified settings locally using ConfigManager.
"""

from __future__ import annotations

import logging
import socket
import sys
from typing import Any, Callable, Optional, Tuple
import urllib.parse

import httpx

from edge_agent.config.config_manager import ConfigManager

logger = logging.getLogger("edge_agent.setup")

DEFAULT_PORT = 8000
DEFAULT_TIMEOUT_SEC = 5.0

ASCII_BANNER = r"""
================================================================================
   ______    _             ______                   
  |  ____|  | |           |  ____|                  
  | |__   __| | __ _  ___ | |__   _ __  __ _  ___   
  |  __| / _` |/ _` |/ _ \|  __| | '__|/ _` |/ _ \  
  | |___| (_| | (_| |  __/| |____| |  | (_| | (_) | 
  |______\__,_|\__, |\___||______|_|   \__, |\___/  
                __/ |                   __/ |       
               |___/                   |___/        
   EdgeErgo Posture & Well-Being Intelligence Platform
   Workstation Edge Agent Setup
================================================================================
"""


def normalize_server_url(raw_input: str, default_port: int = DEFAULT_PORT) -> str:
    """Normalize raw server input (IP, host, or full URL) into a valid HTTP/HTTPS URL.

    Rules:
      - '192.168.1.100'        -> 'http://192.168.1.100:8000'
      - '192.168.1.100:9000'   -> 'http://192.168.1.100:9000'
      - 'http://192.168.1.100' -> 'http://192.168.1.100:8000'
      - 'http://192.168.1.100:8000/' -> 'http://192.168.1.100:8000'
      - 'https://secure.lan:8443'    -> 'https://secure.lan:8443'
      - 'https://secure.lan'         -> 'https://secure.lan'
      - 'localhost'            -> 'http://localhost:8000'
      - 'localhost:8000'       -> 'http://localhost:8000'

    Raises:
      ValueError if input is empty, malformed, or has an unsupported protocol scheme.
    """
    s = raw_input.strip()
    if not s:
        raise ValueError("Server address cannot be empty.")

    s = s.rstrip("/")

    # If scheme present, validate scheme
    if "://" in s:
        scheme = s.split("://")[0].lower()
        if scheme not in ("http", "https"):
            raise ValueError(f"Invalid protocol scheme '{scheme}'. Only http:// and https:// are supported.")
    else:
        s = f"http://{s}"

    parsed = urllib.parse.urlsplit(s)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc
    if not netloc:
        raise ValueError(f"Invalid server address '{raw_input}'. Hostname or IP missing.")

    # Determine if port is present in netloc (handling IPv6 brackets safely)
    if netloc.startswith("["):
        if "]" in netloc:
            post_bracket = netloc.split("]")[1]
            has_port = ":" in post_bracket
        else:
            has_port = False
    else:
        has_port = ":" in netloc

    if not has_port:
        if scheme == "http":
            netloc = f"{netloc}:{default_port}"

    path = parsed.path.rstrip("/")
    return f"{scheme}://{netloc}{path}"


def check_server_health(
    server_url: str,
    timeout_sec: float = DEFAULT_TIMEOUT_SEC,
    client: Optional[httpx.Client] = None,
) -> Tuple[bool, dict[str, Any] | str]:
    """Verify connectivity by calling GET /api/v1/health on the Central Server.

    Returns:
      (True, health_data_dict) on HTTP 200.
      (False, error_detail_str) on failure, timeout, or non-200 response.
    """
    clean_url = server_url.rstrip("/")
    health_endpoint = f"{clean_url}/api/v1/health"

    try:
        if client is not None:
            resp = client.get(health_endpoint)
        else:
            with httpx.Client(timeout=timeout_sec, follow_redirects=True) as local_client:
                resp = local_client.get(health_endpoint)

        if resp.status_code == 200:
            try:
                data = resp.json()
            except Exception:
                data = {"status": "healthy", "raw": resp.text}
            return True, data
        else:
            return False, f"Server returned HTTP {resp.status_code} ({resp.reason_phrase})"
    except httpx.ConnectTimeout:
        return False, f"Connection timed out after {timeout_sec:.1f}s. Server is not responding."
    except httpx.ConnectError:
        return False, "Connection refused or unreachable. Ensure the Central Server is running and accessible."
    except httpx.RequestError as exc:
        return False, f"Network request error: {exc}"
    except Exception as exc:
        return False, f"Unexpected error while contacting server: {exc}"


def get_default_workstation_name(saved_name: Optional[str] = None) -> str:
    """Return default workstation name: saved name, system hostname, or fallback."""
    if saved_name and saved_name.strip() and saved_name.strip() not in ("Workstation", "Workstation-Node"):
        return saved_name.strip()
    try:
        hostname = socket.gethostname().strip()
        if hostname:
            return hostname
    except Exception:
        pass
    return "Workstation-01"


def display_welcome_banner(print_func: Callable[..., None] = print) -> None:
    """Print the branded welcome header to the console."""
    print_func(ASCII_BANNER)


def display_connection_failure(
    server_url: str,
    error_detail: str,
    print_func: Callable[..., None] = print,
) -> None:
    """Print a user-friendly failure message and troubleshooting checklist."""
    print_func("\n" + "=" * 80)
    print_func(" [!] CONNECTION FAILED: Unable to reach EdgeErgo Central Server")
    print_func(f"     Target URL: {server_url}")
    print_func(f"     Error:      {error_detail}")
    print_func("-" * 80)
    print_func(" Troubleshooting Checklist:")
    print_func("   [1] Central Server: Is the server running on the central PC?")
    print_func("   [2] Network / LAN:  Are both computers connected to the same local Wi-Fi or LAN?")
    print_func("   [3] IP & Port:      Are the server's IP address and port (:8000) correct?")
    print_func("   [4] Binding:        Was the server launched with '--host 0.0.0.0' (not 127.0.0.1)?")
    print_func("   [5] Firewall:       Does Windows Firewall on the server allow inbound TCP port 8000?")
    print_func("=" * 80)


def run_interactive_setup(
    config_manager: ConfigManager,
    cli_server_url: Optional[str] = None,
    cli_device_name: Optional[str] = None,
    non_interactive: bool = False,
    input_func: Callable[[str], str] = input,
    print_func: Callable[..., None] = print,
    health_checker: Callable[[str, float], Tuple[bool, dict[str, Any] | str]] = check_server_health,
) -> Tuple[str, str]:
    """Execute interactive workstation setup or verify CLI parameters before monitoring begins.

    Steps:
      1. Display EdgeErgo logo / branded welcome message.
      2. Interactively ask for server IP or URL (with saved value as default).
      3. Interactively ask for workstation name (defaulting to hostname or saved name).
      4. Validate inputs.
      5. Verify connectivity via GET /api/v1/health (5-second timeout).
      6. On failure, suggest checklist and offer interactive retry/change/exit options.
      7. On success, display verified server details, save configuration locally, and return.

    Returns:
      (verified_server_url: str, workstation_name: str)

    Raises:
      SystemExit: if the user chooses to exit or non-interactive connectivity fails.
    """
    cfg = config_manager.config
    has_saved_file = cfg.config_file_path.is_file()

    # Determine saved defaults
    saved_url = cfg.server_url.strip() if (has_saved_file and cfg.server_url.strip()) else None
    # If the saved config is just stock localhost but there is no saved file on disk,
    # do not assume localhost is correct for a remote workstation (PRD Requirement 1.3)
    if not has_saved_file and saved_url == "http://localhost:8000":
        saved_url = None

    default_device_name = get_default_workstation_name(cfg.device_name if has_saved_file else None)

    current_server_url: Optional[str] = None
    if cli_server_url:
        try:
            current_server_url = normalize_server_url(cli_server_url)
        except ValueError as exc:
            print_func(f"[!] Warning: Invalid CLI --server URL: {exc}")
            current_server_url = None

    current_device_name: Optional[str] = cli_device_name.strip() if cli_device_name else None

    # If both CLI arguments provided and non-interactive mode requested:
    is_fully_cli = (cli_server_url is not None) and (cli_device_name is not None)
    if non_interactive or (is_fully_cli and not sys.stdin.isatty()):
        target_url = current_server_url or normalize_server_url(saved_url or "http://localhost:8000")
        target_name = current_device_name or default_device_name

        print_func(f"Verifying Central Server connectivity: {target_url} ...")
        is_healthy, detail = health_checker(target_url, DEFAULT_TIMEOUT_SEC)
        if is_healthy:
            config_manager.update({"server_url": target_url, "device_name": target_name}, save_to_disk=True)
            return target_url, target_name
        else:
            display_connection_failure(target_url, str(detail), print_func=print_func)
            print_func("[!] Non-interactive mode: Exiting due to connectivity failure.")
            sys.exit(1)

    # Interactive flow
    display_welcome_banner(print_func=print_func)

    prompt_for_url = current_server_url is None
    prompt_for_name = current_device_name is None

    while True:
        # Prompt for Central Server URL
        if prompt_for_url:
            while True:
                if saved_url:
                    prompt = f"Enter Central Server IP or URL [default: {saved_url}]: "
                else:
                    prompt = "Enter Central Server IP or URL (e.g. 192.168.1.100 or http://192.168.1.100:8000): "

                try:
                    raw_input = input_func(prompt).strip()
                except (EOFError, KeyboardInterrupt):
                    print_func("\nSetup cancelled. Exiting.")
                    sys.exit(0)

                if not raw_input:
                    if saved_url:
                        raw_input = saved_url
                    else:
                        print_func("[!] Server address is required. Please enter an IP or URL.")
                        continue

                try:
                    current_server_url = normalize_server_url(raw_input)
                    break
                except ValueError as exc:
                    print_func(f"[!] Invalid server address: {exc}")
                    continue

        # Prompt for Workstation Name
        if prompt_for_name:
            while True:
                prompt = f"Enter Workstation / Desk Name [default: {default_device_name}]: "
                try:
                    raw_name = input_func(prompt).strip()
                except (EOFError, KeyboardInterrupt):
                    print_func("\nSetup cancelled. Exiting.")
                    sys.exit(0)

                current_device_name = raw_name if raw_name else default_device_name
                if current_device_name:
                    break
                print_func("[!] Workstation name cannot be empty.")

        assert current_server_url is not None
        assert current_device_name is not None

        # Verify Connectivity
        print_func(f"\nTesting connection to Central Server: {current_server_url} ...")
        is_healthy, detail = health_checker(current_server_url, DEFAULT_TIMEOUT_SEC)

        if is_healthy:
            # Display verified connection information
            server_status = "Healthy"
            if isinstance(detail, dict):
                server_name = detail.get("server", "EdgeErgo Central Server")
                server_ver = detail.get("version", "0.1.0")
                server_status = f"Healthy ({server_name} v{server_ver})"

            print_func("\n" + "=" * 80)
            print_func(" [✓] Central Server Connected Successfully!")
            print_func(f"     Server URL:        {current_server_url}")
            print_func(f"     Connection Status: {server_status}")
            print_func(f"     Workstation Name:  {current_device_name}")
            print_func("=" * 80)
            print_func("Initializing local AI vision engines, camera, and awareness overlay...\n")

            # Persist settings locally
            config_manager.update(
                {
                    "server_url": current_server_url,
                    "device_name": current_device_name,
                },
                save_to_disk=True,
            )
            return current_server_url, current_device_name

        # Connection failed
        display_connection_failure(current_server_url, str(detail), print_func=print_func)

        # Failure resolution options
        while True:
            print_func("\nConnection Options:")
            print_func("  [1] Retry connection")
            print_func("  [2] Enter a different server IP / URL")
            print_func("  [3] Exit application")

            try:
                choice = input_func("Choose an option [1/2/3]: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print_func("\nSetup cancelled. Exiting.")
                sys.exit(0)

            if choice in ("1", "retry", "r"):
                # Retry: keep current_server_url and loop to test again
                prompt_for_url = False
                prompt_for_name = False
                break
            elif choice in ("2", "change", "c"):
                # Re-prompt for URL
                prompt_for_url = True
                current_server_url = None
                break
            elif choice in ("3", "exit", "q", "quit"):
                print_func("Exiting EdgeErgo Agent. Setup cancelled.")
                sys.exit(0)
            else:
                print_func("Invalid choice. Please enter 1, 2, or 3.")
