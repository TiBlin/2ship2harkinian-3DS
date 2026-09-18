> Document historique : ses patchs, anciens backends et anciennes commandes se rapportent aux livraisons archivées. Pour Blinky 07, utiliser README-BUILD-FR.md et tests/README-BLINKY.md.

# 2Ship3DS — audit de stabilité et premier lot de durcissement

> Document historique antérieur à Blinky. Depuis les migrations 01/02, le
> backend actif est `BlinkyNdspAudioPlayer` ; l'ancien `NdspAudioPlayer` a été
> retiré. Les six régressions NDSP courantes ciblent Blinky. Voir
> `docs/BLINKY-CLEANROOM-AUDIT.md` pour l'état actuel ; ne pas réappliquer le
> patch historique NDSP par-dessus cette migration.

**Variante livrée : `1.0.4-STABILITY-AUDIT1`**  
**Base exacte : `2SHIP3DS-FPS60-AUTO-CRASH26-SOURCES.zip`**  
SHA-256 de la base : `7c7223d413d54efd2f7076424823f5bce7c9d0103ef277abda4d4954be39ab7e`

## Conclusion

Le correctif CRASH26 protège un appel particulier ; il ne constituait pas une stratégie globale de stabilité. L'audit retrouve des problèmes indépendants : lectures binaires hors limites, plages de texture non validées, publication concurrente incohérente, pointeurs persistants vers des ressources évictables et opérations audio après fermeture possible.

**Sept groupes de défauts ont un premier correctif dans cette variante.** Deux utilisations après libération et trois lectures hors limites sont notamment reproduites sur l'ancienne source par AddressSanitizer. L'audit conserve aussi des problèmes prioritaires non corrigés, dont l'écriture des sauvegardes et le traitement des ressources indispensables absentes. Il ne faut donc pas appeler cette archive une version « stable » au sens d'une validation sur console.

Le dump 26 reste le seul crash matériel utilisé comme référence. Il identifie `ResourceMgr_LoadIfDListByName` recevant une ressource nulle pour `objects/object_cs/object_cs_Tex_00EE20`. Aucun nouveau log d'échec de chargement ni les octets de `mm.o2r`/`2ship.o2r` ne sont disponibles ici. **L'audit ne prouve pas que les autres défauts ci-dessous ont causé ce dump et ne tranche pas son échec de chargement initial.**

## 1. Périmètre réellement examiné

Il s'agit d'une revue ciblée des chemins critiques, pas d'une revue ligne par ligne des milliers de fichiers du jeu.

Les points inspectés sont la sélection des sources par `CMakeLists.txt`, les scripts de construction de libultraship, les ponts de `BenPort.cpp`, `ResourceManager`, `ResourceLoader`, `O2rArchive`, `MemoryStream`, `BinaryReader`, les factories de texture et leurs propriétaires, les commandes graphiques persistantes, l'éviction de scène, les consommateurs de squelettes, `SaveManager`, le teardown de `Context`, le backend NDSP, le cadenceur FPS60-AUTO, le cache de l'interpréteur et la retraite des textures du backend Citro3D.

Le backend audio actif est `third_party/libultraship/src/ship/audio/NdspAudioPlayer.cpp`. Les anciens fichiers `platform/3ds/source/audio_runtime_3ds.cpp` et `audio_ndsp_3ds.cpp` ne sont pas les bonnes cibles pour cette construction ; ils n'ont pas été modifiés.

Le chemin utile à auditer est :

```text
Commande / acteur / synthèse
  → pont BenPort
  → ResourceManager : cache et chargement
  → O2rArchive : octets
  → ResourceLoader / factory : structure native
  → shared_ptr propriétaire en cache
  → pointeurs bruts empruntés par le moteur et certaines display lists
  → éviction, remplacement ou fermeture
```

Le point faible n'est donc pas simplement « il manque des if ». Un contrat de durée de vie ou d'échec peut être violé plusieurs fonctions avant la lecture fautive.

### Niveaux de preuve

**Reproduit sur hôte** : le code réel, ou une fonction extraite de ce code avec des collaborateurs explicitement simulés, montre le défaut dans un scénario contrôlé. **Établi par inspection** : un chemin dangereux est visible, sans exécution complète de ce chemin. **À mesurer sur console** : fréquence, impact sonore, pression mémoire réelle et lien avec le dump. Ces niveaux ne sont pas interchangeables.

Les extraits BASE/AUDIT1 avec leurs numéros de ligne se trouvent dans `SOURCE-EVIDENCE.md`. Les diff unifiés et les empreintes des fichiers sont livrés avec les sources.

## 2. Correctifs appliqués

### A01 — Lectures de MemoryStream hors du tampon

**Gravité : élevée si un en-tête ou un bloc est tronqué. Reproduit.**

Fichier : `third_party/libultraship/src/ship/utils/binarytools/MemoryStream.cpp`.

La version précédente utilisait `vector::at(mBaseAddress)` puis copiait `length` octets. Cela valide uniquement le premier octet. Une lecture de quatre octets à partir d'un tampon d'un octet commence à une adresse valide, puis déborde. Trois tests couvrent les deux surcharges de `Read` et le passage par `BinaryReader::ReadUInt32` : l'ancienne source déclenche `heap-buffer-overflow`.

La nouvelle garde valide la plage entière avant allocation/copie :

```text
position ≤ taille ET longueur ≤ taille − position
```

Cette forme évite aussi le débordement arithmétique de `position + longueur`. Les lectures vides à EOF sont autorisées sans déréférencement. Une lecture échouée ne fait plus avancer le curseur. Les constructions avec tampon nul non vide sont rejetées.

L'audit a également corrigé la comptabilité de taille après une écriture et l'overflow de la taille de croissance. L'ancien `WriteByte` retenait une taille inférieure d'un octet ; `Write` pouvait additionner une longueur à tort à la taille existante. **La convention existante de `Seek(..., End)` n'a pas été redéfinie.** Les écritures depuis une source qui aliaserait le tampon à redimensionner ne sont pas couvertes par ce lot.

### A02 — Textures zéro-copie sans validation de la plage publiée

**Gravité : élevée sur payload invalide. Acceptation indue reproduite.**

Fichier : `third_party/libultraship/src/fast/resource/factory/TextureFactory.cpp`.

Les factories V0 et V1 lisaient `ImageDataSize`, puis publiaient directement un pointeur dans le buffer sans vérifier que cette quantité de données y existait. Une texture annonçant 1 024 octets avec seulement sept octets de payload pouvait donc sortir comme ressource chargée. La largeur et la hauteur étaient également rétrécies de 32 à 16 bits sans contrôle.

Le correctif refuse les dimensions nulles ou non représentables dans les champs existants, puis vérifie la position et la longueur du payload avant de publier `ImageData`. Le propriétaire `mImageBuffer` et le zéro-copie sont conservés. Les cas valides V0/V1 restent lisibles après la destruction du `File` et de son reader.

**Ce n'est pas une validation exhaustive des formats de texture.** Il reste à contrôler les rapports entre dimensions, format, stride, facteurs d'échelle, taille consommée par chaque branche de décodage et éventuels formats personnalisés. Les vraies archives de cette console n'ont pas été parcourues.

### A03 — Publication concurrente de deux propriétaires pour une ressource

**Gravité : élevée pour les consommateurs de pointeurs bruts. Interleaving reproduit.**

Fichiers : `ResourceManager.cpp` et `ResourceManager.h` dans libultraship.

L'ancien chemin effectuait une consultation du cache, relâchait le verrou, puis prenait de nouveau ce verrou pour publier. Deux chargements pouvaient chacun constater une absence, puis publier deux objets différents. L'un remplaçait l'autre, alors qu'un consommateur pouvait déjà avoir emprunté son adresse.

Un test avec deux threads et des barrières force précisément ce calendrier : les deux résultats de l'ancienne version sont distincts pour la même clé. La version corrigée choisit un seul propriétaire canonique avec `PublishResourceLoad`, qui réunit relecture et publication sous le même mutex. Le perdant retourne l'objet déjà publié. Les références déplacées sont conservées jusqu'à la sortie du verrou pour éviter de détruire une ressource réentrante en tenant ce mutex.

Le même chemin corrige la confusion entre **absence** et **échec transitoire**. Un `LoadFile` nul n'est plus systématiquement inscrit en `NotFound` lorsque l'index contient encore l'entrée. Un échec d'import ne reçoit plus ce statut définitif. C'est particulièrement pertinent pour `alt/`, dont le chemin utilise le cache négatif pour choisir le fallback. Le chemin standard retentait déjà certains chargements : il serait inexact d'affirmer que tous les échecs précédents étaient bloqués définitivement.

Tests supplémentaires : succès déjà publié conservé face à un échec tardif, nouvelle tentative après erreur de lecture/import, absence réelle mémorisée, destruction hors verrou. **Ce changement ne met pas en place une génération d'éviction et ne sécurise pas tous les autres accès du gestionnaire**, notamment le drapeau dirty, les propriétaires alternatifs ou tous les remplacements externes.

### A04 — Display lists statiques utilisant des ressources de scène libérées

**Gravité : élevée lors d'une réutilisation après éviction. Deux use-after-free reproduits.**

Fichier : `third_party/2ship/mm/2s2h/Enhancements/GfxPatcher/AuthenticGfxPatches.cpp`.

Deux commandes persistantes retenaient seulement des adresses brutes :

- `GfxPatcher_ApplyFierceDeityGIPatch` conserve une texture d'herbe de `Z2_SOUGEN` dans une display list d'objet ;
- `PatchGeometrySeams` conserve une plage de sommets de `Z2_CLOCKTOWER` dans une display list statique.

Ces commandes peuvent vivre plus longtemps qu'un `PlayState`. Le chemin d'éviction des scènes supprime les entrées correspondantes du cache. Une adresse brute ne contribue pas à `shared_ptr::use_count` : son existence n'empêche aucune libération.

Les tests extraient les fonctions réelles et simulent le retrait de leur dernier propriétaire de cache. La lecture ultérieure de la texture et des sommets déclenche `heap-use-after-free` avec l'ancienne version. Le correctif 3DS conserve un propriétaire fort pour chacune de ces deux ressources. **Il ne conserve pas toute la scène et ne désactive pas l'éviction globale.**

La plage de 32 sommets à partir de l'indice 14 est vérifiée avant installation de la correction de jointure. L'herbe est vérifiée contre la quantité minimale utilisée par sa commande RGBA16 32 × 32. En cas d'absence, ces deux workarounds graphiques ne sont pas installés avec un pointeur invalide ; aucun acteur ni tick de jeu n'est supprimé. La correction de jointure désactivée n'impose pas ce chargement.

Le coût mémoire est celui des deux ressources effectivement retenues, pas celui d'un dossier entier ; leur empreinte exacte n'est pas mesurée sans les assets. Le comportement de rechargement dynamique des mods reste celui d'une commande statique : ce n'est pas un nouveau système d'invalidation des mods.

### A05 — Diagnostic de cache avec des string_view devenus pendants

**Gravité : modérée, potentiellement crashante lors d'une éviction concurrente. Reproduit par calendrier contrôlé.**

Fichier : `ResourceManager.cpp`, méthode `Soh3dsCacheReport`.

Les noms de catégories étaient des vues sur les chaînes des clés du cache. Le verrou était relâché entre la collecte de ces vues et leur mise en forme. Un autre thread pouvait effacer les clés pendant cet intervalle.

Le verrou couvre maintenant la mise en forme, limitée à 24 catégories, et une sortie vide est correctement terminée. Le test insère uniquement un point d'ordonnancement avant le tri ; un autre thread tente l'éviction. La version d'origine produit une sortie invalide après libération, la nouvelle empêche l'effacement tant que les vues sont utilisées. Ce test ne repose pas sur une attente aléatoire et n'est pas une mesure de contention sur ARM.

### A06 — Contrat NDSP : état de fermeture et flush

**Gravité : élevée pour le cycle de vie ; effet sonore d'un flush raté non mesuré. Reproduit avec SDK simulé.**

Fichier : `third_party/libultraship/src/ship/audio/NdspAudioPlayer.cpp`.

`Buffered()` vérifiait l'initialisation avant de prendre le verrou, puis appelait NDSP sans revérifier. `DoClose()` pouvait passer entre ces deux étapes. De plus, le booléen lu sans verrou n'était pas atomique. Enfin, la soumission ne vérifiait pas le `Result` de `svcFlushProcessDataCache`.

Le drapeau est maintenant atomique ; `Buffered()` le revérifie sous verrou ; un flush échoué n'est jamais suivi de `ndspChnWaveBufAdd` pour ce bloc. Des compteurs saturants et le dernier `Result` alimentent la trace de pacing déjà existante ; aucune boucle de retry ni nouvelle écriture SD par bloc n'a été ajoutée. Un échec reste une perte de soumission, pas un bloc magiquement récupéré.

Les huit slots de 2 048 frames, les 32 000 frames/s, le PCM s16 stéréo entrelacé, les blocs produits et la barrière audio/jeu sont conservés. Les tests vérifient copie, taille, statut de slot, pool plein, fermeture intercalée, flush raté et nettoyage après allocation partielle.

Le libellé de la métrique « gaps » devient « empty observations » : une file vide pendant démarrage, pause ou fermeture n'est pas à elle seule un underrun audible mesuré. Les statuts NDSP et son curseur restent asynchrones ; **cette série n'est ni une capture PCM ni une preuve de disparition des coupures**. L'initialisation et la fermeture restent soumises au cycle de vie existant, sans support ajouté pour une réinitialisation concurrente arbitraire.

### A07 — Métadonnées XML/alias nulles

**Gravité : modérée à élevée avec ressource personnalisée invalide. Reproduit.**

Fichier : `ResourceLoader.cpp`.

`ReadResourceInitDataXml` utilisait `root->Name()` sans vérifier l'existence d'un élément racine. L'absence de document pouvait également produire des métadonnées par défaut plutôt qu'un échec. Le chemin `.meta` déréférençait ensuite `metaInitData` sans vérifier le résultat de son parsing.

Les documents/racines absents donnent maintenant un résultat vide explicite ; un alias invalide n'est pas déréférencé et ne remplace pas le fichier d'origine. Les cas document/racine valides et alias valide sont testés. Cela ne résout pas le cache de présence des `.meta` décrit plus bas.

## 3. Problèmes encore prioritaires

### R01 — Ressources indispensables : il manque un protocole d'échec de bout en bout

**Priorité avant de qualifier le port de stable.**

`ResourceMgr_LoadTexOrDListByName`, `ResourceMgr_ResourceIsBackground`, les accès aux animations/tableaux et `ResourceMgr_LoadSeqByName` comportent encore des consommateurs qui supposent un résultat chargé. `SkelAnime_InitFlex` utilise immédiatement le squelette renvoyé ; `OTRPlay_SpawnScene` transmet le résultat du chargement à l'initialisation sans transaction complète.

Retourner zéro partout ne serait pas une solution : cela peut laisser une animation partielle, un acteur incohérent ou une scène incomplète qui continue à mettre à jour et sauvegarder le jeu. La direction recommandée est de distinguer la ressource facultative de la ressource obligatoire, et de faire échouer une initialisation entière à une frontière contrôlée. Les catégories proposées — absence, lecture, format, allocation — doivent rester distinctes dans la trace et dans les décisions. Ce schéma est une proposition, pas une API déjà implémentée.

Le correctif CRASH26 préserve légitimement le chemin original lorsque le probe ne retourne pas de display list. Le renderer possède certains contrôles de résultat nul, mais d'autres consommateurs ne les possèdent pas. **La protection d'un probe n'est pas une restauration de la texture.** Le log CRASH26 reste nécessaire pour établir l'erreur initiale de cet asset.

### R02 — Sauvegardes : troncature directe et erreurs de flux silencieuses

Fichier : `SaveManager/SaveManager.cpp`, `SaveManager_WriteSaveFile`.

La fonction ouvre directement le fichier final avec `std::ofstream`, écrit, ferme, et compte sur un `catch`. Elle ne vérifie pas les états d'échec du flux et ne configure pas ses exceptions. Une erreur d'écriture peut donc tronquer le fichier existant tout en laissant la fonction retourner normalement.

**Contre-exemple exécuté :** la fonction réelle est extraite ; seul le sérialiseur JSON est remplacé par un collaborateur de chaîne. Le sous-processus Linux est limité à 64 octets par fichier après création d'une ancienne sauvegarde fictive. Une écriture de 1 025 octets laisse 64 octets, détruit l'ancien contenu et ne déclenche aucun log d'erreur. Ce n'est pas un test de la SD ni du sérialiseur JSON ; c'est un test de la gestion d'erreur d'`ofstream` dans cette fonction. Aucun fichier de sauvegarde réel n'a été utilisé.

La future correction doit écrire dans un fichier temporaire du même dossier, vérifier écriture/fermeture, garder une récupération et ne promouvoir la nouvelle version qu'après succès. La résistance à une coupure pendant la promotion doit être testée sur le système de fichiers réel. **Ce protocole n'a pas été improvisé dans ce premier lot. Sauvegarder une copie du dossier de saves avant les essais est indispensable.**

### R03 — Fermeture avec des tâches de chargement encore actives

Dans `ResourceManager.h`, `mMutex` et d'autres membres sont déclarés après `mThreadPool`. Ils sont donc détruits avant le pool. Le destructeur du pool fourni attend ses workers, mais le destructeur de `ResourceManager` ne les draine pas explicitement avant la destruction des membres.

`Context::DestroyInstance` remet aussi le singleton à nul, alors que les factories utilisent ce singleton ; la fenêtre et d'autres services sont libérés avant le gestionnaire de ressources. **S'il reste des tâches actives**, attendre implicitement le pool trop tard ne garantit pas que leurs dépendances existent encore. Les anciens tests de teardown couvraient des sous-systèmes partiellement initialisés simulés, pas ce calendrier de workers.

Le contrat à implémenter est : bloquer les nouvelles tâches, arrêter les producteurs, drainer/annuler de façon définie, puis libérer les consommateurs et enfin le contexte. Déplacer uniquement le mutex ne résoudrait pas tous ces accès.

### R04 — Cache de présence des `.meta` et états partagés

`ResolveMetaAlias` utilise des statiques `sCheckedArchiveCount`/`sAnyMeta` non synchronisées. Le nombre d'archives sert de seule invalidation : remplacer un ensemble par un autre de même cardinalité ne force pas une nouvelle observation. Un worker et le thread appelant peuvent également accéder à ces variables pendant leur mise à jour.

La correction d'A03 ne revendique pas résoudre cette course. Il faut associer l'observation à une identité/génération d'index, avec publication synchronisée. `IResource::mIsDirty` et certaines options partagées méritent le même traitement ; ce lot n'affirme pas un gestionnaire entièrement exempt de data races.

### R05 — Validation des autres imports et tailles ZIP sur ARM32

`zip_stat.size` est une taille 64 bits alors que `vector<char>` prend une taille native. Le chemin examiné ne pose pas de garde explicite avant cette conversion sur la cible 32 bits ; la boucle de lecture conserve ensuite la taille ZIP. Une taille hors domaine doit être refusée avant conversion, même lorsqu'elle provient d'une archive théoriquement valide. Aucune entrée aussi grande n'a été fournie ici.

Les factories d'animations, squelettes et listes de commandes ne sont pas couvertes exhaustivement par A01/A02. Une garde de copie ne contrôle pas un indice sémantique, une allocation excessive, une liste sans terminateur ou un compte multiplié par un stride. Un passage d'audit supplémentaire doit associer chaque compte sérialisé au budget d'octets et aux limites du consommateur.

Le chemin 3DS d'O2rArchive gère déjà les lectures positives courtes en boucle et refuse une lecture prématurément terminée ; il n'a pas été remplacé par un lecteur improvisé.

### R06 — Cache graphique non transactionnel face à bad_alloc

`Interpreter::TextureCacheLookup` insère d'abord le nœud de map, puis le nœud LRU. Si cette seconde allocation échoue, le premier nœud peut rester sans lien LRU valide. D'autres opérations d'éviction présupposent ce lien. L'exception ne doit donc pas être considérée comme proprement absorbée simplement parce qu'une frame peut être abandonnée.

C'est un scénario établi par inspection de la séquence, non une injection de panne exécutée dans tout l'interpréteur. Une correction doit construire les deux éléments avec rollback et vérifier le devenir de l'identifiant GPU. Elle doit être testée avec allocation forcée en échec à chaque étape, sans libérer une texture encore utilisée par une commande GPU.

Le backend Citro3D contient déjà des mécanismes utiles : descripteurs à adresses stables, retraite des textures et attente de queue avant certaines libérations. Ils n'ont pas été supprimés ni remplacés par un simple `FrameSync`. La validité d'une page mémoire n'est par ailleurs pas la preuve de validité d'un objet C++ qui y résidait.

## 4. Tests effectués et limites

Le nouveau runner `tests/test_stability_audit1.py` exécute **46 cas positifs sur la variante** et **24 contrôles négatifs sur la base**, soit 70 cas dans la comparaison. Un échec de compilation ou un timeout n'est pas compté comme une reproduction réussie.

Il compile les vrais fichiers `MemoryStream`, `Stream`, `BinaryReader`, `TextureFactory`, `Texture` et les bases de ressource. La journalisation est simulée. Les fonctions de gestionnaire, les patchs persistants et les fonctions XML/alias sont extraites avec des collaborateurs explicitement fournis. Le backend NDSP réel est compilé contre un SDK de test ; son type d'adresse est élargi pour l'hôte, ce qui exclut toute prétention de validation ABI ARM. AddressSanitizer et UndefinedBehaviorSanitizer sont activés. Aucun résultat de ThreadSanitizer n'est revendiqué.

Les tests couvrent les cas normaux autant que les échecs : octets préservés, ownership zéro-copie, cache hit, slot DONE réutilisable, 2 176 octets/544 frames, capacité du pool, allocation partielle, pinning et refus de plages invalides. Le contre-exemple de sauvegarde reste un constat de problème non corrigé, séparé du runner de non-régression.

Les **17 scripts de test préexistants** ont été relancés sans réécrire leurs assertions : contrôles natifs, preflight, éviction, horodatages, wizard, teardown partiel, FPS60, frameskip, timing/audio, ADPCM, presets audio, mélange des contrôles, CRASH26, mixer, filtre de notes et artwork. Avec le nouveau runner, la suite comporte 18 scripts.

Le premier test artwork sur la base a échoué car l'extraction Python n'avait pas remis le droit d'exécution du `bannertool` Linux. Après restauration de ce droit, le même test passe ; ce n'était pas une correction du moteur. L'événement et son retest sont conservés dans les preuves.

**Non effectué :** build complet devkitARM ; lancement Windows du wizard ; mesure de performances sur New 3DS ; test réel NDSP/GPU ; validation des archives personnelles ; endurance de transitions ; validation de sauvegarde sur SD. Les anciens tests et les nouveaux contre-exemples ne suffisent pas à prouver la stabilité globale.

## 5. Invariants conservés et traçabilité

Le moteur de notes, le mixer et le scheduler audio de `BenPort.cpp` sont inchangés. La cible FPS60, le frameskip, la barrière audio, la stéréoscopie, les formats des render targets et le backend Citro3D sont inchangés. Seules deux commandes graphiques persistantes ont reçu des propriétaires de ressources ; ce n'est pas un changement de gameplay.

Le lot touche **sept fichiers de runtime** (six unités C++ et un header) plus les deux libellés de version du wizard. Les tests, documents et manifests ajoutés sont séparés. Les fichiers manifest historiques de la distribution ne décrivent pas rétroactivement les nouvelles empreintes : utiliser `stability-audit1-manifest.json` pour ce delta.

Les modifications de libultraship exigent sa reconstruction. Lancer le wizard dans un nouveau dossier avec « Reconstruction propre » ; ne pas utiliser `--skip-lus`. Le wizard conserve l'ELF et le manifeste du packaging : les garder avec l'exécutable réellement installé, puis avec chaque nouveau dump. Un hash du manifeste n'est pas à lui seul une preuve que ce binaire a été installé.

## 6. Validation console avant de parler de stabilité

| Essai | Critère d'acceptation |
|---|---|
| Nouvelle partie et reprise d'une copie de sauvegarde | Aucun crash de chargement ; build et ELF identifiés. |
| Scène/NPC du dump 26 | Absence de nouveau déréférencement ; trace du chargement examinée même sans crash. |
| Sortir de Clock Town, visiter Termina Field, revenir, répéter | Pas de réutilisation invalide des deux commandes persistantes ; ressources recréées normalement. |
| Afficher les objets et activer/désactiver la correction de jointure | Pas de crash de vertex/texture ; comparaison visuelle. |
| Pauses, reprises, fermeture du logiciel, veille/réveil | Pas d'appel de backend après fermeture ni de deadlock ; test séparé des performances. |
| Scènes lourdes en FPS60-AUTO et comparaison avec frameskip désactivé | Cadence logique conservée ; pas de conclusion d'underrun basée seulement sur un compteur de file vide. |
| Plusieurs changements de scène et de forme | Occupation heap/linear examinée ; pas de croissance inexpliquée à cycle comparable. |
| Sauvegardes sur support de test avec récupération | Ancien état récupérable après échec ; le protocole sûr reste à implémenter. |

Le fichier `sdmc:/3ds/2ship/resource-failure-crash26.log` reste une pièce déterminante pour le crash d'origine. Une absence de trace ne prouve pas une absence d'erreur : le budget peut être consommé ou l'écriture SD échouer.

## 7. Vérifications d'API externes, distinctes de l'audit du projet

Les faits de code ci-dessus viennent de l'archive fournie. Des sources primaires externes ont seulement servi à vérifier des contrats d'API : devkitPro/libctru (`svc.h` pour le retour `Result`, `synchronization.c` pour `LightLock`), devkitPro/citro3d (`renderqueue.c` pour la synchronisation de queue), documentation officielle libzip (`zip_fread`, `zip_stat`). Elles ne prouvent pas la version exacte de ces dépendances sur le PC ou la console de l'utilisateur et ne remplacent pas les tests du binaire.
