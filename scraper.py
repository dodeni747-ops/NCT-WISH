import json
import os
import urllib.request
import urllib.parse
from bs4 import BeautifulSoup

# SM&STORE에서 'NCT WISH' 검색 결과 페이지 (1페이지부터 끝까지 자동 탐색)
SEARCH_KEYWORD = "NCT WISH"
BASE_SEARCH_URL = f"https://smtownandstore.com{urllib.parse.quote(SEARCH_KEYWORD)}&page="

def fetch_smstore_goods():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
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

    # 1페이지부터 최대 15페이지까지 자동으로 넘기면서 모든 상품 수집
    for page in range(1, 16):
        url = BASE_SEARCH_URL + str(page)
        req = urllib.request.Request(url, headers=headers)
        try:
            html = urllib.request.urlopen(req).read().decode('utf-8')
        except Exception as e:
            print(f"{page}페이지 접속 실패:", e)
            break

        soup = BeautifulSoup(html, 'html.parser')
        products = soup.select("ul.prdList > li")

        # 더 이상 상품이 없으면 반복 종료
        if not products:
            break

        added_in_page = 0
        for idx, prd in enumerate(products):
            prd_id = prd.get("id", "").replace("anchorBoxId_", "")
            if not prd_id:
                prd_id = f"page{page}_item{idx}"

            # 중복 상품 건너뛰기
            if prd_id in seen_ids:
                continue

            name_tag = prd.select_one(".description .name a span:last-child") or prd.select_one(".description .name a")
            name = name_tag.get_text(strip=True) if name_tag else ""

            # 상품명에 'NCT WISH'가 포함된 진짜 NCT WISH 굿즈만 필터링
            if "NCT WISH" not in name.upper():
                continue

            seen_ids.add(prd_id)
            added_in_page += 1

            link_tag = prd.select_one(".thumbnail a") or prd.select_one(".description .name a")
            href = link_tag.get("href", "") if link_tag else ""
            if href.startswith("/"):
                item_url = "https://smtownandstore.com" + href
            elif href.startswith("http"):
                item_url = href
            else:
                item_url = url

            img_tag = prd.select_one(".thumbnail img")
            img_src = img_tag.get("src", "") if img_tag else ""
            if img_src.startswith("//"):
                img_src = "https:" + img_src
            elif img_src.startswith("/"):
                img_src = "https://smtownandstore.com" + img_src

            # 품절 여부 확인 (품절 아이콘, 텍스트, 클래스 등 다각도 체크)
            soldout_icon = prd.select_one("img[alt*='품절'], img[alt*='SOLD'], .soldout, .icon_img[src*='soldout']")
            prd_text = prd.get_text()
            in_stock = (soldout_icon is None) and ("SOLD OUT" not in prd_text.upper()) and ("품절" not in prd_text)

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

        # 현재 페이지에서 새로운 상품이 하나도 추가되지 않았다면 마지막 페이지로 간주하고 종료
        if added_in_page == 0:
            break

    if new_goods_list:
        with open("goods.json", "w", encoding="utf-8") as f:
            json.dump(new_goods_list, f, ensure_ascii=False, indent=2)
        print(f"총 {len(new_goods_list)}개의 NCT WISH 상품 업데이트 완료")
    else:
        print("NCT WISH 상품을 찾지 못했습니다.")

if __name__ == "__main__":
    fetch_smstore_goods()
