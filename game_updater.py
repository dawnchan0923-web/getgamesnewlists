import feedparser
import datetime
import smtplib
import urllib.parse
from email.mime.text import MIMEText
from email.header import Header

# --- 1. 配置：核心游戏清单 ---
GAMES = ["王者荣耀", "和平精英", "无畏契约", "穿越火线", "第五人格", "超自然行动"]

# 官方域名池
OFFICIAL_KEYWORDS = ["qq.com", "163.com", "taptap.cn", "bilibili.com", "weibo.com", "val.qq.com", "pvp.qq.com", "gp.qq.com", "cf.qq.com"]

# 行业噪音黑名单（只要标题含这些词，直接过滤）
NOISE_WORDS = [
    "汽车", "奔驰", "豪华车", "SUV", "股价", "跌超", "涨超", "裁员", "财报", 
    "开庭", "诉讼", "判决", "理财", "全家桶", "苹果", "裁撤", "股市", "盘中",
    "基金", "投资", "收购", "合并", "地产", "楼盘"
]

# 搜索关键词（缩窄范围，只要最相关的）
SEARCH_KEYWORDS = ["更新", "维护", "公告", "版本", "停服"]

CHECK_RANGE_HOURS = 24  # 检查 24 小时内

def get_beijing_time():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))

def fetch_game_updates(game):
    results = []
    # 升级搜索指令：intitle: 强制标题匹配
    kw_query = ' OR '.join(['"{}"'.format(kw) for kw in SEARCH_KEYWORDS])
    # 强制标题包含游戏名
    query = 'intitle:"{}" ({})'.format(game, kw_query)
    
    encoded_query = urllib.parse.quote(query)
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
    
    try:
        feed = feedparser.parse(rss_url)
        now = datetime.datetime.now(datetime.timezone.utc)
        
        for entry in feed.entries:
            if not hasattr(entry, 'published_parsed') or not entry.published_parsed:
                continue
            
            pub_time = datetime.datetime(*entry.published_parsed[:6], tzinfo=datetime.timezone.utc)
            
            if (now - pub_time).total_seconds() / 3600 < CHECK_RANGE_HOURS:
                title = entry.title
                
                # --- 硬核过滤开始 ---
                # 1. 标题必须包含游戏名（大小写不敏感）
                if game.lower() not in title.lower():
                    continue
                
                # 2. 必须包含至少一个更新关键词
                if not any(kw in title for kw in SEARCH_KEYWORDS):
                    continue
                    
                # 3. 排除噪音行业的干扰词
                if any(noise in title for noise in NOISE_WORDS):
                    continue
                
                # 4. 过滤一些明显的非游戏资讯源
                source_name = entry.source.get('title', '全网聚合')
                if any(noise_src in source_name for noise_src in ["经济", "汽车", "财经", "金融", "房产"]):
                    continue
                # --- 硬核过滤结束 ---

                url = entry.link
                is_off = any(k in url.lower() for k in OFFICIAL_KEYWORDS)
                
                results.append({
                    "title": title.split(" - ")[0], # 去掉标题末尾的来源后缀
                    "link": url,
                    "source": source_name,
                    "time": pub_time.astimezone(datetime.timezone(datetime.timedelta(hours=8))),
                    "official": is_off
                })
    except Exception as e:
        print(f"   ⚠️ {game} 检索失败: {e}")
        
    # 去重
    unique_list = []
    seen = set()
    for item in results:
        if item['title'][:12] not in seen:
            unique_list.append(item)
            seen.add(item['title'][:12])
            
    # 排序：官方置顶
    unique_list.sort(key=lambda x: x['official'], reverse=True)
    return unique_list

def generate_html(data_dict):
    html = f"""
    <html><head><style>
        body {{ font-family: 'Helvetica Neue', Arial, sans-serif; background: #f0f2f5; padding: 20px; color: #333; }}
        .card {{ max-width: 600px; margin: 0 auto; background: #fff; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); overflow: hidden; }}
        .header {{ background: #1a73e8; color: white; padding: 20px; text-align: center; }}
        .section {{ padding: 15px 20px; border-bottom: 1px solid #f0f0f0; }}
        .game-header {{ font-size: 18px; font-weight: bold; color: #1a73e8; margin-bottom: 12px; border-left: 5px solid #1a73e8; padding-left: 10px; }}
        .news-item {{ display: block; text-decoration: none; color: #202124; padding: 12px; margin-bottom: 8px; background: #f8f9fa; border-radius: 8px; border: 1px solid #eee; }}
        .news-item:hover {{ border-color: #1a73e8; background: #fff; }}
        .tag-off {{ background: #34a853; color: white; font-size: 10px; padding: 2px 6px; border-radius: 4px; margin-right: 8px; font-weight: bold; }}
        .meta {{ font-size: 11px; color: #70757a; margin-top: 8px; }}
    </style></head><body><div class="card"><div class="header"><h2 style="margin:0;">🎯 游戏更新日报 (严格过滤版)</h2></div>
    """
    for game, items in data_dict.items():
        html += f'<div class="section"><div class="game-header"># {game}</div>'
        if not items:
            html += '<p style="font-size:13px; color:#999; font-style:italic;">今日暂无相关更新公告</p>'
        else:
            for item in items:
                tag = '<span class="tag-off">官方渠道</span>' if item['official'] else ''
                html += f"""
                <a class="news-item" href="{item['link']}">
                    <div style="font-size:15px; font-weight:500;">{tag}{item['title']}</div>
                    <div class="meta">{item['source']} • {item['time'].strftime('%m-%d %H:%M')}</div>
                </a>
                """
        html += '</div>'
    html += '<div style="padding:15px; text-align:center; font-size:11px; color:#999;">技术支持: Google News RSS 严格检索机制<br>已排除汽车、财经及无关行业噪音</div></div></body></html>'
    return html

if __name__ == "__main__":
    import os
    conf = {'host': 'smtp.163.com', 'user': os.environ.get('MAIL_USER'), 'password': os.environ.get('MAIL_PASS')}
    
    all_data = {}
    for game in GAMES:
        print(f"🚀 正在提取精选公告: {game}...")
        all_data[game] = fetch_game_updates(game)
        
    if any(all_data.values()):
        msg = MIMEText(generate_html(all_data), 'html', 'utf-8')
        msg['From'] = conf['user']
        msg['To'] = conf['user']
        msg['Subject'] = Header(f"🎮 游戏更新精选日报 - {datetime.date.today()}", 'utf-8')
        try:
            s = smtplib.SMTP_SSL(conf['host'], 465)
            s.login(conf['user'], conf['password'])
            s.sendmail(conf['user'], [conf['user']], msg.as_string())
            s.quit()
            print("✅ 精选日报发送成功！")
        except Exception as e:
            print(f"❌ 发送失败: {e}")
