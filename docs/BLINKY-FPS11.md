# Blinky 11 — limite à 20 FPS

À la demande de l'utilisateur, la présentation native est plafonnée à
20 images par seconde. La cible d'interpolation MM est également fixée à
20, afin de ne pas générer des images intermédiaires destinées à 30 ou
60 FPS. La simulation et la production audio conservent leur cadence MM.

Le backend de fenêtre démarre à 20 FPS et borne les demandes supérieures
à 20. Le renderer utilise effectivement ce plafond pour son budget de
présentation, au lieu de convertir les demandes inférieures à 60 en 30.
Une ancienne configuration à 30/60 FPS, ou l'option de correspondance au
rafraîchissement de l'écran, ne rétablit donc pas une limite supérieure.
Le menu inférieur indique « Presentation: 20 FPS (fixed) » ; les autres
réglages restent disponibles.

Les corrections d'orientation de Blinky 10 sont conservées. Le marqueur
inférieur devient « Blinky 11 » et le journal commence par
« Blinky runtime: fps cap 11 (20 FPS) ».

Les scénarios existants du backend vérifient le démarrage à 20, les demandes
20/30/60/999, les valeurs non positives et une cible inférieure à 20.
Les contrôles hôtes et la compilation ne constituent pas un essai console.
Le plafond ne garantit pas d'atteindre 20 FPS si le rendu prend plus de 50 ms.

Pour l'installation, remplacer le 3DSX et son SMDH dans /3ds/2ship/ ou
réinstaller la nouvelle CIA. Conserver les archives O2R et les sauvegardes.
