import sys

from app.services.instagram import get_user_profile
from app.services.voice import first_speakable_name

sys.stdout.reconfigure(encoding="utf-8")

IGSIDS = ["1420122640048360", "2109690816315244"]

for igsid in IGSIDS:
    profile = get_user_profile(igsid)
    print(igsid, "->", profile, "| nome usado:", first_speakable_name(profile))

print()
for name in ["Gabriela Souza", "Jo", "Xxkillerxx", "Maria", "  ", "João Pedro", "oficial insta"]:
    print(f"{name!r:<20} -> {first_speakable_name({'name': name})}")
