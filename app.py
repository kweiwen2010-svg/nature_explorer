import streamlit as st
from supabase import create_client
import requests

# 1. 頁面基本設定
st.set_page_config(
    page_title="大自然觀察筆記",
    page_icon="🌿",
    layout="centered"
)

st.title("🌿 大自然隨身觀察筆記")
st.write("拍下你的植物、鳥類或岩石，讓 AI 幫你辨識並永久記錄到雲端！")

# 2. 讀取安全金鑰 (secrets.toml)
try:
    plantnet_key = st.secrets["PLANTNET_API_KEY"]
    gemini_key = st.secrets["GEMINI_API_KEY"]
    supabase_url = st.secrets["SUPABASE_URL"]
    supabase_key = st.secrets["SUPABASE_KEY"]
    
    # 建立 Supabase 連線
    supabase = create_client(supabase_url, supabase_key)
except Exception as e:
    st.error(f"❌ 讀取設定發生錯誤：{e}")

# 3. 拍照或上傳圖片介面
uploaded_file = st.file_uploader("選擇或拍攝一張大自然照片", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    # 顯示使用者上傳的照片
    st.image(uploaded_file, caption="您上傳的照片", use_container_width=True)
    
    # 選擇分類
    category = st.selectbox("這是一張什麼照片？", ["🌿 植物", "🦅 鳥類", "🪨 岩石"])
    
    # 輸入個人備註
    notes = st.text_area("個人備註（例如：在公園散步看到的）", "")
    
    if st.button("🚀 開始辨識並上傳紀錄"):
        with st.spinner("AI 正在努力辨識並上傳至雲端中..."):
            try:
                result_name = "未命名"
                
                # 如果選擇的是「植物」，呼叫 PlantNet API 進行辨識
                if "植物" in category:
                    url = f"https://my-api.plantnet.org/v2/identify/all?api-key={plantnet_key}"
                    files = [('images', (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type))]
                    data = {'organs': ['leaf']}
                    
                    response = requests.post(url, files=files, data=data)
                    res_json = response.json()
                    
                    if response.status_code == 200 and 'results' in res_json and len(res_json['results']) > 0:
                        best_match = res_json['results'][0]
                        species = best_match['species'].get('scientificNameWithoutAuthor', '未知植物')
                        
                        # 試著抓取中文俗名
                        common_names = best_match['species'].get('commonNames', [])
                        chinese_name = ""
                        for name in common_names:
                            if any('\u4e00' <= c <= '\u9fff' for c in name):
                                chinese_name = name
                                break
                        
                        # 組合中文與學名
                        if chinese_name:
                            result_name = f"{chinese_name} ({species})"
                        else:
                            result_name = species
                            
                        score = round(best_match['score'] * 100, 1)
                        result_name = f"{result_name} [準確度: {score}%]"
                    else:
                        result_name = "PlantNet 無法辨識此植物"
                else:
                    result_name = f"{category}辨識（即將解鎖 Gemini AI）"

                # 準備寫入 Supabase 資料庫
                data_to_insert = {
                    "category": category,
                    "result_name": result_name,
                    "notes": notes
                }
                
                supabase.table("observations").insert(data_to_insert).execute()
                
                st.success(f"🎉 辨識成功！結果：{result_name}")
                st.info("✅ 紀錄已成功寫入 Supabase 雲端資料庫！")
                
            except Exception as e:
                st.error(f"❌ 處理過程中發生錯誤：{e}")

# 4. 網頁即時歷史紀錄區塊
st.divider()
st.subheader("📜 歷史觀察紀錄")

if st.button("🔄 重新載入歷史紀錄"):
    st.rerun()

try:
    # 從 Supabase 抓取資料，依照 id 倒序排序（最新的在最上面）
    response = supabase.table("observations").select("*").order("id", desc=True).execute()
    records = response.data
    
    if records and len(records) > 0:
        for item in records:
            with st.container(border=True):
                st.markdown(f"**分類：** {item.get('category', '未分類')}")
                st.markdown(f"**辨識結果：** `{item.get('result_name', '無')}`")
                if item.get('notes'):
                    st.markdown(f"**備註：** {item.get('notes')}")
                st.caption(f"記錄時間編號 ID: {item.get('id')}")
    else:
        st.info("目前還沒有任何歷史紀錄，趕快上傳第一張照片吧！")
except Exception as e:
    st.warning(f"目前無法讀取歷史紀錄：{e}")