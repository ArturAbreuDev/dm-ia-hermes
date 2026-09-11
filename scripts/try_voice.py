import sys

from app.config import get_settings
from app.services import elevenlabs, voice

sys.stdout.reconfigure(encoding="utf-8")
get_settings.cache_clear()
settings = get_settings()

print("voice_ready", settings.voice_ready)
print("voice_id", settings.elevenlabs_voice_id)
print("base_url", settings.base_url)

CASES = [
    ("oi", "kkkk oi 😌", False),
    ("você vende conteúdo?", "tenho simm 👀", False),
    ("[a pessoa mandou um áudio]", "adorei ouvir sua voz 😏", True),
    ("quanto é?", "olha o link aí: https://botgram.club/livia-gomes-fotos", False),
]
for user_text, reply, is_audio in CASES:
    decision = voice.should_use_voice(user_text, reply, is_audio)
    print(f"audio={decision!s:<5} | recebido={user_text[:28]:<30} | resposta={reply[:32]}")

texto = "tenho simm, e olha que aqui eu mostro bem pouquinho"
audio = elevenlabs.synthesize_wav(voice._strip_for_speech(texto))
if audio:
    with open("data/amostra_voz.wav", "wb") as handle:
        handle.write(audio)
    print("wav_bytes", len(audio))
    print("arquivo data/amostra_voz.wav")
else:
    print("falhou ao gerar o audio")
