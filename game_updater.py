import requests
import datetime
import smtplib
import time
from email.mime.text import MIMEText
from email.header import Header

# --- 1. 配置：游戏官号的微博 UID ---
# 获取方式：手机网页版微博进入官号主页，URL里的数字即 UID
GAMES = [
    {"name": "王者荣耀", "uid": "5698024830", "containerid": "1076035698024830"},
    {"name": "和平精英", "uid": "6512318439", "containerid": "1076036512318439"},
    {"name": "无畏契约", "uid": "7490218706", "containerid": "1076037490218706"},
    {"name": "穿越火线", "uid": "1888365260", "containerid": "1076031888365260"},
    {"name": "第五人格", "uid": "6140485607", "containerid": "1076036140485607"},
    {"name": "超自然行动", "uid": "7922246752", "containerid": "1076037922246752"},
]

KEYWORDS = ["更新", "维护", "版本", "公告", "赛季", "停服"]
CHECK_RANGE_HOURS = 48  # 检查过去 48 小时

def get_weibo_news(game):
    results = []
    print(f"🔍 正在检查微博官号: {game['name']}...")
    try:
        # 微博移动端 API
        url = f"https://m.weibo.cn/api/container/getIndex?type=uid&value={game['uid']}&containerid={game['containerid']}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
            'Referer': 'https://m.weibo.cn/'
        }
        
        # 增加重试机制
        response = requests.get(url, headers=headers, timeout=20)
        if response.status_code != 200:
            print(f"   ❌ 请求失败，状态码: {response.status_code}")
            return []

        data = response.json()
        cards = data.get('data', {}).get('cards', [])
        print(f"   ✅ 成功连通！获取到 {len(cards)} 条博文记录")

        now = datetime.datetime.now()
        for card in cards:
            mblog = card.get('mblog')
            if not mblog: continue
            
            # 获取内容
            text = mblog.get('text', '')
            # 获取时间
            created_at = mblog.get('created_at')
            # 获取链接
            bid = mblog.get('bid')
            link = f"https://weibo.com/{game['uid']}/{bid}"

            # 过滤逻辑
            if any(kw in text for kw in KEYWORDS):
                # 微博时间格式比较特殊，简单处理：只要在列表中且含关键词就视为近期动态
                # 因为接口返回的本来就是最新的前10条
                clean_text = "".join(re.findall(r'[\u4e00-\u9fa5]+', text))[:50] # 只取前50个汉字作为摘要
                results.append(f"【{game['name']}】{clean_text}...\n链接: {link}")
                
    except Exception as e:
        print(f"   ❌ 抓取失败: {e}")
        
    return list(set(results))

import re # 别忘了导入正则

def send_email(content_list, smtp):
    if not content_list:
        print("\n📢 结果：微博接口通畅，但过去 48 小时无匹配关键词的博文。")
        return
    
    body = "游戏更新自动监控报告（数据源：微博官号）：\n\n" + "\n\n".join(content_list)
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
        all_news.extend(get_weibo_news(g))
        time.sleep(2) # 稍微停顿，防止被微博识别为攻击
    
    send_email(all_news, conf)
