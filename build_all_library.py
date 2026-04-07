from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> int:
    cmd = [sys.executable, 'brain.py', 'build-library', '--library-id', 'example']
    print('>>', ' '.join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)
    print('\nBundled merged library built. Try:')
    print('  python3 brain.py ask "how do I make steak" --library-id example')
    print('  python3 brain.py respond "why does my SPA 404 on refresh" --library-id example --response-mode code_assistant')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
