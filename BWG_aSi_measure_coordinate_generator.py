import streamlit as st
import numpy as np
import pandas as pd
from scipy.optimize import curve_fit
import io

st.set_page_config(page_title="6英寸晶圆坐标校准与生成", page_icon="🎯", layout="centered")

st.title("🎯 6英寸晶圆全盘测试坐标校准工具")
st.markdown("请输入实测点坐标（支持 3 到 6 个点），系统将自动进行最小二乘法拟合，并生成全盘 Die 坐标 Excel 表格。")

# 创建输入表单
st.subheader("📝 输入实测点坐标 (cm)")
col1, col2, col3 = st.columns([1, 1, 1])

with col1:
    st.markdown("**点位名称**")
with col2:
    st.markdown("**实测 X 坐标**")
with col3:
    st.markdown("**实测 Y 坐标**")

# 默认点位及网格映射
default_points = [
    ("P1 (网格 1,0)", 1.80687, -1.37350),
    ("P2 (网格 -1,0)", -2.59025, -1.40250),
    ("P3 (网格 0,-1)", -0.37825, -3.58650),
    ("P4 (网格 0,0)", -0.39175, -1.38775),
    ("P5 (网格 2,1)", 3.99163, 0.83912),
    ("P6 (网格 -2,3)", -4.83012, 5.18000)
]

indices_map = {
    0: (1, 0),
    1: (-1, 0),
    2: (0, -1),
    3: (0, 0),
    4: (2, 1),
    5: (-2, 3)
}

user_points = []
input_x, input_y = [], []

for i, (p_name, def_x, def_y) in enumerate(default_points):
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        st.text(p_name)
    with c2:
        val_x = st.text_input(f"X_{i}", value=str(def_x), label_visibility="collapsed")
    with c3:
        val_y = st.text_input(f"Y_{i}", value=str(def_y), label_visibility="collapsed")

    # 允许过滤掉没填的行（实现灵活输入 3~6 个点）
    if val_x.strip() and val_y.strip():
        user_points.append({
            'index': i,
            'grid': indices_map[i],
            'x': float(val_x),
            'y': float(val_y)
        })

if st.button("🚀 开始计算并生成 Excel 坐标表", type="primary", use_container_width=True):
    if len(user_points) < 3:
        st.error("❌ 至少需要输入 3 个有效的实测点才能进行网格拟合！")
    else:
        try:
            i_arr = np.array([p['grid'][0] for p in user_points])
            j_arr = np.array([p['grid'][1] for p in user_points])
            x_meas = np.array([p['x'] for p in user_points])
            y_meas = np.array([p['y'] for p in user_points])


            def wafer_model(coords, x0, y0, a, b):
                i, j = coords
                x = x0 + i * a - j * b
                y = y0 + i * b + j * a
                return np.concatenate([x, y])


            # 初始猜测值使用第 4 个点或第一个点
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

            # 显示计算结果看板
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
                file_name="wafer_coordinates_web_calibrated.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

            # 展示表格前几行预览
            st.subheader("👀 生成的坐标预览（部分）")
            st.dataframe(df_final.head(10), use_container_width=True)

        except Exception as e:
            st.error(f"计算过程中发生错误: {str(e)}")