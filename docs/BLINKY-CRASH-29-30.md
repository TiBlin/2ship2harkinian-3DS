# Blinky 09 — plantage du parcours des archives

Les dumps ARM11 29 et 30 fournis par l'utilisateur correspondent tous deux
à l'ELF livré avec Blinky 08. Les 96 octets d'instructions sauvegardés dans
chaque dump sont identiques à cet ELF, dont le SHA-256 est
`99eac35ec2b1cd0da7c194df50378f72347e39b691a9a535d02e4df0c7526364`.
Le premier processus est `2Ship3DS` (titre `0004000002534800`), le second
`3dsx_app`. Les deux formats rencontrent la même erreur.

## Diagnostic

Les deux PC et LR valent `0x00261f64`, dans `OTRExtScanner`. L'instruction
`ldr r4, [r4, #8]` tente de lire une structure à travers un pointeur invalide :

| Dump | R4 | Adresse de faute | Accès |
| --- | --- | --- | --- |
| 29 | 0x0000584a | 0x00005852 | lecture |
| 30 | 0x00005849 | 0x00005851 | lecture |

Le scanner introduit en 07 parcourait `*index->GetArchives()` directement.
Cette fonction LUS construit un nouveau vecteur et le retourne dans un
`shared_ptr`. En C++20, la référence obtenue en déréférençant ce temporaire
ne conserve pas le propriétaire pendant la boucle. Le vecteur était donc
libéré avant sa première lecture. Le désassemblage ARM le confirme : appel
de `GetArchives` à `0x00261f14`, destruction du propriétaire à `0x00261f24`,
puis lecture du vecteur à `0x00261f28`.

Le test précédent conservait lui-même le vecteur dans son faux gestionnaire
d'archives. Cette différence de durée de vie masquait la régression. Le défaut
du menu corrigé en 08 empêchait auparavant d'atteindre cette étape.

## Correction et vérification

Le scanner conserve désormais un `shared_ptr` nommé pour le vecteur des
archives, ainsi qu'un autre pour la table des fichiers parcourue. Il continue
à utiliser l'index existant pour les noms ordinaires et à ne stocker que les
alias nécessaires. Les priorités des mods, les noms alternatifs et le retrait
des alias après fermeture d'une archive sont préservés.

Le test d'extension utilise le contrat de création du snapshot LUS réel et
contrôle sa durée de vie. Il doit rejeter l'ancien scanner, puis réussir avec
le scanner corrigé sur des archives vides, absentes et contenant plus de
50 000 ressources. Les autres tests hôtes restent dans `scripts/verify_port.py`.

Deux messages sont ajoutés au journal : `extension scan complete` après le
parcours et `MM bridge initialized` à la fin de l'initialisation de la liaison
au jeu. Le marqueur de démarrage est `startup fix 09` et l'écran inférieur
affiche `Blinky 09`. Les optimisations graphiques de 07 restent en place.

## Installation

Remplacer le 3DSX et le SMDH dans `sd:/3ds/2ship`. Pour le titre installé,
réinstaller la nouvelle CIA ; copier un 3DSX ne met pas ce titre à jour.
Conserver les archives O2R, les sauvegardes et la configuration existantes.

Le correctif et les contrôles logiciels ne constituent pas un essai console.
Vérifier le démarrage, le menu des sauvegardes et Bourg-Clocher dans les deux
formats. Les performances GPU/CPU, le son, HOME et le capot de 09 restent à
valider sur matériel. En cas d'échec, conserver le journal avant un autre
lancement et le nouveau dump Luma.
