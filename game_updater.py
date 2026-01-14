import requests
import json
import datetime
import smtplib
import re
from email.mime.text import MIMEText
from email.header import Header

# --- 1. 核心配置：直接指向官方数据源 ---
# 腾讯游戏大多使用这个数据存储格式
GAMES = [
    {"name": "王者荣耀", "url": "https://pvp.qq.com/web201706/js/newsdata.js", "type": "tencent"},
    {"name": "和平精英", "url": "https://gp.qq.com/web201908/js/newsdata.js", "type": "tencent"},
    {"name": "无畏契约", "url": "https://val.qq.com/web202306/js/newsdata.js", "type": "tencent"},
    {"name": "穿越火线", "url": "https://cf.qq.com/web202004/js/news_data.js", "type": "tencent"},
]

KEYWORDS = ["更新", "维护", "版本", "公告", "Season", "赛季", "停服"]
CHECK_RANGE_HOURS = 24  # 检查过去24小时

def get_tencent_news(game):
    results = []
    try:
        # 腾讯的这些 .js 文件其实是封装好的 JSON
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(game['url'], headers=headers)
        response.encoding = 'gbk' # 腾讯接口通常用 GBK 编码
        
        # 提取真正的 JSON 内容
        content = response.text
        json_str = content[content.find('{'):content.rfind('}')+1]
        data = json.loads(json_str)
        
        # 遍历新闻列表 (通常在 news_all 字段)
        news_list = data.get('news_all', [])
        now = datetime.datetime.now()

        for item in news_list:
            title = item.get('sTitle', '')
            date_str = item.get('sIdxTime', '') # 格式通常是 2024-05-20 10:00:00
            # 兼容不同游戏的跳转链接
            raw_url = item.get('sRedirectURL') or item.get('vLink') or ""
            link = "https:" + raw_url if raw_url.startswith('//') else raw_url

            if not date_str: continue
            
            pub_time = datetime.datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
            
            # 判断时间范围和关键词
            if (now - pub_time).total_seconds() / 3600 < CHECK_RANGE_HOURS:
                if any(kw in title for kw in KEYWORDS):
                    results.append(f"【{game['name']}】{title}\n链接: {link}")
    except Exception as e:
        print(f"❌ 抓取 {game['name']} 失败: {e}")
    return results

def send_email(content_list, smtp_config):
    if not content_list:
        print("今日无符合条件的更新公告。")
        return

    mail_content = "检测到以下游戏更新：\n\n" + "\n\n".join(content_list)
    msg = MIMEText(mail_content, 'plain', 'utf-8')
    msg['From'] = smtp_config['sender']
    msg['To'] = smtp_config['receiver']
    msg['Subject'] = Header(f"游戏更新汇总 - {datetime.date.today()}", 'utf-8')

    try:
        server = smtplib.SMTP_SSL(smtp_config['host'], 465)
        server.login(smtp_config['user'], smtp_config['password'])
        server.sendmail(smtp_config['sender'], [smtp_config['receiver']], msg.as_string())
        server.quit()
        print("🚀 邮件发送成功！")
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")

if __name__ == "__main__":
    import os
    SMTP_CONFIG = {
        'host': 'smtp.qq.com',
        'user': os.environ.get('MAIL_USER'),
        'password': os.environ.get('MAIL_PASS'),
        'sender': os.environ.get('MAIL_USER'),
        'receiver': os.environ.get('MAIL_USER')
    }
    
    all_news = []
    for game in GAMES:
        print(f"正在抓取: {game['name']}...")
        all_news.extend(get_tencent_news(game))
    
    send_email(all_news, SMTP_CONFIG)
