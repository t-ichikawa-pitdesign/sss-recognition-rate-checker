import streamlit as st
import pymysql
import os
from datetime import datetime, date, time as dtime

def get_connection():
    return pymysql.connect(
        host=os.environ['DB_HOST'],
        user=os.environ['DB_USER'],
        password=os.environ['DB_PASSWORD'],
        database=os.environ['DB_NAME'],
        cursorclass=pymysql.cursors.DictCursor,
        charset="utf8mb4"
    )

st.set_page_config(layout="wide")
st.title("ナンバープレート画像補正アプリ")

with st.sidebar:
    st.header("期間を指定")
    start_date = st.date_input("開始日", date.today())
    start_time = st.time_input("開始時間", dtime.min)
    end_date = st.date_input("終了日", date.today())
    end_time = st.time_input("終了時間", dtime.max)
    filter_unchecked = st.checkbox("未チェックのみ表示", value=False)

    start_dt = datetime.combine(start_date, start_time)
    end_dt = datetime.combine(end_date, end_time)
    st.session_state["start_dt"] = start_dt
    st.session_state["end_dt"] = end_dt

    if st.button("検索"):
        st.session_state["search_triggered"] = True

if st.session_state.get("search_triggered", False):
    conn = get_connection()

    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT COUNT(*) AS checked,
                   SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) AS correct
            FROM analysis_results
            WHERE analyzed_at BETWEEN %s AND %s
              AND correct_plate_number IS NOT NULL
        """, (st.session_state['start_dt'], st.session_state['end_dt']))
        stats = cursor.fetchone()
        checked = stats['checked'] or 0
        correct = stats['correct'] or 0
        recognition_rate = (correct / checked * 100) if checked > 0 else 0
        st.session_state['recognition_rate'] = recognition_rate

    with st.sidebar:
        st.markdown("---")
        st.markdown(f"### 🔍 認識率: <span style='color:limegreen; font-size: 28px;'>{recognition_rate:.1f}%</span>", unsafe_allow_html=True)

    with conn.cursor() as cursor:
        sql = """
        SELECT * FROM analysis_results
        WHERE analyzed_at BETWEEN %s AND %s
        """
        if filter_unchecked:
            sql += " AND is_correct IS NULL AND correct_plate_number IS NULL"
        sql += " ORDER BY analyzed_at DESC LIMIT 100"
        cursor.execute(sql, (st.session_state['start_dt'], st.session_state['end_dt']))
        results = cursor.fetchall()

    for row in results:
        updated = any([
            row.get('correct_plate_place'),
            row.get('correct_plate_class'),
            row.get('correct_plate_hiragana'),
            row.get('correct_plate_number'),
            row.get('is_correct')
        ])

        container = st.container()
        if updated:
            container.markdown("<div style='background-color: #f0f0f0; padding: 10px; border-radius: 5px;'>", unsafe_allow_html=True)

        container.markdown(f"## ID: {row['id']} - {row['name']} - 車室: {row['lot']}")

        image_area, form_col = container.columns([3, 2.2], gap="small")

        with image_area:
            inner_img_col1, inner_img_col2 = st.columns([1.2, 1])
            with inner_img_col1:
                st.image(row['vehicle_path'], caption="車両画像")
            with inner_img_col2:
                st.image(row['plate_path'], caption="プレート画像")
                st.markdown(f"Topスコア: {row.get('top_score', '')}")
                st.markdown(f"Bottomスコア: {row.get('bottom_score', '')}")

        with form_col:
            with st.form(f"correct_form_{row['id']}"):
                st.markdown("### 認識結果")

                def display_label_value(label, value):
                    st.markdown(f"<span style='color: gray;'>{label}</span>", unsafe_allow_html=True)
                    st.markdown(f"<div style='font-weight: bold; font-size: 1.2em;'>{value}</div>", unsafe_allow_html=True)

                # 地域
                c1, c2 = st.columns(2)
                with c1:
                    display_label_value("地域", row['plate_place'])
                with c2:
                    c_place = st.text_input("地域", value=row.get("correct_plate_place") or row.get("plate_place") or "")

                # 分類番号
                c3, c4 = st.columns(2)
                with c3:
                    display_label_value("分類番号", row['plate_class'])
                with c4:
                    c_class = st.text_input("分類番号", value=row.get("correct_plate_class") or row.get("plate_class") or "")

                # ひらがな
                c5, c6 = st.columns(2)
                with c5:
                    display_label_value("ひらがな", row['plate_hiragana'])
                with c6:
                    c_hira = st.text_input("ひらがな", value=row.get("correct_plate_hiragana") or row.get("plate_hiragana") or "")

                # 車番
                c7, c8 = st.columns(2)
                with c7:
                    display_label_value("車番", row['plate_number'])
                with c8:
                    c_number = st.text_input("車番", value=row.get("correct_plate_number") or row.get("plate_number") or "")

                # 全桁一致 & 保存
                col_check, col_button = st.columns([1, 1])
                with col_check:
                    is_correct = st.checkbox("全桁一致", value=row.get("is_correct", False))
                with col_button:
                    submitted = st.form_submit_button("保存")

                if submitted:
                    update_sql = """
                    UPDATE analysis_results
                    SET correct_plate_place = %s,
                        correct_plate_class = %s,
                        correct_plate_hiragana = %s,
                        correct_plate_number = %s,
                        is_correct = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """
                    with conn.cursor() as cursor2:
                        cursor2.execute(update_sql, (
                            c_place, c_class, c_hira, c_number,
                            is_correct, row['id']
                        ))
                        conn.commit()

                    # 認識率再取得
                    with conn.cursor() as cursor3:
                        cursor3.execute("""
                            SELECT COUNT(*) AS checked,
                                   SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) AS correct
                            FROM analysis_results
                            WHERE analyzed_at BETWEEN %s AND %s
                              AND is_correct IS NOT NULL
                        """, (st.session_state['start_dt'], st.session_state['end_dt']))
                        stats = cursor3.fetchone()
                        checked = stats['checked'] or 0
                        correct = stats['correct'] or 0
                        st.session_state['recognition_rate'] = (correct / checked * 100) if checked > 0 else 0

                    st.success("保存しました ✅")

        if updated:
            container.markdown("</div>", unsafe_allow_html=True)
