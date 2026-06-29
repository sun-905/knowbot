import { useCallback, useRef, useState } from "react";
import { streamChat } from "../api/chat";
import { useChatStore } from "../stores/chatStore";

export function useChatStream(onSessionError?: () => void) {
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const store = useChatStore();
  const { addMessage, appendStreamToken, commitStreamBuffer, setLastAssistantId, setStreaming, setFollowups, setIntent, setProcessingStage, setReferences } = store;

  const send = useCallback(
    async (content: string) => {
      const sid = useChatStore.getState().sessionId;
      if (sid == null) return;
      setReferences([]);
      setError(null);
      setStreaming(true);
      setFollowups([]);
      setIntent({ intent: "", source: "", confidence: 0 });
      setProcessingStage("");
      addMessage({ role: "user", content });

      abortRef.current?.abort();
      abortRef.current = new AbortController();

      try {
        await streamChat(
          sid,
          content,
          {
            onIntent: (data) => setIntent(data),
            onProcessing: (stage) => setProcessingStage(stage),
            onReferences: (data) => setReferences(data),
            onDelta: (token) => appendStreamToken(token),
            onFollowups: (data) => setFollowups(data),
            onDone: (data) => {
              commitStreamBuffer();
              if (data?.message_id) {
                setLastAssistantId(data.message_id);
              }
              setStreaming(false);
            },
            onSSEError: (code, detail) => {
              commitStreamBuffer();
              if (code === "session_not_found") {
                onSessionError?.();
              } else {
                setError(detail || "请求处理失败");
              }
              setStreaming(false);
            },
            onConnectionError: () => {
              commitStreamBuffer();
              setError("网络连接异常，请稍后重试");
              setStreaming(false);
            },
          },
          abortRef.current.signal
        );
      } catch {
        commitStreamBuffer();
        setStreaming(false);
      }
    },
    [addMessage, appendStreamToken, commitStreamBuffer, setLastAssistantId, setStreaming, setFollowups, setIntent, setProcessingStage, setReferences, onSessionError]
  );

  const abort = useCallback(() => {
    abortRef.current?.abort();
    commitStreamBuffer();
    setStreaming(false);
  }, [commitStreamBuffer, setStreaming]);

  return { send, abort, error };
}
