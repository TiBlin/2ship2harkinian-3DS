# Provenance et limites

Les nouveaux fichiers src/blinky/* et BlinkyInput.h sont écrits pour cette
migration. Le shader PICA transmet les attributs ; les recettes proviennent de
gfx_cc_get_features, sans décodeur de shader-ID parallèle. Le raster CPU suit
le contrat des shaders GLSL du LUS officiel. Le décodeur de textures et le jeu
restent les implémentations amont, avec leurs licences.

L'interpréteur et son header ont été restaurés depuis le LUS de référence, puis
adaptés pour vérifier les pointeurs 3DS et réimporter une texture dont la mémoire
DMA a été libérée. Les contrôleurs ont été restaurés avant l'ajout d'une source
HID native. Gui.cpp et SDLGyroMapping.cpp sont de nouveau identiques à l'amont.
Les enums, masques, signatures libctru/Citro3D et macros GBI identiques sont des
interfaces publiques nécessaires, pas une reprise d'un renderer SoH.

Sources de conception publiques :

- [LibUltraShip épinglé](https://github.com/kenix3/libultraship/tree/7f9b86a593c526fc42261d7fe197100cecf57178), contrats GfxRenderingAPI, contrôleurs, gfx_cc_get_features et default.shader.glsl.
- [2Ship épinglé](https://github.com/HarbourMasters/2ship2harkinian/tree/6bfd6a35a0e0d8900273e61ce85cb038d4f4a528), main MM, archives et GBI.
- [libctru : allocation](https://github.com/devkitPro/libctru/blob/master/libctru/source/system/allocateHeaps.c), paramètres faibles du tas SDK.
- [libctru : gfx](https://github.com/devkitPro/libctru/blob/master/libctru/source/gfx.c), propriété des LCD (pas de refcount gfxInit/gfxExit).
- [Citro3D : renderqueue](https://github.com/devkitPro/citro3d/blob/master/source/renderqueue.c), clôture, copies et destruction hors frame.
- [Citro3D : TexEnv](https://github.com/devkitPro/citro3d/blob/master/source/texenv.c), couleur initiale du buffer et masques de mise à jour. L'allocation RGB/alpha de la livraison 06 est écrite ici à partir de cette API publique.
- [Citro3D](https://github.com/devkitPro/citro3d), headers installés 1.7.1 : textures, TexEnv et profondeur.
- [Exemples devkitPro](https://github.com/devkitPro/3ds-examples), conventions de textures et shader PICA ; aucune logique de port SoH reprise.

SDK local compilé : devkitARM r68 / GCC 16.1, libctru 2.7, Citro3D 1.7.1.
Les liens master documentent les API consultées ; les headers réellement
compilés sont ceux de cette installation. Les builds ne téléchargent pas alpha3.

La comparaison 999sian porte sur v0.1.0-alpha.3,
af3a7e80208e5eff755704d3ae5f5a25a6b7ed6e. Archives SHA-256 :

```text
alpha3 41602d1f75cc811d6d778352fc90105c0903af25c3c166ef61366de17c46eca9
LUS    656ca95a03bc7f762b71bd76a26749f6ba2f734369a646f99fddaa996c9551c7
2Ship  216b4792595fa3023e9ba2dae68754ce69286fabef3c2d00985353c497d45ae6
```

Le lecteur O2R natif est une nouvelle unité de compilation Blinky. Archive,
Config, CrashHandler et consolevariablebridge ont été restaurés depuis LUS.
Le gestionnaire d'archives repart de LUS avec un nouveau tableau trié. Le
gestionnaire et le décodeur de ressources repartent aussi de LUS avec des méthodes
réimplémentées ; ils restent des fichiers mixtes, et non entièrement écrits ici.
Les règles de propriété et de lecture viennent de la documentation
[libzip source FILE](https://libzip.org/documentation/zip_source_filep/),
[lecture](https://libzip.org/documentation/zip_fread/) et
[fermeture](https://libzip.org/documentation/zip_close/).
Config conserve une sauvegarde récupérable et une validation du commit sur SD ;
le contrat rename du SDK est documenté depuis [libctru 2.1](https://github.com/devkitPro/libctru/blob/master/Changelog.md).

La livraison 07 ajoute une revue par modification des entrées historiques
ouvertes en 06 dans le périmètre MM/LUS/natif. BLINKY-REVIEWED-DELTAS.json
rattache le contenu final à des empreintes et à des contrats précis. Les
adaptations publiques d'ABI restent attribuées ; les fichiers mêlant base
officielle et delta Blinky ne sont pas classés entièrement A. La liste des
retraits figure dans BLINKY-RETIRED-FILES.json.

Les scripts de construction, packaging et contrôles locaux sont également
réimplémentés. Les tests utiles sont maintenus ; leurs extraits et fixtures
amont gardent leur attribution. Voir BLINKY-CLEANROOM-AUDIT.md pour les limites
de la revue, et BLINKY-PERFORMANCE-07.md pour les effets GPU supplémentaires.
