# core/classifier.py
import sys
import os

# 1. 动态添加项目根目录到 Python 搜索路径
# 获取当前文件 (classifier.py) 的上一级 (core) 的上一级 (shipping_agent_v2)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

# core/classifier.py
import json
import logging
from core.llm_client import LLMClient
from config.prompt_templates import CLASSIFY_SYSTEM_PROMPT

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EmailClassifier:
    def __init__(self):
        self.llm = LLMClient()

    # 🔥 核心修改：增加了 sender 参数，并给默认值防止报错 🔥
    def classify(self, email_subject: str, email_body: str, sender: str = None):
        """
        输入邮件标题和正文，返回分类结果 (JSON Dict)
        """
        # 1. 预处理：截取前 1500 字符 (通常开头就能看出类型，省钱)
        # 很多邮件后面全是免责声明，没用
        clean_body = email_body[:1500].replace("\r", "").replace("\n", " ")

        # 处理 sender 为空的情况
        sender_info = sender if sender else "Unknown"

        # 2. 构建 User Prompt (把发件人信息喂给 AI)
        user_content = f"""
        Sender: {sender_info}
        Subject: {email_subject}

        Body Snippet:
        {clean_body}
        """

        # 3. 调用 AI
        # logger.info(f"正在分类邮件: {email_subject[:30]}...")
        # (注释掉上面这行，减少刷屏，main_v2 已经有进度条了)

        response_str = self.llm.get_completion(
            prompt=user_content,
            system_prompt=CLASSIFY_SYSTEM_PROMPT,
            response_format="json_object"
        )

        # 4. 解析结果
        if not response_str:
            return "OTHER" # 简化返回，直接返回类型字符串，为了配合 main_v2 的逻辑

        try:
            # 清洗一下 AI 可能返回的 Markdown 标记 (以防万一)
            response_str = response_str.replace("```json", "").replace("```", "").strip()
            result = json.loads(response_str)

            # 获取类型，并转大写
            email_type = result.get('type', 'OTHER').upper()

            # 安全校验
            valid_types = ["TONNAGE", "CARGO", "FIXTURE", "MARKET", "OTHER"]
            if email_type not in valid_types:
                email_type = "OTHER"

            # 打印调试信息 (可选，保留 debug 用)
            # logger.info(f"分类: [{email_type}] (Conf: {result.get('confidence')})")

            # 🔥 注意：main_v2 目前只需要返回字符串类型，不需要整个字典 🔥
            # 如果你需要 reason，可以改回 return result，但 main_v2 也要相应修改
            # 为了你现在的 main_v2 能直接跑通，我们直接返回字符串
            return email_type

        except json.JSONDecodeError:
            logger.error(f"JSON 解析失败. AI 返回: {response_str}")
            return "OTHER"

# ==========================================
# 单元测试 (直接运行此文件时执行)
# ==========================================
if __name__ == "__main__":
    classifier = EmailClassifier()

    print("\n--- 测试开始 ---")

    # 测试案例 1: 船源
    subj1 = "OPEN LIST // MV SEAJOURNEY // broker@example.com"
    body1 = "Good day, Please propose: MV SEAJOURNEY Open E.MED 28 DEC."
    classifier.classify(subj1, body1)

    # 测试案例 2: 合成的 Recap 邮件
    subj2 = "RE: MV EXAMPLE / DEMO CHARTERER - MAINTERM RECAP"
    body2 = "We are pleased to confirm this synthetic recap for testing."
    classifier.classify(subj2, body2)

    # 测试案例 3: 合成货盘邮件
    subj3 = "ACC LANGLOIS BLACK SEA ORDER"
    body3 = "Need vsl for 30k grain Black Sea to WAFR."
    classifier.classify(subj3, body3)

    print("\n--- 测试结束 ---")
