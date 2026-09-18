# Blinky 07 — effets de jeu sur PICA200

## Constat matériel de 06

La photo montre Bourg-Clocher dans le bon sens, à 967,5 ms/image : 363,8 draws,
119 triangles GPU et 2 081,3 triangles CPU par image. Le journal « performance
fix 06 » montre un compteur CPU stable dans le menu, puis une forte hausse en
jeu. Les replis dominants sont fragment-effects pour le brouillard/alpha et
les limites UV. Le JSON à la frame 600 ne contient pas tous les shaders du journal.

## Changements de 07

Le brouillard utilise une rampe alpha de 256×8 texels sur la troisième unité
de texture (8 Kio linéaires). Le shader transmet le facteur avec interpolation
perspective ; TexEnv mélange la couleur du brouillard et le combiner. Il suit
l'attribut LUS et ne remplace pas le brouillard par une approximation en fonction de Z.

Les limites UV coupent le triangle aux changements de fonction avant de
borner les coordonnées. L'interpolation homogène conserve couleurs, brouillard
et limites variables. Borner seulement les trois coins déformerait les bords.
Les tests comparent les points intérieurs à la formule perspective d'origine
et vérifient la conservation de surface.

Les découpes transparentes utilisent deux passes partageant les mêmes sommets.
La première teste l'alpha et fixe l'alpha des fragments survivants sans écrire
Z ; la seconde écrit RGB opaque et la profondeur demandée. Le test Z d'origine
reste respecté, y compris à profondeur égale. Le seuil PICA travaille sur 8 bits :
près de 0,19, la quantification peut différer du calcul flottant GLSL.

Les lots regroupent les triangles aux états TexEnv identiques dans un appel
LUS. Ils sont vidés avant copies, mutations de texture et clôtures. Les textures
de 1, 2 ou 4 texels dont la période remplit le stockage minimal PICA utilisent
un padding périodique, y compris en miroir. Les changements de sampler
reconstruisent ce padding après la clôture nécessaire.

## Vérifications

scripts/verify_port.py --cxx <compilateur hôte> exécute les régressions maintenues.
Les tests compilent le vrai renderer/décodeur LUS, capturent les commandes SDK
et évaluent indépendamment leurs fragments.

- 2 560 fragments des shaders du menu passent sur GPU.
- 8 352 fragments des variantes de jeu brouillard/clamp et 696 triangles de partition passent.
- 6 144 cas de découpe alpha/profondeur passent, y compris les égalités Z.
- 300 triangles alpha compatibles sont envoyés en deux commandes, sans copies CPU.
- 5 184 texels de padding repeat/mirror/clamp et les transitions de sampler passent.
- Les régressions de raster CPU, readback, profondeur, ownership et clôture restent actives.

Ces tests ne sont pas une émulation PICA200. Le gain de FPS, la mémoire libre
et le rendu de 07 doivent être mesurés sur console. Les variantes signées,
certains conflits de sources, le grayscale et les répétitions NPOT non
représentables gardent un chemin CPU correct. Le compteur CPU reste réel.

## Contrats publics consultés

Cette extension est écrite dans Blinky à partir du
[shader LUS](https://github.com/kenix3/libultraship/blob/7f9b86a593c526fc42261d7fe197100cecf57178/src/fast/shaders/opengl/default.shader.glsl),
de [TexEnv Citro3D](https://github.com/devkitPro/citro3d/blob/master/source/texenv.c),
des [états de mélange](https://github.com/devkitPro/citro3d/blob/master/source/effect.c)
et des [registres PICA](https://www.3dbrew.org/wiki/GPU/Internal_Registers).
Aucun renderer alpha 3 n'est importé. Voir BLINKY-PROVENANCE.md pour le
périmètre exact des créations Blinky et des dépendances conservées.
