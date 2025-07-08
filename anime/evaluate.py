import requests
from bs4 import BeautifulSoup
import re
import os
import time
import random
import json
from datetime import datetime
import colorgram
from PIL import Image

# ==================== 配置区域 ====================

# 1. Bangumi 用户ID
USER_ID = '950475'

# 2. 筛选条件 (核心配置)
FILTER_AIR_YEAR_MONTH = '2025-04' # 格式: 'YYYY-MM'

# 3. Headers 
SCRAPE_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}
API_HEADERS = {
    'User-Agent': 'MyAnimePosterDownloader/1.1 (https://github.com/ienone)'
}

# 4. 需要爬取的状态
STATUSES = ['collect', 'on_hold', 'dropped']

# 5. 代理设置 (如果不需要代理，请将 PROXY 设置为 None)
PROXY = {
    'http': 'http://127.0.0.1:7890',
    'https': 'http://127.0.0.1:7890'
}
# PROXY = None 

# ==================== 工具函数 ====================

def setup_directory(dir_name):
    if not os.path.exists(dir_name):
        os.makedirs(dir_name)
        print(f"✅ 已创建目录: {dir_name}")

def sanitize_filename(filename):
    return re.sub(r'[\\/*?:"<>|]', "", filename).strip()

def parse_date(date_str):
    if not date_str or date_str == "Unknown":
        return None
    date_str = date_str.replace('年', '-').replace('月', '-').replace('日', '')
    formats = ['%Y-%m-%d', '%Y-%m']
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    try:
        return datetime.strptime(date_str.strip(), '%Y')
    except ValueError:
        pass
    return None

def extract_air_date(info_text):
    info_text = info_text.strip()
    patterns = [
        r'(\d{4}[年/-]\d{1,2}[月/-]\d{1,2}日?)',
        r'(\d{4}年\d{1,2}月)',
        r'(\d{4}-\d{2}-\d{2})',
        r'(\d{4}-\d{2})',
        r'(\d{4}年)',
        r'(\d{4})'
    ]
    for pattern in patterns:
        match = re.search(pattern, info_text)
        if match:
            return match.group(1).replace('/', '-')
    return "Unknown"

# def extract_dominant_rgb(image_path):
#     """优化版主色提取"""
#     if not os.path.exists(image_path):
#         return None
    
#     try:
#         # 先缩小图片尺寸再提取颜色
#         img = Image.open(image_path)
        
#         # 转换为RGB如果还不是
#         if img.mode != 'RGB':
#             img = img.convert('RGB')
            
#         # 直接采样部分像素而不是分析全部
#         pixels = list(img.getdata())
#         sample_size = min(500, len(pixels))
#         sampled_pixels = random.sample(pixels, sample_size)
        
#         # 简单的颜色聚类
#         from collections import defaultdict
#         color_groups = defaultdict(list)
#         for r, g, b in sampled_pixels:
#             # 将颜色分组到较大的区间
#             key = (r//16, g//16, b//16)
#             color_groups[key].append((r, g, b))
            
#         # 找出最大的颜色组
#         largest_group = max(color_groups.values(), key=len)
#         avg_color = tuple(int(sum(x)/len(x)) for x in zip(*largest_group))
        
#         return avg_color
        
#     except Exception as e:
#         print(f"⚠️ 提取颜色失败: {e}")
#         return None

def extract_dominant_rgb(image_path):
    """从图片提取一个美观的主色调，返回RGB元组 (r, g, b)"""
    if not image_path or not os.path.exists(image_path):
        return None
    try:
        colors = colorgram.extract(image_path, 12)
        best_color = None
        max_score = -1
        for color in colors:
            hsl = color.hsl
            if hsl.s < 0.1 or hsl.l < 0.05 or hsl.l > 0.95:
                continue
            score = hsl.s - abs(hsl.l - 0.5)
            if score > max_score:
                max_score = score
                best_color = color.rgb
        if best_color:
            return best_color
        else:
            for color in sorted(colors, key=lambda c: c.proportion, reverse=True):
                if color.rgb.r > 10 and color.rgb.g > 10 and color.rgb.b > 10 and \
                   color.rgb.r < 245 and color.rgb.g < 245 and color.rgb.b < 245:
                    return color.rgb
        return colors[0].rgb
    except Exception as e:
        print(f"    ⚠️ 提取颜色失败 ({os.path.basename(image_path)}): {e}。")
        return None

def is_color_light(rgb_tuple):
    """根据W3C亮度公式判断颜色是浅色还是深色"""
    if not rgb_tuple:
        return False
    r, g, b = rgb_tuple
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return luminance > 0.5 # 亮度大于0.5认为是浅色

# ==================== 海报下载函数 ====================

def download_poster(subject_id, title, poster_dir):
    api_url = f'https://api.bgm.tv/v0/subjects/{subject_id}/image?type=large'
    safe_title = sanitize_filename(title)
    
    try:
        response = requests.get(api_url, headers=API_HEADERS, proxies=PROXY, timeout=15, allow_redirects=True)
        response.raise_for_status()

        content_type = response.headers.get('Content-Type')
        extension = 'jpg'
        if content_type:
            if 'png' in content_type: extension = 'png'
            elif 'webp' in content_type: extension = 'webp'
            
        filename = f"{safe_title}_{subject_id}.{extension}"
        filepath = os.path.join(poster_dir, filename)
        
        with open(filepath, 'wb') as f:
            f.write(response.content)
        
        if extension == 'webp':
            try:
                img = Image.open(filepath).convert("RGB")
                new_filepath = os.path.join(poster_dir, f"{safe_title}_{subject_id}.jpg")
                img.save(new_filepath, "jpeg")
                os.remove(filepath)
                print(f"    🖼️ 海报已下载并转换为JPG: {os.path.basename(new_filepath)}")
                return new_filepath
            except Exception as e:
                print(f"    ⚠️ WebP转换失败: {e}。")

        print(f"    🖼️ 海报已下载: {filename}")
        return filepath

    except requests.exceptions.RequestException as e:
        print(f"    ❌ 下载海报失败 (ID: {subject_id}): {e}")
        return None

# ==================== 页面解析函数 (保持不变) ====================
def parse_page(soup, status):
    item_list_ul = soup.find('ul', id='browserItemList')
    if not item_list_ul: return []
    items = item_list_ul.find_all('li', class_='item')
    results = []
    for item in items:
        try:
            h3 = item.find('h3')
            a_tag = h3.find('a', class_='l')
            title, link = a_tag.text.strip(), "https://bgm.tv" + a_tag['href']
            subject_id = re.search(r'/subject/(\d+)', link).group(1)
            info_tip_text = item.find('p', class_='info tip').text.strip() if item.find('p', class_='info tip') else ""
            air_date = extract_air_date(info_tip_text)
            collect_info = item.find('p', class_='collectInfo')
            rating, rating_date = 0, None
            if collect_info:
                date_tag = collect_info.find('span', class_='tip_j')
                if date_tag: rating_date = date_tag.text.strip()
                stars_tag = collect_info.find('span', class_=re.compile(r'stars\d+'))
                if stars_tag:
                    star_class = next((c for c in stars_tag.get('class', []) if c.startswith('stars')), None)
                    if star_class:
                        match = re.search(r'stars(\d+)', star_class)
                        if match: rating = int(match.group(1))
            comment_box = item.find('div', id='comment_box')
            comment = comment_box.find('div', class_='text').text.strip() if comment_box and comment_box.find('div', class_='text') else None
            results.append({'subject_id': subject_id, 'title': title, 'link': link, 'air_date': air_date, 'rating_date': rating_date, 'rating_score': rating, 'comment': comment, 'status': status, 'poster_path': None})
        except Exception as e:
            print(f"❌ 解析某个条目时出错，已跳过: {e}")
    return results

# ==================== Markdown 生成函数====================

def generate_markdown_file(anime_list, output_dir):
    md_path = os.path.join(output_dir, "index.md")
    
    # 1. Front Matter (无变化)
    year, month = FILTER_AIR_YEAR_MONTH.split('-')
    title = f"{year}年{month}月新番观后简评"
    today = datetime.now().strftime('%Y-%m-%d')
    
    front_matter = f"""---
title: "{title}"
date: {today}
description: "记录{year}年{month}月新番个人简评。"
slug: "anime-review-{FILTER_AIR_YEAR_MONTH}"
tags: ["番剧", "季度总结", "{year}年"]
series: ["季度新番"]
series_order: 1
showTableOfContents: true
---
"""

    # 2. 概述
    overview = """
{{< lead >}}
在这里写下你对本季新番的总体概述和看法...
{{< /lead >}}

---
"""
    
    # 3. 生成卡片
    cards_content = ""
    for item in anime_list:
        if not item['poster_path']: continue

        cards_content += f"\n### {item['title']}\n\n"
        
        poster_filename = os.path.basename(item['poster_path'])
        poster_md_path = f"./bgm_posters/{poster_filename}"
        
        dominant_rgb = extract_dominant_rgb(item['poster_path'])
        
        if dominant_rgb:
            background_style = f"background-color: rgba({dominant_rgb.r}, {dominant_rgb.g}, {dominant_rgb.b}, 0.75);"
            # background_style = f"background-color: rgba({dominant_rgb[0]}, {dominant_rgb[1]}, {dominant_rgb[2]}, 0.75);"
            is_light = is_color_light(dominant_rgb)
            link_class = 'text-gray-800 hover:text-sky-600' if is_light else 'text-white hover:text-sky-300'
            prose_class = 'prose' if is_light else 'prose prose-invert'
            border_class = 'border-gray-400/50' if is_light else 'border-gray-500/50'
            comment_bg_class = 'bg-black/10' if is_light else 'bg-white/10'
        else:
            background_style = "background-color: #374151;"
            link_class = 'text-white hover:text-sky-300'
            prose_class = 'prose prose-invert'
            border_class = 'border-gray-500/50'
            comment_bg_class = 'bg-white/10'

        status_text = {'collect': '看过', 'on_hold': '搁置', 'dropped': '弃番'}.get(item['status'], '未知')
        rating_text = f"<strong>{item['rating_score']}/10</strong>" if item['rating_score'] > 0 else "未评分"
        comment = item['comment'].replace('\r\n', '<br>').replace('\n', '<br>') if item['comment'] else "暂无短评。"
        card_html = f"""
<div class="mb-8 p-4 border rounded-lg dark:border-neutral-700" style="{background_style}">
    <div class="flex flex-col sm:flex-row gap-4">
        <!-- 海报区域 -->
        <div class="w-full sm:w-1/4 flex-shrink-0 flex justify-center items-start">
            <img src="{poster_md_path}" alt="{item['title']} 海报" 
                class="rounded-md object-cover w-full max-w-xs mx-auto shadow-md">
        </div>
        <!-- 内容区域 -->
        <div class="w-full sm:w-3/4 {prose_class}">
            <!-- 标题区域 -->
            <div class="pb-3 border-b {border_class}">
                <h4 class="text-2xl font-bold">
                    <a href="{item['link']}" target="_blank" rel="noopener noreferrer" class="{link_class} transition-colors duration-200">
                        {item['title']}
                    </a>
                </h4>
                <div class="flex items-center mt-2 gap-4">
                    <div class="font-semibold flex items-center">
                        <span class="text-amber-400 flex items-center">{{{{< icon "star" >}}}}</span>
                        <span class="ml-1.5">{rating_text}</span>
                    </div>
                    <div>
                        <span class="font-medium">状态:</span> {status_text}
                    </div>
                </div>
            </div>
            <!-- 评论区域 -->
            <div class="rounded-lg p-4 my-4 {comment_bg_class}">
                <div class="{prose_class} max-w-none leading-relaxed">
                    <p>{comment}</p>
                </div>
            </div>
            <!-- 元信息区域 -->
            <div class="mt-4 pt-3 border-t {border_class} text-sm">
                <div class="flex flex-wrap gap-x-6 gap-y-2">
                    <div><span class="font-medium">放送日期:</span> {item['air_date']}</div>
                    <div><span class="font-medium">评价日期:</span> {item['rating_date'] or '未知'}</div>
                </div>
            </div>
        </div>
    </div>
</div>
"""
        cards_content += card_html

    # 4. 写入文件 
    try:
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(front_matter)
            f.write(overview)
            f.write(cards_content)
        print(f"\n🎉 成功生成 Markdown 文件: {md_path}")
    except IOError as e:
        print(f"❌ 保存 Markdown 文件失败: {e}")


def main():
    if not FILTER_AIR_YEAR_MONTH or not re.match(r'^\d{4}-\d{2}$', FILTER_AIR_YEAR_MONTH):
        print("❌ 错误: 请在脚本中正确设置 FILTER_AIR_YEAR_MONTH (格式: YYYY-MM)。")
        return

    output_dir = f"anime-evaluate-{FILTER_AIR_YEAR_MONTH}"
    poster_dir = os.path.join(output_dir, "bgm_posters")
    
    setup_directory(output_dir)
    setup_directory(poster_dir)
    
    all_collected_data = []
    print("🚀 开始爬取 Bangumi 数据...")

    for status in STATUSES:
        page, has_next_page = 1, True
        print(f"\n--- 正在处理状态: {status} ---")
        while has_next_page:
            url = f"https://bgm.tv/anime/list/{USER_ID}/{status}?page={page}"
            print(f"🌐 请求页面: {url}")
            try:
                response = requests.get(url, headers=SCRAPE_HEADERS, proxies=PROXY, timeout=15)
                response.raise_for_status()
                response.encoding = 'utf-8'
                soup = BeautifulSoup(response.text, 'lxml')
                items = parse_page(soup, status)
                
                if not items or not soup.find('a', class_='p', text='››'):
                    has_next_page = False
                
                print(f"    找到 {len(items)} 个条目。")
                all_collected_data.extend(items)
                page += 1
                time.sleep(1)
            except requests.exceptions.RequestException as e:
                print(f"❌ 网络请求失败: {e}。停止处理 {status}。")
                has_next_page = False
    
    print(f"\n✅ 爬取完成。共获取 {len(all_collected_data)} 个条目。")
    print("\n🔍 开始根据配置进行筛选和下载...")
    
    filtered_results = []
    for item in all_collected_data:
        # 使用正则表达式检查放送月份
        air_date_dt = parse_date(item['air_date'])
        if air_date_dt and f"{air_date_dt.year}-{air_date_dt.month:02d}" == FILTER_AIR_YEAR_MONTH:
            print(f"⬇️  处理符合条件的番剧: {item['title']}")
            poster_path = download_poster(item['subject_id'], item['title'], poster_dir)
            item['poster_path'] = poster_path
            filtered_results.append(item)
            time.sleep(0.5) # API调用也需要限速

    if not filtered_results:
        print("\n⏹️  筛选后没有找到任何符合条件的番剧。脚本执行结束。")
        return

    print(f"\n✅ 筛选和下载完成。共处理 {len(filtered_results)} 个符合条件的番剧。")
    
    # 按评分排序后生成文件
    generate_markdown_file(sorted(filtered_results, key=lambda x: x.get('rating_score', 0), reverse=True), output_dir)

if __name__ == "__main__":
    main()