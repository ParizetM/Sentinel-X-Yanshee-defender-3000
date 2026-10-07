# Sentinel-X — Geste Mème "6 - 7" (Six-Seven / La Balance)

Reproduit la fameuse danse/balance virale **« 6 - 7 »** :
1. Le robot lève les deux avant-bras paumes vers le ciel à l'horizontale.
2. Il balance alternativement la main gauche en l'air (**"SIX"**), puis la main droite (**"SEVEN"**), en inclinant la tête au rythme de la cadence.
3. Répète le mouvement sur plusieurs cycles puis revient en position neutre.

---

## 1. Exécution

### Depuis le Mac en 1 commande :
```bash
ssh sentinel "/home/pi/run_six_seven.sh"
```
*(Faites `Ctrl + C` à tout moment pour interrompre).*

---

## 2. Personnalisation (`.env`)

* `GESTURE_REPEAT=4` : Nombre de cycles 6-7 (par défaut 4).
* `GESTURE_SPEED_MS=450` : Vitesse de bascule entre chaque bras en millisecondes.
