import { fetchEventSource } from "@microsoft/fetch-event-source";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export interface ChatEventHandlers {
  onIntent?: (data: { intent: string; confidence: number; source: string; clarify?: boolean }) => void;
  onProcessing?: (stage: string) => void;
  onReferences?: (data: { doc_name: string; doc_id: number; score: number }[]) => void;
  onDelta?: (content: string) => void;
  onFollowups?: (data: string[]) => void;
  onDone?: (data: { message_id?: number }) => void;
  onSSEError?: (code: string, detail: string) => void;
  onConnectionError?: (error: string) => void;
}

export function streamChat(
  sessionId: number,
  content: string,
  handlers: ChatEventHandlers,
  signal?: AbortSignal
): Promise<void> {
  const token = localStorage.getItem("token");
  return fetchEventSource(`${API_URL}/sessions/${sessionId}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ content, stream: true }),
    signal,
    onmessage(event) {
      try {
        const data = JSON.parse(event.data);
        switch (event.event) {
          case "intent":
            handlers.onIntent?.(data);
            break;
          case "processing":
            handlers.onProcessing?.(data.stage || "处理中");
            break;
          case "references":
            handlers.onReferences?.(data);
            break;
          case "delta":
            handlers.onDelta?.(data.content || "");
            break;
          case "followups":
            handlers.onFollowups?.(data);
            break;
          case "error":
            handlers.onSSEError?.(data.code, data.detail);
            break;
          case "done":
            handlers.onDone?.(data);
            break;
        }
      } catch {
        // non-JSON event, ignore
      }
    },
    onerror(err) {
      handlers.onConnectionError?.(err.message);
      throw err; // 不重试——SSE 不会因为响应慢而报错
    },
  });
}

export async function createSession(title = "新对话", kbId?: number): Promise<{ id: number; title: string; kb_id: number | null }> {
  const { default: client } = await import("./client");
  const { data } = await client.post("/sessions", { title, kb_id: kbId ?? null });
  return data;
}

export async function listSessions(page = 1, pageSize = 20) {
  const { default: client } = await import("./client");
  const { data } = await client.get("/sessions", { params: { page, page_size: pageSize } });
  return data;
}

export async function getSession(sessionId: number) {
  const { default: client } = await import("./client");
  const { data } = await client.get(`/sessions/${sessionId}`);
  return data;
}

export async function deleteSession(sessionId: number): Promise<void> {
  const { default: client } = await import("./client");
  await client.delete(`/sessions/${sessionId}`);
}
