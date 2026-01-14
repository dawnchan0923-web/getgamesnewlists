import requests
import datetime
import smtplib
import json
from email.mime.text import MIMEText
from email.header import Header

# --- 1. 核心配置：各游戏 B 站官号的 UID ---
# 获取 UID 方法：去 B 站搜索官号，空间主页 URL 里的数字就是 UID
GAMES = [
    {"name": "王者荣耀", "uid": "5780482"},
    {"name": "和平精英", "uid": "311027170"},
    {"name": "无畏契约", "uid": "1478516035"},
    {"name": "穿越火线", "uid": "11132514"},
    {"name": "第五人格", "uid": "271502434"},
    {"name": "超自然行动", "uid": "3546654013446051"}, # 官号：超自然行动
]

KEYWORDS = ["更新", "维护", "版本", "公告", "赛季", "停服"]
CHECK_RANGE_HOURS = 48 # 检查过去 48 小时

def get_bili_news(game):
    results = []
    print(f"🔍 正在检查 B 站官号: {game['name']}...")
    try:
        # B 站公开动态接口
        url = f"https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space?host_mid={game['uid']}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.bilibili.com/'
        }
        r = requests.get(url, headers=headers, timeout=15)
        data = r.json()
        
        items = data.get('data', {}).get('items', [])
        print(f"   ✅ 成功连接！获取到 {len(items)} 条动态记录")

        now = datetime.datetime.now()
        for item in items:
            # 提取动态文字内容
            try:
                desc = item.get('modules', {}).get('module_dynamic', {}).get('desc', {}).get('text', '')
                pub_time_raw = item.get('modules', {}).get('module_author', {}).get('pub_ts', 0)
                pub_time = datetime.datetime.fromtimestamp(pub_time_raw)
                id_str = item.get('id_str', '')
                link = f"https://t.bilibili.com/{id_str}"
                
                # 时间和关键词匹配
                if (now - pub_time).total_seconds() / 3600 < CHECK_RANGE_HOURS:
                    if any(kw in desc for kw in KEYWORDS):
                        # 截取前 50 个字符作为标题
                        title = desc.split('\n')[0][:50]
                        results.append(f"【{game['name']}】{title}\n链接: {link}")
            except:
                continue
                
    except Exception as e:
        print(f"   ❌ 抓取失败: {e}")
        
    return list(set(results)) # 去重

def send_email(content_list, smtp):
    if not content_list:
        print("\n📢 结果：B 站接口通畅，但过去 48 小时无更新相关动态。")
        return
    
    body = "游戏更新自动监控报告（数据源：B站官号动态）：\n\n" + "\n\n".join(content_list)
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['From'] = smtp['user']
    msg['To'] = smtp['user']
    msg['Subject'] = Header(f"游戏更新汇总 - {datetime.date.today()}", 'utf-8')

    try:
        s = smtplib.SMTP_SSL(smtp['host'], 465)
        s.login(smtp['user'], smtp['password'])
        s.sendmail(smtp['user'], [smtp['user']], msg.as_string())
        s.quit()
        print("\n🚀 邮件已成功发送！")
    except Exception as e:
        print(f"\n❌ 邮件发送失败: {e}")

if __name__ == "__main__":
    import os
    conf = {
        'host': 'smtp.qq.com',
        'user': os.environ.get('MAIL_USER'),
        'password': os.environ.get('MAIL_PASS')
    }
    
    all_news = []
    for g in GAMES:
        all_news.extend(get_bili_news(g))
    
    send_email(all_news, conf)
