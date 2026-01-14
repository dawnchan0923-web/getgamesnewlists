import feedparser
import datetime
import smtplib
import time
from email.mime.text import MIMEText
from email.header import Header

# --- 1. 游戏列表配置 ---
# 换成了更稳定的镜像地址 rsshub.moeyy.cn
BASE_URL = "https://rsshub.moeyy.cn" 

GAMES = [
    {"name": "王者荣耀", "rss_url": f"{BASE_URL}/tencent/pvp/news/index"},
    {"name": "和平精英", "rss_url": f"{BASE_URL}/tencent/gp/news/all"},
    {"name": "无畏契约", "rss_url": f"{BASE_URL}/tencent/val/news"},
    {"name": "穿越火线", "rss_url": f"{BASE_URL}/tencent/cf/news/all"},
    {"name": "第五人格", "rss_url": f"{BASE_URL}/netease/ds/id5"},
]

KEYWORDS = ["更新", "维护", "版本", "公告", "Season", "赛季"]
CHECK_RANGE_HOURS = 72  # 调试阶段建议先改成 72 小时（3天），确保能抓到东西

def get_game_updates():
    summary_list = []
    now = datetime.datetime.now(datetime.timezone.utc)

    for game in GAMES:
        print(f"正在检查: {game['name']}...")
        try:
            # 增加请求头模拟浏览器，防止被封
            feed = feedparser.parse(game['rss_url'])
            
            if not feed.entries:
                print(f"  ⚠️ 未能从 {game['name']} 抓取到任何内容，可能是接口维护或被拦截。")
                continue
                
            print(f"  ✅ 发现 {len(feed.entries)} 条原始公告，开始关键词过滤...")
            
            for entry in feed.entries:
                # 尝试获取发布时间
                pub_time = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    pub_time = datetime.datetime(*entry.published_parsed[:6], tzinfo=datetime.timezone.utc)
                
                # 如果没抓到时间，默认给个现在的时间让它通过过滤
                if not pub_time:
                    pub_time = now

                # 逻辑判断：时间范围 + 关键词
                hours_diff = (now - pub_time).total_seconds() / 3600
                if hours_diff < CHECK_RANGE_HOURS:
                    if any(kw.lower() in entry.title.lower() for kw in KEYWORDS):
                        summary_list.append(f"【{game['name']}】{entry.title}\n链接: {entry.link}")
        except Exception as e:
            print(f"  ❌ 抓取 {game['name']} 出错: {e}")
            
    return summary_list

def send_email(content_list, smtp_config):
    if not content_list:
        print("今日无符合条件的更新内容，跳过发送邮件。")
        return

    mail_content = "为您汇总以下游戏更新动态：\n\n" + "\n\n".join(content_list)
    msg = MIMEText(mail_content, 'plain', 'utf-8')
    msg['From'] = smtp_config['sender']
    msg['To'] = smtp_config['receiver']
    msg['Subject'] = Header(f"游戏更新汇总 - {datetime.date.today()}", 'utf-8')

    try:
        server = smtplib.SMTP_SSL(smtp_config['host'], 465)
        server.login(smtp_config['user'], smtp_config['password'])
        server.sendmail(smtp_config['sender'], [smtp_config['receiver']], msg.as_string())
        server.quit()
        print("🚀 邮件发送成功！")
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
