from unittest.mock import patch

from app.services import incoming


def test_texto_simples() -> None:
    chegada = incoming.read({"text": "oi tudo bem?"})
    assert chegada.text == "oi tudo bem?"
    assert chegada.kind == "texto"
    assert not chegada.is_media
    assert not chegada.is_audio


def test_audio_vira_transcricao() -> None:
    message = {
        "attachments": [{"type": "audio", "payload": {"url": "https://cdn/a.mp4"}}]
    }
    with patch.object(incoming.vision, "transcribe", return_value="você vende conteúdo?"):
        chegada = incoming.read(message)
    assert "você vende conteúdo?" in chegada.text
    assert chegada.is_audio
    assert chegada.is_media


def test_audio_sem_transcricao_ainda_pede_resposta() -> None:
    message = {"attachments": [{"type": "audio", "payload": {"url": "https://cdn/a.mp4"}}]}
    with patch.object(incoming.vision, "transcribe", return_value=None):
        chegada = incoming.read(message)
    assert "não conseguiu ouvir" in chegada.text
    assert chegada.is_audio
    assert chegada.is_media


def test_story_mention_vira_descricao() -> None:
    message = {
        "attachments": [{"type": "story_mention", "payload": {"url": "https://cdn/s.jpg"}}]
    }
    with patch.object(incoming.vision, "describe", return_value="um print do seu perfil"):
        chegada = incoming.read(message)
    assert "te marcou no story" in chegada.text
    assert "um print do seu perfil" in chegada.text
    assert chegada.kind == "story_mention"
    assert chegada.is_media


def test_foto_vira_descricao() -> None:
    message = {"attachments": [{"type": "image", "payload": {"url": "https://cdn/i.jpg"}}]}
    with patch.object(incoming.vision, "describe", return_value="uma selfie dele no carro"):
        chegada = incoming.read(message)
    assert "uma selfie dele no carro" in chegada.text
    assert chegada.kind == "imagem"


def test_texto_junto_com_audio_e_preservado() -> None:
    message = {
        "text": "escuta isso",
        "attachments": [{"type": "audio", "payload": {"url": "https://cdn/a.mp4"}}],
    }
    with patch.object(incoming.vision, "transcribe", return_value="oi gata"):
        chegada = incoming.read(message)
    assert "oi gata" in chegada.text
    assert "escuta isso" in chegada.text


def test_tipo_desconhecido_nao_fica_sem_texto() -> None:
    chegada = incoming.read({"attachments": [{"type": "sticker"}]})
    assert chegada.text
    assert chegada.is_media
