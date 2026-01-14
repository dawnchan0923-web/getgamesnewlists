import feedparser
import datetime
import smtplib
import urllib.parse
from email.mime.text import MIMEText
from email.header import Header

# --- 1. 配置 ---
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
                if not hasattr(entry, 'published_parsed') or not entry.published_parsed:
                    continue
                pub_time = datetime.datetime(*entry.published_parsed[:6], tzinfo=datetime.timezone.utc)
                
                if (now - pub_time).total_seconds() / 3600 < CHECK_RANGE_HOURS:
                    if game in entry.title:
                        # 存储为字典，方便后续生成 HTML
                        results.append({
                            "game": game,
                            "title": entry.title,
                            "link": entry.link,
                            "source": entry.source.get('title', '未知来源'),
                            "time": pub_time.strftime('%Y-%m-%d %H:%M')
                        })
        except Exception as e:
            print(f"   ❌ 检索失败: {e}")
            
    return results

def send_email(news_items, smtp):
    if not news_items:
        print("\n📢 今日无更新。")
        return
    
    today = datetime.date.today()
    
    # --- 2. 构造 HTML 内容 ---
    html_body = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Microsoft YaHei', sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eee; border-radius: 10px; }}
            .header {{ background-color: #f8f9fa; padding: 10px 20px; border-bottom: 3px solid #007bff; border-radius: 10px 10px 0 0; }}
            .game-tag {{ background: #007bff; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px; margin-right: 10px; }}
            .item {{ margin-bottom: 20px; padding: 15px; border-bottom: 1px solid #f0f0f0; }}
            .title {{ font-size: 16px; font-weight: bold; color: #0056b3; text-decoration: none; }}
            .footer {{ font-size: 12px; color: #999; margin-top: 20px; text-align: center; }}
            .meta {{ font-size: 12px; color: #666; margin-top: 5px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>🎮 游戏更新情报汇总</h2>
                <p style="color: #666;">日期：{today}</p>
            </div>
    """

    for item in news_items:
        html_body += f"""
            <div class="item">
                <span class="game-tag">{item['game']}</span>
                <a class="title" href="{item['link']}" target="_blank">{item['title']}</a>
                <div class="meta">来源：{item['source']} | 时间：{item['time']}</div>
            </div>
        """

    html_body += """
            <div class="footer">
                此邮件由 GitHub Actions 自动化工作流发送<br>
                数据聚合自 Google News RSS
            </div>
        </div>
    </body>
    </html>
    """

    # --- 3. 发送设置 ---
    # 注意这里将 'plain' 改成了 'html'
    msg = MIMEText(html_body, 'html', 'utf-8')
    msg['From'] = smtp['user']
    msg['To'] = smtp['user']
    msg['Subject'] = Header(f"🎮 游戏更新情报汇总 - {today}", 'utf-8')

    try:
        server = smtplib.SMTP_SSL(smtp['host'], 465, timeout=30)
        server.login(smtp['user'], smtp['password'])
        server.sendmail(smtp['user'], [smtp['user']], msg.as_string())
        server.quit()
        print("\n🚀 HTML 格式邮件已成功发送！")
    except Exception as e:
        print(f"\n❌ 发送失败: {e}")

if __name__ == "__main__":
    import os
    conf = {
        'host': 'smtp.163.com',
        'user': os.environ.get('MAIL_USER'),
        'password': os.environ.get('MAIL_PASS')
    }
    
    news_data = get_google_news_updates()
    send_email(news_data, conf)
