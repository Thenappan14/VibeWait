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

import hashlib
import os
import subprocess
import sys
import tempfile
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


SOCIAL_MEDIA_TARGETS = [
    ("Instagram", "https://www.instagram.com/reels/", ["instagram", "reels"]),
    ("TikTok", "https://www.tiktok.com/foryou", ["tiktok"]),
    ("YouTube Shorts", "https://www.youtube.com/shorts/", ["youtube", "shorts"]),
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

IN_PROGRESS_KEYWORDS = [
    "stop",
    "cancel",
    "agent status",
    "interrupt",
    "abort",
]

BROWSER_WINDOW_KEYWORDS = [
    "instagram",
    "tiktok",
    "youtube",
    "shorts",
    "reels",
]

POLL_INTERVAL_SECONDS = 2.0
START_THRESHOLD_POLLS = 4
STOP_THRESHOLD_POLLS = 3
MAX_STABLE_POLLS_DURING_SESSION = 4
POST_SESSION_COOLDOWN_POLLS = 5
MAX_WINDOW_TEXT_ITEMS = 400
DEBUG_ENABLED = True
DEBUG_TEXT_PREVIEW_LENGTH = 220
SIGNATURE_PREVIEW_LENGTH = 1200


@dataclass
class DetectionResult:
    generating: bool
    evidence: list[str]
    debug_lines: list[str]
    tracked_ai_signature: str
    tracked_ai_title: str


def normalize_text(value: str) -> str:
    return " ".join(value.lower().split())


def contains_any(text: str, patterns: list[str]) -> bool:
    return any(pattern in text for pattern in patterns)


def matching_keywords(text: str, patterns: list[str]) -> list[str]:
    return [pattern for pattern in patterns if pattern in text]


def debug_log(message: str) -> None:
    if DEBUG_ENABLED:
        print(f"[debug] {message}")


def make_text_signature(text: str) -> str:
    if not text:
        return ""
    return hashlib.sha1(text[:SIGNATURE_PREVIEW_LENGTH].encode("utf-8", errors="ignore")).hexdigest()


def is_short_ui_label(text: str) -> bool:
    words = text.split()
    return bool(words) and len(text) <= 40 and len(words) <= 4


def open_social_media() -> None:
    print("\nOpening your vibe screen...\n")
    
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VibeWait - Scroll Zone</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            background: #0a0a0b;
            color: #e8e8ec;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            height: 100vh;
            overflow: hidden;
        }
        
        .container {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            height: 100vh;
            gap: 1px;
            background: #1a1a1f;
        }
        
        .panel {
            background: #111114;
            border-left: 1px solid #222228;
            display: flex;
            flex-direction: column;
            position: relative;
            overflow: hidden;
        }
        
        .panel:first-child {
            border-left: none;
        }
        
        .panel-header {
            background: #1a1a1f;
            padding: 12px 16px;
            font-weight: 600;
            font-size: 13px;
            border-bottom: 1px solid #222228;
            display: flex;
            align-items: center;
            justify-content: space-between;
            z-index: 10;
        }
        
        .panel-ig .panel-header { color: #e1306c; }
        .panel-tt .panel-header { color: #69c9d0; }
        .panel-yt .panel-header { color: #ff0000; }
        
        .panel-content {
            flex: 1;
            overflow-y: auto;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        
        .link-box {
            text-align: center;
        }
        
        .link-box h2 {
            font-size: 18px;
            margin-bottom: 16px;
            font-weight: 600;
        }
        
        .app-link {
            display: inline-block;
            padding: 12px 28px;
            background: linear-gradient(135deg, #333333 0%, #444444 100%);
            color: #fff;
            text-decoration: none;
            border-radius: 6px;
            font-weight: 500;
            font-size: 14px;
            border: 1px solid #555555;
            transition: all 0.2s ease;
            cursor: pointer;
        }
        
        .app-link:hover {
            background: linear-gradient(135deg, #444444 0%, #555555 100%);
            border-color: #666666;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        }
        
        .timer {
            position: fixed;
            top: 12px;
            right: 12px;
            background: #3cf0a0;
            color: #000;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            z-index: 1000;
            font-family: 'Courier New', monospace;
        }
        
        /* Scrollbar styling */
        .panel-content::-webkit-scrollbar {
            width: 8px;
        }
        
        .panel-content::-webkit-scrollbar-track {
            background: #1a1a1f;
        }
        
        .panel-content::-webkit-scrollbar-thumb {
            background: #333333;
            border-radius: 4px;
        }
        
        .panel-content::-webkit-scrollbar-thumb:hover {
            background: #444444;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="panel panel-ig">
            <div class="panel-header">
                <span>📸 Instagram Reels</span>
            </div>
            <div class="panel-content">
                <div class="link-box">
                    <h2>Instagram Reels</h2>
                    <a href="https://www.instagram.com/reels/" target="_blank" class="app-link">Open in New Tab →</a>
                </div>
            </div>
        </div>
        
        <div class="panel panel-tt">
            <div class="panel-header">
                <span>🎵 TikTok</span>
            </div>
            <div class="panel-content">
                <div class="link-box">
                    <h2>TikTok</h2>
                    <a href="https://www.tiktok.com/foryou" target="_blank" class="app-link">Open in New Tab →</a>
                </div>
            </div>
        </div>
        
        <div class="panel panel-yt">
            <div class="panel-header">
                <span>▶️ YouTube Shorts</span>
            </div>
            <div class="panel-content">
                <div class="link-box">
                    <h2>YouTube Shorts</h2>
                    <a href="https://www.youtube.com/shorts/" target="_blank" class="app-link">Open in New Tab →</a>
                </div>
            </div>
        </div>
    </div>
    
    <div class="timer" id="timer">00:00</div>
    
    <script>
        let elapsed = 0;
        setInterval(() => {
            elapsed++;
            const m = String(Math.floor(elapsed / 60)).padStart(2, '0');
            const s = String(elapsed % 60).padStart(2, '0');
            document.getElementById('timer').textContent = m + ':' + s;
        }, 1000);
    </script>
</body>
</html>"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
        f.write(html_content)
        temp_path = f.name
    
    viewer_url = "file:///" + temp_path.replace("\\", "/")
    webbrowser.open(viewer_url)
    print("   Opened all three socials in split-screen view.\n")
    print("Your vibe screen is ready. Scroll until the code is ready.\n")


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


def get_window_titles() -> list[str]:
    if not PYGETWINDOW_AVAILABLE:
        return []

    try:
        return [title.strip() for title in gw.getAllTitles() if title and title.strip()]
    except Exception:
        return []


def get_active_window_title() -> str:
    if not PYGETWINDOW_AVAILABLE:
        return ""

    try:
        active_window = gw.getActiveWindow()
    except Exception:
        return ""

    if not active_window:
        return ""

    try:
        return (active_window.title or "").strip()
    except Exception:
        return ""


def close_tabs() -> None:
    if not focus_first_window(BROWSER_WINDOW_KEYWORDS):
        print("Could not find browser window to close.")

    if PYAUTOGUI_AVAILABLE:
        print("Closing vibe screen...")
        try:
            pyautogui.hotkey("ctrl", "w")
            time.sleep(0.4)
            print("   Closed vibe screen.")
        except Exception as exc:
            print(f"   Could not close: {exc}")
    else:
        print("pyautogui not installed. Browser window was left open.")
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


def collect_window_text_items(window) -> list[str]:
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

    return list(dict.fromkeys(texts))


def detect_generation() -> DetectionResult:
    evidence: list[str] = []
    debug_lines: list[str] = []
    tracked_ai_signature = ""
    tracked_ai_title = ""
    active_title = get_active_window_title()

    for window in iter_candidate_windows():
        text_items = collect_window_text_items(window)
        if not text_items:
            continue

        normalized_items = [normalize_text(item) for item in text_items if item.strip()]
        combined_text = " ".join(normalized_items)
        short_ui_items = [item for item in normalized_items if is_short_ui_label(item)]
        short_ui_text = " ".join(short_ui_items)

        ai_matches = matching_keywords(combined_text, AI_TOOL_KEYWORDS)
        generation_matches = matching_keywords(short_ui_text, GENERATION_KEYWORDS)
        progress_matches = matching_keywords(short_ui_text, IN_PROGRESS_KEYWORDS)

        try:
            title = window.window_text().strip() or "Unnamed window"
        except Exception:
            title = "Unnamed window"

        preview = combined_text[:DEBUG_TEXT_PREVIEW_LENGTH]
        debug_lines.append(
            f'UIA window="{title}" ai={ai_matches or ["-"]} gen={generation_matches or ["-"]} '
            f'progress={progress_matches or ["-"]} '
            f'text="{preview}"'
        )

        if ai_matches and not tracked_ai_title:
            tracked_ai_title = title
            tracked_ai_signature = make_text_signature(short_ui_text or combined_text)

        if title == active_title and ai_matches:
            tracked_ai_title = title
            tracked_ai_signature = make_text_signature(short_ui_text or combined_text)

        if ai_matches and generation_matches:
            evidence.append(title)

    if evidence:
        return DetectionResult(
            generating=True,
            evidence=evidence,
            debug_lines=debug_lines,
            tracked_ai_signature=tracked_ai_signature,
            tracked_ai_title=tracked_ai_title,
        )

    all_titles = get_window_titles()

    if active_title:
        debug_lines.append(f'Active window="{active_title}"')

    for title in all_titles:
        normalized_title = normalize_text(title)
        editor_matches = matching_keywords(normalized_title, EDITOR_WINDOW_KEYWORDS)
        ai_matches = matching_keywords(normalized_title, AI_TOOL_KEYWORDS)
        generation_matches = matching_keywords(normalized_title, GENERATION_KEYWORDS)
        progress_matches = matching_keywords(normalized_title, IN_PROGRESS_KEYWORDS)

        if editor_matches or ai_matches or generation_matches or progress_matches:
            debug_lines.append(
                f'Title window="{title}" editor={editor_matches or ["-"]} '
                f'ai={ai_matches or ["-"]} gen={generation_matches or ["-"]} '
                f'progress={progress_matches or ["-"]}'
            )

        if ai_matches and generation_matches:
            evidence.append(title)

    if not PYWINAUTO_AVAILABLE:
        if any(contains_any(normalize_text(title), EDITOR_WINDOW_KEYWORDS) for title in all_titles):
            debug_lines.append(
                "pywinauto is missing, so VibeWait can only read window titles right now."
            )
            debug_lines.append(
                "Install it with: pip install pywinauto"
            )
        elif all_titles:
            debug_lines.append(
                "Windows were found, but none matched the editor/AI keywords yet."
            )
        else:
            debug_lines.append(
                "No window titles were returned by pygetwindow."
            )

    if not debug_lines:
        debug_lines.append("No candidate editor/AI windows were found.")

    return DetectionResult(
        generating=bool(evidence),
        evidence=evidence,
        debug_lines=debug_lines,
        tracked_ai_signature=tracked_ai_signature,
        tracked_ai_title=tracked_ai_title,
    )


def print_banner() -> None:
    print("\n" + "=" * 60)
    print("  VibeWait - automatic AI wait-time watcher")
    print("=" * 60)
    print("\nKeep this script running while you use Codex in your editor.")
    print("It will watch for AI generation text and open socials automatically.")
    print("Press Ctrl+C to stop the watcher.\n")
    debug_log("Debug logging is enabled.")

    if not PYWINAUTO_AVAILABLE:
        print("Warning: pywinauto is not installed.")
        print("The detector will be much less accurate without it.\n")


def watch_for_generation() -> None:
    print_banner()

    active_session = False
    positive_streak = 0
    negative_streak = 0
    last_status = "idle"
    last_active_ai_signature = ""
    last_active_ai_title = ""
    signature_change_streak = 0
    stable_signature_streak = 0
    cooldown_polls_remaining = 0

    try:
        while True:
            result = detect_generation()
            signature_changed = (
                bool(result.tracked_ai_signature)
                and result.tracked_ai_title == last_active_ai_title
                and result.tracked_ai_signature != last_active_ai_signature
            )

            if result.tracked_ai_signature and result.tracked_ai_title:
                if signature_changed:
                    signature_change_streak += 1
                    stable_signature_streak = 0
                else:
                    signature_change_streak = 0
                    stable_signature_streak += 1
                last_active_ai_signature = result.tracked_ai_signature
                last_active_ai_title = result.tracked_ai_title
            else:
                signature_change_streak = 0
                stable_signature_streak = 0

            inferred_generation = result.generating
            session_finished_by_stability = (
                active_session
                and stable_signature_streak >= MAX_STABLE_POLLS_DURING_SESSION
            )

            debug_log(
                f"poll generating={result.generating} inferred_generation={inferred_generation} "
                f"active_session={active_session} positive_streak={positive_streak} "
                f"negative_streak={negative_streak} signature_change_streak={signature_change_streak} "
                f"stable_signature_streak={stable_signature_streak}"
            )
            for line in result.debug_lines:
                debug_log(line)
            if signature_changed and result.tracked_ai_title:
                debug_log(
                    f'Tracked AI window text changed: "{result.tracked_ai_title}"'
                )
            if session_finished_by_stability:
                debug_log("Active AI window has been stable long enough to treat the run as finished.")
            if cooldown_polls_remaining > 0:
                debug_log(f"cooldown_polls_remaining={cooldown_polls_remaining}")

            if inferred_generation:
                positive_streak += 1
                negative_streak = 0
            else:
                negative_streak += 1
                positive_streak = 0

            if (
                not active_session
                and cooldown_polls_remaining == 0
                and positive_streak >= START_THRESHOLD_POLLS
            ):
                trigger = result.evidence[0] if result.evidence else result.tracked_ai_title or "AI window"
                print(f"\nDetected AI generation in: {trigger}")
                open_social_media()
                active_session = True
                last_status = "active"
                stable_signature_streak = 0

            elif active_session and (
                negative_streak >= STOP_THRESHOLD_POLLS or session_finished_by_stability
            ):
                print("\nAI generation looks finished. Returning you to work...\n")
                close_tabs()
                focus_editor()
                active_session = False
                last_status = "idle"
                stable_signature_streak = 0
                signature_change_streak = 0
                positive_streak = 0
                negative_streak = 0
                cooldown_polls_remaining = POST_SESSION_COOLDOWN_POLLS

            else:
                current_status = "active" if active_session else "watching"
                if current_status != last_status:
                    if current_status == "watching":
                        print("Watching for a new AI generation...")
                    last_status = current_status

            if cooldown_polls_remaining > 0:
                cooldown_polls_remaining -= 1

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
