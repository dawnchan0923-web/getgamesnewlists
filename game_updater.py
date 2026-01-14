import requests
import datetime
import smtplib
import re
import json
from email.mime.text import MIMEText
from email.header import Header

# --- 1. 核心配置 ---
GAMES = [
    {"name": "王者荣耀", "url": "https://pvp.qq.com/web201706/js/newsdata.js"},
    {"name": "和平精英", "url": "https://gp.qq.com/web201908/js/newsdata.js"},
    {"name": "无畏契约", "url": "https://val.qq.com/web202306/js/newsdata.js"},
    {"name": "穿越火线", "url": "https://cf.qq.com/web202004/js/news_data.js"},
]

KEYWORDS = ["更新", "维护", "版本", "公告", "赛季", "停服"]
# 检查范围：设置为过去 10 天，确保测试时有数据
CHECK_RANGE_HOURS = 240 

def get_news(game):
    results = []
    print(f"🔍 正在连接: {game['name']}...")
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        # 强制不使用缓存，获取最新 JS
        r = requests.get(game['url'], headers=headers, timeout=15, verify=False)
        content = r.text

        # 诊断：打印前100个字符看看格式
        print(f"   📊 数据快照: {content[:100]}...")

        # 1. 提取所有标题、时间和链接
        # 腾讯格式通常是 "sTitle":"...", "sIdxTime":"..."
        titles = re.findall(r'sTitle["\']?\s*:\s*["\'](.*?)["\']', content)
        dates = re.findall(r'sIdxTime["\']?\s*:\s*["\'](.*?)["\']', content)
        urls = re.findall(r'(?:sRedirectURL|vLink|sUrl)["\']?\s*:\s*["\'](.*?)["\']', content)
        
        print(f"   ✅ 抓取到 {len(titles)} 条原始记录")

        now = datetime.datetime.now()
        for i in range(len(titles)):
            # --- 关键步骤：处理 Unicode 转义 ---
            # 把 \u66f4\u65b0 这种转成真正的中文
            raw_title = titles[i]
            try:
                clean_title = raw_title.encode('utf-8').decode('unicode_escape')
            except:
                clean_title = raw_title # 如果解析失败就用原样

            raw_date = dates[i] if i < len(dates) else ""
            raw_url = urls[i] if i < len(urls) else ""
            
            if not raw_date: continue
            
            try:
                p_time = datetime.datetime.strptime(raw_date, '%Y-%m-%d %H:%M:%S')
                # 2. 判断时间与关键词
                if (now - p_time).total_seconds() / 3600 < CHECK_RANGE_HOURS:
                    if any(kw in clean_title for kw in KEYWORDS):
                        link = "https:" + raw_url if raw_url.startswith('//') else raw_url
                        results.append(f"【{game['name']}】{clean_title}\n链接: {link}")
            except:
                continue

    except Exception as e:
        print(f"   ❌ 失败: {e}")
        
    return results

def send_email(content_list, smtp):
    if not content_list:
        print("\n📢 诊断结果：数据已抓取，但解码后仍未匹配到关键词。请检查关键词设置。")
        return
    
    body = "游戏更新自动监控报告（测试覆盖10天内容）：\n\n" + "\n\n".join(content_list)
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['From'] = smtp['user']
    msg['To'] = smtp['user']
    msg['Subject'] = Header(f"游戏更新汇总 - {datetime.date.today()}", 'utf-8')

    try:
        s = smtplib.SMTP_SSL(smtp['host'], 465)
        s.login(smtp['user'], smtp['password'])
        s.sendmail(smtp['user'], [smtp['user']], msg.as_string())
        s.quit()
        print("\n🚀 邮件已发送！请查收。")
    except Exception as e:
        print(f"\n❌ 发信失败: {e}")

if __name__ == "__main__":
    import os
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    conf = {
        'host': 'smtp.qq.com',
        'user': os.environ.get('MAIL_USER'),
        'password': os.environ.get('MAIL_PASS')
    }
    
    final_results = []
    for g in GAMES:
        final_results.extend(get_news(g))
    
    send_email(final_results, conf)
