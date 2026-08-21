# core/llm_client.py
from openai import OpenAI
# 从刚才写的 settings 导入变量
from config.settings import API_KEY, API_BASE_URL, MODEL_NAME

class LLMClient:
    def __init__(self):
        # 打印一下，方便调试 (上线后可以注释掉)
        # print(f"[LLM Init] Connecting to {API_BASE_URL} with model {MODEL_NAME}")

        if not API_KEY:
            raise ValueError("❌ 未找到 API Key，请检查 .env 文件！")

        self.client = OpenAI(
            api_key=API_KEY,
            base_url=API_BASE_URL
        )
        self.model = MODEL_NAME

    def get_completion(self, prompt: str, system_prompt: str = "You are a helpful assistant.", response_format="text") -> str:
        try:
            params = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1,
            }

            # DeepSeek 的 JSON 模式有时候需要显式指定，或者在 Prompt 里强调
            if response_format == "json_object":
                params["response_format"] = {"type": "json_object"}

            response = self.client.chat.completions.create(**params)
            return response.choices[0].message.content

        except Exception as e:
            print(f"[AI Error] 调用失败: {e}")
            return None