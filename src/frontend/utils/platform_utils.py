"""Platform and window utilities."""

from __future__ import annotations

import platform
import subprocess
import importlib
from typing import Tuple

from kivy.clock import Clock

from shared.logging_config import logger


def _window():
    """Lazily import Kivy Window to avoid import-time GL initialization."""
    from kivy.core.window import Window as KivyWindow

    return KivyWindow


def diagnose_macos_issues() -> None:
    """Diagnose common macOS issues that cause hangs."""
    if platform.system() != "Darwin":
        return

    try:
        logger.info("=== macOS Compatibility Check ===")

        try:
            if importlib.util.find_spec("AppKit") is None:
                raise ImportError
            logger.info("✓ AppKit available")
        except ImportError:
            logger.info("⚠ AppKit not available (install pyobjc-framework-Cocoa)")

        try:
            if importlib.util.find_spec("Quartz") is None:
                raise ImportError
            logger.info("✓ Quartz available")
        except ImportError:
            logger.info("⚠ Quartz not available (install pyobjc-framework-Quartz)")

        try:
            result = subprocess.run(
                ["system_profiler", "SPHardwareDataType"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if result.returncode == 0:
                logger.info("✓ system_profiler responsive")
            else:
                logger.info("⚠ system_profiler returned error")
        except subprocess.TimeoutExpired:
            logger.info("⚠ system_profiler hanging (this was causing your issue!)")
        except Exception as exc:  # pragma: no cover - best-effort diagnostics
            logger.info("⚠ system_profiler error: %s", exc)

        logger.info("=== End Compatibility Check ===")

    except Exception as exc:  # pragma: no cover
        logger.warning("Error in macOS diagnostics: %s", exc)


def get_screen_resolution() -> Tuple[int, int]:
    """Get screen resolution using fast, reliable methods that don't hang on macOS."""
    try:
        system = platform.system()

        if system == "Darwin":
            try:
                result = subprocess.run(
                    [
                        "osascript",
                        "-e",
                        'tell application "Finder" to get bounds of window of desktop',
                    ],
                    capture_output=True,
                    text=True,
                    timeout=3,
                )
                if result.returncode == 0 and result.stdout.strip():
                    bounds = [int(x.strip()) for x in result.stdout.strip().split(", ")]
                    if len(bounds) >= 4:
                        return bounds[2], bounds[3]
            except Exception as exc:
                logger.info("osascript method failed: %s", exc)

            try:
                from Quartz import CGDisplayBounds, CGMainDisplayID  # type: ignore

                bounds = CGDisplayBounds(CGMainDisplayID())
                width = int(bounds.size.width)
                height = int(bounds.size.height)
                if width > 0 and height > 0:
                    return width, height
            except ImportError:
                logger.info("Quartz/CoreGraphics not available")
            except Exception as exc:
                logger.info("CoreGraphics method failed: %s", exc)

            try:
                from AppKit import NSScreen  # type: ignore

                main_screen = NSScreen.mainScreen()
                if main_screen:
                    frame = main_screen.frame()
                    width = int(frame.size.width)
                    height = int(frame.size.height)
                    if width > 0 and height > 0:
                        return width, height
            except ImportError:
                logger.info("AppKit not available")
            except Exception as exc:
                logger.info("AppKit method failed: %s", exc)

            try:
                import tkinter as tk

                root = tk.Tk()
                root.withdraw()
                width = root.winfo_screenwidth()
                height = root.winfo_screenheight()
                root.destroy()
                if width > 0 and height > 0:
                    return width, height
            except Exception as exc:
                logger.info("tkinter method failed: %s", exc)

            return 1920, 1080

        if system == "Windows":
            try:
                import ctypes

                user32 = ctypes.windll.user32
                return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
            except Exception:
                return 1920, 1080

        if system == "Linux":
            try:
                import tkinter as tk

                root = tk.Tk()
                root.withdraw()
                width = root.winfo_screenwidth()
                height = root.winfo_screenheight()
                root.destroy()
                return width, height
            except ImportError:
                try:
                    result = subprocess.run(
                        ["xrandr"], capture_output=True, text=True, timeout=5
                    )
                    for line in result.stdout.split("\n"):
                        if " connected" in line:
                            for part in line.split():
                                if "x" in part and "+" in part:
                                    resolution = part.split("+")[0]
                                    w, h = resolution.split("x")
                                    return int(w), int(h)
                    return 1920, 1080
                except Exception:
                    return 1920, 1080

        return 360, 640

    except Exception as exc:
        logger.warning("Could not get screen resolution: %s", exc)
        return 1920, 1080


def is_mobile_platform() -> bool:
    """Check if running on mobile platform with improved detection."""
    try:
        system = platform.system()
        if system in ["iOS", "Android"]:
            return True

        import sys

        if hasattr(sys, "platform"):
            platform_str = sys.platform.lower()
            if any(
                mobile in platform_str
                for mobile in ["ios", "android", "kivy-ios", "python-for-android"]
            ):
                return True

        try:
            from kivy.utils import platform as kivy_platform

            if kivy_platform in ["android", "ios"]:
                return True
        except ImportError:
            pass

        try:
            importlib.import_module("android")
            return True
        except ImportError:
            pass

        try:
            importlib.import_module("ios")
            return True
        except ImportError:
            pass

        machine = platform.machine().lower()
        if any(arch in machine for arch in ["arm", "aarch"]) and system not in [
            "Darwin",
            "Linux",
        ]:
            return True

        return False

    except Exception as exc:
        logger.warning("Error detecting mobile platform: %s", exc)
        return False


def validate_window_size(
    width: int, height: int, screen_width: int, screen_height: int
) -> Tuple[int, int]:
    """Validate and adjust window size to ensure it fits on screen."""
    try:
        max_width = int(screen_width * 0.95)
        max_height = int(screen_height * 0.90)

        if width > max_width:
            width = max_width
            logger.info("Adjusted window width to fit screen: %s", width)

        if height > max_height:
            height = max_height
            logger.info("Adjusted window height to fit screen: %s", height)

        width = max(width, 480)
        height = max(height, 600)
        return int(width), int(height)

    except Exception as exc:
        logger.warning("Error validating window size: %s", exc)
        return width, height


def calculate_optimal_window_size() -> Tuple[int, int]:
    """Calculate optimal window size: 85% width, 90% height on desktop; full-screen on mobile."""
    screen_width, screen_height = get_screen_resolution()
    mobile = is_mobile_platform()

    logger.info(
        "Detected screen resolution: %sx%s, Mobile: %s",
        screen_width,
        screen_height,
        mobile,
    )

    if mobile:
        return screen_width, screen_height

    target_width = int(screen_width * 0.85)
    target_height = int(screen_height * 0.90)

    min_width = 600
    max_width = 1800
    min_height = 700
    max_height = 1200

    optimal_width = max(min_width, min(target_width, max_width))
    optimal_height = max(min_height, min(target_height, max_height))

    optimal_width, optimal_height = validate_window_size(
        optimal_width, optimal_height, screen_width, screen_height
    )

    logger.info(
        "Calculated desktop window size: %sx%s (%sx%s before constraints)",
        optimal_width,
        optimal_height,
        target_width,
        target_height,
    )

    return int(optimal_width), int(optimal_height)


def set_window_on_top() -> None:
    """Set window to appear on top when opened - platform-specific best effort."""
    try:
        system = platform.system()

        if system == "Windows":
            try:
                import ctypes

                def bring_to_front(dt):
                    try:
                        window = _window()
                        hwnd = ctypes.windll.user32.FindWindowW(None, window.title)
                        if hwnd:
                            ctypes.windll.user32.ShowWindow(hwnd, 9)
                            ctypes.windll.user32.SetForegroundWindow(hwnd)
                            ctypes.windll.user32.BringWindowToTop(hwnd)
                    except Exception as exc:
                        logger.warning("Could not bring window to front: %s", exc)

                Clock.schedule_once(bring_to_front, 0.5)
            except Exception as exc:
                logger.warning("Could not set window on top (Windows): %s", exc)

        elif system == "Darwin":
            try:

                def bring_to_front_pyobjc(dt):
                    try:
                        from AppKit import NSApplication  # type: ignore

                        app = NSApplication.sharedApplication()
                        if app:
                            app.activateIgnoringOtherApps_(True)
                        return True
                    except ImportError:
                        return False
                    except Exception as exc:
                        logger.warning("PyObjC activation failed: %s", exc)
                        return False

                Clock.schedule_once(bring_to_front_pyobjc, 0.5)
            except Exception as exc:
                logger.warning("Could not set window on top (macOS): %s", exc)

        elif system == "Linux":
            try:

                def bring_to_front_linux(dt):
                    try:
                        window = _window()
                        subprocess.run(
                            ["wmctrl", "-a", window.title], check=False, timeout=2
                        )
                    except (FileNotFoundError, subprocess.TimeoutExpired):
                        logger.info("wmctrl not available or timed out")
                    except Exception as exc:
                        logger.warning(
                            "Could not bring window to front (Linux): %s", exc
                        )

                Clock.schedule_once(bring_to_front_linux, 0.5)
            except Exception as exc:
                logger.warning("Could not set window on top (Linux): %s", exc)

    except Exception as exc:
        logger.warning("Could not set window on top: %s", exc)


def set_window_basics(title: str) -> None:
    """Common logic for setting window size, title, and positioning."""
    try:
        window = _window()
        width, height = calculate_optimal_window_size()
        window.size = (width, height)
        window.title = title

        mobile = is_mobile_platform()
        if mobile:
            window.resizable = False
            window.fullscreen = "auto"
            logger.info("Mobile window configured: %sx%s (fullscreen)", width, height)
        else:
            window.resizable = True
            window.fullscreen = False
            window.minimum_width = 480
            window.minimum_height = 600
            logger.info("Desktop window configured: %sx%s", width, height)

            Clock.schedule_once(lambda dt: _position_and_focus_window(), 0.5)

    except Exception as exc:
        logger.error("Error setting up window: %s", exc)
        _fallback_window_setup()


def _position_and_focus_window() -> None:
    """Position window and bring it to front after it's created - desktop only."""
    try:
        if is_mobile_platform():
            return

        try:
            window = _window()
            screen_width, screen_height = get_screen_resolution()
            width, height = window.size
            pos_x = max(0, (screen_width - width) // 2)
            pos_y = max(0, (screen_height - height) // 2)
            window.left = pos_x
            window.top = pos_y
            logger.info("Desktop window positioned at: %s, %s (centered)", pos_x, pos_y)
        except Exception as exc:
            logger.info("Could not position window: %s", exc)

        set_window_on_top()

    except Exception as exc:
        logger.warning("Error in window positioning/focusing: %s", exc)


def _fallback_window_setup() -> None:
    from kivy.core.window import Window as KivyWindow

    if is_mobile_platform():
        KivyWindow.size = (360, 640)
        KivyWindow.fullscreen = "auto"
    else:
        KivyWindow.size = (1056, 756)
        KivyWindow.resizable = True
        KivyWindow.minimum_width = 480
        KivyWindow.minimum_height = 600
    KivyWindow.title = "Spotify Playlist Exporter - Powered by ReccoBeats"


__all__ = [
    "diagnose_macos_issues",
    "get_screen_resolution",
    "is_mobile_platform",
    "validate_window_size",
    "calculate_optimal_window_size",
    "set_window_on_top",
    "set_window_basics",
]
