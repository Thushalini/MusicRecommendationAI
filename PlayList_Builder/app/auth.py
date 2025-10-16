# app/auth_local.py
import os, json, secrets, hashlib, hmac, time
from pathlib import Path
from typing import Optional, Dict, Any

APPDATA_DIR = Path(__file__).resolve().parent.parent / ".appdata"
USERS_JSON = APPDATA_DIR / "users.json"

APPDATA_DIR.mkdir(parents=True, exist_ok=True)
if not USERS_JSON.exists():
    USERS_JSON.write_text(json.dumps({"users": {}}, indent=2), encoding="utf-8")

def _load() -> Dict[str, Any]:
    try:
        return json.loads(USERS_JSON.read_text(encoding="utf-8"))
    except Exception:
        return {"users": {}}

def _save(data: Dict[str, Any]) -> None:
    USERS_JSON.write_text(json.dumps(data, indent=2), encoding="utf-8")

def _pwd_hash(password: str, salt: str) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return dk.hex()

def create_user(email: str, display_name: str, password: str, avatar_url: Optional[str] = None) -> Dict[str, Any]:
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        raise ValueError("invalid email")
    if not password or len(password) < 6:
        raise ValueError("password too short")
    data = _load()
    if email in data.get("users", {}):
        raise ValueError("user already exists")

    salt = secrets.token_hex(16)
    rec = {
        "email": email,
        "display_name": display_name.strip() or email,
        "salt": salt,
        "pwd": _pwd_hash(password, salt),
        "avatar_url": (avatar_url or "").strip() or None,
        "created_at": int(time.time())
    }
    data["users"][email] = rec
    _save(data)
    # do not return salt/pwd to caller
    return {"email": rec["email"], "display_name": rec["display_name"], "avatar_url": rec["avatar_url"]}

def authenticate(email: str, password: str) -> Optional[Dict[str, Any]]:
    email = (email or "").strip().lower()
    data = _load()
    rec = (data.get("users") or {}).get(email)
    if not rec:
        return None
    calc = _pwd_hash(password, rec["salt"])
    if hmac.compare_digest(calc, rec["pwd"]):
        return {"email": rec["email"], "display_name": rec["display_name"], "avatar_url": rec.get("avatar_url")}
    return None

def get_profile(email: str) -> Optional[Dict[str, Any]]:
    email = (email or "").strip().lower()
    data = _load()
    rec = (data.get("users") or {}).get(email)
    if not rec:
        return None
    return {"email": rec["email"], "display_name": rec["display_name"], "avatar_url": rec.get("avatar_url")}
