import streamlit as st
import google.generativeai as genai
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# ── 1. 페이지 설정 ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="미적분 AI 튜터",
    page_icon="📐",
    layout="centered"
)

# ── 2. 비밀번호 잠금 ────────────────────────────────────────────────────────────
CLASS_PASSWORD = "1234"

if "unlocked" not in st.session_state:
    st.session_state.unlocked = False

if not st.session_state.unlocked:
    st.title("📐 미적분 AI 튜터")
    st.info("🔒 수업 시간에만 이용할 수 있습니다. 선생님이 알려주신 비밀번호를 입력하세요.")
    pw = st.text_input("비밀번호", type="password", placeholder="선생님이 알려주신 숫자를 입력하세요")
    if st.button("입장하기", type="primary"):
        if pw == CLASS_PASSWORD:
            st.session_state.unlocked = True
            st.rerun()
        else:
            st.error("❌ 비밀번호가 틀렸습니다. 선생님께 확인하세요.")
    st.stop()

# ── 3. Gemini API 초기화 (표준 라이브러리 방식) ──────────────────────────────────
# Streamlit Secrets에서 API 키를 가져옵니다.
genai.configure(api_key=st.secrets["gemini"]["api_key"])

# 모델 설정 (가장 안정적인 1.5-flash 모델)
model = genai.GenerativeModel('gemini-1.5-flash')

SYSTEM_PROMPT = """당신은 고등학교·대학교 미적분 전문 튜터입니다.
학생들이 미적분 개념을 쉽게 이해할 수 있도록 도와주세요.
- 수식은 텍스트로 명확하게 설명하세요 (예: x^2, dy/dx)
- 단계별로 차근차근 설명하고, 구체적인 예시를 들어주세요.
- 학생이 스스로 생각할 수 있도록 유도하는 질문도 섞어주세요.
- 항상 한국어로 답변하세요."""

# ── 4. Google Sheets 연결 함수 ──────────────────────────────────────────────────
def get_sheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    # Secrets에 저장된 서비스 계정 정보를 가져옵니다.
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    gc = gspread.authorize(creds)
    spreadsheet = gc.open_by_key(st.secrets["sheets"]["spreadsheet_id"])
    return spreadsheet.sheet1

def save_to_sheet(student_id, name, chat_history, learned):
    sheet = get_sheet()
    # 헤더가 없으면 생성
    if sheet.row_count == 0 or sheet.cell(1, 1).value != "학번":
        sheet.insert_row(["학번", "이름", "제출 시각", "대화 내용", "새롭게 알게 된 점"], 1)
    
    chat_text = ""
    for msg in chat_history:
        role = "학생" if msg["role"] == "user" else "AI 튜터"
        chat_text += f"[{role}] {msg['content']}\n\n"
        
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sheet.append_row([student_id, name, timestamp, chat_text.strip(), learned])

# ── 5. 세션 상태 초기화 ─────────────────────────────────────────────────────────
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "chat_ended" not in st.session_state:
    st.session_state.chat_ended = False
if "submitted" not in st.session_state:
    st.session_state.submitted = False

# ── 6. 화면 구성 ─────────────────────────────────────────────────────────────
st.title("📐 미적분 AI 튜터")
st.caption("궁금한 미적분 개념을 자유롭게 질문하세요!")

# 학생 정보 입력란
st.subheader("👤 내 정보")
col1, col2 = st.columns(2)
with col1:
    student_id = st.text_input("학번", placeholder="예: 20241234")
with col2:
    student_name = st.text_input("이름", placeholder="예: 홍길동")

st.divider()

# 채팅 기록 출력
for msg in st.session_state.chat_history:
    role = "user" if msg["role"] == "user" else "assistant"
    with st.chat_message(role, avatar="📐" if role == "assistant" else None):
        st.write(msg["content"])

# ── 7. 채팅 진행 로직 ───────────────────────────────────────────────────────────
if not st.session_state.chat_ended and not st.session_state.submitted:
    user_input = st.chat_input("미적분에 대해 무엇이든 물어보세요!")

    if user_input:
        if not student_id or not student_name:
            st.warning("⚠️ 먼저 학번과 이름을 입력해주세요!")
        else:
            # 사용자 메시지 추가
            st.session_state.chat_history.append({"role": "user", "content": user_input})
            with st.chat_message("user"):
                st.write(user_input)

            # AI 응답 생성
            with st.chat_message("assistant", avatar="📐"):
                with st.spinner("생각하는 중..."):
                    try:
                        # 대화 기록 구성 (역대 대화 포함)
                        history = [{"role": "user", "parts": [SYSTEM_PROMPT]}, {"role": "model", "parts": ["알겠습니다. 미적분 튜터로서 성실히 답변하겠습니다."]}]
                        for m in st.session_state.chat_history[:-1]:
                            history.append({
                                "role": "user" if m["role"] == "user" else "model",
                                "parts": [m["content"]]
                            })
                        
                        chat_session = model.start_chat(history=history)
                        response = chat_session.send_message(user_input)
                        
                        ai_reply = response.text
                        st.write(ai_reply)
                        st.session_state.chat_history.append({"role": "assistant", "content": ai_reply})
                    except Exception as e:
                        st.error(f"API 오류가 발생했습니다: {e}")

    # 질문 종료 버튼 (채팅 내역이 있을 때만 표시)
    if len(st.session_state.chat_history) >= 2:
        st.divider()
        if st.button("✅ 질문 다 했어요! 대화 종료하기", type="primary", use_container_width=True):
            st.session_state.chat_ended = True
            st.rerun()

# ── 8. 학습 정리 및 제출 ─────────────────────────────────────────────────────────
if st.session_state.chat_ended and not st.session_state.submitted:
    st.subheader("✏️ 오늘의 학습 정리")
    learned = st.text_area("오늘 새롭게 알게 된 점을 적어보세요", height=130)

    if st.button("📤 제출하기 (구글 시트에 저장)", type="primary", use_container_width=True):
        if not learned.strip():
            st.warning("⚠️ '새롭게 알게 된 점'을 적어주세요!")
        else:
            with st.spinner("저장 중..."):
                try:
                    save_to_sheet(student_id, student_name, st.session_state.chat_history, learned)
                    st.session_state.submitted = True
                    st.rerun()
                except Exception as e:
                    st.error(f"저장 중 오류 발생: {e}")

# ── 제출 완료 화면 (코드의 가장 마지막 부분입니다) ─────────────────────────────────
if st.session_state.submitted:
    st.success("🎉 제출 완료! 선생님 구글 시트에 기록되었습니다.")
    st.balloons()
    st.info(f"**{student_name}** 학생, 오늘 수업도 수고했어요! 😊")
    
    if st.button("새 세션 시작 (다음 학생)"):
        # 세션 상태 초기화
        keys_to_reset = ["chat_history", "chat_ended", "submitted", "unlocked"]
        for key in keys_to_reset:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()
