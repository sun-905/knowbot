import { useEffect, useState, useRef, useCallback } from "react";
import { Table, Button, Upload, App, Popconfirm, Tooltip, Tag } from "antd";
import {
  UploadOutlined,
  DeleteOutlined,
  ReloadOutlined,
  FileTextOutlined,
  FilePdfOutlined,
  FileMarkdownOutlined,
  CheckCircleFilled,
  SyncOutlined,
  CloseCircleFilled,
} from "@ant-design/icons";
import type { KnowledgeDoc } from "../api/knowledge";
import { listDocs, uploadDoc, deleteDoc } from "../api/knowledge";
import { useRequireAuth } from "../hooks/useAuth";

/** 文件类型 → 图标映射 */
const FILE_ICON: Record<string, React.ReactNode> = {
  pdf: <FilePdfOutlined style={{ color: "var(--color-danger)", marginRight: 6 }} />,
  md: <FileMarkdownOutlined style={{ color: "var(--color-cyan)", marginRight: 6 }} />,
  txt: <FileTextOutlined style={{ color: "var(--color-steel-dim)", marginRight: 6 }} />,
};

/** 状态配置 */
const STATUS_CONFIG: Record<string, { color: string; text: string; icon: React.ReactNode }> = {
  ready: {
    color: "var(--color-success)",
    text: "就绪",
    icon: <CheckCircleFilled style={{ marginRight: 4 }} />,
  },
  processing: {
    color: "var(--color-cyan)",
    text: "处理中",
    icon: <SyncOutlined spin style={{ marginRight: 4 }} />,
  },
  failed: {
    color: "var(--color-danger)",
    text: "失败",
    icon: <CloseCircleFilled style={{ marginRight: 4 }} />,
  },
};

/** 延迟刷新序列：3s → 8s → 16s → 30s（覆盖 0~60s 处理时长） */
const RETRY_DELAYS = [3000, 8000, 16000, 30000];

export default function Knowledge() {
  const { message } = App.useApp();
  useRequireAuth();
  const [docs, setDocs] = useState<KnowledgeDoc[]>([]);
  const [uploading, setUploading] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const loadedRef = useRef(false);

  const fetchDocs = useCallback(async () => {
    try {
      const data = await listDocs(1, 50);
      if (!data) return null;
      setDocs(data.items);
      loadedRef.current = true;
      return data.items as KnowledgeDoc[];
    } catch {
      // 首次加载失败才提示
      if (!loadedRef.current) message.error("加载文档列表失败");
      return null;
    }
  }, [message]);

  const stopTimer = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  /** 单次延迟刷新：处理完成则停，否则按序列延迟再次检查 */
  const scheduleRefresh = useCallback((retry: number) => {
    if (retry >= RETRY_DELAYS.length) return;
    stopTimer();
    timerRef.current = setTimeout(async () => {
      const items = await fetchDocs();
      if (!items) return;
      if (items.some((d) => d.status === "processing")) {
        scheduleRefresh(retry + 1);
      }
    }, RETRY_DELAYS[retry]);
  }, [fetchDocs, stopTimer]);

  useEffect(() => {
    fetchDocs().then((items) => {
      if (items?.some((d) => d.status === "processing")) {
        scheduleRefresh(0);
      }
    });
    return () => stopTimer();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleUpload = async (file: File) => {
    setUploading(true);
    try {
      const doc = await uploadDoc(file);
      message.success(`"${file.name}" 上传成功，后台处理中`);
      setDocs((prev) => [doc, ...prev]);
      scheduleRefresh(0);
    } catch (err: any) {
      message.error(err.response?.data?.detail || "上传失败");
    } finally {
      setUploading(false);
    }
    return false;
  };

  const handleDelete = async (id: number) => {
    try {
      setDocs((prev) => prev.filter((d) => d.id !== id));
      await deleteDoc(id);
      message.success("已删除");
      const data = await listDocs(1, 50);
      if (data) setDocs(data.items);
    } catch {
      message.error("删除失败");
      fetchDocs();
    }
  };

  const handleRefresh = () => {
    fetchDocs().then((items) => {
      if (items?.some((d) => d.status === "processing")) {
        scheduleRefresh(0);
      }
    });
  };

  const columns = [
    {
      title: "文档名称",
      dataIndex: "filename",
      ellipsis: true,
      render: (name: string, record: KnowledgeDoc) => (
        <span style={{ fontWeight: 500 }}>
          {FILE_ICON[record.file_type] || FILE_ICON.txt}
          {name}
        </span>
      ),
    },
    {
      title: "上传时间",
      dataIndex: "created_at",
      width: 180,
      render: (v: string) => (
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--color-steel-dim)" }}>
          {new Date(v).toLocaleString("zh-CN")}
        </span>
      ),
    },
    {
      title: "状态",
      dataIndex: "status",
      width: 120,
      render: (v: string, record: KnowledgeDoc) => {
        const cfg = STATUS_CONFIG[v];
        if (!cfg) return <Tag>{v}</Tag>;
        const tag = (
          <Tag
            color={undefined}
            style={{
              color: cfg.color,
              borderColor: cfg.color,
              background: "transparent",
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              letterSpacing: "0.04em",
            }}
          >
            <span style={{ display: "inline-flex", alignItems: "center" }}>
              {cfg.icon}
              {cfg.text}
            </span>
          </Tag>
        );
        // 失败时悬停显示错误详情
        if (v === "failed" && record.error_msg) {
          return (
            <Tooltip title={record.error_msg} color="var(--color-danger)" placement="topLeft">
              {tag}
            </Tooltip>
          );
        }
        return tag;
      },
    },
    {
      title: "操作",
      key: "action",
      width: 80,
      render: (_: any, record: KnowledgeDoc) => (
        <Popconfirm title="确定删除？删除后对应知识将不可检索" onConfirm={() => handleDelete(record.id)}>
          <Button icon={<DeleteOutlined />} danger size="small" style={{ borderRadius: 2 }} />
        </Popconfirm>
      ),
    },
  ];

  return (
    <div style={{ animation: "fade-in-up 0.3s ease" }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 20 }}>
        <h2
          style={{
            fontFamily: "var(--font-display)",
            color: "var(--color-cyan)",
            letterSpacing: "0.08em",
          }}
        >
          知识库管理
        </h2>
        <div style={{ display: "flex", gap: 8 }}>
          <Button
            icon={<ReloadOutlined />}
            onClick={handleRefresh}
            style={{ borderRadius: 2 }}
          >
            刷新
          </Button>
          <Upload
            beforeUpload={(file) => {
              handleUpload(file);
              return false;
            }}
            showUploadList={false}
            accept=".pdf,.txt,.md"
          >
            <Button
              type="primary"
              icon={<UploadOutlined />}
              loading={uploading}
              style={{ borderRadius: 2 }}
            >
              上传文档
            </Button>
          </Upload>
        </div>
      </div>
      <Table
        columns={columns}
        dataSource={docs}
        rowKey="id"
        size="middle"
        pagination={{ pageSize: 50 }}
        rowClassName={(record) =>
          record.status === "processing" ? "row-processing" : ""
        }
      />
    </div>
  );
}
