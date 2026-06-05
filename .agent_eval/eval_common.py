import os
from pathlib import Path


def get_default_token_paths():
    # Try repository runtime path via engine.runtime_paths if available
    try:
        from engine.runtime_paths import private_runtime_file

        token = private_runtime_file("auth", ".local_token")
        yield Path(token)
    except Exception:
        pass

    # Fallback: AppData Roaming (Windows), and XDG on *nix
    home = Path.home()
    # Windows default used by quick_agent_run historically
    yield home / "AppData" / "Roaming" / "DataBox" / "auth" / ".local_token"
    # Common fallback inside repo
    yield Path(".local_token")


def get_local_token_path():
    for p in get_default_token_paths():
        if p and p.exists():
            return p
    return None


def get_local_token():
    p = get_local_token_path()
    if not p:
        raise FileNotFoundError("Local token not found; expected one of known locations")
    return p.read_text(encoding="utf-8").strip()
