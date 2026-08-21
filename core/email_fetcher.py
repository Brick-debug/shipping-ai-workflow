# core/email_fetcher.py
import sys
import os
import socket  # <--- 🛡️ 导入网络底层库
socket.setdefaulttimeout(180)  # <--- 🛡️ 强行把超时断开时间从 60 秒延长到 3 分钟！

# --- 寻根逻辑 ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
# ----------------

import imaplib
import email
from email.header import decode_header
import logging
import re
from datetime import datetime

# 🔥 导入配置
try:
    from config.settings import IMAP_SERVER, EMAIL_ACCOUNT, EMAIL_PASSWORD
except ImportError:
    IMAP_SERVER = os.getenv("IMAP_SERVER")
    EMAIL_ACCOUNT = os.getenv("EMAIL_ACCOUNT") or os.getenv("EMAIL_USER")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD") or os.getenv("EMAIL_PASS")

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EmailFetcher:
    def __init__(self):
        self.imap_server = IMAP_SERVER
        self.email_user = EMAIL_ACCOUNT
        self.email_pass = EMAIL_PASSWORD
        self.save_dir = "data/raw_emails"

        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)

    def close(self):
        if hasattr(self, 'mail') and self.mail:
            try:
                self.mail.close()
                self.mail.logout()
            except:
                pass
            self.mail = None

    def _decode_str(self, text):
        if not text: return ""
        try:
            decoded_list = decode_header(text)
            default_charset = 'utf-8'
            decoded_text = ""
            for content, charset in decoded_list:
                if isinstance(content, bytes):
                    try:
                        decoded_text += content.decode(charset or default_charset)
                    except:
                        for enc in ['gb18030', 'gbk', 'latin1']:
                            try:
                                decoded_text += content.decode(enc)
                                break
                            except:
                                continue
                else:
                    decoded_text += str(content)
            return decoded_text.strip()
        except Exception as e:
            return str(text)

    # 👇 递归式正文提取
    def _extract_text_recursive(self, msg):
        text_content = ""
        html_content = ""

        if msg.is_multipart():
            for part in msg.walk():
                if part.get('Content-Disposition') and 'attachment' in part.get('Content-Disposition'):
                    continue
                if part.get_content_maintype() == 'multipart':
                    continue

                content_type = part.get_content_type()
                try:
                    payload = part.get_payload(decode=True)
                    if not payload: continue
                    charset = part.get_content_charset() or 'utf-8'
                    decoded = payload.decode(charset, errors='replace')

                    if content_type == "text/plain":
                        text_content += decoded + "\n"
                    elif content_type == "text/html":
                        html_content += decoded + "\n"
                except:
                    pass
        else:
            try:
                payload = msg.get_payload(decode=True)
                charset = msg.get_content_charset() or 'utf-8'
                decoded = payload.decode(charset, errors='replace')
                if msg.get_content_type() == "text/plain":
                    text_content = decoded
                elif msg.get_content_type() == "text/html":
                    html_content = decoded
            except:
                pass

        if text_content.strip():
            return text_content.strip()
        elif html_content.strip():
            text = re.sub('<[^<]+?>', ' ', html_content)
            text = re.sub(r'\s+', ' ', text).strip()
            return text
        else:
            return ""

    # =========================================================
    # 🔥 核心抓取逻辑 (彻底变成无状态实时抢夺) 🔥
    # =========================================================
    def fetch_emails(self, limit=60): # 默认每次抢最后 60 封
        if not self.imap_server or not self.email_user:
            logger.error("❌ 配置缺失: 请检查 .env 文件")
            return []

        self.mail = imaplib.IMAP4_SSL(self.imap_server)
        try:
            logger.info(f"正在连接邮箱 {self.email_user}...")
            self.mail.login(self.email_user, self.email_pass)
            self.mail.select("inbox")

            logger.info("⚡ 实时快照模式: 直接盘点服务器当前存活的所有邮件...")
            typ, data = self.mail.uid('search', None, "ALL")

            messages_to_fetch = []
            if data[0]:
                all_uids_in_inbox = data[0].split()
                total_found = len(all_uids_in_inbox)
                logger.info(f"🚨 【抢夺雷达】服务器当前存活: {total_found} 封邮件！")

                # 如果邮件太多，只抢最新的 limit 封
                if limit and limit < total_found:
                    messages_to_fetch = all_uids_in_inbox[-limit:]
                    logger.info(f"✂️ 截取最新的 {limit} 封准备抓取。")
                else:
                    messages_to_fetch = all_uids_in_inbox
            else:
                logger.info("✅ 服务器的 INBOX 已经被同事抽干了！(一封都没有)")
                return []

            email_data_list = []

            # 遍历抢到的 UID 列表
            for uid in messages_to_fetch:
                uid_str = uid.decode('utf-8') if isinstance(uid, bytes) else str(uid)
                if not uid_str.isdigit(): continue

                try:
                    typ, msg_data = self.mail.uid('fetch', uid_str, "(RFC822)")
                    for response_part in msg_data:
                        if isinstance(response_part, tuple):
                            msg = email.message_from_bytes(response_part[1])

                            subject = self._decode_str(msg["Subject"])
                            sender = self._decode_str(msg["From"])
                            sent_time = msg["Date"]
                            body = self._extract_text_recursive(msg)

                            email_data_list.append({
                                "subject": subject,
                                "sender": sender,
                                "body": body,
                                "sent_time": sent_time,
                                "uid": int(uid_str)
                            })
                            print(f"📥 抓取: {subject[:30]}... (长度: {len(body)})")

                except Exception as e:
                    logger.error(f"处理邮件 UID {uid} 失败: {e}")
                    continue

            # 🚨 已经删除了保存 TXT 文件的代码，抓完就走！
            self.close()
            return email_data_list

        except Exception as e:
            logger.error(f"邮箱连接失败: {e}")
            self.close()
            return []