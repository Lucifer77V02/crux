import streamlit as st
import requests
from streamlit_lottie import st_lottie
import google.generativeai as genai
import re
import io
import os
import yt_dlp
from openai import OpenAI
from markdown_pdf import MarkdownPdf, Section

# --- 1. PAGE SETUP & BRANDING ---
st.set_page_config(page_title="CruX | Instant Cheat Sheets", page_icon="⚡", layout="centered")

st.markdown("""
<style>
    .stApp { background-color: #E3F2FD; }
    .hero-container {
        background: linear-gradient(135deg, #0D47A1 0%, #42A5F5 100%);
        padding: 40px; border-radius: 25px; text-align: center;
        box-shadow: 0 10px 25px rgba(0,0,0,0.05); margin-bottom: 30px;
    }
    .hero-title { font-size: 3.5rem !important; font-weight: 800; color: white !important; }
    .hero-subtitle { font-size: 1.3rem; color: #E3F2FD !important; }
    .stTextInput input { border-radius: 15px !important; border: 2px solid #BBDEFB !important; }
</style>
""", unsafe_allow_html=True)

# --- 2. LOAD ANIMATION ---
def load_lottieurl(url):
    r = requests.get(url)
    return r.json() if r.status_code == 200 else None

lottie_graphic = load_lottieurl("https://assets5.lottiefiles.com/packages/lf20_vnikrcia.json")

# --- 3. HEADER ---
col1, col2 = st.columns([2, 1], gap="large")
with col1:
    st.markdown('<div class="hero-container"><h1 class="hero-title">⚡ CruX</h1><p class="hero-subtitle">Turn hours of lectures into a 2-minute cheat sheet.</p></div>', unsafe_allow_html=True)
    st.markdown("### Paste your YouTube link below to begin.")
with col2:
    if lottie_graphic: st_lottie(lottie_graphic, height=200)

st.markdown("---")

# --- 4. SECRETS ---
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
    client = OpenAI(api_key=OPENAI_API_KEY)
except KeyError:
    st.error("⚠️ API Keys (GEMINI or OPENAI) missing in Streamlit Secrets!")
    st.stop()

# --- 5. CORE LOGIC (Whisper) ---
def get_video_transcript_whisper(youtube_url):
    audio_filename = "temp_lecture_audio.m4a"
    
    ydl_opts = {
        'format': 'm4a/bestaudio/best',
        'outtmpl': 'temp_lecture_audio',
        'noplaylist': True,
        # --- ADD THESE TO BYPASS 403 ---
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'logtostderr': False,
        'add_header': [
            'User-Agent:Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
        ],
        # -------------------------------
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'm4a',
        }],
    }
    try:
        # 1. Download Audio
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([youtube_url])
        
        # 2. Transcribe with OpenAI Whisper
        with open(audio_filename, "rb") as audio_file:
            transcript_response = client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_file
            )
        
        # 3. Cleanup file
        if os.path.exists(audio_filename):
            os.remove(audio_filename)
            
        return transcript_response.text, None

    except Exception as e:
        # Cleanup on failure
        if os.path.exists(audio_filename): os.remove(audio_filename)
        return None, f"Whisper Error: {str(e)}"

def generate_cheat_sheet(transcript, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = f"Expert Professor: Create a Cheat Sheet from this transcript. Include Summary, Core Concepts, Key Terms, and a 5-question Practice Exam with Answer Key. \n\nTranscript: {transcript}"
    response = model.generate_content(prompt)
    return response.text

# --- 6. INTERFACE ---
youtube_url = st.text_input("🔗 YouTube Lecture Link:", placeholder="https://...")
generate_button = st.button("🚀 Generate Cheat Sheet", type="primary", use_container_width=True)

if generate_button:
    if not youtube_url:
        st.warning("⚠️ Paste a link first!")
    else:
        with st.status("CruX is listening to your lecture...", expanded=True) as status:
            st.write("📥 Downloading audio & transcribing (OpenAI Whisper)...")
            transcript, error = get_video_transcript_whisper(youtube_url)
            
            if error:
                status.update(label="Transcription Failed", state="error")
                st.error(error)
            else:
                st.write("🧠 AI Analyzing Lecture...")
                try:
                    cheat_sheet = generate_cheat_sheet(transcript, API_KEY)
                    
                    pdf = MarkdownPdf(toc_level=0)
                    pdf.add_section(Section(cheat_sheet))
                    pdf_buffer = io.BytesIO()
                    pdf.save_bytes(pdf_buffer)
                    
                    status.update(label="Ready!", state="complete")
                    st.balloons()
                    st.markdown(cheat_sheet)
                    st.download_button("📥 Download PDF", data=pdf_buffer.getvalue(), file_name="CruX_CheatSheet.pdf", mime="application/pdf")
                except Exception as e:
                    st.error(f"AI Error: {e}")
