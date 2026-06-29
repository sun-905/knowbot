import { useEffect, useState } from "react";
import { Card, Statistic, Row, Col, Table, Spin, App, Tag } from "antd";
import {
  MessageOutlined,
  LikeOutlined,
  CommentOutlined,
} from "@ant-design/icons";
import client from "../api/client";
import { useRequireAuth } from "../hooks/useAuth";
import SparkLine from "../components/SparkLine";

interface FeedbackComment {
  id: number;
  rating: string;
  comment: string;
  message_id: number;
  user: { nickname: string; phone: string | null; email: string | null };
  created_at: string | null;
}

export default function Admin() {
  const { message } = App.useApp();
  useRequireAuth();
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<any>({});
  const [comments, setComments] = useState<FeedbackComment[]>([]);
  const [commentsTotal, setCommentsTotal] = useState(0);
  const [commentsPage, setCommentsPage] = useState(1);

  const fetchStats = async () => {
    try {
      const [daily, fb, intent] = await Promise.all([
        client.get("/admin/stats/daily", { params: { days: 7 } }),
        client.get("/admin/stats/feedback", { params: { days: 7 } }),
        client.get("/admin/stats/intent", { params: { days: 7 } }),
      ]);
      setStats({ daily: daily.data, feedback: fb.data, intent: intent.data });
    } catch {
      message.error("统计数据加载失败");
    }
  };

  const fetchComments = async (page = 1) => {
    try {
      const { data } = await client.get("/admin/feedback-comments", {
        params: { page, page_size: 10 },
      });
      setComments(data.items);
      setCommentsTotal(data.total);
      setCommentsPage(page);
    } catch {
      // 静默
    }
  };

  useEffect(() => {
    (async () => {
      await Promise.all([fetchStats(), fetchComments()]);
      setLoading(false);
    })();
  }, []);

  if (loading)
    return (
      <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: 300 }}>
        <Spin description={<span style={{ color: "var(--color-cyan)", fontFamily: "var(--font-display)", letterSpacing: "0.06em" }}>加载统计数据中</span>} />
      </div>
    );

  const fb = stats.feedback?.summary || {};
  const dl = stats.daily?.summary || {};
  const dailyData = (stats.daily?.data || []).map((d: any) => ({
    date: d.date,
    value: d.total_questions,
  }));

  const statCards = [
    { title: "7日总提问", value: dl.total_questions || 0, accent: "var(--color-cyan)", icon: <MessageOutlined /> },
    { title: "日均提问", value: dl.avg_daily || 0, accent: "var(--color-cyan)", icon: <MessageOutlined /> },
    { title: "好评数", value: fb.total_likes || 0, accent: "var(--color-success)", icon: <LikeOutlined /> },
    { title: "好评率", value: fb.like_rate || 0, suffix: "%", accent: "var(--color-success)", icon: <LikeOutlined /> },
  ];

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
        管理后台
      </h2>

      {/* 统计卡片 */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        {statCards.map((card, idx) => (
          <Col span={6} key={idx}>
            <Card
              style={{
                border: `1px solid rgba(0, 229, 255, 0.08)`,
                boxShadow: `0 0 16px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(0, 229, 255, 0.04)`,
                transition: "border-color 0.2s",
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLElement).style.borderColor = "rgba(0, 229, 255, 0.2)";
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLElement).style.borderColor = "rgba(0, 229, 255, 0.08)";
              }}
            >
              <Statistic
                title={
                  <span style={{ fontFamily: "var(--font-display)", fontSize: 11, letterSpacing: "0.06em", color: "var(--color-steel-dim)" }}>
                    {card.title}
                  </span>
                }
                value={card.value}
                suffix={card.suffix}
                prefix={card.icon}
                valueStyle={{
                  color: card.accent,
                  fontFamily: "var(--font-display)",
                  fontWeight: 600,
                  letterSpacing: "0.04em",
                }}
              />
            </Card>
          </Col>
        ))}
      </Row>

      {/* 日均问答折线图 + 意图分布 */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={14}>
          <Card
            title={
              <span style={{ fontFamily: "var(--font-display)", color: "var(--color-steel)", letterSpacing: "0.06em", fontSize: 15 }}>
                日均问答趋势
              </span>
            }
            style={{
              border: "1px solid var(--color-border-lit)",
              boxShadow: "var(--glow-card)",
            }}
          >
            <SparkLine data={dailyData} width={620} height={200} />
          </Card>
        </Col>
        <Col span={10}>
          <Card
            title={
              <span style={{ fontFamily: "var(--font-display)", color: "var(--color-steel)", letterSpacing: "0.06em", fontSize: 15 }}>
                意图分布
              </span>
            }
            style={{
              border: "1px solid var(--color-border-lit)",
              boxShadow: "var(--glow-card)",
            }}
          >
            <Table
              dataSource={stats.intent?.data || []}
              rowKey="intent"
              columns={[
                { title: "意图", dataIndex: "intent" },
                {
                  title: "数量",
                  dataIndex: "count",
                  render: (v: number) => (
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: 13, color: "var(--color-cyan)" }}>
                      {v}
                    </span>
                  ),
                },
                {
                  title: "占比",
                  dataIndex: "pct",
                  render: (v: number) => (
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>
                      {v}%
                    </span>
                  ),
                },
              ]}
              pagination={false}
              size="small"
            />
          </Card>
        </Col>
      </Row>

      {/* 用户文字反馈记录 */}
      <Card
        title={
          <span style={{ fontFamily: "var(--font-display)", color: "var(--color-steel)", letterSpacing: "0.06em", fontSize: 15 }}>
            <CommentOutlined style={{ marginRight: 8, color: "var(--color-amber)" }} />
            文字反馈记录
          </span>
        }
        style={{
          border: "1px solid var(--color-border-lit)",
          boxShadow: "var(--glow-card)",
        }}
      >
        <Table
          dataSource={comments}
          rowKey="id"
          size="small"
          pagination={{
            current: commentsPage,
            total: commentsTotal,
            pageSize: 10,
            onChange: (page) => fetchComments(page),
            showTotal: (t) => `共 ${t} 条`,
          }}
          columns={[
            {
              title: "用户",
              dataIndex: "user",
              width: 120,
              render: (u: FeedbackComment["user"]) => (
                <span style={{ fontSize: 12 }}>{u.nickname || u.phone || u.email || "—"}</span>
              ),
            },
            {
              title: "评价",
              dataIndex: "rating",
              width: 70,
              render: (v: string) =>
                v === "dislike" ? (
                  <Tag color="error" style={{ fontSize: 11 }}>👎 差评</Tag>
                ) : (
                  <Tag color="success" style={{ fontSize: 11 }}>👍 好评</Tag>
                ),
            },
            {
              title: "反馈内容",
              dataIndex: "comment",
              ellipsis: true,
              render: (v: string) => (
                <span style={{ fontSize: 12, color: "var(--color-steel)" }}>{v}</span>
              ),
            },
            {
              title: "时间",
              dataIndex: "created_at",
              width: 160,
              render: (v: string) => (
                <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--color-steel-dim)" }}>
                  {v ? new Date(v).toLocaleString("zh-CN") : ""}
                </span>
              ),
            },
          ]}
        />
      </Card>
    </div>
  );
}
