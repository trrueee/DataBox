import json
import httpx
from pathlib import Path
import time

BASE_URL = "http://127.0.0.1:18625"
TOKEN_PATH = Path.home() / "AppData" / "Roaming" / "DataBox" / "auth" / ".local_token"

CASES = json.loads(Path('.agent_eval/cases.smoke_subset.json').read_text(encoding='utf-8'))


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


def run_case(case):
    token = TOKEN_PATH.read_text(encoding='utf-8').strip()
    run_url = f"{BASE_URL.rstrip('/')}/api/v1/agent-kernel/run/stream"
    payload = {
        "datasource_id": f"ds-spider-{case['db_id'].replace('_','-')}",
        "question": case['question'],
        "execute": False,
        "max_steps": 15,
    }
    headers = {"X-Local-Token": token, "Content-Type": "application/json"}
    client = httpx.Client(timeout=60.0)
    try:
        with client.stream("POST", run_url, json=payload, headers=headers, timeout=180.0) as resp:
            if resp.status_code != 200:
                print('HTTP ERROR', resp.status_code, resp.text[:400])
                return None, f"HTTP {resp.status_code}: {resp.text[:200]}"
            events = parse_sse_lines(resp)
            return events, None
    except Exception as e:
        return None, str(e)
    finally:
        client.close()


if __name__ == '__main__':
    outputs = []
    for case in CASES:
        print('\nRunning:', case['case_id'])
        events, err = run_case(case)
        record = {"case_id": case['case_id'], "events": events, "error": err}
        outputs.append(record)
        print('done', case['case_id'], 'err=', err)
        time.sleep(0.5)
    Path('.agent_eval/outputs/agent_only_results.jsonl').write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in outputs), encoding='utf-8')
    print('\nWrote .agent_eval/outputs/agent_only_results.jsonl')
