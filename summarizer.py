from transformers import (
    BartForConditionalGeneration,
    PreTrainedTokenizerFast,
)
import torch
import streamlit as st

# 모델 한 번만 메모리에 유지
_model, _tok = None, None


def load_model():
    global _model, _tok
    if _model is None:
        model_name = "digit82/kobart-summarization"
        _tok = PreTrainedTokenizerFast.from_pretrained(model_name)
        _model = BartForConditionalGeneration.from_pretrained(model_name)
    return _tok, _model


def summarize(text: str, max_len: int = 1024, sum_len: int = 128) -> str:
    tok, model = load_model()
    ids = tok.encode(text, max_length=max_len, truncation=True, return_tensors="pt")
    with torch.no_grad():
        out = model.generate(
            ids,
            max_length=sum_len,
            num_beams=4,
            early_stopping=True,
            no_repeat_ngram_size=2,
        )
    return tok.decode(out[0], skip_special_tokens=True)


# 추가된 코드 블록
from summarizer import summarize
print(summarize("애플이 WWDC에서 새로운 인공지능 칩을 공개했다.")) 

try:
    full_text = cached_article(row["url"])
    if len(full_text) < 80:
        summary = "⚠️ 본문 추출 실패"
    else:
        summary = cached_summary(full_text)   # summarize_cached 사용
except Exception as e:
    summary = f"요약 실패: {e}"

# ────────────────
# 아래 줄(디버그용)은 삭제!
# st.write(summary) 
