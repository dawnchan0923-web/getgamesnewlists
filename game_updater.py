import feedparser
import datetime
import smtplib
from email.mime.text import MIMEText
from email.header import Header

# --- 1. 游戏列表配置 (基于 RSSHub) ---
# 路由说明：https://docs.rsshub.app/routes/game
GAMES = [
    {"name": "王者荣耀", "rss_url": "https://rsshub.app/tencent/pvp/news/index"},
    {"name": "和平精英", "rss_url": "https://rsshub.app/tencent/gp/news/all"},
    {"name": "无畏契约", "rss_url": "https://rsshub.app/tencent/val/news"},
    {"name": "穿越火线", "rss_url": "https://rsshub.app/tencent/cf/news/all"},
    {"name": "第五人格", "rss_url": "https://rsshub.app/netease/ds/id5"}, # 网易大神源
    # 如需增加游戏，只需按此格式添加 RSS 地址即可
]

# --- 2. 过滤配置 ---
KEYWORDS = ["更新", "维护", "版本", "公告", "Season", "赛季"]
CHECK_RANGE_HOURS = 240  # 只获取过去24小时内的公告

def get_game_updates():
    summary_list = []
    now = datetime.datetime.now(datetime.timezone.utc)

    for game in GAMES:
        print(f"正在检查: {game['name']}...")
        try:
            feed = feedparser.parse(game['rss_url'])
            for entry in feed.entries:
                # 获取发布时间
                pub_time = datetime.datetime(*entry.published_parsed[:6], tzinfo=datetime.timezone.utc)
                
                # 逻辑判断：时间在24小时内 + 关键词匹配
                if (now - pub_time).total_seconds() < CHECK_RANGE_HOURS * 3600:
                    if any(kw.lower() in entry.title.lower() for kw in KEYWORDS):
                        summary_list.append(f"【{game['name']}】{entry.title}\n链接: {entry.link}")
        except Exception as e:
            print(f"抓取 {game['name']} 出错: {e}")
            
    return summary_list

def send_email(content_list, smtp_config):
    if not content_list:
        print("今日无更新内容。")
        return

    mail_content = "\n\n".join(content_list)
    msg = MIMEText(mail_content, 'plain', 'utf-8')
    msg['From'] = smtp_config['sender']
    msg['To'] = smtp_config['receiver']
    msg['Subject'] = Header(f"游戏更新汇总 - {datetime.date.today()}", 'utf-8')

    try:
        server = smtplib.SMTP_SSL(smtp_config['host'], 465)
        server.login(smtp_config['user'], smtp_config['password'])
        server.sendmail(smtp_config['sender'], [smtp_config['receiver']], msg.as_string())
        server.quit()
        print("邮件发送成功！")
    except Exception as e:
        print(f"邮件发送失败: {e}")

# --- 3. 执行入口 ---
if __name__ == "__main__":
    import os
    
    # 从 GitHub Secrets 中读取敏感信息
    SMTP_CONFIG = {
        'host': 'smtp.qq.com', # 如果用 Gmail 请改为 smtp.gmail.com
        'user': os.environ.get('MAIL_USER'),     # 你的邮箱地址
        'password': os.environ.get('MAIL_PASS'), # 邮箱授权码
        'sender': os.environ.get('MAIL_USER'),
        'receiver': os.environ.get('MAIL_USER')  # 发给自己
    }
    
    updates = get_game_updates()
    send_email(updates, SMTP_CONFIG)
