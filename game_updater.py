import feedparser
import datetime
import smtplib
import urllib.parse
from email.mime.text import MIMEText
from email.header import Header

# --- 1. 配置：需要监控的游戏列表 ---
GAMES = ["王者荣耀", "和平精英", "无畏契约", "穿越火线", "第五人格", "超自然行动"]
KEYWORDS = ["更新", "维护", "公告", "版本", "赛季"]
CHECK_RANGE_HOURS = 24 

def get_google_news_updates():
    results = []
    now = datetime.datetime.now(datetime.timezone.utc)
    for game in GAMES:
        print(f"🔍 正在检索: {game}...")
        keyword_query = ' OR '.join(['"{}"'.format(kw) for kw in KEYWORDS])
        query = '{} ({})'.format(game, keyword_query)
        encoded_query = urllib.parse.quote(query)
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
        try:
            feed = feedparser.parse(rss_url)
            for entry in feed.entries:
                if not hasattr(entry, 'published_parsed') or not entry.published_parsed: continue
                pub_time = datetime.datetime(*entry.published_parsed[:6], tzinfo=datetime.timezone.utc)
                if (now - pub_time).total_seconds() / 3600 < CHECK_RANGE_HOURS:
                    if game in entry.title:
                        source = entry.source.get('title', '未知')
                        results.append(f"【{game}】{entry.title}\n链接: {entry.link}")
        except Exception as e:
            print(f"   ❌ 检索失败: {e}")
    return list(set(results))

def send_email(content_list, smtp):
    if not content_list:
        print("\n📢 今日无更新。")
        return
    
    today = datetime.date.today()
    body = f"游戏更新汇总（{today}）：\n\n" + "\n\n".join(content_list)
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['From'] = smtp['user']
    msg['To'] = smtp['user']
    msg['Subject'] = Header(f"游戏更新汇总 - {today}", 'utf-8')

    print(f"📧 正在尝试通过网易邮箱 ({smtp['host']}) 发送...")
    
    try:
        # 网易邮箱强制要求使用 SSL 465 端口
        server = smtplib.SMTP_SSL(smtp['host'], 465, timeout=30)
        # server.set_debuglevel(1) # 如果还是不行，取消此行注释看详细报错
        server.login(smtp['user'], smtp['password'])
        server.sendmail(smtp['user'], [smtp['user']], msg.as_string())
        server.quit()
        print("\n🚀 网易邮箱发送成功！")
    except Exception as e:
        print(f"\n❌ 发送失败。错误原因: {e}")
        print("提示：请确认 MAIL_PASS 是16位授权码，且 host 匹配（163或126）。")

if __name__ == "__main__":
    import os
    # --- 关键修改区 ---
    # 如果你是 126 邮箱，请把 smtp.163.com 改为 smtp.126.com
    conf = {
        'host': 'smtp.163.com', 
        'user': os.environ.get('MAIL_USER'),     # 填你的完整网易邮箱地址
        'password': os.environ.get('MAIL_PASS')  # 填刚才获取的16位授权码
    }
    
    updates = get_google_news_updates()
    send_email(updates, conf)
