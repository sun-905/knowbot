import client from "./client";

export interface KnowledgeDoc {
  id: number;
  kb_id: number;
  filename: string;
  file_type: string;
  file_size: number;
  chunk_count: number;
  status: string;
  error_msg: string | null;
  created_at: string;
}

export async function uploadDoc(file: File, kbId = 1): Promise<KnowledgeDoc> {
  const form = new FormData();
  form.append("file", file);
  form.append("kb_id", String(kbId));
  const { data } = await client.post("/knowledge/docs/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

/** 同一时间最多 1 个 listDocs 请求，新请求会取消旧请求 */
let listDocsController: AbortController | null = null;

export async function listDocs(page = 1, pageSize = 20) {
  // 取消前一个未完成的请求，确保同时只有 1 个 inflight
  if (listDocsController) {
    listDocsController.abort();
  }
  const ctrl = new AbortController();
  listDocsController = ctrl;
  try {
    const { data } = await client.get("/knowledge/docs", {
      params: { page, page_size: pageSize },
      timeout: 8000,
      signal: ctrl.signal,
    });
    return data;
  } catch (err: any) {
    // 被新请求取消时静默，不抛异常
    if (err?.code === "ERR_CANCELED" || err?.name === "CanceledError") {
      return null;
    }
    throw err;
  } finally {
    if (listDocsController === ctrl) {
      listDocsController = null;
    }
  }
}

export async function deleteDoc(docId: number): Promise<void> {
  await client.delete(`/knowledge/docs/${docId}`);
}

export interface KnowledgeBase {
  id: number;
  name: string;
  description: string;
  is_default: boolean;
}

export async function listBases(): Promise<KnowledgeBase[]> {
  const { data } = await client.get("/knowledge/bases");
  return data;
}

export async function createBase(name: string, description = ""): Promise<KnowledgeBase> {
  const { data } = await client.post("/knowledge/bases", { name, description });
  return data;
}

export async function deleteBase(baseId: number): Promise<void> {
  await client.delete(`/knowledge/bases/${baseId}`);
}
