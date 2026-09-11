import json
import sys
from datetime import datetime, timedelta, timezone

sys.stdout.reconfigure(encoding="utf-8")

BR = timezone(timedelta(hours=-3))
ALVOS = {
    "1271608568365383": "euricelio_faco",
    "1550828799575385": "liviagomes19099",
}

eventos = []
with open("logs.json", encoding="utf-8") as handle:
    for linha in handle:
        linha = linha.strip()
        if not linha.startswith("{"):
            continue
        try:
            item = json.loads(linha)
        except json.JSONDecodeError:
            continue
        texto = json.dumps(item, ensure_ascii=False)
        if not any(alvo in texto for alvo in ALVOS):
            continue
        eventos.append(item)

eventos.sort(key=lambda i: i["timestamp"])
for item in eventos:
    quando = datetime.fromtimestamp(item["timestamp"] / 1000, BR).strftime("%H:%M:%S")
    quem = next((nome for k, nome in ALVOS.items() if k in json.dumps(item)), "?")
    print(f"===== {quando}  {quem}  {item.get('requestPath')}")
    for log in item.get("logs") or []:
        msg = log["message"]
        msg = msg.replace("\n", " | ")[:300]
        print(f"   [{log['level']}] {msg}")
    print()
