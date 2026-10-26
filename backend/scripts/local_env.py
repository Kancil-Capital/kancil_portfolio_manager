"""
scripts/local_env.py
Point the app at the local Supabase stack, or back at production.

    uv run python scripts/local_env.py on    # write local Supabase URL + keys into .env.local
    uv run python scripts/local_env.py off   # remove them, so .env (production) applies again

Only the Supabase variables are touched; anything else in backend/.env.local or
frontend/.env.local is kept. Values come from `supabase status -o env`.
Run via `make db-env` / `make use-prod` from the repo root.
"""

import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
FRONTEND = BACKEND.parent / "frontend"

# .env.local file → {app variable: `supabase status -o env` variable}
MAPPING = {
    BACKEND / ".env.local": {
        "SUPABASE_URL": "API_URL",
        "SUPABASE_SECRET_KEY": "SECRET_KEY",
        "SUPABASE_JWT_SECRET": "JWT_SECRET",
    },
    FRONTEND / ".env.local": {
        "NEXT_PUBLIC_SUPABASE_URL": "API_URL",
        "NEXT_PUBLIC_SUPABASE_ANON_KEY": "PUBLISHABLE_KEY",
    },
}


def local_status() -> dict[str, str]:
    result = subprocess.run(
        ["supabase", "status", "-o", "env"], cwd=BACKEND, capture_output=True, text=True
    )
    status = {}
    for line in result.stdout.splitlines():
        key, sep, value = line.partition("=")
        if sep:
            status[key.strip()] = value.strip().strip('"')
    if "API_URL" not in status:
        sys.exit("Local Supabase isn't running. Start it with `make db-start` (needs Docker).")
    return status


def strip_vars(lines: list[str], names: set[str]) -> list[str]:
    return [ln for ln in lines if ln.partition("=")[0].strip() not in names]


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode not in ("on", "off"):
        sys.exit("usage: local_env.py on|off")

    status = local_status() if mode == "on" else {}

    for path, mapping in MAPPING.items():
        lines = path.read_text().splitlines() if path.exists() else []
        lines = strip_vars(lines, set(mapping))
        if mode == "on":
            lines += [f"{name}={status[src]}" for name, src in mapping.items()]

        has_vars = any("=" in ln and not ln.lstrip().startswith("#") for ln in lines)
        if has_vars:
            path.write_text("\n".join(lines) + "\n")
        elif path.exists():
            path.unlink()
        print(f"{'local' if mode == 'on' else 'production'}: {path.relative_to(BACKEND.parent)}")

    if mode == "on":
        print("Using local Supabase. Restart `make dev` if it's running.")
    else:
        print("Using production Supabase (.env). Restart `make dev` if it's running.")


if __name__ == "__main__":
    main()
