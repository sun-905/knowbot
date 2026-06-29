import { useState } from "react";
import { Button, Input, Space, App } from "antd";
import { LikeOutlined, DislikeOutlined, SendOutlined } from "@ant-design/icons";
import client from "../api/client";

interface Props {
  messageId: number;
}

type State = "idle" | "done" | "dislike_input";

export default function FeedbackButton({ messageId }: Props) {
  const { message } = App.useApp();
  const [state, setState] = useState<State>("idle");
  const [submitting, setSubmitting] = useState(false);
  const [comment, setComment] = useState("");

  // 点赞：直接提交，不弹文字框
  const submitLike = async () => {
    setSubmitting(true);
    try {
      await client.post(`/messages/${messageId}/feedback`, { rating: "like" });
      message.success("感谢您的认可");
      setState("done");
    } catch {
      message.error("反馈提交失败");
    } finally {
      setSubmitting(false);
    }
  };

  // 踩：弹出文字输入框
  const showDislikeInput = () => {
    setState("dislike_input");
  };

  // 提交踩 + 文字反馈
  const submitDislikeWithComment = async () => {
    setSubmitting(true);
    try {
      await client.post(`/messages/${messageId}/feedback`, {
        rating: "dislike",
        comment: comment.trim() || undefined,
      });
      message.success("收到反馈，持续优化中");
      setState("done");
    } catch {
      message.error("反馈提交失败");
    } finally {
      setSubmitting(false);
    }
  };

  const cancelDislike = () => {
    setState("idle");
    setComment("");
  };

  // --- 已完成 ---
  if (state === "done") {
    return (
      <span
        style={{
          fontSize: 12,
          color: "var(--color-cyan)",
          fontFamily: "var(--font-display)",
          letterSpacing: "0.04em",
          position: "relative",
          zIndex: 1,
        }}
      >
        ✓ 已反馈
      </span>
    );
  }

  // --- 踩：文字反馈输入框 ---
  if (state === "dislike_input") {
    return (
      <div style={{ marginTop: 6, position: "relative", zIndex: 1 }}>
        <Space direction="vertical" style={{ width: "100%" }} size={6}>
          <span
            style={{
              fontSize: 12,
              color: "var(--color-amber)",
              fontFamily: "var(--font-display)",
              letterSpacing: "0.04em",
            }}
          >
            ◉ 不满意
          </span>
          <Input.TextArea
            size="small"
            rows={2}
            maxLength={500}
            showCount
            placeholder="补充文字反馈（选填）"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            style={{ fontSize: 13 }}
          />
          <Space size={8}>
            <Button
              size="small"
              type="primary"
              icon={<SendOutlined />}
              loading={submitting}
              onClick={submitDislikeWithComment}
            >
              提交反馈
            </Button>
            <Button size="small" onClick={cancelDislike}>
              取消
            </Button>
          </Space>
        </Space>
      </div>
    );
  }

  // --- 初始：👍 👎 两个按钮 ---
  return (
    <div style={{ display: "flex", gap: 6, marginTop: 4, position: "relative", zIndex: 1 }}>
      <Button
        size="small"
        icon={<LikeOutlined />}
        onClick={submitLike}
        loading={submitting}
        type="text"
        style={{ color: "var(--color-steel-dim)" }}
      />
      <Button
        size="small"
        icon={<DislikeOutlined />}
        onClick={showDislikeInput}
        type="text"
        style={{ color: "var(--color-steel-dim)" }}
      />
    </div>
  );
}
