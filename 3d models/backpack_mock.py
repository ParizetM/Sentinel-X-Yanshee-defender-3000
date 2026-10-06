"""
Backpack ESP8266 - MOCK paramétrique pour Fusion 360 (Mac)
Génère : une base (boîte ouverte) + un couvercle à lèvre, posé à côté.
Tout est en millimètres. Modifie uniquement la section PARAMETRES.

Vue de face (couvercle vu de l'extérieur), breadboard à la verticale :

        +---------------------+
        |              (O)    |  <- passage câble capteur de présence (haut droite)
        |                     |
        |     breadboard      |
        |                     |
        |      [ OLED ]       |  <- fenêtre OLED (bas, centre)
        +---------------------+
"""
import adsk.core, adsk.fusion, traceback

# ======================= PARAMETRES (mm) =======================
# Intérieur : espace utile pour breadboard + ESP8266 + fils
INNER_W = 70.0      # largeur intérieure (breadboard demi-taille = 55 mm + marge)
INNER_H = 100.0     # hauteur intérieure (breadboard demi-taille = 82 mm + marge)
INNER_D = 32.0      # profondeur intérieure (breadboard + ESP + fils)
WALL = 2.5          # épaisseur des parois

# Couvercle
LIP_H = 4.0         # hauteur de la lèvre qui rentre dans la base
LIP_T = 1.6         # épaisseur de la lèvre
TOL = 0.3           # jeu d'ajustement (par côté)
LID_GAP = 15.0      # écart entre base et couvercle sur le plan de travail

# Fenêtre OLED (bas, centrée)
OLED_W = 26.0
OLED_H = 15.0
OLED_MARGIN_BOTTOM = 8.0   # distance entre bord intérieur bas et le bas de la fenêtre

# Passage du capteur de présence (haut, à droite)
SENSOR_D = 10.0            # diamètre du trou (câble/connecteur du capteur)
SENSOR_MARGIN_RIGHT = 12.0 # distance centre du trou -> bord intérieur droit
SENSOR_MARGIN_TOP = 12.0   # distance centre du trou -> bord intérieur haut
# ===============================================================

MM = 0.1  # Fusion travaille en cm en interne


def P(x, y, z=0.0):
    return adsk.core.Point3D.create(x * MM, y * MM, z * MM)


def V(v):
    return adsk.core.ValueInput.createByReal(v * MM)


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        design = adsk.fusion.Design.cast(app.activeProduct)
        root = design.rootComponent
        extrudes = root.features.extrudeFeatures

        OUT_W = INNER_W + 2 * WALL
        OUT_H = INNER_H + 2 * WALL
        TOTAL_D = INNER_D + WALL

        def offset_plane(z):
            pin = root.constructionPlanes.createInput()
            pin.setByOffset(root.xYConstructionPlane, V(z))
            return root.constructionPlanes.add(pin)

        # ------------------------- BASE -------------------------
        sk = root.sketches.add(root.xYConstructionPlane)
        sk.sketchCurves.sketchLines.addCenterPointRectangle(P(0, 0), P(OUT_W / 2, OUT_H / 2))
        inp = extrudes.createInput(sk.profiles.item(0), adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        inp.setDistanceExtent(False, V(TOTAL_D))
        base = extrudes.add(inp).bodies.item(0)
        base.name = "Backpack_Base"

        # cavité (ouverte vers le haut)
        sk = root.sketches.add(offset_plane(WALL))
        sk.sketchCurves.sketchLines.addCenterPointRectangle(P(0, 0), P(INNER_W / 2, INNER_H / 2))
        inp = extrudes.createInput(sk.profiles.item(0), adsk.fusion.FeatureOperations.CutFeatureOperation)
        inp.setDistanceExtent(False, V(INNER_D))
        extrudes.add(inp)

        # ------------------------ COUVERCLE ------------------------
        lx = OUT_W + LID_GAP   # centre X du couvercle

        # plaque
        sk = root.sketches.add(root.xYConstructionPlane)
        sk.sketchCurves.sketchLines.addCenterPointRectangle(P(lx, 0), P(lx + OUT_W / 2, OUT_H / 2))
        inp = extrudes.createInput(sk.profiles.item(0), adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        inp.setDistanceExtent(False, V(WALL))
        lid = extrudes.add(inp).bodies.item(0)
        lid.name = "Backpack_Couvercle"

        # trous : OLED (bas centre) + capteur (haut droite)
        sk = root.sketches.add(root.xYConstructionPlane)
        oled_cy = -INNER_H / 2 + OLED_MARGIN_BOTTOM + OLED_H / 2
        sk.sketchCurves.sketchLines.addCenterPointRectangle(
            P(lx, oled_cy), P(lx + OLED_W / 2, oled_cy + OLED_H / 2))
        sx = lx + INNER_W / 2 - SENSOR_MARGIN_RIGHT
        sy = INNER_H / 2 - SENSOR_MARGIN_TOP
        sk.sketchCurves.sketchCircles.addByCenterRadius(P(sx, sy), SENSOR_D / 2 * MM)

        profs = adsk.core.ObjectCollection.create()
        for i in range(sk.profiles.count):
            profs.add(sk.profiles.item(i))
        inp = extrudes.createInput(profs, adsk.fusion.FeatureOperations.CutFeatureOperation)
        inp.setDistanceExtent(False, V(WALL))
        extrudes.add(inp)

        # lèvre (anneau) sous la plaque
        sk = root.sketches.add(root.xYConstructionPlane)
        lw = INNER_W - 2 * TOL
        lh = INNER_H - 2 * TOL
        sk.sketchCurves.sketchLines.addCenterPointRectangle(P(lx, 0), P(lx + lw / 2, lh / 2))
        sk.sketchCurves.sketchLines.addCenterPointRectangle(
            P(lx, 0), P(lx + (lw - 2 * LIP_T) / 2, (lh - 2 * LIP_T) / 2))
        ring = None
        best = -1
        for i in range(sk.profiles.count):
            a = sk.profiles.item(i).areaProperties().area
            if a > best:
                best, ring = a, sk.profiles.item(i)
        inp = extrudes.createInput(ring, adsk.fusion.FeatureOperations.JoinFeatureOperation)
        inp.setDistanceExtent(False, V(-LIP_H))
        extrudes.add(inp)

        app.activeViewport.fit()
        ui.messageBox("Mock généré : base + couvercle.\nAjuste les cotes en haut du script puis relance-le.")

    except:
        if ui:
            ui.messageBox("Erreur :\n{}".format(traceback.format_exc()))
