import requests
import datetime
import smtplib
import re
from email.mime.text import MIMEText
from email.header import Header

# --- 1. 核心配置：直接连接各游戏主官网 (DNS解析最稳) ---
GAMES = [
    {"name": "王者荣耀", "url": "https://pvp.qq.com/web201706/js/newsdata.js", "enc": "gbk"},
    {"name": "和平精英", "url": "https://gp.qq.com/web201908/js/newsdata.js", "enc": "gbk"},
    {"name": "无畏契约", "url": "https://val.qq.com/web202306/js/newsdata.js", "enc": "gbk"},
    {"name": "穿越火线", "url": "https://cf.qq.com/web202004/js/news_data.js", "enc": "gbk"},
    # 第五人格改用网易官方移动端通用接口
    {"name": "第五人格", "url": "https://id5.163.com/news/index.html", "enc": "utf-8", "type": "html"},
]

KEYWORDS = ["更新", "维护", "版本", "公告", "Season", "赛季", "停服"]
# 设置为 720 小时（30天），确保在测试阶段一定能抓到东西，确认“发信功能”正常
CHECK_RANGE_HOURS = 720 

def get_news(game):
    results = []
    print(f"🔍 正在连接: {game['name']}...")
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        # 增加 verify=False 防止 SSL 证书解析问题导致的 DNS 波动
        r = requests.get(game['url'], headers=headers, timeout=20, verify=False)
        r.encoding = game['enc']
        content = r.text

        if not content:
            print("   ⚠️ 返回内容为空")
            return []

        # 暴力提取模式：不再尝试转JSON，直接用正则抠出所有的标题和日期
        # 腾讯系 JS 逻辑
        if ".js" in game['url']:
            # 匹配 sTitle:"..." 或 sTitle:'...'
            titles = re.findall(r'sTitle\s*:\s*["\'](.*?)["\']', content)
            dates = re.findall(r'sIdxTime\s*:\s*["\'](.*?)["\']', content)
            urls = re.findall(r'(?:sRedirectURL|vLink|sUrl)\s*:\s*["\'](.*?)["\']', content)
            
            print(f"   ✅ 抓取到 {len(titles)} 条潜在公告")
            
            now = datetime.datetime.now()
            for i in range(min(len(titles), 20)): # 只看最新的20条
                t, d = titles[i], dates[i] if i < len(dates) else ""
                u = urls[i] if i < len(urls) else ""
                
                if not d: continue
                try:
                    p_time = datetime.datetime.strptime(d, '%Y-%m-%d %H:%M:%S')
                    if (now - p_time).total_seconds() / 3600 < CHECK_RANGE_HOURS:
                        if any(kw in t for kw in KEYWORDS):
                            link = "https:" + u if u.startswith('//') else u
                            results.append(f"【{game['name']}】{t}\n链接: {link}")
                except: continue

        # 针对第五人格等 HTML 页面做简单处理
        elif game.get("type") == "html":
            # 简单抠取 HTML 里的标题
            items = re.findall(r'<a.*?>(.*?)更新(.*?)</a>', content)
            if items:
                results.append(f"【{game['name']}】发现更新相关公告，请前往官网查看\n链接: {game['url']}")

    except Exception as e:
        print(f"   ❌ 访问失败: {e}")
        
    return results

def send_email(content_list, smtp):
    if not content_list:
        print("\n📢 结果：由于 DNS 或屏蔽原因，依然未能获取有效数据。")
        return
    
    body = "游戏更新自动监控报告（测试模式-30天范围）：\n\n" + "\n\n".join(content_list)
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
    
    final = []
    for g in GAMES:
        final.extend(get_news(g))
    
    send_email(final, conf)
