import json
import os
import re
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

# 아까 직접 접속하셨던 검색 주소 그대로 사용 (keyword=WISH)
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
            viewport={"width": 390, "height": 844},
            locale="ko-KR"
        )
        page = context.new_page()

        # 1. 먼저 메인 페이지에 접속해 해외배송(WORLD SHIPPING) 팝업이 뜨면 닫기 처리
        try:
            page.goto("https://smtownandstore.com", wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(1500)
            # 팝업 닫기 버튼이나 대한민국 선택 버튼이 있으면 클릭
            close_btn = page.locator("text=닫기, .close, #popup_close").first
            if close_btn.is_visible():
                close_btn.click()
        except:
            pass

        # 2. 1페이지부터 최대 50페이지까지 검색 결과 순회
        for page_num in range(1, 51):
            url = BASE_URL + str(page_num)
            print(f"{page_num}페이지 접속 중: {url}")
            try:
                page.goto(url, wait_until="networkidle", timeout=25000)
                page.wait_for_timeout(2000)
            except Exception as e:
                print(f"{page_num}페이지 타임아웃/에러:", e)
                break

            html = page.content()
            soup = BeautifulSoup(html, "html.parser")

            # 하단 'Recommended for You 추천 상품' 영역 제거
            for rec in soup.select("[class*='recommend'], .xans-product-listrecommend"):
                rec.decompose()

            # 클래스 이름에 상관없이 'product_no='가 포함된 모든 상품 블록(li) 찾기
            all_li = soup.select("li")
            added_in_page = 0

            for li in all_li:
                # 내부에 상품 상세 링크가 있는지 확인
                link_tag = li.select_one("a[href*='product_no=']")
                if not link_tag:
                    continue

                href = link_tag.get("href", "")
                match = re.search(r'product_no=(\d+)', href)
                if not match:
                    continue

                prd_id = match.group(1)
                if prd_id in seen_ids:
                    continue

                # 상품 카드 전체 텍스트에서 'NCT WISH' 포함 여부 확인
                card_text = li.get_text(" ", strip=True)
                if "NCT WISH" not in card_text.upper():
                    continue

                # 정확한 상품명 추출 (이미지 alt 속성 또는 링크 텍스트 활용)
                img_tag = li.select_one("img")
                name = ""
                if img_tag and img_tag.get("alt") and "NCT WISH" in img_tag.get("alt").upper():
                    name = img_tag.get("alt").strip()
                else:
                    # 링크들 중 텍스트가 가장 긴 것을 상품명으로 선택
                    texts = [a.get_text(" ", strip=True) for a in li.select("a[href*='product_no=']") if a.get_text(strip=True)]
                    if texts:
                        name = max(texts, key=len)

                if not name or "NCT WISH" not in name.upper():
                    continue

                seen_ids.add(prd_id)
                added_in_page += 1

                # 개별 구매 상세 링크
                item_url = f"https://smtownandstore.comproduct/detail.html?product_no={prd_id}"

                # 썸네일 이미지 주소 추출
                img_src = ""
                if img_tag:
                    img_src = img_tag.get("data-src") or img_tag.get("src") or ""
                if img_src.startswith("//"):
                    img_src = "https:" + img_src
                elif img_src.startswith("/"):
                    img_src = "https://smtownandstore.com" + img_src

                # 품절 여부 확인 (카드 내 텍스트 및 품절 아이콘 확인)
                soldout_icon = li.select_one("img[alt*='품절'], img[alt*='SOLD'], [class*='soldout'], [src*='soldout']")
                upper_text = card_text.upper()
                in_stock = (
                    soldout_icon is None
                    and "SOLD OUT" not in upper_text
                    and "품절" not in upper_text
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

            print(f"{page_num}페이지에서 NCT WISH 상품 {added_in_page}개 발견")
            # 더 이상 새로운 NCT WISH 상품이 나오지 않으면 종료 (단, 1페이지가 비어있을 수 있으므로 2페이지까지는 확인)
            if page_num >= 2 and added_in_page == 0:
                break

        browser.close()

    if new_goods_list:
        with open("goods.json", "w", encoding="utf-8") as f:
            json.dump(new_goods_list, f, ensure_ascii=False, indent=2)
        print(f"성공! 총 {len(new_goods_list)}개의 NCT WISH 상품 저장 완료")
    else:
        print("상품을 찾지 못했습니다. (해외 IP 차단 가능성 확인 필요)")

if __name__ == "__main__":
    fetch_smstore_goods()
