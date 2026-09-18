# Architecture Blinky native 07

Le CMake racine produit le véritable 2ship-3ds.elf : 816 unités du jeu, 532
unités d'extensions 2Ship, LUS, codecs et gfx_blinky_citro3d. Les formats 3DSX
et CIA emballent cet exécutable. Aucune ROM ni archive de jeu n'est fournie.

```text
main MM -> précontrôle SD -> InitOTR -> Context -> Fast3dWindow
  -> GfxWindowBackendBlinky3DS
  -> GfxRenderingAPIBlinkyCitro3D
  -> Interpreter::Init / Run / EndFrame
  -> display lists MM -> décodeur/combiner officiel LUS
  -> PICA TexEnv si représentable, raster de référence CPU sinon
  -> framebuffer logique -> rotation LCD -> Citro3D

aptMainLoop -> hidScanInput -> Blinky HID -> LUS Controller -> OSContPad MM
MM audio -> LUS AudioPlayer -> Blinky NDSP -> PCM s16 LE stéréo à 32000 Hz
```

Le runtime utilise l'allocateur public libctru, avec 16 Mio de mémoire linéaire
et une pile principale de 1 Mio. Le tas normal reçoit le budget restant selon
libctru. Ce choix remplace l'allocateur privé V7 : la marge disponible pour les
services devra être vérifiée sur CIA et 3DSX. Les workers C++ reçoivent une pile
minimale de 128 Kio, sans modifier une pile explicitement fournie par l'appelant.

Le renderer possède gfx/Citro3D, les cibles VRAM, textures et sommets linéaires.
Les textures RGBA fournies par LUS sont converties en ordre ABGR et tuiles Morton
8×8 ; allocations puissance de deux, minimum 8, maximum 1024. LUS continue de
décoder RGBA16/32, IA, I et CI/TLUT. Les copies CPU s'effectuent hors frame :
C3D_SyncTextureCopy peut seulement mettre en file une copie dans une frame.
Une clôture GPU précède libération, redimensionnement et remplacement de
stockage. Une texture DMA évincée est réimportée par le cache LUS.

Les sommets GPU occupent 56 octets : clip, couleur, UV0/UV1 et coordonnée
de brouillard. Une rampe sur texture 2 et un étage TexEnv appliquent le
brouillard. Les limites UV partitionnent les triangles en conservant
l'interpolation homogène. Les découpes alpha utilisent deux passes et les
mêmes sommets. Les triangles compatibles sont groupés dans un appel LUS.
Voir BLINKY-PERFORMANCE-07.md pour les limites de précision.

La profondeur PICA est inversée, D16, clear=0, comparaison GREATER/GEQUAL.
Le clip GL [-w,w] devient PICA [-w,0]. L'écran logique reste 400×240 ; seule
la présentation vers la surface LCD 240×400 effectue une rotation. Les
framebuffers intermédiaires sont des textures VRAM indépendantes.

Le chemin CPU conserve une copie du framebuffer entre triangles consécutifs,
avec clipping homogène, interpolation perspective, profondeur, échantillonnage
et combiner. Il termine sa copie avant de repasser au GPU. Il s'agit d'un filet
de vérification fonctionnelle potentiellement très lent, pas d'une garantie de
30/60 FPS. Son bruit déterministe n'est pas bit-identique au GLSL. Le biais de
décalque ne reproduit pas encore le polygon offset OpenGL : GEQUAL seulement.

La cadence de présentation propose 30 et 60 ; le choix est conservé. Le rythme
de simulation, les quantités de PCM et la barrière audio restent ceux de MM.
Le mode mono est le seul mode Blinky actuel. MSAA n'est pas implémenté et le
chemin natif sélectionne explicitement une seule sample.

SELECT ouvre le menu texte inférieur ; D-pad sélectionne/modifie, A change,
B/SELECT ferme. Les mappings sont stockés sous gBlinky.Input.*, distincts des
anciens profils SDL. Le tactile inférieur fournit quatre touches C. Le
C-Stick alimente le stick droit LUS. La gyroscopie native reste à implémenter.

Le coordinateur APT mémorise HOME et capot séparément. NDSP garde la pause même
avant son initialisation. La dernière reprise réactive le son. EXIT reste
terminal ; DeinitOTR quiesce le DSP avant de joindre le worker. Les callbacks
du renderer sont retirés avant destruction. Les données PCM ne sont réutilisées
qu'après DONE et toutes les copies d'un batch sont vidées du cache avant sa
publication. Le verrou de registre précède toujours celui du périphérique.

Les données, sauvegardes et configurations restent dans sd:/3ds/2ship.
blinky.log rapporte le démarrage, les replis CPU et les erreurs ;
blinky-shaders.json décrit les recettes et compteurs. Les erreurs d'archives
et de décodage passent aussi dans blinky.log. Le RomFS n'est pas utilisé pour
remplacer les deux archives O2R exigées sur SD.

L'archive O2R native conserve un seul handle libzip, fermé par RAII. Les lectures
et écritures se partagent un mutex ; une transaction d'écriture ferme le lecteur,
valide le commit, puis rouvre la vue. Une lecture partielle est poursuivie et une
erreur de CRC/EOF ferme l'entrée sans publier de ressource. L'index du gestionnaire
est un tableau trié hash/numéro d'archive/pointeur de chemin ; il ne recopie pas
les chaînes déjà détenues par chaque archive. La dernière archive montée garde
la priorité. Le décodage emploie un worker sur 3DS et publie sous un verrou unique.
Un échec transitoire de lecture/décodage ne crée pas d'entrée négative persistante.

Une opération de rendu rejetée provoque désormais un arrêt signalé dans le journal.
Une frame partiellement exécutée n'est plus ignorée pour poursuivre silencieusement.

En 07, les files de messages libultra ont une unité native Blinky dédiée.
La publication CVar conserve des valeurs immuables sous mutex. Les ponts MM
conservent des propriétaires explicites pour la résidence et le worker audio.
Les erreurs fatales natives passent par BlinkyAbortProcess puis svcExitProcess
pour éviter le démontage des heaps avec des workers GSP encore actifs.
La sortie normale arrête les producteurs et périphériques dans l'ordre.
