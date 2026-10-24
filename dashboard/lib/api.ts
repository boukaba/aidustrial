const CONFIGURED_API = process.env.NEXT_PUBLIC_AGENT_API;

/**
 * Dev runs the dashboard on :3010 and the agent on :8781; the single-container
 * build serves both from one origin. An empty NEXT_PUBLIC_AGENT_API means
 * "same origin" rather than a hard-coded localhost URL a judge's browser
 * cannot reach.
 */
export function apiBase(): string {
  if (CONFIGURED_API) return CONFIGURED_API;
  if (typeof window !== "undefined" && process.env.NODE_ENV === "production") {
    return window.location.origin;
  }
  return "http://localhost:8781";
}
