# Script de l'oral · Sentinel-X · Groupe 7

Support : `Workshop2026-M1-G7-Pres.pptx`. Passage de 10 min, chronométré, coupé net si on dépasse.

| Temps | Partie | Diapos |
|---|---|---|
| 0:00 – 1:00 | Présentation de l'équipe et de la variante d'architecture | 1 à 3 |
| 1:00 – 2:00 | Teaser | 4 |
| 2:00 – 5:00 | Démo live | 5 |
| 5:00 – 10:00 | Pitch, le jury interrompt librement | 6 à 14 |

**Orateurs** : la répartition par pôle n'est qu'une proposition, adaptez-la à qui maîtrise quoi. Le texte entre guillemets est à dire à peu près tel quel ; le reste, ce sont des indications. Ne lisez pas, c'est un guide.

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

## Diapo 1 · Titre (0:00 – 0:25) · tout le monde

Chacun se présente en une phrase, en commençant par le pôle Infra.

> « Bonjour. Nous sommes le groupe 7. Elios et Benoit pour l'infrastructure, Felis, Martin et Matis pour le développement. »

> « AetherCorp perd des micro-centrales isolées, attaquées sur trois fronts à la fois. Notre réponse, c'est **Sentinel-X**. »

## Diapo 2 · Trois menaces (0:25 – 0:40) · Dev

> « Trois menaces, une réponse pour chacune. L'intrusion physique : une IA de vision sur la caméra du robot Yanshee. La fuite de gaz ou la surchauffe : notre boîtier et une IA prédictive. La cyberattaque : du chiffrement partout et des serveurs durcis. Et surtout, tout est relié. »

## Diapo 3 · Variante d'architecture (0:40 – 1:00) · Infra

Le sujet l'exige dans la première minute.

> « Notre variante, c'est l'option B distribuée : le PC Serveur Local est réparti sur des machines virtuelles Proxmox, dans 4 VLAN. À la place de la webcam USB, on utilise la caméra du robot Yanshee, une variante validée par les coachs. »

Montrer les flèches rouges.

> « En rouge, tout ce qui est chiffré en TLS. Tout passe par le broker MQTT, sauf la vidéo, trop lourde. »

## Diapo 4 · Teaser (1:00 – 2:00)

> « Voici Sentinel Drop. »

Lancer la vidéo en plein écran. **Silence total pendant la lecture.**

## Diapo 5 · Démo live (2:00 – 5:00) · un pilote au clavier, un narrateur

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

**5. Le chiffrement.** Basculer sur Wireshark.

> « Voici le trafic MQTT capturé : c'est du TLS, totalement illisible. »

**6. Le durcissement.** Basculer sur le terminal et lancer `sudo ufw status verbose`.

> « Pare-feu actif, tout est fermé par défaut. Et une connexion SSH par mot de passe est refusée : on n'entre qu'avec une clé. »

**Si quelque chose plante**, ne vous excusez pas longtemps :

> « Le Wi-Fi de la salle nous lâche, on bascule sur notre démo de secours qui rejoue un vrai scénario. »

Puis lancer `simulate.py`.

## Diapo 6 · Le boîtier (5:00 – 5:30) · Dev firmware

> « Le boîtier, c'est un ESP8266 programmé en C++ : température, humidité, gaz, présence, écran OLED, buzzer et LED. »

> « Trois choix qui comptent. Un : le MQTT est chiffré en TLS, et le certificat de notre autorité est embarqué dans la carte, donc le boîtier vérifie qu'il parle au vrai broker. Deux : s'il tombe, le broker publie automatiquement "offline". Trois : la boucle est non bloquante, donc les capteurs tournent même sans réseau. »

> « Et le boîtier ne décide jamais seul de sonner : c'est le centre de commandement qui décide. »

## Diapo 7 · IA de vision (5:30 – 6:00) · Dev IA vision

> « La caméra du robot envoie du 640 par 480 à 25 images par seconde, encodé par son propre GPU. YOLO26n, le modèle le plus léger de la famille, ne cherche qu'une classe : les personnes. »

> « Dès qu'il en voit une, il publie le nombre de personnes, une photo de preuve et l'ordre de riposte. La vidéo ne passe jamais par MQTT, sinon le broker saturerait : on limite à une photo toutes les 10 secondes. »

Si vous avez mesuré la latence, dites-la ici : « … en ___ millisecondes par image, sous les 100 demandées. »

## Diapo 8 · IA prédictive : les chiffres (6:00 – 6:40) · Dev IA prédictive

C'est **notre point fort**. Prenez le temps.

> « Le sujet interdit les `if temp > 40`. Et on a prouvé pourquoi : notre firmware a des seuils avec une référence qui s'adapte, mais une fuite lente se fait absorber par cette référence. Le firmware ne la voit **jamais**. »

> « Notre IA, c'est un Isolation Forest qui apprend le fonctionnement normal, plus un Random Forest qui pose le diagnostic. Un modèle par capteur. Résultat : on détecte une surchauffe lente 22 minutes avant le seuil critique, une fuite lente 9 minutes avant. Et seulement 0,15 fausse alerte par heure. »

## Diapo 9 · Le scénario (6:40 – 7:00) · même orateur

Montrer le graphique avec le pointeur.

> « Ici le gaz monte à partir de 10 minutes. La référence du firmware le suit, en pointillés : il reste à "normal". En bas, notre indice de risque passe au-dessus de 1 vers 11 minutes. Et on l'a vérifié sur un vrai enregistrement de nos capteurs, que le modèle n'avait jamais vu. »

## Diapo 10 · Infrastructure (7:00 – 7:30) · Infra

> « Côté infra, tout tourne sur Proxmox, en 4 VLAN : le web, la base de données, la supervision, l'automatisation. Un VLAN compromis ne donne pas accès aux autres. »

> « La base, c'est un cluster Galera de 3 nœuds. Pourquoi 3 ? Avec 2, si un nœud tombe, il n'y a plus de majorité et tout se bloque. Devant, une IP virtuelle HAProxy : l'API ne voit jamais un serveur isolé. Tout est supervisé par Zabbix et déployé par Ansible. »

## Diapo 11 · Sécurité (7:30 – 8:00) · Infra

> « Tout ce qui est marqué "en place", on vient de vous le montrer en démo, ou on peut vous le montrer maintenant : TLS, HTTPS, pare-feu, SSH par clé, segmentation. Les secrets ont été retirés du dépôt. »

> « Et on est transparents sur ce qui reste partiel : aujourd'hui, tous les clients partagent un même compte sur le broker. La prochaine étape, c'est un compte par client avec des droits par topic. »

## Diapo 12 · Audit et pentest (8:00 – 8:30) · Infra ou Dev

**À compléter après le pentest de cet après-midi.**

> « Avant le pentest, on s'est audités nous-mêmes : 11 constats, du critique au faible, tous dans le dossier avec leur correctif. »

Puis le bilan réel du pentest : « Cet après-midi, on a subi ___ attaques. ___ ont été bloquées. La faille exploitée était ___, et on l'a corrigée en ___. »

Si la faille critique (les routes de commande de l'API sans jeton) a été corrigée, dites-le. Si elle a été exploitée, assumez-le et expliquez le correctif : le jury valorise la lucidité.

## Diapo 13 · Équipe (8:30 – 8:50) · Dev

> « Notre risque numéro un, identifié lundi, c'était l'intégration. Alors on a figé dès le premier jour le contrat entre les briques : les topics MQTT, les formats JSON, les routes de l'API. C'est ce qui nous a permis d'avoir la chaîne complète dès mercredi. Une branche par brique, des pull requests, des tests automatisés. »

## Diapo 14 · Conclusion (8:50 – 9:00) · la personne qui a ouvert

> « Sentinel-X, c'est trois choses : une chaîne chiffrée de bout en bout, une IA qui anticipe la panne, et une infrastructure qui encaisse les pannes. **Sentinel-X : la sécurité à la bordure.** Merci, on attend vos questions. »

---

## Questions probables du jury

| Question | Réponse courte |
|---|---|
| Pourquoi pas la webcam USB ? | Variante validée par les coachs : le robot apporte à la fois la caméra et une contre-mesure physique. L'encodage se fait sur son GPU, donc rien ne charge le serveur. |
| Comment prouvez-vous le chiffrement ? | Avec Wireshark, comme dans la démo. En plus, le firmware vérifie le certificat du broker avec notre CA embarqué : c'est authentifié, pas seulement chiffré. |
| Et si on vous attaque en homme du milieu ? | Le boîtier et l'IA de vision vérifient le certificat, donc ils refusent un faux broker. Pour l'API et le robot, la vérification est le prochain correctif, et c'est noté dans l'audit. |
| Pourquoi un MQ-135 et pas un MQ-2 ? | Même principe, même brochage analogique. On mesure l'écart à l'air calme, pas une concentration absolue. |
| Vos données d'entraînement sont simulées ? | Le fonctionnement normal est simulé, mais calibré sur le bruit réel de nos capteurs, et nous l'avons validé sur un vrai enregistrement jamais vu. Prochaine étape : réentraîner sur une heure réelle dans la salle (`data_take.py`). |
| Pourquoi Isolation Forest et Random Forest ? | Le premier apprend uniquement le normal et repère n'importe quel incident, même inconnu. Le second nomme l'incident. L'un sans l'autre, on perdrait soit la détection de l'inconnu, soit le diagnostic. |
| La fuite brutale ? | Le firmware la voit 3 s avant l'IA : c'est voulu. Le firmware reste le premier rempart rapide, l'IA ajoute le diagnostic et le niveau critique. |
| Pourquoi 3 nœuds Galera ? | Pour le quorum : avec 2 nœuds, en perdre un bloque le cluster. |
| Que se passe-t-il si le broker tombe ? | C'est notre point de défaillance unique, identifié. Piste : un cluster Mosquitto. Le boîtier et les services se reconnectent seuls quand il revient. |
| Pourquoi ne pas faire passer la vidéo par MQTT ? | 25 images par seconde satureraient le broker. Seuls les événements (compteur, photo toutes les 10 s) y transitent. |
| Qu'est-ce que vous amélioreriez ? | Un compte broker par client avec des ACL, des jetons API à durée de vie courte, le réentraînement sur des données réelles, et des sauvegardes de la base. |
