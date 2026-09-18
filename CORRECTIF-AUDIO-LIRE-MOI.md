> Document historique : ses patchs, anciens backends et anciennes commandes se rapportent aux livraisons archivées. Pour Blinky 07, utiliser README-BUILD-FR.md et tests/README-BLINKY.md.

# 2Ship3DS V2 — correctif ciblé du filtre d’adresse audio

**Le correctif est déjà appliqué aux sources de ce dossier.**

Cette livraison contient des sources, pas de nouveaux exécutables `.cia` ou
`.3dsx`. Le défaut de contrôle de flux a été reproduit sur l’hôte, puis corrigé.
Le résultat sonore de ce correctif n’a pas été testé sur une New Nintendo 3DS.

## Le changement

Un seul fichier de production existant est modifié :

```text
third_party/2ship/mm/src/audio/lib/playback.c
```

Dans `AudioPlayback_ProcessNotes`, la garde devient :

```c
#if !defined(__WIIU__) && !defined(__3DS__)
```

L’ancienne garde ne faisait exception que pour la Wii U. Sur le chemin 3DS,
le test `parentLayer < 0x7FFFFFFF` pouvait donc écarter une couche native valide,
avant ADSR, vibrato/portamento et `AudioPlayback_InitSampleState`.
`AudioSynth_SyncSampleStates` consommait ensuite `needsInit`, même lorsque
l’initialisation n’avait pas été transmise à la tranche de synthèse.

La modification exclut la 3DS de cette heuristique d’adresse N64. Le seuil,
les pointeurs, les corps de traitement des notes et `NO_LAYER` ne changent pas.
L’exception Wii U et la politique des autres plateformes sont conservées.
Il ne s’agit pas d’ajouter une validation générale des pointeurs.

**Aucun changement** au renderer, à la stéréoscopie, au gameplay, aux sauvegardes,
aux assets, aux volumes, à la fréquence audio, au mixer, au backend NDSP,
aux buffers, à la cadence 528/544/528, aux mutex ni à l’ordonnancement.
Aucune instrumentation n’est intégrée à ce lot.

Le fichier `patches/mm-3ds-note-address-gate.patch` est le diff de production
pour inspection. Ne pas l’appliquer de nouveau : le fichier livré est corrigé.
La version source du moteur n’a pas été changée.

## Choisir le ZIP

### ZIP SOURCES — dossier complet

Décompresser `2SHIP3DS-V2-AUDIO-FIX-SOURCES.zip` dans un **nouveau dossier**.
Il contient la même racine `2Ship3DS/` que le ZIP V2, avec le correctif appliqué,
le nouveau test, les preuves d’exécution et ce document. Ne pas mélanger un cache
CMake provenant d’un ancien emplacement avec cette nouvelle copie.

### ZIP PATCH — uniquement les fichiers modifiés et ajoutés

`2SHIP3DS-V2-AUDIO-FIX-PATCH.zip` s’adresse à une copie locale de l’archive V2
exacte mentionnée ci-dessous. Fusionner son dossier `2Ship3DS/` avec le dossier
`2Ship3DS/` existant, en acceptant le remplacement de `playback.c`.
**Ne pas créer `2Ship3DS/2Ship3DS/`.**

Il n’est pas nécessaire d’utiliser les deux ZIP.
Ne pas superposer ce patch à une branche ayant d’autres modifications de
`playback.c` sans examiner le diff, car le ZIP PATCH contient le fichier complet.

Avant de reconstruire une copie déjà compilée, renommer son dossier `build-arm`
(par exemple `build-arm-avant-correctif-audio`). Cela conserve l’ancien build et
force une nouvelle compilation des objets du jeu. Ne pas simplement
reconditionner l’ancien ELF avec `package_3ds.py` : il ne contient pas le correctif.

## Reconstruire les exécutables

La chaîne devkitPro/ARM utilisée pour ton build précédent reste nécessaire.
Depuis le dossier `2Ship3DS` contenant `build.py`, la commande fournie par le kit est :

```powershell
& 'C:\devkitPro\msys2\mingw64\bin\python.exe' .\build.py --devkitpro C:/devkitPro --jobs 4 --output .\dist
```

Adapter le chemin devkitPro seulement s’il est différent sur ta machine.
La commande n’utilise pas `--skip-lus` : elle reconstruit aussi libultraship avec
le kit courant. Le backend n’a pas été modifié, mais un ancien binaire LUS issu
d’un autre kit ne doit pas être réutilisé arbitrairement.

Les sorties attendues après une reconstruction réussie sont notamment :

```text
dist/SD/3ds/2ship/2ship-3ds.3dsx
dist/SD/3ds/2ship/2ship-3ds.smdh
dist/SD/cias/2ship-3ds.cia
```

Les scripts de build et de packaging sont inchangés. Consulter
`README-BUILD-FR.md` pour leurs prérequis et les autres sorties.
La compilation ne régénère pas `mm.o2r` et `2ship.o2r` : conserver les archives
compatibles déjà utilisées, ainsi que les réglages et les sauvegardes.

Aucun nouveau build ARM n’a été exécuté dans l’environnement de préparation de
ce correctif : `arm-none-eabi-gcc` et `arm-none-eabi-g++` n’y sont pas installés.

## Résultats effectivement obtenus

| Contrôle | Résultat |
| --- | --- |
| Source V2 originale, mode reproduction | Réussite : le défaut est reproduit avec une véritable couche à l’adresse basse `0x404060` |
| Source V2 originale avec `--require-fixed` | Échec attendu, code 1 |
| Source corrigée avec `--require-fixed` | Réussite, code 0 |
| Contrôles Wii U avant/après | Comportement conservé |
| Contrôles plateforme par défaut avant/après | Comportement conservé |
| Chemin de relâchement `NO_LAYER` | Conservé dans les six variantes |
| `test_mm_3ds_timing_audio.py` | Réussite : 24 cas de FPS, exclusion et barrière |
| `test_mm_audio_specs.py` | Réussite : 21 presets natifs, 84 découpages ; contrôle historique conservé |
| `test_mm_adpcm_boundaries.py` | Réussite : 480 cas natifs ; contrôle historique conservé |
| `test_mm_mixer_effects.py` | Réussite : 77 vecteurs de gain, 5 cas MM no-op ; contrôles historiques conservés |

Dans le test de couche attachée, l’ancien filtre donne zéro appel ADSR,
zéro appel vibrato et zéro écriture d’état. Avec la garde corrigée, chacun vaut 1.
Après le vrai `AudioSynth_SyncSampleStates`, `needsInit` a été consommé dans la
note, mais reste transmis à la tranche de synthèse dans le cas corrigé.
Le changement de fréquence lors d’une mise à jour suivante est également testé.

Le nouveau test est dérivé de `test_note_address_gate.py`, récupéré dans
`2SHIP3DS-AUDIO-DIAGNOSTIC.zip`. Son contrôle négatif historique reste intact.
Les ajouts portent sur les variantes Wii U corrigée et plateforme par défaut
avant/après, ainsi que sur sa ligne d’utilisation.

**Portée des tests :** `AudioPlayback_ProcessNotes` et
`AudioSynth_SyncSampleStates` sont extraits des sources réelles. Les types du
banc de test et les fonctions auxiliaires sont des doubles explicites ; le test
ne valide ni l’ABI ARM, ni l’audio PCM complet, ni NDSP, ni le son sur console.
Les quatre tests préexistants sont strictement inchangés.

Pour relancer sous Linux x86-64 avec Python 3 et `g++` :

```sh
python3 tests/test_mm_note_address_gate.py . --require-fixed
python3 tests/test_mm_3ds_timing_audio.py
python3 tests/test_mm_audio_specs.py
python3 tests/test_mm_adpcm_boundaries.py
python3 tests/test_mm_mixer_effects.py
```

Le nouveau test exige `g++` et `-fno-pie -no-pie` pour obtenir une adresse
réellement basse ; il n’est pas présenté comme un test hôte Windows portable.
Le script existant `scripts/verify_port.py` n’a pas été modifié pour le lancer
automatiquement : la première commande ci-dessus est nécessaire.

Détails des exécutions : `validation/audio-note-address-gate/tests.txt` et
`validation/audio-note-address-gate/results.json`.

## Ce qui reste à vérifier sur ta console

Comparer le build V2 original et le build corrigé seul, avec les mêmes archives,
la même scène et les mêmes réglages. Écouter les voix, les effets, les attaques,
les notes tenues et les relâchements. Tester séparément `.3dsx` et `.cia`, en
vérifiant que chacun a effectivement été remplacé par la nouvelle compilation.
Conserver les empreintes du manifeste de packaging du build installé.

Les coupures peuvent avoir une cause indépendante. Ce correctif ne prétend pas
avoir mesuré des underruns, ni avoir corrigé l’alimentation de la file NDSP.
Il ne traite pas non plus le crash de transition du premier jour.
Le contrat de diagnostic fourni est conservé dans le dossier de validation,
pour poursuivre séparément l’enquête si le problème sonore persiste.

## Provenance et intégrité

Archive d’entrée exacte : `2SHIP3DS-CORRECTIF-V2-SOURCES(1).zip`

```text
SHA-256 : 1806cc31f4d7f881934fe2efeaad37fba1ee71c8d41d00409ea8ca898234f4c0
```

`playback.c` avant correction :

```text
5d220233ab43f2d75831c81ce4ac7f05521579034f6d7676ab3a66838e48694a
```

`playback.c` après correction :

```text
e462a5e0d6bb641e768f692c5c3f6da1ee306bdf6c5fb06b5ecb6605a24e0b18
```

Les 8 872 autres fichiers de l’archive d’entrée sont conservés octet pour octet.
Aucun fichier d’origine n’est supprimé. Les crédits et licences existants sont
conservés ; ce correctif ne change pas les conditions de redistribution.

`source-manifest.json` est conservé comme manifeste de la **base V2 originale**.
Son entrée `playback.c` décrit donc l’état AVANT ce correctif, et non le fichier
corrigé. Le nouveau `audio-note-gate-fix-manifest.json` fournit les empreintes
avant/après et celles des fichiers ajoutés. Ne pas interpréter cette différence
attendue comme une corruption, ni utiliser le manifeste V2 seul pour certifier
l’ensemble du paquet corrigé.
