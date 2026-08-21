# main_v2.py
import sys
import os
import time
from datetime import datetime, timedelta  # <--- 修改这里，加上 timedelta
import pandas as pd                       # <--- 新增这行，数据处理神器
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

# 加载环境变量 (防止有时候找不到配置)
from dotenv import load_dotenv
load_dotenv()

from core.email_fetcher import EmailFetcher
from core.classifier import EmailClassifier
from core.extractor import DataExtractor
from core.exporter import ExcelExporter
from database.schema import RawItem

# ==========================================
# 🧠 🆕 UID 记忆库：防止重复抓取，省下海量 Token
# ==========================================
UID_FILE = os.path.join(BASE_DIR, "processed_uids.txt")

def load_uids():
    """读取已经处理过的 UID 黑名单"""
    if not os.path.exists(UID_FILE):
        return set()
    try:
        with open(UID_FILE, 'r') as f:
            return set(line.strip() for line in f if line.strip())
    except Exception as e:
        print(f"⚠️ 读取 UID 记录失败: {e}")
        return set()

def save_uid(uid):
    """将新的 UID 安全追加到黑名单"""
    if not uid or str(uid).strip() == "": return
    try:
        with open(UID_FILE, 'a') as f:
            f.write(f"{str(uid).strip()}\n")
    except Exception as e:
        print(f"⚠️ 保存 UID 失败: {e}")


# ==========================================
# 辅助函数：更新主数据库 (船、货、归档 三轨安全更新)
# ==========================================
def update_master_excel(new_vessels, new_cargoes, new_archives):
    print("\n🔄 开始清洗并合并数据到 Master (看板数据库)...")

    master_path = os.path.join(BASE_DIR, "data", "master", "current_master.xlsx")
    os.makedirs(os.path.dirname(master_path), exist_ok=True)

    # 1. 完整读取旧表，作为基础底盘（防抹除护盾）
    existing_sheets = {}
    if os.path.exists(master_path):
        try:
            existing_sheets = pd.read_excel(master_path, sheet_name=None)
        except Exception:
            pass

    # 2. 🚢 处理船盘 (Tonnage)
    old_v_df = existing_sheets.get('Tonnage_List', pd.DataFrame())
    if new_vessels:
        new_v_df = pd.DataFrame([v.to_dict() for v in new_vessels])
        if 'dwt' in new_v_df.columns:
            new_v_df['dwt_num'] = pd.to_numeric(new_v_df['dwt'], errors='coerce').fillna(0)
            def assign_class(dwt):
                if pd.isna(dwt) or dwt == 0: return "Unknown"
                dwt = int(dwt)
                if dwt < 15000: return "Small"
                if 15000 <= dwt < 37000: return "Handysize"
                if 37000 <= dwt < 50000: return "Handymax"
                if 50000 <= dwt < 60000: return "Supramax"
                if 60000 <= dwt < 67000: return "Ultramax"
                if 67000 <= dwt < 85000: return "Panamax/Kamsarmax"
                if 85000 <= dwt < 110000: return "Post-Panamax"
                if dwt >= 110000: return "Capesize"
                return "Other"
            new_v_df['Vessel_Class'] = new_v_df['dwt_num'].apply(assign_class)
            new_v_df = new_v_df.drop(columns=['dwt_num'])

        comb_v_df = pd.concat([old_v_df, new_v_df], ignore_index=True)
        if not comb_v_df.empty and 'vessel_name' in comb_v_df.columns:
            comb_v_df.drop_duplicates(subset=['vessel_name', 'email_subject'], keep='last', inplace=True)
            if 'laycan_to' in comb_v_df.columns:
                comb_v_df['laycan_to_dt'] = pd.to_datetime(comb_v_df['laycan_to'], errors='coerce')
                today = pd.Timestamp(datetime.now().date())
                comb_v_df = comb_v_df[(comb_v_df['laycan_to_dt'] >= today) | (comb_v_df['laycan_to_dt'].isna())]
                comb_v_df = comb_v_df.drop(columns=['laycan_to_dt'])
                # Laycan 格式化 (恢复为标准 Date，供看板筛选)
                comb_v_df['laycan_to'] = pd.to_datetime(comb_v_df['laycan_to'], errors='coerce').dt.date
            if 'laycan_from' in comb_v_df.columns:
                comb_v_df['laycan_from'] = pd.to_datetime(comb_v_df['laycan_from'], errors='coerce').dt.date
        existing_sheets['Tonnage_List'] = comb_v_df

    # 3. 📦 处理货盘 (Cargo)
    old_c_df = existing_sheets.get('Cargo_List', pd.DataFrame())
    if new_cargoes:
        new_c_df = pd.DataFrame([c.to_dict() for c in new_cargoes])
        comb_c_df = pd.concat([old_c_df, new_c_df], ignore_index=True)
        if not comb_c_df.empty and 'cargo_name' in comb_c_df.columns:
            comb_c_df.drop_duplicates(subset=['cargo_name', 'load_port', 'email_subject'], keep='last', inplace=True)
            # Laycan 格式化
            if 'laycan_from' in comb_c_df.columns:
                comb_c_df['laycan_from'] = pd.to_datetime(comb_c_df['laycan_from'], errors='coerce').dt.date
            if 'laycan_to' in comb_c_df.columns:
                comb_c_df['laycan_to'] = pd.to_datetime(comb_c_df['laycan_to'], errors='coerce').dt.date
        existing_sheets['Cargo_List'] = comb_c_df

    # 4. 📈 处理归档 (Archive)
    old_a_df = existing_sheets.get('Archive_List', pd.DataFrame())
    if new_archives:
        new_a_df = pd.DataFrame([a.to_dict() for a in new_archives])
        comb_a_df = pd.concat([old_a_df, new_a_df], ignore_index=True)
        if not comb_a_df.empty and 'subject' in comb_a_df.columns:
            comb_a_df.drop_duplicates(subset=['subject', 'sent_time'], keep='last', inplace=True)
        existing_sheets['Archive_List'] = comb_a_df

    # 5. 安全写入 (确保不会丢失之前的任何 Sheet)
    if existing_sheets:
        with pd.ExcelWriter(master_path, engine='openpyxl') as writer:
            for sheet_name, df in existing_sheets.items():
                if not df.empty:
                    df.to_excel(writer, index=False, sheet_name=sheet_name)
        print(f"✅ Master 数据库 (船、货、Market) 全部安全覆盖更新完毕！")

# ==========================================
# 主运行逻辑
# ==========================================
def main():
    print("🚀 Shipping Agent V2 - 启动")
    print("=" * 60)

    # 1. 初始化
    fetcher = EmailFetcher()
    classifier = EmailClassifier()
    extractor = DataExtractor()
    exporter = ExcelExporter()

    # 2. 抓取
    # 建议设为 100 进行压力测试
    limit_num = 5
    print(f"\n📥 正在抓取邮件 (Limit: {limit_num})...")
    recent_emails = fetcher.fetch_emails(limit=limit_num)

    if not recent_emails:
        print("⚠️ 未抓取到邮件，请检查网络或配置。")
        return

    # 3. 准备容器
    all_vessels = []
    all_cargoes = []
    all_archives = [] # 归档容器
    failed_emails = [] # <--- 🆕 新增：错题本容器

    print(f"\n🧠 AI 正在分析 {len(recent_emails)} 封邮件内容...")

    # 🔥 🆕 1. 抓取大循环前，先翻开记忆小本本
    processed_uids = load_uids()
    skipped_count = 0

    for i, email_data in enumerate(recent_emails, 1):
        # 🔥 🆕 2. 拿到这封邮件的身份证号
        uid_str = str(email_data.get('uid', ''))

        # 🔥 🆕 3. 如果处理过，直接跳过！不消耗一滴 Token！
        if uid_str in processed_uids:
            skipped_count += 1
            print(f"\r[{i}/{len(recent_emails)}] ⏭️ 跳过已处理邮件: {email_data.get('subject', '')[:20]}...", end="", flush=True)
            continue

        subject = email_data.get('subject', 'No Subject')
        body = email_data.get('body', '')
        sender = email_data.get('sender', 'Unknown')
        sent_time = email_data.get('sent_time', '')

        # 生成当前的抓取时间
        fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 打印进度
        print(f"\r[{i}/{len(recent_emails)}] 处理: {subject[:30]}...", end="", flush=True)

        try:
            # Step 1: 分类
            cls_res = classifier.classify(subject, body, sender) # 注意：classify 现在接收 sender 参数
            email_type = cls_res # 现在的 classify 直接返回字符串 "TONNAGE" 等

            # 1.2. 补全后半截（打印分类结果）
            if email_type == "TONNAGE":
                print(f" -> [🚢 TONNAGE]") # 加个小图标，看起来更直观
            elif email_type == "CARGO":
                print(f" -> [📦 CARGO]")
            elif email_type == "MARKET":
                print(f" -> [📈 MARKET]")
            elif email_type == "FIXTURE":
                print(f" -> [🤝 FIXTURE]")
            else:
                print(f" -> [🗑️ OTHER]")

            # Step 2: 分流处理
            if email_type == "TONNAGE":
                items = extractor.extract_vessel(body)
                for v in items:
                    # 🔥 注入元数据 🔥
                    v.email_subject = subject
                    v.sender = sender
                    v.sent_time = sent_time
                    v.fetch_time = fetch_time
                    v.original_body = body
                all_vessels.extend(items)

            elif email_type == "CARGO":
                items = extractor.extract_cargo(body)
                for c in items:
                    # 🔥 注入元数据 🔥
                    c.email_subject = subject
                    c.sender = sender
                    c.sent_time = sent_time
                    c.fetch_time = fetch_time
                    c.original_body = body
                all_cargoes.extend(items)

            # Step 3: 归档 (FIXTURE / MARKET)
            elif email_type in ["FIXTURE", "MARKET"]:
                archive_item = RawItem(
                    category=email_type,
                    subject=subject,
                    body=body,
                    sender=sender,
                    sent_time=sent_time,
                    fetch_time=fetch_time
                )
                all_archives.append(archive_item)

        except Exception as e:
            # 打印错误但不中断，单个邮件报错不影响整体
            print(f"\n❌ [Error] 邮件 {i} 处理失败: {e}")

            # 🔥 🆕 核心防御：把失败的邮件扔进错题本
            failed_emails.append({
                "uid": email_data.get('uid', 'Unknown'),
                "subject": subject,
                "sender": sender,
                "sent_time": sent_time,
                "error_reason": str(e),
                "body_preview": body[:300] # 存前 300 个字以便人工排查
            })
            continue

    print(f"\n\n✅ 全部处理完成！(跳过了 {skipped_count} 封已存盘的旧邮件)")
    print(f"   - 船源提取: {len(all_vessels)} 条")
    print(f"   - 货盘提取: {len(all_cargoes)} 条")
    print(f"   - 归档记录: {len(all_archives)} 条")
    print(f"   - 失败记录: {len(failed_emails)} 条") # <--- 新增打印

    # 4. 导出每日流水账快照 (原逻辑保留)
    exporter.export(all_vessels, all_cargoes, all_archives)

    # 5. 🔥 更新看板核心数据库 🔥
    update_master_excel(all_vessels, all_cargoes, all_archives)

    # 6. 🚑 🆕 错题本存档逻辑
    if failed_emails:
        print(f"\n⚠️ 警告：有 {len(failed_emails)} 封邮件处理失败，正在生成错题本...")
        error_df = pd.DataFrame(failed_emails)

        # 确保输出目录存在
        output_dir = os.path.join(BASE_DIR, "data", "output")
        os.makedirs(output_dir, exist_ok=True)

        # 命名格式：failed_emails_20260228_2315.xlsx
        error_file_path = os.path.join(output_dir, f"failed_emails_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
        error_df.to_excel(error_file_path, index=False)
        print(f"📁 错题本已保存至: {error_file_path}")

    # ==========================================
    # 🔥 核心业务逻辑：清洗与淘汰 🔥
    # ==========================================
if __name__ == "__main__":
    main()