import streamlit as st
import pandas as pd
import numpy as np
import json
import streamlit.components.v1 as components

# --- 1. Page Configuration ---
st.set_page_config(
    page_title="Store Map & Laser Destructor",
    page_icon="💥",
    layout="wide"
)

st.title("📍 Store Map Explorer & Laser Strike Simulator")
st.caption("Filter stores or toggle 'Laser Mode' in the sidebar to incinerate locations on click!")

# --- 2. Data Loading & Preprocessing ---
@st.cache_data
def load_data():
    try:
        df = pd.read_csv("store.csv")
    except FileNotFoundError:
        try:
            df = pd.read_csv("store_filtered.csv")
        except FileNotFoundError:
            st.error("Data file ('store.csv' or 'store_filtered.csv') not found.")
            return pd.DataFrame(), None

    # Filter categories
    df = df[df["상권업종소분류명"].isin(["편의점", "카페"])].copy()

    # Clean Lat/Lon
    df["위도"] = pd.to_numeric(df["위도"], errors="coerce")
    df["경도"] = pd.to_numeric(df["경도"], errors="coerce")
    df = df.dropna(subset=["위도", "경도"])

    # Detect Dong column
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

# --- 3. Sidebar - Filtering & Laser Controls ---
st.sidebar.header("🔍 Location Filter")

sido_list = sorted(df_raw["시도명"].dropna().unique().tolist())
selected_sido = st.sidebar.selectbox("Select Region (Sido)", sido_list)

filtered_df = df_raw[df_raw["시도명"] == selected_sido].copy()

if dong_column:
    dong_list = ["All"] + sorted(filtered_df[dong_column].dropna().unique().tolist())
    selected_dong = st.sidebar.selectbox("Select Neighborhood (Dong)", dong_list)

    if selected_dong != "All":
        filtered_df = filtered_df[filtered_df[dong_column] == selected_dong]

# Mode Toggle & Laser Sliders
st.sidebar.markdown("---")
laser_mode = st.sidebar.checkbox("🔥 Enable Laser Destruction Mode", value=False)

strike_radius = 60
particle_count = 5

if laser_mode:
    st.sidebar.subheader("💥 Laser Strike Controls")
    strike_radius = st.sidebar.slider("Strike Blast Radius (px)", min_value=20, max_value=200, value=80, step=10)
    particle_count = st.sidebar.slider("Explosion Intensity (Particles)", min_value=1, max_value=20, value=8, step=1)

# --- 4. Metrics Cards ---
convenience_count = len(filtered_df[filtered_df["상권업종소분류명"] == "편의점"])
cafe_count = len(filtered_df[filtered_df["상권업종소분류명"] == "카페"])
total_count = len(filtered_df)

col1, col2, col3 = st.columns(3)
col1.metric("🏪 Convenience Stores", f"{convenience_count:,}")
col2.metric("☕ Cafes", f"{cafe_count:,}")
col3.metric("🏢 Total Stores", f"{total_count:,}")

st.markdown("---")

# --- 5. Map & Interactive Canvas ---
if filtered_df.empty:
    st.info("No stores match the selected criteria.")
else:
    if laser_mode:
        st.warning(f"🎯 Click anywhere on the map! Blast Radius: {strike_radius}px | Particles per frame: {particle_count}")
        
        # Prepare data for JS
        stores_data = []
        for _, row in filtered_df.iterrows():
            stores_data.append({
                "name": str(row["상호명"]),
                "type": str(row["상권업종소분류명"]),
                "lat": float(row["위도"]),
                "lng": float(row["경도"])
            })

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
            <div id="info">Remaining Stores: <span id="count">0</span> (Click to fire laser!)</div>
            <canvas id="canvas"></canvas>

            <script>
                const canvas = document.getElementById('canvas');
                const ctx = canvas.getContext('2d');
                const countEl = document.getElementById('count');

                canvas.width = window.innerWidth;
                canvas.height = 650;

                const rawStores = {json.dumps(stores_data)};
                const blastRadius = {strike_radius};
                const particleIntensity = {particle_count};

                // Normalize bounding coordinates
                let minLat = Infinity, maxLat = -Infinity, minLng = Infinity, maxLng = -Infinity;
                rawStores.forEach(s => {{
                    if(s.lat < minLat) minLat = s.lat;
                    if(s.lat > maxLat) maxLat = s.lat;
                    if(s.lng < minLng) minLng = s.lng;
                    if(s.lng > maxLng) maxLng = s.lng;
                }});

                const pad = 60;
                let stores = rawStores.map(s => {{
                    const x = pad + ((s.lng - minLng) / (maxLng - minLng || 1)) * (canvas.width - pad * 2);
                    const y = canvas.height - pad - ((s.lat - minLat) / (maxLat - minLat || 1)) * (canvas.height - pad * 2);
                    return {{
                        ...s, x, y,
                        alive: true,
                        burnProgress: 0
                    }};
                }});

                let lasers = [];
                let particles = [];
                let reticles = [];

                function draw() {{
                    ctx.fillStyle = '#181c24';
                    ctx.fillRect(0, 0, canvas.width, canvas.height);

                    // Grid lines
                    ctx.strokeStyle = '#2a3242';
                    ctx.lineWidth = 1;
                    for(let x=0; x<canvas.width; x+=50) {{
                        ctx.beginPath(); ctx.moveTo(x,0); ctx.lineTo(x, canvas.height); ctx.stroke();
                    }}
                    for(let y=0; y<canvas.height; y+=50) {{
                        ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(canvas.width, y); ctx.stroke();
                    }}

                    // Draw blast area reticles
                    reticles.forEach((r, idx) => {{
                        ctx.beginPath();
                        ctx.arc(r.x, r.y, blastRadius * r.scale, 0, Math.PI * 2);
                        ctx.strokeStyle = `rgba(255, 0, 0, ${{r.alpha}})`;
                        ctx.lineWidth = 2;
                        ctx.stroke();

                        r.scale += 0.05;
                        r.alpha -= 0.04;
                        if(r.alpha <= 0) reticles.splice(idx, 1);
                    }});

                    // Draw store nodes & burning animation
                    let activeCount = 0;
                    stores.forEach(s => {{
                        if(!s.alive) return;
                        activeCount++;

                        if(s.burning) {{
                            s.burnProgress += 0.04;
                            
                            // Spawn particles based on slider intensity
                            for(let i=0; i<particleIntensity; i++) {{
                                particles.push({{
                                    x: s.x, y: s.y,
                                    vx: (Math.random()-0.5) * (particleIntensity * 1.2),
                                    vy: (Math.random()-0.5) * (particleIntensity * 1.2),
                                    life: 1.0,
                                    color: Math.random() > 0.3 ? '#ff4500' : '#ffff00'
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

                        ctx.fillStyle = 'rgba(255,255,255,0.6)';
                        ctx.font = '10px sans-serif';
                        ctx.fillText(s.name, s.x + 8, s.y + 3);
                    }});

                    countEl.innerText = activeCount;

                    // Draw incoming laser strike beam
                    lasers.forEach((l, index) => {{
                        ctx.beginPath();
                        ctx.moveTo(l.sx, l.sy);
                        ctx.lineTo(l.ex, l.ey);
                        ctx.strokeStyle = '#00ffff';
                        ctx.lineWidth = l.width;
                        ctx.shadowColor = '#00ffff';
                        ctx.shadowBlur = 20;
                        ctx.stroke();
                        ctx.shadowBlur = 0;

                        l.width *= 0.75;
                        if(l.width < 0.5) lasers.splice(index, 1);
                    }});

                    // Update & draw particles
                    particles.forEach((p, index) => {{
                        p.x += p.vx;
                        p.y += p.vy;
                        p.life -= 0.025;
                        if(p.life <= 0) {{
                            particles.splice(index, 1);
                        }} else {{
                            ctx.beginPath();
                            ctx.arc(p.x, p.y, Math.random()*2 + 1, 0, Math.PI*2);
                            ctx.fillStyle = p.color;
                            ctx.globalAlpha = p.life;
                            ctx.fill();
                            ctx.globalAlpha = 1.0;
                        }}
                    }});

                    requestAnimationFrame(draw);
                }}

                canvas.addEventListener('click', (e) => {{
                    const rect = canvas.getBoundingClientRect();
                    const targetX = e.clientX - rect.left;
                    const targetY = e.clientY - rect.top;

                    // Laser beam
                    lasers.push({{
                        sx: targetX + (Math.random() - 0.5) * 300,
                        sy: 0,
                        ex: targetX,
                        ey: targetY,
                        width: 15
                    }});

                    // Visual shockwave ring matching blast radius
                    reticles.push({{ x: targetX, y: targetY, scale: 0.1, alpha: 1.0 }});

                    // Trigger stores inside blastRadius
                    stores.forEach(s => {{
                        if(s.alive && !s.burning) {{
                            const dist = Math.hypot(s.x - targetX, s.y - targetY);
                            if(dist <= blastRadius) {{
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
        # Standard Plotly Map
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

        fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0}, legend_title_text="Category")
        st.plotly_chart(fig, use_container_width=True)
