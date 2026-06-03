"""
Query 规则化改写模块
在 Redis 精确匹配之前对用户问题进行标准化，扩大 BM25 通道的命中面
"怎么处理" / "怎么办" / "咋回事" 统一去掉 → 提取核心实体做多级匹配 → 不引入向量判断，零误判风险
"""
import re
import hashlib
from typing import Optional, List, Tuple


class QueryNormalizer:
    def __init__(self):
        # ---------- 1. 语气词/疑问词 → 去掉 ----------
        self.filler_pattern = re.compile(
            r"(怎么处理|怎么办|咋回事|怎么回事|如何解决|如何处理"
            r"|请问|问一下|我想问|我想知道|帮我看一下|帮忙看看"
            r"|是什么|为什么|什么原因|是什么原因|怎么排查)",
            re.IGNORECASE
        )

        # ---------- 2. 同义词映射 ----------
        self.synonym_map = {
            "报错": "报错",
            "报-": "报错-",
            "错误码": "报错-",
            "错误代码": "报错-",
            "报了": "报错-",
            "返回": "报错-",
            "初始化报错": "初始化报错",
            "启动报错": "启动报错",
            "初始化报": "初始化报错-",
            "启动报": "启动报错-",
            "sdk": "SDK",
            "api": "API",
            "版本": "版本",
            "v2": "V2",
            "v3": "V3",
        }

        # ---------- 3. 错误码/实体提取正则 ----------
        # 匹配常见错误码格式: -1001, 0xABCD, E001, 10001
        self.error_code_pattern = re.compile(
            r"(-\d{3,6}|0x[0-9A-Fa-f]+|[A-Z]{1,3}\d{3,5}|\d{5,6})"
        )

    def normalize(self, query: str) -> str:
        """主入口：把原始 query 规则化为标准化短句"""
        q = query.strip()
        # 1. 去标点、统一空格
        q = re.sub(r"[，,。！？?！\s]+", "", q)
        # 2. 去语气词/疑问词
        q = self.filler_pattern.sub("", q)
        # 3. 同义词统一
        for old, new in self.synonym_map.items():
            q = q.replace(old, new)
        return q.strip()

    def extract_entity_key(self, query: str) -> Optional[str]:
        """提取核心实体作为索引键，如错误码、API 名"""
        # 尝试提取错误码
        match = self.error_code_pattern.search(query)
        if match:
            return f"err:{match.group(1)}"
        # 尝试提取 API 名称（大写字母+数字组合）
        api_match = re.search(r"([A-Z]{2,}\w{2,})", query)
        if api_match:
            return f"api:{api_match.group(1).lower()}"
        return None

    def get_lookup_keys(self, query: str) -> List[str]:
        """生成多级查找键，按优先级排列"""
        keys = []
        # 第1级：原始 query
        keys.append(query.strip())
        # 第2级：规则化后的 query
        normalized = self.normalize(query)
        if normalized and normalized != query.strip():
            keys.append(normalized)
        # 第3级：实体键
        entity_key = self.extract_entity_key(query)
        if entity_key:
            keys.append(entity_key)
        # 第4级：实体键 + 规则化 query 的 hash（精准兜底）
        if entity_key and normalized:
            keys.append(f"{entity_key}:{hashlib.md5(normalized.encode()).hexdigest()[:8]}")
        return keys

    def remake_answer_key(self, query: str) -> str:
        """生成缓存写入用的 key——用标准化后的 query"""
        return f"qa:{self.normalize(query)}"
