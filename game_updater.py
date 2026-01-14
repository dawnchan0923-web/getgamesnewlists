import requests
import datetime
import smtplib
import json
from email.mime.text import MIMEText
from email.header import Header

# --- 1. 核心配置：腾讯官方内容中心 API ---
# 这里使用的是腾讯 wmp (Web Management Platform) 接口，是目前最稳的源
GAMES = [
    {"name": "王者荣耀", "id": "533", "biz": "pvp"},       # 533是公告类目
    {"name": "和平精英", "id": "1894", "biz": "gp"},      # 1894是公告类目
    {"name": "无畏契约", "id": "1141", "biz": "val"},     # 1141是公告类目
    {"name": "穿越火线", "id": "339", "biz": "cf"},       # 339是公告类目
]

KEYWORDS = ["更新", "维护", "版本", "公告", "Season", "赛季", "停服"]
CHECK_RANGE_HOURS = 72  # 检查过去3天，确保能抓到东西

def get_tencent_official_news(game):
    results = []
    # 腾讯官方移动端通用接口
    url = "https://apps.game.qq.com/wmp/v3c/cgi/news/list"
    params = {
        "p0": game['biz'],
        "id": game['id'],
        "type": "iTag",
        "order": "sIdxTime",
        "r0": "json",
        "p1": "1" # 第一页
    }
    
    print(f"🔍 正在检查: {game['name']} (Biz: {game['biz']})")
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Mobile/15E148 Safari/604.1',
            'Referer': f'https://{game["biz"]}.qq.com/'
        }
        response = requests.get(url, params=params, headers=headers, timeout=10)
        
        # 调试：打印状态和前100个字符
        if response.status_code != 200:
            print(f"   ❌ 请求失败，状态码: {response.status_code}")
            return []

        # 腾讯这个接口返回的内容有时候带些奇怪的字符，进行清洗
        raw_text = response.text.strip()
        data = json.loads(raw_text)
        
        # 验证抓取是否成功
        if data.get('ret') != 0:
            print(f"   ⚠️ 接口返回异常: {data.get('msg')}")
            return []

        news_list = data.get('msg', {}).get('result', [])
        print(f"   ✅ 成功连接！抓取到 {len(news_list)} 条原始公告")

        now = datetime.datetime.now()
        
        # 验证抓取到的信息是什么样的（打印前1条作为示例）
        if news_list:
            example = news_list[0]
            print(f"   📊 数据样例 -> 标题: {example.get('sTitle')[:15]}... 时间: {example.get('sIdxTime')}")

        for item in news_list:
            title = item.get('sTitle', '')
            date_str = item.get('sIdxTime', '')
            # 腾讯链接拼接
            news_id = item.get('iNewsId')
            link = f"https://{game['biz']}.qq.com/webplat/info/news_version3/139/533/m534/index.shtml?id={news_id}"

            if not date_str: continue
            
            pub_time = datetime.datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
            
            # 检查时间 + 关键词
            if (now - pub_time).total_seconds() / 3600 < CHECK_RANGE_HOURS:
                if any(kw in title for kw in KEYWORDS):
                    results.append(f"【{game['name']}】{title}\n链接: {link}")
                    
    except Exception as e:
        print(f"   ❌ 解析出错: {e}")
        
    return results

def send_email(content_list, smtp_config):
    if not content_list:
        print("\n📢 验证报告：接口畅通，但过去72小时内无匹配关键词的更新公告。")
        return

    mail_content = "为您汇总以下游戏更新公告：\n\n" + "\n\n".join(content_list)
    msg = MIMEText(mail_content, 'plain', 'utf-8')
    msg['From'] = smtp_config['user']
    msg['To'] = smtp_config['user']
    msg['Subject'] = Header(f"游戏更新汇总测试 - {datetime.date.today()}", 'utf-8')

    try:
        server = smtplib.SMTP_SSL(smtp_config['host'], 465)
        server.login(smtp_config['user'], smtp_config['password'])
        server.sendmail(smtp_config['user'], [smtp_config['user']], msg.as_string())
        server.quit()
        print("\n🚀 邮件发送成功！请检查收件箱。")
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
        all_news.extend(get_tencent_official_news(g))
    
    send_email(all_news, conf)
