import asyncio
import os
from datetime import datetime, timezone, timedelta
from playwright.async_api import async_playwright
from feedgen.feed import FeedGenerator

# 目标网站配置
URL = "https://www.techflowpost.com/zh-CN"
RSS_FILE = "feed.xml"

async def run():
    async with async_playwright() as p:
        # 1. 启动浏览器 (Headless模式)
        browser = await p.chromium.launch(headless=True)
        # 设置 user-agent 防止被识别为机器人
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()

        print(f"正在访问: {URL}")
        try:
            # 访问网页，等待网络空闲（意味着内容加载完毕）
            await page.goto(URL, wait_until="networkidle", timeout=60000)

            # 模拟滚动到底部，触发懒加载（防止只有首屏数据）
            await page.evaluate("window.scrollBy(0, 1000)")
            await asyncio.sleep(2) # 等待滚动后的加载

            # 2. 核心抓取逻辑 (针对你截图的红色区域)
            # 策略：寻找所有指向 /article/ 的链接，且文本长度大于5（排除图标或空链接）
            articles = await page.evaluate('''() => {
                // 获取所有包含 /article/ 的链接标签
                const anchors = Array.from(document.querySelectorAll('a[href*="/article/"]'));

                const results = [];
                const seenLinks = new Set();

                anchors.forEach(a => {
                    const title = a.innerText.trim();
                    const href = a.href;

                    // 过滤条件：标题不能太短，且链接未重复
                    if (title.length > 5 && !seenLinks.has(href)) {
                        // 尝试抓取简介：通常在标题链接的父级元素的下一个兄弟元素，或者同级div中
                        // 这是一个“尽力而为”的抓取，如果抓不到就为空
                        let desc = "";
                        try {
                            // 简单的尝试：获取链接父级周围的文本作为简介
                            // 根据DeepTide结构，简介通常在标题下方
                            const parentText = a.parentElement ? a.parentElement.innerText : "";
                            if(parentText.length > title.length + 10) {
                                desc = parentText.replace(title, "").substring(0, 200) + "...";
                            }
                        } catch(e) {}

                        results.push({
                            title: title,
                            link: href,
                            description: desc
                        });
                        seenLinks.add(href);
                    }
                });
                return results;
            }''')

            print(f"成功抓取到 {len(articles)} 篇文章")

            # 3. 生成 RSS 文件
            fg = FeedGenerator()
            fg.id(URL)
            fg.title('深潮 TechFlow - 精选新闻')
            fg.author({'name': 'RSS Bot', 'email': 'bot@example.com'})
            fg.link(href=URL, rel='alternate')
            fg.subtitle('TechFlow Auto-Generated Feed')
            fg.language('zh-CN')

            # 北京时间 (UTC+8)
            tz = timezone(timedelta(hours=8))

            # 添加文章到 RSS (取前 20 条)
            for art in articles[:20]:
                fe = fg.add_entry()
                fe.id(art['link'])
                fe.title(art['title'])
                fe.link(href=art['link'])
                fe.description(art['description'])
                # 因为网页上是“15分钟前”这种相对时间，解析复杂，这里直接用抓取时间作为发布时间
                fe.published(datetime.now(timezone.utc))

            fg.rss_file(RSS_FILE)
            print("RSS 文件生成成功！")

        except Exception as e:
            print(f"发生错误: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
