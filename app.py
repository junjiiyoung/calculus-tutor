import streamlit as st
import google.generativeai as genai
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# ── 페이지 설정 ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="미적분 AI 튜터",
    page_icon="📐",
    layout="centered"
)

# ── 비밀번호 잠금 ────────────────────────────────────────────────────────────
CLASS_PASSWORD = "1234"   # ← 수업마다 이 숫자를 바꾸세요!

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

# ── 이 아래부터는 비밀번호 통과한 학생만 볼 수 있음 ──────────────────────────

st.title("📐 미적분 AI 튜터")
st.caption("궁금한 미적분 개념을 자유롭게 질문하세요! 질문이 끝나면 '대화 종료' 버튼을 눌러주세요.")

# ── Gemini API 초기화 (새 패키지) ────────────────────────────────────────────

client = genai.Client(api_key=st.secrets["gemini"]["api_key"])

SYSTEM_PROMPT = """당신은 고등학교·대학교 미적분 전문 튜터입니다.
학생들이 미적분 개념(극한, 미분, 적분, 테일러 급수 등)을 쉽게 이해할 수 있도록 도와주세요.
- 수식은 텍스트로 명확하게 설명하세요 (예: x^2, dy/dx)
- 단계별로 차근차근 설명하고, 구체적인 예시를 들어주세요
- 학생이 스스로 생각할 수 있도록 유도하는 질문도 섞어주세요
- 미적분과 관련 없는 질문은 정중히 거절하고 미적분 주제로 안내하세요
- 항상 한국어로 답변하세요"""

# ── Google Sheets 연결 함수 ──────────────────────────────────────────────────
def get_sheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    gc = gspread.authorize(creds)
    spreadsheet = gc.open_by_key(st.secrets["sheets"]["spreadsheet_id"])
    return spreadsheet.sheet1

def save_to_sheet(student_id, name, chat_history, learned):
    sheet = get_sheet()
    if sheet.row_count == 0 or sheet.cell(1, 1).value != "학번":
        sheet.insert_row(["학번", "이름", "제출 시각", "대화 내용", "새롭게 알게 된 점"], 1)
    chat_text = ""
    for msg in chat_history:
        role = "학생" if msg["role"] == "user" else "AI 튜터"
        chat_text += f"[{role}] {msg['content']}\n\n"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sheet.append_row([student_id, name, timestamp, chat_text.strip(), learned])

# ── 세션 상태 초기화 ─────────────────────────────────────────────────────────
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "chat_ended" not in st.session_state:
    st.session_state.chat_ended = False
if "submitted" not in st.session_state:
    st.session_state.submitted = False

# ── 학생 정보 입력 ───────────────────────────────────────────────────────────
st.subheader("👤 내 정보")
col1, col2 = st.columns(2)
with col1:
    student_id = st.text_input("학번", placeholder="예: 20241234")
with col2:
    student_name = st.text_input("이름", placeholder="예: 홍길동")

st.divider()

# ── 채팅 영역 ────────────────────────────────────────────────────────────────
st.subheader("💬 AI 튜터와 대화하기")

for msg in st.session_state.chat_history:
    if msg["role"] == "user":
        with st.chat_message("user"):
            st.write(msg["content"])
    else:
        with st.chat_message("assistant", avatar="📐"):
            st.write(msg["content"])

# ── 채팅 진행 중 ─────────────────────────────────────────────────────────────
if not st.session_state.chat_ended and not st.session_state.submitted:

    user_input = st.chat_input("미적분에 대해 무엇이든 물어보세요! 추가 질문도 계속 할 수 있어요.")

   if user_input:
    if not student_id or not student_name:
        st.warning("⚠️ 먼저 학번과 이름을 입력해주세요!")
    else:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.write(user_input)

        with st.chat_message("assistant", avatar="📐"):
            with st.spinner("생각하는 중..."):
                try:
                    # 대화 맥락 유지 (역대 대화 기록 전달)
                    history = []
                    for msg in st.session_state.chat_history[:-1]:
                        role = "user" if msg["role"] == "user" else "model"
                        history.append({"role": role, "parts": [msg["content"]]})
                    
                    # 채팅 시작
                    chat = model.start_chat(history=history)
                    # 시스템 프롬프트는 첫 질문에만 살짝 섞거나 설정 시 넣습니다.
                    response = chat.send_message(user_input)
                    
                    ai_reply = response.text
                    st.write(ai_reply)
                    st.session_state.chat_history.append({"role": "assistant", "content": ai_reply})
                except Exception as e:
                    st.error(f"API 오류가 발생했습니다: {e}")

    if len(st.session_state.chat_history) >= 2:
        st.divider()
        col_end, col_reset = st.columns([3, 1])
        with col_end:
            if st.button("✅ 질문 다 했어요! 대화 종료하기", type="primary", use_container_width=True):
                st.session_state.chat_ended = True
                st.rerun()
        with col_reset:
            if st.button("🔄 처음부터 다시", use_container_width=True):
                st.session_state.chat_history = []
                st.rerun()

# ── 대화 종료 후: 학습 정리 & 제출 ─────────────────────────────────────────
if st.session_state.chat_ended and not st.session_state.submitted:
    st.divider()
    st.subheader("✏️ 오늘의 학습 정리")
    q_count = len([m for m in st.session_state.chat_history if m["role"] == "user"])
    st.success(f"총 {q_count}개의 질문을 했어요! 마지막으로 오늘 배운 점을 정리해봐요.")

    learned = st.text_area(
        "오늘 새롭게 알게 된 점을 적어보세요",
        placeholder="예: 미분은 함수의 순간 변화율을 구하는 것이고, 극한 개념이 기초가 된다는 것을 알았다.",
        height=130
    )

    col_submit, col_back = st.columns([3, 1])
    with col_submit:
        if st.button("📤 제출하기 (구글 시트에 저장)", type="primary", use_container_width=True):
            if not student_id or not student_name:
                st.warning("⚠️ 위로 올라가서 학번과 이름을 먼저 입력해주세요!")
            elif not learned.strip():
                st.warning("⚠️ '새롭게 알게 된 점'을 한 줄이라도 적어주세요!")
            else:
                with st.spinner("구글 시트에 저장하는 중..."):
                    try:
                        save_to_sheet(student_id, student_name, st.session_state.chat_history, learned)
                        st.session_state.submitted = True
                        st.rerun()
                    except Exception as e:
                        st.error(f"저장 오류: {e}")
    with col_back:
        if st.button("↩️ 질문 더 하기", use_container_width=True):
            st.session_state.chat_ended = False
            st.rerun()

# ── 제출 완료 화면 ───────────────────────────────────────────────────────────
if st.session_state.submitted:
    st.success("🎉 제출 완료! 선생님 구글 시트에 저장되었습니다.")
    st.balloons()
    st.info(f"**{student_name}** 학생, 오늘 수업도 수고했어요! 😊")
    if st.button("새 세션 시작 (다음 학생)"):
        for key in ["chat_history", "chat_ended", "submitted", "unlocked"]:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()
