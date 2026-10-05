"""Ordered region contract shared by config, UI, capture and recovery."""
import copy

RESERVED = {"NEXT", "PROGRESS"}
BROWSERS = {"msedge.exe": "Edge", "chrome.exe": "Chrome", "brave.exe": "Brave", "firefox.exe": "Firefox"}
NAVIGATION = ("next_button", "manual", "none")


def navigation(cfg):
    mode = cfg.get("navigation_mode", "next_button")
    if mode not in NAVIGATION:
        raise ValueError("navigation_mode: next_button, manual oder none.")
    return mode


def capture_rects(cfg):
    if "regions" in cfg:
        regions = cfg["regions"]
        if not isinstance(regions, list) or not regions:
            raise ValueError("regions muss mindestens ein Rechteck enthalten.")
        return copy.deepcopy(regions)
    from .geometry import right_rect
    return [copy.deepcopy(cfg["left_rect"]), copy.deepcopy(right_rect(cfg))]


def capture_names(rects):
    return [name for name in rects if name not in RESERVED]


def selection(cfg):
    names = [f"REGION_{i:03d}" for i in range(1, len(capture_rects(cfg))+1)] if "regions" in cfg else ["LEFT", "RIGHT"]
    result = dict(zip(names, capture_rects(cfg)))
    result.update(NEXT=copy.deepcopy(cfg.get("button_rect")), PROGRESS=copy.deepcopy(cfg.get("progress_rect")))
    return result


def browser_name(executable, requested="auto"):
    from pathlib import PureWindowsPath
    found = BROWSERS.get(PureWindowsPath(executable).name.lower())
    if not found or (requested != "auto" and requested.casefold() != found.casefold()):
        raise ValueError("Ziel muss Brave, Edge, Firefox oder Chrome sein und zur Browserwahl passen.")
    return found


def image_names(cfg, index):
    if "regions" not in cfg:
        return [f"{index:06d}_left.png", f"{index:06d}_right.png"]
    return [f"{index:06d}_region_{i:03d}.png" for i in range(1, len(capture_rects(cfg))+1)]
