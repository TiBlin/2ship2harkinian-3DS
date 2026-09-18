# Variante CRASH26 — FPS60-AUTO, garde de ressource et trace ciblée

## À quoi sert ce build

Le dump 26 correspond à l'ELF fourni (96/96 octets autour du PC). Une ressource
nulle est passée à GetInitData depuis ResourceMgr_LoadIfDListByName, pendant
EnBomjimb_Draw pour objects/object_cs/object_cs_Tex_00EE20 (segment 9).

Cette variante empêche ce déréférencement précis et enregistre la raison de
l'échec lorsqu'elle traverse un des points instrumentés. Elle ne garantit PAS
que la texture soit réparée, que tout le jeu fonctionne ou que tous les autres
crashs disparaissent. Elle ne remplace pas les ressources du jeu.

Le wizard est conservé et porte toujours le titre v1.0.3-FPS60-AUTO.
Le cap 60, le frameskip automatique, l'audio, la stéréoscopie et la protection
contre la boucle CMake restent inchangés.

## Compilation Windows

1. Extraire le ZIP COMPLET dans un NOUVEAU dossier, par exemple
   C:\dev\2Ship3DS-CRASH26. Éviter de le fusionner avec un build plus récent.
2. Lancer LANCER-WIZARD.bat à la racine extraite.
3. Choisir Reconstruction propre et Compiler. Garder les mêmes ressources.

Important : libultraship DOIT être reconstruite également. Ne pas utiliser
--skip-lus. Deux fichiers de cette bibliothèque contiennent la nouvelle trace.

Installer/lancer uniquement le CIA/3DSX provenant de ce nouveau résultat BUILD.
Conserver son 2ship-3ds.elf et son package-manifest.json pour tout nouveau dump.
Aucun exécutable recompilé pour ARM n'est fourni dans ce ZIP.

## Après l'essai

Sur la carte SD :

    3ds/2ship/resource-failure-crash26.log

Récupérer ce fichier, même si le jeu ne plante plus. La trace est active sans
activer le logging général, limitée à 16 tentatives d'enregistrement par
lancement pour la texture concernée. Les anciennes lignes sont conservées :
renommer le log avant un nouvel essai de cette variante s'il existe déjà.

Une ligne peut préciser archive-load-exception, archive-load-null, read-header,
factory-lookup, factory-read, puis segment-probe. Le détail exact de l'exception,
le type/version/format lus et les mesures mallinfo servent au prochain diagnostic.
Un simple "resource-null" ne suffit pas à en identifier la cause ; "heap_free"
ne représente pas toute la RAM libre et errno n'est qu'un instantané.

En cas d'autre plantage, conserver le nouveau dump et le nouvel ELF/manifeste.
La trace peut causer une brève pause en cas d'échec ciblé ; ce build n'est pas
un benchmark. Une erreur d'écriture SD peut empêcher la création du log.

## Fichiers de production modifiés

- third_party/2ship/mm/2s2h/BenPort.cpp : garde du probe de display list sur 3DS.
- third_party/libultraship/src/ship/resource/ResourceManager.cpp : traces des
  retours nuls/exceptions avant l'import, sans changer leur comportement.
- third_party/libultraship/src/ship/resource/ResourceLoader.cpp : trace ciblée
  de la texture, budget indépendant saturant, fermeture/synchronisation et
  relances EINTR bornées.

Le résultat nullptr du probe est déjà prévu par gSPSegment : le chemin original
reste dans la commande. Le patch ne change pas les squelettes et ne supprime
pas l'acteur. Une texture toujours indisponible peut encore mal s'afficher ou
révéler une autre défaillance du pipeline.

## Tests

    python tests/test_mm_crash26_resource_probe.py .

18 contrôles hôte avec doubles explicites et UBSan passent. Le test détecte
l'ancien bug (contrôle négatif et exécution sur les sources d'origine).
Les cinq tests audio, FPS60 et frameskip ont également été relancés avec succès.
Pas de compilation ARM complète ni de test sur console réalisés ici.

Définir TWOSHIP3DS_DISABLE_CRASH26_TRACE à la compilation de LUS désactive
la nouvelle trace sans retirer la garde. Ce n'est pas une option UI du wizard.
