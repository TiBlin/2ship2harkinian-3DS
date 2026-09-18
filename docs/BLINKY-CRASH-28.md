# Crash ARM11 28 — diagnostic et correctif 05

L'utilisateur signale un crash directement au démarrage. Le dump de 244 octets
identifie le processus 2Ship3DS, Title ID 0004000002534800, ARM11 core 0.
Ses 96 octets d'instructions correspondent exactement à l'ELF archivé de la
migration 04 (SHA-256 79bbfc684a048598cc11e5f570c8548510430cbdbaa7f0e8229f7d8a95ffb840).
Le 3DSX et le fichier CIA présents sur la SD avaient d'autres empreintes :
leur présence ne permet pas d'identifier la version CIA installée.

## Crash secondaire pendant l'arrêt

- PC 00d73f6c : syncArbitrateAddress, instruction ARM push {lr}.
- LR 00d7a66c : gspEventThreadMain.
- SP 084b10b0 ; adresse fautive 084b10ac, donc SP moins 4.
- DFSR 00000805 : écriture, Translation Section ; aucune pile lisible dans le dump.

Le journal se termine par « Blinky fatal: Blinky draw references absent texture ».
La fonction Fatal de 04 appelle std::_Exit. Dans le SDK effectivement lié, cette
voie atteint __libctru_exit qui libère les tas avant svcExitProcess. Les piles
des threads GSP et des autres workers peuvent donc disparaître pendant leur
exécution. Le dump correspond à ce scénario d'arrêt et non à une instruction
du jeu tentant directement d'accéder à une texture.

Fatal utilise maintenant svcExitProcess après vidage du journal et arrêt NDSP.
Le noyau termine le processus complet sans démappage préalable des piles par
l'application. Cette voie d'urgence revient à HOME, y compris depuis le 3DSX ;
la fermeture normale conserve son chemin habituel.

## Texture déclarée et texture réellement lue

Le décodeur officiel LUS peut déclarer les deux jeux d'UV pour un shader à deux
cycles alors que le combiner ne lit qu'une texture. L'interpréteur importe
seulement les textures effectivement utilisées. Blinky 04 exigeait cependant
une allocation pour chaque jeu d'UV déclaré et levait une exception.

Le nouveau test, compilant le vrai renderer avec le vrai décodeur LUS, reproduit
l'exception exacte sur 04. Après correction, les deux cas (sampler 0 seul et
sampler 1 seul après permutation du deuxième cycle) passent sur les voies GPU
simulée et CPU. La voie CPU vérifie chaque pixel du rectangle rouge attendu.
Le format du VBO, ShaderGetInfo et les offsets d'UV restent ceux de LUS.
L'analyse des dépendances ignore l'alpha désactivé et les termes annulés.

Les textures réellement manquantes restent des erreurs explicites : le journal
indique désormais unité, shader, frame, draw et état de liaison/allocation,
avec export de blinky-shaders.json. Aucun dessin n'est silencieusement ignoré
et aucune texture fictive ne remplace un asset manquant.

Limite : le journal 04 ne contient pas l'identifiant du shader responsable.
Le mécanisme reproduit est compatible avec l'erreur observée ; le dump seul
ne permet pas de prouver que cette anomalie était son unique déclencheur.

## Persistance des réglages

Le journal contient aussi des échecs répétés de remplacement du fichier JSON.
La sauvegarde native normalise le chemin, ferme et contrôle complètement le
temporaire, puis déplace l'ancien fichier vers .blinky-backup avant de publier
le nouveau. Aucun renommage ne cible un fichier déjà présent. Une publication
échouée restaure l'ancien fichier ; un arrêt entre les deux renommages permet
sa récupération au prochain démarrage. Le fichier valide reste prioritaire.
Les appels Save sont sérialisés. Ce remplacement à deux étapes n'est pas une
transaction atomique du système de fichiers.

Les tests injectent les échecs de publication, sauvegarde, restauration et
nettoyage, et contrôlent la récupération au relancement. La cause précise du
retour ENOENT du SD n'est pas déterminée par ce journal ; la persistance doit
être vérifiée sur console.

## Validation et portée

Les journaux de compilation et des tests sont livrés dans validation/.
Les tests hôtes vérifient les chemins de code, les pixels CPU et la propriété
mémoire ; ils ne simulent ni le GPU PICA200 ni le système 3DS complet.
Le correctif 05 n'a pas été exécuté sur une console par l'agent.
Il ne constitue pas une certification d'originalité de tout l'arbre source :
les dépendances officielles et les fichiers encore non réattribués restent
signalés dans l'inventaire de provenance.

Références publiques utilisées pour le diagnostic :

- Format du dump : https://github.com/LumaTeam/luma3ds_exception_dump_parser/blob/master/luma3ds_exception_dump_parser/__main__.py
- Sortie SDK : https://github.com/devkitPro/libctru/blob/master/libctru/source/system/ctru_exit.c
- Adaptation SD : https://github.com/devkitPro/libctru/blob/master/libctru/source/archive_dev.c
