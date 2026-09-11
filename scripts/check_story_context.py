import sys
import uuid

from app.services.sales_agent import generate_sales_reply
from app.store import memory, story_context

sys.stdout.reconfigure(encoding="utf-8")

PERGUNTA = "voce foi na expointer né?"

# O banco local guarda entre execuções, então limpamos para o teste valer.
with memory._sqlite() as conn:
    conn.execute("DELETE FROM story_context")

print("=== SEM contexto nenhum (regra de nao negar) ===")
for _ in range(3):
    thread = f"semctx-{uuid.uuid4().hex[:8]}"
    print("  ->", generate_sales_reply(thread, PERGUNTA).reply)

print("\n=== COM o story anotado ===")
story_context.save("teste-expointer", "fui na Expointer ver os animais e comi churros", kind="nota")
for _ in range(3):
    thread = f"comctx-{uuid.uuid4().hex[:8]}"
    print("  ->", generate_sales_reply(thread, PERGUNTA).reply)

print("\n=== respondendo direto a um story ===")
thread = f"story-{uuid.uuid4().hex[:8]}"
print(
    "  ->",
    generate_sales_reply(
        thread,
        "que lugar é esse?",
        story_reply="fui na Expointer ver os animais e comi churros",
    ).reply,
)

print("\n=== o que ela sabe da propria vida ===")
for item in story_context.recent():
    print(f"  {item['quando']}: {item['description']}")
