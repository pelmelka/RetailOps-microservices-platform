"""Compatibility entrypoint for the local critical workflow smoke.

TASK-014 moved the primary client journey to Redis Streams async workflow
orchestration. Keep this script path stable and delegate to the async smoke.
"""

from __future__ import annotations

import sys

from check_async_workflow import main


if __name__ == "__main__":
    print("check_critical_workflow.py delegates to check_async_workflow.py")
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL critical workflow smoke: {exc}", file=sys.stderr)
        raise SystemExit(1)
