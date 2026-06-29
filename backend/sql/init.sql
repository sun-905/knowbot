-- AI智能客服系统 — 数据库初始化脚本
-- MySQL 8.0+, 字符集 utf8mb4

CREATE TABLE IF NOT EXISTS users (
    id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    phone         VARCHAR(20)    DEFAULT NULL COMMENT '手机号',
    email         VARCHAR(255)   DEFAULT NULL COMMENT '邮箱',
    password_hash VARCHAR(255)   NOT NULL COMMENT '密码哈希(bcrypt)',
    nickname      VARCHAR(100)   DEFAULT '' COMMENT '昵称',
    avatar_url    VARCHAR(500)   DEFAULT '' COMMENT '头像URL',
    daily_quota   INT            DEFAULT 100 COMMENT '每日提问上限',
    is_admin      TINYINT(1)     DEFAULT 0 COMMENT '是否管理员(0=否,1=是)',
    is_active     TINYINT(1)     DEFAULT 1 COMMENT '是否启用',
    created_at    DATETIME       DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME       DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_phone (phone),
    UNIQUE KEY uk_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表';

CREATE TABLE IF NOT EXISTS sessions (
    id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id     BIGINT UNSIGNED NOT NULL COMMENT '用户ID',
    title       VARCHAR(200)    DEFAULT '新对话' COMMENT '会话标题',
    status      ENUM('active','closed') DEFAULT 'active' COMMENT '会话状态',
    created_at  DATETIME        DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME        DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_user_created (user_id, created_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='会话表';

CREATE TABLE IF NOT EXISTS messages (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    session_id      BIGINT UNSIGNED NOT NULL COMMENT '会话ID',
    role            ENUM('user','assistant','system') NOT NULL COMMENT '角色',
    content         TEXT            NOT NULL COMMENT '消息内容',
    intent          VARCHAR(50)     DEFAULT NULL COMMENT '意图分类及来源(如: 产品咨询|vector|0.92)',
    references_json JSON            DEFAULT NULL COMMENT '引用来源(assistant消息)',
    token_count     INT             DEFAULT 0 COMMENT 'Token消耗数',
    created_at      DATETIME        DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_session_id (session_id),
    INDEX idx_session_created (session_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='消息表';

CREATE TABLE IF NOT EXISTS knowledge_bases (
    id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(200)  NOT NULL COMMENT '知识库名称',
    description VARCHAR(500)  DEFAULT '' COMMENT '知识库描述',
    is_default  TINYINT(1)    DEFAULT 0 COMMENT '是否默认知识库',
    created_at  DATETIME      DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME      DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='知识库表';

CREATE TABLE IF NOT EXISTS knowledge_docs (
    id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    kb_id       BIGINT UNSIGNED DEFAULT 1 COMMENT '知识库ID',
    filename    VARCHAR(500)    NOT NULL COMMENT '原始文件名',
    file_type   ENUM('txt','md','pdf') NOT NULL COMMENT '文件类型',
    file_size   INT UNSIGNED    DEFAULT 0 COMMENT '文件大小(字节)',
    chunk_count INT UNSIGNED    DEFAULT 0 COMMENT '切片数量',
    status      ENUM('processing','ready','failed') DEFAULT 'processing',
    error_msg   VARCHAR(500)    DEFAULT NULL COMMENT '失败原因',
    created_at  DATETIME        DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME        DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_kb_id (kb_id),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='知识库文档表';

CREATE TABLE IF NOT EXISTS feedbacks (
    id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    message_id  BIGINT UNSIGNED NOT NULL COMMENT '消息ID',
    user_id     BIGINT UNSIGNED NOT NULL COMMENT '用户ID',
    rating      ENUM('like','dislike') NOT NULL COMMENT '评价类型',
    comment     VARCHAR(500)    DEFAULT NULL COMMENT '文字反馈',
    created_at  DATETIME        DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_user_message (user_id, message_id),
    INDEX idx_message_id (message_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='反馈表';

CREATE TABLE IF NOT EXISTS daily_usage (
    id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id     BIGINT UNSIGNED NOT NULL,
    usage_date  DATE            NOT NULL,
    count       INT UNSIGNED    DEFAULT 0 COMMENT '当日已用次数',
    created_at  DATETIME        DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME        DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_user_date (user_id, usage_date),
    INDEX idx_user_date (user_id, usage_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='每日配额使用表';

-- 默认知识库初始数据
INSERT INTO knowledge_bases (id, name, description, is_default)
VALUES (1, '默认知识库', '系统默认知识库', 1)
ON DUPLICATE KEY UPDATE name=name;
