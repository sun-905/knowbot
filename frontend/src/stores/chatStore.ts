import { create } from "zustand";

export interface ChatMessage {
  id?: number;
  role: "user" | "assistant" | "system";
  content: string;
  intent?: string;
  references?: { doc_name: string; doc_id: number; score: number; snippet?: string }[];
}

interface ChatState {
  sessionId: number | null;
  messages: ChatMessage[];
  isStreaming: boolean;
  followups: string[];
  currentIntent: { intent: string; source: string; confidence: number } | null;
  currentReferences: { doc_name: string; doc_id: number; score: number }[];
  streamBuffer: string;

  setSessionId: (id: number) => void;
  addMessage: (msg: ChatMessage) => void;
  appendStreamToken: (token: string) => void;
  commitStreamBuffer: () => void;
  setLastAssistantId: (id: number) => void;
  setStreaming: (v: boolean) => void;
  setFollowups: (v: string[]) => void;
  setIntent: (v: { intent: string; source: string; confidence: number }) => void;
  setReferences: (v: { doc_name: string; doc_id: number; score: number }[]) => void;
  setProcessingStage: (v: string) => void;
  loadMessages: (msgs: ChatMessage[]) => void;
  reset: () => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  sessionId: null,
  messages: [],
  isStreaming: false,
  followups: [],
  currentIntent: null,
  currentReferences: [],
  processingStage: "",
  streamBuffer: "",

  setSessionId: (id) => set({ sessionId: id }),
  loadMessages: (msgs) => set({ messages: msgs }),
  addMessage: (msg) =>
    set((s) => ({ messages: [...s.messages, msg] })),
  appendStreamToken: (token) =>
    set((s) => ({ streamBuffer: s.streamBuffer + token })),
  commitStreamBuffer: () =>
    set((s) => {
      if (!s.streamBuffer) return s;
      const msgs = [...s.messages, { role: "assistant" as const, content: s.streamBuffer }];
      return { messages: msgs, streamBuffer: "" };
    }),
  setStreaming: (v) => set({ isStreaming: v }),
  setLastAssistantId: (id) =>
    set((s) => {
      const msgs = [...s.messages];
      for (let i = msgs.length - 1; i >= 0; i--) {
        if (msgs[i].role === "assistant") {
          msgs[i] = { ...msgs[i], id };
          break;
        }
      }
      return { messages: msgs };
    }),
  setFollowups: (v) => set({ followups: v }),
  setIntent: (v) => set({ currentIntent: v }),
  setReferences: (v) => set({ currentReferences: v }),
  setProcessingStage: (v) => set({ processingStage: v }),
  reset: () => set({ messages: [], followups: [], currentIntent: null, currentReferences: [], processingStage: "", streamBuffer: "", isStreaming: false }),
}));
