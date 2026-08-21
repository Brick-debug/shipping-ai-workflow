# database/schema.py
from dataclasses import dataclass, asdict, field
from typing import Optional, List

@dataclass
class BaseSchema:
    def to_dict(self):
        return {k: v for k, v in asdict(self).items()}

# 1. 船源表 (Tonnage)
@dataclass
class VesselItem(BaseSchema):
    # 核心数据
    vessel_name: str = ""
    imo: Optional[str] = ""
    dwt: int = 0
    built_year: Optional[int] = None
    vessel_type: str = ""
    open_port: str = ""
    open_region: str = ""

    # --- Laycan 结构化 (V3.0 新增) ---
    laycan_raw: str = ""          # 原文: "End Jan"
    laycan_from: str = ""         # 机器读: "2026-01-25"
    laycan_to: str = ""           # 机器读: "2026-01-31"

    operator: str = ""
    # --- 核心硬指标 (V2.5 新增) ---
    cranes: str = ""              # 吊机 (e.g. 4x30t)
    tanktop_strength: str = ""    # 舱底板强度 (e.g. 20t/m2)
    speed_consumption: str = ""   # 航速油耗 (e.g. 12kn/24mt)
    preferred_trade: str = ""     # 船东偏好 (e.g. Pref Pacific)
    features: List[str] = field(default_factory=list) # 其他杂项

    # 证据链 & 元数据
    raw_snippet: str = ""
    original_body: str = ""
    email_subject: str = ""
    sender: str = ""
    sent_time: str = ""
    fetch_time: str = ""

# 2. 货盘表 (Cargo)
@dataclass
class CargoItem(BaseSchema):
    # 核心数据
    cargo_name: str = ""
    charterer: str = ""           # 租家 / charterer
    quantity_raw: str = ""
    quantity_num: int = 0     # <--- 🌟 改成 int = 0，完美匹配纯数字，方便未来算数学题
    load_port: str = ""
    load_region: str = ""       # <--- 🆕 新增装货大区
    discharge_port: str = ""
    discharge_region: str = ""  # <--- 🆕 新增卸货大区

    # --- Laycan 结构化 (V3.0 新增) ---
    laycan_raw: str = ""
    laycan_from: str = ""
    laycan_to: str = ""

    terms: str = ""
    special_requirements: str = "" # 特殊要求 / special requirements

    # 证据链 & 元数据
    raw_snippet: str = ""
    original_body: str = ""
    email_subject: str = ""
    sender: str = ""
    sent_time: str = ""
    fetch_time: str = ""

# 3. 归档表 (Market/Fixture Log) - 当前主力
@dataclass
class RawItem(BaseSchema):
    category: str = ""      # 类型: FIXTURE / MARKET / OTHER
    subject: str = ""       # 标题
    body: str = ""          # 全文
    sender: str = ""        # 发件人
    sent_time: str = ""     # 发送时间 (修复了这里的重复)
    fetch_time: str = ""    # 抓取时间

# 4. 成交表 (Fixture) - 未来备用，暂时留空
@dataclass
class FixtureItem(BaseSchema):
    vessel_name: str = ""
    charterer: str = ""
    price: str = ""
    route: str = ""
    fixture_date: str = ""
    source_type: str = "EMAIL"
    # 补齐元数据，防止未来用的时候报错
    original_body: str = ""
    email_subject: str = ""
    sender: str = ""
    sent_time: str = ""
    fetch_time: str = ""
