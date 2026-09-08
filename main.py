import streamlit as st
import pandas as pd
import numpy as np
import json
import streamlit.components.v1 as components

# --- 1. 페이지 기본 설정 ---
st.set_page_config(
    page_title="편의점 & 카페 지도 탐색기 (레이저 모드 포함)",
    page_icon="💥",
    layout="wide"
)

st.title("📍 편의점 & 카페 지도 탐색기")
st.caption("기본 필터 기능과 함께 상단의 '🔥 레이저 모드'를 켜면 지도를 클릭해 매장을 파괴할 수 있습니다!")

# --- 2. 데이터 불러오기 및 전처리 ---
@st.cache_data
def load_data():
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

    # 동 관련 컬럼 탐색
    dong_col = None
    possible_dong_cols = ["행정동명", "법정동명", "동명", "법정동", "행정동"]
    for col in possible_dong_cols:
        if col in df.columns:
            dong_col = col
            break

    return df, dong_col

df_raw, dong_column = load_data()

if df_raw.empty:
    st.stop()

# --- 3. 사이드바 - 검색 및 필터 옵션 ---
st.sidebar.header("🔍 검색 필터")

sido_list = sorted(df_raw["시도명"].dropna().unique().tolist())
selected_sido = st.sidebar.selectbox("지역(시/도) 선택", sido_list)

filtered_df = df_raw[df_raw["시도명"] == selected_sido].copy()

if dong_column:
    dong_list = ["전체"] + sorted(filtered_df[dong_column].dropna().unique().tolist())
    selected_dong = st.sidebar.selectbox("동 선택", dong_list)

    if selected_dong != "전체":
        filtered_df = filtered_df[filtered_df[dong_column] == selected_dong]

# 상단 모드 전환 옵션
laser_mode = st.checkbox("🔥 레이저 파괴 모드 활성화", value=False)

# --- 4. 일반 지표 카드 ---
convenience_count = len(filtered_df[filtered_df["상권업종소분류명"] == "편의점"])
cafe_count = len(filtered_df[filtered_df["상권업종소분류명"] == "카페"])
total_count = len(filtered_df)

col1, col2, col3 = st.columns(3)
col1.metric("🏪 편의점 수", f"{convenience_count:,} 개")
col2.metric("☕ 카페 수", f"{cafe_count:,} 개")
col3.metric("🏢 전체 매장 수", f"{total_count:,} 개")

st.markdown("---")

# --- 5. 지도 및 레이저 모드 분기 처리 ---
if filtered_df.empty:
    st.info("조건에 맞는 매장이 없습니다. 필터 옵션을 변경해 보세요.")
else:
    if laser_mode:
        st.warning("🎯 화면(지도)을 클릭해 보세요! 마우스 위치로 레이저가 쏴지며 주변 매장이 타서 소멸합니다.")
        
        # HTML/JS용 좌표 데이터 변환
        stores_data = []
        for _, row in filtered_df.iterrows():
            stores_data.append({
                "name": str(row["상호명"]),
                "type": str(row["상권업종소분류명"]),
                "lat": float(row["위도"]),
                "lng": float(row["경도"])
            })

        # Canvas 기반 레이저 애니메이션 인터랙티브 앱 (HTML/JS)
        html_code = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ margin: 0; overflow: hidden; background: #111; font-family: sans-serif; }}
                canvas {{ display: block; cursor: crosshair; }}
                #info {{
                    position: absolute; top: 10px; left: 10px; color: #fff;
                    background: rgba(0,0,0,0.7); padding: 8px 12px; border-radius: 5px;
                    pointer-events: none; font-size: 14px;
                }}
            </style>
        </head>
        <body>
            <div id="info">남은 매장: <span id="count">0</span>개 (클릭시 레이저 발사!)</div>
            <canvas id="canvas"></canvas>

            <script>
                const canvas = document.getElementById('canvas');
                const ctx = canvas.getContext('2d');
                const countEl = document.getElementById('count');

                canvas.width = window.innerWidth;
                canvas.height = 650;

                const rawStores = {json.dumps(stores_data)};

                // 경계 좌표 구하기
                let minLat = Infinity, maxLat = -Infinity, minLng = Infinity, maxLng = -Infinity;
                rawStores.forEach(s => {{
                    if(s.lat < minLat) minLat = s.lat;
                    if(s.lat > maxLat) maxLat = s.lat;
                    if(s.lng < minLng) minLng = s.lng;
                    if(s.lng > maxLng) maxLng = s.lng;
                }});

                // 화면 좌표 변환 (Padding 포함)
                const pad = 60;
                let stores = rawStores.map(s => {{
                    const x = pad + ((s.lng - minLng) / (maxLng - minLng || 1)) * (canvas.width - pad * 2);
                    const y = canvas.height - pad - ((s.lat - minLat) / (maxLat - minLat || 1)) * (canvas.height - pad * 2);
                    return {{
                        ...s, x, y,
                        alive: true,
                        burnProgress: 0 // 타들어가는 애니메이션 상태
                    }};
                }});

                let lasers = [];
                let particles = [];

                function draw() {{
                    // 어두운 배경 지도 느낌
                    ctx.fillStyle = '#181c24';
                    ctx.fillRect(0, 0, canvas.width, canvas.height);

                    // 그리드 선 그리대로 지도 분위기 연출
                    ctx.strokeStyle = '#2a3242';
                    ctx.lineWidth = 1;
                    for(let x=0; x<canvas.width; x+=50) {{
                        ctx.beginPath(); ctx.moveTo(x,0); ctx.lineTo(x, canvas.height); ctx.stroke();
                    }}
                    for(let y=0; y<canvas.height; y+=50) {{
                        ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(canvas.width, y); ctx.stroke();
                    }}

                    // 매장(점) 그리기 및 불타서 없어지는 연출
                    let activeCount = 0;
                    stores.forEach(s => {{
                        if(!s.alive) return;
                        activeCount++;

                        if(s.burning) {{
                            s.burnProgress += 0.05;
                            // 타들어갈 때 주황/빨강 폭발 파티클 생성
                            for(let i=0; i<3; i++) {{
                                particles.push({{
                                    x: s.x, y: s.y,
                                    vx: (Math.random()-0.5)*6,
                                    vy: (Math.random()-0.5)*6,
                                    life: 1.0,
                                    color: Math.random() > 0.5 ? '#ff4500' : '#ffa500'
                                }});
                            }}
                            if(s.burnProgress >= 1) {{
                                s.alive = false;
                            }}
                        }}

                        ctx.beginPath();
                        ctx.arc(s.x, s.y, s.type === '편의점' ? 5 : 6, 0, Math.PI * 2);
                        if(s.burning) {{
                            ctx.fillStyle = `rgba(255, 69, 0, ${{1 - s.burnProgress}})`;
                        }} else {{
                            ctx.fillStyle = s.type === '편의점' ? '#4da6ff' : '#ff9933';
                        }}
                        ctx.fill();

                        // 매장명 텍스트
                        ctx.fillStyle = 'rgba(255,255,255,0.6)';
                        ctx.font = '10px sans-serif';
                        ctx.fillText(s.name, s.x + 8, s.y + 3);
                    }});

                    countEl.innerText = activeCount;

                    // 레이저 그리기
                    lasers.forEach((l, index) => {{
                        ctx.beginPath();
                        ctx.moveTo(l.sx, l.sy);
                        ctx.lineTo(l.ex, l.ey);
                        ctx.strokeStyle = '#00ffff';
                        ctx.lineWidth = l.width;
                        ctx.shadowColor = '#00ffff';
                        ctx.shadowBlur = 15;
                        ctx.stroke();
                        ctx.shadowBlur = 0;

                        l.width *= 0.7; // 레이저 서서히 사라짐
                        if(l.width < 0.5) lasers.splice(index, 1);
                    }});

                    // 파티클(재/파편) 애니메이션
                    particles.forEach((p, index) => {{
                        p.x += p.vx;
                        p.y += p.vy;
                        p.life -= 0.03;
                        if(p.life <= 0) {{
                            particles.splice(index, 1);
                        }} else {{
                            ctx.beginPath();
                            ctx.arc(p.x, p.y, 2, 0, Math.PI*2);
                            ctx.fillStyle = p.color;
                            ctx.globalAlpha = p.life;
                            ctx.fill();
                            ctx.globalAlpha = 1.0;
                        }}
                    }});

                    requestAnimationFrame(draw);
                }}

                // 클릭 시 마우스 위치로 레이저 발사 및 피격 판정
                canvas.addEventListener('click', (e) => {{
                    const rect = canvas.getBoundingClientRect();
                    const targetX = e.clientX - rect.left;
                    const targetY = e.clientY - rect.top;

                    // 하늘(위쪽)에서 타겟으로 궤적 레이저 발사
                    lasers.push({{
                        sx: targetX + (Math.random() - 0.5) * 200,
                        sy: 0,
                        ex: targetX,
                        ey: targetY,
                        width: 12
                    }});

                    // 타격 위치 주변(반경 60px) 매장 불태우기
                    stores.forEach(s => {{
                        if(s.alive && !s.burning) {{
                            const dist = Math.hypot(s.x - targetX, s.y - targetY);
                            if(dist < 60) {{
                                s.burning = true;
                            }}
                        }}
                    }});
                }});

                draw();
            </script>
        </body>
        </html>
        """
        components.html(html_code, height=670)

    else:
        # 기존 Plotly 기반 일반 지도 표시
        import plotly.express as px
        color_map = {"편의점": "#1f77b4", "카페": "#ff7f0e"}

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
            "zoom": 10,
        }

        if hasattr(px, "scatter_map"):
            fig = px.scatter_map(**map_kwargs, map_style="open-street-map")
        else:
            fig = px.scatter_mapbox(**map_kwargs, mapbox_style="open-street-map")

        fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0}, legend_title_text="업종 구분")
        st.plotly_chart(fig, use_container_width=True)
