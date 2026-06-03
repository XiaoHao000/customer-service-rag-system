-- 创建 support_kb 数据库
CREATE DATABASE IF NOT EXISTS support_kb CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE support_kb;

-- FAQ 知识库表（与 init_data.py 中的 schema 保持一致）
CREATE TABLE IF NOT EXISTS faq_kb (
    id INT AUTO_INCREMENT PRIMARY KEY,
    product_line VARCHAR(50) COMMENT '产品线',
    question VARCHAR(1000) COMMENT '问题',
    answer TEXT COMMENT '答案',
    UNIQUE KEY uk_product_question (product_line(50), question(200))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 对话历史表
CREATE TABLE IF NOT EXISTS conversations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(36) NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    timestamp DATETIME NOT NULL,
    INDEX idx_session_id (session_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

SELECT '数据库初始化完成！' AS status;
