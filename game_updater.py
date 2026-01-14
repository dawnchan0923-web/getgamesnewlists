import feedparser
import datetime
import smtplib
import urllib.parse
import requests
import re
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
        # 2. 标题去重（取前15个字符判断相似度）
        title_summary = item['title'][:15]
        if title_summary in seen_titles:
            continue
        seen_titles.add(title_summary)
        unique_items.append(item)
    return unique_items

def fetch_from_google(game_name):
    """从 Google News 获取数据"""
    results = []
    # 增加官方站点权重
    query = f'{game_name} ("{"\" OR \"".join(KEYWORDS)}")'
    encoded_query = urllib.parse.quote(query)
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
    
    try:
        feed = feedparser.parse(rss_url)
        for entry in feed.entries:
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
    except: pass
    return results

def fetch_from_taptap(game_name, app_id):
    """从 TapTap 官方社区获取数据（作为补充）"""
    results = []
    if not app_id: return results
    url = f"https://www.taptap.cn/web-api/tds-forum/v1/categories/official/topics?app_id={app_id}&limit=5"
    try:
        resp = requests.get(url, timeout=10).json()
        items = resp.get('data', {}).get('list', [])
        for item in items:
            title = item.get('topic', {}).get('title', '')
            if any(kw in title for kw in KEYWORDS):
                topic_id = item.get('topic', {}).get('id')
                results.append({
                    "title": title,
                    "link": f"https://www.taptap.cn/moment/{topic_id}",
                    "source": "TapTap官方社区",
                    "time": datetime.datetime.now(datetime.timezone.utc), # 接口时间解析较复杂，暂用当前
                    "is_official": True
                })
    except: pass
    return results

# --- 3. 邮件模板生成 ---

def generate_html(all_data):
    today = datetime.date.today()
    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f7f9; color: #333; }}
            .container {{ max-width: 650px; margin: 20px auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }}
            .header {{ background: linear-gradient(135deg, #1a73e8, #0d47a1); color: white; padding: 30px 20px; text-align: center; }}
            .game-section {{ padding: 20px; border-bottom: 8px solid #f4f7f9; }}
            .game-title {{ font-size: 20px; font-weight: bold; color: #1a73e8; border-left: 5px solid #1a73e8; padding-left: 10px; margin-bottom: 15px; }}
            .news-item {{ padding: 12px; margin-bottom: 10px; border-radius: 8px; transition: background 0.3s; background: #fff; border: 1px solid #eee; }}
            .news-title {{ text-decoration: none; color: #202124; font-weight: 500; font-size: 15px; display: block; }}
            .news-title:hover {{ color: #1a73e8; }}
            .badge-official {{ background: #e6f4ea; color: #1e8e3e; font-size: 11px; padding: 2px 6px; border-radius: 4px; font-weight: bold; margin-right: 5px; }}
            .meta {{ font-size: 12px; color: #70757a; margin-top: 8px; }}
            .empty {{ color: #999; font-style: italic; font-size: 14px; padding: 10px; }}
            .footer {{ background: #f8f9fa; padding: 20px; text-align: center; font-size: 12px; color: #70757a; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1 style="margin:0;">🎮 游戏更新情报精选</h1>
                <p style="margin:10px 0 0; opacity: 0.8;">北京时间：{get_beijing_time().strftime('%Y-%m-%d %H:%M')}</p>
            </div>
    """
    
    for game, news in all_data.items():
        html += f'<div class="game-section"><div class="game-title">{game}</div>'
        if not news:
            html += '<div class="empty">今日暂无重要更新公告</div>'
        else:
            for item in news:
                official_badge = '<span class="badge-official">官方权威</span>' if item['is_official'] else ''
                rel_time = format_relative_time(item['time'])
                html += f"""
                <div class="news-item">
                    {official_badge}<a class="news-title" href="{item['link']}">{item['title']}</a>
                    <div class="meta">{item['source']} • {rel_time}</div>
                </div>
                """
        html += '</div>'

    html += """
            <div class="footer">
                自动化情报系统已开启过滤机制：已剔除攻略、八卦及重复信息<br>
                由 GitHub Actions 驱动 • 数据源自 Google & TapTap
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
        # 1. 从 Google News 获取
        raw_news = fetch_from_google(game_name)
        
        # 2. 针对特定游戏或作为补充从 TapTap 获取
        if len(raw_news) < 2: # 如果 Google 搜到的少，去 TapTap 补货
            raw_news.extend(fetch_from_taptap(game_name, app_id))
            
        # 3. 清洗与去重
        filtered_news = clean_and_filter(raw_news)
        
        # 4. 排序：官方源排在前面
        filtered_news.sort(key=lambda x: x['is_official'], reverse=True)
        
        all_game_data[game_name] = filtered_news

    # 发送邮件
    html_content = generate_html(all_game_data)
    msg = MIMEText(html_content, 'html', 'utf-8')
    msg['From'] = conf['user']
    msg['To'] = conf['user']
    msg['Subject'] = Header(f"🎮 游戏更新情报日报 - {datetime.date.today()}", 'utf-8')

    try:
        server = smtplib.SMTP_SSL(conf['host'], 465, timeout=30)
        server.login(conf['user'], conf['password'])
        server.sendmail(conf['user'], [conf['user']], msg.as_string())
        server.quit()
        print("🚀 成功发送分类精选报告！")
    except Exception as e:
        print(f"❌ 发送失败: {e}")
