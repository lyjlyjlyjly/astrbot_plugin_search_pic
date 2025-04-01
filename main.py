import asyncio
import os
# import urllib
# import urllib.error
# import urllib.request
# import urllib.parse
import mimetypes
from lxml import html
from astrbot.api.all import AstrMessageEvent, Context, Image, Plain, Node
import astrbot.api.event.filter as filter
from astrbot.api.star import register, Star
import aiohttp

@register(
    "astrbot_plugin_search_pic",
    "lyjlyjlyjly",
    r"从 https://saucenao.com/ 搜索图片",
    "v1.1.0",
    "https://github.com/lyjlyjlyjly/astrbot_plugin_search_pic"
)
class Main(Star):
    def __init__(self, context: Context) -> None:
        super().__init__(context)
        self.headers = {
            'User-Agent': r'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
            'cookie': r'cf_clearance=y2kbPKKv9x3DXTEwSteVqPVQ8e27ZFFPPm9RNojjoMY-1743054836-1.2.1.1-hU2rrvp14Y2pKC6CPQlozZy52JKkapg4.9o6fURpHqPODjFBAVzoJq5KwEeli2fblV_ZJsP7I2rs7brczC0nXkFXxoMuSNddlx_kvXNt0n_BR2fx7pQ1KeEu6lBXZIA.nGNPxwCd6jjQJWZjAnzwrWBPV0dCeybKMD9vKUAgzXx6YcV9rSM86DqrCkJBh10TsUL2l8BQ1TUjN.W.jAlIHMvF_HK1cj4liGcA7mCHdmDt53RGDCLDw4h1OSVCRuvbSY3gAacsL59uqAcTSWpmrnDBXM0qCGfH25AtTogDE3cFOU9DaZMDBbzivWhs5CW0qyfmT306LeaK77eG2.qDQTYgxkDCJ1EfJWxJ3XwJSEpJaocsyWHtIcqkkB3jtVOArgeWrD5JqyCnlgq._M1jalgJShfidvUU53Vwo.4AFf0; user=147390; auth=d5e61417a0c0e0202cc1cfa9137d2a767b6fd54d; _gat_gtag_UA_412819_5=1; __utma=4212273.167531699.1743002465.1743054955.1743054955.1; __utmc=4212273; __utmz=4212273.1743054955.1.1.utmcsr=(direct)|utmccn=(direct)|utmcmd=(none); __utmt=1; __utmb=4212273.1.10.1743054955; _ga_LK5LRE77R3=GS1.1.1743053390.6.1.1743054964.0.0.0; _ga=GA1.2.167531699.1743002465',
        }
        self.upload_url = r'https://saucenao.com/search.php'
        self.source_db = r"""从 https://saucenao.com/ 搜索图片，功能是以图搜图

搜索范围如下：
1. H-Magazines
2. H-Game CG
3. DoujinshiDB
4. pixiv Images
5. Nico Nico Seiga
6. Danbooru
7. drawr Images
8. Nijie Images
9. Yande.re
10. Shutterstock
11. FAKKU
12. H-Misc (nH)
13. 2D-Market
14. MediBang
15. Anime
16. H-Anime
17. Movies
18. Shows
19. Gelbooru
20. Konachan
21. Sankaku Channel
22. Anime-Pictures.net
23. e621.net
24. Idol Complex
25. bcy.net Illust
26. bcy.net Cosplay
27. PortalGraphics.net
28. deviantArt
29. Pawoo.net
30. Madokami (Manga)
31. MangaDex
32. H-Misc (eH)
33. ArtStation
34. FurAffinity
35. Twitter
36. Furry Network
37. Kemono
38. Skeb
        """

    async def get_table_info(self, tree) -> list:
        result_image_src = None
        img = tree.xpath(r'.//img')
        if len(img) > 0:
            img = img[0]
            img_src_tag = ['data-src2', 'data-src', 'src']
            # img_src_tag[:2] = img_src_tag[1::-1]

            # R18图标清图地址在 data-src2, 缩略图在 data-src, src会根据网页情况选择 data-src 还是 data-src2
            # 非R18图地址在src
            # 另外当相似度过低时，平台会将src指向一个极小的.gif，以制造隐藏的效果，不是有效url格式
            # 以上规律有较小可能出现意外
            # 如果想要R18返回缩略图，可以给 data-src2 和 data-src 换位置

            for tag in img_src_tag:
                if img.get(tag):
                    result_image_src = img.get(tag)
                    break

        result_similarity_info = tree.xpath(
            r'./td[@class="resulttablecontent"]/div[@class="resultmatchinfo"]/div[@class="resultsimilarityinfo"]/text()')[0]
        result_content_column = tree.xpath(r'./td[@class="resulttablecontent"]/div[@class="resultcontent"]/div')

        grouped_text = ["similarity: " + result_similarity_info]
        for ele in result_content_column:
            div_text = ele.xpath(r'.//text()')
            cleaned_text = [text.strip() for text in div_text if text.strip()]
            i = 0
            while i < len(cleaned_text):
                grouped_text.append(cleaned_text[i])
                if i + 1 < len(cleaned_text) and cleaned_text[i].endswith(":"):
                    grouped_text[-1] += " " + cleaned_text[i + 1]
                    i += 1
                i += 1
        return [result_image_src, "\n".join(grouped_text)]

    async def upload_image_and_search(self, img_obj, url):
        max_retries = 3
        retries = 0
        file_path = None
        while retries < max_retries:
            try:
                file_path = await img_obj.convert_to_file_path()
                if file_path:
                    break
            except Exception as e:
                retries += 1
                if retries == max_retries:
                    raise e
                await asyncio.sleep(1)

        if not file_path:
            raise ValueError('No file found')

        # 上传图片
        retries = 0
        while retries < max_retries:
            try:
                async with aiohttp.ClientSession() as session:
                    file_name = os.path.basename(file_path)
                    content_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
                    with open(file_path, 'rb') as file:
                        file_content = file.read()
                    data = aiohttp.FormData()
                    data.add_field('file', file_content, filename=file_name, content_type=content_type)

                    async with session.post(url, data=data, headers=self.headers) as response:
                        response_content = await response.text()
                        return response_content
            except aiohttp.ClientError as e:
                retries += 1
                if retries == max_retries:
                    raise e
                await asyncio.sleep(1)

    @filter.command("搜图", alias={"soutu"})
    async def handle_search_pic(self, message: AstrMessageEvent):
        message_obj = message.message_obj
        upload_url = self.upload_url
        image_obj = None
        for i in message_obj.message:
            if isinstance(i, Image):
                image_obj = i
                break
        if image_obj is None:
            yield message.plain_result("没有发送图片")
            return

        try:
            html_text = await self.upload_image_and_search(image_obj, upload_url)
            if html_text is None:
                raise ValueError("未获取到有效的HTML内容")
            tree = html.fromstring(html_text)
            # 一个resulttable就是一条查找记录
            result_table_xpath = r'//div[@id="middle"]//table[@class="resulttable"]'
            elements = tree.xpath(result_table_xpath)
            if len(elements) == 0:
                yield message.plain_result("未找到搜索结果")
                return

            content = []
            for ele in elements[:min(3, len(elements))]:  # 枚举前三个记录
                src, text = await self.get_table_info(ele.xpath(r".//tr[1]")[0])

                async def check_src_exists(_src):
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.head(_src, headers=self.headers) as response:
                                return response.status
                    except aiohttp.ClientError:
                        return None

                if src is None:
                    content.extend([Plain(text), Plain("\n"), Plain(f"该图片src不存在"), Plain("\n\n")])
                    continue
                exit_code = await check_src_exists(src)
                if exit_code == 200:
                    content.extend([Plain(text), Plain("\n"), Image.fromURL(src), Plain("\n\n")])
                else:
                    content.extend([Plain(text), Plain("\n"), Plain(f"该图片资源不存在，状态码: {exit_code}"), Plain("\n\n")])

            yield message.chain_result([Node(
                uin=3824609399,
                name="1145141919810",
                content=content
            )])
        except Exception as e:
            raise e

    @filter.command("搜图来源")
    async def print_query_range(self, message: AstrMessageEvent):
        text = self.source_db
        # 发送纯文本就用上面的，发送转发消息就用下面的
        # yield message.plain_result(text)
        yield message.chain_result([Node(
            uin=3824609399,
            name="1145141919810",
            content=[
                Plain(text)
            ]
        )])

    @filter.command("搜图帮助")
    async def print_help(self, message: AstrMessageEvent):
        help_text = r"""插件 astrbot_plugin_search_pic 帮助信息：

作者: lyjlyjlyjly
版本: v1.0.0

指令列表：
- 搜图
    别名 “soutu”
    发出消息后在 30s 内发送图片进行搜图
    搜索结果仅供参考，有概率出现网站上存在但是搜不到的问题
    由于QQ有审查机制，R18的图在群里可能发不出来，所以搜R18建议私聊
    图片不要旋转
- 搜图来源
    查询搜索范围
- 搜图帮助
    获取帮助信息

如果是在群聊消息，需要在前面加上astrbot的唤醒前缀
"""
        # yield message.plain_result(help_text)
        yield message.chain_result([Node(
            uin=3824609399,
            name="1145141919810",
            content=[
                Plain(help_text)
            ]
        )])