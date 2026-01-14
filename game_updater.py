import feedparser
import datetime
import smtplib
import urllib.parse
import re
from email.mime.text import MIMEText
from email.header import Header

# --- 1. 配置：游戏与官方域名定义 ---
# 我们通过强制 site 搜索来确保信息的纯净度
GAMES = ["王者荣耀", "和平精英", "无畏契约", "穿越火线", "第五人格", "超自然行动"]

# 官方域名白名单（用于强制搜索和权威标记）
OFFICIAL_SITES = ["qq.com", "163.com", "taptap.cn", "bilibili.com", "weibo.com", "val.qq.com", "pvp.qq.com"]

KEYWORDS = ["更新", "维护", "公告", "版本", "赛季", "停服"]
BLACKLIST = ["爆料", "八卦", "盘点", "攻略", "玩家吐槽", "传闻", "教学", "壁纸", "测评"]

# 匹配版本号的正则：如 v1.2, 2.0版本, 第35赛季, S35
VERSION_PATTERN = r'[vV]?\d+\.\d+\.?\d*|[第]?\s*\d+\s*[版本|赛季|Season|阶段]'

CHECK_RANGE_HOURS = 24

# --- 2. 逻辑函数 ---

def get_beijing_time():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))

def extract_version(title):
    """提取版本号标记"""
    match = re.search(VERSION_PATTERN, title)
    return f"[{match.group().strip()}] " if match else ""

def is_official(url):
    """通过域名判断是否为官方源"""
    return any(domain in url.lower() for domain in OFFICIAL_SITES)

def fetch_game_news(game_name):
    """
    双重搜索逻辑：
    1. 强制搜索官方域名下的该游戏公告
    2. 搜索全网公告作为补充
    """
    results = []
    
    # 构造高级搜索指令
    # 逻辑：游戏名 + 关键词 + (site:官方域名1 OR site:官方域名2...)
    kw_query = ' OR '.join(['"{}"'.format(kw) for kw in KEYWORDS])
    site_query = ' OR '.join(['site:{}'.format(site) for site in OFFICIAL_SITES])
    
    # 混合搜索：优先搜官方，同时也搜全网
    query = f'{game_name} ({kw_query}) ({site_query} OR "官方")'
    encoded_query = urllib.parse.quote(query)
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
    
    try:
        feed = feedparser.parse(rss_url)
        now = datetime.datetime.now(datetime.timezone.utc)
        
        for entry in feed.entries:
            if not hasattr(entry, 'published_parsed') or not entry.published_parsed:
                continue
            
            pub_time = datetime.datetime(*entry.published_parsed[:6], tzinfo=datetime.timezone.utc)
            
            # 时间过滤
            if (now - pub_time).total_seconds() / 3600 < CHECK_RANGE_HOURS:
                title = entry.title
                # 排除黑名单
                if any(word in title for word in BLACKLIST):
                    continue
                # 确保标题包含游戏名
                if game_name in title:
                    url = entry.link
                    results.append({
                        "game": game_name,
                        "title": title,
                        "link": url,
                        "source": entry.source.get('title', '全网'),
                        "time": pub_time,
                        "official": is_official(url),
                        "version_tag": extract_version(title)
                    })
    except Exception as e:
        print(f"   ⚠️ {game_name} 抓取异常: {e}")
    
    # 简单去重
    unique_news = []
    seen = set()
    for n in results:
        if n['title'][:15] not in seen:
            unique_news.append(n)
            seen.add(n['title'][:15])
    
    # 排序：官方置顶
    unique_news.sort(key=lambda x: x['official'], reverse=True)
    return unique_news

# --- 3. HTML 模板 ---

def generate_html(all_data):
    today = datetime.date.today()
    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background-color: #f6f8fa; margin: 0; padding: 20px; }}
            .card {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,0.05); overflow: hidden; }}
            .header {{ background: #0366d6; color: white; padding: 20px; text-align: center; }}
            .section {{ padding: 15px 20px; border-bottom: 1px solid #e1e4e8; }}
            .game-name {{ font-size: 18px; font-weight: bold; color: #0366d6; margin-bottom: 12px; display: flex; align-items: center; }}
            .news-link {{ display: block; text-decoration: none; padding: 10px; margin: 5px 0; border-radius: 6px; background: #fff; border: 1px solid #f1f1f1; }}
            .news-link:hover {{ background: #fbfbfb; border-color: #0366d6; }}
            .v-tag {{ color: #d73a49; font-weight: bold; font-size: 13px; }}
            .title-text {{ color: #24292e; font-size: 14px; line-height: 1.5; }}
            .badge-off {{ background: #28a745; color: white; font-size: 10px; padding: 1px 4px; border-radius: 3px; margin-right: 5px; }}
            .meta {{ font-size: 11px; color: #586069; margin-top: 6px; }}
            .empty {{ font-size: 13px; color: #999; padding: 10px; }}
            .footer {{ padding: 20px; text-align: center; font-size: 11px; color: #6a737d; }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="header">
                <h2 style="margin:0;">🎯 游戏更新深度日报</h2>
                <div style="font-size:12px; margin-top:5px; opacity:0.8;">{get_beijing_time().strftime('%Y-%m-%d %H:%M')} | 官方优先模式已开启</div>
            </div>
    """
    
    for game in GAMES:
        news_list = all_data.get(game, [])
        html += f'<div class="section"><div class="game-name"># {game}</div>'
        
        if not news_list:
            html += '<div class="empty">今日暂无官方及相关更新公告</div>'
        else:
            for item in news_list:
                off_icon = '<span class="badge-off">官方</span>' if item['official'] else ''
                v_tag = f'<span class="v-tag">{item["version_tag"]}</span>' if item['version_tag'] else ''
                pub_time_str = item['time'].astimezone(datetime.timezone(datetime.timedelta(hours=8))).strftime('%H:%M')
                
                html += f"""
                <a class="news-link" href="{item['link']}">
                    <div class="title-text">{off_icon}{v_tag}{item['title']}</div>
                    <div class="meta">{item['source']} • {pub_time_str} 发布</div>
                </a>
                """
        html += '</div>'

    html += """
            <div class="footer">
                情报来源说明：系统优先检索游戏官网及B站/TapTap官号内容。<br>
                [官方] 标记代表链接直达腾讯/网易/B站官方域名。
            </div>
        </div>
    </body>
    </html>
    """
    return html

# --- 4. 执行 ---

if __name__ == "__main__":
    import os
    conf = {
        'host': 'smtp.163.com',
        'user': os.environ.get('MAIL_USER'),
        'password': os.environ.get('MAIL_PASS')
    }

    final_report = {}
    for game in GAMES:
        print(f"🚀 检索中: {game}...")
        final_report[game] = fetch_game_news(game)

    # 发送
    html_report = generate_html(final_report)
    msg = MIMEText(html_report, 'html', 'utf-8')
    msg['From'] = conf['user']
    msg['To'] = conf['user']
    msg['Subject'] = Header(f"🎮 游戏更新日报 - {datetime.date.today()}", 'utf-8')

    try:
        server = smtplib.SMTP_SSL(conf['host'], 465, timeout=30)
        server.login(conf['user'], conf['password'])
        server.sendmail(conf['user'], [conf['user']], msg.as_string())
        server.quit()
        print("✅ 日报发送成功！")
    except Exception as e:
        print(f"❌ 发送失败: {e}")
