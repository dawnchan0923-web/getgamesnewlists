import feedparser
import datetime
import smtplib
import urllib.parse
from email.mime.text import MIMEText
from email.header import Header

# --- 1. 配置：需要监控的游戏列表 ---
GAMES = ["王者荣耀", "和平精英", "无畏契约", "穿越火线", "第五人格", "超自然行动"]

# 关键词组合
KEYWORDS = ["更新", "维护", "公告", "版本", "赛季"]
CHECK_RANGE_HOURS = 24  # 每天检查一次

def get_google_news_updates():
    results = []
    now = datetime.datetime.now(datetime.timezone.utc)
    
    for game in GAMES:
        print(f"🔍 正在通过 Google News 检索: {game}...")
        
        # 构造搜索关键词：游戏名 + (关键词1 OR 关键词2...)
        query = f'{game} ("{"\" OR \"".join(KEYWORDS)}")'
        encoded_query = urllib.parse.quote(query)
        
        # Google News RSS 接口 (全球最稳的数据源)
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
        
        try:
            feed = feedparser.parse(rss_url)
            print(f"   ✅ 检索到 {len(feed.entries)} 条相关快讯")
            
            count = 0
            for entry in feed.entries:
                # 解析发布时间
                pub_time = datetime.datetime(*entry.published_parsed[:6], tzinfo=datetime.timezone.utc)
                
                # 只取过去 24 小时内的，且标题里确实含有游戏名的
                if (now - pub_time).total_seconds() / 3600 < CHECK_RANGE_HOURS:
                    if game in entry.title:
                        results.append(f"【{game}】{entry.title}\n来源: {entry.source.get('title', '未知')}\n链接: {entry.link}")
                        count += 1
            print(f"   ✨ 筛选出 {count} 条最新公告")
        except Exception as e:
            print(f"   ❌ 检索失败: {e}")
            
    return list(set(results)) # 去重

def send_email(content_list, smtp):
    if not content_list:
        print("\n📢 结果：今日暂无最新的游戏更新公告。")
        return
    
    body = "您关注的游戏更新汇总（来源：Google News 聚合）：\n\n" + "\n\n".join(content_list)
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['From'] = smtp['user']
    msg['To'] = smtp['user']
    msg['Subject'] = Header(f"游戏更新汇总 - {datetime.date.today()}", 'utf-8')

    try:
        s = smtplib.SMTP_SSL(smtp['host'], 465)
        s.login(smtp['user'], smtp['password'])
        s.sendmail(smtp['user'], [smtp['user']], msg.as_string())
        s.quit()
        print("\n🚀 邮件已成功发送至您的邮箱！")
    except Exception as e:
        print(f"\n❌ 邮件发送失败: {e}")

if __name__ == "__main__":
    import os
    conf = {
        'host': 'smtp.qq.com',
        'user': os.environ.get('MAIL_USER'),
        'password': os.environ.get('MAIL_PASS')
    }
    
    updates = get_google_news_updates()
    send_email(updates, conf)
