# VibeWait

VibeWait is a Windows-only watcher that tries to detect when your editor is in
an active AI generation state. When it sees that state, it opens Instagram,
TikTok, and YouTube Shorts as browser tabs. When the generation appears to
finish, it closes those tabs and tries to refocus your editor or terminal.

## Run it

```powershell
cd C:\Users\Projects\VibeWait\VibeWait
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python vibewait.py
```

## Important note

This is still a best-effort detector, not a real VS Code or Codex plugin. It
uses window text and Windows UI automation, so you may need to tune the keyword
lists in `vibewait.py` if your editor labels generation differently.
