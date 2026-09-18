# Régressions maintenues — Blinky 07

Définir `CXX` vers un compilateur C++20 pour PC, puis exécuter `python scripts/verify_port.py`.
Le lanceur couvre précontrôles O2R, entrées MM, teardown, timing/audio, ADPCM, mixer,
fenêtre/NDSP/APT, combiner et renderer de production, ZIP/index, publication des
ressources, caches de scènes, pointeurs audio et contrats mémoire.

Le runner `test_stability_audit1.py` a été réécrit pour les fonctions actuelles :
37 cas d’alias, de limites binaires, de textures, de publication concurrente,
de durée de vie des ressources et de métadonnées XML. Les 9 fixtures pertinentes
ont été conservées. Les anciens tests/faux SDK de NDSP ont été retirés : les
régressions du backend Blinky vérifient sa file et son cycle de vie.

La garde d’adresses des notes audio exécute maintenant ses contrôles sur Windows
avec une base d’image fixe, ou sur Linux avec un binaire non PIE. Les sondages
crash26 exécutent les fonctions actuelles et ne requièrent plus UBSan.

Le packager est testé avec le vrai bannertool pour les PNG et SMDH/CBMD fournis.
Les tests d’horodatages préservent les octets des sources et les anciens caches.
Certaines fixtures de liens symboliques ou CMake/cc peuvent être ignorées si le
système ne fournit pas les prérequis; le journal le précise.

Les tests hôte ne simulent ni PICA200, ni le DSP, ni une carte SD. Les sanitizers
sont facultatifs (`test_stability_audit1.py --sanitizers`) et ne sont pas déclarés
actifs lorsqu’ils sont absents. La procédure console est dans
`docs/BLINKY-HARDWARE-TESTS.md`.

Les anciens tests stéréo/SoH/FPS60/wizard et les patchs historiques sont archivés
dans le ZIP de sources complet de la livraison 06, extérieur au source courant.
Ne pas restaurer une ancienne backend pour faire passer un test devenu obsolète.
