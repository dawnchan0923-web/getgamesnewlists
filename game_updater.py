import requests
import datetime
import smtplib
import json
from email.mime.text import MIMEText
from email.header import Header

# --- 1. 配置：腾讯最新的内容分发中心 (CMS v3) ---
# 这里的 service_type 是腾讯各游戏的内部识别码
GAMES = [
    {"name": "王者荣耀", "code": "pvp", "type": "tencent"},
    {"name": "和平精英", "code": "gp", "type": "tencent"},
    {"name": "无畏契约", "code": "val", "type": "tencent"},
    {"name": "穿越火线", "code": "cf", "type": "tencent"},
    # 网易游戏通过 TapTap 稳定接口抓取
    {"name": "第五人格", "code": "35915", "type": "taptap"},
    {"name": "超自然行动", "code": "380482", "type": "taptap"},
]

KEYWORDS = ["更新", "维护", "版本", "公告", "Season", "赛季", "停服"]
CHECK_RANGE_HOURS = 168  # 强制大范围检查 168 小时（7天），确保一定有内容

def fetch_tencent(game):
    results = []
    # 腾讯 CMS v3 接口，这是目前官网、社区、App 通用的最新接口
    url = f"https://content.game.qq.com/c/w/get_news_list?service_type={game['code']}&type=0&page_size=10&page_index=1"
    
    print(f"🔍 正在抓取腾讯: {game['name']}...")
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15',
            'Referer': f'https://{game["code"]}.qq.com/'
        }
        resp = requests.get(url, headers=headers, timeout=10)
        data = resp.json()
        
        # 腾讯这个接口的状态码在 data['status'] 里
        news_list = data.get('data', {}).get('list', [])
        print(f"   ✅ 连通成功，获取到 {len(news_list)} 条记录")

        now = datetime.datetime.now()
        for item in news_list:
            title = item.get('sTitle', '')
            # 兼容不同字段的时间戳
            date_str = item.get('sIdxTime') or item.get('sCreatedTime')
            # 链接跳转
            link = f"https://{game['code']}.qq.com/webplat/info/news_version3/139/533/m534/index.shtml?id={item.get('iNewsId')}"

            if not date_str: continue
            pub_time = datetime.datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
            
            if (now - pub_time).total_seconds() / 3600 < CHECK_RANGE_HOURS:
                if any(kw in title for kw in KEYWORDS):
                    results.append(f"【{game['name']}】{title}\n链接: {link}")
    except Exception as e:
        print(f"   ❌ 抓取失败: {e}")
    return results

def fetch_taptap(game):
    results = []
    # TapTap 的官方社区 API
    url = f"https://www.taptap.cn/web-api/tds-forum/v1/categories/official/topics?app_id={game['code']}&limit=10"
    print(f"🔍 正在抓取 TapTap: {game['name']}...")
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers, timeout=10)
        items = resp.json().get('data', {}).get('list', [])
        print(f"   ✅ 获取到 {len(items)} 条记录")

        for item in items:
            title = item.get('topic', {}).get('title', '')
            link = f"https://www.taptap.cn/moment/{item.get('topic', {}).get('id')}"
            if any(kw in title for kw in KEYWORDS):
                results.append(f"【{game['name']}】{title}\n链接: {link}")
    except Exception as e:
        print(f"   ❌ 抓取失败: {e}")
    return results

def send_email(content_list, smtp):
    if not content_list:
        print("\n📢 结果：接口通畅，但最近7天无更新关键词公告。")
        return
    
    body = "游戏更新汇总诊断报告（覆盖范围7天）：\n\n" + "\n\n".join(content_list)
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['From'] = smtp['user']
    msg['To'] = smtp['user']
    msg['Subject'] = Header(f"游戏更新汇总 - {datetime.date.today()}", 'utf-8')

    try:
        s = smtplib.SMTP_SSL(smtp['host'], 465)
        s.login(smtp['user'], smtp['password'])
        s.sendmail(smtp['user'], [smtp['user']], msg.as_string())
        s.quit()
        print("\n🚀 邮件已成功寄出！")
    except Exception as e:
        print(f"\n❌ 发信失败: {e}")

if __name__ == "__main__":
    import os
    conf = {
        'host': 'smtp.qq.com',
        'user': os.environ.get('MAIL_USER'),
        'password': os.environ.get('MAIL_PASS')
    }
    
    final_list = []
    for g in GAMES:
        if g['type'] == 'tencent':
            final_list.extend(fetch_tencent(g))
        else:
            final_list.extend(fetch_taptap(g))
            
    send_email(final_list, conf)
