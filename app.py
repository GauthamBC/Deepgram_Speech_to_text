import os
import re
import io
import html
import wave
import requests
from difflib import SequenceMatcher
import streamlit as st
from deepgram import DeepgramClient

# ----------------------------
# Config
# ----------------------------
st.set_page_config(page_title="Pronunciation Checker (Deepgram)", page_icon="🎙️", layout="centered")

STT_MODEL = "nova-3"                 # hardcoded
TTS_VOICE_MODEL = "aura-2-thalia-en" # hardcoded
MAX_SECONDS = 60

# ----------------------------
# Helpers: auth
# ----------------------------
def get_deepgram_api_key() -> str:
    api_key = os.getenv("DEEPGRAM_API_KEY") or st.secrets.get("DEEPGRAM_API_KEY", "")
    if not api_key:
        raise RuntimeError("Missing DEEPGRAM_API_KEY. Set it in Streamlit secrets or env var.")
    return api_key

# ----------------------------
# Helpers: audio duration
# ----------------------------
def wav_duration_seconds(wav_bytes: bytes) -> float:
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            if rate <= 0:
                return 0.0
            return frames / float(rate)
    except wave.Error:
        return -1.0

# ----------------------------
# Helpers: normalization/tokenization
# ----------------------------
NUM_WORDS = {
    "zero","one","two","three","four","five","six","seven","eight","nine","ten",
    "eleven","twelve","thirteen","fourteen","fifteen","sixteen","seventeen","eighteen","nineteen",
    "twenty","thirty","forty","fifty","sixty","seventy","eighty","ninety",
    "hundred","thousand","million","billion"
}

def normalize_text_for_scoring(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\b\d+(?:[.,]\d+)?\b", "<num>", text)
    tokens = re.findall(r"[a-z']+|<num>", text)
    out = []
    for t in tokens:
        out.append("<num>" if t in NUM_WORDS else t)
    return " ".join(out)

def tokenize(text: str) -> list[str]:
    return normalize_text_for_scoring(text).split()

# ----------------------------
# Alignment + highlighting
# ----------------------------
def align_words(ref_tokens: list[str], hyp_tokens: list[str]):
    sm = SequenceMatcher(a=ref_tokens, b=hyp_tokens)
    return sm.get_opcodes()

def score_and_mismatches(ref_text: str, hyp_text: str):
    ref_tokens = tokenize(ref_text)
    hyp_tokens = tokenize(hyp_text)

    if not ref_tokens:
        return 0.0, [], ref_tokens, hyp_tokens, []

    ops = align_words(ref_tokens, hyp_tokens)

    matched = 0
    mismatches = []
    ref_marks = ["ok"] * len(ref_tokens)

    for tag, i1, i2, j1, j2 in ops:
        if tag == "equal":
            matched += (i2 - i1)
        elif tag == "replace":
            for k in range(i1, i2):
                if 0 <= k < len(ref_marks):
                    ref_marks[k] = "bad"
            mismatches.append({"type": "replace", "ref": " ".join(ref_tokens[i1:i2]), "hyp": " ".join(hyp_tokens[j1:j2])})
        elif tag == "delete":
            for k in range(i1, i2):
                if 0 <= k < len(ref_marks):
                    ref_marks[k] = "bad"
            mismatches.append({"type": "delete", "ref": " ".join(ref_tokens[i1:i2]), "hyp": "(missing)"})
        elif tag == "insert":
            mismatches.append({"type": "insert", "ref": "(extra)", "hyp": " ".join(hyp_tokens[j1:j2])})

    score = 100.0 * matched / max(1, len(ref_tokens))
    return score, mismatches, ref_tokens, hyp_tokens, ref_marks

def render_highlighted_reference(ref_tokens: list[str], ref_marks: list[str]) -> str:
    chunks = []
    for tok, mark in zip(ref_tokens, ref_marks):
        safe = html.escape(tok)
        if mark == "bad":
            chunks.append(
                f"<span style='background:#ffebee; color:#b71c1c; padding:2px 4px; border-radius:6px; margin:1px; display:inline-block;'>{safe}</span>"
            )
        else:
            chunks.append(
                f"<span style='background:#e8f5e9; color:#1b5e20; padding:2px 4px; border-radius:6px; margin:1px; display:inline-block;'>{safe}</span>"
            )
    return " ".join(chunks)

# ----------------------------
# Deepgram STT (pre-recorded)
# ----------------------------
def deepgram_transcribe(audio_bytes: bytes, language: str) -> str:
    api_key = get_deepgram_api_key()
    client = DeepgramClient(api_key=api_key)
    response = client.listen.v1.media.transcribe_file(
        request=audio_bytes,
        model=STT_MODEL,      # hardcoded nova-3
        language=language,
        smart_format=True,
        punctuate=True,
    )
    return response.results.channels[0].alternatives[0].transcript or ""

# ----------------------------
# Deepgram TTS (REST)
# ----------------------------
@st.cache_data(show_spinner=False)
def deepgram_tts_audio(text: str, voice_model: str = TTS_VOICE_MODEL) -> bytes:
    """
    Cached by (text, voice_model). Returns WAV bytes for stable Streamlit playback.
    """
    api_key = get_deepgram_api_key()
    url = "https://api.deepgram.com/v1/speak"
    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "application/json",
    }
    params = {
        "model": voice_model,
        "container": "wav",
        "encoding": "linear16",
        "sample_rate": "16000",
    }
    payload = {"text": text}

    r = requests.post(url, headers=headers, params=params, json=payload, timeout=60)
    r.raise_for_status()
    return r.content

def practice_items_from_mismatches(mismatches: list[dict], max_items: int = 12) -> list[str]:
    """
    Pick unique 'expected' segments to practice.
    """
    out = []
    seen = set()
    for m in mismatches:
        ref = (m.get("ref") or "").strip()
        if not ref or ref in {"(extra)"}:
            continue
        ref = ref.replace("<num>", "number")  # better than speaking "<num>"
        if ref in seen:
            continue
        seen.add(ref)
        out.append(ref)
        if len(out) >= max_items:
            break
    return out

# ----------------------------
# Session state: widget reset keys + last results
# ----------------------------
if "ref_key" not in st.session_state:
    st.session_state.ref_key = 0
if "audio_key" not in st.session_state:
    st.session_state.audio_key = 0
if "last" not in st.session_state:
    st.session_state.last = None

def clear_session():
    st.session_state.last = None
    st.session_state.ref_key += 1
    st.session_state.audio_key += 1
    st.cache_data.clear()
    st.rerun()

# ----------------------------
# UI
# ----------------------------
st.title("🎙️ Pronunciation Checker (Deepgram)")
st.caption("Model is locked to **nova-3**. Record ≤ 60s. Score is based on reference words matched (punctuation ignored, numbers normalized).")

top = st.columns([1, 1, 1])
with top[0]:
    language = st.selectbox("Transcription dialect", ["en-GB", "en-US", "en"], index=0)
with top[1]:
    st.text_input("STT model (locked)", value=STT_MODEL, disabled=True)
with top[2]:
    if st.button("🧹 Clear / New session", use_container_width=True):
        clear_session()

ref_text = st.text_area(
    "Original text (paste what you read)",
    height=150,
    placeholder="Paste the passage you read...",
    key=f"ref_text_{st.session_state.ref_key}",
)

audio_file = st.audio_input(
    "Record your voice (stop before 60 seconds)",
    sample_rate=16000,
    key=f"audio_{st.session_state.audio_key}",
)

audio_bytes = None
if audio_file is not None:
    audio_bytes = audio_file.getvalue()
    st.audio(audio_bytes, format="audio/wav")
    dur = wav_duration_seconds(audio_bytes)
    if dur >= 0:
        st.info(f"Detected duration: **{dur:.1f}s** (target ≤ {MAX_SECONDS}s).")
        if dur > MAX_SECONDS:
            st.warning("This recording is longer than 60 seconds. Please re-record shorter for best results.")
    else:
        st.warning("Could not detect duration (non-WAV). The app will still try to transcribe.")

score_btn = st.button("✅ Check pronunciation", type="primary", use_container_width=True)

if score_btn:
    if not ref_text.strip():
        st.error("Please paste the original text first.")
        st.stop()
    if audio_bytes is None:
        st.error("Please record audio first.")
        st.stop()

    with st.spinner("Transcribing (nova-3)…"):
        try:
            transcript = deepgram_transcribe(audio_bytes, language=language)
        except Exception as e:
            st.error(f"Deepgram transcription failed: {e}")
            st.stop()

    score, mismatches, ref_tokens, hyp_tokens, ref_marks = score_and_mismatches(ref_text, transcript)
    st.session_state.last = {
        "score": score,
        "mismatches": mismatches,
        "ref_tokens": ref_tokens,
        "ref_marks": ref_marks,
    }

# ---- Render results (if any)
if st.session_state.last is not None:
    score = st.session_state.last["score"]
    mismatches = st.session_state.last["mismatches"]
    ref_tokens = st.session_state.last["ref_tokens"]
    ref_marks = st.session_state.last["ref_marks"]

    st.subheader("Pronunciation score")
    st.metric("Pronunciation score", f"{score:.1f} / 100")

    st.subheader("Reference text with highlighted issues")
    st.markdown(render_highlighted_reference(ref_tokens, ref_marks), unsafe_allow_html=True)

    if mismatches:
        st.subheader("Practice audio (slow & clear)")
        items = practice_items_from_mismatches(mismatches, max_items=12)

        # header row
        h1, h2, h3 = st.columns([2, 1.5, 1.5])
        h1.markdown("**Word / phrase**")
        h2.markdown("**Repeat 1**")
        h3.markdown("**Repeat 2**")

        for phrase in items:
            # Two separate audios (slight variation: second has longer pause)
            t1 = f"{phrase}."
            t2 = f"{phrase}..."

            c1, c2, c3 = st.columns([2, 1.5, 1.5])
            c1.write(phrase)

            try:
                a1 = deepgram_tts_audio(t1)
                a2 = deepgram_tts_audio(t2)
                c2.audio(a1, format="audio/wav")
                c3.audio(a2, format="audio/wav")
            except Exception as e:
                c2.warning(f"TTS failed: {e}")
                c3.empty()

        st.caption(f"Voice: {TTS_VOICE_MODEL}")
    else:
        st.success("Nice — no mismatches detected after normalization. 🎉")

    st.caption(
        "Note: This is a pronunciation proxy using speech recognition matching. "
        "It’s best for tracking improvement + spotting tricky words."
    )
