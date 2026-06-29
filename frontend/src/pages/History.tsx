import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button, Popconfirm, App, Flex, Spin } from "antd";
import { DeleteOutlined, MessageOutlined } from "@ant-design/icons";
import { listSessions, deleteSession } from "../api/chat";
import { useRequireAuth } from "../hooks/useAuth";

interface SessionItem {
  id: number;
  title: string;
  status: string;
  created_at: string;
}

export default function History() {
  const { message } = App.useApp();
  useRequireAuth();
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const fetchData = async () => {
    setLoading(true);
    try {
      const data = await listSessions(1, 50);
      setSessions(data.items);
    } catch {
      message.error("加载失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleDelete = async (id: number) => {
    try {
      await deleteSession(id);
      setSessions((prev) => prev.filter((s) => s.id !== id));
      message.success("已删除");
    } catch {
      message.error("删除失败");
    }
  };

  return (
    <div style={{ animation: "fade-in-up 0.3s ease" }}>
      <h2
        style={{
          fontFamily: "var(--font-display)",
          color: "var(--color-cyan)",
          marginBottom: 20,
          letterSpacing: "0.08em",
        }}
      >
        会话日志
      </h2>
      <Spin spinning={loading}>
        {sessions.length === 0 && !loading ? (
          <div style={{ textAlign: "center", padding: 48, color: "var(--color-steel-dim)" }}>
            暂无会话记录
          </div>
        ) : (
          sessions.map((item) => (
            <Flex
              key={item.id}
              justify="space-between"
              align="center"
              style={{
                borderBottom: "1px solid var(--color-border)",
                padding: "16px 0",
              }}
            >
              <div style={{ flex: 1 }}>
                <div
                  style={{
                    color: "var(--color-steel)",
                    fontFamily: "var(--font-display)",
                    letterSpacing: "0.04em",
                    marginBottom: 4,
                  }}
                >
                  {item.title}
                </div>
                <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--color-steel-dim)" }}>
                  {new Date(item.created_at).toLocaleString("zh-CN")}
                  <span style={{ margin: "0 8px", color: "var(--color-border-lit)" }}>|</span>
                  <span style={{ color: item.status === "active" ? "var(--color-cyan)" : "var(--color-steel-dim)" }}>
                    {item.status === "active" ? "进行中" : "已关闭"}
                  </span>
                </span>
              </div>
              <Flex gap={8} style={{ flexShrink: 0 }}>
                <Button
                  icon={<MessageOutlined />}
                  onClick={() => navigate(`/chat/${item.id}`)}
                  style={{ borderRadius: 2 }}
                >
                  继续
                </Button>
                <Popconfirm title="确定删除？" onConfirm={() => handleDelete(item.id)}>
                  <Button icon={<DeleteOutlined />} danger style={{ borderRadius: 2 }} />
                </Popconfirm>
              </Flex>
            </Flex>
          ))
        )}
      </Spin>
    </div>
  );
}
