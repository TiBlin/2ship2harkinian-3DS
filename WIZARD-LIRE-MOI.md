# Lanceur Blinky 07

Le lanceur historique avec interface graphique a été remplacé par un petit lanceur PowerShell indépendant. Double-cliquez sur `LANCER-WIZARD.bat` pour compiler avec le SDK installé dans `C:/devkitPro`. Les fichiers validés sont placés dans `dist/`. Aucune archive de jeu ni sauvegarde n’est modifiée.

La commande directe permet de choisir le SDK, le parallélisme et la destination :

```powershell
.\Wizard-2Ship3DS.ps1 -DevkitPro C:/devkitPro -Jobs 6 -Output .\dist
```

Pour les tests hôte, définissez `CXX` avec le chemin d’un compilateur C++ pour PC, puis exécutez `-VerifyOnly`. La compilation ARM ne suffit pas à valider le rendu ou les performances sur console.

Les opérations restent accessibles séparément :

- `build.py --devkitpro C:/devkitPro --jobs 6 --output dist` : compilation et paquet complet.
- `scripts/package_3ds.py --elf build-arm/2ship-3ds.elf --output dist --devkitpro C:/devkitPro` : génération 3DSX, CIA et CCI et validation des formats/hachages.
- `scripts/package_3ds.py --artwork-only --output work/artwork --devkitpro C:/devkitPro` : icône et bannière géométriques.
- `scripts/verify_port.py --cxx C:/ProgramData/mingw64/mingw64/bin/g++.exe` : régressions maintenues.

Le packager accepte toujours `--icon` (PNG 48×48 ou SMDH) et `--banner` (PNG 256×128 ou CBMD). Les fichiers fournis sont conservés sans modification. Les archives MM restent à installer séparément dans `sdmc:/3ds/2ship/`.

Les anciens tests de l’interface et les patchs historiques sont conservés dans le ZIP des sources de la livraison 06, extérieur au nouveau dossier source. Les régressions du rendu, du son, de l’arrêt, des archives et des horodatages restent maintenues.