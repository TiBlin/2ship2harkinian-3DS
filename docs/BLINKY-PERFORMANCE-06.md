# Blinky 06 — menu accéléré et présentation corrigée

## Observations sur la livraison 05

La photo de l'utilisateur montre le menu de sauvegardes à 1,0 FPS / 996,8 ms,
avec le texte inversé gauche-droite sur l'écran supérieur. L'écran inférieur
est dans le bon sens. Le journal récupéré sur sa carte SD commence par
« Blinky runtime: crash28 fix 05 » et confirme le démarrage du vrai jeu.

Entre les images 120 et 240, le renderer rapporte 28 920 triangles supplémentaires,
dont 14 760 traités par CPU, soit 123 triangles CPU par image en moyenne.
La mémoire linéaire disponible reste à 12 645 888 octets et les uploads à 319.
Ces compteurs ne mesurent pas le temps de chaque shader. Ils permettent de
cibler la voie logicielle sans attribuer la lenteur à un manque de mémoire.

Le rapport contient quatre variantes refusées par la voie GPU pour conflit
de constantes TexEnv :

| shaderId0 | shaderId1 | Opération concernée |
| --- | --- | --- |
| 0000000001082821 | fffffffffffe0001 | Interpolation entre deux couleurs, alpha texturé |
| 0000000001082821 | fffffffffffe0021 | Même opération avec seuil alpha |
| 000000000108010c | fffffffffffe0001 | Couleur primitive et alpha texturé |
| d0003d32818a818a | fffffffffffe0010 | Deux cycles, mélange de textures puis de couleurs |

## Modifications

Le renderer utilise maintenant la couleur de sommet même lorsqu'elle est
constante sur le triangle. RGB et alpha sont affectés séparément à cette
couleur interpolée. Les autres couleurs constantes peuvent utiliser le
registre de chaque étage TexEnv et la couleur initiale du previous buffer.
Les écritures intermédiaires dans ce buffer sont désactivées pour conserver
la constante sur tous les étages. Cette allocation se fait par triangle :
les couleurs animées et celles des différents objets restent prises en compte.

Les produits par un s'identifient désormais à leur autre opérande. Cela évite
de consommer un registre pour une opération neutre. Les mélanges convexes
conservent leurs équations ; les formules signées ou les valeurs hors [0,1]
continuent à utiliser le rendu logiciel. Aucun shader n'est ignoré.

La coordonnée Y du rectangle de présentation natif passe de x à -x. Ce changement
inverse le sens horizontal observé sur le LCD, après rendu dans le framebuffer
logique. Les copies, les UV du jeu et les coordonnées de l'écran tactile gardent
leurs conventions existantes.

L'écran inférieur identifie la version 06 et affiche les moyennes par image
des draws, triangles GPU, triangles CPU et uploads, sur six images. Les compteurs
cumulatifs restent disponibles dans blinky.log et blinky-shaders.json.

## Vérification

Le test de régression échoue avec le renderer et le header mathématique archivés
de 05 : le premier mélange de couleurs bascule encore sur CPU. Il passe avec 06.
Le vrai renderer et le vrai décodeur LUS sont compilés dans le test hôte.

Quatre variantes issues du rapport et un cas supplémentaire avec RGB/alpha
variant indépendamment sont exercés avec 16 jeux de couleurs chacun. Les
80 triangles sont soumis à la voie GPU sans lecture CPU du framebuffer.
Un évaluateur distinct des registres TexEnv compare 2 560 fragments avec le
calcul de référence, avec une tolérance inférieure à 2/255. Les couleurs des
registres sont quantifiées en huit bits ; ce test n'émule pas la précision
interne ni la rasterisation du PICA200.

Les coins du rectangle final sont vérifiés selon l'orientation native observée.
Les tests existants continuent à vérifier les copies, la profondeur, les pixels
CPU, les dépendances de textures, les barrières GPU, l'audio, le lifecycle et
les sauvegardes de configuration. Les journaux de validation accompagnent le
paquet. L'exécution et le nombre de FPS réels de 06 restent à mesurer sur console.

Les deux variantes signées c0003d3100008218 et 010d3d318000821a du journal ne sont
pas accélérées par ce correctif. D'autres effets, dont le filtrage trois points
et certains brouillards, restent susceptibles d'utiliser le CPU. La livraison
ne certifie donc pas les performances de toutes les scènes du jeu.

Cette implémentation utilise les contrats publics de
[Citro3D TexEnv](https://github.com/devkitPro/citro3d/blob/master/source/texenv.c)
et du LUS épinglé. Aucun composant de l'alpha 3 n'est importé. Les dépendances
et les fichiers encore non réattribués restent recensés dans l'audit de provenance.
