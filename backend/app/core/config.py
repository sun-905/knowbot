from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # MySQL
    database_url: str = "mysql+aiomysql://root:root123@127.0.0.1:3307/cs_bot?init_command=SET time_zone='%2B08:00'"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""

    # LLM (DeepSeek)
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    llm_model: str = "deepseek-chat"

    # LLM Backup (Qwen)
    qwen_api_key: str = ""
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # Embedding
    embedding_model: str = "BAAI/bge-large-zh-v1.5"
    embedding_device: str = "cuda"

    # App
    jwt_secret: str = "cs-bot-jwt-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440
    daily_quota_limit: int = 100
    max_question_length: int = 500
    max_context_rounds: int = 5
    retrieval_top_k: int = 5  # 默认值，被 K_floor/K_opt 覆盖前使用
    retrieval_top_k_floor: int = 0  # P95(gt_rank)+1，简单查询用；0=未校准，回退到 retrieval_top_k
    retrieval_top_k_opt: int = 0    # 窄窗消融最优值，复杂查询用；0=未校准，回退到 retrieval_top_k
    retrieval_threshold: float = 0.43
    retrieval_coarse_k: int = 20
    intent_clarify_threshold: float = 0.7

    # 查询改写
    query_rewrite_enabled: bool = True
    query_rewrite_timeout: float = 5.0  # 改写 LLM 调用超时（秒）
    query_rewrite_model: str = "deepseek-chat"  # 改写专用模型，可与主模型不同

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
