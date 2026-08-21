# core/exporter.py
import pandas as pd
import os
import re # <--- 必须导入正则库
from datetime import datetime

class ExcelExporter:
    def __init__(self, output_dir="data/output"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

        # Region normalization used by the prototype workflow.
        self.REGION_MAP = {
            # CJK / TAIWAN
            "CJK": "CJK", "SHANGHAI": "CJK", "TAICANG": "CJK", "NANTONG": "CJK",
            "ZHANGJIAGANG": "CJK", "NINGBO": "CJK", "ZHOUSHAN": "CJK", "DAFENG": "CJK",
            "TAIWAN": "CJK", "KAOHSIUNG": "CJK", "TAICHUNG": "CJK", "MAILIAO": "CJK",

            # N.CHINA
            "N.CHINA": "N.CHINA", "TIANJIN": "N.CHINA", "XINGANG": "N.CHINA", "CAOFEIDIAN": "N.CHINA",
            "JINGTANG": "N.CHINA", "BAYUQUAN": "N.CHINA", "QINGDAO": "N.CHINA", "RIZHAO": "N.CHINA",
            "YANTAI": "N.CHINA", "DALIAN": "N.CHINA", "LANSHAN": "N.CHINA", "LIAONING": "N.CHINA",

            # S.CHINA
            "S.CHINA": "S.CHINA", "HONG KONG": "S.CHINA", "GUANGZHOU": "S.CHINA",
            "NANSHA": "S.CHINA", "FANGCHENG": "S.CHINA", "QINZHOU": "S.CHINA", "ZHANJIANG": "S.CHINA",

            # SE.ASIA
            "SINGAPORE": "SE.ASIA", "HO CHI MINH": "SE.ASIA", "PHU MY": "SE.ASIA",
            "INDONESIA": "SE.ASIA", "VIETNAM": "SE.ASIA", "THAILAND": "SE.ASIA",
            "MALAYSIA": "SE.ASIA", "PHILIPPINES": "SE.ASIA",

            # 🔥 [修改] 印度次大陆拆分 (实务逻辑) 🔥
            # 1. WC.India (印西 - 靠近 PG)
            "KANDLA": "WC.India", "MUNDRA": "WC.India", "MUMBAI": "WC.India",
            "NEW MANGALORE": "WC.India", "MORMUGAO": "WC.India", "GOA": "WC.India",
            "SIKKA": "WC.India", "HAZIRA": "WC.India",

            # 2. EC.India (印东 - 靠近 SE.Asia)
            "HALDIA": "EC.India", "PARADIP": "EC.India", "VISAKHAPATNAM": "EC.India",
            "VIZAG": "EC.India", "GANGAVARAM": "EC.India", "CHENNAI": "EC.India",
            "ENNORE": "EC.India", "KRISHNAPATNAM": "EC.India", "DHAMRA": "EC.India",
            "KAKINADA": "EC.India",

            # 3. ISC (其他次大陆 / 泛指)
            # 如果邮件只写 "India" 没写港口，只能归入 ISC
            "INDIA": "ISC",
            # 巴基斯坦和孟加拉通常归为 ISC，或者你也可以单独列出来
            "BANGLADESH": "ISC", "CHITTAGONG": "ISC", "MONGLA": "ISC",
            "PAKISTAN": "ISC", "KARACHI": "ISC", "PORT QASIM": "ISC",
            "SRI LANKA": "ISC", "COLOMBO": "ISC", "TRINCOMALEE": "ISC",

            # OTHERS
            "RED SEA": "Red Sea", "JEDDAH": "Red Sea",
            "ROTTERDAM": "N.CONT", "ANTWERP": "N.CONT",
            "SANTOS": "ECSA", "PARANAGUA": "ECSA",
            "RICHARDS BAY": "SE.AFRICA", "DURBAN": "SE.AFRICA",
            # Common dry-bulk market labels
            "ABIDJAN":"WAF", "LAGOS": "WAF", "LOME": "WAF", "WEST AFRICA": "WAF",
            "USG": "USG", "NEW ORLEANS": "USG",
            "MED": "MED", "ALEXANDRIA": "MED", "BLACK SEA": "MED", "BSEA": "MED",
            "COLOMBIA": "USG/NCSA",
        }

    def _get_vessel_class(self, dwt):
        """DWT 自动分类 (给单行数据定级)"""
        # 1. 如果是空值或者 0，直接返回 Unknown
        import pandas as pd # 确保顶部或者这里有导入 pandas 用来判断 pd.isna
        if pd.isna(dwt) or not dwt or str(dwt).strip() == "" or str(dwt) == "0":
            return "Unknown"

        # 2. 尝试把传进来的单个数字转换成整数并分类
        try:
            d = int(float(dwt))
            if d < 15000: return "Small"
            if 15000 <= d < 37000: return "Handysize"
            if 37000 <= d < 50000: return "Handymax"
            if 50000 <= d < 60000: return "Supramax"
            if 60000 <= d < 67000: return "Ultramax"
            if 67000 <= d < 85000: return "Panamax/Kamsarmax"
            if 85000 <= d < 110000: return "Post-Panamax"
            return "Capesize"
        except Exception:
            # 如果转换失败（比如混入了奇怪的字母），也返回 Unknown
            return "Unknown"

    def _map_region(self, port, current_region):
        """如果区域为空，尝试通过港口自动补全"""
        if current_region and len(current_region) > 2:
            return current_region
        if not port:
            return ""

        # 简单查字典 (转大写匹配)
        port_upper = str(port).upper().strip()
        for key, region in self.REGION_MAP.items():
            if key in port_upper:
                return region
        return ""

    # 🔥 V3.1 核心算法: 智能融合逻辑 🔥
    # 🔥 新增：强力清洗非法字符 (防崩关键) 🔥
    def _clean_illegal_chars(self, val):
        if isinstance(val, str):
            # 去除不可见字符 (0x00-0x1F) 但保留换行符
            # 这里的正则意思是：除了换行(\n)、回车(\r)、制表(\t)之外的控制符都删掉
            val = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', val)
        return val

    def _smart_merge_vessels(self, df):
        # 1. 预处理：确保有 valid_cols_count 辅助判断
        df['valid_cols_count'] = df.apply(lambda x: x.count(), axis=1)

        # 2. 定义融合函数 (针对每一组同名船)
        def merge_group(group):
            # A. 按时间降序排，第一条是最新的（作为 Master）
            group = group.sort_values(by='sent_time', ascending=False)
            master = group.iloc[0].copy()

            # B. 聚合信源 (把所有 Broker 拼起来)
            # 结果示例: "Arrow; Simpson; Maersk"
            all_senders = group['sender'].dropna().unique()
            master['sender'] = " | ".join(all_senders)

            # C. 聚合原文 (可选，为了溯源)
            # master['raw_snippet'] = " | ".join(group['raw_snippet'].dropna().unique())

            # D. 填补静态数据的空缺 (Backfill)
            # 如果 Master 的 DWT 是 0，但旧邮件里有，就拿过来
            static_cols = ['dwt', 'built_year', 'imo', 'vessel_type', 'cranes', 'tanktop_strength', 'speed_consumption']

            for col in static_cols:
                if col in master and (pd.isna(master[col]) or master[col] == 0 or master[col] == '' or str(master[col]) == 'None'):
                    # 在旧记录里找第一个非空的值
                    for _, row in group.iterrows():
                        val = row[col]
                        if not (pd.isna(val) or val == 0 or val == '' or str(val) == 'None'):
                            master[col] = val
                            break

            return master

        # 3. 应用分组融合
        # 注意：先按 vessel_name 分组
        merged_df = df.groupby('vessel_name', group_keys=False).apply(merge_group, include_groups=False).reset_index(drop=True)
        return merged_df

    def export(self, vessel_list: list, cargo_list: list, raw_list: list = None):
        if not vessel_list and not cargo_list and not raw_list:
            print("⚠️ 没有数据需要导出")
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Shipping_Data_{timestamp}.xlsx"
        filepath = os.path.join(self.output_dir, filename)

        # 0.1. 转换为 DataFrame
        df_vessel = pd.DataFrame([v.to_dict() for v in vessel_list]) if vessel_list else pd.DataFrame()
        df_cargo = pd.DataFrame([c.to_dict() for c in cargo_list]) if cargo_list else pd.DataFrame()
        df_raw = pd.DataFrame([r.to_dict() for r in raw_list]) if raw_list else pd.DataFrame()

        # 0.2. 🔥 关键修复：强制把 DWT 和 年份 转为数字格式 🔥
        # 这样你在 Excel 里就可以直接排序筛选了
        if not df_vessel.empty:
            # 1. 数字转换
            for col in ['dwt', 'built_year']:
                if col in df_vessel.columns:
                    df_vessel[col] = pd.to_numeric(df_vessel[col], errors='coerce').fillna(0).astype(int)

            # 2. Laycan 日期转换 (用于 Excel 筛选)
            for col in ['laycan_from', 'laycan_to']:
                if col in df_vessel.columns:
                    df_vessel[col] = pd.to_datetime(df_vessel[col], errors='coerce')

            # 3. 🔥 执行智能融合 (V3.1) 🔥
            # 先去重，再分类，效率更高
            print(f"⚡ 开始融合: 原始 {len(df_vessel)} 条...")
            df_vessel = self._smart_merge_vessels(df_vessel)
            print(f"✅ 融合完成: 剩余 {len(df_vessel)} 条独一无二的船源")

            # 4. DWT 分类 & 区域补全
            df_vessel['Vessel_Class'] = df_vessel['dwt'].apply(self._get_vessel_class)

            # 0.3. 🔥 区域自动映射补全 🔥
            df_vessel['open_region'] = df_vessel.apply(
                lambda row: self._map_region(row.get('open_port'), row.get('open_region')), axis=1
            )

            # 🔥 过滤过期 Laycan (时效性管理) 🔥
            today = pd.Timestamp.now().normalize()
            if 'laycan_to' in df_vessel.columns:
                # 保留：Laycan结束时间 >= 今天 OR Laycan为空的(模糊时间)
                df_vessel = df_vessel[ (df_vessel['laycan_to'] >= today) | (df_vessel['laycan_to'].isna()) ]

            # 🔥 全局非法字符清洗 🔥
            df_vessel = df_vessel.map(self._clean_illegal_chars)

        # --- 货盘表清洗 ---
        if not df_cargo.empty:
             df_cargo = df_cargo.map(self._clean_illegal_chars)

        # 🔥 新增：利用现有字典，通过卸港自动推算货盘的流向区域 (Direction / BH) 🔥
             df_cargo['discharge_region'] = df_cargo.apply(
                 lambda row: self._map_region(row.get('discharge_port'), ""), axis=1
             )

        # --- 原始数据清洗 ---
        if not df_raw.empty:
             df_raw = df_raw.map(self._clean_illegal_chars)

        try:
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                # Sheet 1: Tonnage
                if not df_vessel.empty:
                    # 定义列顺序 (把好用的放前面)
                    cols = [
                        'Vessel_Class', 'vessel_name', 'dwt', 'built_year',
                        'open_port', 'open_region',
                        'laycan_from', 'laycan_to', 'laycan_raw', # 日期放前面
                        'cranes', 'tanktop_strength', 'speed_consumption', 'preferred_trade',
                        'operator', 'sent_time', 'sender', 'email_subject',
                        'raw_snippet', 'original_body'
                    ]
                    # 自动补齐没写在上面的列
                    final_cols = [c for c in cols if c in df_vessel.columns] + [c for c in df_vessel.columns if c not in cols]
                    df_vessel[final_cols].to_excel(writer, sheet_name='Tonnage_List', index=False)

                # Sheet 2: Cargo
                if not df_cargo.empty:
                    # 货盘也可以做日期转换，但不建议做合并去重（因为货盘太杂）
                    for col in ['laycan_from', 'laycan_to']:
                        if col in df_cargo.columns:
                            df_cargo[col] = pd.to_datetime(df_cargo[col], errors='coerce')

                    cols = [
                        'cargo_name', 'charterer', 'quantity_raw', 'quantity_num', 'load_port', 'discharge_port',  'discharge_region',
                        'laycan_from', 'laycan_to', 'laycan_raw','special_requirements',
                        'sent_time', 'sender', 'email_subject', 'raw_snippet', 'original_body'
                    ]
                    final_cols = [c for c in cols if c in df_cargo.columns] + [c for c in df_cargo.columns if c not in cols]
                    df_cargo[final_cols].to_excel(writer, sheet_name='Cargo_List', index=False)

                # Sheet 3: Market_Log (归档)
                if not df_raw.empty:
                    cols = ['sent_time', 'category', 'subject', 'sender', 'body']
                    final_cols = [c for c in cols if c in df_raw.columns]
                    df_raw[final_cols].to_excel(writer, sheet_name='Market_Log', index=False)

            print(f"🎉 Excel 导出成功: {filepath}")
            return filepath
        except Exception as e:
            # 如果 Excel 导出失败，尝试导出 CSV 作为保底
            print(f"❌ Excel 导出失败: {e}")
            try:
                csv_path = filepath.replace(".xlsx", ".csv")
                df_vessel.to_csv(csv_path, index=False)
                print(f"⚠️ 已紧急保存为 CSV: {csv_path}")
            except:
                pass
            return None
