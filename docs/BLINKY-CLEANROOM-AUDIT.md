# Revue de provenance Blinky 07

Le périmètre est le portage natif local, ses adaptations MM/LUS, ses scripts
et ses tests. Les adaptations historiques encore ouvertes en 06 ont fait
l'objet de trois revues par fichier : MM, LibUltraShip et outils locaux.
Les différences restent attribuées séparément de leur base officielle.

BLINKY-REVIEWED-DELTAS.json enregistre ces preuves. Le script
scripts/audit_blinky_provenance.py vérifie les empreintes finales et les
références amont ; une preuve périmée ne permet pas de reclasser silencieusement
un fichier. Le CSV et le résumé JSON donnent le résultat de ce contrôle.

| Ensemble | Traitement |
| --- | --- |
| Fenêtre, renderer, runtime, HID, NDSP, lifecycle, O2R | Modules Blinky conservés et testés ; rendu GPU étendu en 07 |
| MM BenPort, heaps, messages et ponts de ressources | Audio, résidence, pinning et contrôles mémoire réimplémentés ; base MM attribuée |
| LUS CVar, messages libultra, logger, backend et ressources | Réécriture ou restauration amont avec adaptations isolées |
| Types, signatures, enums et CMake publics | Contrats MM/LUS/SDK attribués, sans revendication d'invention Blinky |
| Construction, packaging et contrôles locaux | Implémentations remplacées, formats et régressions contrôlés |
| Tests utiles | Conservés, portés ou réécrits ; fixtures et extraits amont attribués |
| Fichiers des anciens backends | Retirés ; liste et sauvegarde avant application |

Classification : A = création Blinky ; B = LUS amont ; C = MM amont ;
D = contrat public ; B+A/C+A = base amont et delta Blinky ; B+D/C+D = base
amont et adaptation d'interface ; E/F = origine héritée ou restant à établir.
Un retrait ne transforme pas son ancien contenu en code original.
Les dépendances vendor hors MM/LUS conservent leurs crédits dans THIRD-PARTY.md.

Le dossier local fourni est la source de travail. Le GitHub personnel de
l'utilisateur n'est pas utilisé. L'alpha 3 de 999sian sert à la comparaison ;
aucun de ses composants natifs n'est importé dans les nouvelles implémentations.
Des fichiers hérités ont été lus : il ne s'agit pas d'une clean-room juridique
avec équipes séparées. Ni une différence de hash ni cette revue ne certifient
une originalité mondiale de chaque ligne.

**MM, LibUltraShip et le SDK restent du code tiers. Le source complet n'est
donc pas « 100 % écrit par Blinky ».** Le travail réalisé concerne la réécriture
et l'attribution des adaptations natives examinées. Les résultats matériels
de 07 restent à obtenir ; les photos de 06 ne les remplacent pas.

Références : MM 6bfd6a35a0e0d8900273e61ce85cb038d4f4a528 ; LUS
7f9b86a593c526fc42261d7fe197100cecf57178 ; alpha 3
af3a7e80208e5eff755704d3ae5f5a25a6b7ed6e. L'arbre fourni n'a pas
d'historique .git : ces pins identifient les bases comparées.

## Correction de la revue fonctionnelle en 08

L'égalité amont de MenuTypes.h en 07 était exacte, mais sa restauration avait
supprimé un raccord public nécessaire à l'initialisation du menu natif.
L'écran noir est reproduit par un test du vrai code de menu. Le correctif08
rétablit cette entrée et classe le fichier C+D. Les preuves07 restent conservées
comme historique ; docs/provenance08 documente la correction. Une attribution
correcte ne constitue pas une preuve de fonctionnement.
