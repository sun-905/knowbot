"""
Test Agent Task Decomposer with mock service documentation.
Tests run without actual LLM calls — they validate DAG structure, dependency logic, and Mermaid output.
"""

import pytest
from app.services.agent import TaskDecomposer, TaskDAG, TaskNode


MOCK_SERVICES = [
    {
        "name": "user-service",
        "description": "用户信息管理、认证授权",
        "responsibilities": "用户注册、登录、信息查询、权限验证",
        "apis": ["GET /users/{id}", "POST /users", "PATCH /users/{id}"],
        "dependencies": [],
    },
    {
        "name": "order-service",
        "description": "订单创建、查询、状态管理",
        "responsibilities": "创建订单、查询订单、取消订单、修改订单",
        "apis": ["POST /orders", "GET /orders/{id}", "PATCH /orders/{id}/status"],
        "dependencies": ["user-service"],
    },
    {
        "name": "payment-service",
        "description": "支付处理、退款",
        "responsibilities": "发起支付、查询支付状态、退款处理",
        "apis": ["POST /payments", "GET /payments/{id}", "POST /payments/{id}/refund"],
        "dependencies": ["order-service"],
    },
    {
        "name": "notification-service",
        "description": "消息推送、短信、邮件、站内信",
        "responsibilities": "发送短信、发送邮件、推送通知、消息模板管理",
        "apis": ["POST /notifications/sms", "POST /notifications/email"],
        "dependencies": ["user-service"],
    },
]


class TestTaskNode:
    def test_node_creation(self):
        node = TaskNode(id="task_1", service="order-service", action="create", description="创建订单")
        assert node.id == "task_1"
        assert node.service == "order-service"
        assert node.dependencies == []

    def test_node_with_dependencies(self):
        node = TaskNode(id="task_2", service="payment-service", action="pay", description="处理支付", dependencies=["task_1"])
        assert "task_1" in node.dependencies


class TestTaskDAG:
    def test_to_dict(self):
        dag = TaskDAG(
            requirement="用户下单",
            nodes=[TaskNode(id="task_1", service="order-service", action="create", description="创建订单")],
            parallel_groups=[["task_1"]],
        )
        d = dag.to_dict()
        assert d["requirement"] == "用户下单"
        assert len(d["nodes"]) == 1
        assert d["parallel_groups"] == [["task_1"]]

    def test_to_mermaid(self):
        dag = TaskDAG(
            requirement="用户下单",
            nodes=[
                TaskNode(id="task_user", service="user-service", action="verify", description="验证用户"),
                TaskNode(id="task_order", service="order-service", action="create", description="创建订单", dependencies=["task_user"]),
            ],
            parallel_groups=[["task_user"], ["task_order"]],
        )
        mermaid = dag.to_mermaid()
        assert "graph TD" in mermaid
        assert "task_user" in mermaid
        assert "task_order" in mermaid
        assert "task_user --> task_order" in mermaid


class TestTaskDecomposer:
    def test_init(self):
        decomposer = TaskDecomposer()
        assert decomposer.llm is not None

    def test_build_dag_structure(self):
        decomposer = TaskDecomposer()
        affected = [
            {"name": "order-service", "description": "创建订单", "primary_action": "create_order"},
            {"name": "notification-service", "description": "发送通知", "primary_action": "send_notification"},
        ]
        dependencies = {"notification-service": ["order-service"]}

        dag = decomposer._build_dag("用户下单后通知", affected, dependencies)

        assert len(dag.nodes) == 2
        assert dag.requirement == "用户下单后通知"
        # notification-service depends on order-service
        notif_node = next(n for n in dag.nodes if n.service == "notification-service")
        assert len(notif_node.dependencies) == 1
        assert "order_service" in notif_node.dependencies[0]
        # parallel groups: order first, then notification
        assert len(dag.parallel_groups) >= 1
        assert any("order_service" in g[0] for g in dag.parallel_groups if g)

    def test_parallel_detection(self):
        decomposer = TaskDecomposer()
        affected = [
            {"name": "user-service", "description": "验证用户", "primary_action": "verify"},
            {"name": "order-service", "description": "创建订单", "primary_action": "create"},
            {"name": "notification-service", "description": "发短信", "primary_action": "notify"},
        ]
        dependencies = {
            "order-service": ["user-service"],
            "notification-service": ["user-service", "order-service"],
        }

        dag = decomposer._build_dag("下单后发通知", affected, dependencies)

        assert len(dag.nodes) == 3
        # user-service should be in first parallel group (no deps)
        first_group = dag.parallel_groups[0]
        assert any("user_service" in nid for nid in first_group)
        # notification-service should be last (depends on both)
        last_group = dag.parallel_groups[-1]
        assert any("notification_service" in nid for nid in last_group)
