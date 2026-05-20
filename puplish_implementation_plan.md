# Social Media Publish Feature

## Goal
Add a **"Publish" button** on each finished clip in the Production Gallery that opens a dropdown of available platforms (TikTok, YouTube, Instagram, X/Twitter). When the user selects a platform, the backend launches a browser-based authentication + upload flow using **Playwright stealth wrappers** (inspired by TikTokAutoUploader's Phantomwright approach).

## User Review Required

> [!IMPORTANT]
> This feature uses **browser automation** (Playwright/Phantomwright) to publish to platforms — **not official APIs**. This means:
> - First-time use per platform requires a manual login in a visible browser window
> - Session cookies are persisted locally so subsequent uploads are automatic
> - Platform ToS may consider automation a violation — use at your own risk
> - No API keys or OAuth needed

> [!WARNING]
> TikTok publishing uses `tiktokautouploader` (pip package) which requires **Node.js** on PATH. YouTube/Instagram use direct Playwright stealth automation. All publishing runs locally on your machine.

## Open Questions

> [!NOTE]
> - Should we support **scheduled publishing** (e.g., "post at 3:00 PM tomorrow")? TikTokAutoUploader supports this natively.
> - Should we add a **caption/description editor** in the publish dialog or use a default caption?

## Proposed Changes

---

### Frontend — Publish UI on Gallery Clips

#### [MODIFY] [App.jsx](file:///c:/Users/Mohamad60025/Desktop/App/utik/frontend/src/App.jsx)

1. **Add `Share2` icon** to lucide imports (for the Publish button)
2. **Add `PublishDropdown` component** — a small reusable component that:
   - Renders a "Publish" button on each clip card
   - On click, shows an animated dropdown with platform options:
     - 🎵 TikTok (via `tiktokautouploader`)
     - ▶️ YouTube (Shorts) (via Playwright)
     - 📸 Instagram (Reels) (via Playwright)
     - 🐦 X / Twitter (via Playwright)
   - Each option shows platform icon, name, and auth status (logged in / needs login)
   - On platform select → calls backend `POST /publish` endpoint
   - Shows real-time status: "Launching browser...", "Authenticating...", "Uploading...", "Published ✓"
3. **Integrate `PublishDropdown`** into the gallery clip card (next to the Download button)
4. **Add publish state tracking** — `publishStatus` state map keyed by `clip.filename + platform`

---

### Backend — Publishing Engine

#### [NEW] [publisher.py](file:///c:/Users/Mohamad60025/Desktop/App/utik/publisher.py)

A unified publishing module with platform-specific uploaders:

```python
class SocialPublisher:
    """Manages browser sessions and uploads for each platform."""
    
    async def publish_tiktok(video_path, caption, hashtags, account):
        # Uses tiktokautouploader pip package
        from tiktokautouploader import upload_tiktok
        upload_tiktok(video=video_path, description=caption,
                      accountname=account, hashtags=hashtags, headless=False)
    
    async def publish_youtube(video_path, title, description):
        # Playwright stealth → navigate to studio.youtube.com → upload flow
        
    async def publish_instagram(video_path, caption):
        # Playwright stealth → navigate to instagram.com → create reel flow
    
    async def publish_twitter(video_path, text):
        # Playwright stealth → navigate to x.com → compose tweet with media
```

Key design decisions:
- **First login is interactive** (`headless=False`) — user sees the browser, logs in manually, cookies get saved to `./sessions/{platform}/`
- **Subsequent uploads are headless** — saved cookies are reloaded
- **Session persistence** — cookie files stored in `./sessions/` directory (gitignored)
- **Status polling** — each publish job updates `sessions[session_id]["publish_status"]`

#### [MODIFY] [server.py](file:///c:/Users/Mohamad60025/Desktop/App/utik/server.py)

Add three new endpoints:

```
POST /publish              — Start a publish job (video_path, platform, caption)
GET  /publish/status/{id}  — Poll publish job status  
GET  /publish/accounts     — List authenticated platform accounts
```

Add `PublishRequest` Pydantic model and background task runner.

---

### Session & Cookie Management

#### [NEW] [sessions/](file:///c:/Users/Mohamad60025/Desktop/App/utik/sessions/)

Directory structure for persisted browser sessions:
```
sessions/
├── tiktok/
│   └── {account_name}/cookies.json
├── youtube/
│   └── cookies.json
├── instagram/
│   └── cookies.json
└── twitter/
    └── cookies.json
```

#### [MODIFY] [.gitignore](file:///c:/Users/Mohamad60025/Desktop/App/utik/.gitignore)

Add `sessions/` to prevent auth cookies from being committed.

---

## Verification Plan

### Automated Tests
- Run `pip install tiktokautouploader playwright` and `playwright install chromium`
- Start the server, verify `GET /publish/accounts` returns empty list
- Trigger `POST /publish` with TikTok, verify browser opens for login
- After login, verify cookies saved to `sessions/tiktok/`

### Manual Verification
- Open Gallery tab with a finished clip
- Click "Publish" → verify dropdown appears with 4 platform options
- Select TikTok → verify browser opens, authentication flow works
- Verify the publish status updates in real-time on the clip card
- Verify dark mode styling on the dropdown is correct
