# Couverture de rendu Blinky 07

La photo et les journaux de 06 confirment le démarrage, le sens de l'image et
l'accès à Bourg-Clocher. Les extensions GPU de 07 sont testées sur hôte, avec
le vrai renderer et le décodeur LUS. Le collaborateur Citro3D capture les
commandes ; il n'émule pas le silicium PICA200.

| Cas | Chemin 07 | Limite |
| --- | --- | --- |
| Formules convexes à un/deux cycles | Replace/Multiply/Mix TexEnv | Une couleur interpolée, constantes par canal ; incompatibilités sur CPU |
| Brouillard | Rampe alpha sur texture 2, interpolation TexEnv | RGB constant dans chaque triangle, facteur fini dans [0,1] |
| Alpha edge | Deux passes GPU, test alpha puis écriture opaque | Seuil 8 bits >48 ; écart de quantification possible près de 0,19 |
| Limites UV des textures 0 et 1 | Partition des triangles et GPU | Limites et coordonnées finies ; interpolation homogène conservée |
| Repeat/mirror de petites textures | Padding périodique GPU | Période divisant exactement la dimension physique |
| Padding non périodique | GPU si empreintes intérieures, CPU sinon | Pas de répétition arbitraire NPOT sur PICA |
| Intermédiaires signés | CPU de référence | Le wrap signé LUS interdit un remplacement arbitraire par ADD saturé |
| Grayscale, bruit avec alpha variable, masques/remplacements, 3-point | CPU | Effets spécialisés non accélérés |
| Deux textures et permutation du second cycle | GPU/CPU | Métadonnées issues uniquement de LUS |
| Test/écriture Z, profondeur primitive | GPU/CPU | D16 inversé, précision matérielle à vérifier |
| Décalque | GEQUAL GPU/CPU | Biais dépendant de pente non implémenté |
| Framebuffers, copies et readbacks | Cibles VRAM et copies CPU | Texture servant aussi de cible active : chemin de référence |
| Shader Prism personnalisé | Rejet explicite et export JSON | Pas de compilateur Prism vers PICA |
| MSAA / stéréo | Non implémentés | Mono, sample unique |

Les lots regroupent les triangles compatibles dans un appel LUS et préservent
l'ordre. Un lot de 300 triangles alpha edge nécessite deux commandes dans le
test, sans raster CPU ; ce nombre ne prédit pas les commandes d'une scène MM.

Les essais vérifient 30 632 cas mathématiques, 2 560 fragments TexEnv du menu,
8 352 fragments de jeu avec perspective/brouillard/clamp, 6 144 cas alpha/Z et
5 184 texels de padding. Ils incluent les limites UV variables, des W différents,
la conservation d'aire après partition, les profondeurs égales et tous les alpha 8 bits.

Le JSON expose recettes, raisons et triangles CPU, toutes les 600 frames et
à la destruction ; les programmes évacués du cache n'apparaissent plus.
Les compteurs inférieurs sont des moyennes sur six images : CPU tris compte
le raster logiciel, GPU tris les triangles d'entrée acceptés avant partition.
Ces compteurs ne sont pas des temps CPU/GPU.

Les cinq scènes de blinky-smoke.txt restent disponibles ; retirer ce fichier
pour revenir aux display lists MM. Voir BLINKY-HARDWARE-TESTS.md.
