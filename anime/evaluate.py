import re
import os
import time
import random
import json
import html
from datetime import datetime, timedelta

# ==================== 配置区域 ====================

# 1. Bangumi 用户ID
USER_ID = '950475'

# 2. 筛选条件 (核心配置)
FILTER_AIR_YEAR_MONTH = '2025-07' # 格式: 'YYYY-MM'

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

# 6. 图片处理配置
MAX_POSTER_WIDTH = 1200  # 海报保存时的最大宽度
COLOR_SAMPLING_WIDTH = 480  # 颜色提取时的采样宽度

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

def parse_rating_date(date_str):
    """解析收藏日期，支持多种格式"""
    if not date_str:
        return None
    
    # 移除可能的额外文本
    date_str = date_str.strip()
    
    # 尝试各种日期格式
    patterns = [
        (r'(\d{4}-\d{1,2}-\d{1,2})', '%Y-%m-%d'),
        (r'(\d{4}/\d{1,2}/\d{1,2})', '%Y/%m/%d'),
        (r'(\d{4}-\d{1,2})', '%Y-%m'),
        (r'(\d{4}/\d{1,2})', '%Y/%m'),
    ]
    
    for pattern, fmt in patterns:
        match = re.search(pattern, date_str)
        if match:
            try:
                return datetime.strptime(match.group(1), fmt)
            except ValueError:
                continue
    
    return None

def get_date_range(target_month_str):
    """根据目标月份生成收藏日期筛选区间（目标月 + 往后4个月）"""
    year, month = map(int, target_month_str.split('-'))
    start_date = datetime(year, month, 1)
    
    # 计算结束日期：往后4个月的月末
    end_month = month + 3
    end_year = year
    if end_month > 12:
        end_year += end_month // 12
        end_month = end_month % 12
        if end_month == 0:
            end_month = 12
            end_year -= 1
    
    # 获取该月的最后一天
    if end_month == 12:
        next_month_start = datetime(end_year + 1, 1, 1)
    else:
        next_month_start = datetime(end_year, end_month + 1, 1)
    end_date = next_month_start - timedelta(days=1)
    
    return start_date, end_date

def should_stop_pagination(rating_date_str, start_date):
    """判断是否应该停止分页（遇到早于起始日期的条目）"""
    rating_date = parse_rating_date(rating_date_str)
    if rating_date and rating_date < start_date:
        return True
    return False

def get_season_info(target_month_str):
    """根据目标月份获取季度信息"""
    year, month = map(int, target_month_str.split('-'))
    
    # 定义季度区间
    if month in [1, 2, 3]:
        season_name = "冬季"
        season_months = [1, 2, 3]
    elif month in [4, 5, 6]:
        season_name = "春季" 
        season_months = [4, 5, 6]
    elif month in [7, 8, 9]:
        season_name = "夏季"
        season_months = [7, 8, 9]
    else:  # [10, 11, 12]
        season_name = "秋季"
        season_months = [10, 11, 12]
    
    return {
        'year': year,
        'season_name': season_name,
        'season_months': season_months,
        'start_month': season_months[0],
        'end_month': season_months[-1]
    }

def categorize_anime(air_date_str, target_month_str):
    """根据首播日期分类番剧"""
    air_date = parse_date(air_date_str)
    if not air_date:
        return "unknown"
    
    season_info = get_season_info(target_month_str)
    target_year = season_info['year']
    season_months = season_info['season_months']
    
    # 判断是否为当季新番
    if (air_date.year == target_year and 
        air_date.month in season_months):
        return "current_season"  # 当季新番
    
    # 计算上一个季度的月份范围
    current_season_start = datetime(target_year, season_months[0], 1)
    
    # 上一个季度（3个月前）
    if season_months[0] == 1:  # 当前冬季，上一季度是去年秋季
        prev_season_months = [10, 11, 12]
        prev_season_year = target_year - 1
    elif season_months[0] == 4:  # 当前春季，上一季度是冬季
        prev_season_months = [1, 2, 3]
        prev_season_year = target_year
    elif season_months[0] == 7:  # 当前夏季，上一季度是春季
        prev_season_months = [4, 5, 6]
        prev_season_year = target_year
    else:  # season_months[0] == 10，当前秋季，上一季度是夏季
        prev_season_months = [7, 8, 9]
        prev_season_year = target_year
    
    # 判断是否为上一季度番剧（近期番剧）
    if (air_date.year == prev_season_year and 
        air_date.month in prev_season_months):
        return "recent_anime"  # 近期番剧（上一季度）
    
    # 其他都归类为补旧番
    return "old_anime"  # 补旧番

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

def resize_image_with_aspect_ratio(image, max_width):
    """保持长宽比缩放图片到指定最大宽度"""
    from PIL import Image
    if image.width <= max_width:
        return image
    
    ratio = max_width / image.width
    new_height = int(image.height * ratio)
    return image.resize((max_width, new_height), Image.Resampling.LANCZOS)

def extract_dominant_rgb(image_path):
    """从图片提取一个美观的主色调，返回RGB元组 (r, g, b)"""
    import colorgram
    from PIL import Image
    if not image_path or not os.path.exists(image_path):
        return None
    try:
        # 先缩放图片到较小尺寸进行颜色采样，提升处理速度
        with Image.open(image_path) as img:
            img = img.convert("RGB")
            sampled_img = resize_image_with_aspect_ratio(img, COLOR_SAMPLING_WIDTH)
            
        colors = colorgram.extract(sampled_img, 12)
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
    import requests
    from PIL import Image
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
        
        # 临时保存原始图片
        temp_filepath = filepath + '.temp'
        with open(temp_filepath, 'wb') as f:
            f.write(response.content)
        
        # 处理图片：格式转换和尺寸优化
        try:
            with Image.open(temp_filepath) as img:
                img = img.convert("RGB")
                
                # 如果图片宽度超过限制，则缩放
                if img.width > MAX_POSTER_WIDTH:
                    img = resize_image_with_aspect_ratio(img, MAX_POSTER_WIDTH)
                    print(f"    📏 图片已缩放至宽度 {MAX_POSTER_WIDTH}px")
                
                # 保存为JPG格式
                final_filepath = os.path.join(poster_dir, f"{safe_title}_{subject_id}.jpg")
                img.save(final_filepath, "JPEG", quality=85, optimize=True)
                
            # 删除临时文件
            os.remove(temp_filepath)
            print(f"    🖼️ 海报已下载并优化: {os.path.basename(final_filepath)}")
            return final_filepath
            
        except Exception as e:
            # 如果图片处理失败，使用原始文件
            os.rename(temp_filepath, filepath)
            print(f"    ⚠️ 图片处理失败，使用原始文件: {e}")
            print(f"    🖼️ 海报已下载: {filename}")
            return filepath

    except requests.exceptions.RequestException as e:
        print(f"    ❌ 下载海报失败 (ID: {subject_id}): {e}")
        return None

# ==================== 页面解析函数 (修改) ====================
def parse_page(soup, status, start_date, end_date, target_month):
    item_list_ul = soup.find('ul', id='browserItemList')
    if not item_list_ul: 
        return [], False
    
    items = item_list_ul.find_all('li', class_='item')
    results = []
    should_stop = False
    
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
                if date_tag: 
                    rating_date = date_tag.text.strip()
                    
                    # 检查是否应该停止分页
                    if should_stop_pagination(rating_date, start_date):
                        should_stop = True
                        break
                    
                    # 检查收藏日期是否在目标区间内
                    rating_date_obj = parse_rating_date(rating_date)
                    if not rating_date_obj or rating_date_obj < start_date or rating_date_obj > end_date:
                        continue
                
                stars_tag = collect_info.find('span', class_=re.compile(r'stars\d+'))
                if stars_tag:
                    star_class = next((c for c in stars_tag.get('class', []) if c.startswith('stars')), None)
                    if star_class:
                        match = re.search(r'stars(\d+)', star_class)
                        if match: rating = int(match.group(1))
            
            # 分类番剧
            category = categorize_anime(air_date, target_month)
            if category == "unknown":
                continue  # 跳过未知日期的条目
                
            comment_box = item.find('div', id='comment_box')
            comment = comment_box.find('div', class_='text').text.strip() if comment_box and comment_box.find('div', class_='text') else None
            
            results.append({
                'subject_id': subject_id, 
                'title': title, 
                'link': link, 
                'air_date': air_date, 
                'rating_date': rating_date, 
                'rating_score': rating, 
                'comment': comment, 
                'status': status, 
                'category': category,
                'poster_path': None
            })
            
        except Exception as e:
            print(f"❌ 解析某个条目时出错，已跳过: {e}")
    
    return results, should_stop

# ==================== Markdown 生成函数 (修改) ====================

def generate_markdown_file(anime_data, output_dir):
    md_path = os.path.join(output_dir, "index.md")
    
    # 分离不同类型的番剧，只保留当季新番和补旧番
    current_season = [item for item in anime_data if item['category'] == 'current_season']
    old_anime = [item for item in anime_data if item['category'] == 'old_anime']
    # 近期番剧不展示，因为应该在上个季度已经被总结过了
    
    # 获取季度信息
    season_info = get_season_info(FILTER_AIR_YEAR_MONTH)
    year = season_info['year']
    season_name = season_info['season_name']
    
    # 1. Front Matter
    title = f"{year}年{season_name}新番观后简评"
    today = datetime.now().strftime('%Y-%m-%d')
    
    front_matter = f"""---
title: "{title}"
date: {today}
description: "记录{year}年{season_name}新番个人简评。"
slug: "anime-review-{FILTER_AIR_YEAR_MONTH}"
tags: ["番剧", "季度总结", "{year}年", "{season_name}"]
series: ["季度新番"]
series_order: 1
showTableOfContents: true
---
"""

    # 2. 概述
    overview = f"""
{{{{< lead >}}}}
在这里写下你对本季新番的总体概述和看法...
{{{{< /lead >}}}}

## 简单总结
### {season_name}新番
- 本季度新番共看完 {len([x for x in current_season if x['status'] == 'collect'])} 部，弃番 {len([x for x in current_season if x['status'] == 'dropped'])} 部，搁置 {len([x for x in current_season if x['status'] == 'on_hold'])} 部。

### 补旧番
- 补旧番共 {len(old_anime)} 部：
{generate_old_anime_summary(old_anime)}

---

## {season_name}新番详评
"""
    
    # 3. 生成当季新番卡片
    current_season_content = ""
    for item in sorted(current_season, key=lambda x: x.get('rating_score', 0), reverse=True):
        if not item['poster_path']: 
            continue
        current_season_content += generate_anime_card(item)

    # 4. 补旧番简要展示
    old_anime_section = ""
    if old_anime:
        old_anime_section = "\n## 补旧番记录\n\n"
        for item in sorted(old_anime, key=lambda x: x.get('rating_score', 0), reverse=True):
            status_text = {'collect': '看过', 'on_hold': '搁置', 'dropped': '弃番'}.get(item['status'], '未知')
            rating_text = f"{item['rating_score']}/10" if item['rating_score'] > 0 else "未评分"
            old_anime_section += f"- [{item['title']}]({item['link']}) ({item['air_date']}) : {rating_text} ({status_text})\n"

    # 5. 写入文件
    try:
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(front_matter)
            f.write(overview)
            f.write(current_season_content)
            f.write(old_anime_section)
        print(f"\n🎉 成功生成 Markdown 文件: {md_path}")
    except IOError as e:
        print(f"❌ 保存 Markdown 文件失败: {e}")

def generate_old_anime_summary(old_anime_list):
    """生成补旧番概述"""
    if not old_anime_list:
        return "  - 本期间未补旧番"
    
    summary_lines = []
    for item in old_anime_list:
        rating_text = f"{item['rating_score']}/10" if item['rating_score'] > 0 else "未评分"
        summary_lines.append(f"  - [{item['title']}]({item['link']}) ({item['air_date']}) : {rating_text}")
    
    return "\n".join(summary_lines)

def generate_anime_card(item):
    """生成与历史文章共用的 review-card shortcode（无需网络或颜色提取）。"""
    poster_filename = os.path.basename(item['poster_path'])
    status_text = {'collect': '看过', 'on_hold': '搁置', 'dropped': '弃番'}.get(item['status'], '未知')
    rating_text = f"{item['rating_score']}/10" if item['rating_score'] > 0 else "未评分"
    attributes = {
        'title': item['title'],
        'href': item['link'],
        'poster': f"./bgm_posters/{poster_filename}",
        'alt': f"{item['title']} 海报",
        'rating': rating_text,
        'status': status_text,
        'aired': item['air_date'],
        'dateLabel': '评价日期',
        'date': item['rating_date'] or '未知',
    }
    # JSON string quoting is also valid Hugo shortcode quoting. Remote comments
    # are text, not trusted HTML or executable shortcode source.
    params = "\n".join(f"  {key}={json.dumps(str(value), ensure_ascii=False)}" for key, value in attributes.items())
    comment = html.escape(item['comment'] or "暂无短评。")
    comment = comment.replace('{{', '&#123;&#123;').replace('}}', '&#125;&#125;')
    comment = comment.replace('\r\n', '\n').replace('\n', '<br>')
    return (f"\n### {item['title']}\n\n"
            + "{{< review-card\n" + params + "\n>}}\n"
            + f"<p>{comment}</p>\n"
            + "{{< /review-card >}}\n\n")

# ==================== 主函数 (修改) ====================

def main():
    # Optional scraping dependencies are loaded only for a requested fetch.
    import requests
    from bs4 import BeautifulSoup

    if not FILTER_AIR_YEAR_MONTH or not re.match(r'^\d{4}-\d{2}$', FILTER_AIR_YEAR_MONTH):
        print("❌ 错误: 请在脚本中正确设置 FILTER_AIR_YEAR_MONTH (格式: YYYY-MM)。")
        return

    # 计算日期区间
    start_date, end_date = get_date_range(FILTER_AIR_YEAR_MONTH)
    print(f"📅 收藏日期筛选区间: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}")
    
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
                
                items, should_stop = parse_page(soup, status, start_date, end_date, FILTER_AIR_YEAR_MONTH)
                
                print(f"    找到 {len(items)} 个符合条件的条目。")
                all_collected_data.extend(items)
                
                # 检查是否应该停止分页
                if should_stop or not soup.find('a', class_='p', text='››'):
                    has_next_page = False
                    if should_stop:
                        print(f"    ⏹️ 遇到早于目标区间的条目，停止遍历 {status}")
                
                page += 1
                time.sleep(1)
            except requests.exceptions.RequestException as e:
                print(f"❌ 网络请求失败: {e}。停止处理 {status}。")
                has_next_page = False
    
    print(f"\n✅ 爬取完成。共获取 {len(all_collected_data)} 个条目。")
    
    if not all_collected_data:
        print("\n⏹️ 未找到任何符合条件的番剧。脚本执行结束。")
        return
    
    # 先进行分类统计
    current_season = [item for item in all_collected_data if item['category'] == 'current_season']
    old_anime = [item for item in all_collected_data if item['category'] == 'old_anime']
    recent_anime = [item for item in all_collected_data if item['category'] == 'recent_anime']
    
    print(f"\n📊 分类统计:")
    print(f"  - 当季新番: {len(current_season)} 部")
    print(f"  - 近期番剧: {len(recent_anime)} 部 (不下载海报)")
    print(f"  - 补旧番: {len(old_anime)} 部 (不下载海报)")
    
    # 只为当季新番下载海报
    if current_season:
        print(f"\n🖼️ 开始为当季新番下载海报...")
        for item in current_season:
            print(f"⬇️ 处理: {item['title']}")
            poster_path = download_poster(item['subject_id'], item['title'], poster_dir)
            item['poster_path'] = poster_path
            time.sleep(0.5)
    else:
        print("\n⚠️ 没有当季新番需要下载海报。")
    
    # 为补旧番和近期番剧设置空的海报路径
    for item in old_anime + recent_anime:
        item['poster_path'] = None

    # 生成Markdown文件
    valid_items = [item for item in all_collected_data if item['category'] == 'current_season' and item['poster_path']] + old_anime
    print(f"\n✅ 处理完成。有效条目 {len(valid_items)} 个（当季新番: {len([x for x in valid_items if x['category'] == 'current_season'])}, 补旧番: {len(old_anime)}）。")
    
    generate_markdown_file(valid_items, output_dir)

if __name__ == "__main__":
    main()