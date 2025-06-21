import requests, time, json, streamlit as st

def send_kakao(text: str):
    """카카오톡 텍스트 메시지 전송.
    로컬 개발 환경이나 secrets.toml 미설정 시 예외 없이 무시한다."""
    try:
        token = st.secrets["KAKAO"]["ACCESS"]
    except (FileNotFoundError, KeyError):
        # 배포 환경이 아니면 그냥 패스
        return
    url   = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    payload = {
        "template_object": json.dumps({
            "object_type":"text",
            "text": text,
            "link": {"web_url":"https://streamlit.io", "mobile_web_url":"https://streamlit.io"}
        })
    }
    r = requests.post(url, data=payload,
                      headers={"Authorization": f"Bearer {token}"})
    if r.status_code == 401:
        st.error("카카오 토큰 만료 – 새로 발급 필요")
