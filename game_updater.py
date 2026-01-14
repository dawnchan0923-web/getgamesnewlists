import feedparser
import datetime
import smtplib
import time
import requests
from email.mime.text import MIMEText
from email.header import Header

# --- 1. 游戏列表配置 (改用 TapTap 官方公告源，更稳定) ---
# 这里的 ID 是各游戏在 TapTap 的官方编号
GAMES = [
    {"name": "王者荣耀", "id": "18103"},
    {"name": "和平精英", "id": "70056"},
    {"name": "无畏契约", "id": "213506"},
    {"name": "穿越火线", "id": "11046"},
    {"name": "第五人格", "id": "35915"},
    {"name": "超自然行动", "id": "380482"}, # 新增你提到的超自然行动
]

# 备选镜像站列表，提高稳定性
MIRRORS = [
    "https://rsshub.rss.how",
    "https://rsshub.moeyy.cn",
    "https://hub.anyway.run"
]

KEYWORDS = ["更新", "维护", "版本", "公告", "Season", "赛季", "停服"]
CHECK_RANGE_HOURS = 72 # 强制检查3天内，确保有内容

def fetch_rss(game_name, game_id):
    for mirror in MIRRORS:
        url = f"{mirror}/taptap/topic/{game_id}/official"
        print(f"  正在尝试镜像 {mirror} ...")
        try:
            # 增加 User-Agent 伪装
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                feed = feedparser.parse(response.text)
                if feed.entries:
                    return feed.entries
            print(f"  ⚠️ 镜像 {mirror} 返回数据为空或报错")
        except Exception as e:
            print(f"  ❌ 镜像 {mirror} 访问失败: {e}")
    return []

def get_game_updates():
    summary_list = []
    now = datetime.datetime.now(datetime.timezone.utc)

    for game in GAMES:
        print(f"正在检查: {game['name']}...")
        entries = fetch_rss(game['name'], game['id'])
        
        if not entries:
            print(f"  🚫 {game['name']} 所有镜像均失效。")
            continue
            
        print(f"  ✅ 成功获取 {len(entries)} 条公告，正在匹配关键词...")
        for entry in entries:
            pub_time = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                pub_time = datetime.datetime(*entry.published_parsed[:6], tzinfo=datetime.timezone.utc)
            
            if not pub_time: pub_time = now

            if (now - pub_time).total_seconds() / 3600 < CHECK_RANGE_HOURS:
                if any(kw.lower() in entry.title.lower() for kw in KEYWORDS):
                    summary_list.append(f"【{game['name']}】{entry.title}\n链接: {entry.link}")
            
    return summary_list

def send_email(content_list, smtp_config):
    if not content_list:
        print("今日无符合条件的更新公告。")
        return

    mail_content = "为您汇总以下游戏更新动态（测试模式）：\n\n" + "\n\n".join(content_list)
    msg = MIMEText(mail_content, 'plain', 'utf-8')
    msg['From'] = smtp_config['sender']
    msg['To'] = smtp_config['receiver']
    msg['Subject'] = Header(f"游戏更新汇总 - {datetime.date.today()}", 'utf-8')

    try:
        server = smtplib.SMTP_SSL(smtp_config['host'], 465)
        server.login(smtp_config['user'], smtp_config['password'])
        server.sendmail(smtp_config['sender'], [smtp_config['receiver']], msg.as_string())
        server.quit()
        print("🚀 邮件发送成功！请检查收件箱或垃圾箱。")
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")

if __name__ == "__main__":
    import os
    SMTP_CONFIG = {
        'host': 'smtp.qq.com',
        'user': os.environ.get('MAIL_USER'),
        'password': os.environ.get('MAIL_PASS'),
        'sender': os.environ.get('MAIL_USER'),
        'receiver': os.environ.get('MAIL_USER')
    }
    updates = get_game_updates()
    send_email(updates, SMTP_CONFIG)
