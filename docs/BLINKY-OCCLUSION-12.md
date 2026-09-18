# Blinky 12 — prototype conservateur d'occlusion

Le prototype rejette des **lots opaques statiques LUS entiers** avant le travail
Blinky/Citro3D. Il ne saute aucun callback d'acteur, aucune display list contenant
des changements d'etat, ni aucune transformation deja effectuee par LUS.
Le plafond reste a **20 FPS**. Le culling est **OFF par defaut**.

## Inspection et insertion

Voir `BLINKY-OCCLUSION-PIPELINE.md`, redige avant les modifications : les salles
actives, le tri proche-lointain OPA de `Room_DrawCullable`, les tests de volume et
distance des acteurs, les rejets de triangles LUS et le depth test PICA existaient
deja. Aucun graphe de portails ignore exploitable n'a ete identifie.

`Room_Draw` emet de petits NOOP natifs de categorie autour des salles normales et
cullables. Le handler LUS vide son lot avant de changer de categorie. Le test est
dans `GfxRenderingAPIBlinkyCitro3D::DrawTriangles`, apres validation du shader et
des textures, avant decodage Blinky, `Hardware`, `Reference` et `C3D_DrawArrays`.
L'unite rejetee est un lot de triangles compatibles, **pas une salle ou un acteur**.
Cette limite evite de supprimer les effets des commandes de display list et
d'utiliser les spheres d'activation du jeu comme des bornes graphiques exactes.

## Algorithme et cout

- Grille **50 x 30**, soit 1 500 profondeurs `uint16_t` : **3 000 octets**.
  Objet complet avec budgets et marges : **3 044 octets**. Les statistiques
  optionnelles ajoutent environ 172 octets globaux. Pas d'allocation par test.
- Profondeur logique proche=0, loin=1 ; le depth buffer PICA D16 inverse reste
  actif et inchange. Aucune lecture de profondeur GPU pour alimenter la grille.
- Un occluder est un triangle reel accepte par le chemin GPU, sans subdivision.
  Une cellule est valide seulement si **tout son rectangle, agrandi d'un pixel**,
  est strictement dans ce triangle. Les trous et les diagonales non prouvees
  restent inconnus ; deux demi-cellules ne sont pas fusionnees arbitrairement.
- La profondeur enregistree est le maximum des profondeurs des trois sommets,
  arrondi vers le lointain et augmente de 32 unites D16. Un triangle qui echoue
  au depth test ne compromet pas la preuve : la profondeur existante est alors
  au moins aussi proche, tant que les ecritures restent monotones.
- Candidat : au moins huit triangles. Une seule passe sur toutes les positions
  clip deja transformees produit le rectangle englobant et la profondeur la plus
  proche. Rectangle dilate d'un pixel, cellules arrondies vers l'exterieur,
  profondeur arrondie vers le proche puis diminuee de 32 unites. **Chaque cellule**
  doit prouver une profondeur strictement devant cette borne, sinon DRAW.
- NaN/infini, W negatif/trop petit/trop grand, plan proche/lointain ou bord d'ecran
  traverse, viewport partiel, scissor insuffisant, cible sans Z : DRAW.
  Pas de clipping logiciel complexe, d'inversion de matrice ou d'historique.
- Cout : O(V + cellules du rectangle) par test ; enregistrement O(cellules du
  rectangle du triangle), avec trois fonctions de bord par cellule. Budgets par
  image : **128 tests, 32 768 sommets examines, 8 192 cellules interrogees,
  256 tentatives d'occluder, 8 192 cellules d'enregistrement**. Epuisement => DRAW.
  Une invalidation efface au plus 3 Ko et ne recharge pas les budgets.

Effacement a chaque image. Invalidation sur changement de cible/viewport,
redimensionnement/inversion de la cible active, effacement Z global/partiel,
ecriture Z sans comparaison, ou activation 3D inattendue. Les copies/effacements
de couleur seuls ne changent pas Z et conservent sa preuve, comme le rendu OFF.

## Geometrie autorisee et exclusions

Occluders : triangles suffisamment grands des lots **room OPA normaux/cullables**,
dessines par `Hardware`, avec Z compare/ecrit, viewport complet et scissor le
couvrant. Un mur, batiment, rocher ou terrain peut contribuer si ses triangles
respectent ces conditions. La texture opaque ordinaire et le brouillard sont
admis ; la geometrie reelle, et non sa boite, fournit la couverture.

Exclus : XLU, acteurs, effets, sprites hors salles, fonds de rooms IMAGE,
melange alpha, alpha-test/cutout, bruit/invisibilite/grayscale, masques, textures
de framebuffer, profondeur primitive, decal, shaders personnalises, triangles
CPU, triangles subdivises, petits triangles et projections incertaines.
Une animation ne peut fournir aucune preuve historique : seule la geometrie
effective du lot statique courant est examinee.

Le backend actuel force le **mono**. Si `gfxIs3D()` devient vrai, tous les lots
restent dessines et la grille est invalidee. Le noyau fournit aussi
`HiddenStereo(left, right, ...)`, teste avec deux preuves independantes et AND ;
il n'est pas branche sur un renderer stereo inexistant. Une future integration
stereo devra alimenter deux grilles avec les vrais occluders de chaque oeil.

## Fichiers et fonctions

| Fichiers modifies/ajoutes | Fonctions ou responsabilite |
| --- | --- |
| `src/blinky/coarse_occlusion.h` | `BeginFrame`, `Invalidate`, `Configure`, `Project`, `Hidden`, `HiddenBounds`, `HiddenStereo`, `RegisterTriangle` |
| `src/blinky/gfx_blinky_citro3d.cpp` | `OcclusionEligible`, `InvalidateOcclusion`, `OcclusionReport`; insertion et compteurs GPU/copies/attentes |
| `src/blinky/visibility_bridge.cpp` et `third_party/libultraship/include/ship/port/3ds/BlinkyVisibility.h` | `BlinkyVisibilityScope/GetScope`, `GameBegin/End`, `InterpretBegin/End`, `FrameBegin/End`, compteurs et timer optionnels |
| `third_party/libultraship/src/fast/interpreter.cpp` | NOOP natif, Flush avant changement de categorie, bornes de mesure |
| `third_party/2ship/mm/src/code/z_room.c` | categories des salles et compteurs de listes/rejets existants |
| `third_party/2ship/mm/src/code/z_actor.c`, `z_play.c` | compteurs des callbacks/rejets existants et temps de construction ; logique de jeu preservee |
| `src/blinky/native_input.cpp`, `native_runtime.cpp` | marqueur 12, diagnostic OFF/ON, lots/triangles evites, temps et soumissions GPU |
| `CMakeLists.txt`, `build.py` | trois options independantes, compatibilite avec la chaine existante |
| `scripts/verify_port.py`, `tests/test_blinky_occlusion.py`, `tests/blinky/occlusion.cpp` | ajout des regressions du noyau |
| `tests/test_blinky_renderer.py`, `tests/blinky/graphics/{renderer.cpp,occlusion.inc,3ds.h,citro3d.h}` | quatre combinaisons de flags, vrais appels du backend et collaborateurs host |
| `scripts/summarize_blinky_visibility.py` | mediane, p95 et moyenne des images echantillonnees du journal |

Les fichiers de provenance et ces documents accompagnent les changements ;
l'inventaire et le patch livres donnent la liste exacte. Les attributions
MM/LUS sont conservees. Aucune implementation d'occlusion externe n'est importee.

## Compilation A/B

Depuis la racine, avec la meme version de devkitPro :

```text
python build.py --occlusion off --render-stats --output dist-off
python build.py --occlusion on  --render-stats --output dist-on
```

Les deux produisent les formats existants `.3dsx`, `.cia`, `.3ds` et l'ELF associe.
Les options CMake correspondantes sont `BLINKY_OCCLUSION_CULLING`,
`BLINKY_RENDER_STATS`, `BLINKY_OCCLUSION_DEBUG`. Sans `--render-stats`, les compteurs
de profilage et les lectures de temps sont compiles hors du chemin. Sans
occlusion, aucun tag de salle n'est emis sauf si les statistiques sont demandees.
`--occlusion-debug` avec ON ecrit une petite image PGM tous les 120 frames : noir
inconnu, clair proche. Cette sortie disque est OFF dans les deux builds A/B.

## Validation et limites

21 programmes de regression host passent. Le renderer est compile/teste en
OFF sans stats, OFF avec stats, ON avec stats/debug et ON sans stats. Les tests
comptent les vrais appels du backend a `C3D_DrawArrays` via ses collaborateurs,
et conservent les 5 537 controles d'orientation existants.

Les dix cas demandes sont couverts : visible, partiel, cache, depassement,
plan proche, W proche/derriere la camera, transparent non-occluder, visible dans
un oeil, cache dans les deux, et OFF. S'ajoutent egalite Z, valeurs non finies,
budgets, cible inverse/offscreen, scissor, Z clear, nouvelle image et acteurs.
L'oracle geometrique independant verifie **257 744 coins de cellules** et
**711 rejets aleatoires** sur 1 000 triangles avec profondeur/perspective variables.
Le cas synthetique cache supprime un appel contenant huit triangles ; OFF le soumet.

Ces tests ne remplacent pas une validation PICA reelle. Les marges de couverture
et de profondeur sont prudentes, mais la precision/rasterisation du GPU et les
scenes du jeu doivent encore etre verifiees sur console. Le compromis attendu
est beaucoup de faux negatifs, notamment aux diagonales, bords d'ecran et pour
les lots tres disperses. Le gain peut etre **nul ou negatif** si les lots caches
sont rares ou si les transformations LUS dominent. Aucun gain FPS mesure sur
New 3DS n'est revendique pour cette version.

## Mesures sur console

Les deux builds utilisent le meme plafond de 20 FPS et les memes statistiques.
Tester la meme sauvegarde, position, camera et filtre : Clock Town, interieur,
grande zone ouverte, puis portes, transitions, camera collee aux murs, effets
transparents et mouvement rapide. Alterner OFF/ON sur trois parcours comparables
apres echauffement. Verifier les images pendant les mouvements, pas seulement
les chiffres. La carte SD n'etait pas montee pendant la livraison.

L'ecran inferieur affiche tests/rejets, triangles et appels LUS evites, temps
d'occlusion et appels GPU. `blinky.log` contient `Blinky visibility:` tous les
120 frames : **un frame echantillonne**, pas une moyenne sur 120 frames.

| Mesure | Interpretation |
| --- | --- |
| `frame_ms` | intervalle entre presentations, jeu/audio/limiteur inclus ; 50 ms correspond au plafond 20 FPS |
| `build_ms`, `interpreter_ms`, `backend_ms` | construction MM, interpretation LUS, travail Blinky ; durées inclusives, ne pas les additionner |
| `reference_ms`, `cpu_tris`, `copies`, `copy_bytes`, `fence_ms` | cout possible du chemin CPU et de ses synchronisations |
| `gpu_calls`, `gpu_tris`, `gpu_vertices`, `command_splits` | charge reellement soumise, passes supplementaires et quad final compris |
| `room_calls`, `room_lists`, `actor_callbacks` | lots opaques de salle, listes emises, callbacks acteurs executes |
| `actor_volume_rejected`, `room_depth_rejected` | rejets existants de volume/distance et de profondeur, pas de nouveaux rejets d'acteurs |
| `eligible`, `tested`, `rejected`, `avoided_lus_calls`, `avoided_tris` | efficacite du prototype ; un appel LUS peut produire plusieurs appels GPU, donc ce n'est pas un compte exact d'appels PICA evites |
| `occ_ms`, `occluders`, `cells`, `budget_stops`, `invalidations` | cout tests/enregistrement/effacements et validite/utilite de la grille |
| `gpu_last_queue_ms`, `command_last_queue_ms` | dernier echantillon de queue Citro3D ; **pas le temps GPU total du frame** |

Pour comparer deux journaux copies dans des fichiers distincts :

```text
python scripts/summarize_blinky_visibility.py off.log on.log
```

Comparer mediane et p95 de `frame_ms`, puis le travail GPU/CPU retire au cout
`occ_ms`. Une forte duree `reference_ms`/copies suggere le raster CPU ; une forte
charge commandes/soumissions avec peu de triangles suggere le cout des appels ;
les temps de queue et sommets orientent vers le GPU sans distinguer a eux seuls
vertex et fragment. Un test de camera/scene a charge geometrique comparable et
surfaces couvertes differentes est necessaire pour affiner cette distinction.
Si ON est plus lent, garder OFF et fournir les journaux pour cibler le cout reel.
