import os
import wave
import time
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Load your existing GEMINI_API_KEY from the .env file
load_dotenv()
client = genai.Client()

# Ensure the output directory exists
OUTPUT_DIR = "audio"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Complete list of all 30 prebuilt Gemini voices
VOICES = [
    # Male Voices
    "Charon", "Puck", "Fenrir", "Orus", "Achird", "Algenib", "Algieba", "Alnilam",
    "Enceladus", "Iapetus", "Rasalgethi", "Sadachbia", "Sadaltager", "Schedar",
    "Umbriel", "Zubenelgenubi",
    # Female Voices
    "Kore", "Aoede", "Achernar", "Autonoe", "Callirrhoe", "Despina", "Erinome",
    "Gacrux", "Laomedeia", "Leda", "Pulcherrima", "Sulafat", "Vindemiatrix", "Zephyr"
]

# --- Tuning knobs ---
WAIT_BETWEEN_SUCCESS = 30      # seconds to wait after a successful generation
MAX_RETRIES_PER_VOICE = 5      # give up on a voice after this many 429s
BASE_RETRY_SLEEP = 35          # starting backoff sleep on a 429
BACKOFF_MULTIPLIER = 1.5       # each retry waits longer than the last


def save_wav_file(filename, raw_audio_bytes, channels=1, rate=24000, sample_width=2):
    """Helper function to wrap raw PCM audio bytes into a playable .wav file."""
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(raw_audio_bytes)


def generate_voice_introductions():
    print(f"🎙️ Starting audio generation for {len(VOICES)} voices...")

    for voice_name in VOICES:
        filepath = os.path.join(OUTPUT_DIR, f"{voice_name}.wav")

        # 1. SKIP LOGIC: Don't waste quota on voices we already have
        if os.path.exists(filepath):
            print(f"⏭️  Skipping {voice_name} - already saved in folder.")
            continue

        print(f"Generating audio for {voice_name}...")
        prompt_text = f"Say exactly this: 'Hi, I'm {voice_name}, I will be your technical interviewer today.'"

        # 2. RETRY LOGIC WITH A CAP: retry on rate limits, but don't loop forever
        success = False
        attempts = 0
        retry_sleep = BASE_RETRY_SLEEP

        while not success and attempts < MAX_RETRIES_PER_VOICE:
            attempts += 1
            try:
                response = client.models.generate_content(
                    model="gemini-3.1-flash-tts-preview",
                    contents=prompt_text,
                    config=types.GenerateContentConfig(
                        response_modalities=["AUDIO"],
                        speech_config=types.SpeechConfig(
                            voice_config=types.VoiceConfig(
                                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                    voice_name=voice_name
                                )
                            )
                        ),
                    ),
                )

                # Extract the audio bytes
                audio_bytes = None
                for part in response.candidates[0].content.parts:
                    if part.inline_data:
                        audio_bytes = part.inline_data.data
                        break

                if audio_bytes:
                    save_wav_file(filepath, audio_bytes)
                    print(f"  ✅ Saved {filepath}")
                    success = True

                    # 3. SPEED LIMIT: wait to avoid hitting the per-minute limit
                    print(f"  ⏳ Waiting {WAIT_BETWEEN_SUCCESS}s to respect free-tier rate limits...")
                    time.sleep(WAIT_BETWEEN_SUCCESS)
                else:
                    print(f"  ⚠️  No audio data returned for {voice_name}")
                    success = True  # nothing to retry, move on

            except Exception as e:
                error_msg = str(e)
                print(f"  FULL ERROR: {error_msg}")  # helps tell per-minute vs per-day quota apart

                # A "PerDay" quotaId means retrying won't help until tomorrow (PT) —
                # stop immediately instead of burning 5 retries and several minutes.
                if "PerDay" in error_msg:
                    print(f"  🛑 Daily quota exhausted for this model (10 requests/day on free tier). "
                          f"Retrying won't help until it resets (~midnight Pacific Time). "
                          f"Stopping here — you got through {voice_name and 'this voice, run again tomorrow'}.")
                    return

                if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                    if attempts >= MAX_RETRIES_PER_VOICE:
                        print(f"  🛑 Gave up on {voice_name} after {attempts} attempts. "
                              f"This usually means your DAILY quota is exhausted, not just per-minute. "
                              f"Stop the script and try again after your quota resets.")
                        return  # stop the whole run — if one voice is stuck, the rest will be too
                    print(f"  ⏳ Rate limit hit! Sleeping {retry_sleep:.0f}s before retry "
                          f"{attempts}/{MAX_RETRIES_PER_VOICE} for {voice_name}...")
                    time.sleep(retry_sleep)
                    retry_sleep *= BACKOFF_MULTIPLIER  # back off a bit more each time
                else:
                    # Different kind of error — log it and move to the next voice
                    print(f"  ❌ Error generating {voice_name}: {e}")
                    break

    print("\n🎉 All done! Check the 'audio/' folder.")


if __name__ == "__main__":
    generate_voice_introductions()