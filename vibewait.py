"""
VibeWait - automatic AI wait-time monitor for Windows.

The script watches editor and terminal windows for text that looks like an
active AI generation state. When it sees one, it opens the configured social
media tabs. When the generation state disappears, it closes those tabs and
tries to refocus the editor.

This is a best-effort detector. It does not hook directly into VS Code or
Codex yet, so the keyword lists below are the main tuning knobs.
"""

from __future__ import annotations

import subprocess
import sys
import time
import webbrowser
from dataclasses import dataclass


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

try:
    from pywinauto import Desktop

    PYWINAUTO_AVAILABLE = True
except ImportError:
    PYWINAUTO_AVAILABLE = False


SOCIAL_MEDIA_URLS = [
    "https://www.instagram.com/reels/",
    "https://www.tiktok.com/foryou",
    "https://www.youtube.com/shorts/",
]

EDITOR_WINDOW_KEYWORDS = [
    "visual studio code",
    "vscode",
    "cursor",
    "windsurf",
    "terminal",
    "powershell",
    "cmd",
    "codex",
]

AI_TOOL_KEYWORDS = [
    "codex",
    "copilot",
    "cursor",
    "chatgpt",
    "openai",
    "cline",
    "roo",
]

GENERATION_KEYWORDS = [
    "generating",
    "thinking",
    "working",
    "responding",
    "streaming",
    "processing",
    "writing",
    "planning",
    "running",
    "executing",
]

BROWSER_WINDOW_KEYWORDS = [
    "instagram",
    "tiktok",
    "youtube",
    "shorts",
    "reels",
]

POLL_INTERVAL_SECONDS = 2.0
START_THRESHOLD_POLLS = 2
STOP_THRESHOLD_POLLS = 2
MAX_WINDOW_TEXT_ITEMS = 120


@dataclass
class DetectionResult:
    generating: bool
    evidence: list[str]


def normalize_text(value: str) -> str:
    return " ".join(value.lower().split())


def contains_any(text: str, patterns: list[str]) -> bool:
    return any(pattern in text for pattern in patterns)


def open_social_media(urls: list[str] = SOCIAL_MEDIA_URLS) -> None:
    print("\nOpening your vibe tabs...\n")

    for url in urls:
        webbrowser.open_new_tab(url)
        time.sleep(0.6)
        print(f"   Opened {url}")

    print("\nAll tabs open. Scroll until the code is ready.\n")


def focus_first_window(keywords: list[str]) -> bool:
    if not PYGETWINDOW_AVAILABLE:
        return False

    for title in gw.getAllTitles():
        normalized_title = normalize_text(title)
        if contains_any(normalized_title, keywords):
            try:
                target = gw.getWindowsWithTitle(title)[0]
                target.activate()
                return True
            except Exception:
                continue

    return False


def close_tabs() -> None:
    if not focus_first_window(BROWSER_WINDOW_KEYWORDS):
        print("Could not find a browser tab to focus before closing tabs.")

    if PYAUTOGUI_AVAILABLE:
        print("Closing social media tabs...")
        for index in range(len(SOCIAL_MEDIA_URLS)):
            try:
                pyautogui.hotkey("ctrl", "w")
                time.sleep(0.4)
                print(f"   Closed tab {index + 1}/{len(SOCIAL_MEDIA_URLS)}")
            except Exception as exc:
                print(f"   Could not close tab {index + 1}: {exc}")
    else:
        print("pyautogui is not installed, so tabs were left open.")
        print("Install it with: pip install pyautogui\n")


def focus_editor() -> bool:
    print("Focusing your editor window...\n")

    if focus_first_window(EDITOR_WINDOW_KEYWORDS):
        print("   Focused an editor or terminal window.\n")
        return True

    print("   Trying PowerShell fallback...")

    for keyword in EDITOR_WINDOW_KEYWORDS:
        try:
            ps_command = f'(New-Object -ComObject WScript.Shell).AppActivate("{keyword}")'
            result = subprocess.run(
                ["powershell", "-Command", ps_command],
                capture_output=True,
                timeout=3,
            )
            if result.returncode == 0:
                print(f'   Activated via PowerShell: "{keyword}"\n')
                return True
        except Exception:
            continue

    print("   Could not auto-focus the editor. Click it manually.\n")
    return False


def iter_candidate_windows():
    if not PYWINAUTO_AVAILABLE:
        return []

    candidates = []

    try:
        windows = Desktop(backend="uia").windows()
    except Exception:
        return []

    for window in windows:
        try:
            title = window.window_text().strip()
        except Exception:
            continue

        if not title:
            continue

        normalized_title = normalize_text(title)
        if contains_any(normalized_title, EDITOR_WINDOW_KEYWORDS + AI_TOOL_KEYWORDS):
            candidates.append(window)

    return candidates


def collect_window_text(window) -> str:
    texts: list[str] = []

    try:
        title = window.window_text().strip()
    except Exception:
        title = ""

    if title:
        texts.append(title)

    try:
        descendants = window.descendants()
    except Exception:
        descendants = []

    for element in descendants[:MAX_WINDOW_TEXT_ITEMS]:
        try:
            text = element.window_text().strip()
        except Exception:
            continue

        if text:
            texts.append(text)

    unique_texts = list(dict.fromkeys(texts))
    return normalize_text(" ".join(unique_texts))


def detect_generation() -> DetectionResult:
    evidence: list[str] = []

    for window in iter_candidate_windows():
        combined_text = collect_window_text(window)
        if not combined_text:
            continue

        if contains_any(combined_text, AI_TOOL_KEYWORDS) and contains_any(
            combined_text, GENERATION_KEYWORDS
        ):
            try:
                title = window.window_text().strip() or "Unnamed window"
            except Exception:
                title = "Unnamed window"
            evidence.append(title)

    if evidence:
        return DetectionResult(generating=True, evidence=evidence)

    if PYGETWINDOW_AVAILABLE:
        for title in gw.getAllTitles():
            normalized_title = normalize_text(title)
            if contains_any(normalized_title, AI_TOOL_KEYWORDS) and contains_any(
                normalized_title, GENERATION_KEYWORDS
            ):
                evidence.append(title)

    return DetectionResult(generating=bool(evidence), evidence=evidence)


def print_banner() -> None:
    print("\n" + "=" * 60)
    print("  VibeWait - automatic AI wait-time watcher")
    print("=" * 60)
    print("\nKeep this script running while you use Codex in your editor.")
    print("It will watch for AI generation text and open socials automatically.")
    print("Press Ctrl+C to stop the watcher.\n")

    if not PYWINAUTO_AVAILABLE:
        print("Warning: pywinauto is not installed.")
        print("The detector will be much less accurate without it.\n")


def watch_for_generation() -> None:
    print_banner()

    active_session = False
    positive_streak = 0
    negative_streak = 0
    last_status = "idle"

    try:
        while True:
            result = detect_generation()

            if result.generating:
                positive_streak += 1
                negative_streak = 0
            else:
                negative_streak += 1
                positive_streak = 0

            if not active_session and positive_streak >= START_THRESHOLD_POLLS:
                trigger = result.evidence[0] if result.evidence else "AI window"
                print(f"\nDetected AI generation in: {trigger}")
                open_social_media()
                active_session = True
                last_status = "active"

            elif active_session and negative_streak >= STOP_THRESHOLD_POLLS:
                print("\nAI generation looks finished. Returning you to work...\n")
                close_tabs()
                focus_editor()
                active_session = False
                last_status = "idle"

            else:
                current_status = "active" if active_session else "watching"
                if current_status != last_status:
                    if current_status == "watching":
                        print("Watching for a new AI generation...")
                    last_status = current_status

            time.sleep(POLL_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("\n\nStopping VibeWait.")
        if active_session:
            close_tabs()
        focus_editor()
        print("Back to work.\n")
        sys.exit(0)


def run() -> None:
    watch_for_generation()


if __name__ == "__main__":
    run()
