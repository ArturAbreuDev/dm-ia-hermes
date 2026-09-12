"""Confere a tela de bloqueio do diário sem precisar publicar."""

from __future__ import annotations

import os
import sys

os.environ.setdefault("DIARY_PASSWORD", "teste123")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
cliente = TestClient(app)
SENHA = "teste123"

pagina = cliente.get("/diario", params={"k": SENHA})
print("GET /diario ->", pagina.status_code)
for marca in (
    "Não responder",
    'name="arroba"',
    "/diario/bloquear",
    "/diario/liberar",
    "Ninguém bloqueado",
    "O que ela sabe",
):
    print("  ok    " if marca in pagina.text else "  FALTA", marca)

vazio = cliente.post(
    "/diario/bloquear", data={"k": SENHA, "arroba": "   "}, follow_redirects=False
)
print("@ vazio ->", vazio.status_code, vazio.headers.get("location"))

inexistente = cliente.post(
    "/diario/bloquear", data={"k": SENHA, "arroba": "@nao_existe_xyz"}, follow_redirects=False
)
print("@ inexistente ->", inexistente.status_code, inexistente.headers.get("location"))

sem_senha = cliente.post(
    "/diario/bloquear", data={"k": "errada", "arroba": "@alguem"}, follow_redirects=False
)
print("senha errada ->", sem_senha.status_code)

aviso = cliente.get("/diario", params={"k": SENHA, "aviso": "nao-achei"})
print("aviso conhecido aparece:", "Não achei esse @" in aviso.text)

forjado = cliente.get("/diario", params={"k": SENHA, "aviso": "<script>x</script>"})
print("aviso forjado ignorado:", "<script>x</script>" not in forjado.text)

# Com alguém silenciado a lista precisa mostrar o @ e o botão de liberar. O @ vai
# semeado junto para a página não sair buscando perfil na API durante o teste.
from app.store import memory  # noqa: E402

FALSO = "igsid-de-teste-999"
memory.set_muted(FALSO, True)
memory.remember_username(FALSO, "fulano_teste")

com_bloqueio = cliente.get("/diario", params={"k": SENHA})
print("\ncom alguém silenciado:")
for marca in ("@fulano_teste", "/diario/liberar", "liberar"):
    print("  ok    " if marca in com_bloqueio.text else "  FALTA", marca)

soltou = cliente.post(
    "/diario/liberar", data={"k": SENHA, "igsid": FALSO}, follow_redirects=False
)
print("POST liberar ->", soltou.status_code, soltou.headers.get("location"))
print("saiu da lista:", "@fulano_teste" not in cliente.get("/diario", params={"k": SENHA}).text)
print("lead limpo:", memory.get_lead(FALSO))
