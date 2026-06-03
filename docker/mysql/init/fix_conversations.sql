-- 修复对话历史表结构
USE support_kb;

-- 如果表已存在，先删除（注意：这会清空历史数据，如果是生产环境请手动 ALTER TABLE）
DROP TABLE IF EXISTS conversations;

CREATE TABLE conversations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(36) NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_session_id (session_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

SELECT '对话历史表修复完成！' AS status;