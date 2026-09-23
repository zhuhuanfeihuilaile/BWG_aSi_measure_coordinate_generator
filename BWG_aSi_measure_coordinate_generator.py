import streamlit as st
import numpy as np
import pandas as pd
from scipy.optimize import curve_fit
import io

st.set_page_config(page_title="6英寸晶圆坐标智能校准与生成", page_icon="🎯", layout="centered")

st.title("🎯 6英寸晶圆全盘测试坐标校准工具（智能识别版）")
st.markdown("请输入 **3 到 6 个点的实测 X、Y 坐标**（输入框默认留空，直接填入您的实测数据即可），系统将自动识别网格并生成全盘坐标！")

st.subheader("📝 输入实测物理坐标 (cm)")
col1, col2, col3 = st.columns([1, 1.5, 1.5])
with col1: st.markdown("**测点编号**")
with col2: st.markdown("**实测 X 坐标 (cm)**")
with col3: st.markdown("**实测 Y 坐标 (cm)**")

# 初始化 6 个空的输入行
user_raw_points = []
for idx in range(6):
    c1, c2, c3 = st.columns([1, 1.5, 1.5])
    with c1:
        st.text(f"点 {idx + 1}")
    with c2:
        x_val = st.text_input(f"x_{idx}", value="", placeholder="例如: 1.8068", label_visibility="collapsed")
    with c3:
        y_val = st.text_input(f"y_{idx}", value="", placeholder="例如: -1.3735", label_visibility="collapsed")
    
    # 只有用户填写了内容的行才会被采纳
    if x_val.strip() and y_val.strip():
        try:
            user_raw_points.append((float(x_val), float(y_val)))
        except ValueError:
            pass

if st.button("🚀 自动识别网格并生成 Excel 坐标表", type="primary", use_container_width=True):
    if len(user_raw_points) < 3:
        st.error("❌ 至少需要完整输入 3 个有效的坐标点才能进行智能识别与拟合！")
    else:
        try:
            pts = np.array(user_raw_points)
            x_meas = pts[:, 0]
            y_meas = pts[:, 1]
            
            # --- 核心：自动识别网格索引 (i, j) ---
            x_center_guess = np.mean(x_meas)
            y_center_guess = np.mean(y_meas)
            nominal_pitch = 2.2
            
            i_arr = np.round((x_meas - x_center_guess) / nominal_pitch).astype(int)
            j_arr = np.round((y_meas - y_center_guess) / nominal_pitch).astype(int)
            
            if len(np.unique(list(zip(i_arr, j_arr)))) < len(user_raw_points):
                st.warning("⚠️ 注意：部分点计算出的网格索引重复，请确保输入的随机点空间跨度足够大。")

            # --- 最小二乘法精确拟合 ---
            def wafer_model(coords, x0, y0, a, b):
                i, j = coords
                x = x0 + i * a - j * b
                y = y0 + i * b + j * a
                return np.concatenate([x, y])
                
            p0 = [x_center_guess, y_center_guess, 2.2, 0.0]
            popt, _ = curve_fit(wafer_model, (i_arr, j_arr), np.concatenate([x_meas, y_meas]), p0=p0)
                              
            x0_f, y0_f, a_f, b_f = popt
            fitted_pitch = np.sqrt(a_f**2 + b_f**2)
            theta_deg = np.degrees(np.arctan2(b_f, a_f))
            
            # 生成全盘坐标 (半径 <= 7.62cm)
            coords_final = []
            for i in range(-5, 6):
                for j in range(-5, 6):
                    x = x0_f + i * a_f - j * b_f
                    y = y0_f + i * b_f + j * a_f
                    dist = np.sqrt(x**2 + y**2)
                    if dist <= 7.62:
                        coords_final.append({
                            '列索引 (X_idx)': i,
                            '行索引 (Y_idx)': j,
                            'X 坐标 (cm)': round(x, 4),
                            'Y 坐标 (cm)': round(y, 4),
                            '距圆心距离 (cm)': round(dist, 4)
                        })
            df_final = pd.DataFrame(coords_final)
            
            # 展示计算结果与识别出的网格
            st.success("✨ 智能网格识别与拟合计算成功！")
            
            recognized_df = pd.DataFrame({
                '实测 X': x_meas,
                '实测 Y': y_meas,
                '自动识别网格 i': i_arr,
                '自动识别网格 j': j_arr
            })
            with st.expander("🔍 查看系统自动识别的网格对应关系"):
                st.dataframe(recognized_df, use_container_width=True)
            
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("拟合周期 (Pitch)", f"{fitted_pitch:.4f} cm")
            m2.metric("旋转偏角 (Angle)", f"{theta_deg:.2f}°")
            m3.metric("原点坐标 (X0, Y0)", f"({x0_f:.2f}, {y0_f:.2f})")
            m4.metric("有效 Die 总数", f"{len(df_final)} 个")
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_final.to_excel(writer, index=False, sheet_name='晶圆全盘坐标')
            excel_data = output.getvalue()
            
            st.download_button(
                label="📥 点击下载生成的 Excel 坐标表",
                data=excel_data,
                file_name="wafer_auto_recognized_coordinates.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
            
            st.subheader("👀 生成的坐标预览（部分）")
            st.dataframe(df_final.head(10), use_container_width=True)
            
        except Exception as e:
            st.error(f"计算过程中发生错误: {str(e)}")
