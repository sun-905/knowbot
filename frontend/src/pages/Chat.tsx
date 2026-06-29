import { useEffect, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Input, Button, Spin } from "antd";
import { SendOutlined, PlusOutlined, StopOutlined } from "@ant-design/icons";
import { useChatStore } from "../stores/chatStore";
import { useChatStream } from "../hooks/useChatStream";
import { createSession, getSession } from "../api/chat";
import ChatBubble from "../components/ChatBubble";
import ReferenceCard from "../components/ReferenceCard";
import FollowupChips from "../components/FollowupChips";
import FeedbackButton from "../components/FeedbackButton";
import RagPulse from "../components/RagPulse";
import { useRequireAuth } from "../hooks/useAuth";

export default function Chat() {
  useRequireAuth();
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const [input, setInput] = useState("");
  const [initializing, setInitializing] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const { send, abort, error } = useChatStream(() => {
    store.reset();
    navigate("/chat");
  });
  const store = useChatStore();
  const setSessionId = useChatStore((s) => s.setSessionId);
  const loadMessages = useChatStore((s) => s.loadMessages);
  const creatingRef = useRef(false);
  const loadedSessionRef = useRef<number | null>(null);
  const sendingRef = useRef(false);  // 防止连续点击导致的重复请求

  useEffect(() => {
    if (!sessionId && !creatingRef.current) {
      creatingRef.current = true;
      setInitializing(true);
      createSession()
        .then((s) => {
          creatingRef.current = false;
          setInitializing(false);
          navigate(`/chat/${s.id}`, { replace: true });
        })
        .catch(() => {
          creatingRef.current = false;
          setInitializing(false);
        });
    } else if (sessionId) {
      setInitializing(false);
      const sid = Number(sessionId);
      if (loadedSessionRef.current !== sid) {
        loadedSessionRef.current = sid;
        setSessionId(sid);
        useChatStore.getState().reset();
        getSession(sid).then((data) => {
          if (data.messages && data.messages.length > 0) {
            loadMessages(data.messages.map((m: any) => ({
              id: m.id,
              role: m.role,
              content: m.content,
              intent: m.intent,
              references: m.references_json || [],
            })));
          }
        }).catch(() => {
          // 会话可能已被删除
          useChatStore.getState().reset();
          navigate("/chat");
        });
      }
    }
  }, [sessionId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [store.messages]);

  const handleSend = () => {
    const text = input.trim();
    if (!text || store.isStreaming || sendingRef.current) return;
    sendingRef.current = true;
    setInput("");
    send(text).finally(() => { sendingRef.current = false; });
  };

  if (initializing) {
    return (
      <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "calc(100vh - 120px)" }}>
        <Spin description={<span style={{ color: "var(--color-cyan)", fontFamily: "var(--font-display)", letterSpacing: "0.06em" }}>初始化会话中</span>} />
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "calc(100vh - 120px)" }}>
      {/* 顶部工具栏 */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 16,
          position: "relative",
          zIndex: 1,
        }}
      >
        <div>
          {store.currentIntent?.intent && (
            <span style={{ fontSize: 12, color: "var(--color-steel-dim)", fontFamily: "var(--font-mono)" }}>
              意图: <span style={{ color: "var(--color-cyan)" }}>{store.currentIntent.intent}</span>
            </span>
          )}
        </div>
        <Button
          icon={<PlusOutlined />}
          onClick={() => {
            store.reset();
            navigate("/chat");
          }}
          style={{ borderRadius: 2 }}
        >
          新对话
        </Button>
      </div>

      {/* 消息区域 — 承载 RagPulse 粒子背景 */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "0 8px",
          position: "relative",
          background: "rgba(10, 14, 39, 0.4)",
          borderRadius: 4,
          border: "1px solid var(--color-border)",
        }}
      >
        {/* RAG Pulse — 签名级氛围可视化 */}
        <RagPulse active={store.isStreaming} />

        <div style={{ position: "relative", zIndex: 1, padding: "12px 0" }}>
          {store.messages.map((m, i) => (
            <div key={i}>
              <ChatBubble
                role={m.role}
                content={m.content}
                isStreaming={
                  store.isStreaming &&
                  i === store.messages.length - 1 &&
                  m.role === "assistant"
                }
              />
              {m.role === "assistant" && m.id && (
                <FeedbackButton messageId={m.id} />
              )}
              {/* 最后一条助手消息后面，非流式状态下显示参考来源 */}
              {m.role === "assistant" &&
                i === store.messages.length - 1 &&
                !store.isStreaming &&
                store.currentReferences.length > 0 && (
                  <ReferenceCard references={store.currentReferences} />
                )}
            </div>
          ))}
          {/* 流式缓冲区 — 实时显示 LLM 输出 */}
          {store.isStreaming && store.streamBuffer && (
            <div style={{ display: "flex", justifyContent: "flex-start", marginBottom: 16, position: "relative", zIndex: 1 }}>
              <ChatBubble role="assistant" content={store.streamBuffer} isStreaming={true} />
            </div>
          )}
          {/* 等待中占位 — 尚未收到第一个 token */}
          {store.isStreaming &&
            !store.streamBuffer &&
            store.messages.length > 0 &&
            store.messages[store.messages.length - 1].role === "user" && (
              <div style={{ display: "flex", justifyContent: "flex-start", marginBottom: 16, position: "relative", zIndex: 1 }}>
                <div
                  style={{
                    maxWidth: "75%",
                    padding: "14px 18px",
                    borderRadius: "4px 4px 4px 0",
                    background: "rgba(17, 22, 51, 0.9)",
                    border: "1px solid rgba(0, 229, 255, 0.12)",
                    color: "var(--color-cyan)",
                    fontFamily: "var(--font-mono)",
                    fontSize: 13,
                    boxShadow: "0 0 16px rgba(0, 229, 255, 0.06)",
                  }}
                >
                  {store.processingStage || "思考中，请稍候..."}
                  <span className="cursor-blink" style={{ color: "var(--color-cyan)" }}>▊</span>
                </div>
              </div>
            )}
          {error && (
            <div
              style={{
                color: "var(--color-danger)",
                textAlign: "center",
                padding: 12,
                fontSize: 13,
                fontFamily: "var(--font-mono)",
                position: "relative",
                zIndex: 1,
              }}
            >
              ⚠ 信号中断: {error}
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* 追问建议标签 */}
      <FollowupChips
        items={store.followups}
        onSelect={(q) => setInput(q)}
        disabled={store.isStreaming}
      />

      {/* 输入区域 — 终端风格 */}
      <div
        style={{
          display: "flex",
          gap: 8,
          marginTop: 12,
          position: "relative",
          zIndex: 1,
        }}
      >
        <div style={{ position: "relative", flex: 1 }}>
          <Input.TextArea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onPressEnter={(e) => {
              e.preventDefault();
              handleSend();
            }}
            placeholder="> 输入查询指令...（Enter 发送）"
            autoSize={{ minRows: 1, maxRows: 4 }}
            maxLength={500}
            disabled={store.isStreaming}
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 13,
              borderRadius: 2,
              background: "rgba(10, 14, 39, 0.6)",
            }}
          />
        </div>
        {store.isStreaming ? (
          <Button
            icon={<StopOutlined />}
            danger
            onClick={abort}
            style={{ borderRadius: 2 }}
          >
            终止
          </Button>
        ) : (
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={handleSend}
            disabled={!input.trim()}
            style={{ borderRadius: 2 }}
          >
            执行
          </Button>
        )}
      </div>
    </div>
  );
}
