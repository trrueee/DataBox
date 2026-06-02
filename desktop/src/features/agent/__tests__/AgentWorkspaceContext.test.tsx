import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AgentWorkspace } from "../AgentWorkspace";
import type { AgentArtifact, AgentRunResponse, AgentWorkspaceContext } from "../types";

const workspaceContext: AgentWorkspaceContext = {
  datasource_id: "ds-1",
  project_id: "project-1",
  active_sql: "SELECT id FROM users LIMIT 10",
  last_query_result_preview: { columns: ["id"], rows: [{ id: 1 }], rowCount: 1 },
  selected_table_names: ["users"],
  selected_artifact_id: "artifact-suggestion",
};

const sqlSuggestion: AgentArtifact = {
  id: "artifact-suggestion",
  semantic_id: "sql_suggestion",
  type: "sql_suggestion",
  title: "SQL suggestion",
  payload: {
    proposed_sql: "SELECT id FROM users LIMIT 10",
    suggestions: [
      {
        id: "apply",
        title: "Apply SQL",
        proposed_sql: "SELECT id FROM users LIMIT 10",
        action: "apply_to_editor",
      },
    ],
  },
  presentation: { mode: "both", priority: 1 },
};

const response: AgentRunResponse = {
  run_id: "run-1",
  session_id: "session-1",
  success: true,
  status: "success",
  question: "Explain this SQL",
  artifacts: [sqlSuggestion],
  steps: [],
};

afterEach(() => {
  cleanup();
});

describe("AgentWorkspace workspace context", () => {
  it("shows the lightweight workspace context indicator", () => {
    render(<AgentWorkspace result={response} workspaceContext={workspaceContext} />);

    expect(screen.getByText("Current SQL")).toBeTruthy();
    expect(screen.getByText("Last result")).toBeTruthy();
    expect(screen.getByText("Selected table")).toBeTruthy();
    expect(screen.getByText("Selected artifact")).toBeTruthy();
    expect(screen.getByText("users")).toBeTruthy();
  });

  it("applies proposed sql to the editor without executing", () => {
    const onApplySql = vi.fn();
    const onOpenSql = vi.fn();

    render(
      <AgentWorkspace
        result={response}
        workspaceContext={workspaceContext}
        onApplySql={onApplySql}
        onOpenSql={onOpenSql}
      />,
    );

    fireEvent.click(screen.getByText("Apply to SQL Editor"));

    expect(onApplySql).toHaveBeenCalledWith("SELECT id FROM users LIMIT 10");
    expect(onOpenSql).not.toHaveBeenCalled();
  });

  it("passes workspace context through follow-up composer", () => {
    const onAsk = vi.fn();

    render(<AgentWorkspace result={response} workspaceContext={workspaceContext} onAsk={onAsk} />);

    fireEvent.change(screen.getByPlaceholderText("Ask a follow-up about this result"), {
      target: { value: "continue" },
    });
    fireEvent.click(screen.getByText("Ask"));

    expect(onAsk).toHaveBeenCalledWith("continue", workspaceContext);
  });

  it("does not crash when context is absent", () => {
    render(<AgentWorkspace result={response} />);

    expect(screen.getByText("Artifact Inspector")).toBeTruthy();
  });
});
