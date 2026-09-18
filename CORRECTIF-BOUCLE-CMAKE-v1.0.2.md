> Document historique : ses patchs, anciens backends et anciennes commandes se rapportent aux livraisons archivées. Pour Blinky 07, utiliser README-BUILD-FR.md et tests/README-BLINKY.md.

# 2Ship3DS — correctif du wizard v1.0.2

## Lancer cette version

Arrêter l'ancien wizard avant toute manipulation. Extraire ce ZIP complet dans
un **nouveau dossier**, par exemple `C:\dev\2Ship3DS-v1.0.2`, puis double-cliquer
sur le `LANCER-WIZARD.bat` extérieur. Il repère le sous-dossier `2Ship3DS`.

Conserver `C:\devkitPro` et choisir **Reconstruction propre**, puis **Compiler**.
Il n'est pas nécessaire de réinstaller devkitPro. Rechoisir les archives et
visuels seulement si leur copie/personnalisation est souhaitée : les anciens
chemins personnels du wizard ne sont pas inclus dans ce nouveau ZIP.

Les sources AUDIO-FIX sont déjà présentes. Aucun nouveau CIA/3DSX précompilé
n'est fourni. Les sorties réussies restent dans `2Ship3DS/dist-wizard/BUILD-...`.

## Défaut retrouvé dans le ZIP transmis

Le journal inclus dans `LANCER-WIZARD.zip` termine par :

```text
ninja: error: manifest 'build.ninja' still dirty after 100 tries, perhaps system time is not set
```

Les métadonnées du ZIP montrent l'ordre temporel suivant. Il ne s'agit pas
seulement de l'affichage local : le champ ZIP étendu UTC confirme le décalage.

| Fichier | Heure ZIP locale | Heure UTC étendue, 16 septembre 2026 |
|---|---|---|
| `cmake/3DS.cmake` | 08:09:54 | 12:09:54 UTC |
| `third_party/build-deps/prism/CMakeLists.txt` | 08:09:54 | 12:09:54 UTC |
| `third_party/libultraship/CMakeLists.txt` | 08:09:54 | 12:09:54 UTC |
| `third_party/libultraship/build-3ds/CMakeCache.txt` | 05:22:52 | 09:22:53 UTC |
| `third_party/libultraship/build-3ds/build.ninja` | 05:25:28 | 09:25:28 UTC |

Les entrées CMake sont donc encore **2 h 44 min 26 s plus récentes** que le
manifeste final. Ninja utilise l'ordre des dates de modification pour décider
quelles sorties régénérer; il régénère/recharge son propre manifeste si une
entrée est plus récente. Une date de source toujours dans le futur entretient
cette boucle. Référence primaire :
https://ninja-build.org/manual.html

Un décalage de fuseau lors de la création/extraction de l'ancien ZIP explique
ces données; ce n'est pas une preuve que l'horloge Windows est mal réglée,
ni que OneDrive a causé le problème. Le correctif ne change aucune horloge.

## Changements de cette version

1. **Dates du nouveau ZIP normalisées à une date ancienne fixe**, y compris le
   champ UTC : pas de fichiers datés de quelques heures dans le futur à
   l'extraction. Cette date de distribution n'est pas une date d'auteur.
2. **Détection et réparation des dates futures avant CMake**, dans les seules
   arborescences d'entrée du build. Seuls les horodatages concernés changent;
   les octets des fichiers restent identiques. `third_party/build-deps` est
   bien traité comme source, pas comme cache.
3. **Anciens caches conservés puis reconstruction** si une réparation est
   nécessaire, pour ne pas masquer une modification dans un build incrémental.
   Les caches deviennent `*.avant-horodatages-<date>-<id>`. Le mode propre
   préexistant conserve aussi ses caches, avec `*.avant-wizard-...`.
4. **Contrôle Ninja à blanc après la configuration de libultraship**. Si son
   manifeste veut déjà relancer CMake, la compilation s'arrête immédiatement
   et conserve `third_party/libultraship/build-3ds/ninja-regeneration-diagnostic.txt`.
   Les lignes `ninja explain` désignent l'entrée problématique. La vérification
   a une limite de 30 secondes; elle n'exécute pas de commande de compilation.

La régénération automatique CMake n'est **pas désactivée**. Les modifications
ultérieures de CMake continuent de déclencher une vraie reconfiguration.
Le contrôle à blanc est limité à libultraship : le graphe du jeu possède des
vérifications de glob légitimes, qu'il ne faut pas confondre avec cette boucle.

Le bouton **Vérifier** reste non destructif : la réparation d'horodatages
intervient au moment de **Compiler**, pas lors d'une simple vérification.
Les fichiers devkitPro externes, les archives `.o2r`/`.otr`, les ROM et les
sauvegardes ne sont pas retouchés. Un fichier externe daté dans le futur
provoque un diagnostic plutôt qu'une modification silencieuse du SDK.

Le build direct `python build.py ...` bénéficie aussi du correctif, ainsi que
`scripts/build_lus_3ds.py`. Après une réparation invalidant les caches,
`--skip-lus` ne permet pas de réutiliser une vieille bibliothèque : le script
annonce la reconstruction nécessaire et reconstruit LUS.

## Préservation du jeu

Aucun changement de contenu dans le code du jeu, du rendu, de l'audio, de la
stéréoscopie, des CMakeLists ou du toolchain CMake. Les changements exécutables
concernent uniquement `build.py`, `scripts/build_lus_3ds.py`, le nouveau
`scripts/build_clock.py`, et la version/validation des fichiers du wizard.
Le packager et ses visuels sont conservés.

Empreinte SHA-256 de `third_party/2ship/mm/src/audio/lib/playback.c` :

```text
e462a5e0d6bb641e768f692c5c3f6da1ee306bdf6c5fb06b5ecb6605a24e0b18
```

L'archive nettoyée omet les anciens caches, logs d'exécution personnels,
réglages locaux et verrous. Rien n'est supprimé de votre ZIP original ni de
votre PC par la création de cette copie. Les crédits/licences présents dans
les sources sont conservés; ce ZIP n'ajoute aucune autorisation de publication.

## Vérifications réellement exécutées

- **15 tests du nouveau correctif**, dont reproduction réelle des 100 relances
  avec CMake/Ninja sur un petit projet hôte, réparation puis compilation et
  exécution réussies, second build sans travail, et reconfiguration conservée
  après une vraie modification CMake.
- **Répétition sur les arborescences du ZIP transmis** : 8 831 dates UTC de
  fichiers d'entrée réappliquées puis corrigées; 8 832 empreintes de contenu
  identiques avant/après. Les deux anciens caches sont conservés. Le second
  passage ne modifie rien. Ce contrôle ne compile pas le jeu.
- **43 tests existants du wizard**, sans réécriture de leurs assertions.
- **Cinq scripts de tests audio**, dont le test de garde avec `--require-fixed`.
- Création réelle d'icône/bannière avec le bannertool Linux fourni.

Les journaux sont dans `validation/wizard-v1.0.2/`. Les doubles utilisés par
les tests de pilotage du wizard ne constituent pas une compilation ARM.

**Non exécutés ici :** interface Windows, compilation complète du jeu avec
devkitARM, installation CIA/3DSX, essai sonore ou gameplay sur New 3DS.
Le correctif traite la boucle de build observée; il ne garantit pas l'absence
d'autres erreurs de compilation, ne répare pas de nouvelles coupures audio
et ne traite pas le crash de transition du premier jour.
