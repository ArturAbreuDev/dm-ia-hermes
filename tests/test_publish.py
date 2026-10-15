"""Testes do serviço de publicação (sem chamar a Meta de verdade)."""

from app.services import publish


def test_feed_exige_imagem() -> None:
    try:
        publish.publish("feed")
        assert False, "deveria falhar"
    except publish.PublishError as erro:
        assert "image_url" in str(erro)


def test_reels_exige_video() -> None:
    try:
        publish.publish("reels")
        assert False, "deveria falhar"
    except publish.PublishError as erro:
        assert "video_url" in str(erro)


def test_story_exige_midia() -> None:
    try:
        publish.publish("story")
        assert False, "deveria falhar"
    except publish.PublishError as erro:
        assert "image_url" in str(erro) or "video_url" in str(erro)
