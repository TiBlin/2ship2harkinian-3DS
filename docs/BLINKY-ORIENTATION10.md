# Blinky 10 — orientation du monde et du HUD

La photo de Blinky 09 montre le monde à l'envers, les positions verticales du
HUD inversées et ses textes encore lisibles. Elle affiche 4,3 FPS, 234,5 ms,
2 773,2 triangles GPU et 66,3 triangles CPU par image. Le journal récupéré
sur la SD confirme le marqueur 09, le démarrage du jeu et les deux chemins
de rendu. Ces observations portent sur 09, pas sur 10.

## Cause et correction

Le viewport PICA et le viewport logique du moteur font croître Y du bas vers
le haut. En mémoire tuilée, PICA écrit cette ligne à `hauteur_allouée - 1 - y`.
Le raster CPU écrivait directement la ligne y : un même triangle changeait
donc de sens selon le chemin utilisé. Les snapshots de couleur **et** de
profondeur emploient désormais la conversion PICA. La hauteur allouée est
utilisée, y compris pour une cible dont la taille logique n'est pas une
puissance de deux.

Le sampler PICA inverse lui aussi les lignes tuilées. L'upload plaçait déjà
les texels dans ce sens, mais le shader appliquait encore `1 - v` aux textures
ordinaires. Ce retournement supplémentaire est supprimé. Les textures
ordinaires et les textures de framebuffer utilisent les mêmes coordonnées
normalisées, ajustées à leur taille allouée.

La présentation finale utilise la rotation Citro3D `(x, y) -> (y, -x)`.
L'ancienne transformation `(-y, -x)` ajoutait une réflexion. Enfin,
`GetClipParameters` transmet au moteur le drapeau `invertY` de la cible
active. Les copies, lectures CPU et lectures de profondeur conservent leur
contrat logique ; aucune inversion supplémentaire ne leur est ajoutée.

Les quatre corrections doivent être considérées ensemble. Une simple
inversion de l'écran masquait une partie du problème et inversait les
textes ou les triangles issus de l'autre chemin.

## Copie évitée

Le raster CPU ne prend plus de snapshot d'un framebuffer simplement resté
lié à une unité que le combiner ne lit pas. Le filtre tient aussi compte des
masques et textures de remplacement réellement utilisés. Le test reproduit
quatre copies supplémentaires pour deux triangles avec 09 ; 10 conserve
les mêmes pixels sans ces copies. Cela ne mesure pas le gain sur console.

## Contrats publics consultés

Cette correction est écrite dans Blinky ; aucun composant de l'alpha 3
n'est importé. Les sources suivantes servent à vérifier les conventions
matérielles et la projection, sans en reprendre une implémentation :

- [Citro3D : projection inclinée](https://github.com/devkitPro/citro3d/blob/master/source/maths/mtx_orthotilt.c)
- [Citro3D : viewport](https://github.com/devkitPro/citro3d/blob/master/source/base.c)
- [Citro3D : framebuffer](https://github.com/devkitPro/citro3d/blob/master/source/framebuffer.c)
- [Azahar : adressage couleur/profondeur PICA](https://github.com/azahar-emu/azahar/blob/master/src/video_core/renderer_software/sw_framebuffer.cpp)
- [Azahar : coordonnées et sampler PICA](https://github.com/azahar-emu/azahar/blob/master/src/video_core/renderer_software/sw_rasterizer.cpp)

## Vérification

La régression graphique couvre des repères asymétriques, une surface dont
les dimensions logiques diffèrent de l'allocation, les deux chemins de
rendu et la présentation. Le modèle GPU hôte est volontairement limité aux
cas testés ; il ne simule ni tous les shaders PICA ni l'écran physique.
Les contrôles négatifs emploient le renderer 09 conservé, afin de vérifier
que les nouveaux tests détectent le défaut.

Sur console, l'écran inférieur doit afficher **Blinky 10** et le journal
`Blinky runtime: orientation fix 10`. Contrôler le menu des sauvegardes,
le monde, les cœurs, les rubis et le texte du bouton Attack dans la même
sauvegarde. Le décor et les positions du HUD doivent être à l'endroit,
avec les caractères et les motifs de texture dans le bon sens. Les scènes
graphiques décrites dans BLINKY-HARDWARE-TESTS.md permettent de séparer ces
contrôles. Réinstaller la CIA pour mettre à jour le titre installé.

La validation logicielle et la compilation ne remplacent pas cet essai.
Aucun nouveau FPS, résultat audio ou comportement HOME/capot de 10 n'est
annoncé comme validé. Les auteurs et licences MM, LUS et SDK sont conservés.
