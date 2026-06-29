import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Form, Input, Button, Card, App } from "antd";
import { UserOutlined, LockOutlined } from "@ant-design/icons";
import { login } from "../api/auth";
import { useAuthStore } from "../stores/authStore";

export default function Login() {
  const { message } = App.useApp();
  const [loading, setLoading] = useState(false);
  const setAuth = useAuthStore((s) => s.setAuth);
  const navigate = useNavigate();

  const onFinish = async (values: { account: string; password: string }) => {
    setLoading(true);
    try {
      const res = await login(values.account, values.password);
      setAuth(res.access_token, res.user);
      message.success("登录成功");
      navigate("/chat");
    } catch {
      message.error("账号或密码错误");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        minHeight: "100vh",
        background: "var(--color-void)",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* Ambient glow behind card */}
      <div
        style={{
          position: "absolute",
          width: 600,
          height: 600,
          borderRadius: "50%",
          background: "radial-gradient(circle, rgba(0, 229, 255, 0.05) 0%, transparent 70%)",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
          pointerEvents: "none",
        }}
        aria-hidden="true"
      />

      <Card
        title={
          <div style={{ textAlign: "center" }}>
            <div
              style={{
                fontFamily: "var(--font-display)",
                fontSize: 24,
                fontWeight: 700,
                letterSpacing: "0.08em",
                color: "var(--color-steel)",
                marginBottom: 4,
              }}
            >
              <span style={{ color: "var(--color-cyan)" }}>◈</span> NEURAL DESK
            </div>
            <div style={{ fontFamily: "var(--font-display)", fontSize: 16, fontWeight: 500, color: "var(--color-steel-dim)", letterSpacing: "0.06em" }}>
              身份验证 · IDENTITY CHECK
            </div>
          </div>
        }
        style={{
          width: 400,
          border: "1px solid var(--color-border-lit)",
          boxShadow: "var(--glow-card)",
          animation: "fade-in-up 0.4s ease",
        }}
      >
        <Form onFinish={onFinish} size="large">
          <Form.Item
            name="account"
            rules={[{ required: true, message: "请输入手机号或邮箱" }]}
          >
            <Input prefix={<UserOutlined />} placeholder="手机号或邮箱" />
          </Form.Item>
          <Form.Item
            name="password"
            rules={[{ required: true, message: "请输入密码" }]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="密码" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} block>
              登录
            </Button>
          </Form.Item>
          <div style={{ textAlign: "center", color: "var(--color-steel-dim)", fontSize: 13 }}>
            还没有账号？<Link to="/register" style={{ color: "var(--color-cyan)" }}>立即注册</Link>
          </div>
        </Form>
      </Card>
    </div>
  );
}
