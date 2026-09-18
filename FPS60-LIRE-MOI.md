> Document historique : ses patchs, anciens backends et anciennes commandes se rapportent aux livraisons archivées. Pour Blinky 07, utiliser README-BUILD-FR.md et tests/README-BLINKY.md.

# 2Ship3DS — AUDIO-FIX + Wizard v1.0.2-FPS60

Cette **nouvelle variante** part de `2SHIP3DS-AUDIO-FIX-WIZARD-v1.0.2.zip`.
Les sources et le wizard sont inclus. Aucun nouveau fichier du jeu `.cia`,
`.3dsx` ou `.elf` compilé n'est livré : il faut compiler sur votre PC.

## Lancer la compilation

1. Extraire entièrement le ZIP dans un **nouveau dossier**, par exemple
   `C:\dev\2Ship3DS-FPS60`. Le dossier obtenu contient `LANCER-WIZARD.bat`
   et le sous-dossier `2Ship3DS` avec les sources.
2. Double-cliquer sur `LANCER-WIZARD.bat` à la racine du dossier extrait.
   Le titre du wizard indique maintenant `v1.0.2-FPS60`.
3. Sélectionner `C:\devkitPro`, choisir **Reconstruction propre**, puis
   **Compiler**. Les choix d'archives, d'icône, de bannière et de CIA restent
   disponibles comme avant. Le SDK déjà utilisé pour la V2 reste nécessaire.

La sortie reste `2Ship3DS/dist-wizard/BUILD-.../SD/`, accessible par
**Ouvrir le résultat**. Le rapport `wizard-build-report.json` identifie le
wizard par `1.0.2-FPS60` et donne les empreintes des nouveaux fichiers produits.
N'installer que les fichiers d'une nouvelle compilation réussie.

### Avec le petit ZIP de correctif

Le petit ZIP est réservé à **cette même base v1.0.2 AUDIO-FIX**. Fermer le
wizard, fusionner son dossier `2Ship3DS` avec celui du projet existant, puis
accepter les remplacements. Ne pas créer `2Ship3DS/2Ship3DS` par erreur.
Choisir impérativement **Reconstruction propre** pour ce premier build : les
dates neutres du ZIP ne doivent pas laisser réutiliser un ancien objet compilé.
Les caches sont conservés par le mécanisme du wizard, pas effacés à l'aveugle.

## Ce qui change réellement

Le plafond effectif de 60 FPS existait déjà, mais la base sélectionnait 20 FPS
par défaut et respectait un ancien réglage sauvegardé. Cette variante :

- sélectionne `gInterpolationFPS = 60` **à chaque lancement 3DS**, après le
  chargement des réglages, même si l'ancienne configuration avait 20 ou 30;
- utilise également 60 comme valeur de repli 3DS si cette variable est absente;
- conserve le plafond effectif à 60, même lorsqu'une valeur supérieure est
  demandée, ainsi que la normalisation existante vers 20 / 30 / 60;
- conserve la possibilité de choisir un taux inférieur pendant la session.
  Le prochain lancement de cette variante repart toutefois à 60.

Le setter ajouté n'efface pas le fichier de configuration et ne demande pas
son enregistrement. Une sauvegarde générale ultérieure par le jeu ou son menu
peut naturellement enregistrer les valeurs courantes. Aucun fichier de réglages
ni sauvegarde utilisateur n'est livré, écrasé ou supprimé par ce correctif.

Il ne s'agit **pas** de remplacer `R_UPDATE_RATE` par 1 ni de faire tourner
la logique native trois fois plus vite. Le rendu utilise le chemin
d'interpolation déjà présent. À cadence logique 20 Hz, le test du code de
planification observe trois soumissions graphiques par tick (coefficients
1/3, 2/3, 1), pas trois mises à jour du jeu. Le calcul des matrices interpolées
et leur affichage sur GPU ne sont pas validés par ce test.

## Modifications et éléments préservés

Un seul fichier de production du jeu change :

`third_party/2ship/mm/2s2h/BenPort.cpp`

Les deux autres fichiers existants modifiés ne changent que l'étiquette du
wizard : `Wizard-2Ship3DS.ps1` et `wizard/build_wizard.py`. Les mécanismes de
compilation, de reprise, de packaging et de contrôle des archives sont inchangés.

Les 8 903 autres fichiers de la base sont conservés octet pour octet, dont
`playback.c` et son correctif audio, le backend NDSP, le renderer, la
stéréoscopie, CMake et la protection contre la boucle de dates futures.
Dans `BenPort.cpp`, `OTRAudio_Thread`, `Graph_ProcessGfxCommands` et
`RunCommands` sont également conservés intégralement.

Le diff est dans `patches/mm-3ds-fps60.patch`. Le manifeste de cette variante
est `fps60-profile-manifest.json`. Les anciens manifestes et guides sont des
documents historiques des livraisons antérieures, conservés comme tels :
cette fiche décrit le changement additionnel FPS60.

## Validation effectuée

Le journal complet est `validation/fps60/tests.txt`.

- Nouveau test `tests/test_mm_3ds_fps60.py` : compilation hôte des fonctions
  extraites des sources réelles; défaut absent, 18 combinaisons de réglages
  sauvegardés, taux inférieurs en session, plafond 60 et branche non-3DS.
- Pour `R_UPDATE_RATE` = 1, 2 et 3 : respectivement 60, 30 et 20 soumissions
  logiques par seconde simulée, chacune totalisant 60 soumissions graphiques,
  60 blocs audio et 32 000 frames PCM. Le worker et sa barrière sont exécutés
  sur des threads hôte; synthèse, CVar et sorties GPU/DSP sont des doubles.
- Le nouveau test échoue sur le `BenPort.cpp` original de v1.0.2, comme attendu.
- Les cinq tests audio préexistants passent sans modification de leurs
  assertions, y compris le contrôle historique négatif du filtre d'adresse.
- Les 43 tests du wizard, les 15 tests de protection des horodatages et les
  tests de création des visuels avec le bannertool Linux fourni passent.

Ces contrôles ne constituent **pas** une compilation complète devkitARM,
une exécution de l'interface Windows, une validation PCM réelle ni un test
sur New 3DS. Ils ne mesurent pas les performances du jeu.

## Limites

**60 FPS est une cible et un plafond de rendu, pas une garantie de 60 images
réellement affichées par seconde.** Le matériel peut ne pas suivre la charge.
Demander davantage d'images peut aussi aggraver un ralentissement ou des
coupures audio si la boucle de jeu n'alimente plus le DSP à temps. Aucun
gain de performance n'est revendiqué ici.

Le correctif audio antérieur est conservé, mais aucune nouvelle correction
des coupures ni du crash de transition du premier jour n'est ajoutée. Les
licences, crédits et conditions de la base restent inchangés. Ni ROM ni
archives de jeu `.o2r` ne sont incluses.
