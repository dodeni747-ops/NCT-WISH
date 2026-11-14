import json
import os
import re
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

# 아까 보내주신 실제 모바일 검색 주소 기반 (키워드: NCT WISH, 신상품순)
BASE_URL = "https://smtownandstore.com"

def fetch_smstore_goods():
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

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
            viewport={"width": 390, "height": 844}
        )
        page = context.new_page()

        # 1페이지부터 최대 30페이지까지 실제 브라우저로 접속해 탐색
        for page_num in range(1, 31):
            url = BASE_URL + str(page_num)
            print(f"{page_num}페이지 로딩 중...")
            try:
                page.goto(url, wait_until="networkidle", timeout=20000)
                page.wait_for_timeout(1500) # 상품 이미지/목록 렌더링 대기
            except Exception as e:
                print(f"{page_num}페이지 접속 에러:", e)
                break

            html = page.content()
            soup = BeautifulSoup(html, "html.parser")

            # 하단 'Recommended for You 추천 상품' 영역 완전히 제거
            for rec in soup.select(".xans-product-listrecommend, .recommend, [class*='recommend']"):
                rec.decompose()

            # 모바일 및 PC 상품 리스트 선택자 모두 탐색
            products = soup.select("ul.prdList > li, .prdList li")
            if not products:
                print("더 이상 상품이 없어 종료합니다.")
                break

            added_in_page = 0

            for idx, prd in enumerate(products):
                # 링크 및 고유 상품 번호(product_no) 추출
                link_tag = prd.select_one("a[href*='product_no']") or prd.select_one(".thumbnail a") or prd.select_one("a")
                href = link_tag.get("href", "") if link_tag else ""

                match = re.search(r'product_no=(\d+)', href)
                if not match:
                    # data-product-no 속성 등 보조 탐색
                    prd_id = prd.get("id", "").replace("anchorBoxId_", "")
                else:
                    prd_id = match.group(1)

                if not prd_id or prd_id in seen_ids:
                    continue

                # 상품명 추출
                name_tag = prd.select_one(".description .name a") or prd.select_one(".name a") or prd.select_one(".name")
                if not name_tag:
                    continue

                for hidden in name_tag.select(".title, .displaynone"):
                    hidden.decompose()
                name = name_tag.get_text(" ", strip=True)
                name = re.sub(r'^상품명\s*:\s*', '', name).strip()

                # 오직 'NCT WISH'가 포함된 상품만 필터링
                if "NCT WISH" not in name.upper():
                    continue

                seen_ids.add(prd_id)
                added_in_page += 1

                # 개별 구매 상세 링크 (모바일/PC 공용 상세페이지)
                item_url = f"https://smtownandstore.com{prd_id}"

                # 실제 썸네일 이미지 주소 추출
                img_tag = prd.select_one(".thumbnail img") or prd.select_one("img")
                img_src = ""
                if img_tag:
                    img_src = img_tag.get("data-src") or img_tag.get("src") or ""
                if img_src.startswith("//"):
                    img_src = "https:" + img_src
                elif img_src.startswith("/"):
                    img_src = "https://smtownandstore.com" + img_src

                # 품절 여부 확인 (품절 아이콘, SOLD OUT, 일시품절 텍스트)
                soldout_icon = prd.select_one("img[alt*='품절'], img[alt*='SOLD'], .soldout, .icon_img[src*='soldout']")
                prd_text = prd.get_text(" ", strip=True).upper()
                in_stock = (
                    soldout_icon is None
                    and "SOLD OUT" not in prd_text
                    and "품절" not in prd_text
                )

                # 재입고(NEW) 여부 판별
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

            print(f"{page_num}페이지에서 NCT WISH 상품 {added_in_page}개 수집 완료")
            if added_in_page == 0:
                break

        browser.close()

    # 무조건 결과를 저장하여 예전 잘못된 데이터 덮어쓰기
    with open("goods.json", "w", encoding="utf-8") as f:
        json.dump(new_goods_list, f, ensure_ascii=False, indent=2)
    print(f"최종 총 {len(new_goods_list)}개의 NCT WISH 상품 저장 완료!")

if __name__ == "__main__":
    fetch_smstore_goods()
