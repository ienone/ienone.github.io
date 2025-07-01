import os
import re
import sys
import requests
from bs4 import BeautifulSoup

# --- 配置 ---
MARKDOWN_FILE = 'index.md'
OUTPUT_DIR = 'anime_posters_new' # 新的输出目录，避免与旧文件混淆
API_URL_TEMPLATE = 'https://api.bgm.tv/v0/subjects/{}/image?type=common'
HEADERS = {
    'User-Agent': 'MyAnimePosterDownloader/1.1 (https://github.com/ienone)'
}
# --- 配置结束 ---

def sanitize_filename(filename):
    """移除文件名中的非法字符，虽然从src提取的一般是安全的，但以防万一。"""
    return re.sub(r'[\\/*?:"<>|]', "", filename).strip()

def setup_directory(dir_name):
    """创建输出目录（如果不存在）"""
    if not os.path.exists(dir_name):
        try:
            os.makedirs(dir_name)
            print(f"✅ 成功创建目录: '{dir_name}'")
        except OSError as e:
            print(f"❌ 创建目录 '{dir_name}' 失败: {e}")
            sys.exit(1)

def parse_and_download():
    """解析 Markdown 文件并下载所有番剧图片"""
    try:
        with open(MARKDOWN_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"❌ 错误: 未找到文件 '{MARKDOWN_FILE}'。请确保脚本和该文件在同一目录下。")
        sys.exit(1)

    soup = BeautifulSoup(content, 'lxml')
    
    anime_cards = soup.find_all('div', class_=re.compile(r'flex.*border.*rounded-lg'))
    
    if not anime_cards:
        print("⚠️ 警告: 在文件中未找到任何番剧卡片。请检查 HTML 结构是否正确。")
        return

    print(f"🔍 找到了 {len(anime_cards)} 个番剧条目，开始处理...")
    
    for card in anime_cards:
        # 寻找包含 subject ID 的链接
        link_tag = card.find('a', href=re.compile(r'bgm.tv/subject/'))
        # 寻找 <img> 标签
        img_tag = card.find('img')
        
        if not link_tag or not img_tag:
            print("⚠️ 警告: 发现一个卡片，但无法提取链接或图片标签，已跳过。")
            continue
            
        # 从链接中提取 subject ID
        match_id = re.search(r'/subject/(\d+)', link_tag['href'])
        if not match_id:
            print(f"⚠️ 警告: 在链接 '{link_tag['href']}' 中未找到 subject ID，已跳过。")
            continue
        subject_id = match_id.group(1)
        
        # 从 <img> 标签的 src 属性中提取文件名
        src_path = img_tag.get('src', '')
        if not src_path:
             print(f"⚠️ 警告: 找到一个图片标签，但没有 'src' 属性，已跳过。 (ID: {subject_id})")
             continue
        # os.path.basename 可以安全地从路径中提取文件名
        target_filename = os.path.basename(src_path)

        # 下载图片
        download_image(subject_id, target_filename)

def download_image(subject_id, target_filename):
    """根据 subject ID 和目标文件名下载图片"""
    api_url = API_URL_TEMPLATE.format(subject_id)
    # 从文件名中提取标题，用于日志打印
    anime_title_log = os.path.splitext(target_filename)[0].replace('_', ' ').title()
    print(f"\n🚀 正在处理: '{anime_title_log}' (ID: {subject_id})")
    
    try:
        response = requests.get(api_url, headers=HEADERS, timeout=15)
        response.raise_for_status()

        # 拼接最终保存路径
        safe_filename = sanitize_filename(target_filename)
        filepath = os.path.join(OUTPUT_DIR, safe_filename)
        
        # 写入文件
        with open(filepath, 'wb') as f:
            f.write(response.content)
        print(f"   - ✅ 图片已保存为: '{filepath}'")

    except requests.exceptions.RequestException as e:
        print(f"   - ❌ 下载失败: {e}")

if __name__ == "__main__":
    print("--- Bangumi 番剧海报下载脚本 ---")
    setup_directory(OUTPUT_DIR)
    parse_and_download()
    print("\n--- 所有任务已完成 ---")