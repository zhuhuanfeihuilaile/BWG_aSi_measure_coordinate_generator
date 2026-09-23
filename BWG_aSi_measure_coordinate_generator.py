import streamlit as st
import numpy as np
import pandas as pd
from scipy.optimize import curve_fit
import io

st.set_page_config(page_title="6英寸晶圆坐标校准与生成", page_icon="🎯", layout="centered")

st.title("🎯 6英寸晶圆全盘测试坐标校准工具（通用版）")
st.markdown("请输入实测点的**网格索引 (i, j)** 以及对应的**实测物理坐标 (X, Y)**（支持 3 到 6 个点）。")

st.subheader("📝 输入网格索引与实测坐标")

# 默认提供 6 行，用户可以自由修改每行的网格索引和坐标
default_data = [
    {"name": "点 1", "i": 1, "j": 0, "x": 1.80687, "y": -1.37350},
    {"name": "点 2", "i": -1, "j": 0, "x": -2.59025, "y": -1.40250},
    {"name": "点 3", "i": 0, "j": -1, "x": -0.37825, "y": -3.58650},
    {"name": "点 4", "i": 0, "j": 0, "x": -0.39175, "y": -1.38775},
    {"name": "点 5", "i": 2, "j": 1, "x": 3.99163, "y": 0.83912},
    {"name": "点 6", "i": -2, "j": 3, "x": -4.83012, "y": 5.18000}
]

# 表头
col_h1, col_h2, col_h3, col_h4, col_h5 = st.columns([1, 1, 1, 1.2, 1.2])
with col_h1: st.markdown("**点位**")
with col_h2: st.markdown("**网格 X (i)**")
with col_h3: st.markdown("**网格 Y (j)**")
with col_h4: st.markdown("**实测 X (cm)**")
with col_h5: st.markdown("**实测 Y (cm)**")

user_points = []

for idx, def_val in enumerate(default_data):
    c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 1.2, 1.2])
    with c1:
        st.text(def_val["name"])
    with c2:
        i_val = st.text_input(f"i_{idx}", value=str(def_val["i"]), label_visibility="collapsed")
    with c3:
        j_val = st.text_input(f"j_{idx}", value=str(def_val["j"]), label_visibility="collapsed")
    with c4:
        x_val = st.text_input(f"x_{idx}", value=str(def_val["x"]), label_visibility="collapsed")
    with c5:
        y_val = st.text_input(f"y_{idx}", value=str(def_val["y"]), label_visibility="collapsed")

    # 只要这行填了实测坐标，就将其纳入计算
    if x_val.strip() and y_val.strip() and i_val.strip() and j_val.strip():
        try:
            user_points.append({
                'i': float(i_val),
                'j': float(j_val),
                'x': float(x_val),
                'y': float(y_val)
            })
        except ValueError:
            pass

if st.button("🚀 开始计算并生成 Excel 坐标表", type="primary", use_container_width=True):
    if len(user_points) < 3:
        st.error("❌ 至少需要完整填写 3 个有效的点（包含网格索引和实测坐标）才能进行拟合！")
    else:
        try:
            i_arr = np.array([p['i'] for p in user_points])
            j_arr = np.array([p['j'] for p in user_points])
            x_meas = np.array([p['x'] for p in user_points])
            y_meas = np.array([p['y'] for p in user_points])


            def wafer_model(coords, x0, y0, a, b):
                i, j = coords
                x = x0 + i * a - j * b
                y = y0 + i * b + j * a
                return np.concatenate([x, y])


            # 初始猜测值
            p0 = [x_meas[0], y_meas[0], 2.2, 0.0]
            popt, _ = curve_fit(wafer_model, (i_arr, j_arr), np.concatenate([x_meas, y_meas]), p0=p0)

            x0_f, y0_f, a_f, b_f = popt
            fitted_pitch = np.sqrt(a_f ** 2 + b_f ** 2)
            theta_deg = np.degrees(np.arctan2(b_f, a_f))

            # 生成全盘坐标 (半径 <= 7.62cm)
            coords_final = []
            for i in range(-5, 6):
                for j in range(-5, 6):
                    x = x0_f + i * a_f - j * b_f
                    y = y0_f + i * b_f + j * a_f
                    dist = np.sqrt(x ** 2 + y ** 2)
                    if dist <= 7.62:
                        coords_final.append({
                            '列索引 (X_idx)': i,
                            '行索引 (Y_idx)': j,
                            'X 坐标 (cm)': round(x, 4),
                            'Y 坐标 (cm)': round(y, 4),
                            '距圆心距离 (cm)': round(dist, 4)
                        })
            df_final = pd.DataFrame(coords_final)

            # 展示计算结果看板
            st.success("✨ 拟合计算成功！")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("拟合周期 (Pitch)", f"{fitted_pitch:.4f} cm")
            m2.metric("旋转偏角 (Angle)", f"{theta_deg:.2f}°")
            m3.metric("原点坐标 (X0, Y0)", f"({x0_f:.2f}, {y0_f:.2f})")
            m4.metric("有效 Die 总数", f"{len(df_final)} 个")

            # 在内存中生成 Excel 文件供下载
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_final.to_excel(writer, index=False, sheet_name='晶圆全盘坐标')
            excel_data = output.getvalue()

            st.download_button(
                label="📥 点击下载生成的 Excel 坐标表",
                data=excel_data,
                file_name="wafer_coordinates_custom_grid.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

            # 展示表格前几行预览
            st.subheader("👀 生成的坐标预览（部分）")
            st.dataframe(df_final.head(10), use_container_width=True)

        except Exception as e:
            st.error(f"计算过程中发生错误: {str(e)}")
