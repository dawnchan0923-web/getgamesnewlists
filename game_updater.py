import requests
import json
import datetime
import smtplib
import re
from email.mime.text import MIMEText
from email.header import Header

# --- 1. 配置：腾讯官方数据接口 ---
GAMES = [
    {"name": "王者荣耀", "url": "https://pvp.qq.com/web201706/js/newsdata.js"},
    {"name": "和平精英", "url": "https://gp.qq.com/web201908/js/newsdata.js"},
    {"name": "无畏契约", "url": "https://val.qq.com/web202306/js/newsdata.js"},
    {"name": "穿越火线", "url": "https://cf.qq.com/web202004/js/news_data.js"},
]

KEYWORDS = ["更新", "维护", "版本", "公告", "Season", "赛季", "停服"]
CHECK_RANGE_HOURS = 48  # 测试阶段建议设为48小时，确保有数据

def get_news_list(game):
    results = []
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(game['url'], headers=headers, timeout=10)
        
        # 腾讯接口通常是 GBK 编码，强制转换防止乱码
        response.encoding = 'gbk'
        content = response.text
        
        # --- 核心清洗逻辑：使用正则表达式提取 [] 之间的新闻列表 ---
        match = re.search(r'\[.*\]', content, re.S)
        if not match:
            print(f"  ⚠️ {game['name']} 未能在JS中匹配到数据数组")
            return []
            
        data_str = match.group()
        # 简单处理一些 JS 对象和标准 JSON 的差异（比如末尾多余的逗号）
        data_str = re.sub(r',\s*]', ']', data_str)
        
        news_list = json.loads(data_str)
        print(f"  ✅ {game['name']} 成功解析 {len(news_list)} 条原始数据")
        
        now = datetime.datetime.now()
        for item in news_list:
            title = item.get('sTitle', '')
            date_str = item.get('sIdxTime', '')
            # 兼容不同链接字段
            raw_url = item.get('sRedirectURL') or item.get('vLink') or ""
            link = "https:" + raw_url if raw_url.startswith('//') else raw_url
            
            if not date_str: continue
            
            # 转换时间
            try:
                pub_time = datetime.datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
            except:
                continue

            # 过滤逻辑
            if (now - pub_time).total_seconds() / 3600 < CHECK_RANGE_HOURS:
                if any(kw in title for kw in KEYWORDS):
                    results.append(f"【{game['name']}】{title}\n链接: {link}")
                    
    except Exception as e:
        print(f"  ❌ {game['name']} 处理出错: {str(e)[:100]}")
        
    return results

def send_email(content_list, smtp_config):
    if not content_list:
        print("今日无符合条件的更新公告。")
        return

    mail_content = "为您汇总以下游戏更新公告（过去48小时）：\n\n" + "\n\n".join(content_list)
    msg = MIMEText(mail_content, 'plain', 'utf-8')
    msg['From'] = smtp_config['sender']
    msg['To'] = smtp_config['receiver']
    msg['Subject'] = Header(f"游戏更新汇总 - {datetime.date.today()}", 'utf-8')

    try:
        server = smtplib.SMTP_SSL(smtp_config['host'], 465)
        server.login(smtp_config['user'], smtp_config['password'])
        server.sendmail(smtp_config['sender'], [smtp_config['receiver']], msg.as_string())
        server.quit()
        print("🚀 邮件发送成功！请查看收件箱。")
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")

if __name__ == "__main__":
    import os
    # 环境变量读取
    SMTP_CONFIG = {
        'host': 'smtp.qq.com',
        'user': os.environ.get('MAIL_USER'),
        'password': os.environ.get('MAIL_PASS'),
        'sender': os.environ.get('MAIL_USER'),
        'receiver': os.environ.get('MAIL_USER')
    }
    
    final_list = []
    for game in GAMES:
        print(f"正在抓取: {game['name']}...")
        final_list.extend(get_news_list(game))
    
    send_email(final_list, SMTP_CONFIG)
