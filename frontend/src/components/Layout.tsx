import { Outlet, useNavigate } from "react-router-dom";
import { Layout as AntLayout, Menu, Button, Avatar } from "antd";
import {
  MessageOutlined,
  HistoryOutlined,
  BookOutlined,
  DashboardOutlined,
  LogoutOutlined,
} from "@ant-design/icons";
import { useAuthStore } from "../stores/authStore";
import { useChatStore } from "../stores/chatStore";

const { Header, Content } = AntLayout;

export default function Layout() {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();
  // 读取当前会话 ID，用于"对话"菜单回到上次会话而非创建新会话
  const sessionId = useChatStore((s) => s.sessionId);

  const menuItems = [
    { key: "/chat", icon: <MessageOutlined />, label: "对话" },
    { key: "/history", icon: <HistoryOutlined />, label: "历史" },
  ];

  if (user?.is_admin) {
    menuItems.push(
      { key: "/knowledge", icon: <BookOutlined />, label: "知识库" },
      { key: "/admin", icon: <DashboardOutlined />, label: "管理" }
    );
  }

  // 回到对话页：有历史会话则回去，没有才创建新会话
  const goToChat = () => {
    navigate(sessionId ? `/chat/${sessionId}` : "/chat");
  };

  return (
    <AntLayout style={{ minHeight: "100vh", background: "var(--color-void)" }}>
      <Header
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 24px",
          height: 56,
          /* 玻璃质感 */
          background: "rgba(17, 22, 51, 0.85)",
          backdropFilter: "blur(12px)",
          WebkitBackdropFilter: "blur(12px)",
          borderBottom: "1px solid rgba(0, 229, 255, 0.12)",
          position: "sticky",
          top: 0,
          zIndex: 100,
          /* 入场动画 */
          animation: "fade-in 0.3s ease",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 32 }}>
          {/* Logo — Rajdhani 展示字体 */}
          <div
            style={{
              fontFamily: "var(--font-display)",
              fontSize: 20,
              fontWeight: 700,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              color: "var(--color-steel)",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
            onClick={goToChat}
          >
            <span style={{ color: "var(--color-cyan)", fontWeight: 700 }}>◈</span>
            NEURAL DESK
          </div>

          <Menu
            theme="dark"
            mode="horizontal"
            selectable={false}
            items={menuItems}
            onClick={({ key }) => {
              if (key === "/chat") goToChat();
              else navigate(key);
            }}
            style={{
              flex: 1,
              minWidth: 300,
              background: "transparent",
              borderBottom: "none",
            }}
          />
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Avatar
            size="small"
            style={{
              background: "rgba(0, 229, 255, 0.15)",
              color: "var(--color-cyan)",
              fontFamily: "var(--font-display)",
              fontWeight: 600,
            }}
          >
            {user?.nickname?.[0] || "U"}
          </Avatar>
          <span style={{ color: "var(--color-steel-dim)", fontSize: 13 }}>
            {user?.nickname || "用户"}
          </span>
          <Button
            type="text"
            icon={<LogoutOutlined />}
            onClick={() => {
              logout();
              navigate("/login");
            }}
            style={{ color: "var(--color-steel-dim)" }}
          >
            退出
          </Button>
        </div>
      </Header>

      {/* 霓虹发光线 — header 底部 */}
      <div
        style={{
          height: 1,
          background: "linear-gradient(90deg, transparent, var(--color-cyan), var(--color-amber), transparent)",
          opacity: 0.5,
        }}
        aria-hidden="true"
      />

      <Content
        style={{
          padding: 24,
          maxWidth: 1200,
          margin: "0 auto",
          width: "100%",
          position: "relative",
        }}
      >
        <Outlet />
      </Content>
    </AntLayout>
  );
}
