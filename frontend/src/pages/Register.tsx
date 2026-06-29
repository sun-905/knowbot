import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Form, Input, Button, Card, App } from "antd";
import { PhoneOutlined, MailOutlined, LockOutlined } from "@ant-design/icons";
import { register } from "../api/auth";

export default function Register() {
  const { message } = App.useApp();
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const onFinish = async (values: {
    phone: string;
    email?: string;
    password: string;
    nickname: string;
  }) => {
    setLoading(true);
    try {
      await register(values);
      message.success("注册成功，请登录");
      navigate("/login");
    } catch (err: any) {
      message.error(err.response?.data?.detail || "注册失败");
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
      <div
        style={{
          position: "absolute",
          width: 600,
          height: 600,
          borderRadius: "50%",
          background: "radial-gradient(circle, rgba(255, 183, 77, 0.04) 0%, transparent 70%)",
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
              <span style={{ color: "var(--color-amber)" }}>◈</span> NEURAL DESK
            </div>
            <div style={{ fontFamily: "var(--font-display)", fontSize: 16, fontWeight: 500, color: "var(--color-steel-dim)", letterSpacing: "0.06em" }}>
              账号注册 · Account Registration
            </div>
          </div>
        }
        style={{
          width: 400,
          border: "1px solid rgba(255, 183, 77, 0.12)",
          boxShadow: "0 0 0 1px rgba(255, 183, 77, 0.04), 0 2px 24px rgba(0, 0, 0, 0.4)",
          animation: "fade-in-up 0.4s ease",
        }}
      >
        <Form onFinish={onFinish} size="large">
          <Form.Item
            name="phone"
            rules={[{ required: true, message: "请输入手机号" }]}
          >
            <Input prefix={<PhoneOutlined />} placeholder="手机号" />
          </Form.Item>
          <Form.Item name="email">
            <Input prefix={<MailOutlined />} placeholder="邮箱（选填）" />
          </Form.Item>
          <Form.Item
            name="nickname"
            rules={[{ required: true, message: "请输入昵称" }]}
          >
            <Input placeholder="昵称" />
          </Form.Item>
          <Form.Item
            name="password"
            rules={[{ required: true, min: 6, message: "密码至少6位" }]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="密码" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} block>
              注册账号
            </Button>
          </Form.Item>
          <div style={{ textAlign: "center", color: "var(--color-steel-dim)", fontSize: 13 }}>
            已有账号？<Link to="/login" style={{ color: "var(--color-cyan)" }}>立即登录</Link>
          </div>
        </Form>
      </Card>
    </div>
  );
}
