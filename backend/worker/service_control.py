"""
Service lifecycle helpers — start/stop external AI services around pipeline phases.

Draw Things automation notes
──────────────────────────────
Draw Things is a Mac Catalyst app. Its Accessibility tree is only exposed when
the app is the foreground (frontmost) process. Launching it programmatically puts
it in background mode where System Events cannot reach its UI.

Strategy implemented here:
  1. Launch Draw Things (it appears in the Dock with a bounce).
  2. Show a status message asking the user to click the Dock icon once.
  3. Poll for the app becoming frontmost (NSRunningApplication.isActive).
  4. The moment it's frontmost, run an AppleScript that navigates to Settings
     and AXPresses the API Enable switch (index 6 of all checkboxes in the window).
  5. Keep polling the HTTP API until it responds.
"""
import asyncio
import subprocess
import platform

import httpx
from config import settings

# ── AppleScript: click API Enable toggle inside Draw Things Settings ──────────

_DT_ENABLE_SCRIPT = r"""
-- Draw Things is already frontmost when this runs.
delay 0.5

tell application "System Events"
    tell process "DrawThings"
        set w to window 1

        -- Navigate to Settings view (look for a "Settings" button)
        try
            set allBtns to every button of w
            repeat with btn in allBtns
                try
                    if name of btn is "Settings" then
                        click btn
                        delay 1.5
                        exit repeat
                    end if
                end try
            end repeat
        end try

        -- Scroll the settings list to the bottom so the API Enable toggle
        -- is within reach.
        try
            set sas to every scroll area of w
            repeat with sa in sas
                try
                    set vBars to every scroll bar of sa
                    if (count of vBars) >= 2 then
                        set value of item 2 of vBars to 1.0
                    else if (count of vBars) = 1 then
                        set value of item 1 of vBars to 1.0
                    end if
                end try
            end repeat
        end try
        delay 0.5

        -- AXPress the checkbox by reference — works even when off-screen
        -- because it triggers the accessibility action, not mouse coordinates.
        -- From prior inspection: checkbox 6 is the API server Enable switch.
        set allCBs to every checkbox of w
        set cbCount to count of allCBs

        set _done to false

        -- Primary: target by known index
        if cbCount >= 6 then
            set targetCB to item 6 of allCBs
            if value of targetCB is 0 then
                perform action "AXPress" of targetCB
                set _done to true
                delay 0.5
            else
                set _done to true  -- already enabled
            end if
        end if

        -- Fallback: scan all "switch"-style checkboxes
        if not _done then
            repeat with cb in allCBs
                try
                    if description of cb is "switch" and value of cb is 0 then
                        perform action "AXPress" of cb
                        delay 0.5
                    end if
                end try
            end repeat
        end if

    end tell
end tell
return "ok"
"""


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _is_draw_things_ready() -> bool:
    try:
        async with httpx.AsyncClient(timeout=2.0) as c:
            r = await c.get(f"{settings.draw_things_base_url}/")
            return r.status_code < 500
    except Exception:
        return False


def _is_draw_things_frontmost() -> bool:
    """Return True if Draw Things is the active (foreground) application."""
    try:
        result = subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to tell process "DrawThings" to frontmost'],
            capture_output=True, text=True, timeout=4,
        )
        return result.stdout.strip() == "true"
    except Exception:
        return False


def _is_draw_things_running() -> bool:
    try:
        result = subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to'
             ' (count of (processes whose name is "DrawThings")) > 0'],
            capture_output=True, text=True, timeout=3,
        )
        return result.stdout.strip() == "true"
    except Exception:
        return False


def _launch_draw_things() -> None:
    for key in ("apiServerEnabled", "enableAPIServer"):
        subprocess.run(
            ["defaults", "write", "com.liuliu.draw-things", key, "-bool", "true"],
            capture_output=True,
        )
    subprocess.Popen(
        ["open", "-a", "Draw Things"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def _enable_api_via_applescript() -> None:
    subprocess.run(
        ["osascript", "-e", _DT_ENABLE_SCRIPT],
        capture_output=True, timeout=30,
    )


# ── Public API ────────────────────────────────────────────────────────────────

async def release_ollama_model():
    """Unload the current Ollama model from RAM (keep_alive=0)."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            await c.post(
                f"{settings.ollama_base_url}/api/generate",
                json={"model": settings.ollama_model, "keep_alive": 0},
            )
    except Exception:
        pass


async def start_draw_things(on_status=None) -> bool:
    """
    Launch Draw Things and wait for its HTTP API to become ready.

    Because Draw Things (Mac Catalyst) only exposes its Accessibility UI when
    frontmost, the function:
      • Launches the app so it appears in the Dock with a bounce.
      • Prompts the user (via on_status) to click the Dock icon once.
      • Detects when the app becomes frontmost.
      • Immediately runs the AppleScript to click the API Enable toggle.
      • Returns True as soon as the HTTP API responds.
    """
    if await _is_draw_things_ready():
        return True

    if on_status:
        await on_status("Starting Draw Things...")

    loop = asyncio.get_event_loop()

    if platform.system() == "Darwin":
        if not _is_draw_things_running():
            _launch_draw_things()

    api_enable_attempted = False
    dock_prompt_ticks = set()

    for tick in range(75):           # ≤ 150 s
        await asyncio.sleep(2)

        if await _is_draw_things_ready():
            if on_status:
                await on_status("Draw Things ready ✓")
            return True

        if platform.system() != "Darwin":
            continue

        # Detect if user brought Draw Things to the foreground
        frontmost = await loop.run_in_executor(None, _is_draw_things_frontmost)

        if frontmost and not api_enable_attempted:
            if on_status:
                await on_status("Draw Things is active — enabling API server...")
            asyncio.ensure_future(
                loop.run_in_executor(None, _enable_api_via_applescript)
            )
            api_enable_attempted = True

        # Every ~10 s remind the user if the API is still not ready
        elif not frontmost and tick % 5 == 0 and tick not in dock_prompt_ticks:
            dock_prompt_ticks.add(tick)
            if on_status:
                await on_status(
                    "⚡ Draw Things is open — click it in the Dock once to enable the API server"
                )

    if on_status:
        await on_status("Draw Things API timed out — using image placeholder")
    return False


def stop_draw_things():
    """Force-quit Draw Things to free GPU/memory for the next stage."""
    try:
        subprocess.run(["pkill", "-f", "DrawThings"], capture_output=True)
    except Exception:
        pass
