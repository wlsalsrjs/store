import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# --- 1. 페이지 기본 설정 ---
st.set_page_config(
    page_title="편의점 & 카페 지도 탐색기",
    page_icon="📍",
    layout="wide"
)

st.title("📍 편의점 & 카페 위치 탐색 지도")
st.caption("시/도 및 동별 매장 위치 탐색과 기준 매장 중심 반경 검색 기능을 제공합니다.")

# --- 2. 데이터 불러오기 및 전처리 함수 ---
@st.cache_data
def load_data():
    # 파일명 예외 처리 (store.csv 우선, 없으면 store_filtered.csv 시도)
    try:
        df = pd.read_csv("store.csv")
    except FileNotFoundError:
        try:
            df = pd.read_csv("store_filtered.csv")
        except FileNotFoundError:
            st.error("데이터 파일('store.csv' 또는 'store_filtered.csv')을 찾을 수 없습니다.")
            return pd.DataFrame(), None

    # 업종 필터링 ("편의점", "카페")
    df = df[df["상권업종소분류명"].isin(["편의점", "카페"])].copy()

    # 위도·경도 결측치 제거 및 숫자형 변환
    df["위도"] = pd.to_numeric(df["위도"], errors="coerce")
    df["경도"] = pd.to_numeric(df["경도"], errors="coerce")
    df = df.dropna(subset=["위도", "경도"])

    # 동 관련 컬럼 자동 탐색 ("행정동명", "법정동명", "동명" 순으로 찾기)
    dong_col = None
    possible_dong_cols = ["행정동명", "법정동명", "동명", "법정동", "행정동"]
    for col in possible_dong_cols:
        if col in df.columns:
            dong_col = col
            break

    return df, dong_col

# 데이터 로드
df_raw, dong_column = load_data()

if df_raw.empty:
    st.stop()

# --- 3. 하버사인(Haversine) 거리 계산 함수 ---
def haversine_distance(lat1, lon1, lat2, lon2):
    """
    두 위도/경도 좌표 간의 대권 거리를 km 단위로 계산하는 함수
    """
    R = 6371.0  # 지구 반지름 (km)

    # 라디안 변환
    lat1_rad, lon1_rad = np.radians(lat1), np.radians(lon1)
    lat2_rad, lon2_rad = np.radians(lat2), np.radians(lon2)

    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    # 하버사인 공식
    a = np.sin(dlat / 2.0)**2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon / 2.0)**2
    c = 2 * np.arcsin(np.sqrt(a))

    return R * c

# --- 4. 사이드바 - 검색 및 필터 옵션 ---
st.sidebar.header("🔍 검색 필터")

# 4-1. 시/도 선택
sido_list = sorted(df_raw["시도명"].dropna().unique().tolist())
selected_sido = st.sidebar.selectbox("지역(시/도) 선택", sido_list)

# 선택한 시/도의 매장 1차 필터링
filtered_df = df_raw[df_raw["시도명"] == selected_sido].copy()

# 4-2. 동 선택 (동 컬럼이 존재할 경우)
if dong_column:
    dong_list = ["전체"] + sorted(filtered_df[dong_column].dropna().unique().tolist())
    selected_dong = st.sidebar.selectbox("동 선택", dong_list)

    if selected_dong != "전체":
        filtered_df = filtered_df[filtered_df[dong_column] == selected_dong]
else:
    st.sidebar.info("💡 데이터셋에 동(행정동/법정동) 정보 열을 찾지 못해 동별 필터가 비활성화되었습니다.")

# 4-3. 반경 검색 옵션
st.sidebar.markdown("---")
use_radius = st.sidebar.checkbox("반경 검색 사용하기")

selected_store_name = None
radius_km = 1.0

if use_radius:
    if not filtered_df.empty:
        # 기준 매장 선택 드롭다운 (상호명 표시)
        store_options = filtered_df["상호명"].tolist()
        selected_store_name = st.sidebar.selectbox("기준 매장 선택", store_options)
        
        # 반경 설정 슬라이더 (0.5km ~ 10km)
        radius_km = st.sidebar.slider("검색 반경 (km)", min_value=0.5, max_value=10.0, value=1.0, step=0.5)

        # 기준 매장의 위도/경도 가져오기
        target_store = filtered_df[filtered_df["상호명"] == selected_store_name].iloc[0]
        target_lat = target_store["위도"]
        target_lon = target_store["경도"]

        # 거리 계산 후 반경 내 매장 필터링
        filtered_df["거리_km"] = haversine_distance(target_lat, target_lon, filtered_df["위도"], filtered_df["경도"])
        filtered_df = filtered_df[filtered_df["거리_km"] <= radius_km]
    else:
        st.sidebar.warning("선택 조건에 맞는 매장이 없습니다.")

# --- 5. 화면 상단 - 지표 카드 (st.metric) ---
if use_radius and selected_store_name:
    st.subheader(f"📍 '{selected_store_name}' 기준 반경 {radius_km} km 이내")

convenience_count = len(filtered_df[filtered_df["상권업종소분류명"] == "편의점"])
cafe_count = len(filtered_df[filtered_df["상권업종소분류명"] == "카페"])
total_count = len(filtered_df)

col1, col2, col3 = st.columns(3)
col1.metric("🏪 편의점 수", f"{convenience_count:,} 개")
col2.metric("☕ 카페 수", f"{cafe_count:,} 개")
col3.metric("🏢 전체 매장 수", f"{total_count:,} 개")

st.markdown("---")

# --- 6. 지도 시각화 ---
if filtered_df.empty:
    st.info("조건에 맞는 매장이 없습니다. 필터 옵션을 변경해 보세요.")
else:
    # 색상 지정 (편의점: 파란색, 카페: 주황색)
    color_map = {"편의점": "#1f77b4", "카페": "#ff7f0e"}

    # Hover 정보 설정
    hover_cols = {"상권업종소분류명": True, "위도": False, "경도": False}
    if dong_column:
        hover_cols[dong_column] = True

    map_kwargs = {
        "data_frame": filtered_df,
        "lat": "위도",
        "lon": "경도",
        "color": "상권업종소분류명",
        "color_discrete_map": color_map,
        "hover_name": "상호명",
        "hover_data": hover_cols,
        "zoom": 13 if use_radius else 11,
    }

    if use_radius and selected_store_name:
        map_kwargs["center"] = {"lat": target_lat, "lon": target_lon}

    # Plotly 버전에 따른 scatter_map vs scatter_mapbox 호환성 분기 처리
    if hasattr(px, "scatter_map"):
        # 최신 Plotly (v5.24.0 이상)
        fig = px.scatter_map(
            **map_kwargs,
            map_style="open-street-map"
        )
    else:
        # 구버전 Plotly
        fig = px.scatter_mapbox(
            **map_kwargs,
            mapbox_style="open-street-map"
        )

    # 레이아웃 조정
    fig.update_layout(
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        legend_title_text="업종 구분"
    )

    # 지도 출력
    st.plotly_chart(fig, use_container_width=True)
