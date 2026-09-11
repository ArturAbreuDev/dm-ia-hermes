from app.services import stories
from app.store import memory, story_context


def _limpar() -> None:
    with memory._sqlite() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS story_context (id TEXT PRIMARY KEY, description TEXT NOT NULL, kind TEXT NOT NULL, created_at TEXT NOT NULL)")
        conn.execute("DELETE FROM story_context")


def test_nota_salva_e_volta_no_contexto() -> None:
    _limpar()
    story_context.save("teste-1", "fui na Expointer ver os animais", kind="nota")
    itens = story_context.recent()
    assert itens[0]["description"] == "fui na Expointer ver os animais"
    assert itens[0]["quando"] == "hoje"


def test_contexto_entra_no_prompt() -> None:
    _limpar()
    story_context.save("teste-2", "fui na Expointer", kind="nota")
    bloco = stories.prompt_block()
    assert "fui na Expointer" in bloco


def test_resposta_a_story_aparece_no_prompt() -> None:
    _limpar()
    bloco = stories.prompt_block(replying_to="postei uma selfie no espelho")
    assert "postei uma selfie no espelho" in bloco
    assert "nunca copie" in bloco.lower()


def test_sem_nada_o_bloco_fica_vazio() -> None:
    _limpar()
    assert stories.prompt_block() == ""


def test_descricao_em_cache_nao_chama_a_api() -> None:
    _limpar()
    story_context.save("story-abc", "mostrei meu café da manhã")
    # URL inválida de propósito: se usar o cache, nem tenta baixar.
    assert stories.describe_story("story-abc", "http://invalido") == "mostrei meu café da manhã"
