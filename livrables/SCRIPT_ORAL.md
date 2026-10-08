# Script de l'oral · Sentinel-X · Groupe 7

Support : la présentation `pres.pptx` du dépôt. **10 min d'oral** chronométrées (introduction, teaser, démo, pitch), puis **15 min de questions** du jury, à part.

| Temps | Partie | Diapos | Qui parle |
|---|---|---|---|
| 0:00 – 1:00 | Mise en scène, contexte, variante d'architecture | 1 à 3 | tous, puis Felis, puis Elios |
| 1:00 – 2:00 | Teaser | 4 | (vidéo) |
| 2:00 – 5:00 | Démo live | 5 | Martin au clavier, Matis raconte, Elios et Benoit pour les preuves de sécurité |
| 5:00 – 9:30 | Pitch technique | 6 à 13 | chacun sa partie |
| 9:30 – 10:00 | Conclusion, puis marge de sécurité | 14 | Felis |
| après | Questions du jury (15 min) | — | celui dont c'est le domaine répond |

**Le mail des coachs l'exige : chaque membre doit prendre la parole.** La répartition ci-dessous est une proposition : échangez les diapos selon qui a réellement fait quoi, le jury pose ses questions à celui qui a présenté. Le texte entre guillemets est à dire à peu près tel quel, le reste ce sont des indications. Ne lisez pas : c'est un guide.

| Membre | Prend la parole sur |
|---|---|
| Elios | Variante d'architecture (3), preuve Wireshark (démo), sécurité (11) |
| Benoit | Preuve du durcissement (démo), infrastructure (10), audit et pentest (12) |
| Felis | Contexte (2), boîtier (6), conclusion (14) |
| Martin | Pilote de la démo, IA de vision (7), méthode d'équipe (13) |
| Matis | Narration de la démo, IA prédictive (8 et 9) |

---

## Avant d'entrer (checklist 10 min avant)

- [ ] Boîtier alimenté depuis **plus de 60 s** (chauffe du gaz) et **plus de 30 s** (calibration du PIR). L'OLED affiche `MQTT: connecte`.
- [ ] `anomaly_service.py` lancé depuis **plus de 60 s** (il lui faut 60 s d'historique).
- [ ] Le dashboard est ouvert, les courbes bougent, la jauge IA est sous 1.
- [ ] Le robot est allumé, YOLO tourne sur la VM IA, le flux s'affiche.
- [ ] Wireshark est ouvert, filtré sur `tcp.port == 8883`.
- [ ] Un terminal SSH est ouvert sur une VM, avec `sudo ufw status verbose` prêt à lancer.
- [ ] Le teaser est prêt en plein écran.
- [ ] La source de chaleur est prête (sèche-cheveux à distance, ou la main), ainsi que le gel hydroalcoolique.
- [ ] **Plan B** prêt dans un terminal : `python prediction_ia/simulate.py --scenario demo --minutes 20 --onset 120 --publish --speed 5`

---

## Diapo 1 · Titre (0:00 – 0:25) · tous

Le mail demande de « bien introduire et de se mettre en scène ». Jouez le consortium d'ingénieurs qui livre son produit à AetherCorp.

> Felis : « Mesdames et messieurs de la direction d'AetherCorp, merci de nous recevoir. Nous sommes le consortium chargé de l'initiative Sentinel-X. »

Puis chacun dit son prénom et son rôle, en une phrase : Elios, Benoit (infrastructure), Martin, Matis (développement).

> Felis : « En 2050, vos micro-centrales isolées sont attaquées sur trois fronts à la fois. Aujourd'hui, nous vous livrons la réponse : **Sentinel-X**. »

## Diapo 2 · Trois menaces (0:25 – 0:40) · Felis

> « Trois menaces, une réponse pour chacune. L'intrusion physique : une IA de vision sur la caméra du robot Yanshee. La fuite de gaz ou la surchauffe : notre boîtier et une IA prédictive. La cyberattaque : du chiffrement partout et des serveurs durcis. Et surtout, tout est relié. »

## Diapo 3 · Variante d'architecture (0:40 – 1:00) · Elios

Le sujet l'exige dans la première minute.

> « Notre variante, c'est l'option B distribuée : le PC Serveur Local est réparti sur des machines virtuelles Proxmox, dans 4 VLAN. À la place de la webcam USB, on utilise la caméra du robot Yanshee, une variante validée par les coachs. »

Montrer les flèches rouges.

> « En rouge, tout ce qui est chiffré en TLS. Tout passe par le broker MQTT, sauf la vidéo, trop lourde. »

## Diapo 4 · Teaser (1:00 – 2:00)

> « Voici Sentinel Drop. »

Lancer la vidéo en plein écran. **Silence total pendant la lecture.**

## Diapo 5 · Démo live (2:00 – 5:00) · Martin au clavier, Matis raconte

Laisser la diapo 2 secondes, puis basculer sur le dashboard. Le narrateur parle, le pilote agit. Comptez environ 30 s par étape.

**1. Le boîtier vit.** Montrer l'OLED puis le dashboard.

> « Le boîtier affiche son IP et sa connexion au broker. Il publie chaque seconde : vous voyez les courbes bouger en direct. »

**2. Commande à distance.** Cliquer sur « Alerte totale ».

> « Un clic : la commande traverse l'API et le broker chiffré, et le boîtier sonne en moins d'une seconde. »

Puis « Arrêt d'urgence ».

**3. La dérive avant le seuil.** C'est **le moment clé** : lancez la chauffe dès le début de la démo, puisque l'IA met environ 1 à 2 min à réagir.

> « Pendant qu'on vous parlait, on chauffe doucement le capteur. Regardez l'OLED : il dit toujours "normal". Regardez la jauge IA : elle vient de passer au-dessus de 1, et l'alerte est tombée avec son diagnostic. L'IA voit la dérive bien avant le seuil critique. »

**4. L'intrus.** Une personne passe devant le robot.

> « Une présence humaine : YOLO la détecte, prend une photo de preuve qui arrive dans la galerie, lève une alerte d'intrusion… et le robot riposte. »

**5. Le chiffrement.** Elios prend la parole. Basculer sur Wireshark.

> « Voici le trafic MQTT capturé : c'est du TLS, totalement illisible. »

**6. Le durcissement.** Benoit prend la parole. Basculer sur le terminal et lancer `sudo ufw status verbose`.

> « Pare-feu actif, tout est fermé par défaut. Et une connexion SSH par mot de passe est refusée : on n'entre qu'avec une clé. »

**Si quelque chose plante**, ne vous excusez pas longtemps :

> « Le Wi-Fi de la salle nous lâche, on bascule sur notre démo de secours qui rejoue un vrai scénario. »

Puis lancer `simulate.py`.

## Diapo 6 · Le boîtier (5:00 – 5:35) · Felis

> « Le boîtier, c'est un ESP8266 programmé en C++ : température, humidité, gaz, présence, écran OLED, buzzer et LED. »

> « Trois choix qui comptent. Un : le MQTT est chiffré en TLS, et le certificat de notre autorité est embarqué dans la carte, donc le boîtier vérifie qu'il parle au vrai broker. Deux : s'il tombe, le broker publie automatiquement "offline". Trois : la boucle est non bloquante, donc les capteurs tournent même sans réseau. »

> « Et le boîtier ne décide jamais seul de sonner : c'est le centre de commandement qui décide. »

## Diapo 7 · IA de vision (5:35 – 6:10) · Martin

> « La caméra du robot envoie du 640 par 480 à 25 images par seconde, encodé par son propre GPU. YOLO26n, le modèle le plus léger de la famille, ne cherche qu'une classe : les personnes. »

> « Dès qu'il en voit une, il publie le nombre de personnes, une photo de preuve et l'ordre de riposte. La vidéo ne passe jamais par MQTT, sinon le broker saturerait : on limite à une photo toutes les 10 secondes. »

Si vous avez mesuré la latence, dites-la ici : « … en ___ millisecondes par image, sous les 100 demandées. »

## Diapo 8 · IA prédictive : les chiffres (6:10 – 6:55) · Matis

C'est **notre point fort**. Prenez le temps.

> « Le sujet interdit les `if temp > 40`. Et on a prouvé pourquoi : notre firmware a des seuils avec une référence qui s'adapte, mais une fuite lente se fait absorber par cette référence. Le firmware ne la voit **jamais**. »

> « Notre IA, c'est un Isolation Forest qui apprend le fonctionnement normal, plus un Random Forest qui pose le diagnostic. Un modèle par capteur. Résultat : on détecte une surchauffe lente 22 minutes avant le seuil critique, une fuite lente 9 minutes avant. Et seulement 0,15 fausse alerte par heure. »

## Diapo 9 · Le scénario (6:55 – 7:20) · Matis

Montrer le graphique avec le pointeur.

> « Ici le gaz monte à partir de 10 minutes. La référence du firmware le suit, en pointillés : il reste à "normal". En bas, notre indice de risque passe au-dessus de 1 vers 11 minutes. Et on l'a vérifié sur un vrai enregistrement de nos capteurs, que le modèle n'avait jamais vu. »

## Diapo 10 · Infrastructure (7:20 – 7:55) · Benoit

> « Côté infra, tout tourne sur Proxmox, en 4 VLAN : le web, la base de données, la supervision, l'automatisation. Un VLAN compromis ne donne pas accès aux autres. »

> « La base, c'est un cluster Galera de 3 nœuds. Pourquoi 3 ? Avec 2, si un nœud tombe, il n'y a plus de majorité et tout se bloque. Devant, une IP virtuelle HAProxy : l'API ne voit jamais un serveur isolé. Tout est supervisé par Zabbix et déployé par Ansible. »

## Diapo 11 · Sécurité (7:55 – 8:25) · Elios

> « Tout ce qui est sur cette diapo, on vient de vous le montrer en démo, ou on peut vous le montrer maintenant : TLS de bout en bout, HTTPS, pare-feu fermé par défaut, SSH par clé uniquement, réseau segmenté. Et aucun secret dans notre dépôt : tout passe par des fichiers d'environnement. »

## Diapo 12 · Audit et pentest (8:25 – 8:55) · Benoit

> « Avant le pentest, on s'est audités nous-mêmes : revue de code de toutes les briques, recherche de secrets, revue des ports et du TLS. Cinq correctifs appliqués dans la foulée, par exemple : le boîtier ne parle plus jamais en clair, et aucun service ne démarre sans ses secrets. »

Puis le bilan du pentest, **à compléter après l'après-midi** :

> « Pendant le pentest croisé, on a subi ___ attaques, dont ___ bloquées. »

## Diapo 13 · Équipe (8:55 – 9:20) · Martin

> « Notre risque numéro un, identifié lundi, c'était l'intégration. Alors on a figé dès le premier jour le contrat entre les briques : les topics MQTT, les formats JSON, les routes de l'API. C'est ce qui nous a permis d'avoir la chaîne complète dès mercredi. Une branche par brique, des pull requests, des tests automatisés. »

## Diapo 14 · Conclusion (9:20 – 9:40) · Felis

> « Sentinel-X, c'est trois choses : une chaîne chiffrée de bout en bout, une IA qui anticipe la panne, et une infrastructure qui encaisse les pannes. **Sentinel-X : la sécurité à la bordure.** Merci. Nous sommes à votre disposition pour vos questions. »

---

## Questions du jury (15 min, après l'oral)

Règle : **celui qui a présenté la partie répond**, les autres complètent seulement si besoin. Firmware et boîtier : Felis. Vision et robot : Martin. IA prédictive : Matis. Réseau, Galera, Zabbix, Ansible, audit et pentest : Benoit. TLS, pare-feu, SSH, architecture : Elios.

### Questions probables

| Question | Réponse courte |
|---|---|
| Pourquoi pas la webcam USB ? | Variante validée par les coachs : le robot apporte à la fois la caméra et une contre-mesure physique. L'encodage se fait sur son GPU, donc rien ne charge le serveur. |
| Comment prouvez-vous le chiffrement ? | Avec Wireshark, comme dans la démo. En plus, le firmware vérifie le certificat du broker avec notre CA embarqué : c'est authentifié, pas seulement chiffré. |
| Et si on vous attaque en homme du milieu ? | Tout le MQTT est en TLS. Le boîtier et l'IA de vision vérifient en plus le certificat du broker avec notre CA : ils refusent un faux broker. |
| Pourquoi un MQ-135 et pas un MQ-2 ? | Même principe, même brochage analogique. On mesure l'écart à l'air calme, pas une concentration absolue. |
| Vos données d'entraînement sont simulées ? | Le fonctionnement normal est simulé, mais calibré sur le bruit réel de nos capteurs, et nous l'avons validé sur un vrai enregistrement jamais vu. Prochaine étape : réentraîner sur une heure réelle dans la salle (`data_take.py`). |
| Pourquoi Isolation Forest et Random Forest ? | Le premier apprend uniquement le normal et repère n'importe quel incident, même inconnu. Le second nomme l'incident. L'un sans l'autre, on perdrait soit la détection de l'inconnu, soit le diagnostic. |
| La fuite brutale ? | Le firmware la voit 3 s avant l'IA : c'est voulu. Le firmware reste le premier rempart rapide, l'IA ajoute le diagnostic et le niveau critique. |
| Pourquoi 3 nœuds Galera ? | Pour le quorum : avec 2 nœuds, en perdre un bloque le cluster. |
| Que se passe-t-il si le broker tombe ? | Le boîtier, l'API et les IA se reconnectent seuls dès qu'il revient, et le Last Will signale le boîtier hors ligne. Évolution prévue : un cluster Mosquitto. |
| Pourquoi ne pas faire passer la vidéo par MQTT ? | 25 images par seconde satureraient le broker. Seuls les événements (compteur, photo toutes les 10 s) y transitent. |
| Et la suite ? | Un cluster Mosquitto pour la haute disponibilité du broker, le réentraînement de l'IA sur les données de la salle, des sauvegardes automatisées de la base. |
