import { afterEach, describe, expect, it, vi } from "vitest";
import {
  createAgentRunDraft,
  agentApi,
  reduceAgentRuntimeEvent,
  resolveAgentApproval,
  streamResumeAgentRun,
} from "../agent";
import type { AgentApproval, AgentRunResponse, AgentRuntimeEvent } from "../types";

const approval: AgentApproval = {
  id: "approval_1",
  run_id: "run_1",
  session_id: "session_1",
  step_name: "validate_sql",
  tool_name: "sql.execute_readonly",
  status: "pending",
  risk_level: "warning",
  reason: "Production datasource requires confirmation.",
  policy_decision: { blocked_reasons: ["requires_confirmation"] },
  requested_action: { sql: "SELECT id FROM users LIMIT 3" },
  created_at: "2026-06-02T00:00:00Z",
};

const completedResponse: AgentRunResponse = {
  run_id: "run_1",
  session_id: "session_1",
  success: true,
  status: "success",
  question: "list users",
  steps: [],
  artifacts: [],
};

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("agent runtime reducer", () => {
  it("stores approval state and marks waiting_approval without failing", () => {
    let draft = createAgentRunDraft("list users");
    draft = reduceAgentRuntimeEvent(draft, event("agent.approval.required", { approval }));
    draft = reduceAgentRuntimeEvent(draft, event("agent.run.waiting_approval", {
      approval,
      response: {
        ...completedResponse,
        success: false,
        status: "waiting_approval",
        approval,
      },
    }));

    expect(draft.status).toBe("waiting_approval");
    expect(draft.error).toBeNull();
    expect(draft.approval?.id).toBe("approval_1");
    expect(draft.response?.status).toBe("waiting_approval");
  });

  it("keeps old completed events working", () => {
    const draft = reduceAgentRuntimeEvent(createAgentRunDraft("list users"), event("agent.run.completed", {
      response: completedResponse,
    }));

    expect(draft.status).toBe("completed");
    expect(draft.response?.run_id).toBe("run_1");
  });
});

describe("agent approval api", () => {
  it("sends workspace_context with agent run payloads", async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify(completedResponse), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await agentApi.runAgentQuery("ds-1", "Explain this SQL", {
      workspaceContext: {
        datasource_id: "ds-1",
        active_sql: "SELECT id FROM users LIMIT 10",
        selected_table_names: ["users"],
      },
    });

    const [, options] = fetchMock.mock.calls[0];
    const body = JSON.parse(String(options?.body));
    expect(body.workspace_context).toEqual({
      datasource_id: "ds-1",
      active_sql: "SELECT id FROM users LIMIT 10",
      selected_table_names: ["users"],
    });
  });

  it("posts approval decisions to the run-scoped endpoint", async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ ...approval, status: "approved" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await resolveAgentApproval("run_1", "approval_1", "approved", "reviewed");

    expect(result.status).toBe("approved");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, options] = fetchMock.mock.calls[0];
    expect(String(url)).toContain("/query/agent-runs/run_1/approvals/approval_1");
    expect(JSON.parse(String(options?.body))).toEqual({ decision: "approved", note: "reviewed" });
  });

  it("streams resume events and returns the final response", async () => {
    const resumed = event("agent.run.resumed", { approval: { ...approval, status: "approved" } });
    const completed = event("agent.run.completed", { response: completedResponse });
    const body = `event: agent.run.resumed\ndata: ${JSON.stringify(resumed)}\n\nevent: agent.run.completed\ndata: ${JSON.stringify(completed)}\n\n`;
    const fetchMock = vi.fn(async () => new Response(body, { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const onEvent = vi.fn();

    const result = await streamResumeAgentRun("run_1", "approval_1", { onEvent });

    expect(result.run_id).toBe("run_1");
    expect(onEvent).toHaveBeenCalledTimes(2);
    const [url, options] = fetchMock.mock.calls[0];
    expect(String(url)).toContain("/query/agent-runs/run_1/resume/stream");
    expect(JSON.parse(String(options?.body))).toEqual({ approval_id: "approval_1" });
  });
});

function event(type: AgentRuntimeEvent["type"], patch: Partial<AgentRuntimeEvent>): AgentRuntimeEvent {
  return {
    event_id: `${type}_1`,
    run_id: "run_1",
    sequence: 1,
    created_at_ms: 1,
    type,
    ...patch,
  };
}
