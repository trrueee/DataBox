import json
import httpx
import argparse
from pathlib import Path
import time
import sys

# Allow running this file directly as a script (python .agent_eval/quick_agent_run.py)
# by ensuring the .agent_eval directory is on sys.path and importing eval_common normally.
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from eval_common import get_local_token, get_local_token_path


def parse_sse_lines(response: httpx.Response):
    events = []
    current_event = None
    current_data = []
    for raw_line in response.iter_lines():
        line = raw_line.strip() if raw_line else ""
        if not line:
            if current_data:
                payload = "\n".join(current_data)
                try:
                    event = json.loads(payload)
                    if current_event:
                        event["_sse_event"] = current_event
                    events.append(event)
                except json.JSONDecodeError:
                    events.append({"_sse_event": current_event or "unknown", "raw": payload})
            current_event = None
            current_data = []
            continue
        if line.startswith("event:"):
            current_event = line[len("event:"):].strip()
        elif line.startswith("data:"):
            current_data.append(line[len("data:"):].strip())
    return events


def run_case(case, base_url: str, token: str, execute: bool, max_steps: int, timeout: int = 180):
    run_url = f"{base_url.rstrip('/')}/api/v1/agent-kernel/run/stream"
    payload = {
        "datasource_id": f"ds-spider-{case['db_id'].replace('_','-')}",
        "question": case['question'],
        "execute": execute,
        "max_steps": max_steps,
    }
    headers = {"X-Local-Token": token, "Content-Type": "application/json"}
    client = httpx.Client(timeout=60.0)
    try:
        # Lightweight pre-check: attempt a simple POST to ensure TCP connects and server accepts POST.
        try:
            r = client.post(run_url, json={"datasource_id": payload["datasource_id"], "question": payload["question"], "execute": False, "max_steps": 1}, headers=headers, timeout=5.0)
            # If server rejects method or requires stream, we still proceed to stream path when status indicates OK-ish.
            if r.status_code not in (200, 204, 422):
                # return structured HTTP error
                return None, {"error": f"HTTP {r.status_code}", "body": r.text[:400], "status_code": r.status_code}
        except Exception as pre_e:
            # connection-level error — report it clearly
            return None, {"error": "connection_error", "detail": repr(pre_e), "message": str(pre_e)}

        # Now open streaming connection
        with client.stream("POST", run_url, json=payload, headers=headers, timeout=timeout) as resp:
            if resp.status_code != 200:
                return None, {"error": f"HTTP {resp.status_code}", "body": resp.text[:400], "status_code": resp.status_code}
            events = parse_sse_lines(resp)
            return events, None
    except Exception as e:
        return None, {"error": "exception", "detail": repr(e), "message": str(e)}
    finally:
        client.close()


def collect_metadata(case_id, events, err):
    rec = {
        "case_id": case_id,
        "error": None,
        "status_code": None,
        "events_count": 0,
        "final_status": None,
        "generation_source": None,
        "agent_sql": None,
        "safety.can_execute": None,
        "blocked_reasons": None,
    }
    if err:
        rec["error"] = err
        return rec
    rec["events_count"] = len(events)
    # try to extract useful fields from events
    for ev in events:
        if isinstance(ev, dict):
            # candidate/gen info
            if "generation_source" in ev:
                rec["generation_source"] = ev.get("generation_source")
            if "agent_sql" in ev:
                rec["agent_sql"] = ev.get("agent_sql")
            if "safe_sql" in ev:
                rec["agent_sql"] = ev.get("safe_sql")
            # nested safety
            safety = ev.get("safety") or ev.get("safety_check") or {}
            if isinstance(safety, dict):
                if "can_execute" in safety:
                    rec["safety.can_execute"] = safety.get("can_execute")
                if "blocked_reasons" in safety:
                    rec["blocked_reasons"] = safety.get("blocked_reasons")
            # final status
            if ev.get("status"):
                rec["final_status"] = ev.get("status")
    return rec


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:18625")
    parser.add_argument("--cases", default=".agent_eval/cases.smoke_subset.json")
    parser.add_argument("--out", default=".agent_eval/outputs/agent_only_results.jsonl")
    parser.add_argument("--execute", default="false")
    parser.add_argument("--max-steps", default=15, type=int)
    args = parser.parse_args()

    base_url = args.base_url
    cases_path = Path(args.cases)
    out_path = Path(args.out)
    execute = str(args.execute).lower() in ("1", "true", "yes")
    max_steps = args.max_steps

    # preflight health
    try:
        r = httpx.get(f"{base_url.rstrip('/')}/api/v1/health", timeout=3.0)
        if r.status_code != 200:
            print("Health check failed:", r.status_code, r.text[:200])
            print("Please run: python .agent_eval/start_eval_backend.py")
            raise SystemExit(2)
    except Exception as e:
        print("Health check error for base_url=", base_url)
        print("Error:", e)
        print("Please run: python .agent_eval/start_eval_backend.py")
        raise SystemExit(2)

    # token
    token_path = get_local_token_path()
    if not token_path:
        print("Local token not found. Ensure backend started and token file exists.")
        raise SystemExit(3)
    token = get_local_token()

    if not cases_path.exists():
        print("Cases file not found:", cases_path)
        raise SystemExit(4)

    CASES = json.loads(cases_path.read_text(encoding='utf-8'))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    outputs = []

    for case in CASES:
        cid = case.get("case_id")
        print("Running:", cid)
        events, err = run_case(case, base_url, token, execute, max_steps)
        rec = collect_metadata(cid, events, err)
        outputs.append(rec)
        print('done', cid, 'err=', rec.get('error'))
        time.sleep(0.5)

    out_path.write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in outputs), encoding='utf-8')
    print('\nWrote', out_path)


if __name__ == '__main__':
    main()
