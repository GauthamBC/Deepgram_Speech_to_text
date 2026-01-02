import os
import re
import io
import html
import wave
from difflib import SequenceMatcher
import streamlit as st
from deepgram import DeepgramClient

# ----------------------------
# Config
# ----------------------------
st.set_page_config(page_title="Pronunciation Checker (Deepgram)", page_icon="🎙️", layout="centered")

DEFAULT_MODEL = "nova-2"  # change to "nova-3" if your Deepgram plan supports it
MAX_SECONDS = 60

# ----------------------------
# Helpers: audio duration
# ----------------------------
def wav_duration_seconds(wav_bytes: bytes) -> float:
    """
    st.audio_input typically returns WAV bytes.
    We'll compute duration from WAV header safely.
    """
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            if rate <= 0:
                return 0.0
            return frames / float(rate)
    except wave.Error:
        # If it's not WAV (rare), we can't compute duration reliably without extra deps.
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
    """
    - Lowercase
    - Remove punctuation
    - Normalize numbers: digits -> <num>, number-words -> <num>
    """
    text = text.lower()

    # Replace digits with <num>
    text = re.sub(r"\b\d+(?:[.,]\d+)?\b", "<num>", text)

    # Replace number words with <num> (simple but effective)
    # This treats "twenty" and "20" as the same token.
    tokens = re.findall(r"[a-z']+|<num>", text)
    out = []
    for t in tokens:
        if t in NUM_WORDS:
            out.append("<num>")
        else:
            out.append(t)
    return " ".join(out)

def tokenize(text: str) -> list[str]:
    text = normalize_text_for_scoring(text)
    return text.split()

# ----------------------------
# Alignment + highlighting
# ----------------------------
def align_words(ref_tokens: list[str], hyp_tokens: list[str]):
    """
    Returns operations from SequenceMatcher over token lists.
    Each op: (tag, i1, i2, j1, j2)
    tags: 'equal', 'replace', 'delete', 'insert'
    """
    sm = SequenceMatcher(a=ref_tokens, b=hyp_tokens)
    return sm.get_opcodes()

def score_and_mismatches(ref_text: str, hyp_text: str):
    ref_tokens = tokenize(ref_text)
    hyp_tokens = tokenize(hyp_text)

    if not ref_tokens:
        return 0.0, [], ref_tokens, hyp_tokens, []

    ops = align_words(ref_tokens, hyp_tokens)

    matched = 0
    mismatches = []  # list of dicts describing each mismatch
    ref_marks = ["ok"] * len(ref_tokens)  # ok / bad

    for tag, i1, i2, j1, j2 in ops:
        if tag == "equal":
            matched += (i2 - i1)
        elif tag == "replace":
            # mark these reference tokens as problematic
            for k in range(i1, i2):
                if 0 <= k < len(ref_marks):
                    ref_marks[k] = "bad"
            mismatches.append({
                "type": "replace",
                "ref": " ".join(ref_tokens[i1:i2]),
                "hyp": " ".join(hyp_tokens[j1:j2])
            })
        elif tag == "delete":
            for k in range(i1, i2):
                if 0 <= k < len(ref_marks):
                    ref_marks[k] = "bad"
            mismatches.append({
                "type": "delete",
                "ref": " ".join(ref_tokens[i1:i2]),
                "hyp": "(missing)"
            })
        elif tag == "insert":
            mismatches.append({
                "type": "insert",
                "ref": "(extra)",
                "hyp": " ".join(hyp_tokens[j1:j2])
            })

    # Score based on % matched reference words (simple + interpretable)
    score = 100.0 * matched / max(1, len(ref_tokens))
    return score, mismatches, ref_tokens, hyp_tokens, ref_marks

def render_highlighted_reference(ref_tokens: list[str], ref_marks: list[str]) -> str:
    """
    Highlight mismatched reference tokens in red.
    """
    chunks = []
    for tok, mark in zip(ref_tokens, ref_marks):
        safe = html.escape(tok)
        if mark == "bad":
            chunks.append(f"<span style='background:#ffebee; color:#b71c1c; padding:2px 4px; border-radius:6px; margin:1px; display:inline-block;'>{safe}</span>")
        else:
            chunks.append(f"<span style='background:#e8f5e9; color:#1b5e20; padding:2px 4px; border-radius:6px; margin:1px; display:inline-block;'>{safe}</span>")
    return " ".join(chunks)

# ----------------------------
# Deepgram transcription
# ----------------------------
def deepgram_transcribe(audio_bytes: bytes, language: str, model: str) -> str:
    """
    Transcribe pre-recorded bytes using Deepgram Python SDK.
    """
    api_key = os.getenv("DEEPGRAM_API_KEY") or st.secrets.get("DEEPGRAM_API_KEY", "")
    if not api_key:
        raise RuntimeError("Missing DEEPGRAM_API_KEY. Set it in Streamlit secrets or env var.")

    client = DeepgramClient(api_key=api_key)

    # Using SDK's file transcription method (bytes in -> transcript out). :contentReference[oaicite:2]{index=2}
    response = client.listen.v1.media.transcribe_file(
        request=audio_bytes,
        model=model,
        language=language,
        smart_format=True,
        punctuate=True
    )
    return response.results.channels[0].alternatives[0].transcript or ""

# ----------------------------
# UI
# ----------------------------
st.title("🎙️ Pronunciation Checker (Deepgram)")
st.caption("Paste the text you read, record up to 60s, then score based on unmatched words (punctuation ignored, numbers normalized).")

col1, col2 = st.columns(2)
with col1:
    language = st.selectbox("Transcription dialect", ["en-GB", "en-US", "en"], index=0,
                            help="Pick the dialect you want Deepgram to bias toward.")
with col2:
    model = st.text_input("Deepgram model", value=DEFAULT_MODEL,
                          help="Common options include nova-2 and nova-3 (depends on your account).")

ref_text = st.text_area("Original text (paste what you read)", height=150, placeholder="Paste the passage you read...")

audio_file = st.audio_input("Record your voice (stop before 60 seconds)", sample_rate=16000)

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
    if audio_file is None:
        st.error("Please record audio first.")
        st.stop()

    with st.spinner("Transcribing with Deepgram…"):
        try:
            transcript = deepgram_transcribe(audio_bytes, language=language, model=model)
        except Exception as e:
            st.error(f"Deepgram transcription failed: {e}")
            st.stop()

    st.subheader("Transcript")
    st.write(transcript if transcript else "*(No transcript returned)*")

    score, mismatches, ref_tokens, hyp_tokens, ref_marks = score_and_mismatches(ref_text, transcript)

    st.subheader("Overall Score")
    st.metric("Match score (based on reference words matched)", f"{score:.1f} / 100")

    st.subheader("Reference text with highlighted issues")
    highlighted = render_highlighted_reference(ref_tokens, ref_marks)
    st.markdown(highlighted, unsafe_allow_html=True)

    if mismatches:
        st.subheader("Unmatched segments (what to practice)")
        # A compact, useful display
        for m in mismatches[:50]:
            label = m["type"].upper()
            st.write(f"**{label}** — expected: `{m['ref']}` | heard: `{m['hyp']}`")
        if len(mismatches) > 50:
            st.caption(f"Showing first 50 mismatches (total: {len(mismatches)}).")
    else:
        st.success("Nice — no mismatches detected after normalization. 🎉")

    st.caption(
        "Note: This is a pronunciation proxy using speech recognition matching. "
        "It’s best for tracking improvement + spotting tricky words, not for judging accent ‘authenticity’."
    )
