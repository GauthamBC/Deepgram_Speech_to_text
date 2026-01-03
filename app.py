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
# Config (hardcoded)
# ----------------------------
st.set_page_config(page_title="Pronunciation Checker", page_icon="🎙️", layout="centered")

STT_MODEL = "nova-3"                 # hardcoded
STT_LANGUAGE = "en-GB"               # hardcoded (change to "en-US" or "en" if you want)
TTS_VOICE_MODEL = "aura-2-draco-en"  # hardcoded
MAX_SECONDS = 60

# Practice settings
MAX_PRACTICE_ITEMS = 12
SLOW_FACTOR = 0.75   # 0.75x speed (lower pitch too, but clearer for learners)
FAST_FACTOR = 1.20   # 1.2x speed


# ----------------------------
# Helpers: auth
# ----------------------------
def get_api_key() -> str:
    api_key = os.getenv("DEEPGRAM_API_KEY") or st.secrets.get("DEEPGRAM_API_KEY", "")
    if not api_key:
        raise RuntimeError("Missing DEEPGRAM_API_KEY. Set it in Streamlit secrets or env var.")
    return api_key


# ----------------------------
# Helpers: WAV duration
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
# STT: transcription (pre-recorded)
# ----------------------------
def transcribe(audio_bytes: bytes) -> str:
    api_key = get_api_key()
    client = DeepgramClient(api_key=api_key)

    response = client.listen.v1.media.transcribe_file(
        request=audio_bytes,
        model=STT_MODEL,
        language=STT_LANGUAGE,
        smart_format=True,
        punctuate=True,
    )
    return response.results.channels[0].alternatives[0].transcript or ""


# ----------------------------
# TTS: speak request -> WAV bytes
# ----------------------------
@st.cache_data(show_spinner=False)
def tts_wav_bytes(text: str, voice_model: str = TTS_VOICE_MODEL) -> bytes:
    """
    One TTS call per phrase. We return WAV linear16 @16k for easy speed variants.
    """
    api_key = get_api_key()
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


# ----------------------------
# Audio: create slow/fast variants by changing WAV playback rate
# (simple & cheap; pitch changes slightly but clarity is good for learners)
# ----------------------------
def wav_change_playback_rate(wav_bytes: bytes, rate_multiplier: float) -> bytes:
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        nchannels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        nframes = wf.getnframes()
        frames = wf.readframes(nframes)

    new_rate = max(8000, int(framerate * rate_multiplier))

    out = io.BytesIO()
    with wave.open(out, "wb") as ww:
        ww.setnchannels(nchannels)
        ww.setsampwidth(sampwidth)
        ww.setframerate(new_rate)
        ww.writeframes(frames)

    return out.getvalue()


# ----------------------------
# Practice item selection
# ----------------------------
def practice_items_from_mismatches(mismatches: list[dict], max_items: int = MAX_PRACTICE_ITEMS) -> list[str]:
    out = []
    seen = set()
    for m in mismatches:
        ref = (m.get("ref") or "").strip()
        if not ref or ref in {"(extra)"}:
            continue

        # Make <num> pronounceable
        ref = ref.replace("<num>", "number")

        if ref in seen:
            continue
        seen.add(ref)
        out.append(ref)
        if len(out) >= max_items:
            break
    return out


# ----------------------------
# Session state + "New session"
# ----------------------------
if "ref_key" not in st.session_state:
    st.session_state.ref_key = 0
if "audio_key" not in st.session_state:
    st.session_state.audio_key = 0
if "last" not in st.session_state:
    st.session_state.last = None

def reset_session():
    st.session_state.last = None
    st.session_state.ref_key += 1
    st.session_state.audio_key += 1
    st.cache_data.clear()

def clear_query_params():
    # Works across Streamlit versions
    try:
        st.query_params.clear()
    except Exception:
        st.experimental_set_query_params()

def handle_new_session_param():
    # If user clicks sticky "New session" link
    try:
        qp = st.query_params
        val = qp.get("new_session")
    except Exception:
        qp = st.experimental_get_query_params()
        val = qp.get("new_session", [None])[0]

    if val == "1":
        reset_session()
        clear_query_params()
        st.rerun()

handle_new_session_param()


# ----------------------------
# Sticky top bar (always visible)
# ----------------------------
st.markdown(
    """
<style>
div.block-container { padding-top: 4.25rem; }

#sticky-topbar {
  position: fixed;
  top: 0; left: 0; right: 0;
  z-index: 9999;
  background: rgba(10, 12, 16, 0.92);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid rgba(255,255,255,0.08);
}

#sticky-topbar .inner {
  max-width: 980px;
  margin: 0 auto;
  padding: 0.75rem 1rem;
  display: flex;
  justify-content: flex-end;
}

#sticky-topbar a.ns-btn {
  text-decoration: none;
  font-weight: 600;
  padding: 0.55rem 0.9rem;
  border-radius: 12px;
  border: 1px solid rgba(255,255,255,0.18);
  background: rgba(255,255,255,0.06);
  color: rgba(255,255,255,0.92);
}

#sticky-topbar a.ns-btn:hover {
  background: rgba(255,255,255,0.12);
}
</style>

<div id="sticky-topbar">
  <div class="inner">
    <a class="ns-btn" href="?new_session=1">🆕 New session</a>
  </div>
</div>
""",
    unsafe_allow_html=True,
)


# ----------------------------
# UI
# ----------------------------
st.title("🎙️ Pronunciation Checker")
st.caption("Record ≤ 60s. Score is based on reference words matched (punctuation ignored, numbers normalized).")

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

    with st.spinner("Analyzing…"):
        try:
            transcript = transcribe(audio_bytes)
        except Exception as e:
            st.error(f"Transcription failed: {e}")
            st.stop()

    score, mismatches, ref_tokens, hyp_tokens, ref_marks = score_and_mismatches(ref_text, transcript)
    st.session_state.last = {
        "score": score,
        "mismatches": mismatches,
        "ref_tokens": ref_tokens,
        "ref_marks": ref_marks,
    }

# Render results (if any)
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
        st.subheader("Practice audio (normal / slow / fast)")
        items = practice_items_from_mismatches(mismatches, max_items=MAX_PRACTICE_ITEMS)

        h1, h2, h3, h4 = st.columns([2.2, 1.4, 1.4, 1.4])
        h1.markdown("**Word / phrase**")
        h2.markdown("**Normal**")
        h3.markdown("**Slow**")
        h4.markdown("**Fast**")

        for phrase in items:
            # Generate ONE normal TTS WAV, then derive slow/fast locally
            try:
                normal_wav = tts_wav_bytes(phrase)
                slow_wav = wav_change_playback_rate(normal_wav, SLOW_FACTOR)
                fast_wav = wav_change_playback_rate(normal_wav, FAST_FACTOR)

                c1, c2, c3, c4 = st.columns([2.2, 1.4, 1.4, 1.4])
                c1.write(phrase)
                c2.audio(normal_wav, format="audio/wav")
                c3.audio(slow_wav, format="audio/wav")
                c4.audio(fast_wav, format="audio/wav")

            except Exception as e:
                c1, c2, c3, c4 = st.columns([2.2, 1.4, 1.4, 1.4])
                c1.write(phrase)
                c2.warning(f"TTS failed: {e}")
                c3.empty()
                c4.empty()

        st.caption(f"Voice: {TTS_VOICE_MODEL}")
    else:
        st.success("Nice — no mismatches detected after normalization. 🎉")

    st.caption(
        "Note: This is a pronunciation proxy using speech recognition matching. "
        "It’s best for tracking improvement + spotting tricky words."
    )
