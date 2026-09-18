# 2Ship3DS — Wizard Windows v1.0.2

**Ce dossier contient les sources V2 avec le correctif audio déjà appliqué et un assistant graphique de compilation.** Il ne contient pas de nouveaux exécutables du jeu déjà compilés. Le wizard utilise la chaîne devkitPro installée sur votre PC.

## Correctif v1.0.2 — boucle Ninja/CMake

Cette version corrige les dates de sources futures avant compilation et vérifie
que le manifeste de libultraship est stable après CMake. Les caches concernés
sont conservés avant reconstruction; les sources du jeu restent identiques.
Le ZIP ne transporte plus les caches ou réglages personnels d'une exécution
précédente. Les détails, la preuve du défaut et les limites des tests figurent
dans `CORRECTIF-BOUCLE-CMAKE-v1.0.2.md`.

## Démarrage

Extraire **tout** le ZIP, idéalement dans un chemin local court, par exemple `C:\dev\2Ship3DS`. Ne pas lancer les fichiers depuis la vue compressée de l'Explorateur.

Dans le dossier contenant `build.py`, double-cliquer sur :

```text
LANCER-WIZARD.bat
```

L'interface est en français. Le lanceur utilise Windows PowerShell et Windows Forms : **pas de Tkinter, de module PowerShell à installer, de pip ni de fenêtre de terminal dans laquelle saisir la commande de build**. La console du lanceur peut rester visible derrière l'interface. Le lanceur ne change pas durablement la politique d'exécution PowerShell et ne demande pas les droits administrateur.

### 1. Compilation

- **devkitPro** : normalement `C:\devkitPro`.
- **Python** : normalement `C:\devkitPro\msys2\mingw64\bin\python.exe`. Le wizard propose aussi les installations Python Windows repérées lorsqu'il ne trouve pas celle du SDK. Choisir Python 3.10 ou ultérieur.
- **Dossier des résultats** : par défaut `dist-wizard` dans le projet. Chaque exécution réussie crée un nouveau sous-dossier `BUILD-<date>-<identifiant>`. Les résultats précédents ne sont pas écrasés.
- **Tâches parallèles** : 4 par défaut, réglables de 1 à 64.
- **Mode** : garder **Reconstruction propre** pour le premier essai. Les dossiers `build-arm` et `third_party/libultraship/build-3ds`, s'ils existent, sont renommés avec le suffixe `.avant-wizard-...`, pas supprimés. Ce choix peut consommer de l'espace disque si les anciens builds sont volumineux.
- **Créer également le CIA** : activé par défaut. Sans cette option, seuls les formats 3DSX/SMDH/ELF sont produits. Avec elle, le packager conserve aussi le CCI `.3ds` utilisé pour ses contrôles croisés CIA/CCI.

Le bouton **Vérifier** contrôle les sources, la présence du correctif audio, les principaux outils/bibliothèques, les versions de Python et CMake, les chemins de reprise, les visuels et les archives sélectionnées. Il ne compile pas et ne renomme aucun cache. Il crée uniquement ses logs/configurations et les copies temporaires nécessaires aux visuels.

Le bouton **Compiler** refait ces vérifications, reconstruit le jeu et libultraship, puis effectue le packaging. Aucune option `--skip-lus` n'est employée. **Reprendre** signifie compilation incrémentale avec les caches compatibles du même emplacement; pas réutilisation aveugle d'un ancien ELF. Les dépendances sont tout de même présentées à CMake/Ninja pour actualisation.

### 2. Archives

La case **Copier mes archives existantes dans la sortie** est désactivée par défaut : les archives ne sont pas nécessaires à la compilation du code. Pour utiliser celles déjà présentes sur votre console, la laisser désactivée et conserver ces fichiers sur la SD.

Pour préparer aussi une copie des assets dans le nouveau résultat, activer la case et choisir :

```text
mm.o2r       archives du jeu, métadonnée de version 2Ship 5.x
2ship.o2r    archive support, métadonnée de version 5.0.1
```

Le bouton **Chercher depuis une SD / un dossier** permet de sélectionner la racine de la SD, un dossier `SD`, ou le dossier contenant directement les deux archives. Il recherche notamment `3ds/2ship/`. La SD sert uniquement de **source de lecture** : aucune écriture directe sur cette carte n'est effectuée.

Les contrôles suivent la politique de version de `src/port3ds/archive_checks.h`. Ils ajoutent la détection des doublons, des ZIP chiffrés ou d'une compression non prise en charge, les CRC complets par défaut, et les empreintes SHA-256. Les ressources support ajoutées au commit du port sont recherchées; leur absence produit un avertissement, pas une modification automatique de l'archive.

**Limite :** une version et des CRC valides ne prouvent pas la validité sémantique de toutes les ressources ni le bon fonctionnement de toutes les scènes. Privilégier les deux archives déjà utilisées avec votre build V2.

Aucune extraction de ROM, conversion `.otr`, régénération d'assets ni import des archives dans le RomFS du jeu n'est effectué. Les entrées ZIP sont lues en flux, pas extraites sur le disque.

### 3. Icône et bannière

Laisser les deux champs vides conserve les visuels par défaut. Pour personnaliser :

- une image PNG/JPG/BMP est copiée et redimensionnée en **48 × 48** pour l'icône ou **256 × 128** pour la bannière; le rapport de forme est conservé et des marges noires peuvent être ajoutées;
- une icône `.smdh` déjà compilée ou une bannière `.bnr`, `.bin` ou `.banner` au format CBMD est contrôlée puis recopiée telle quelle;
- les fichiers sélectionnés ne sont jamais remplacés;
- une image de bannière utilise le son silencieux du packager. Une bannière compilée conserve son propre contenu, y compris son éventuel son.

Le TitleID reste celui du kit. Changer les visuels ne crée pas une autre identité d'application. L'icône concerne le SMDH du 3DSX et le CIA; la bannière concerne les conteneurs CIA/CCI.

### 4. Journal et arrêt

Le journal suit l'exécution dans une page séparée et indique l'étape et le temps **déjà écoulé**, sans inventer de pourcentage de compilation. En l'absence de nouvelle ligne, il indique depuis combien de temps le processus est silencieux; cela ne prouve pas à lui seul un blocage.

**Arrêter** termine l'arbre des processus de cette compilation. Fermer la fenêtre pendant une compilation demande de confirmer l'arrêt. Aucun build n'est relancé automatiquement après un échec.

Les logs complets, la configuration de chaque exécution et le rapport de vérification sont conservés dans :

```text
wizard-logs/<date-identifiant>/
    run.json
    run.preflight.json
    run.status.json
    stdout.log
    stderr.log
```

Les chemins sélectionnés sont mémorisés localement dans `wizard/settings.json`. Ce fichier et les logs peuvent contenir votre nom de session Windows ou des chemins personnels; les examiner avant de les publier.

## Récupérer les fichiers

Après une réussite, **Ouvrir le résultat** ouvre uniquement le nouveau dossier terminé :

```text
dist-wizard/
└── BUILD-<date-identifiant>/
    ├── SD/
    │   ├── 3ds/2ship/
    │   │   ├── 2ship-3ds.3dsx
    │   │   ├── 2ship-3ds.smdh
    │   │   ├── mm.o2r           # seulement si copie demandée
    │   │   └── 2ship.o2r        # seulement si copie demandée
    │   └── cias/
    │       └── 2ship-3ds.cia    # seulement si CIA demandé
    ├── 2ship-3ds.elf
    ├── 2ship-3ds.3ds            # seulement si CIA demandé
    ├── package-manifest.json
    ├── wizard-build-report.json
    └── INSTALLATION.txt
```

Copier le **contenu de `SD`** à la racine de la carte SD, en conservant les sauvegardes, les réglages et les archives existantes que vous n'avez pas demandé à recopier. Pour le CIA, installer ce nouveau fichier avec l'installateur habituel; le copier sur la SD seul ne remplace pas le titre installé.

Les dossiers `.incomplet-...` correspondent à une exécution non publiée/échouée : ne pas installer leurs fichiers. Une sortie n'obtient son nom `BUILD-...` qu'après le packaging et les copies vérifiées. Le rapport du wizard donne les empreintes des fichiers produits; le manifeste du packager décrit les exécutables sans les archives ajoutées séparément.

## Prérequis et erreurs usuelles

Utiliser le SDK qui compilait déjà cette V2. Le wizard **n'installe ni ne met à jour devkitPro ou les portlibs**. Il demande les mêmes bibliothèques ARM/3DS que `README-BUILD-FR.md`, et les outils CMake 3.26+, Ninja, Python 3.10+, devkitARM, picasso et 3dsxtool. Les outils makerom et bannertool déjà fournis dans le kit restent soumis à la vérification de leurs empreintes.

Citro3D est contrôlé dans `devkitPro/libctru/include` et `devkitPro/libctru/lib`, conformément au toolchain du kit et à la règle d'installation de Citro3D; pas dans un hypothétique dossier séparé `devkitPro/citro3d`.

**Cache déplacé ou incompatible :** choisir Reconstruction propre. Les sauvegardes des caches se trouvent à côté de leurs dossiers d'origine. Elles peuvent être supprimées manuellement après validation d'un nouveau build, jamais par ce wizard automatiquement.

**Correctif audio absent :** le petit ajout de wizard ne remplace pas `playback.c`. Utiliser les sources AUDIO-FIX ou l'archive complète avec wizard, pas la V2 originale non corrigée.

**Dépendance manquante :** suivre la liste exacte du journal et `README-BUILD-FR.md`. Le wizard ne boucle pas sur une installation de paquets.

## Périmètre des modifications

Par rapport à `2SHIP3DS-V2-AUDIO-FIX-SOURCES.zip` :

- le code du jeu, l'audio corrigé, le rendu, la stéréoscopie et CMake sont inchangés;
- depuis v1.0.2, `build.py` et `scripts/build_lus_3ds.py` intègrent la réparation des horodatages et le contrôle du manifeste décrits dans le nouveau lire-moi;
- seul le fichier existant `scripts/package_3ds.py` est étendu : visuels personnalisés facultatifs et mode sans CIA;
- les autres ajouts sont le lanceur, l'interface, le moteur du wizard, ce guide, les tests et les fichiers de validation/provenance.

Les manifestes de la V2 et du correctif audio sont conservés comme documents de leurs livraisons respectives. `wizard-manifest.json` décrit le changement supplémentaire du packager et les fichiers ajoutés. Les licences et crédits d'origine sont conservés; le wizard ne modifie pas les permissions de redistribution de la base.

## Validation réalisée et limites

**Exécuté dans l'environnement de préparation :** 43 tests hôte Python du wizard; les cinq tests audio du kit corrigé; création réelle d'icônes/bannières via le bannertool Linux fourni, avec PNG personnalisés et recopie de SMDH/CBMD. Les visuels par défaut ont aussi été comparés octet pour octet à ceux du packager précédent. Les tests de pilotage de compilation/packaging utilisent des doubles explicites et des fichiers synthétiques, pas des exécutables du jeu.

**Non exécuté ici :** l'interface Windows Forms, Windows PowerShell 5.1, la compilation complète du jeu avec devkitARM et l'écoute/test sur une New 3DS. Un contrôle lexical des délimiteurs PowerShell ne constitue pas une exécution ni une validation complète de son langage. Le wizard devra donc être confirmé sur votre PC. Le correctif audio ne garantit pas la disparition des coupures et ne traite pas le crash de transition du premier jour.

Logs de cette préparation : `validation/wizard/tests.txt`.

Pour relancer les tests du moteur sous un Python hôte :

```text
python tests/test_build_wizard.py
python tests/test_wizard_artwork.py
```

Pour tester uniquement la fonction de protection des arguments dans PowerShell, sans ouvrir la fenêtre :

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Wizard-2Ship3DS.ps1 -SelfTest
```

Ce dernier autotest est fourni, mais n'a pas été exécuté dans l'environnement Linux de préparation.

### Références techniques consultées

Les règles propres au port proviennent des fichiers locaux `build.py`, `scripts/build_lus_3ds.py`, `scripts/package_3ds.py`, `cmake/3DS.cmake`, `src/port3ds/archive_checks.h` et `scripts/prepare_support.py`.

- Microsoft Learn, `Start-Process`, redirections et transmission des arguments : https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.management/start-process?view=powershell-5.1
- Python, gestion des processus : https://docs.python.org/3/library/subprocess.html
- Python, lecture des ZIP : https://docs.python.org/3/library/zipfile.html
- devkitPro/Citro3D, règle d'installation : https://raw.githubusercontent.com/devkitPro/citro3d/master/Makefile
