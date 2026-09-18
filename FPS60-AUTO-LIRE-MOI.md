> Document historique : ses patchs, anciens backends et anciennes commandes se rapportent aux livraisons archivées. Pour Blinky 07, utiliser README-BUILD-FR.md et tests/README-BLINKY.md.

# 2Ship3DS — AUDIO-FIX + Wizard v1.0.3-FPS60-AUTO

Nouvelle variante construite à partir de **2SHIP3DS-AUDIO-FIX-WIZARD-v1.0.2-FPS60.zip**.
Sources complètes et wizard inclus. **Aucun nouveau .cia/.3dsx/.elf du jeu précompilé.**
Ce guide décrit la version présente; les guides et manifestes FPS60/v1.0.2 antérieurs
restent dans le dossier comme historique, et ne décrivent pas ce changement additionnel.

## Lancement

Extraire le ZIP complet dans un nouveau dossier, par exemple
`C:\dev\2Ship3DS-FPS60-AUTO`. Lancer **LANCER-WIZARD.bat** à la racine extraite.
Le titre doit afficher **v1.0.3-FPS60-AUTO**. Sélectionner le devkitPro existant,
choisir **Reconstruction propre**, puis **Compiler**. Les choix d'archives,
d'icône, de bannière et de CIA sont conservés.

Ce paquet réutilise vos archives `mm.o2r` et `2ship.o2r` existantes. Les
polices binaires `.ttf`/`.otf` (ressources/exemples de la base) ne sont pas
fournies dans ce ZIP; la cible native du wizard ne les compile pas à partir
de ces fichiers. Le manifeste énumère ces exclusions. Le petit patch ne
supprime aucun fichier de votre copie existante.

Les nouveaux fichiers, après compilation réussie, seront dans
`2Ship3DS/dist-wizard/BUILD-.../SD/`. Utiliser **Ouvrir le résultat**, et non un
ancien dossier de sortie. Le rapport du build fournit version et empreintes.
Ni les sauvegardes ni les fichiers de configuration de la SD ne sont modifiés
par ce patch ou copiés depuis un autre utilisateur.

Avec le petit ZIP de patch, partir **exactement de la variante v1.0.2-FPS60**,
fermer le wizard, fusionner le dossier `2Ship3DS` avec le dossier du projet
contenant `build.py`, puis accepter les remplacements. Ne pas créer un second
`2Ship3DS` à l'intérieur. Faire une reconstruction propre au premier build :
les dates de distribution sont volontairement anciennes pour éviter la boucle
CMake/Ninja, et ne doivent pas entraîner la réutilisation d'objets précédents.
Le ZIP complet et le petit patch sont deux alternatives, pas deux étapes.

## Comportement choisi : frameskip automatique

**La cible reste à 60 FPS.** Ce n'est pas un contrôleur qui remplace le réglage
par des paliers 60 → 30 → 20. Le nombre de rendus exécutés s'adapte en sautant
les créneaux interpolés déjà en retard. Quand le retard disparaît, les rendus
interpolés reprennent automatiquement, sans intervention ni délai de remontée.

À cadence logique de 20 ticks/s et cible de 60 FPS, un tick prévoit trois rendus
aux coefficients 1/3, 2/3 et 1. Les deux premiers sont facultatifs : chacun peut
être sauté s'il est déjà trop tard. **Le dernier rendu prévu de chaque tick est
toujours exécuté.** À 30 FPS pour une logique à 20 Hz, certains ticks n'ont qu'un
rendu à t=2/3 : celui-ci est lui aussi obligatoire, même s'il est interpolé.

La décision utilise les hooks déjà présents dans le renderer,
`Soh3dsFrameBehind` / `Soh3dsFrameDropped`. Ils n'étaient pas appelés par le
`RunCommands` de MM dans la base FPS60. Le créneau d'une image sautée est consommé
par le cadenceur existant : on n'efface pas du temps du calendrier de rendu.
L'indice d'interpolation d'origine est conservé pour la liste d'affichage.

Un premier contrôle évite de calculer les matrices d'une image déjà obsolète;
un second contrôle, après interpolation, évite sa soumission si ce calcul a
lui-même fait dépasser l'échéance. Le retard est mesuré par le compteur LCD
utilisé par le renderer, pas par un prétendu pourcentage de CPU/GPU.

Une garde empêche d'utiliser une ancienne période après changement de cible.
Un retard dépassant les six vblanks de dette déjà admises par le renderer ne
provoque pas une salve de skips : `EndFrame` conserve sa resynchronisation.
Au démarrage et après une remise à zéro à la sortie de veille, aucun créneau
n'est sauté sur la base d'un ancien calendrier. Aucun nouveau thread n'est créé.

## Activer / désactiver

Dans le menu **Settings → Graphics**, la case **Auto frameskip (3DS)** contrôle
`g3DS.FrameSkip` : **1 activé**, **0 désactivé**. La valeur par défaut est 1.
Une désactivation déjà enregistrée est respectée, elle n'est pas forcée à 1
à chaque lancement. L'ancienne politique FPS60, qui sélectionne 60 au lancement,
reste inchangée. Le débogueur graphique désactive le frameskip pour ses captures.
Les backends sans les deux hooks fonctionnels n'activent pas le skip.

Le contrôle a été ajouté au code du menu; son affichage/utilisation sur l'écran
de la console n'a pas été testé ici. Il n'est pas nécessaire d'ouvrir le menu
pour profiter du défaut activé sur une configuration qui ne connaît pas encore
`g3DS.FrameSkip`.

## Ce qui reste inchangé

`Graph_ProcessGfxCommands`, `GetInterpolationFPS`, `OTRAudio_Thread`,
`OTRAudio_Init`, `StartFrame`, `EndFrame`, `Soh3dsFrameDropped` et le reset de
pacing à la sortie de veille sont conservés textuellement.

Les ticks du jeu, les réveils audio, les mutex et la barrière de fin de tick
ne sont pas sautés. Le correctif d'adresse de `playback.c`, le backend NDSP,
le mixer, la fréquence/format PCM et les tailles de buffers sont conservés.
Les fonctions de soumission GPU, les formats d'image/profondeur, les shaders,
la résolution et le rendu stéréoscopique ne changent pas. Le skip intervient
avant l'appel de rendu complet, pas entre l'œil gauche et l'œil droit.
La protection des dates CMake/Ninja et les fonctions du wizard sont conservées.

Trois fichiers de production sont concernés :

- `third_party/2ship/mm/2s2h/BenPort.cpp` : défaut du réglage, raccordement des
  hooks et saut des rendus facultatifs uniquement dans `RunCommands`;
- `platform/3ds/source/gfx_citro3d.cpp` : gardes de période et de dette dans
  `Soh3dsFrameBehind`, sans changement des fonctions de rendu/pacing;
- `third_party/2ship/mm/2s2h/BenGui/BenMenu.cpp` : case 3DS activable.

Les deux étiquettes du wizard sont mises à jour. Le test FPS60 précédent reçoit
les déclarations des hooks faibles nécessaires à son extraction de fonction;
**toutes ses assertions sont conservées**. Les cinq tests audio ne changent pas.
Le diff exact et les empreintes sont fournis dans `patches/mm-3ds-auto-frameskip.patch`
et `fps60-auto-manifest.json`.

## Validation exécutée

Journal : `validation/fps60-auto/tests.txt`.

Le nouveau `tests/test_mm_3ds_frameskip.py` compile les vraies fonctions extraites
ainsi que le bloc de pacing de `EndFrame`. Il vérifie 27 combinaisons de cadence
logique, plafond et retard simulé; les indices/coefficients; la conservation du
dernier rendu; le retour sans skip après récupération; le dépassement pendant
l'interpolation; les charges excessives; les changements de période; le passage
à zéro du compteur; l'opt-out et le débogueur. Cinq variantes sont compilées :
3DS simulée, autre plateforme, hook de retard absent, hook de consommation absent,
et les deux absents. Le worker audio et sa barrière tournent sur des threads hôte.

Les comptes obtenus pour une seconde **logique planifiée** restent 60 blocs
528/544/528 et 32 000 frames audio, quelle que soit la quantité de rendus sautés.
**Cela ne prouve pas que cette seconde logique prend une seconde murale sur 3DS.**
L'horloge LCD, le GPU, la synthèse, les matrices et la sortie audio sont simulés.

Le contrôle négatif remplace seulement `RunCommands` par la version FPS60
précédente : le test échoue à l'assertion de saut effectif, comme attendu.
Le test FPS60, les cinq tests audio, les **43 tests du wizard** et les
**15 tests des horodatages/CMake** passent également.

Pas de compilation complète devkitARM, pas d'exécution de l'interface Windows,
pas de mesure de performance matérielle, ni de validation de la sortie PCM réelle.
Les scénarios de test ne sont pas des benchmarks du jeu.

## Limites et comparaison sur console

Le frameskip retire du travail **graphique facultatif**; il ne réduit pas le
coût de la logique, de la synthèse, d'un rendu obligatoire ou d'un blocage GPU.
Si ce socle est déjà trop lent, le jeu peut encore ralentir et l'audio peut
encore manquer de données. Il n'y a pas de simulation accélérée, de production
audio autonome ni de changement de vitesse pour masquer cela.

Le mouvement peut devenir moins fluide quand des images sautent, et les images
conservées ne sont pas nécessairement espacées uniformément. Ce compromis doit
être évalué sur console. Aucun minimum réel de 20, 30 ou 60 FPS n'est garanti.
Le crash de transition du premier jour et les autres défauts audio existants
ne sont pas traités par ce lot.

Comparer la même scène, les mêmes archives/réglages et la même position du
curseur 3D avec la case ON puis OFF. Vérifier animation, contrôle de Link,
transitions, HUD et son. Tester aussi pause/veille/reprise et changement de
cible. Installer seulement les sorties du nouveau build réussi.

## Référence API externe

Le compteur vient de Citro3D, dont `source/renderqueue.c` incrémente
`frameCounter` dans les callbacks vblank suivant `C3D_FrameRate`. Cette base
appelle déjà `C3D_FrameRate(60.0f)`; ce patch ne change pas cet appel.
Source primaire consultée : https://github.com/devkitPro/citro3d/blob/master/source/renderqueue.c
Déclarations : https://github.com/devkitPro/citro3d/blob/master/include/c3d/renderqueue.h
Cette vérification de l'API ne remplace pas l'exécution sur la version du SDK
installée sur le PC de l'utilisateur.

Les licences, crédits et conditions de la base sont conservés. Aucun contenu
ROM ni archive de jeu `.o2r` n'est ajouté à cette distribution.
