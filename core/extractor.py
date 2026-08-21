# core/extractor.py
import sys
import os
import re
import json
import logging
from datetime import datetime # 记得导入

# 寻根逻辑
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from core.llm_client import LLMClient
from config.prompt_templates import VESSEL_EXTRACT_PROMPT, CARGO_EXTRACT_PROMPT
from database.schema import VesselItem, CargoItem

# logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DataExtractor:
    def __init__(self, llm_client: LLMClient = None):
        self.llm = llm_client or LLMClient()

    def _parse_json_response(self, response_str: str):
        """清洗 AI 返回的 JSON (带 Markdown 容错)"""
        if not response_str:
            return {}

        # 尝试清洗 Markdown 标记
        clean_str = str(response_str).replace("```json", "").replace("```", "").strip()

        try:
            return json.loads(clean_str)
        except json.JSONDecodeError:
            # 如果还不行，尝试用正则提取 {} 或 [] 内容
            m = re.search(r"(\{.*\}|\[.*\])", clean_str, re.S)
            if m:
                try:
                    return json.loads(m.group(0))
                except Exception:
                    pass
            logger.error(f"JSON 解析失败: {clean_str[:100]}...")
            return {"items": []}

    def _clean_number(self, value):
        """超级清洗器: 处理 '50k', '50,000', '33.5k' 等"""
        if not value: return 0

        s = str(value).lower().strip()

        # 1. 处理 'k' (千): 50k -> 50000
        if 'k' in s:
            match = re.search(r'([\d\.]+)\s*k', s)
            if match:
                try:
                    num = float(match.group(1))
                    return int(num * 1000)
                except:
                    pass

        # 2. 去除逗号
        clean_s = s.replace(",", "")

        # 3. 提取第一个有效数字
        match = re.search(r'(\d+(\.\d+)?)', clean_s)
        if match:
            try:
                return int(float(match.group(1)))
            except:
                return 0
        return 0

    def extract_vessel(self, email_body: str) -> list[VesselItem]:
        """提取船源信息 (含 V2.5 新字段 + V3.0 日期注入)"""

        # 🔥 V3.0 关键修改: 获取今天日期 🔥
        today_str = datetime.now().strftime("%Y-%m-%d")

        # 🔥 V3.0 关键修改: 动态填入 Prompt 🔥
        # 使用 replace 而不是 format，防止破坏 Prompt 里原本的 JSON 大括号
        system_prompt_filled = VESSEL_EXTRACT_PROMPT.replace("{current_date}", today_str)

        prompt = f"邮件正文:\n{email_body[:2500]}"

        response_str = self.llm.get_completion(
            prompt=prompt,
            system_prompt=system_prompt_filled, # <--- 注意这里用了填充后的 prompt
            response_format="json_object"
        )

        data = self._parse_json_response(response_str)
        items = []

        for item_dict in data.get("items", []):
            try:
                # 清洗数字
                dwt_val = self._clean_number(item_dict.get("dwt"))
                built_val = self._clean_number(item_dict.get("built_year"))

                # 年份校验
                if built_val is not None and (built_val < 1980 or built_val > 2030):
                    built_val = None

                vessel = VesselItem(
                    vessel_name=item_dict.get("vessel_name", "Unknown"),
                    dwt=dwt_val,
                    built_year=built_val,
                    vessel_type=item_dict.get("vessel_type", ""),
                    open_port=item_dict.get("open_port", ""),
                    open_region=item_dict.get("open_region", ""),

                    # 🔥 V3.0 Laycan 结构化 🔥
                    laycan_raw=item_dict.get("laycan_raw", ""),
                    laycan_from=item_dict.get("laycan_from", ""),
                    laycan_to=item_dict.get("laycan_to", ""),

                    operator=item_dict.get("operator", ""),
                    features=item_dict.get("features", []),

                    # 🔥 V2.5 新增字段映射 🔥
                    cranes=str(item_dict.get("cranes", "")),
                    tanktop_strength=str(item_dict.get("tanktop_strength", "")),
                    speed_consumption=str(item_dict.get("speed_consumption", "")),
                    preferred_trade=str(item_dict.get("preferred_trade", "")),

                    # 证据链
                    raw_snippet=item_dict.get("raw_snippet", "")
                )
                items.append(vessel)
            except Exception as e:
                logger.warning(f"跳过错误数据: {e}")
        return items

    def extract_cargo(self, email_body: str) -> list[CargoItem]:
        """提取货盘信息 (含 V3.0 日期注入)"""

        # 🔥 V3.0: 货盘也可能有 PPT，所以也注入日期 🔥
        today_str = datetime.now().strftime("%Y-%m-%d")

        # 如果 CARGO Prompt 里没写 {current_date}，这行代码也不会报错，只是不替换而已，很安全
        system_prompt_filled = CARGO_EXTRACT_PROMPT.replace("{current_date}", today_str)

        prompt = f"邮件正文:\n{email_body[:2500]}"

        response_str = self.llm.get_completion(
            prompt=prompt,
            system_prompt=system_prompt_filled, # <--- 使用填充版
            response_format="json_object"
        )

        data = self._parse_json_response(response_str)
        items = []

        for item_dict in data.get("items", []):
            try:
                # ==========================================
                # 🛡️ 强制防弹处理：应对 AI 的幻觉和旧字段
                # ==========================================
                # 1. 提取 raw (如果 AI 输出了 quantity_raw 就用，如果输出了旧的 quantity 也兼容)
                raw_qty = str(item_dict.get("quantity_raw", item_dict.get("quantity", "")))

                # 2. 提取 num 并强制转为数字，防崩溃
                num_qty = item_dict.get("quantity_num", 0)
                try:
                    num_qty = int(num_qty)
                except:
                    num_qty = 0
                # ==========================================

                cargo = CargoItem(
                    cargo_name=item_dict.get("cargo_name", ""),
                    charterer=item_dict.get("charterer", ""),             # <--- 新增这行
                    # 🔥 这里的两个字段完美对接了你新的 Schema 🔥
                    quantity_raw=raw_qty,
                    quantity_num=num_qty,
                    # quantity=str(item_dict.get("quantity", "")),
                    load_port=item_dict.get("load_port", ""),
                    load_region=item_dict.get("load_region", "UNKNOWN"),       # <--- 🆕 新增
                    discharge_region=item_dict.get("discharge_region", "UNKNOWN"), # <--- 🆕 新增
                    discharge_port=item_dict.get("discharge_port", ""),

                    # 🔥 V3.0 Laycan 结构化 🔥
                    laycan_raw=item_dict.get("laycan_raw", ""),
                    laycan_from=item_dict.get("laycan_from", ""),
                    laycan_to=item_dict.get("laycan_to", ""),

                    terms=item_dict.get("commission", ""),
                    special_requirements=item_dict.get("special_requirements", ""), # <--- 新增这行

                    # 证据链
                    raw_snippet=item_dict.get("raw_snippet", "")
                )
                items.append(cargo)
            except Exception as e:
                 logger.warning(f"跳过一条错误数据: {e}")
        return items