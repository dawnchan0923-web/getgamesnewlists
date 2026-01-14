import feedparser
import datetime
import smtplib
import urllib.parse
import requests
import re
import json
from email.mime.text import MIMEText
from email.header import Header

# --- 1. 核心配置 ---
# 格式：{ "游戏名": "TapTap_ID" (如果没有则填 None) }
GAMES_CONFIG = {
    "王者荣耀": "18103",
    "和平精英": "70056",
    "无畏契约": "213506",
    "穿越火线": "11046",
    "第五人格": "35915",
    "超自然行动": "380482"
}

KEYWORDS = ["更新", "维护", "公告", "版本", "赛季", "停服"]
BLACKLIST = ["爆料", "八卦", "盘点", "攻略", "玩家吐槽", "传闻", "泄露", "教学", "壁纸"]
OFFICIAL_DOMAINS = ["qq.com", "taptap.cn", "163.com", "bilibili.com", "weibo.com"]

CHECK_RANGE_HOURS = 24

# --- 2. 核心功能函数 ---

def get_beijing_time():
    """获取北京时间"""
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))

def format_relative_time(pub_time):
    """计算相对时间字符串"""
    now = get_beijing_time()
    # 统一时区进行计算
    delta = now - pub_time.astimezone(datetime.timezone(datetime.timedelta(hours=8)))
    hours = int(delta.total_seconds() / 3600)
    if hours < 1:
        return "刚刚"
    return f"{hours}小时前"

def is_official(url):
    """通过域名判断是否为官方源"""
    return any(domain in url.lower() for domain in OFFICIAL_DOMAINS)

def clean_and_filter(items):
    """去重及黑名单过滤"""
    seen_titles = set()
    unique_items = []
    for item in items:
        # 1. 黑名单过滤
        if any(word in item['title'] for word in BLACKLIST):
            continue
        # 2. 标题相似度去重（取前15个字符）
        title_summary = item['title'][:15]
        if title_summary in seen_titles:
            continue
        seen_titles.add(title_summary)
        unique_items.append(item)
    return unique_items

def fetch_from_google(game_name):
    """从 Google News 获取数据"""
    results = []
    # 修正 f-string 语法：先在外部处理好关键字查询字符串
    keyword_query = ' OR '.join(['"{}"'.format(kw) for kw in KEYWORDS])
    query = '{} ({})'.format(game_name, keyword_query)
    
    encoded_query = urllib.parse.quote(query)
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
    
    try:
        feed = feedparser.parse(rss_url)
        for entry in feed.entries:
            if not hasattr(entry, 'published_parsed') or not entry.published_parsed:
                continue
            pub_time = datetime.datetime(*entry.published_parsed[:6], tzinfo=datetime.timezone.utc)
            if (datetime.datetime.now(datetime.timezone.utc) - pub_time).total_seconds() / 3600 < CHECK_RANGE_HOURS:
                if game_name in entry.title:
                    results.append({
                        "title": entry.title,
                        "link": entry.link,
                        "source": entry.source.get('title', '全网聚合'),
                        "time": pub_time,
                        "is_official": is_official(entry.link)
                    })
    except Exception as e:
        print(f"   ⚠️ Google News 抓取失败 ({game_name}): {e}")
    return results

def fetch_from_taptap(game_name, app_id):
    """从 TapTap 官方社区获取数据（作为补充）"""
    results = []
    if not app_id: return results
    # TapTap 官方公告 API
    url = f"https://www.taptap.cn/web-api/tds-forum/v1/categories/official/topics?app_id={app_id}&limit=5"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers, timeout=10).json()
        items = resp.get('data', {}).get('list', [])
        for item in items:
            topic_data = item.get('topic', {})
            title = topic_data.get('title', '')
            if any(kw in title for kw in KEYWORDS):
                topic_id = topic_data.get('id')
                results.append({
                    "title": title,
                    "link": f"https://www.taptap.cn/moment/{topic_id}",
                    "source": "TapTap官方社区",
                    "time": datetime.datetime.now(datetime.timezone.utc), 
                    "is_official": True
                })
    except Exception as e:
        print(f"   ⚠️ TapTap 抓取失败 ({game_name}): {e}")
    return results

# --- 3. 邮件模板生成 ---

def generate_html(all_data):
    today = datetime.date.today()
    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background-color: #f0f2f5; margin: 0; padding: 20px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); overflow: hidden; }}
            .header {{ background: #1a73e8; color: white; padding: 25px; text-align: center; }}
            .game-section {{ padding: 20px; border-bottom: 1px solid #eee; }}
            .game-title {{ font-size: 18px; font-weight: bold; color: #1a73e8; margin-bottom: 15px; padding-left: 10px; border-left: 4px solid #1a73e8; }}
            .news-item {{ display: block; padding: 12px; margin-bottom: 8px; background: #fafafa; border-radius: 6px; text-decoration: none; border: 1px solid #f0f0f0; }}
            .news-title {{ color: #202124; font-size: 14px; font-weight: 500; display: block; margin-bottom: 5px; }}
            .badge-official {{ display: inline-block; background: #e6f4ea; color: #1e8e3e; font-size: 10px; padding: 1px 5px; border-radius: 3px; font-weight: bold; margin-right: 6px; }}
            .meta {{ font-size: 11px; color: #70757a; }}
            .empty {{ font-size: 13px; color: #999; padding: 10px; }}
            .footer {{ padding: 20px; font-size: 11px; color: #999; text-align: center; line-height: 1.5; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2 style="margin:0;">🎮 游戏情报分类简报</h2>
                <div style="font-size:12px; margin-top:5px; opacity:0.9;">生成时间: {get_beijing_time().strftime('%Y-%m-%d %H:%M')}</div>
            </div>
    """
    
    for game, news in all_data.items():
        html += f'<div class="game-section"><div class="game-title">{game}</div>'
        if not news:
            html += '<div class="empty">今日暂无匹配的更新公告</div>'
        else:
            for item in news:
                official_badge = '<span class="badge-official">官方</span>' if item['is_official'] else ''
                rel_time = format_relative_time(item['time'])
                html += f"""
                <a class="news-item" href="{item['link']}">
                    <span class="news-title">{official_badge}{item['title']}</span>
                    <span class="meta">{item['source']} • {rel_time}</span>
                </a>
                """
        html += '</div>'

    html += """
            <div class="footer">
                系统已自动排除八卦、爆料及重复信息<br>
                Powered by GitHub Actions • 数据源：Google News & TapTap
            </div>
        </div>
    </body>
    </html>
    """
    return html

# --- 4. 主逻辑 ---

if __name__ == "__main__":
    import os
    conf = {
        'host': 'smtp.163.com',
        'user': os.environ.get('MAIL_USER'),
        'password': os.environ.get('MAIL_PASS')
    }

    all_game_data = {}

    for game_name, app_id in GAMES_CONFIG.items():
        # 1. 获取 Google 数据
        raw_news = fetch_from_google(game_name)
        
        # 2. 如果结果较少，使用 TapTap 补货
        if len(raw_news) < 2:
            raw_news.extend(fetch_from_taptap(game_name, app_id))
            
        # 3. 过滤与清洗
        filtered_news = clean_and_filter(raw_news)
        
        # 4. 排序：官方置顶
        filtered_news.sort(key=lambda x: x['is_official'], reverse=True)
        
        all_game_data[game_name] = filtered_news

    # 5. 生成 HTML 并发送
    html_content = generate_html(all_game_data)
    msg = MIMEText(html_content, 'html', 'utf-8')
    msg['From'] = conf['user']
    msg['To'] = conf['user']
    msg['Subject'] = Header(f"🎮 游戏更新分类情报 - {datetime.date.today()}", 'utf-8')

    try:
        server = smtplib.SMTP_SSL(conf['host'], 465, timeout=30)
        server.login(conf['user'], conf['password'])
        server.sendmail(conf['user'], [conf['user']], msg.as_string())
        server.quit()
        print("🚀 分类情报日报发送成功！")
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")
