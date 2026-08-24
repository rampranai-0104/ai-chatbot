from collections import defaultdict

# A simple in-memory store: session_id -> list of {role, content} dicts
_sessions = defaultdict(list)

def get_history(session_id: str) -> list[dict]:
    """Return the message history for a given session."""
    return _sessions[session_id].copy()

def append_message(session_id: str, role: str, content: str):
    """Append a new message to the session's history."""
    _sessions[session_id].append({"role": role, "content": content})
