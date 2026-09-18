# Validation New 3DS — Blinky 11

Agent : aucun test matériel. L'utilisateur a confirmé les formats 3DSX et CIA
de la migration 01, puis « ça marche » pour la migration 02. Aucun de ces
retours ne valide le renderer, le runtime ou les commandes de la migration 04.

La migration 04 plante « direct au démarrage » ; voir BLINKY-CRASH-28.md.
Le correctif 05 atteint maintenant le menu sur la console de l'utilisateur.
Sa photo montre un miroir gauche-droite et 996,8 ms/image ; son journal confirme
la version 05 et plusieurs shaders passant par le CPU. Ce retour ne confirme
pas le son, HOME, le capot ni la persistance des réglages.

La photo de 06 confirme le sens du texte et l'accès à Bourg-Clocher, mais
montre 967,5 ms/image, 119 triangles GPU et 2 081,3 triangles CPU par image.
Les journaux confirment les replis d'effets de jeu. Ces constats ont guidé
les extensions GPU de 07, décrites dans BLINKY-PERFORMANCE-07.md.

L'utilisateur signale les deux écrans noirs avec 07, en CIA et en 3DSX.
Le journal SD confirme un arrêt unordered_map::at après l'initialisation
Citro3D. Le correctif 08 restaure l'entrée de backend4 manquante dans le
menu MM, sans modifier les optimisations graphiques de 07.

Les dumps 29 et 30 correspondent à 08, en CIA et en 3DSX. Ils montrent le
scanner d'archives utilisant un vecteur déjà libéré. Le correctif 09 conserve
le propriétaire pendant le parcours ; voir BLINKY-CRASH-29-30.md.

La photo de 09 confirme l'accès à Bourg-Clocher : 4,3 FPS, 234,5 ms/image,
2 773,2 triangles GPU et 66,3 triangles CPU/image. Le monde et les positions
du HUD sont verticalement inversés. Le journal SD confirme 09 et ne rapporte
aucun dessin rejeté ; il contient une pause/reprise, sans validation du son
ni du capot. La correction coordonnée des lignes mémoire, UV et rotation
est décrite dans BLINKY-ORIENTATION10.md. Aucun essai matériel de 10 n'a
encore été effectué.

La version 11 conserve les corrections de 10 et rétablit une limite fixe
de 20 FPS à la demande de l'utilisateur. Voir BLINKY-FPS11.md. Aucun retour
console de 10 ou de 11 n'est encore enregistré ici.

## Vérification prioritaire de 11

L'écran inférieur doit afficher « Blinky 11 » et le début du journal
« Blinky runtime: fps cap 11 (20 FPS) ». Une installation CIA doit être mise
à jour avec la nouvelle CIA ; copier le 3DSX ne remplace pas ce titre.

Avec filtre Linear, ouvrir la même sauvegarde et revenir à Bourg-Clocher.
Attendre six images avant de relever FPS, ms, GPU tris/frame et CPU tris/frame.
Les compteurs sont des moyennes, pas des totaux depuis l'intro. Comparer aussi
le menu de sauvegardes. Vérifier d'abord le sens du décor, la position des
cœurs et des rubis et le sens du texte Attack. Contrôler ensuite contours, brouillard, transparences et bords
des textures en déplacement. Les effets ciblés doivent passer sur GPU ;
d'autres shaders gardent le raster CPU. La présentation est plafonnée à
20 FPS ; aucun FPS matériel de 11 n'est encore mesuré.

Changer un réglage, relancer et vérifier sa persistance. Vérifier ensuite son,
HOME et capot séparément : les photos disponibles ne les valident pas.

## Installation et retour arrière

Conserver la précédente livraison fonctionnelle. Copier le contenu SD de cette
livraison en conservant les archives, sauvegardes et configuration existantes.
Le titre CIA conserve l'identifiant du port : son installation met à jour ce
titre. Tester d'abord le 3DSX, puis la CIA. Les deux utilisent sd:/3ds/2ship.
mm.o2r doit être issu de vos données et compatible 2Ship 5.x ; 2ship.o2r doit
correspondre à 5.0.1. Aucun de ces assets n'est inclus ici.

## Cinq contrôles graphiques

Créer sd:/3ds/2ship/blinky-smoke.txt contenant 1 (puis changer le chiffre entre
deux lancements). Les essais utilisent la vraie application et le vrai LUS.

| Chiffre | Résultat attendu | Un échec suggère |
| --- | --- | --- |
| 1 | Triangle central : bas gauche rouge, bas droit vert, sommet bleu, fond noir | Attributs, rotation LCD, viewport ou combiner SHADE |
| 2 | Rectangle à bord noir ; haut gauche rouge, haut droit vert, bas gauche bleu, bas droit blanc | Tuilage ABGR/Morton, UV ou rotation |
| 3 | Triangle vert proche conservé devant le rouge dans leur recouvrement | Clear Z, sens de comparaison ou conversion clip |
| 4 | Rouge à moitié transparent sur le vert : recouvrement jaune sombre | Alpha ou mélange |
| 5 | Même motif qu'en 2, environ moitié moins lumineux | TEXEL0×SHADE ou interpolation de couleur |

Le chiffre 0 fait défiler les scènes toutes les 240 frames présentées. Noter
la scène exacte et photographier **les deux écrans**. Les tests logiciels ne
permettent pas de cocher ces cinq cases à la place de cette observation.

## Jeu normal, commandes, cadence

Supprimer ou renommer blinky-smoke.txt. Vérifier le titre, l'ouverture d'une
sauvegarde, l'intro puis Bourg-Clocher. Une scène smoke persistante indique que
le fichier est encore présent. Observer aussi le menu pause et les photos,
qui exercent copies et orientations des framebuffers.

A/B correspondent à A/B N64 ; L/R à L/R ; ZL à Z ; X à C-haut, Y à C-gauche,
ZR à C-droite ; Start ouvre la pause ; D-pad, Circle Pad et C-Stick sont lus.
Quatre zones tactiles en bas fournissent C-gauche/haut/bas/droite. SELECT ou
une touche sur le titre de l'écran inférieur ouvre le menu. Tester une
modification, fermer, relancer et vérifier sa persistance. Les anciens profils
SDL ne sont pas convertis automatiquement. La gyroscopie n'est pas fournie.

Comparer 30 puis 60 dans ce menu, en relevant FPS, CPU tris/frame et uploads/frame.
Un compteur CPU tris/frame élevé avec des FPS faibles indique des formules à
accélérer, pas une preuve d'échec audio. Aucun minimum de FPS n'est garanti.

## Audio et lifecycle

Avec un volume modéré, créer blinky-tone-test.txt : son stéréo 440 Hz propre,
sans variation de hauteur. Retirer le fichier pour tester musique, voix et
effets MM. Noter les compteurs de file et d'erreurs. Une file vidée est un
indicateur, pas à elle seule une preuve de coupure audible.

Sur titre puis en jeu : HOME, attendre cinq secondes, revenir ; fermer le
capot dix secondes, rouvrir ; refaire trois fois. Image et son doivent reprendre,
sans touche bloquée. Fermer enfin depuis HOME. Refaire sur CIA après le 3DSX.
Comparer les compteurs de pause et les lignes Blinky lifecycle de blinky.log.

## À retourner en cas d'échec

Format lancé, modèle exact, scène ou action, délai, dernier texte de l'écran
inférieur, photo des deux écrans ; fichiers sd:/3ds/2ship/blinky.log et
blinky-shaders.json. Le journal est
réinitialisé au lancement : le copier avant une nouvelle tentative.
Si l'application quitte avant le titre, lire sa dernière ligne fatal/startup.
Un rejet Prism est explicitement consigné ; ne pas le classer comme rendu réussi.
