# 2Ship 3DS — Blinky 09

Application Majora's Mask / 2Ship 5.0.1 pour New Nintendo 3DS, avec rendu
Citro3D, fenêtre, HID, interface inférieure, audio NDSP et lecteur O2R Blinky.
La livraison 07 accélère les effets de brouillard, de découpe transparente et
de limites UV rencontrés dans les journaux de jeu de la version 06.

Les adaptations natives historiques restantes ont été revues individuellement,
remplacées, restaurées depuis l'amont ou attribuées à leurs interfaces publiques.
Les sources officielles de MM, LibUltraShip et des bibliothèques gardent leurs
auteurs et licences : cet arbre entier n'est pas une création originale Blinky.
L'alpha 3 de 999sian a servi à la comparaison, sans import de composants.
Le GitHub personnel de l'utilisateur n'a pas été utilisé.

Lire [la provenance](docs/BLINKY-PROVENANCE.md),
[l'audit par modification](docs/BLINKY-CLEANROOM-AUDIT.md),
[les corrections graphiques](docs/BLINKY-PERFORMANCE-07.md) et
[la construction Windows](README-BUILD-FR.md).

La version 06 atteint Bourg-Clocher sur la console de l'utilisateur, avec
environ une image par seconde. La version 07 a régressé au démarrage : une entrée de menu Citro3D manquait.
Le correctif 08 rétablit ce raccord public et ajoute un test de démarrage.
Les dumps de 08 ont ensuite révélé une liste d'archives libérée avant son parcours.
Le correctif 09 conserve cette liste pendant le scan et renforce le test associé.
La version 09 doit encore être validée sur console ; les tests hôtes ne remplacent pas une exécution PICA200.
La [procédure matérielle](docs/BLINKY-HARDWARE-TESTS.md) décrit cette vérification.
Ce kit ne contient aucune ROM ni archive mm.o2r.

Voir [le correctif de démarrage 08](docs/BLINKY-STARTUP-08.md) et
[le diagnostic des dumps 29 et 30](docs/BLINKY-CRASH-29-30.md).
