import json
import os
import re
import urllib.request
import urllib.parse
from bs4 import BeautifulSoup

# SM&STORE에서 'NCT WISH' 키워드로 검색 (신상품순 정렬 sort_method=10)
BASE_URL = "https://smtownandstore.com"

def fetch_smstore_goods():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
    }

    old_items = {}
    if os.path.exists("goods.json"):
        with open("goods.json", "r", encoding="utf-8") as f:
            try:
                for item in json.load(f):
                    old_items[item["id"]] = item
            except:
                pass

    new_goods_list = []
    seen_ids = set()

    # 1페이지부터 최대 50페이지까지 끝까지 탐색 (총 500~600개 대응)
    for page in range(1, 51):
        url = BASE_URL + str(page)
        req = urllib.request.Request(url, headers=headers)
        try:
            html = urllib.request.urlopen(req, timeout=15).read().decode('utf-8', errors='ignore')
        except Exception as e:
            print(f"{page}페이지 접속 실패:", e)
            break

        soup = BeautifulSoup(html, 'html.parser')

        # 하단 'Recommended for You 추천 상품' 영역이 섞이지 않도록 제거
        for rec in soup.select(".xans-product-listrecommend, .recommend, [class*='recommend']"):
            rec.decompose()

        products = soup.select("ul.prdList > li")
        if not products:
            break

        added_in_page = 0

        for idx, prd in enumerate(products):
            # 1. 링크에서 고유 상품 번호(product_no) 추출
            link_tag = prd.select_one(".thumbnail a") or prd.select_one(".description .name a") or prd.select_one("a[href*='product_no']")
            href = link_tag.get("href", "") if link_tag else ""
            
            match = re.search(r'product_no=(\d+)', href)
            if match:
                prd_id = match.group(1)
            else:
                prd_id = prd.get("id", "").replace("anchorBoxId_", "")
            
            if not prd_id or prd_id in seen_ids:
                continue

            # 2. 상품명 추출 (불필요한 숨김 텍스트 제거)
            name_tag = prd.select_one(".description .name a") or prd.select_one(".name a")
            if not name_tag:
                continue
            
            # 카페24 기본 '상품명 :' 라벨 제거
            for hidden in name_tag.select(".title, .displaynone"):
                hidden.decompose()
            name = name_tag.get_text(" ", strip=True)
            name = re.sub(r'^상품명\s*:\s*', '', name).strip()

            # 3. 제품명에 'NCT WISH'가 정확히 포함된 상품만 필터링 (WayV, 타 아티스트 제외)
            if "NCT WISH" not in name.upper():
                continue

            seen_ids.add(prd_id)
            added_in_page += 1

            # 4. 개별 상품 상세 구매 링크 생성
            if href.startswith("/"):
                item_url = "https://smtownandstore.com" + href
            elif href.startswith("http"):
                item_url = href
            else:
                item_url = f"https://smtownandstore.com{prd_id}"

            # 5. 원본 썸네일 이미지 주소 추출
            img_tag = prd.select_one(".thumbnail img") or prd.select_one("img")
            img_src = ""
            if img_tag:
                img_src = img_tag.get("data-src") or img_tag.get("src") or ""
            if img_src.startswith("//"):
                img_src = "https:" + img_src
            elif img_src.startswith("/"):
                img_src = "https://smtownandstore.com" + img_src

            # 6. 품절 여부 확인 (품절 아이콘, SOLD OUT, 일시품절 텍스트 감지)
            soldout_icon = prd.select_one("img[alt*='품절'], img[alt*='SOLD'], .soldout, .icon_img[src*='soldout']")
            prd_text = prd.get_text(" ", strip=True).upper()
            in_stock = (
                soldout_icon is None
                and "SOLD OUT" not in prd_text
                and "품절" not in prd_text
            )

            # 7. 재입고(NEW) 여부 판별
            is_new = False
            if prd_id in old_items:
                was_in_stock = old_items[prd_id].get("inStock", False)
                if not was_in_stock and in_stock:
                    is_new = True
                elif was_in_stock and in_stock:
                    is_new = old_items[prd_id].get("isNew", False)

            new_goods_list.append({
                "id": prd_id,
                "name": name,
                "image": img_src,
                "url": item_url,
                "inStock": in_stock,
                "isNew": is_new
            })

        # 현재 페이지에서 더 이상 새로운 상품이 나오지 않으면 마지막 페이지로 판단하고 종료
        if added_in_page == 0:
            break

    if new_goods_list:
        with open("goods.json", "w", encoding="utf-8") as f:
            json.dump(new_goods_list, f, ensure_ascii=False, indent=2)
        print(f"총 {len(new_goods_list)}개의 NCT WISH 상품 업데이트 완료!")
    else:
        print("NCT WISH 상품을 찾지 못했습니다.")

if __name__ == "__main__":
    fetch_smstore_goods()
