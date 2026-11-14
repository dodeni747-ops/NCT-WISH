import json
import os
import urllib.request
from bs4 import BeautifulSoup

# SM&STORE NCT WISH 카테고리 URL (필요시 실제 카테고리 번호로 변경)
TARGET_URL = "https://smtownandstore.com"

def fetch_smstore_goods():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    req = urllib.request.Request(TARGET_URL, headers=headers)
    try:
        html = urllib.request.urlopen(req).read().decode('utf-8')
    except Exception as e:
        print("페이지 접속 실패:", e)
        return

    soup = BeautifulSoup(html, 'html.parser')
    
    # 기존 데이터 불러오기 (재입고 NEW 판별용)
    old_items = {}
    if os.path.exists("goods.json"):
        with open("goods.json", "r", encoding="utf-8") as f:
            try:
                for item in json.load(f):
                    old_items[item["id"]] = item
            except:
                pass

    new_goods_list = []
    # 카페24 기반 SM&STORE 상품 리스트 파싱
    products = soup.select("ul.prdList > li")

    for idx, prd in enumerate(products):
        # 1. 상품 ID 추출
        prd_id = prd.get("id", f"item_{idx}").replace("anchorBoxId_", "")
        
        # 2. 상품명 추출
        name_tag = prd.select_one(".description .name a span:last-child") or prd.select_one(".description .name a")
        name = name_tag.get_text(strip=True) if name_tag else "상품명 없음"
        
        # 3. 개별 상품 상세 링크 추출
        link_tag = prd.select_one(".thumbnail a") or prd.select_one(".description .name a")
        href = link_tag.get("href", "") if link_tag else ""
        if href.startswith("/"):
            url = "https://smtownandstore.com" + href
        elif href.startswith("http"):
            url = href
        else:
            url = TARGET_URL

        # 4. 실제 상품 이미지 주소 추출 (프로토콜 보정)
        img_tag = prd.select_one(".thumbnail img")
        img_src = img_tag.get("src", "") if img_tag else ""
        if img_src.startswith("//"):
            img_src = "https:" + img_src
        elif img_src.startswith("/"):
            img_src = "https://smtownandstore.com" + img_src

        # 5. 품절 여부 확인 (품절 아이콘 또는 텍스트 감지)
        soldout_icon = prd.select_one("img[alt*='품절'], img[alt*='SOLD'], .soldout, .icon_img[src*='soldout']")
        in_stock = soldout_icon is None

        # 6. 재입고(NEW) 여부 판별 (이전에 품절이었으나 현재 재고가 생긴 경우)
        is_new = False
        if prd_id in old_items:
            was_in_stock = old_items[prd_id].get("inStock", False)
            if not was_in_stock and in_stock:
                is_new = True
            elif was_in_stock and in_stock:
                # 이미 재입고 상태였다면 유지 (필요시 초기화 조건 추가 가능)
                is_new = old_items[prd_id].get("isNew", False)

        new_goods_list.append({
            "id": prd_id,
            "name": name,
            "image": img_src,
            "url": url,
            "inStock": in_stock,
            "isNew": is_new
        })

    if new_goods_list:
        with open("goods.json", "w", encoding="utf-8") as f:
            json.dump(new_goods_list, f, ensure_ascii=False, indent=2)
        print(f"총 {len(new_goods_list)}개 상품 업데이트 완료")
    else:
        print("상품 목록을 찾지 못했습니다. URL 또는 HTML 구조를 확인하세요.")

if __name__ == "__main__":
    fetch_smstore_goods()
