import requests
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
CHECK_RANGE_HOURS = 500  # 检查过去 3 天，确保有测试数据

def get_news_list(game):
    results = []
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(game['url'], timeout=10)
        response.encoding = 'gbk'
        content = response.text
        
        # --- 核心改进：正则表达式提取 ---
        # 腾讯 JS 里的格式通常是：sTitle:"标题", sIdxTime:"时间", sRedirectURL:"链接"
        # 我们用正则直接把这三样东西一对一对抓出来
        titles = re.findall(r'sTitle\s*:\s*"(.*?)"', content)
        times = re.findall(r'sIdxTime\s*:\s*"(.*?)"', content)
        urls = re.findall(r'(?:sRedirectURL|vLink)\s*:\s*"(.*?)"', content)
        
        print(f"  ✅ {game['name']} 发现 {len(titles)} 条候选公告")
        
        now = datetime.datetime.now()
        
        # 将提取到的字段配对
        for i in range(len(titles)):
            title = titles[i]
            date_str = times[i] if i < len(times) else ""
            raw_url = urls[i] if i < len(urls) else ""
            
            if not date_str: continue
            
            # 链接补全
            link = "https:" + raw_url if raw_url.startswith('//') else raw_url
            
            try:
                pub_time = datetime.datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
            except:
                continue

            # 关键词和时间过滤
            if (now - pub_time).total_seconds() / 3600 < CHECK_RANGE_HOURS:
                if any(kw in title for kw in KEYWORDS):
                    results.append(f"【{game['name']}】{title}\n链接: {link}")
                    
    except Exception as e:
        print(f"  ❌ {game['name']} 抓取失败: {e}")
        
    return results

def send_email(content_list, smtp_config):
    if not content_list:
        print("没有检测到新的更新公告。")
        return

    mail_content = "为您汇总以下游戏更新（测试模式 72小时）：\n\n" + "\n\n".join(content_list)
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
        print(f"❌ 邮件发送出错: {e}")

if __name__ == "__main__":
    import os
    SMTP_CONFIG = {
        'host': 'smtp.qq.com',
        'user': os.environ.get('MAIL_USER'),
        'password': os.environ.get('MAIL_PASS'),
        'sender': os.environ.get('MAIL_USER'),
        'receiver': os.environ.get('MAIL_USER')
    }
    
    final_list = []
    for game in GAMES:
        print(f"正在检查: {game['name']}...")
        final_list.extend(get_news_list(game))
    
    send_email(final_list, SMTP_CONFIG)
