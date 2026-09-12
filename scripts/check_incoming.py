"""Confere o que a Lívia "percebe" de cada tipo de mensagem que chega."""

from __future__ import annotations

import sys

from app.services import incoming

sys.stdout.reconfigure(encoding="utf-8")

CASOS = [
    ("texto puro", {"text": "oi"}),
    (
        "vídeo com legenda",
        {"text": "olha isso", "attachments": [{"type": "video", "payload": {"url": "x"}}]},
    ),
    ("vídeo sem legenda", {"attachments": [{"type": "video", "payload": {"url": "x"}}]}),
    ("reel", {"attachments": [{"type": "ig_reel", "payload": {"url": "x"}}]}),
    (
        "post compartilhado com legenda",
        {"text": "kkkk", "attachments": [{"type": "share", "payload": {"url": "x"}}]},
    ),
    ("coração", {"attachments": [{"type": "like_heart"}]}),
    (
        "resposta a story dela",
        {"text": "que linda", "reply_to": {"story": {"id": "1", "url": "u"}}},
    ),
]

for nome, mensagem in CASOS:
    lido = incoming.read(mensagem)
    print(f"  {nome:32} kind={lido.kind:14} is_media={lido.is_media!s:5} texto={lido.text!r}")
    if lido.story_reply is not None:
        print(f"  {'':32} story_reply={lido.story_reply!r}")
