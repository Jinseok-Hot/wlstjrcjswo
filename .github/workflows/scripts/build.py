#!/usr/bin/env python3
"""
투자내역 xlsx → index.html 빌드 스크립트
"""
import pandas as pd
import json
import base64
import os
import sys

# 경로 설정
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR   = os.path.join(ROOT, 'data')
TEMPLATE   = os.path.join(ROOT, 'template', 'template.html')
OUTPUT     = os.path.join(ROOT, 'index.html')
LOGO_PATH  = os.path.join(ROOT, 'template', 'logo.png')

def find_xlsx():
    """data/ 폴더에서 가장 최근 xlsx 파일 찾기"""
    files = [f for f in os.listdir(DATA_DIR) if f.endswith('.xlsx') or f.endswith('.xls')]
    if not files:
        raise FileNotFoundError("data/ 폴더에 xlsx 파일이 없습니다.")
    files.sort()
    return os.path.join(DATA_DIR, files[-1])

def classify_type(row):
    name = str(row.get('상품명', ''))
    if '(연장)' in name:
        return '연장'
    if row.get('담보구분') == '후취담보':
        return '후취'
    if row.get('지분대출') == '지분대출':
        return '지분'
    return '신규'

def extract_region(addr):
    parts = str(addr or '').strip().split(' ')
    if not parts:
        return ('기타', '기타')
    large = parts[0]
    if large == '세종특별자치시':
        return (large, large)
    detail = ''
    for p in parts[1:]:
        if p.endswith('구') or p.endswith('시') or p.endswith('군'):
            detail = p
            break
    return (large, detail or large)

def build_investor_data(df):
    df['상품유형'] = df.apply(classify_type, axis=1)
    df[['지역_대분류', '지역_상세']] = df['주소'].apply(
        lambda x: pd.Series(extract_region(x))
    )

    investors = {}
    for inv, group in df.groupby('투자자'):
        types = group['상품유형'].unique().tolist()
        regions = group[['지역_대분류', '지역_상세']].drop_duplicates()
        region_list = [{'large': r['지역_대분류'], 'detail': r['지역_상세']} for _, r in regions.iterrows()]

        investors[inv] = {
            'name': inv,
            'types': types,
            'regions': region_list,
            'rate_min': float(group['금리'].min()),
            'rate_max': float(group['금리'].max()),
            'ltv_eff_max': float(group['유효담보비율'].max()),
            'ltv_rec_max': float(group['담보인정비율'].max()),
            'max_single': int(group['투자금액'].max()),
            'total_amt': int(group['투자금액'].sum()),
            'total_count': int(group['상품명'].nunique()),
            'latest_date': str(group['투자일'].max())[:10],
        }

    region_map = {}
    for inv_data in investors.values():
        for r in inv_data['regions']:
            large, detail = r['large'], r['detail']
            if large not in region_map:
                region_map[large] = []
            if detail not in region_map[large]:
                region_map[large].append(detail)
    for k in region_map:
        region_map[k] = sorted(region_map[k])

    return {
        'investors': list(investors.values()),
        'region_map': region_map
    }

def get_date_range(df):
    dates = pd.to_datetime(df['투자일'], errors='coerce').dropna()
    if dates.empty:
        return '데이터'
    return f"{dates.min().strftime('%Y.%m')}–{dates.max().strftime('%Y.%m')}"

def main():
    print("=== 투자자 매칭 HTML 빌드 시작 ===")

    xlsx_path = find_xlsx()
    print(f"데이터 파일: {xlsx_path}")

    df = pd.read_excel(xlsx_path)
    print(f"총 {len(df)}행 로드")

    data = build_investor_data(df)
    print(f"투자자 {len(data['investors'])}명 처리")

    date_range = get_date_range(df)
    inv_count = len(data['investors'])

    with open(TEMPLATE, 'r', encoding='utf-8') as f:
        html = f.read()

    if os.path.exists(LOGO_PATH):
        with open(LOGO_PATH, 'rb') as f:
            logo_b64 = 'data:image/png;base64,' + base64.b64encode(f.read()).decode()
    else:
        logo_b64 = ''
        print("⚠️  logo.png 없음 - 로고 미적용")

    data_str = json.dumps(data, ensure_ascii=False)
    html = html.replace('DATA_JSON_PLACEHOLDER', data_str)
    html = html.replace('LOGO_B64_PLACEHOLDER', logo_b64)
    html = html.replace('📅 2026.04–06 · 70명', f'📅 {date_range} · {inv_count}명')

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"✅ index.html 생성 완료 ({len(html)//1024}KB)")

if __name__ == '__main__':
    main()
