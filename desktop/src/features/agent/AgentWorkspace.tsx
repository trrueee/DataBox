import { useState } from "react";
import { ArtifactInspector } from "./ArtifactInspector";
import { AgentComposer } from "./AgentComposer";
import { AgentNarrativeStream } from "./AgentNarrativeStream";
import { TraceDrawer } from "./TraceDrawer";
import type { AgentRunDraftState, AgentRunResponse, AgentStep, AgentVisibleEvent, FollowUpSuggestion } from "./types";

interface AgentWorkspaceProps {
  result?: AgentRunResponse | null;
  draft?: AgentRunDraftState | null;
  disabled?: boolean;
  onOpenSql?: (sql: string) => void;
  onAsk?: (question: string) => void;
  onSuggestion?: (suggestion: FollowUpSuggestion, result: AgentRunResponse) => void;
}

export function AgentWorkspace({ result, draft, disabled, onOpenSql, onAsk, onSuggestion }: AgentWorkspaceProps) {
  const isRunningDraft = Boolean(draft && draft.status === "running" && !result);
  const artifacts = result?.artifacts || draft?.artifacts || [];
  const events = result?.events || draftVisibleEvents(draft);
  const messageBlocks = result?.message_blocks || [];
  const suggestions = result?.suggestions || [];
  const steps = result?.steps || draftSteps(draft);
  const traceEvents = result?.trace_events || [];
  const success = result ? result.success : draft?.status !== "failed";
  const error = result?.error || draft?.error || null;
  const answer = result?.answer || draft?.answer || null;
  const [selectedArtifactId, setSelectedArtifactId] = useState("");
  const activeArtifactId = selectedArtifactId && artifacts.some((artifact) => artifact.id === selectedArtifactId)
    ? selectedArtifactId
    : artifacts[0]?.id || "";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10, fontSize: "0.68rem", lineHeight: 1.45 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 6 }}>
        <span className={`status-badge ${success ? "status-badge-success" : "status-badge-error"}`}>
          {isRunningDraft ? "Agent running" : success ? "Agent answer" : "Agent stopped"}
        </span>
        {error ? <span style={{ color: "var(--accent-red)", textAlign: "right" }}>{error}</span> : null}
      </div>

      <AgentNarrativeStream
        events={events}
        messageBlocks={messageBlocks}
        fallbackAnswer={answer}
        fallbackArtifacts={artifacts}
        fallbackSuggestions={suggestions}
        onOpenSql={onOpenSql}
        onOpenArtifact={setSelectedArtifactId}
        onAsk={onAsk}
        onSuggestion={onSuggestion && result ? (suggestion) => onSuggestion(suggestion, result) : undefined}
      />

      <ArtifactInspector
        artifacts={artifacts}
        activeArtifactId={activeArtifactId}
        onActiveArtifactChange={setSelectedArtifactId}
        onOpenSql={onOpenSql}
      />
      {onAsk && result ? (
        <AgentComposer
          disabled={disabled}
          placeholder="Ask a follow-up about this result"
          onSubmit={onAsk}
        />
      ) : null}
      <TraceDrawer steps={steps} traceEvents={traceEvents} />
    </div>
  );
}

function draftVisibleEvents(draft?: AgentRunDraftState | null): AgentVisibleEvent[] {
  if (!draft) return [];
  return draft.events.flatMap((event): AgentVisibleEvent[] => {
    if (event.type === "agent.artifact.created" && event.artifact) {
      return [{ type: "agent.artifact.created", artifact: event.artifact }];
    }
    if (event.type === "agent.answer.completed" && event.answer) {
      return [{ type: "agent.answer.completed", answer: event.answer }];
    }
    return [];
  });
}

function draftSteps(draft?: AgentRunDraftState | null): AgentStep[] {
  if (!draft) return [];
  return draft.events
    .filter((event) => event.type === "agent.step.completed" && event.step?.name)
    .map((event) => ({
      name: String(event.step?.name || ""),
      status: event.step?.status === "failed" || event.step?.status === "skipped" ? event.step.status : "success",
      error: typeof event.step?.error === "string" ? event.step.error : null,
      latency_ms: typeof event.step?.latency_ms === "number" ? event.step.latency_ms : 0,
    }));
}
