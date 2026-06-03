# 导入 LangChain 提示模板
from langchain_core.prompts import PromptTemplate
# 导入日志和配置
from base import logger, Config
# 导入 OpenAI
from openai import OpenAI


class StrategySelector:
    def __init__(self):
        # 初始化 OpenAI 客户端
        self.client = OpenAI(api_key=Config().DASHSCOPE_API_KEY,
                             base_url=Config().DASHSCOPE_BASE_URL)
        # 获取策略选择提示模板
        self.strategy_prompt_template = self._get_strategy_prompt()

    def call_dashscope(self, prompt):
        # 调用 DashScope API
        try:
            # 创建聊天完成请求
            completion = self.client.chat.completions.create(
                model=Config().LLM_MODEL,
                messages=[
                    {"role": "system", "content": "你是一个有用的助手。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                timeout=30
            )
            # 返回完成结果
            return completion.choices[0].message.content if completion.choices else "直接检索"
        except Exception as e:
            # 记录 API 调用失败
            logger.error(f"DashScope API 调用失败: {e}")
            # 默认返回直接检索
            return "直接检索"

    def _get_strategy_prompt(self):
        #   定义私有方法，获取策略选择 Prompt 模板
        return PromptTemplate(
            template="""
            你是一个智能助手，负责分析用户查询 {query}，并从以下七种检索增强策略中选择一个最适合的策略，直接返回策略名称，不需要解释过程。

            以下是几种检索增强策略及其适用场景：

            1.  **直接检索：**
                * 描述：对用户查询直接进行检索，不进行任何增强处理。
                * 适用场景：适用于查询意图明确，需要从知识库中检索**特定信息**的问题，例如：
                    * 示例：
                        * 查询：企业微信怎么设置自动回复？
                        * 策略：直接检索
                    * 查询：钉钉考勤打卡定位不准怎么办？
                        * 策略：直接检索
            2.  **历史会话改写：**
                * 描述：结合对话历史，将含有省略指代的追问改写为独立完整的问题后检索。
                * 适用场景：适用于当前查询含指代词（它/这/那）、省略主语、或必须结合上文才能理解的追问，例如：
                    * 示例：
                        * 对话历史：用户刚问了企业微信自动回复。当前查询：那钉钉也有这个功能吗？
                        * 策略：历史会话改写
                    * 对话历史：用户刚问了VPN连接问题。当前查询：那怎么排查路由？
                        * 策略：历史会话改写
            3.  **关键词扩写：**
                * 描述：从用户问题中提取核心关键词，并扩展同义词、近义词和相关术语，用扩展后的关键词进行检索。
                * 适用场景：适用于短查询、术语单一但可多方面扩展的问题，例如：
                    * 示例：
                        * 查询：VPN连接失败
                        * 策略：关键词扩写
                    * 查询：CRM数据乱码
                        * 策略：关键词扩写
            4.  **伪答案改写（HyDE）：**
                * 描述：使用 LLM 生成一个假设的答案，然后基于假设答案进行检索。
                * 适用场景：适用于查询较为抽象，直接检索效果不佳的问题，例如：
                    * 示例：
                        * 查询：企业知识库系统如何帮助提升IT支持效率？
                        * 策略：伪答案改写
            5.  **缩写词改写：**
                * 描述：将用户问题中的缩写词、简称、行业术语替换为完整的正式名称后检索。
                * 适用场景：适用于查询中包含英文缩写或行业简称的问题，例如：
                    * 示例：
                        * 查询：ERP系统的MRP运算逻辑是什么？
                        * 策略：缩写词改写
                    * 查询：CRM中的MQL和SQL怎么区分？
                        * 策略：缩写词改写
            6.  **一般去噪改写：**
                * 描述：将复杂的用户查询转化为更基础、更易于检索的问题，去掉场景细节后检索。
                * 适用场景：适用于查询包含大量场景描述，核心意图被冗余细节包裹的问题，例如：
                    * 示例：
                        * 查询：我有一个包含 100 亿条记录的数据集，想把它存储到 Milvus 中进行查询。可以吗？
                        * 策略：一般去噪改写
            7.  **子查询改写：**
                * 描述：将复杂的用户查询拆分为多个简单的子查询，分别检索并合并结果。
                * 适用场景：适用于查询涉及多个实体或方面，需要分别检索不同信息的问题，例如：
                    * 示例：
                        * 查询：比较 Milvus 和 Zilliz Cloud 的优缺点。
                        * 策略：子查询改写

            根据用户查询 {query}，直接返回最适合的策略名称，例如 "直接检索"。不要输出任何分析过程或其他内容。
            """
            ,
            input_variables=["query"],
        )

    #   定义方法，选择检索策略
    def select_strategy(self, query):
        #   调用 LLM 获取检索策略
        strategy = self.call_dashscope(self.strategy_prompt_template.format(query=query)).strip()
        logger.info(f"为查询 '{query}' 选择的检索策略：{strategy}")
        return strategy


if __name__ == '__main__':
    ss = StrategySelector()
    print(ss.select_strategy('企业微信自动回复怎么设置以及钉钉考勤打卡定位不准怎么办？'))
