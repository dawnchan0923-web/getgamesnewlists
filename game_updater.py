import requests
import datetime
import smtplib
import re
import json
import urllib.parse
from email.mime.text import MIMEText
from email.header import Header

# --- 1. 核心配置 ---
# 腾讯系：直连内容分发中心（官方最快）
TENCENT_GAMES = [
    {"name": "王者荣耀", "id": "pvp"},
    {"name": "和平精英", "id": "gp"},
    {"name": "无畏契约", "id": "val"},
    {"name": "穿越火线", "id": "cf"},
]
# 其他游戏：使用强力过滤的搜索模式
OTHER_GAMES = ["第五人格", "超自然行动"]

KEYWORDS = ["更新", "维护", "公告", "版本", "赛季"]
# 排除掉那些经常发八卦的“二道贩子”域名
EXCLUDE_SITES = ["163.com", "17173.com", "gamersky.com", "sina.com.cn", "sohu.com"]

CHECK_RANGE_HOURS = 48 

# --- 2. 核心抓取逻辑 ---

def fetch_tencent_official(game):
    """直接调用腾讯官方 CMS 接口获取纯正公告"""
    results = []
    # 这是腾讯官方各游戏通用的内容中心接口
    url = f"https://content.game.qq.com/c/w/get_news_list?service_type={game['id']}&type=0&page_size=10&page_index=1"
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)', 'Referer': f'https://{game["id"]}.qq.com/'}
        resp = requests.get(url, headers=headers, timeout=10).json()
        news_list = resp.get('data', {}).get('list', [])
        
        now = datetime.datetime.now()
        for item in news_list:
            title = item.get('sTitle', '')
            pub_time_str = item.get('sIdxTime', '')
            link = f"https://{game['id']}.qq.com/webplat/info/news_version3/139/533/m534/index.shtml?id={item.get('iNewsId')}"
            
            if not pub_time_str: continue
            pub_time = datetime.datetime.strptime(pub_time_str, '%Y-%m-%d %H:%M:%S')
            
            if (now - pub_time).total_seconds() / 3600 < CHECK_RANGE_HOURS:
                if any(kw in title for kw in KEYWORDS):
                    results.append({
                        "game": game['name'],
                        "title": title,
                        "link": link,
                        "source": "腾讯官网",
                        "time": pub_time,
                        "official": True
                    })
    except Exception as e:
        print(f"   ⚠️ 腾讯官方接口调用失败 ({game['name']}): {e}")
    return results

def fetch_by_search(game_name):
    """使用 Google News 搜索，但通过 site 指令强制过滤掉杂质"""
    import feedparser
    results = []
    # 搜索策略：排除掉 EXCLUDE_SITES 里的二道贩子
    exclude_query = " ".join([f"-site:{s}" for s in EXCLUDE_SITES])
    query = f'intitle:{game_name} ("{"\" OR \"".join(KEYWORDS)}") {exclude_query}'
    
    encoded_query = urllib.parse.quote(query)
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
    
    try:
        feed = feedparser.parse(rss_url)
        now = datetime.datetime.now(datetime.timezone.utc)
        for entry in feed.entries:
            pub_time = datetime.datetime(*entry.published_parsed[:6], tzinfo=datetime.timezone.utc)
            if (now - pub_time).total_seconds() / 3600 < CHECK_RANGE_HOURS:
                # 只有标题里明确含游戏名的才要
                if game_name in entry.title:
                    url = entry.link
                    # 如果来源包含 qq.com, 163.com(仅限网易游戏), taptap 则标记为官方
                    is_off = any(d in url for d in ["qq.com", "taptap.cn", "bilibili.com"])
                    if "163.com" in url and game_name in ["第五人格", "超自然行动"]:
                        is_off = True
                        
                    results.append({
                        "game": game_name,
                        "title": entry.title,
                        "link": url,
                        "source": entry.source.get('title', '全网'),
                        "time": pub_time,
                        "official": is_off
                    })
    except: pass
    return results

# --- 3. 邮件模板 ---

def generate_html(all_data):
    html = f"""
    <html><head><style>
        body {{ font-family: 'Helvetica Neue', Arial, sans-serif; background: #f4f7f6; padding: 20px; }}
        .box {{ max-width: 600px; margin: 0 auto; background: #fff; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); overflow: hidden; }}
        .head {{ background: #dc3545; color: white; padding: 20px; text-align: center; }}
        .g-sec {{ padding: 15px; border-bottom: 5px solid #f4f7f6; }}
        .g-name {{ color: #dc3545; font-size: 18px; font-weight: bold; margin-bottom: 10px; border-left: 4px solid #dc3545; padding-left: 10px; }}
        .n-item {{ display: block; text-decoration: none; padding: 10px; border: 1px solid #eee; margin-bottom: 8px; border-radius: 4px; color: #333; }}
        .n-item:hover {{ background: #fff9f9; border-color: #dc3545; }}
        .off-tag {{ background: #28a745; color: #fff; font-size: 10px; padding: 2px 5px; border-radius: 3px; margin-right: 5px; vertical-align: middle; }}
        .n-meta {{ font-size: 11px; color: #888; margin-top: 5px; }}
    </style></head><body><div class="box"><div class="head"><h2>🔥 游戏情报精选 (官方驱动版)</h2></div>
    """
    for game, news in all_data.items():
        html += f'<div class="g-sec"><div class="g-name">{game}</div>'
        if not news:
            html += '<p style="color:#999; font-size:13px;">今日暂无官方更新动态</p>'
        else:
            for n in news:
                tag = '<span class="off-tag">官方</span>' if n['official'] else ''
                t_str = n['time'].astimezone(datetime.timezone(datetime.timedelta(hours=8))).strftime('%m-%d %H:%M')
                html += f'<a class="n-item" href="{n["link"]}"><div>{tag}{n["title"]}</div><div class="n-meta">{n["source"]} · {t_str}</div></a>'
        html += '</div>'
    html += '<div style="padding:20px; font-size:10px; color:#bbb; text-align:center;">系统优先调用腾讯内容分发中心接口 · 过滤非官方资讯源</div></div></body></html>'
    return html

# --- 4. 主流程 ---

if __name__ == "__main__":
    import os
    conf = {'host': 'smtp.163.com', 'user': os.environ.get('MAIL_USER'), 'password': os.environ.get('MAIL_PASS')}
    
    report = {}
    # 1. 抓取腾讯官方接口
    for g in TENCENT_GAMES:
        print(f"📡 正在直连腾讯内容中心: {g['name']}...")
        report[g['name']] = fetch_tencent_official(g)
    
    # 2. 抓取其他游戏（带强力过滤）
    for gname in OTHER_GAMES:
        print(f"🔍 正在深度检索: {gname}...")
        report[gname] = fetch_by_search(gname)

    # 发送
    msg = MIMEText(generate_html(report), 'html', 'utf-8')
    msg['From'] = conf['user']
    msg['To'] = conf['user']
    msg['Subject'] = Header(f"🎮 游戏更新日报 - {datetime.date.today()}", 'utf-8')
    
    try:
        s = smtplib.SMTP_SSL(conf['host'], 465)
        s.login(conf['user'], conf['password'])
        s.sendmail(conf['user'], [conf['user']], msg.as_string())
        s.quit()
        print("✅ 日报发送成功！")
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")
