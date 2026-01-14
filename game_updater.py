import requests
import datetime
import smtplib
import re
import urllib.parse
from email.mime.text import MIMEText
from email.header import Header

# --- 1. 配置：游戏与数据源 ---
TENCENT_GAMES = [
    {"name": "王者荣耀", "url": "https://pvp.qq.com/web201706/js/newsdata.js"},
    {"name": "和平精英", "url": "https://gp.qq.com/web201908/js/newsdata.js"},
    {"name": "无畏契约", "url": "https://val.qq.com/web202306/js/newsdata.js"},
    {"name": "穿越火线", "url": "https://cf.qq.com/web202004/js/news_data.js"},
]

NETEASE_GAMES = [
    {"name": "第五人格", "search_key": "第五人格 官方公告"},
    {"name": "超自然行动", "search_key": "超自然行动 官方公告"},
]

KEYWORDS = ["更新", "维护", "公告", "版本", "赛季", "停服"]
# 强力排除列表：防止垃圾信息干扰
JUNK_SITES = ["douyin.com", "tiktok.com", "zhihu.com", "xiaohongshu.com", "kuaishou.com", "baidu.com"]

CHECK_RANGE_HOURS = 48 

# --- 2. 抓取逻辑 ---

def fetch_tencent(game):
    """抓取腾讯主站 JS 数据，这是目前最稳的官方源"""
    results = []
    print(f"📡 正在直连腾讯官网: {game['name']}...")
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        r = requests.get(game['url'], headers=headers, timeout=15)
        r.encoding = 'gbk'
        content = r.text
        
        # 使用正则抠取 标题、时间、链接
        # 腾讯格式: sTitle:"...", sIdxTime:"..."
        titles = re.findall(r'sTitle\s*:\s*["\'](.*?)["\']', content)
        dates = re.findall(r'sIdxTime\s*:\s*["\'](.*?)["\']', content)
        urls = re.findall(r'(?:sRedirectURL|vLink)\s*:\s*["\'](.*?)["\']', content)

        now = datetime.datetime.now()
        for i in range(min(len(titles), 15)):
            t = titles[i]
            # 解决 Unicode 乱码
            try: t = t.encode('utf-8').decode('unicode_escape')
            except: pass
            
            d_str = dates[i] if i < len(dates) else ""
            u_str = urls[i] if i < len(urls) else ""
            
            if not d_str: continue
            p_time = datetime.datetime.strptime(d_str, '%Y-%m-%d %H:%M:%S')
            
            if (now - p_time).total_seconds() / 3600 < CHECK_RANGE_HOURS:
                if any(kw in t for kw in KEYWORDS):
                    link = "https:" + u_str if u_str.startswith('//') else u_str
                    results.append({"title": t, "link": link, "source": "腾讯官网", "time": p_time, "official": True})
    except Exception as e:
        print(f"   ❌ {game['name']} 失败: {e}")
    return results

def fetch_search(game_name, search_key):
    """带强力过滤的搜索逻辑"""
    import feedparser
    results = []
    print(f"🔍 正在深度检索: {game_name}...")
    
    # 构造搜索指令：排除所有垃圾站点
    exclude_str = " ".join([f"-site:{s}" for s in JUNK_SITES])
    query = f'"{game_name}" (更新 OR 维护 OR 公告) {exclude_str}'
    
    encoded_query = urllib.parse.quote(query)
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
    
    try:
        feed = feedparser.parse(rss_url)
        now = datetime.datetime.now(datetime.timezone.utc)
        for entry in feed.entries:
            pub_time = datetime.datetime(*entry.published_parsed[:6], tzinfo=datetime.timezone.utc)
            if (now - pub_time).total_seconds() / 3600 < CHECK_RANGE_HOURS:
                title = entry.title
                # 二次过滤：标题必须含游戏名，且不含“怎么”、“如何”等攻略词
                if game_name in title and not any(w in title for w in ["怎么", "如何", "哪里", "攻略"]):
                    is_off = any(d in entry.link for d in ["163.com", "qq.com", "taptap.cn"])
                    results.append({
                        "title": title, "link": entry.link, 
                        "source": entry.source.get('title', '全网'), 
                        "time": pub_time, "official": is_off
                    })
    except: pass
    return results

# --- 3. 页面生成与发信 ---

def generate_html(all_data):
    html = """
    <html><head><style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f0f2f5; padding: 20px; }
        .card { max-width: 600px; margin: 0 auto; background: #fff; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); overflow: hidden; }
        .header { background: #1a73e8; color: white; padding: 20px; text-align: center; }
        .section { padding: 15px 20px; border-bottom: 1px solid #eee; }
        .g-name { color: #1a73e8; font-size: 18px; font-weight: bold; margin-bottom: 12px; border-left: 5px solid #1a73e8; padding-left: 10px; }
        .n-item { display: block; text-decoration: none; padding: 12px; background: #fafafa; border-radius: 8px; margin-bottom: 8px; color: #333; border: 1px solid #f0f0f0; }
        .off-tag { background: #34a853; color: white; font-size: 10px; padding: 2px 5px; border-radius: 4px; margin-right: 8px; }
        .meta { font-size: 11px; color: #777; margin-top: 5px; }
    </style></head><body><div class="card"><div class="header"><h2 style="margin:0;">🎮 游戏更新情报 (纯净版)</h2></div>
    """
    for game_name, news in all_data.items():
        html += f'<div class="section"><div class="g-name">{game_name}</div>'
        if not news:
            html += '<p style="color:#999; font-size:13px; font-style:italic;">今日暂无官方更新公告</p>'
        else:
            for n in news:
                tag = '<span class="off-tag">官方</span>' if n['official'] else ''
                t_str = n['time'].strftime('%m-%d %H:%M')
                html += f'<a class="n-item" href="{n["link"]}"><div>{tag}{n["title"]}</div><div class="meta">{n["source"]} · {t_str}</div></a>'
        html += '</div>'
    html += '<div style="padding:15px; font-size:10px; color:#bbb; text-align:center;">已自动剔除抖音/知乎等非官方干扰信息</div></div></body></html>'
    return html

if __name__ == "__main__":
    import os
    conf = {'host': 'smtp.163.com', 'user': os.environ.get('MAIL_USER'), 'password': os.environ.get('MAIL_PASS')}
    
    report = {}
    # 1. 抓取腾讯（直连主站）
    for g in TENCENT_GAMES:
        report[g['name']] = fetch_tencent(g)
    
    # 2. 抓取网易及其他（深度搜索）
    for g in NETEASE_GAMES:
        report[g['name']] = fetch_search(g['name'], g['search_key'])

    # 3. 发送
    msg = MIMEText(generate_html(report), 'html', 'utf-8')
    msg['From'] = conf['user']
    msg['To'] = conf['user']
    msg['Subject'] = Header(f"🎮 游戏更新情报汇总 - {datetime.date.today()}", 'utf-8')
    
    try:
        s = smtplib.SMTP_SSL(conf['host'], 465)
        s.login(conf['user'], conf['password'])
        s.sendmail(conf['user'], [conf['user']], msg.as_string())
        s.quit()
        print("✅ 纯净版日报发送成功！")
    except Exception as e:
        print(f"❌ 发信失败: {e}")
