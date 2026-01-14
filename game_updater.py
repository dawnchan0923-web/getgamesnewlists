import requests
import datetime
import smtplib
import re
import json
import urllib.parse
from email.mime.text import MIMEText
from email.header import Header

# --- 1. 核心配置 ---
# 腾讯系：直接对接官方 CMS 内容分发接口 (目前最稳的官方源)
TENCENT_GAMES = [
    {"name": "王者荣耀", "id": "pvp"},
    {"name": "和平精英", "id": "gp"},
    {"name": "无畏契约", "id": "val"},
    {"name": "穿越火线", "id": "cf"},
]
# 其他游戏：使用聚合搜索
OTHER_GAMES = ["第五人格", "超自然行动"]

KEYWORDS = ["更新", "维护", "公告", "版本", "赛季"]
# 强力排除这些“二道贩子”域名
EXCLUDE_SITES = ["163.com", "17173.com", "gamersky.com", "sina.com.cn", "sohu.com", "yuba.douyu.com"]

CHECK_RANGE_HOURS = 48 

# --- 2. 抓取逻辑 ---

def fetch_tencent_official(game):
    """直连腾讯官方后台接口，获取第一手公告"""
    results = []
    # 腾讯 CMS v3 接口
    url = "https://content.game.qq.com/c/w/get_news_list"
    params = {
        "service_type": game['id'],
        "type": "0",
        "page_size": "10",
        "page_index": "1"
    }
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)',
            'Referer': 'https://' + game['id'] + '.qq.com/'
        }
        # 使用 params 传参更规范
        resp = requests.get(url, params=params, headers=headers, timeout=10).json()
        news_list = resp.get('data', {}).get('list', [])
        
        now = datetime.datetime.now()
        for item in news_list:
            title = item.get('sTitle', '')
            pub_time_str = item.get('sIdxTime', '')
            # 这里的链接直接指向腾讯官网
            link = "https://{}.qq.com/webplat/info/news_version3/139/533/m534/index.shtml?id={}".format(game['id'], item.get('iNewsId'))
            
            if not pub_time_str: continue
            pub_time = datetime.datetime.strptime(pub_time_str, '%Y-%m-%d %H:%M:%S')
            
            if (now - pub_time).total_seconds() / 3600 < CHECK_RANGE_HOURS:
                if any(kw in title for kw in KEYWORDS):
                    results.append({
                        "game": game['name'],
                        "title": title,
                        "link": link,
                        "source": "官方公告",
                        "time": pub_time,
                        "official": True
                    })
    except Exception as e:
        print("   ⚠️ 腾讯接口抓取失败 ({}): {}".format(game['name'], e))
    return results

def fetch_by_search(game_name):
    """搜索抓取，已修复 f-string 语法错误"""
    import feedparser
    results = []
    
    # 修正：避开 f-string 内部的反斜杠限制
    kw_part = ' OR '.join(['"{}"'.format(k) for k in KEYWORDS])
    exclude_part = ' '.join(['-site:{}'.format(s) for s in EXCLUDE_SITES])
    query = 'intitle:{} ({}) {}'.format(game_name, kw_part, exclude_part)
    
    encoded_query = urllib.parse.quote(query)
    rss_url = "https://news.google.com/rss/search?q={}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans".format(encoded_query)
    
    try:
        feed = feedparser.parse(rss_url)
        now = datetime.datetime.now(datetime.timezone.utc)
        for entry in feed.entries:
            if not hasattr(entry, 'published_parsed') or not entry.published_parsed: continue
            pub_time = datetime.datetime(*entry.published_parsed[:6], tzinfo=datetime.timezone.utc)
            
            if (now - pub_time).total_seconds() / 3600 < CHECK_RANGE_HOURS:
                title = entry.title
                if game_name in title:
                    url = entry.link
                    # 识别是否为官方源
                    is_off = any(d in url for d in ["qq.com", "163.com", "taptap.cn", "bilibili.com"])
                    results.append({
                        "game": game_name,
                        "title": title,
                        "link": url,
                        "source": entry.source.get('title', '全网'),
                        "time": pub_time,
                        "official": is_off
                    })
    except: pass
    return results

# --- 3. 模板与发送 ---

def generate_html(all_data):
    html = """
    <html><head><style>
        body { font-family: 'Helvetica Neue', Arial, sans-serif; background: #f8f9fa; padding: 20px; }
        .box { max-width: 600px; margin: 0 auto; background: #fff; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); overflow: hidden; }
        .head { background: #007bff; color: white; padding: 25px; text-align: center; }
        .g-sec { padding: 20px; border-bottom: 1px solid #eee; }
        .g-name { color: #007bff; font-size: 18px; font-weight: bold; margin-bottom: 15px; border-left: 5px solid #007bff; padding-left: 12px; }
        .n-item { display: block; text-decoration: none; padding: 12px; border: 1px solid #f1f1f1; margin-bottom: 10px; border-radius: 8px; color: #333; transition: 0.2s; }
        .n-item:hover { border-color: #007bff; background: #fcfdfe; }
        .off-tag { background: #28a745; color: #fff; font-size: 10px; padding: 2px 6px; border-radius: 4px; margin-right: 8px; font-weight: bold; }
        .n-meta { font-size: 11px; color: #999; margin-top: 8px; }
    </style></head><body><div class="box"><div class="head"><h2 style="margin:0;">🎮 游戏情报中心 (官方直连)</h2></div>
    """
    for game, news in all_data.items():
        html += '<div class="g-sec"><div class="g-name"># {}</div>'.format(game)
        if not news:
            html += '<p style="color:#bbb; font-size:13px; font-style:italic;">今日暂无官方更新动态</p>'
        else:
            for n in news:
                tag = '<span class="off-tag">官方</span>' if n['official'] else ''
                t_str = n['time'].strftime('%m-%d %H:%M')
                html += '<a class="n-item" href="{}"><div>{}{}</div><div class="n-meta">{} · {}</div></a>'.format(
                    n["link"], tag, n["title"], n["source"], t_str)
        html += '</div>'
    html += '<div style="padding:20px; font-size:11px; color:#ccc; text-align:center;">数据源：腾讯内容分发中心 & Google News<br>系统已强力屏蔽非官方资讯域名</div></div></body></html>'
    return html

if __name__ == "__main__":
    import os
    conf = {'host': 'smtp.163.com', 'user': os.environ.get('MAIL_USER'), 'password': os.environ.get('MAIL_PASS')}
    
    report = {}
    # 1. 抓取腾讯
    for g in TENCENT_GAMES:
        print("📡 直连官方接口: {}...".format(g['name']))
        report[g['name']] = fetch_tencent_official(g)
    
    # 2. 抓取其他
    for gname in OTHER_GAMES:
        print("🔍 深度检索: {}...".format(gname))
        report[gname] = fetch_by_search(gname)

    # 发送邮件
    msg = MIMEText(generate_html(report), 'html', 'utf-8')
    msg['From'] = conf['user']
    msg['To'] = conf['user']
    msg['Subject'] = Header("🎮 游戏情报中心日报 - {}".format(datetime.date.today()), 'utf-8')
    
    try:
        s = smtplib.SMTP_SSL(conf['host'], 465)
        s.login(conf['user'], conf['password'])
        s.sendmail(conf['user'], [conf['user']], msg.as_string())
        s.quit()
        print("✅ 成功发送！")
    except Exception as e:
        print("❌ 发送失败: {}".format(e))
