# Provenance des composants

Les licences originales restent dans les répertoires de leurs composants.
Cette liste décrit le code et les outils utilisés ; elle ne remplace pas ces
textes de licence et n'accorde aucun droit sur les données d'une ROM.

## Socle et jeu

| Composant | Source utilisée | Licence présente |
| --- | --- | --- |
| SoH3DS V7 | `SOH3DS-Compilateur-3D-MODS-V7.zip`, préfixe `SOH3DS-Compilateur/source` ; SHA-256 `55cf1562a9231f6101b02ed7517bf9af13e7993ab95a777de68f84dc3bbf92a1` | Conserver les notices des fichiers et bibliothèques de la base |
| 2Ship2Harkinian | [HarbourMasters/2ship2harkinian](https://github.com/HarbourMasters/2ship2harkinian), commit `6bfd6a35a0e0d8900273e61ce85cb038d4f4a528`, version source `5.0.1` | `third_party/2ship/LICENSE`, CC0-1.0 |
| libultraship | Copie incluse dans V7, puis adaptations 2Ship/3DS locales ; origine [kenix3/libultraship](https://github.com/kenix3/libultraship) | `third_party/libultraship/LICENSE`, MIT |
| Rendu PICA200 et outils de compatibilité | Sources du socle V7, avec adaptations MM dans ce kit | Notices des fichiers d'origine |

La déclaration du sous-module LUS dans le dépôt 2Ship sert de référence amont.
Le build de ce kit utilise explicitement `third_party/libultraship`, issu de
V7, et conserve l'interpréteur et son backend de rendu ensemble. Les changements
de types, de mémoire, d'entrée, d'audio et d'initialisation 3DS sont présents
dans les sources livrées.

## Bibliothèques reconstruites depuis les sources locales

| Composant | Version ou révision | Provenance et licence |
| --- | --- | --- |
| ImGui | `v1.91.9b-docking`, correctif LUS `imgui-fixes-and-config.patch` appliqué | [ocornut/imgui](https://github.com/ocornut/imgui) ; `third_party/build-deps/imgui/LICENSE.txt`, MIT |
| prism | `1de054450e7b3c5f777d2e3dfcb228ad120c329d` | [KiritoDv/prism-processor](https://github.com/KiritoDv/prism-processor) ; `third_party/build-deps/prism/LICENSE`, MIT |
| thread-pool | `v4.1.0` | [bshoshany/thread-pool](https://github.com/bshoshany/thread-pool) ; `third_party/build-deps/threadpool/LICENSE.txt`, MIT |
| Monocypher | `0d85f98c9d9b0227e42cf795cb527dff372b40a4` | [LoupVaillant/Monocypher](https://github.com/LoupVaillant/Monocypher) ; `third_party/build-deps/monocypher/LICENCE.md`, choix BSD-2-Clause / CC0-1.0 |
| stb_image | fichier de `0bc88af4de5fb022db643c2d8e549a0927749354` | [nothings/stb](https://github.com/nothings/stb) ; licence incluse dans `stb_image.h`, choix MIT / domaine public |
| libogg | `1.3.6`, sources reprises de V7 | [xiph/ogg](https://github.com/xiph/ogg) ; `third_party/libogg/COPYING` |
| libvorbis / vorbisfile | `1.3.7`, sources reprises de V7 | [xiph/vorbis](https://github.com/xiph/vorbis) ; `third_party/libvorbis/COPYING` |
| Opus | Copie source de V7 ; métadonnées de révision Git absentes de cette copie | [xiph/opus](https://github.com/xiph/opus) ; `third_party/opus/COPYING` et `LICENSE_PLEASE_READ.txt` |
| opusfile | Copie source de V7 ; métadonnées de révision Git absentes de cette copie | [xiph/opusfile](https://github.com/xiph/opusfile) ; `third_party/opusfile/COPYING` |
| libpng | `1.6.58`, commit `3061454d980de7d53608f594194cfac722721d2a` | [pnggroup/libpng](https://github.com/pnggroup/libpng) ; `third_party/libpng/LICENSE` |
| dr_wav / dr_mp3 / dr_flac | `0.14.6` / `0.7.4` / `0.13.4`, en-têtes repris de V7 | [mackron/dr_libs](https://github.com/mackron/dr_libs) ; `third_party/dr_libs/LICENSE` et notices des en-têtes |

Les sources épinglées de LUS ont été copiées depuis le cache de dépendances
existant, sans reprendre ses archives ARM ni ses fichiers objets. Leur détail
figure aussi dans `third_party/build-deps/README.md`. Le SHA-256 du
`stb_image.h` est
`c54b15a689e6a1f32c75e2ec23afa442e3e0e37e894b73c1974d08679b20dd5c` ; CMake le
vérifie avant compilation.

Opus/opusfile sont compilés en calcul fixe pour ARM11, avec API flottante
conservée, sans intrinsics NEON, DRED, OSCE ni HTTP/TLS. Leurs scripts amont
peuvent afficher une version `0` ou `0.0` faute de métadonnées Git ; cela ne
constitue pas une version de release revendiquée. Les sources incluses dans
le ZIP V7 identifié ci-dessus sont la référence de ces copies.

## SDK et bibliothèques ARM installées séparément

Relevé local de l'environnement de compilation :

| Élément | Version observée |
| --- | --- |
| devkitARM | paquet `r68-1`, GCC `16.1.0` |
| Binutils ARM | `2.46.0-1` |
| newlib ARM | `4.6.0.20260123-5` |
| libctru | `2.7.0-1` |
| citro3d | `1.7.1-2` |
| citro2d | `1.7.0-1`, installé dans le SDK ; le lien final principal utilise citro3d |
| picasso | `2.7.2-3` |
| 3dstools / 3dsxtool | paquet `1.3.1-3` |
| CMake Windows natif | `4.4.3` |
| Ninja Windows natif | `1.13.2` |
| Python Windows natif | `3.14.7` |
| SDL2 ARM | en-têtes `2.32.10` |
| zlib ARM | en-têtes `1.3.1` |
| libzip ARM | en-têtes `1.11.4` |
| tinyxml2 ARM | en-têtes `11.0.0` |
| spdlog ARM | en-têtes `1.16.0` |
| nlohmann/json | en-têtes `3.12.0` |

devkitPro : [projet officiel](https://devkitpro.org/),
[libctru](https://github.com/devkitPro/libctru),
[citro3d](https://github.com/devkitPro/citro3d),
[citro2d](https://github.com/devkitPro/citro2d),
[3dstools](https://github.com/devkitPro/3dstools).
Le fichier utilisé pour la cross-compilation est le `cmake/3DS.cmake` du kit,
adapté à CMake natif Windows ; la présence du paquet `3ds-cmake 1.5.2-1` ne
change pas ce choix.

Bibliothèques portlibs : [SDL2](https://github.com/libsdl-org/SDL),
[zlib](https://github.com/madler/zlib), [libzip](https://github.com/nih-at/libzip),
[tinyxml2](https://github.com/leethomason/tinyxml2),
[spdlog](https://github.com/gabime/spdlog),
[nlohmann/json](https://github.com/nlohmann/json).
Elles sont fournies par l'installation ARM existante. Les versions ci-dessus
proviennent des en-têtes effectivement utilisés ; les recettes V7 associées
sont reprises dans `README-BUILD-FR.md`. Le kit source ne redistribue pas le SDK
devkitARM ni les archives de `portlibs`.

## Outils de packaging et illustration

- makerom `0.19.0`, [3DSGuy/Project_CTR](https://github.com/3DSGuy/Project_CTR/releases/tag/makerom-v0.19.0) ;
  licence `tools/LICENSE-makerom.txt`.
- bannertool `1.2.3`, [carstene1ns/3ds-bannertool](https://github.com/carstene1ns/3ds-bannertool/releases/tag/1.2.3) ;
  licence `tools/LICENSE-bannertool.txt`.
- Les binaires Windows/Linux et leurs SHA-256 sont répertoriés dans
  `tools/provenance.json`. Le packager vérifie les binaires fournis avant de
  les lancer. La chaîne de reconstruction documentée et utilisée pour
  cette livraison est Windows ; la présence des outils Linux ne constitue
  pas une validation du build sous Linux.
- L'icône et la bannière sont créées par `scripts/package_3ds.py` avec des
  lettres géométriques et des rectangles originaux. L'audio de bannière est
  silencieux. Ces créations sont proposées sous CC0-1.0 ; aucune image Zelda
  ou SoH n'a été reprise pour ces éléments.

## Archives de ressources du kit SD initial V1

`mm.o2r` est une extraction séparée de la ROM fournie par l'utilisateur avec
l'extracteur officiel 2Ship Windows 5.0.1. Le code de l'extracteur provient de
2Ship, OTRExporter et ZAPDTR ; aucun extracteur desktop n'est compilé dans la
cible 3DS de ce kit. Le rapport `mm-extraction.json` de la livraison conserve
les empreintes et métadonnées de cette opération.

`2ship.o2r` est l'archive support issue de la release officielle 5.0.1,
complétée pour le commit source choisi ; `2ship.provenance.json` liste ces
15 ajouts bruts. `scripts/prepare_support.py` reproduit cette adaptation à
partir de l'archive officielle dont le SHA-256 attendu est
`69b615ba25c6788bd1e4e120608d28e56e99fa6c2d9553d61d722a4457ad109a`.
Ces archives et leurs conditions de redistribution sont distinctes
des sources et licences des bibliothèques. Le script de packaging des
conteneurs ne les embarque pas dans le RomFS.
