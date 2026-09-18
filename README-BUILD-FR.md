# Reconstruire 2Ship 3DS sous Windows

Ce dossier contient un portage expérimental de 2Ship 5.0.1 pour Nintendo 3DS,
construit à partir du socle SoH3DS V7. La compilation et les vérifications des
conteneurs ne prouvent pas le fonctionnement du jeu sur console. Les résultats
de test de la livraison sont décrits séparément dans son README utilisateur.

## Sources de référence

- Base : `SOH3DS-Compilateur-3D-MODS-V7.zip`, sous-dossier
  `SOH3DS-Compilateur/source`.
- SHA-256 de cette archive V7 :
  `55cf1562a9231f6101b02ed7517bf9af13e7993ab95a777de68f84dc3bbf92a1`.
- Jeu : dépôt HarbourMasters/2ship2harkinian, commit
  `6bfd6a35a0e0d8900273e61ce85cb038d4f4a528`, version source déclarée `5.0.1`.
- `CMakeLists.txt` construit Majora's Mask. `CMakeLists.soh-v7.txt` conserve
  l'ancien descriptif comme référence ; il ne pilote pas ce build.
- Le moteur libultraship et le rendu PICA200 proviennent de V7, puis reçoivent
  les adaptations MM et 3DS du présent dossier. Le sous-module libultraship
  desktop déclaré par le dépôt MM n'est pas utilisé pour le build 3DS.

## 1. Préparer la chaîne de compilation

Les commandes ci-dessous utilisent devkitPro dans `C:\devkitPro`, chemin
de l'environnement testé. Un autre emplacement se désigne avec
`--devkitpro` ; adapter aussi le chemin de Python dans les commandes.
Utiliser les outils Windows natifs de `C:\devkitPro\msys2\mingw64\bin` pour CMake,
Ninja et Python. Il faut Python 3.10 ou ultérieur et CMake 3.26 ou ultérieur.
Les versions observées sur la machine de compilation sont détaillées dans
`THIRD-PARTY.md`.

La chaîne ARM doit fournir :

- `devkitARM/bin/arm-none-eabi-gcc.exe` et `arm-none-eabi-g++.exe` ;
- les en-têtes et archives statiques libctru et citro3d ;
- `tools/bin/picasso.exe` et `tools/bin/3dsxtool.exe` ;
- sous `portlibs/3ds/include` : SDL2, libzip, zlib, tinyxml2, spdlog et
  nlohmann/json ;
- sous `portlibs/3ds/lib` : `libSDL2.a`, `libzip.a`,
  `libzlibstatic.a`, `libtinyxml2.a`, `libspdlog.a`, ainsi que les fichiers de
  configuration CMake installés avec ces bibliothèques.

Ces bibliothèques doivent être compilées **pour ARM/3DS**. Des bibliothèques
MinGW x64 ne conviennent pas à l'édition de liens du jeu. `build.py` utilise
une installation SDK existante ; il n'installe pas les paquets et ne compile
pas automatiquement les bibliothèques de `portlibs` manquantes.

Le build V7 utilisait les recettes suivantes pour compléter `portlibs/3ds` :

| Bibliothèque | Révision | Options particulières |
| --- | --- | --- |
| zlib | `v1.3.1` | `ZLIB_BUILD_EXAMPLES=OFF` |
| libzip | `v1.11.4` | BZIP2, LZMA, ZSTD et fournisseurs de cryptographie désactivés ; outils, tests, exemples et docs désactivés ; `LIBZIP_DO_INSTALL=ON` |
| nlohmann/json | `v3.12.0` | `JSON_BuildTests=OFF` |
| tinyxml2 | `11.0.0` | `tinyxml2_BUILD_TESTING=OFF` |
| spdlog | `v1.16.0` | `SPDLOG_BUILD_EXAMPLE=OFF`, `SPDLOG_BUILD_TESTS=OFF` |
| SDL2 | `release-2.32.10` | `SDL_SHARED=OFF`, `SDL_STATIC=ON`, `SDL_TEST=OFF`, `SDL_TESTS=OFF` |

Pour reconstituer une bibliothèque manquante à partir de sa révision amont,
la configuration commune est : `-G Ninja`, `-DCMAKE_BUILD_TYPE=Release`,
`-DCMAKE_POLICY_VERSION_MINIMUM=3.10`, `-DBUILD_SHARED_LIBS=OFF`,
`-DCMAKE_TOOLCHAIN_FILE=<sources>/cmake/3DS.cmake`,
`-DCMAKE_PREFIX_PATH=C:/devkitPro/portlibs/3ds` et
`-DCMAKE_INSTALL_PREFIX=C:/devkitPro/portlibs/3ds`. Définir aussi
`DEVKITPRO=C:/devkitPro`. Compiler avec `cmake --build`, puis installer avec
`cmake --install`. Construire zlib avant libzip. Les liens amont figurent dans
`THIRD-PARTY.md`.

## 2. Lancer la reconstruction complète

Dans PowerShell, se placer dans le dossier contenant `build.py` :

```powershell
& 'C:\devkitPro\msys2\mingw64\bin\python.exe' .\build.py --devkitpro C:/devkitPro --jobs 4 --output .\dist
```

Le script configure et compile successivement :

1. le libultraship V7 adapté, dans `third_party/libultraship/build-3ds` ;
2. les sources C/C++ de MM, le rendu et les codecs, dans `build-arm` ;
3. les conteneurs 3DSX, CIA et CCI à partir du même ELF.

Les sources ImGui, prism, Monocypher, thread-pool et stb sont fournies dans
`third_party/build-deps`. Leur configuration est hors ligne. Ogg, Vorbis,
Opus, opusfile et libpng sont aussi compilés depuis leurs sources locales.
Les exécutables makerom et bannertool sont dans `tools/windows`, avec leurs
licences et leurs empreintes vérifiées avant utilisation.

Le kit source se décompresse dans un autre dossier : ses scripts calculent
les chemins depuis leur propre emplacement. Aucun cache CMake ni objet ARM
n'est fourni. Les sources nécessaires à cette cible 3DS sont incluses ;
une initialisation des sous-modules desktop de 2Ship n'est pas nécessaire.
Le fonctionnement hors ligne suppose que le SDK et les bibliothèques ARM
de la section 1 sont déjà installés. Leur installation initiale reste une
étape séparée. La reconstruction dans un nouveau dossier n'a pas fait
l'objet d'un second build complet ; les chemins et l'inventaire du kit
ont été vérifiés séparément.

Options utiles :

```powershell
# Produire uniquement l'ELF et le 3DSX du build.
& 'C:\devkitPro\msys2\mingw64\bin\python.exe' .\build.py --devkitpro C:/devkitPro --jobs 4 --no-package

# Réutiliser LUS après une modification uniquement côté jeu.
& 'C:\devkitPro\msys2\mingw64\bin\python.exe' .\build.py --devkitpro C:/devkitPro --jobs 4 --skip-lus

# Reconditionner explicitement un ELF déjà compilé.
& 'C:\devkitPro\msys2\mingw64\bin\python.exe' .\scripts\package_3ds.py --elf .\build-arm\2ship-3ds.elf --output .\dist --devkitpro C:/devkitPro
```

`--skip-lus` suppose une archive LUS déjà reconstruite avec ce kit. Ne pas
réutiliser une archive binaire de SoH : MM utilise un masque de boutons
`uint32_t`, contre `uint16_t` par défaut dans l'ancien moteur. Une différence
de largeur change les structures et certaines signatures C++.

`--emulator-safe` désactive l'activation de la fréquence CPU New 3DS par le
renderer (`osSetSpeedupEnable(true)`). Les appels de démarrage propres à
libctru restent possibles. Ce réglage est prévu pour diagnostiquer un
émulateur ; il ne constitue pas une validation du gameplay. Le réglage
ordinaire reste la valeur par défaut.

## 3. Retrouver les résultats

Un build complet place notamment dans `dist` :

- `SD/3ds/2ship/2ship-3ds.3dsx` et `2ship-3ds.smdh` ;
- `SD/cias/2ship-3ds.cia` ;
- `2ship-3ds.3ds`, véritable conteneur cartouche CCI/NCSD ;
- `2ship-3ds.elf` et `package-manifest.json`.

`build-arm/build-report.json` indique le résultat de la commande. Le manifeste
de packaging contient les empreintes des fichiers, le TitleID
`0004000002534800` et les contrôles structurels effectués. Ce TitleID
expérimental diffère de celui de SoH ; il n'est pas présenté comme une
allocation officielle.

Le packager n'intègre pas la ROM ni les données du jeu dans les conteneurs.
Le RomFS embarqué ne contient qu'un readme. Les archives `mm.o2r` et
`2ship.o2r` doivent être placées dans `/3ds/2ship/` sur la carte SD. Elles sont
gérées séparément dans la livraison utilisateur. La compilation ne les
régénère pas. Une ROM renommée `.o2r` ou une archive MPQ `.otr` ne convient pas.

Le `mm.o2r` du kit SD initial V1 a été extrait avec l'exécutable officiel Windows
2Ship 5.0.1, en lui passant explicitement une copie de la ROM compatible :
`2ship.exe baserom.z64`. Le rapport `mm-extraction.json` décrit cette opération.
L'archive support doit correspondre au commit source du port ; consulter
`2ship.provenance.json` pour ses ajouts depuis la release officielle.

Le kit SOURCES ne contient pas `mm.o2r`. Pour reconstruire l'archive support
depuis le `2ship.o2r` officiel Windows 5.0.1, utiliser une destination distincte :

```powershell
python .\scripts\prepare_support.py --base C:\Chemin\Release-5.0.1\2ship.o2r --output .\dist\SD\3ds\2ship\2ship.o2r
```

Le script vérifie l'empreinte de l'archive officielle, conserve ses ressources
converties et ajoute les 15 ressources brutes présentes dans le commit MM.
Il écrit aussi un fichier `.provenance.json`. Le kit SD initial V1 fournit déjà
l'archive support correspondante. Le correctif V2 contient uniquement les
exécutables ; il conserve les archives, réglages et sauvegardes existants.

## Contrôles techniques et limites

- ARMv6K, VFPv2 et ABI hard-float, sans NEON ; calcul du jeu sans fast-math.
- Le fichier `cmake/AudioCodecs3DS.cmake` construit de vrais décodeurs
  Opus/opusfile, sans réseau HTTP/TLS ni DRED/OSCE.
- Les boutons L+R avec Haut/Bas règlent la résolution stéréo ; ZR règle la
  convergence. Ces raccourcis natifs ne dépendent pas de l'affichage ImGui.
- Les tests de raccourcis compilent le code de production sur l'hôte ; le
  test du pont de manette vérifie séparément la conservation des bits MM.
- Le packager vérifie le format ARM de l'ELF, les métadonnées, les identifiants
  et les hashes NCCH, ainsi que l'identité ExeFS/RomFS entre CIA et CCI.

Pour lancer les treize tests disponibles pour ce port MM, avec un compilateur C++ hôte dans
`PATH` ou désigné par `CXX` :

```powershell
python .\scripts\verify_port.py
```

Les tests peuvent aussi être lancés individuellement, par exemple
`python tests/test_2ship_native_controls.py` et
`python tests/test_mm_control_merge.py`. Le compilateur de ces tests doit être
un compilateur hôte, pas `arm-none-eabi-g++`.

Si les sources ou la chaîne de compilation ont été déplacées, repartir d'un
nouveau dossier de build : les caches CMake contiennent des chemins absolus.
Renommer les anciens dossiers `build-arm` et
`third_party/libultraship/build-3ds` avant de relancer conserve les anciens
résultats et permet une configuration propre.
