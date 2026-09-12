from app.services import voice_director


def test_recusa_fala_longa_sem_pontuacao() -> None:
    """Sem ponto final o v3 lê tudo num sopro único, pior que o original."""
    corrido = (
        "amor acho que eu me confundi ali foi mal aquela pagina que voce abriu "
        "ta certinha e ali mesmo que voce escolhe o plano"
    )
    assert not voice_director._usavel(corrido, corrido)


def test_aceita_fala_pontuada() -> None:
    assert voice_director._usavel("Oi amor. Deixa eu te explicar. É bem simples.", "x")


def test_aceita_frase_curta_sem_ponto() -> None:
    """Resposta curta de DM não precisa de ponto para soar bem."""
    assert voice_director._usavel("quem sabe hein", "quem sabe hein")


def test_recusa_vazio() -> None:
    assert not voice_director._usavel("", "algum texto")
