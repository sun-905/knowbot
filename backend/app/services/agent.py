"""
AI 智能体任务分解器

输入：自然语言需求 + 微服务文档
输出：TaskDAG（含节点、边和并行执行标记）
"""

import json
from dataclasses import dataclass, field

from loguru import logger

from ..core.llm_client import _get_deepseek
from ..core.config import settings


@dataclass
class TaskNode:
    """任务节点"""
    id: str
    service: str
    action: str
    description: str
    dependencies: list[str] = field(default_factory=list)


@dataclass
class TaskDAG:
    """任务有向无环图"""
    requirement: str
    nodes: list[TaskNode]
    parallel_groups: list[list[str]]  # 可以并行的节点 ID 分组

    def to_dict(self) -> dict:
        return {
            "requirement": self.requirement,
            "nodes": [
                {"id": n.id, "service": n.service, "action": n.action,
                 "description": n.description, "dependencies": n.dependencies}
                for n in self.nodes
            ],
            "parallel_groups": self.parallel_groups,
        }

    def to_mermaid(self) -> str:
        """导出为 Mermaid 流程图"""
        lines = ["graph TD"]
        for node in self.nodes:
            safe_id = node.id.replace(" ", "_")
            lines.append(f'    {safe_id}["{node.service}\\n{node.action}"]')
        for node in self.nodes:
            for dep in node.dependencies:
                safe_id = node.id.replace(" ", "_")
                safe_dep = dep.replace(" ", "_")
                lines.append(f"    {safe_dep} --> {safe_id}")
        return "\n".join(lines)


class TaskDecomposer:
    """使用大模型进行需求解析和依赖分析的 AI 智能体任务分解器"""

    def __init__(self, llm_client=None):
        self.llm = llm_client
        if self.llm is None:
            try:
                self.llm = _get_deepseek()
            except Exception as e:
                logger.warning(f"LLM 客户端不可用 — 智能体将仅以结构化模式运行: {e}")
                self.llm = None

    async def decompose(self, requirement: str, service_docs: list[dict]) -> TaskDAG:
        """将需求分解为任务 DAG"""
        logger.info(f"正在分解需求: {requirement[:100]}...")
        logger.info(f"可用服务: {[s['name'] for s in service_docs]}")

        # 步骤 1: 解析需求 → 提取实体和动作
        entities, actions = await self._parse_requirement(requirement)

        # 步骤 2: 将实体匹配到服务
        affected = await self._match_services(entities, service_docs)

        # 步骤 3: 分析服务间依赖
        dependencies = await self._analyze_dependencies(requirement, affected, service_docs)

        # 步骤 4: 构建 DAG（含拓扑分层）
        dag = self._build_dag(requirement, affected, dependencies)

        logger.info(f"DAG 构建完成: {len(dag.nodes)} 个节点, {len(dag.parallel_groups)} 个并行组")
        return dag

    async def _parse_requirement(self, requirement: str) -> tuple[list[str], list[str]]:
        """解析需求，提取关键实体和动作"""
        prompt = (
            "从以下需求中提取关键实体和动作。"
            "实体是业务对象（如：用户、订单、支付、通知）。"
            "动作是操作（如：创建、更新、发送、验证、通知）。"
            "返回 JSON：{\"entities\": [...], \"actions\": [...]}"
        )
        result = await self._call_llm(prompt, requirement)
        return result.get("entities", []), result.get("actions", [])

    async def _match_services(self, entities: list[str], service_docs: list[dict]) -> list[dict]:
        """将实体匹配到可用服务"""
        # 简单启发式：实体名匹配服务名和描述
        matched = []
        for svc in service_docs:
            svc_text = f"{svc.get('name', '')} {svc.get('description', '')} {svc.get('responsibilities', '')}"
            for entity in entities:
                if entity.lower() in svc_text.lower():
                    if svc["name"] not in [m["name"] for m in matched]:
                        matched.append(svc)
                    break
        # 若无匹配，降级使用 LLM
        if not matched:
            logger.info("启发式匹配无结果 — 降级使用 LLM 服务匹配")
            prompt = (
                "给定以下实体和可用服务，判断需要哪些服务。"
                f"实体: {json.dumps(entities)}\n"
                f"服务: {json.dumps([{'name': s['name'], 'description': s.get('description','')} for s in service_docs])}\n"
                "返回 JSON：{\"services\": [\"service_name1\", ...]}"
            )
            result = await self._call_llm(prompt, "")
            matched = [s for s in service_docs if s["name"] in result.get("services", [])]

        return matched

    async def _analyze_dependencies(
        self, requirement: str, affected: list[dict], service_docs: list[dict]
    ) -> dict[str, list[str]]:
        """分析服务间的执行依赖关系"""
        if len(affected) <= 1:
            return {}

        prompt = (
            "分析以下服务在给定需求中的执行依赖关系。"
            "对每对服务，判断是否存在依赖（如：支付依赖订单创建）。\n"
            f"需求: {requirement}\n"
            f"服务: {json.dumps([s['name'] for s in affected])}\n"
            f"服务详情: {json.dumps([{'name': s['name'], 'apis': s.get('apis', []), 'dependencies': s.get('dependencies', [])} for s in affected])}\n"
            "返回 JSON：{\"dependencies\": {\"service_a\": [\"service_b\"], ...}} "
            "（key 依赖 values — key 必须在 values 完成后才能开始）"
        )
        result = await self._call_llm(prompt, "")
        return result.get("dependencies", {})

    def _build_dag(self, requirement: str, affected: list[dict], dependencies: dict[str, list[str]]) -> TaskDAG:
        """根据服务和依赖关系构建 DAG，并计算拓扑分层（并行组）"""
        nodes = []
        for svc in affected:
            node = TaskNode(
                id=f"task_{svc['name'].replace(' ', '_').replace('-', '_')}",
                service=svc["name"],
                action=svc.get("primary_action", "process"),
                description=svc.get("description", ""),
                dependencies=[f"task_{d.replace(' ', '_').replace('-', '_')}" for d in dependencies.get(svc["name"], [])],
            )
            nodes.append(node)

        # 通过拓扑分层构建并行组
        in_degree = {n.id: len(n.dependencies) for n in nodes}
        node_map = {n.id: n for n in nodes}
        parallel_groups = []

        while in_degree:
            ready = [nid for nid, deg in in_degree.items() if deg == 0]
            if not ready:
                break
            parallel_groups.append(ready)
            for nid in ready:
                del in_degree[nid]
                for n in nodes:
                    if nid in n.dependencies:
                        in_degree[n.id] = max(0, in_degree.get(n.id, 1) - 1)

        return TaskDAG(requirement=requirement, nodes=nodes, parallel_groups=parallel_groups)

    async def _call_llm(self, system_prompt: str, user_message: str) -> dict:
        """调用 LLM，解析 JSON 响应"""
        if self.llm is None:
            logger.warning("LLM 不可用 — 返回空结果")
            return {}
        try:
            response = await self.llm.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": f"你是一个任务分解引擎。始终返回合法的 JSON。{system_prompt}"},
                    {"role": "user", "content": user_message or system_prompt},
                ],
                temperature=0,
                max_tokens=500,
            )
            raw = response.choices[0].message.content.strip()
            # 提取 JSON
            import re
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                return json.loads(match.group())
            return {}
        except Exception as e:
            logger.error(f"智能体 LLM 调用失败: {e}")
            return {}
