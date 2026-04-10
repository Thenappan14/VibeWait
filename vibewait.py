"""
VibeWait - Developer Productivity Tool
======================================
Automates the "waiting for AI to generate code" experience.
Opens social media tabs, waits for generation to complete,
then closes tabs and refocuses your editor.

Architecture is intentionally modular to support future VSCode extension integration.
"""

import webbrowser
import time
import sys
import subprocess
import psutil

# Optional imports with graceful fallback for environments without GUI support
try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False

try:
    import pygetwindow as gw
    PYGETWINDOW_AVAILABLE = True
except ImportError:
    PYGETWINDOW_AVAILABLE = False


# ---------------------------------------------------------------------------
# Configuration — easy to swap out URLs or add new ones
# ---------------------------------------------------------------------------

SOCIAL_MEDIA_URLS = [
    "https://www.instagram.com/reels/",
    "https://www.tiktok.com/foryou",
    "https://www.youtube.com/shorts/",
]

# Keywords used to find the editor window (case-insensitive)
EDITOR_WINDOW_KEYWORDS = ["visual studio code", "vscode", "code", "terminal", "cmd", "powershell"]

# Browser process names to target when closing tabs on Windows
BROWSER_PROCESS_NAMES = ["chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe"]


# ---------------------------------------------------------------------------
# 1. open_social_media()
# ---------------------------------------------------------------------------

def open_social_media(urls: list[str] = SOCIAL_MEDIA_URLS) -> None:
    """
    Opens each social media URL in the system's default browser.

    Uses Python's built-in `webbrowser` module — no external dependencies needed.
    Each URL opens as a new tab (webbrowser.open_new_tab).

    Future VSCode extension hook:
        Call this function via a subprocess or expose it through a Python language server.
    """
    print("\n🚀 Opening your vibe tabs...\n")

    for url in urls:
        webbrowser.open_new_tab(url)
        # Small delay so the browser doesn't drop tabs under heavy load
        time.sleep(0.6)
        print(f"   ✓ Opened {url}")

    print("\n✅ All tabs open. Go scroll — you've earned it.\n")


# ---------------------------------------------------------------------------
# 2. start_timer()
# ---------------------------------------------------------------------------

def start_timer(seconds: int) -> None:
    """
    Displays a live countdown in the terminal while the AI generates code.

    The countdown uses carriage return (\r) so it updates in place —
    keeps the terminal output clean rather than spamming lines.

    Args:
        seconds: Total wait time in seconds.

    Future VSCode extension hook:
        Replace the print loop with a VSCode progress notification
        using the `vscode.window.withProgress` API.
    """
    print(f"⏳ Timer started: {seconds} seconds\n")

    for remaining in range(seconds, 0, -1):
        bar_length = 30
        filled = int(bar_length * (seconds - remaining) / seconds)
        bar = "█" * filled + "░" * (bar_length - filled)
        sys.stdout.write(f"\r   [{bar}] {remaining:>4}s remaining  ")
        sys.stdout.flush()
        time.sleep(1)

    # Clear the progress line and signal completion
    sys.stdout.write(f"\r   [{'█' * 30}]    0s remaining  \n")
    sys.stdout.flush()
    print("\n🎉 Generation complete! Bringing you back to work...\n")


# ---------------------------------------------------------------------------
# 3. close_tabs()
# ---------------------------------------------------------------------------

def close_tabs(browser_processes: list[str] = BROWSER_PROCESS_NAMES) -> None:
    """
    Attempts to close the social media browser tabs using two strategies:

    Strategy A — Keyboard shortcut (preferred):
        Uses pyautogui to send Ctrl+W repeatedly, closing the active tab
        in most Chromium-based and Firefox browsers. Sends Ctrl+W once
        per social media URL we opened.

    Strategy B — Process termination (nuclear option, disabled by default):
        Uses psutil to find and kill browser processes entirely.
        Only uncomment this if Strategy A is insufficient for your workflow.

    Why not Strategy B by default?
        Killing the whole browser nukes ALL tabs, not just our social ones.
        Most developers have other work open in the browser.

    Future VSCode extension hook:
        The extension can maintain a list of tab handles opened via the
        `vscode.env.openExternal` API and close them programmatically.
    """
    # Strategy A: Close tabs via keyboard shortcut
    if PYAUTOGUI_AVAILABLE:
        print("🗂  Closing social media tabs (Ctrl+W × {})...".format(len(SOCIAL_MEDIA_URLS)))

        for i in range(len(SOCIAL_MEDIA_URLS)):
            try:
                pyautogui.hotkey("ctrl", "w")
                time.sleep(0.4)  # Give the browser time to process each close
                print(f"   ✓ Closed tab {i + 1}/{len(SOCIAL_MEDIA_URLS)}")
            except Exception as e:
                print(f"   ⚠ Could not close tab {i + 1}: {e}")
    else:
        print("⚠  pyautogui not available — skipping tab close.")
        print("   Install it with: pip install pyautogui\n")

    # -----------------------------------------------------------------
    # Strategy B: Kill browser processes entirely (opt-in, use carefully)
    # Uncomment the block below if you want the nuclear option.
    # -----------------------------------------------------------------
    # print("🔪 Terminating browser processes...")
    # for proc in psutil.process_iter(["pid", "name"]):
    #     if proc.info["name"].lower() in [b.lower() for b in browser_processes]:
    #         try:
    #             proc.kill()
    #             print(f"   ✓ Killed {proc.info['name']} (PID {proc.info['pid']})")
    #         except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
    #             print(f"   ⚠ Could not kill {proc.info['name']}: {e}")


# ---------------------------------------------------------------------------
# 4. focus_editor()
# ---------------------------------------------------------------------------

def focus_editor(keywords: list[str] = EDITOR_WINDOW_KEYWORDS) -> bool:
    """
    Brings the developer's editor or terminal window into focus.

    Search order:
        1. pygetwindow: scans open windows for keyword matches (VSCode, terminal, etc.)
        2. subprocess fallback: uses PowerShell's AppActivate as a last resort.

    Args:
        keywords: Window title substrings to search for (case-insensitive).

    Returns:
        True if a window was successfully focused, False otherwise.

    Future VSCode extension hook:
        This function becomes a no-op — the extension itself runs inside VSCode,
        so it can call `vscode.window.showInformationMessage` or activate directly.
    """
    print("🎯 Focusing your editor window...\n")

    # Strategy A: Use pygetwindow to find and activate the editor
    if PYGETWINDOW_AVAILABLE:
        all_windows = gw.getAllTitles()

        for keyword in keywords:
            matches = [title for title in all_windows if keyword.lower() in title.lower()]
            if matches:
                try:
                    target = gw.getWindowsWithTitle(matches[0])[0]
                    target.activate()
                    print(f"   ✓ Focused window: \"{matches[0]}\"\n")
                    return True
                except Exception as e:
                    print(f"   ⚠ Found window but couldn't activate it: {e}")

    # Strategy B: PowerShell fallback using AppActivate
    # Works when pygetwindow fails due to permission issues or minimized windows
    print("   ↩ Trying PowerShell fallback...")

    for keyword in keywords:
        try:
            ps_command = (
                f'(New-Object -ComObject WScript.Shell).AppActivate("{keyword}")'
            )
            result = subprocess.run(
                ["powershell", "-Command", ps_command],
                capture_output=True,
                timeout=3,
            )
            if result.returncode == 0:
                print(f"   ✓ Activated via PowerShell: \"{keyword}\"\n")
                return True
        except Exception:
            continue

    print("   ⚠ Could not auto-focus editor. Click your editor manually.\n")
    return False


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def get_duration_from_user() -> int:
    """
    Prompts the user for generation wait time with input validation.

    Returns:
        A positive integer representing seconds to wait.
    """
    print("\n" + "=" * 50)
    print("  VibeWait 🎧  — AI wait time productivity tool")
    print("=" * 50)
    print("\nWhile your AI generates code, go scroll socials.")
    print("VibeWait will bring you back when it's done.\n")

    while True:
        try:
            raw = input("⏱  How many seconds will the AI generation take? › ").strip()
            seconds = int(raw)
            if seconds <= 0:
                print("   Please enter a positive number of seconds.\n")
                continue
            return seconds
        except ValueError:
            print("   That doesn't look like a number. Try again.\n")
        except (KeyboardInterrupt, EOFError):
            print("\n\n👋 VibeWait cancelled. Back to work!\n")
            sys.exit(0)


def run() -> None:
    """
    Main orchestration function.

    Execution flow:
        1. Ask user for generation duration
        2. Open social media tabs
        3. Start countdown timer
        4. Close social media tabs
        5. Refocus editor

    This function is the single entry point — easy to call from a
    VSCode extension by importing this module and calling vibewait.run().
    """
    duration = get_duration_from_user()

    print(f"\n🕐 Starting {duration}-second vibe session...\n")

    # Step 1: Open the social media URLs
    open_social_media()

    # Step 2: Wait for AI generation to complete
    start_timer(duration)

    # Step 3: Close the tabs we opened
    close_tabs()

    # Step 4: Bring editor/terminal back into focus
    focus_editor()

    print("=" * 50)
    print("  ✅ Session complete. Time to review that code!")
    print("=" * 50 + "\n")


# ---------------------------------------------------------------------------
# Script entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    run()
