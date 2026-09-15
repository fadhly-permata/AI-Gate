# aigate 🚪

Eén deur voor elke AI-provider die je gebruikt. Eén plek waar een AI-agent
het codeerwerk van je overneemt. En dat allemaal ook nog eens vanaf je
telefoon.

Verder is het een gewone Python-app: geen Docker, geen cloud-account. Je
API-sleutels en je historie blijven op je eigen apparaat.

aigate is gratis en open source — er is geen betaald abonnement en niets zit
verstopt achter een betaalmuur. Wie wil mag deze code kopiëren, dus de enige
officiële plek voor aigate is [github.com/fadhly-permata/AI-Gate](https://github.com/fadhly-permata/AI-Gate).

🌐 [English](../../README.md) · [Bahasa Indonesia](README.id.md) · [Русский](README.ru.md) · **Nederlands** · [日本語](README.ja.md) · [简体中文](README.zh.md) · [繁體中文](README.zh-tw.md) · [हिन्दी](README.hi.md)

## 's Avonds op de bank ☕

Kop thee op tafel, laptop op je schoot, en dat ene project geeft weer
foutmeldingen. Je typt één regel voor de agent en drukt op enter. In een
tabblad begint het werk: test draaien, melding lezen, herstellen, opnieuw.
Je hoeft er zelf niets voor te doen. Is de laatste fout weg, dan gaan de
fixes terug naar je main-branch en de tijdelijke branch verdwijnt vanzelf.
De thee is nog warm.

## Wat het bijzonder maakt ✨

- **Alle AI-providers achter één deur.** Je koppelt je accounts één keer;
  daarna kiest aigate zelf een provider voor elke request. Zakt er één
  weg of is je quota op, dan wordt je vraag gewoon elders beantwoord.
- **24 AI-codingtools, zo gepiept.** Ze starten in de ingebouwde
  terminal-tabbladen. Ontbreekt er een? Dan toont aigate een
  installcommando dat op dát apparaat werkt. De lijst groeit nog — in
  volgende versies kunnen tools bijkomen of veranderen.
- **Een self-heal-loop waar je bij kunt kijken.** Wijs hem naar de fouten
  in je project: aigate maakt een branch, draait de agent in een tabblad
  dat je altijd kunt inkijken, repareert de ene na de andere fout en
  mergt het resultaat terug. Ging er iets mis? Dan zegt hij dat het
  misging — hij doet nooit alsof het gelukt is.
- **Draait echt op je telefoon.** In Termux op Android installeer en
  start je aigate zonder compiler en zonder build-tools.
- **Standaard privé.** API-sleutels en historie zijn lokale data op je
  apparaat. Het enige dat je apparaat verlaat, zijn je requests naar de
  providers die je zelf hebt gekozen.
- **Fijne interface.** Licht en donker thema, acht talen in de app, en
  op een klein scherm gedraagt alles zich prima.

## Probeer het in 60 seconden ⏱️

Je hoeft vooraf niets te installeren — geen Python, geen pip, niets. Dit ene
commando pakt wat er nog ontbreekt en start aigate meteen:

```bash
bash scripts/bootstrap.sh
```

Ga daarna naar **http://localhost:8080**. Bij de eerste start pakt aigate
zelf de paar Python-pakketten die het nodig heeft. Heb je al Python 3.10 of
nieuwer? Dan kun je `run.py` nog steeds rechtstreeks draaien.

Op Windows: `pwsh scripts/bootstrap.ps1` (of
`powershell -File scripts\bootstrap.ps1` in de ingebouwde Windows PowerShell 5.1).

Is poort 8080 bezet? Neem er een andere:

```bash
AIGATE_PORT=9090 bash scripts/bootstrap.sh
```

Op Windows: `$env:AIGATE_PORT="9090"; pwsh scripts/bootstrap.ps1`.

## Op je telefoon 📱

Installeer Termux op Android, zet aigate erin en start hem zoals op een
laptop. Lastiger wordt het bij de codingtools zelf: Android pakt
pakketten anders aan dan een desktop. aigate herkent Termux en laat dan
het installcommando zien dat wél werkt — bijvoorbeeld een systeempakket
in plaats van het commando voor de desktop.

aigate is getest op Linux, Windows en Android (Termux), inclusief een
volledige Linux-distro op de telefoon.

## Technische details in de wiki 📚

Wat dit README kort houdt, staat uitgebreid in de wiki: hoe providers en
combo's werken, je codingtools koppelen, en de API aanroepen vanuit eigen
code. Goed startpunt:
[Quick Start](https://github.com/fadhly-permata/AI-Gate/wiki/Quick-Start) ·
[Providers & Combos](https://github.com/fadhly-permata/AI-Gate/wiki/Providers-and-Combos) ·
[Terminal](https://github.com/fadhly-permata/AI-Gate/wiki/Terminal) ·
[CLI Tools](https://github.com/fadhly-permata/AI-Gate/wiki/CLI-Tools).

## Status 📌

aigate is een persoonlijke, lokaal gerichte tool waaraan volop wordt
gewerkt, getest op Linux, Windows en Android (Termux). Probeer hem, breek
hem, en laat me weten waar het knelt.

---

Gemaakt met ❤️ door Fadhly Permata
