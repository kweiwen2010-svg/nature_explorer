import streamlit as st
from supabase import create_client
import google.generativeai as genai
from PIL import Image, ImageOps

# 網頁基礎設定
st.set_page_config(page_title="大自然隨身觀察筆記", page_icon="🌿")

st.title("🌿 大自然隨身觀察筆記")
st.write("拍下你的植物、鳥類、岩石、昆蟲、兩棲爬蟲、真菌菇類、雲況或魚類，讓 AI 幫你辨識並永久記錄到雲端！")

# ================= 1. 讀取金鑰與連線設定 =================
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
model = genai.GenerativeModel('gemini-3.6-flash')


# ================= 2. 上傳與辨識區塊 =================
# 擴充後的完整生態與自然景觀分類清單
categories = ["植物", "鳥類", "岩石", "昆蟲", "兩棲爬蟲", "真菌菇類", "雲況", "魚類"]
category = st.radio("選擇你要記錄的種類：", categories, horizontal=True)

uploaded_file = st.file_uploader("選擇或拍攝一張大自然照片", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    # 自動將手機上傳旋轉過的照片轉正
    image = Image.open(uploaded_file)
    image = ImageOps.exif_transpose(image)
    
    # 顯示轉正後的圖片
    st.image(image, caption="上傳的圖片", use_container_width=True)
    
    if st.button("🚀 開始辨識並上傳紀錄"):
        result_text = ""
        
        with st.spinner(f"Gemini AI 正在努力辨識這個{category}類目標..."):
            try:
                # 針對不同類別給予更精準的提示詞引導
                if category == "兩棲爬蟲":
                    prompt = "請幫我辨識這張圖片裡的是什麼兩棲爬蟲類？請給我它的中文俗名與學名，並簡單介紹特徵，特別提醒「是否有毒或具攻擊性」（50字以內）。"
                elif category == "真菌菇類":
                    prompt = "請幫我辨識這張圖片裡的是什麼真菌或菇類？請給出中文名稱，並說明特徵，特別提醒「是否有毒、是否可食用」（50字以內，並附上安全警語）。"
                elif category == "雲況":
                    prompt = "請幫我辨識這張圖片裡的雲況或天空自然景觀？請指出這是什麼類型的雲或現象，並說明它代表接下來可能的天氣變化（50字以內）。"
                elif category == "魚類":
                    prompt = "請幫我辨識這張圖片裡的是什麼魚類？請給出它的中文俗名與學名（若知），並簡述其特徵與棲息環境（50字以內）。"
                else:
                    prompt = f"請幫我辨識這張圖片裡的是什麼{category}？請給出它的中文名稱或學名，並用繁體中文簡單介紹它的特徵或用途（50字以內）。"
                
                response = model.generate_content([prompt, image])
                result_text = response.text
            except Exception as e:
                result_text = f"辨識發生錯誤：{e}"

        # ================= 3. 儲存結果至 Supabase =================
        if result_text and "錯誤" not in result_text and "失敗" not in result_text:
            with st.spinner("正在將紀錄與小知識儲存到雲端資料庫..."):
                try:
                    supabase.table("observations").insert({"category": category, "result_name": result_text}).execute()
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
            st.markdown(f"**辨識結果：** {item.get('result_name', '無結果')}")
            st.caption(f"記錄編號 ID: {item.get('id', 'N/A')}")
            st.markdown("---")
    else:
        st.info("目前還沒有歷史紀錄喔！趕快拍張照上傳吧！")
except Exception as e:
     st.error(f"無法載入歷史紀錄：{e}")