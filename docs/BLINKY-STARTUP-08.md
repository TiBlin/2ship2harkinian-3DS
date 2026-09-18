# Blinky 08 — arrêt au démarrage après Citro3D

## Reproduction matérielle de 07

L'utilisateur rapporte les deux écrans noirs en CIA et en 3DSX. Le journal SD
du 17 septembre 2026, 21:21:24, contient le marqueur independent port 07,
l'acceptation des archives, l'initialisation de la fenêtre et de Citro3D, puis :

    Blinky fatal: unordered_map::at

Le JSON de shaders resté sur la carte date de la version précédente ; il ne
décrit pas cette exécution. Aucun problème d'archives n'est indiqué.

## Cause et correction

La restauration du fichier MM MenuTypes.h en 07 a retiré l'entrée native
FAST3D_CITRO3D (valeur4) de windowBackendsMap. Pourtant le menu effectue son
initialisation avant d'être masqué. La chaîne Gui::SetMenu -> BenMenu::InitElement
-> Menu::InitElement -> UpdateWindowBackendObjects lit windowBackendsMap.at(4).
Cette lecture lève exactement l'exception du journal.

La restauration 07 était donc incorrecte fonctionnellement. Le correctif
ajoute le raccord public conditionnel __3DS__ associant ce backend au libellé
Blinky Citro3D. Le fichier est attribué C+D : base MM et interface native.
Il ne réintroduit aucune ancienne implémentation du renderer.

Le test test_blinky_startup.py exécute le code de production du menu et ses
données de backend. Il reproduit l'exception avec la table07, puis vérifie
l'initialisation corrigée avec plusieurs configurations. Les contrats des
backends desktop sont aussi préservés.

Les optimisations de brouillard, découpes alpha, limites UV et lots de triangles
de 07 restent en place. Le marqueur runtime devient startup fix 08 et le titre
inférieur Blinky 08. La compilation et le test hôte ne remplacent pas un essai
console : l'affichage et les FPS de 08 doivent encore être observés sur matériel.

## Installation

Copier le nouveau 3DSX/SMDH pour le Homebrew Launcher. Pour le titre installé,
réinstaller la nouvelle CIA : copier seulement le 3DSX ne met pas ce titre à jour.
Conserver archives O2R, sauvegardes et configuration. Vérifier Blinky 08 sur
l'écran inférieur, puis reprendre la même sauvegarde pour mesurer GPU/CPU tris/frame.
