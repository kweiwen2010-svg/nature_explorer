import streamlit as st
import requests
from supabase import create_client
import google.generativeai as genai
from PIL import Image, ImageOps

# 網頁基礎設定
st.set_page_config(page_title="大自然隨身觀察筆記", page_icon="🌿")

st.title("🌿 大自然隨身觀察筆記")
st.write("拍下你的植物、鳥類或岩石，讓 AI 幫你辨識並永久記錄到雲端！")

# ================= 1. 讀取金鑰與連線設定 =================
plantnet_api_key = st.secrets["PLANTNET_API_KEY"]
gemini_api_key = st.secrets["GEMINI_API_KEY"]
supabase_url = st.secrets["SUPABASE_URL"]
supabase_key = st.secrets["SUPABASE_KEY"]

# 初始化 Supabase 連線
@st.cache_resource
def init_supabase():
    return create_client(supabase_url, supabase_key)
supabase = init_supabase()

# 初始化 Gemini AI
genai.configure(api_key=gemini_api_key)
model = genai.GenerativeModel('gemini-1.5-flash')


# ================= 2. 上傳與辨識區塊 =================
category = st.radio("選擇你要記錄的種類：", ["植物", "鳥類", "岩石"], horizontal=True)
uploaded_file = st.file_uploader("選擇或拍攝一張大自然照片", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    # 自動將手機上傳旋轉過的照片轉正
    image = Image.open(uploaded_file)
    image = ImageOps.exif_transpose(image)
    
    # 顯示轉正後的圖片
    st.image(image, caption="上傳的圖片", use_container_width=True)
    
    if st.button("🚀 開始辨識並上傳紀錄"):
        result_text = ""
        
        # --- (A) 植物辨識 (PlantNet 查學名 + Gemini 寫簡介) ---
        if category == "植物":
            with st.spinner("PlantNet 正在努力辨識這株植物..."):
                api_endpoint = f"https://my-api.plantnet.org/v2/identify/all?api-key={plantnet_api_key}"
                
                # 為了傳送給 PlantNet API，我們將轉正後的 image 暫存成位元組
                import io
                img_byte_arr = io.BytesIO()
                image.save(img_byte_arr, format='JPEG')
                img_byte_arr = img_byte_arr.getvalue()
                
                files = [('images', ('uploaded_image.jpg', img_byte_arr))]
                
                try:
                    req = requests.post(api_endpoint, files=files)
                    json_result = req.json()
                    
                    if 'results' in json_result and len(json_result['results']) > 0:
                        best_match = json_result['results'][0]
                        species_name = best_match['species']['scientificNameWithoutAuthor']
                        score = best_match['score'] * 100
                        
                        initial_result = f"{species_name} [準確度: {score:.1f}%]"
                        
                        with st.spinner("Gemini 正在為這株植物撰寫簡介..."):
                            intro_prompt = f"這是一種植物，學名是 {species_name}。請用繁體中文簡單介紹它的特徵或用途（50字以內）。"
                            summary_response = model.generate_content(intro_prompt)
                            
                        result_text = f"{initial_result}\n\n💡 **簡介：**\n{summary_response.text}"
                    else:
                        result_text = "植物辨識失敗，找不到相符的植物，請嘗試其他照片。"
                except Exception as e:
                    result_text = f"植物辨識發生錯誤：{e}"
        
        # --- (B) 鳥類辨識 (直接交給 Gemini) ---
        elif category == "鳥類":
            with st.spinner("Gemini AI 正在努力辨識這隻鳥..."):
                try:
                    prompt = "請幫我辨識這張圖片裡的是什麼鳥類？請給我牠的中文俗名，並用繁體中文簡單介紹一下牠的特徵（50字以內）。"
                    response = model.generate_content([prompt, image])
                    result_text = response.text
                except Exception as e:
                    result_text = f"鳥類辨識發生錯誤：{e}"

        # --- (C) 岩石辨識 (直接交給 Gemini) ---
        elif category == "岩石":
            with st.spinner("Gemini AI 正在努力辨識這顆岩石..."):
                try:
                    prompt = "請幫我辨識這張圖片裡的是什麼岩石或礦物？請給我它的中文名稱，並用繁體中文簡單介紹它的特徵（50字以內）。"
                    response = model.generate_content([prompt, image])
                    result_text = response.text
                except Exception as e:
                    result_text = f"岩石辨識發生錯誤：{e}"

        # ================= 3. 儲存結果至 Supabase =================
        if result_text and "錯誤" not in result_text and "失敗" not in result_text:
            with st.spinner("正在將紀錄與小知識儲存到雲端資料庫..."):
                try:
                    supabase.table("observations").insert({"category": category, "result_text": result_text}).execute()
                    st.success("✅ 辨識完成並已成功儲存到雲端！")
                    st.info(result_text)
                except Exception as e:
                    st.error(f"資料庫儲存失敗：{e}")
        else:
            st.warning(result_text)

st.markdown("---")

# ================= 4. 歷史觀察紀錄區塊 =================
st.header("📜 歷史觀察紀錄")

if st.button("🔄 重新載入歷史紀錄"):
    st.cache_data.clear()

@st.cache_data(ttl=60)
def load_history():
    response = supabase.table("observations").select("*").order("id", desc=True).limit(10).execute()
    return response.data

try:
    history_data = load_history()
    if history_data:
        for item in history_data:
            st.markdown(f"**分類：** {item.get('category', '未分類')}")
            st.markdown(f"**辨識結果：** {item.get('result_text', '無結果')}")
            st.caption(f"記錄編號 ID: {item.get('id', 'N/A')}")
            st.markdown("---")
    else:
        st.info("目前還沒有歷史紀錄喔！趕快拍張照上傳吧！")
except Exception as e:
     st.error(f"無法載入歷史紀錄：{e}")