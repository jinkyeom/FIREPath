import requests, time, streamlit as st

def send_kakao(text):
    token = st.secrets["KAKAO"]["ACCESS"]
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
