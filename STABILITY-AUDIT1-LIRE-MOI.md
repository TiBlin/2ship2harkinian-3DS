> Document historique : ses patchs, anciens backends et anciennes commandes se rapportent aux livraisons archivées. Pour Blinky 07, utiliser README-BUILD-FR.md et tests/README-BLINKY.md.

# STABILITY-AUDIT1 — sources et wizard

Version : **1.0.4-STABILITY-AUDIT1**. Base : **FPS60-AUTO + CRASH26**.

Il s'agit d'un premier lot de durcissement testé sur hôte, **pas d'une version
certifiée stable ni d'exécutables précompilés**. Lire `AUDIT-STABILITE.md` pour
les défauts corrigés, les preuves et les problèmes encore ouverts.

## Installation conseillée

1. Copier à l'abri les sauvegardes présentes sur la SD. Le protocole d'écriture
   des sauvegardes n'est pas modifié : un échec d'écriture reste un risque identifié.
2. Extraire l'archive complète dans un nouveau dossier, par exemple
   `C:\dev\2Ship3DS-AUDIT1`. Ne pas écraser l'ancien dossier de build.
3. Double-cliquer sur `LANCER-WIZARD.bat` à la racine de l'extraction.
   Le titre doit indiquer `v1.0.4-STABILITY-AUDIT1`.
4. Réutiliser devkitPro et les mêmes `mm.o2r` / `2ship.o2r`. Choisir
   **Reconstruction propre**, puis Compiler. **Ne pas utiliser --skip-lus** :
   les corrections de libultraship doivent être recompilées.
5. Installer/lancer uniquement le nouveau résultat. Conserver son
   `2ship-3ds.elf` et son `package-manifest.json` avec chaque nouveau dump.

Les archives de jeu ne sont pas fournies dans ce ZIP. Le correctif audio,
la cible FPS60, le frameskip, la stéréoscopie et la protection CMake/horodatages
sont conservés. Le backend audio reçoit des gardes de fermeture/flush, sans
changement de fréquence, cadence, format ni nombre de buffers.

Le journal `sdmc:/3ds/2ship/resource-failure-crash26.log` reste actif. Les
nouvelles corrections ne prouvent pas la cause initiale du chargement nul de
la texture du dump 26. Conserver les mêmes archives et réglages pour comparer.

## Variante PATCH

Le petit ZIP est un **overlay pour le dossier CRASH26 exact**. Fusionner son
dossier `2Ship3DS` avec la racine du projet correspondante, et remplacer les
fichiers proposés. Ne pas créer `2Ship3DS/2Ship3DS` dans le projet.
L'archive complète suffit à elle seule ; aucun patch supplémentaire nécessaire.

Les deux diff de `patches/stability-audit1-*.patch` sont aussi fournis pour
revue ou application avec Git. Ils ont passé `git apply --check` sur la base.
Ils ne s'appliquent pas en plus de l'overlay déjà copié.

## Tests reproductibles (hôte Linux)

Depuis la racine `2Ship3DS`, avec Python 3 et un C++20 hôte supportant ASan/UBSan :

```sh
python3 tests/test_stability_audit1.py
python3 tests/test_stability_audit1.py --baseline /chemin/vers/BASE-CRASH26/2Ship3DS
```

Le premier appel vérifie 46 cas sur la variante. Le second ajoute 24 contrôles
qui doivent reproduire les défauts de l'ancienne source. Ne pas fournir AUDIT1
comme `--baseline`. Les collaborateurs simulés sont dans `tests/stability_audit1`.
Les tests existants n'ont pas été réécrits. Leur journal final et le test de
sauvegarde séparé sont dans `validation/stability-audit1/`.

## Limites

Pas de compilation ARM complète, pas d'exécution Windows du wizard, pas de
mesure GPU/DSP, de validation des assets personnels, de sauvegarde sur SD ou
d'endurance sur console. Le compteur de file audio vide n'est pas une preuve
d'underrun audible. Les gardes de parsing ne constituent pas une validation
sémantique exhaustive de tous les formats de ressources.

Le protocole d'échec des ressources indispensables, les sauvegardes
transactionnelles et la fermeture avec workers encore actifs restent des
priorités. Ne pas considérer une disparition de crash comme preuve suffisante
de validité du rendu, des sauvegardes ou de l'état du jeu.

## Traçabilité

`stability-audit1-manifest.json` décrit exactement les fichiers modifiés et ajoutés.
Les anciens manifests restent des traces historiques, non l'empreinte du nouveau
runtime. Le manifeste du packaging final identifie le nouvel ELF ; il ne prouve
pas à lui seul que ce binaire est effectivement installé sur la console.
