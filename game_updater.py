import feedparser
import datetime
import smtplib
import urllib.parse
from email.mime.text import MIMEText
from email.header import Header

# --- 1. 配置：需要监控的游戏列表 ---
GAMES = ["王者荣耀", "和平精英", "无畏契约", "穿越火线", "第五人格", "超自然行动"]

# 关键词组合
KEYWORDS = ["更新", "维护", "公告", "版本", "赛季"]
CHECK_RANGE_HOURS = 24  # 检查过去 24 小时

def get_google_news_updates():
    results = []
    now = datetime.datetime.now(datetime.timezone.utc)
    
    for game in GAMES:
        print(f"🔍 正在通过 Google News 检索: {game}...")
        
        # 修正：先在外部处理好关键词字符串，避免 f-string 语法限制
        # 构造类似: "更新" OR "维护" OR "公告"
        keyword_query = ' OR '.join(['"{}"'.format(kw) for kw in KEYWORDS])
        # 最终搜索词: 王者荣耀 ("更新" OR "维护" OR "公告")
        query = '{} ({})'.format(game, keyword_query)
        
        encoded_query = urllib.parse.quote(query)
        
        # Google News RSS 接口
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
        
        try:
            feed = feedparser.parse(rss_url)
            print(f"   ✅ 检索到 {len(feed.entries)} 条相关信息")
            
            count = 0
            for entry in feed.entries:
                # 解析发布时间
                if not hasattr(entry, 'published_parsed') or not entry.published_parsed:
                    continue
                    
                pub_time = datetime.datetime(*entry.published_parsed[:6], tzinfo=datetime.timezone.utc)
                
                # 时间筛选：过去 24 小时
                if (now - pub_time).total_seconds() / 3600 < CHECK_RANGE_HOURS:
                    # 确保标题里包含游戏名
                    if game in entry.title:
                        # 格式化输出
                        source = entry.source.get('title', '未知来源')
                        results.append(f"【{game}】{entry.title}\n来源: {source}\n链接: {entry.link}")
                        count += 1
            print(f"   ✨ 筛选出 {count} 条最新动态")
        except Exception as e:
            print(f"   ❌ 检索失败: {e}")
            
    return list(set(results)) # 去重

def send_email(content_list, smtp):
    if not content_list:
        print("\n📢 结果：今日暂无最新的游戏更新公告。")
        return
    
    # 构造邮件内容
    today = datetime.date.today()
    body = f"您关注的游戏更新汇总（{today}）：\n\n" + "\n\n".join(content_list)
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['From'] = smtp['user']
    msg['To'] = smtp['user']
    msg['Subject'] = Header(f"游戏更新汇总 - {today}", 'utf-8')

    print(f"📧 正在尝试通过 {smtp['host']} 发送邮件...")
    
    try:
        # 方案 A：使用 465 端口和 SSL
        server = smtplib.SMTP_SSL(smtp['host'], 465, timeout=30)
        server.set_debuglevel(1) # 开启调试模式，如果失败能看到更详细原因
        server.ehlo() 
        server.login(smtp['user'], smtp['password'])
        server.sendmail(smtp['user'], [smtp['user']], msg.as_string())
        server.quit()
        print("\n🚀 邮件已成功发送！")
    except Exception as e:
        print(f"\n⚠️ SSL 模式发送失败: {e}，正在尝试 TLS 模式...")
        try:
            # 方案 B：如果 A 失败，尝试 587 端口和 TLS
            server = smtplib.SMTP(smtp['host'], 587, timeout=30)
            server.ehlo()
            server.starttls() # 启动加密
            server.login(smtp['user'], smtp['password'])
            server.sendmail(smtp['user'], [smtp['user']], msg.as_string())
            server.quit()
            print("\n🚀 邮件通过 TLS 模式发送成功！")
        except Exception as e2:
            print(f"\n❌ 两种模式均发送失败。最终错误: {e2}")
            print("请检查：1. 授权码是否正确；2. QQ邮箱设置里是否开启了SMTP服务。")

if __name__ == "__main__":
    import os
    conf = {
        'host': 'smtp.qq.com',
        'user': os.environ.get('MAIL_USER'),
        'password': os.environ.get('MAIL_PASS')
    }
    
    updates = get_google_news_updates()
    send_email(updates, conf)
