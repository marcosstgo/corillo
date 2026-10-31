---
title: "CORILLO — Noticias · Retiran SmileBASIC 4 de la eShop tras jailbreak de Switch 2 con Hatsune Miku en Mario Kart"
description: "Un investigador usó SmileBASIC 4 para un jailbreak por software de la Switch 2 y lo demostró con personajes personalizados en Mario Kart World."
ogTitle: "Retiran SmileBASIC 4 de la eShop tras jailbreak de Switch 2 con Hatsune Miku en Mario Kart"
ogDescription: "Un investigador usó SmileBASIC 4 para un jailbreak por software de la Switch 2 y lo demostró con personajes personalizados en Mario Kart World."
badgeClass: "badge-confirm"
badgeIcon: "fa-solid fa-gamepad"
badgeLabel: "Gaming y esports"
date: "24 octubre 2026"
pubDate: 2026-10-24T11:30:01Z
heroTitle: "Retiran SmileBASIC 4 de la eShop tras jailbreak de Switch 2 con Hatsune Miku en Mario Kart"
heroSub: "Un exploit de software abre la puerta al homebrew en la consola de Nintendo, aunque con limitaciones."
summary: "El investigador Sammy Hajhamid logró un jailbreak parcial de la Switch 2 explotando SmileBASIC 4, y lo demostró añadiendo a Hatsune Miku y otros personajes a Mario Kart World. El juego fue retirado de la eShop poco después."
category: "gaming"
tags: ["Switch 2", "jailbreak", "SmileBASIC 4", "Nintendo", "homebrew"]
ai: true
sources:
  - name: "Dexerto"
    url: "https://www.dexerto.com/gaming/nintendo-pulls-game-from-eshop-after-hacker-uses-it-to-jailbreak-switch-2-put-hatsune-miku-in-mario-kart-3421332/"
  - name: "Ars Technica"
    url: "https://arstechnica.com/gaming/2026/10/switch-2-jailbreak-gives-hackers-new-ways-to-run-homebrew-and-mod-games/"
image: "/noticias/portadas/2026-10-24-retiran-smilebasic-4-de-la-eshop-tras-jailbreak-de-switch-2-con.jpg"
imageCredit: "Ilustración generada para Corillo"
---

La seguridad de la Nintendo Switch 2 recibió un golpe esta semana. El investigador Sammy Hajhamid, conocido como pepsipu, publicó un jailbreak por software que aprovecha una vulnerabilidad en SmileBASIC 4, un entorno de programación originalmente lanzado para la Switch original y compatible con la nueva consola. El exploit funciona en el firmware 23.0.1 y, según el investigador, es el primero de su tipo para la Switch 2.

## Cómo funciona el exploit

El jailbreak es 'tethered', lo que significa que requiere una PC con macOS o Linux en la misma red para ejecutar un paquete de node.js que ayuda a obtener acceso privilegiado. Hajhamid utilizó OpenAI Codex para analizar el intérprete de SmileBASIC y descubrió un desbordamiento de entero de 32 bits al eliminar elementos de un array. Ese error permitió acceso de lectura y escritura a partes de la memoria del sistema. Luego encontró un desbordamiento de búfer en el módulo de servicios FileSystem, lo que le dio privilegios adicionales y ejecución de código nativo.

El acceso obtenido es de tipo 'userland', lo que permite ejecutar homebrew, modificar juegos y respaldar partidas guardadas, pero no otorga control a nivel de kernel. Además, el jailbreak se reinicia cuando la consola se apaga.

## La demostración con Hatsune Miku

Para probar el exploit, Hajhamid modificó Mario Kart World, exclusivo de Switch 2, añadiendo personajes personalizados como Hatsune Miku, Cinnamoroll y Peter Griffin. El investigador dedicó aproximadamente dos semanas al desarrollo del jailbreak, mientras que la modificación del juego le tomó un día.

Poco después de que el jailbreak se hiciera público, SmileBASIC 4 desapareció de la eShop. No está claro si fue Nintendo o el desarrollador SmileBoom quien lo retiró. Nintendo no ha reconocido públicamente el jailbreak.

## Por qué importa

Este exploit demuestra que la Switch 2 no es inmune a las vulnerabilidades de software, aunque no es tan grave como el exploit impatchable de la Switch original de 2018. El acceso userland limita el alcance, y es probable que Nintendo lo parchee en futuras actualizaciones de firmware. Para la comunidad de CORILLO, esto abre la puerta a homebrew y mods, pero también plantea dudas sobre la estabilidad de la plataforma y las medidas que tomará Nintendo.

SmileBASIC ya había sido utilizado en un exploit de homebrew para la 3DS en 2016, conocido como smilehax. La historia se repite, y ahora la pregunta es qué tan rápido responderá Nintendo.
