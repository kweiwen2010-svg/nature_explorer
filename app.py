import streamlit as st
from supabase import create_client
import google.generativeai as genai
from PIL import Image, ImageOps
from PIL.ExifTags import TAGS, GPSTAGS

# 網頁基礎設定
st.set_page_config(page_title="大自然隨身觀察筆記", page_icon="🌿")

st.title("🌿 大自然隨身觀察筆記")
st.write("結合照片（自動抓取 GPS）、聲音辨識與夜空星象，打造你的全方位野外生態寶典！")

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


# ================= 2. 輔助函式：解析照片 GPS =================
def get_image_location(image):
    try:
        exif_data = image._getexif()
        if not exif_data:
            return None
        
        gps_info = {}
        for tag_id, value in exif_data.items():
            tag = TAGS.get(tag_id, tag_id)
            if tag == "GPSInfo":
                for t in value:
                    sub_tag = GPSTAGS.get(t, t)
                    gps_info[sub_tag] = value[t]
        
        if not gps_info:
            return None

        def convert_to_degress(value):
            d = float(value[0])
            m = float(value[1])
            s = float(value[2])
            return d + (m / 60.0) + (s / 3600.0)

        lat_data = gps_info.get('GPSLatitude')
        lat_ref = gps_info.get('GPSLatitudeRef')
        lon_data = gps_info.get('GPSLongitude')
        lon_ref = gps_info.get('GPSLongitudeRef')

        if lat_data and lon_data:
            lat = convert_to_degress(lat_data)
            if lat_ref != 'N':
                lat = -lat
            lon = convert_to_degress(lon_data)
            if lon_ref != 'E':
                lon = -lon
            return f"({lat:.4f}, {lon:.4f})"
    except Exception:
        pass
    return None


# ================= 3. 功能模式選擇 =================
app_mode = st.radio("選擇記錄模式：", ["📸 照片觀察筆記", "🎙️ 聲音辨識筆記 (鳥鳴/蟲鳴)"], horizontal=True)
st.markdown("---")

# ================= 模式一：照片觀察筆記 =================
if app_mode == "📸 照片觀察筆記":
    # 擴充加入「星象星座」
    categories = ["植物", "鳥類", "岩石", "昆蟲", "兩棲爬蟲", "真菌菇類", "雲況", "魚類", "星象星座"]
    category = st.radio("選擇你要記錄的種類：", categories, horizontal=True)
    
    uploaded_file = st.file_uploader("選擇或拍攝一張大自然或星空照片", type=["jpg", "jpeg", "png"])

    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        
        # 抓取 GPS 座標
        gps_coords = get_image_location(image)
        
        # 自動轉正
        image = ImageOps.exif_transpose(image)
        
        st.image(image, caption="上傳的圖片", use_container_width=True)
        if gps_coords:
            st.success(f"📍 成功抓取照片定位座標：{gps_coords}")
        else:
            st.info("ℹ️ 此照片未包含 GPS 定位資訊（不影響辨識）")
        
        if st.button("🚀 開始辨識並上傳紀錄"):
            result_text = ""
            
            with st.spinner(f"Gemini AI 正在努力辨識這個{category}類目標..."):
                try:
                    if category == "兩棲爬蟲":
                        prompt = "請幫我辨識這張圖片裡的是什麼兩棲爬蟲類？請給我它的中文俗名與學名，並簡單介紹特徵，特別提醒「是否有毒或具攻擊性」（50字以內）。"
                    elif category == "真菌菇類":
                        prompt = "請幫我辨識這張圖片裡的是什麼真菌或菇類？請給出中文名稱，並說明特徵，特別提醒「是否有毒、是否可食用」（50字以內，並附上安全警語）。"
                    elif category == "雲況":
                        prompt = "請幫我辨識這張圖片裡的雲況或天空自然景觀？請指出這是什麼類型的雲或現象，並說明它代表接下來可能的天氣變化（50字以內）。"
                    elif category == "魚類":
                        prompt = "請幫我辨識這張圖片裡的是什麼魚類？請給出它的中文俗名與學名（若知），並簡述其特徵與棲息環境（50字以內）。"
                    elif category == "星象星座":
                        prompt = "請幫我辨識這張夜空照片中的星座、明顯星體或星象？請給出其中文名稱與英文名，並簡單介紹其特徵或觀星小知識（50字以內）。"
                    else:
                        prompt = f"請幫我辨識這張圖片裡的是什麼{category}？請給出它的中文名稱或學名，並用繁體中文簡單介紹它的特徵或用途（50字以內）。"
                    
                    response = model.generate_content([prompt, image])
                    result_text = response.text
                    
                    # 若有抓到 GPS，附加到結果中
                    if gps_coords:
                        result_text += f"\n\n📍 **紀錄座標：** {gps_coords}"
                        
                except Exception as e:
                    result_text = f"辨識發生錯誤：{e}"

            # 儲存至 Supabase
            if result_text and "錯誤" not in result_text and "失敗" not in result_text:
                with st.spinner("正在將紀錄儲存到雲端資料庫..."):
                    try:
                        supabase.table("observations").insert({"category": category, "result_name": result_text}).execute()
                        st.success("✅ 辨識完成並已成功儲存到雲端！")
                        st.info(result_text)
                    except Exception as e:
                        st.error(f"資料庫儲存失敗：{e}")
            else:
                st.warning(result_text)

# ================= 模式二：聲音辨識筆記 =================
else:
    st.subheader("🎙️ 大自然聲音聽音辨位")
    st.write("點擊下方錄音按鈕，錄下山裡的鳥鳴、蟬鳴或蟲叫聲，讓 Gemini 幫你聽音辨位！")
    
    audio_file = st.audio_input("錄製鳥鳴或蟲鳴聲音")
    
    if audio_file is not None:
        st.audio(audio_file)
        
        if st.button("🚀 開始分析聲音來源"):
            result_text = ""
            category = "聲音辨識"
            
            with st.spinner("Gemini AI 正在專心聆聽並分析音訊頻率..."):
                try:
                    audio_bytes = audio_file.getvalue()
                    audio_part = {
                        "mime_type": audio_file.type,
                        "data": audio_bytes
                    }
                    prompt = "請聆聽這段大自然錄音檔，辨識這可能是哪種鳥類、昆蟲或其他動物的叫聲。請給出中文俗名與學名（若知），並簡述其特徵與叫聲代表的意義（50字以內）。"
                    
                    response = model.generate_content([prompt, audio_part])
                    result_text = response.text
                except Exception as e:
                    result_text = f"聲音辨識發生錯誤：{e}"

            # 儲存至 Supabase
            if result_text and "錯誤" not in result_text and "失敗" not in result_text:
                with st.spinner("正在將聲音紀錄儲存到雲端資料庫..."):
                    try:
                        supabase.table("observations").insert({"category": category, "result_name": result_text}).execute()
                        st.success("✅ 聲音辨識完成並已成功儲存到雲端！")
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
        st.info("目前還沒有歷史紀錄喔！趕快記錄第一筆觀察吧！")
except Exception as e:
     st.error(f"無法載入歷史紀錄：{e}")