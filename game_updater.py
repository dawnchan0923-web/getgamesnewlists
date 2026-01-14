import feedparser
import datetime
import smtplib
import urllib.parse
from email.mime.text import MIMEText
from email.header import Header

# --- 1. 配置：游戏列表与官方域名 ---
GAMES = ["王者荣耀", "和平精英", "无畏契约", "穿越火线", "第五人格", "超自然行动"]

# 官方域名关键字：只要 URL 包含这些，就视为官方
OFFICIAL_KEYWORDS = ["qq.com", "163.com", "taptap.cn", "bilibili.com", "weibo.com", "val.qq.com", "pvp.qq.com", "gp.qq.com"]

# 排除干扰项：排除掉那些喜欢发八卦攻略的网站
BLACKLIST_SITES = ["douyin.com", "tiktok.com", "zhihu.com", "xiaohongshu.com", "sohu.com", "sina.com.cn"]

# 搜索关键词
SEARCH_KEYWORDS = ["更新", "维护", "公告", "停服"]
CHECK_RANGE_HOURS = 24  # 每天检查

def get_beijing_time():
    """获取北京时间"""
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))

def is_official_link(url):
    """根据链接判断是否为官方源"""
    return any(k in url.lower() for k in OFFICIAL_KEYWORDS)

def fetch_game_updates(game):
    """使用 Google News 聚合引擎抓取"""
    results = []
    # 构造高级搜索指令： 游戏名 (更新 OR 维护...) -site:douyin.com...
    kw_query = ' OR '.join(['"{}"'.format(kw) for kw in SEARCH_KEYWORDS])
    exclude_query = ' '.join(['-site:{}'.format(s) for s in BLACKLIST_SITES])
    
    # 强制让 Google 找官方的域名
    query = '{} ({}) {}'.format(game, kw_query, exclude_query)
    encoded_query = urllib.parse.quote(query)
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
    
    try:
        feed = feedparser.parse(rss_url)
        now = datetime.datetime.now(datetime.timezone.utc)
        
        for entry in feed.entries:
            if not hasattr(entry, 'published_parsed') or not entry.published_parsed:
                continue
            
            pub_time = datetime.datetime(*entry.published_parsed[:6], tzinfo=datetime.timezone.utc)
            
            # 过滤 24 小时内的新闻
            if (now - pub_time).total_seconds() / 3600 < CHECK_RANGE_HOURS:
                title = entry.title
                # 排除攻略类、八卦类词汇
                if any(bad in title for bad in ["攻略", "八卦", "盘点", "怎么样", "推荐", "视频"]):
                    continue
                
                url = entry.link
                is_off = is_official_link(url) or "官方" in entry.source.get('title', '')
                
                results.append({
                    "title": title,
                    "link": url,
                    "source": entry.source.get('title', '全网聚合'),
                    "time": pub_time.astimezone(datetime.timezone(datetime.timedelta(hours=8))),
                    "official": is_off
                })
    except Exception as e:
        print(f"   ⚠️ {game} 检索失败: {e}")
        
    # 去重：按标题前 15 位
    unique_list = []
    seen = set()
    for item in results:
        sig = item['title'][:15]
        if sig not in seen:
            unique_list.append(item)
            seen.add(sig)
            
    # 排序：官方置顶
    unique_list.sort(key=lambda x: x['official'], reverse=True)
    return unique_list

def generate_html(data_dict):
    """美化排版"""
    html = f"""
    <html><head><style>
        body {{ font-family: 'Helvetica Neue', Arial, sans-serif; background: #f4f7f6; padding: 20px; color: #333; }}
        .card {{ max-width: 600px; margin: 0 auto; background: #fff; border-radius: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); overflow: hidden; }}
        .header {{ background: #007bff; color: white; padding: 20px; text-align: center; }}
        .section {{ padding: 15px 20px; border-bottom: 1px solid #eee; }}
        .game-header {{ font-size: 18px; font-weight: bold; color: #007bff; margin-bottom: 10px; border-left: 5px solid #007bff; padding-left: 10px; }}
        .news-item {{ display: block; text-decoration: none; color: #333; padding: 10px; margin-bottom: 5px; background: #f9f9f9; border-radius: 5px; }}
        .news-item:hover {{ background: #f0f7ff; }}
        .tag-off {{ background: #28a745; color: white; font-size: 10px; padding: 2px 5px; border-radius: 3px; margin-right: 5px; vertical-align: middle; }}
        .meta {{ font-size: 11px; color: #888; margin-top: 5px; }}
    </style></head><body><div class="card"><div class="header"><h2 style="margin:0;">🎯 游戏更新汇总 (权威筛选版)</h2></div>
    """
    for game, items in data_dict.items():
        html += f'<div class="section"><div class="game-header">{game}</div>'
        if not items:
            html += '<p style="font-size:13px; color:#999; font-style:italic;">今日暂无官方及核心更新公告</p>'
        else:
            for item in items:
                tag = '<span class="tag-off">官方</span>' if item['official'] else ''
                html += f"""
                <a class="news-item" href="{item['link']}">
                    <div>{tag}{item['title']}</div>
                    <div class="meta">{item['source']} • {item['time'].strftime('%H:%M')} 发布</div>
                </a>
                """
        html += '</div>'
    html += '<div style="padding:15px; text-align:center; font-size:11px; color:#bbb;">数据由 Google News 提供 · 已强力过滤非官方干扰源</div></div></body></html>'
    return html

if __name__ == "__main__":
    import os
    conf = {'host': 'smtp.163.com', 'user': os.environ.get('MAIL_USER'), 'password': os.environ.get('MAIL_PASS')}
    
    all_data = {}
    for game in GAMES:
        print(f"🚀 正在聚合情报: {game}...")
        all_data[game] = fetch_game_updates(game)
        
    html_report = generate_html(all_data)
    
    # 判断是否有任何更新
    if any(all_data.values()):
        msg = MIMEText(html_report, 'html', 'utf-8')
        msg['From'] = conf['user']
        msg['To'] = conf['user']
        msg['Subject'] = Header(f"🎮 游戏情报中心日报 - {datetime.date.today()}", 'utf-8')
        try:
            s = smtplib.SMTP_SSL(conf['host'], 465)
            s.login(conf['user'], conf['password'])
            s.sendmail(conf['user'], [conf['user']], msg.as_string())
            s.quit()
            print("✅ 成功发送权威日报！")
        except Exception as e:
            print(f"❌ 发送失败: {e}")
    else:
        print("今日无符合条件的新内容。")
