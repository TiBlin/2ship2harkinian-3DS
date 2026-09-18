# Inspection avant implementation — prototype 12

Base inspectee : Blinky 11, limite de presentation a 20 FPS.
Ce document est etabli avant modification des chemins de rendu.

## Chemin reel

| Niveau | Fichier / fonctions | Observations |
| --- | --- | --- |
| Monde | `third_party/2ship/mm/src/code/z_play.c`, `Play_DrawMain` | `Scene_Draw`, salle courante et precedente, puis acteurs. Les commandes OPA et XLU sont construites separement ; leur emission CPU ne signifie pas execution immediate. |
| Salles | `third_party/2ship/mm/src/code/z_room.c`, `Room_Draw`, `Room_DrawNormal`, `Room_DrawCullable` | Lots `entry->opa` et `entry->xlu`. Les salles cullables trient deja OPA du proche au lointain et XLU en sens inverse. Certaines salles contournent ce tri. |
| Acteurs | `third_party/2ship/mm/src/code/z_actor.c`, `Actor_DrawAll`, `Actor_Draw` | Test de volume/distance, flags d'exemption, lentille. Le dessin appelle aussi des hooks, des mises a jour d'interpolation et des ombres ; ne pas court-circuiter ces callbacks. |
| Liaison | `third_party/2ship/mm/2s2h/BenPort.cpp`, `Graph_ProcessGfxCommands` | Transmet les display lists a LUS et gere l'interpolation. Ne pas modifier cette cadence ni l'audio. |
| Interpretation | `third_party/libultraship/src/fast/interpreter.cpp`, `Run`, `GfxSpVertex`, `GfxSpTri1`, `Flush` | Transforme, eclaire, rejette des triangles, interprete tous les changements d'etat, regroupe les triangles compatibles, puis appelle `DrawTriangles`. |
| Blinky | `src/blinky/gfx_blinky_citro3d.cpp`, `DrawTriangles`, `Hardware`, `Reference`, `FlushHardwareBatch`, `DrawPacked` | Un appel LUS peut produire plusieurs soumissions GPU, notamment deux passes pour les contours alpha. Le chemin CPU peut lire/copier les framebuffers et rasteriser. |
| GPU | `DrawPacked`, `FlushHardwareBatch` | Deux sites `C3D_DrawArrays`. Aucun `C3D_DrawElements` dans ce backend. Presentation par un quad additionnel. |

## Rejets existants et limites des donnees

- Salle : seuls les rooms actifs sont soumis ; le changement de room est deja gere. Pas de graphe de portails oublie identifie dans le chemin inspecte.
- Geometrie statique : `Room_DrawCullable` teste le rayon de sphere contre les limites proche/lointaine. Ce n'est pas une preuve de couverture opaque a l'ecran.
- Acteurs : `Actor_CullingVolumeTest` et `Ship_CalcShouldDrawAndUpdate` gerent frustum et distance, avec options grand ecran/distance. Les volumes sont des volumes d'activation parametrables, pas des boites garanties de tous les pixels dessines.
- Triangles : `GfxSpTri1` rejette un plan commun hors champ et execute le back-face culling N64. Blinky desactive ensuite le culling PICA pour ne pas le dupliquer.
- `gfx_cull_dl_handler_f3dex2` est encore un TODO. Il s'agit d'un rejet de display list, pas d'une occlusion existante. L'activer sans audit des listes/mods serait une modification distincte du comportement OFF ; ce prototype ne le remplace pas silencieusement.
- Profondeur : Blinky utilise un D16 inverse sur PICA et un chemin CPU correspondant. Le nouveau systeme doit conserver ces tests et n'utiliser que des bornes prudemment arrondies.
- Stereo : le backend actuel appelle `gfxSet3D(false)` et ne cree qu'une sortie gauche. Il est mono. Un futur mode stereo ne doit jamais reutiliser implicitement une preuve mono.

## Point d'insertion retenu

Le premier prototype vise les **lots opaques statiques deja formes par LUS**,
a l'entree de `Blinky::DrawTriangles`, avant le decodage de sommets Blinky,
le choix GPU/CPU, les copies de reference et les soumissions Citro3D.
De petits marqueurs natifs delimitent les salles normales/cullables dans
le flux de commandes ; la construction des display lists et tous leurs
changements d'etat continuent de s'executer. Les marqueurs doivent vider
le lot LUS precedent avant de changer sa categorie.

C'est plus bas qu'un rejet de salle entiere, mais c'est le premier point
ou l'on dispose simultanement de la geometrie effectivement transformee,
du framebuffer, du viewport, du mode Z et du materiau definitif. Sauter une
display list de salle complete pourrait supprimer un changement de segment,
de matrice ou de materiau utilise par une liste suivante. Une sphere ou un
rectangle de batiment ne prouve pas non plus que les portes/trous sont opaques.

Les bornes candidates proviendront des positions clip du lot deja transforme,
sans inversion de matrice ni nouvelle transformation de sommets. Ce premier
palier economise le travail Blinky/GPU ; il n'economise pas la transformation
LUS et ne pretend pas supprimer un acteur complet. Les compteurs doivent
nommer explicitement cette unite : **lot de dessin**, pas objet de gameplay.

## Prototype et garde-fous prevus

- Grille fixe 50 x 30, profondeur uint16, 3 000 octets ; aucune allocation par test.
- Une cellule n'est remplie que si un triangle opaque reel couvre son rectangle entier, avec marge de couverture. Ne jamais remplir une boite d'occluder.
- Borne de profondeur eloignee pour l'occluder, proche pour tout le lot candidat ; arrondis opposes et marge D16. Convention logique proche=0, loin=1, distincte du stockage PICA inverse.
- Seulement triangles GPU opaques de salles, Z compare/ecrit, sans alpha-test, melange, decal, profondeur primitive, masque ou feedback. Un echec de classement ou de projection conserve le dessin.
- Pas de clipping logiciel complexe : plans proche/lointain traverses, W ambigu, bord d'ecran ou projection non finie => dessin/non-enregistrement.
- Budgets fixes de lots, triangles et visites de cellules. Budget epuise => dessin.
- Effacement a chaque image et invalidation sur changement de cible/viewport, effacement Z ou ecriture Z non monotone. Aucune visibilite historique.
- Pour une projection stereo connue : deux preuves independantes, puis AND. Dans le backend mono actuel, si un mode 3D inattendu est actif, conserver tous les dessins.
- Aucun culling d'acteurs, aucun changement de simulation/audio/assets, limite de 20 FPS conservee.

## Mesure avant conclusion

Le journal 09 conserve indique 1,57 % de triangles CPU sur une sequence,
mais ne mesure ni leur surface ni leur temps. Ce pourcentage ne demontre
pas que le GPU est le goulot d'etranglement.

Separer appels LUS, soumissions PICA, triangles/vertices PICA (y compris
passes supplementaires), raster CPU, copies/fences, temps backend, temps
des tests/enregistrement d'occlusion et temps total d'image. Compter a part
callbacks acteurs, rejets de volume acteurs et listes de salle emises.
Les compteurs de construction de scene portent sur le tick MM courant ;
les compteurs renderer portent sur l'image presentee. La derniere duree
de queue Citro3D est un echantillon de queue, pas le temps GPU de l'image.

Reference SDK pour ce dernier point :
[Citro3D renderqueue.c, version 1.7.1](https://github.com/devkitPro/citro3d/blob/v1.7.1/source/renderqueue.c).
Les mesures A/B sur console devront conclure au benefice ou au surcout.
