import type { ActionProcessor } from "../types";

export const TimeoutProcessor: ActionProcessor = {
  name: "timeout",
  meta: {
    phase: "beforeExecute",
    order: 100,
    repeatable: false,
    conflictsWith: [],
    description: "设置本次查询在客户端的最大超时时间，防止长查询挂死连接",
    usage: "@timeout [秒数]",
    examples: ["@timeout 10", "@timeout 60"],
  },

  parse(rest) {
    const sec = parseInt(rest) || 30;
    return { seconds: String(Math.max(1, sec)) };
  },

  apply(action, plan) {
    const sec = parseInt(action.args.seconds ?? "30");
    plan.context.timeoutMs = sec * 1000;
  },

  formatLabel(args) {
    return `超时 ${args.seconds ?? "30"}s`;
  },
};
