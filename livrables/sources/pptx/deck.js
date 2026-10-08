const path = require("path");
const pptxgen = require("pptxgenjs");
const { applyTheme } = require("/Users/felis/.claude/skills/synced/e1825baa-44e5-4f14-ae66-a7089b483edd_177c81d7-6cc6-49ae-bfff-824dde08a92e/pptx/scripts/apply_theme.js");

const OUT = process.argv[2] || "deck.pptx";
const DIR = __dirname;

const THEME = {
  name: "Sentinel-X",
  headFontFace: "Arial",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "14181F", lt1: "FFFFFF", dk2: "3A4452", lt2: "F1F4F6",
    accent1: "F2B705", accent2: "C8372B", accent3: "23824F", accent4: "B86E00",
    accent5: "6B7886", accent6: "2F6DB5", hlink: "2F6DB5", folHlink: "6B7886",
  },
};
const HEX = THEME.colors;

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
pres.title = "Sentinel-X - Soutenance Groupe 7";
pres.author = "Groupe 7";
pres.company = "Workshop EPSI 2026";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;

// ---------- Layouts ----------
pres.defineSlideMaster({
  title: "TITRE_SOMBRE",
  background: { color: C.text1 },
  objects: [
    { placeholder: { options: { name: "kicker", type: "body", x: 0.8, y: 1.2, w: 9, h: 0.4, fontSize: 13, bold: true, color: C.accent1, charSpacing: 4, align: "left" }, text: "" } },
    { placeholder: { options: { name: "title", type: "title", x: 0.8, y: 1.7, w: 9.5, h: 2.4, fontSize: 66, bold: true, color: C.background1, valign: "bottom", align: "left" }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.8, y: 4.3, w: 9.5, h: 1.0, fontSize: 24, color: C.background2, valign: "top", align: "left" }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENU",
  background: { color: C.background1 },
  margin: [0.5, 0.6, 0.6, 0.6],
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.35, w: 12.1, h: 0.85, fontSize: 32, bold: true, color: C.text1, valign: "middle", align: "left", margin: 0 }, text: "" } },
    { text: { text: "Sentinel-X · Groupe 7", options: { x: 0.6, y: 7.0, w: 5, h: 0.3, fontSize: 10, color: C.accent5, margin: 0 } } },
  ],
  slideNumber: { x: 12.3, y: 7.0, w: 0.5, h: 0.3, fontSize: 10, color: HEX.accent5, align: "right" },
});
pres.defineSlideMaster({
  title: "CONTENU_SOMBRE",
  background: { color: C.text1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.35, w: 12.1, h: 0.85, fontSize: 32, bold: true, color: C.background1, valign: "middle", align: "left", margin: 0 }, text: "" } },
    { text: { text: "Sentinel-X · Groupe 7", options: { x: 0.6, y: 7.0, w: 5, h: 0.3, fontSize: 10, color: C.accent5, margin: 0 } } },
  ],
  slideNumber: { x: 12.3, y: 7.0, w: 0.5, h: 0.3, fontSize: 10, color: HEX.accent5, align: "right" },
});

// ---------- Helpers ----------
const tag = (slide, txt, x, y, name, dark = false) => {
  slide.addText(txt, {
    x, y, w: 0.55, h: 0.42, fontSize: 14, bold: true, align: "center", valign: "middle", margin: 0,
    fill: { color: dark ? C.accent1 : C.text1 }, color: dark ? C.text1 : C.accent1,
    shape: pres.ShapeType.roundRect, rectRadius: 0.05, isTextBox: true, objectName: name,
  });
};
const card = (slide, { x, y, w, h, head, kicker, body, name, headH = 0.95, bodySize }) => {
  slide.addShape(pres.ShapeType.roundRect, { x, y, w, h, fill: { color: C.background2 }, line: { color: C.background2 }, rectRadius: 0.06, objectName: name + "-fond" });
  slide.addShape(pres.ShapeType.roundRect, { x, y, w, h: headH, fill: { color: C.text1 }, line: { color: C.text1 }, rectRadius: 0.06, objectName: name + "-entete" });
  slide.addShape(pres.ShapeType.rect, { x, y: y + headH - 0.12, w, h: 0.12, fill: { color: C.text1 }, line: { color: C.text1 }, objectName: name + "-raccord" });
  const runs = [];
  if (kicker) runs.push({ text: kicker, options: { fontSize: 11, bold: true, color: C.accent1, charSpacing: 2, breakLine: true } });
  runs.push({ text: head, options: { fontSize: 18, bold: true, color: C.background1 } });
  slide.addText(runs, { x: x + 0.2, y: y + 0.08, w: w - 0.4, h: headH - 0.16, valign: "middle", margin: 0, isTextBox: true, objectName: name + "-titre" });
  slide.addText(body, { x: x + 0.2, y: y + headH + 0.15, w: w - 0.4, h: h - headH - 0.3, fontSize: bodySize || 15, color: C.text1, valign: "top", margin: 0, isTextBox: true, objectName: name + "-texte" });
};
const stat = (slide, { x, y, w, h, big, label, name, dark = true }) => {
  slide.addShape(pres.ShapeType.roundRect, { x, y, w, h, fill: { color: dark ? C.text1 : C.background2 }, line: { color: dark ? C.text1 : C.background2 }, rectRadius: 0.06, objectName: name + "-fond" });
  slide.addText([
    { text: big, options: { fontSize: 36, bold: true, color: dark ? C.accent1 : C.text1, breakLine: true } },
    { text: label, options: { fontSize: 13, color: dark ? C.background2 : C.text2 } },
  ], { x: x + 0.2, y: y + 0.12, w: w - 0.4, h: h - 0.24, valign: "top", margin: 0, isTextBox: true, objectName: name + "-texte", paraSpaceAfter: 4 });
};
const box = (slide, { x, y, w, h, title, sub, fill, color, subColor, name, titleSize = 16 }) => {
  slide.addShape(pres.ShapeType.roundRect, { x, y, w, h, fill: { color: fill }, line: { color: fill }, rectRadius: 0.06, objectName: name + "-fond" });
  slide.addText([
    { text: title, options: { fontSize: titleSize, bold: true, color, breakLine: !!sub } },
    ...(sub ? [{ text: sub, options: { fontSize: 12, color: subColor || color } }] : []),
  ], { x: x + 0.15, y, w: w - 0.3, h, valign: "middle", margin: 0, isTextBox: true, objectName: name + "-texte" });
};
const band = (slide, runs, { x, y, w, h, fill, name, fontSize = 15 }) => {
  slide.addShape(pres.ShapeType.roundRect, { x, y, w, h, fill: { color: fill }, line: { color: fill }, rectRadius: 0.05, objectName: name + "-fond" });
  slide.addText(runs, { x: x + 0.25, y, w: w - 0.5, h, fontSize, color: C.text1, valign: "middle", margin: 0, isTextBox: true, objectName: name });
};
const arrow = (slide, x, y, w, h, color, name, opts = {}) => {
  slide.addShape(pres.ShapeType.line, { x, y, w, h, line: { color, width: opts.width || 2.5, endArrowType: "triangle", dashType: opts.dash || "solid" }, flipV: !!opts.flipV, objectName: name });
};

// =====================================================================
// 1. Titre
// =====================================================================
pres.addSection({ title: "Ouverture" });
let s = pres.addSlide({ masterName: "TITRE_SOMBRE", sectionTitle: "Ouverture" });
s.addText("AETHERCORP INDUSTRIAL SOLUTIONS · INITIATIVE SENTINEL-X", { placeholder: "kicker" });
s.addText("Sentinel-X", { placeholder: "title" });
s.addText("Yanshee Defender 3000 · la sécurité à la bordure.", { placeholder: "body" });
s.addImage({ path: path.join(DIR, "shield.png"), x: 8.9, y: 0.9, w: 4.6, h: 4.6, transparency: 70, objectName: "logo-bouclier" });
s.addText([
  { text: "Workshop national EPSI Bac+4 · Groupe 7", options: { bold: true, color: C.background1, breakLine: true } },
  { text: "Elios · Benoit (Infra)   ·   Felis · Martin · Matis (Dev)", options: { color: C.accent5 } },
], { x: 0.8, y: 5.9, w: 9, h: 0.8, fontSize: 16, margin: 0, isTextBox: true, objectName: "equipe" });
s.addNotes("ORATEUR : Tous (Felis ouvre). 0:00 – 1:00 · Présentation. Une phrase chacun : prénom et rôle. Puis : « AetherCorp perd ses micro-centrales isolées sous trois menaces à la fois. Notre réponse : Sentinel-X. » Enchaîner sur la variante d'architecture (diapo suivante) avant de lancer le teaser.");

// =====================================================================
// 2. Trois menaces
// =====================================================================
s = pres.addSlide({ masterName: "CONTENU", sectionTitle: "Ouverture" });
s.addText("Trois menaces, une seule sentinelle", { placeholder: "title" });
const threats = [
  ["INTRUSION PHYSIQUE", "Espionnage industriel", "IA de vision YOLO26n sur la caméra du robot Yanshee : détection de personne, photo de preuve, riposte du robot."],
  ["RISQUE ENVIRONNEMENTAL", "Fuite de gaz, surchauffe", "Boîtier ESP8266 : température, humidité, gaz, présence. L'IA prédictive voit la dérive avant le seuil critique."],
  ["CYBERATTAQUE", "Déstabilisation réseau", "MQTT sur TLS avec CA embarqué, HTTPS, pare-feu UFW, SSH par clé, réseau segmenté en 4 VLAN."],
];
threats.forEach(([k, h, b], i) => card(s, { x: 0.6 + i * 4.1, y: 1.55, w: 3.9, h: 3.35, kicker: k, head: h, body: b, name: "menace-" + (i + 1), headH: 1.1, bodySize: 17 }));
band(s, [
  { text: "Mission : ", options: { bold: true } },
  { text: "un boîtier autonome relié de façon chiffrée à un centre de commandement, avec une IA qui décide." },
], { x: 0.6, y: 5.25, w: 12.1, h: 0.75, fill: "FFF4CC", name: "mission", fontSize: 17 });
s.addNotes("ORATEUR : Felis. Trois menaces simultanées, une réponse par menace. Insister : les trois briques sont reliées entre elles, c'est la règle éliminatoire du sujet.");

// =====================================================================
// 3. Architecture
// =====================================================================
s = pres.addSlide({ masterName: "CONTENU", sectionTitle: "Ouverture" });
s.addText("Variante retenue : Edge-to-Server distribuée", { placeholder: "title" });
s.addShape(pres.ShapeType.roundRect, { x: 0.6, y: 1.45, w: 2.6, h: 4.4, fill: { color: "FFF4CC" }, line: { color: "FFF4CC" }, rectRadius: 0.06, objectName: "zone-edge" });
s.addText("TABLE", { x: 0.75, y: 1.5, w: 2.3, h: 0.35, fontSize: 11, bold: true, color: C.accent4, charSpacing: 3, margin: 0, isTextBox: true, objectName: "zone-edge-titre" });
s.addShape(pres.ShapeType.roundRect, { x: 3.45, y: 1.45, w: 9.25, h: 4.4, fill: { color: C.background2 }, line: { color: C.background2 }, rectRadius: 0.06, objectName: "zone-serveur" });
s.addText("CENTRE DE COMMANDEMENT · PROXMOX · 4 VLAN", { x: 3.6, y: 1.5, w: 8, h: 0.35, fontSize: 11, bold: true, color: C.accent5, charSpacing: 3, margin: 0, isTextBox: true, objectName: "zone-serveur-titre" });
box(s, { x: 0.8, y: 2.0, w: 2.2, h: 1.3, title: "Boîtier ESP8266", sub: "DHT22 · MQ-135 · PIR · OLED · buzzer · LED", fill: C.text1, color: C.accent1, subColor: C.background1, name: "boitier" });
box(s, { x: 0.8, y: 4.25, w: 2.2, h: 1.3, title: "Robot Yanshee", sub: "Caméra HD · riposte", fill: C.text1, color: C.accent1, subColor: C.background1, name: "robot" });
box(s, { x: 3.8, y: 2.0, w: 2.5, h: 1.3, title: "Mosquitto", sub: "MQTT/TLS 8883", fill: C.background1, color: C.text1, subColor: C.accent2, name: "mosquitto" });
box(s, { x: 3.8, y: 4.25, w: 2.5, h: 1.3, title: "IA vision", sub: "YOLO26n · 640 px", fill: C.background1, color: C.text1, subColor: C.text2, name: "yolo" });
box(s, { x: 6.85, y: 2.0, w: 2.5, h: 1.3, title: "API FastAPI", sub: "REST + WebSocket", fill: C.background1, color: C.text1, subColor: C.text2, name: "api" });
box(s, { x: 6.85, y: 4.25, w: 2.5, h: 1.3, title: "IA prédictive", sub: "Isolation + Random Forest", fill: C.background1, color: C.text1, subColor: C.text2, name: "ia-pred" });
box(s, { x: 9.9, y: 2.0, w: 2.55, h: 1.3, title: "Galera ×3", sub: "via VIP HAProxy", fill: C.background1, color: C.text1, subColor: C.text2, name: "galera" });
box(s, { x: 9.9, y: 4.25, w: 2.55, h: 1.3, title: "Dashboard", sub: "React · HTTPS / WSS", fill: C.accent2, color: C.background1, name: "dashboard" });
arrow(s, 3.0, 2.65, 0.78, 0, HEX.accent2, "fleche-telemetrie", { width: 3.5 });
arrow(s, 3.0, 4.9, 0.78, 0, HEX.text1, "fleche-video");
arrow(s, 6.3, 2.65, 0.53, 0, HEX.accent2, "fleche-ingestion", { width: 3.5 });
arrow(s, 6.3, 3.35, 0.55, 0.9, HEX.accent2, "fleche-detections", { flipV: true });
arrow(s, 8.1, 3.3, 0, 0.93, HEX.accent2, "fleche-anomalies");
arrow(s, 9.35, 2.65, 0.53, 0, HEX.text1, "fleche-sql");
arrow(s, 9.35, 3.3, 0.55, 0.95, HEX.text1, "fleche-ws");
const chips = [["Option B du sujet", "PC Serveur Local réparti sur des VM Proxmox"], ["Caméra du robot Yanshee", "à la place de la webcam USB, validée par les coachs"], ["Tout passe par le broker", "sauf la vidéo, en MJPEG direct"]];
chips.forEach(([a, b], i) => s.addText([{ text: a, options: { bold: true, breakLine: true } }, { text: b, options: { color: C.text2 } }], { x: 0.6 + i * 4.1, y: 6.05, w: 3.9, h: 0.75, fontSize: 13, color: C.text1, margin: 0, valign: "top", isTextBox: true, objectName: "precision-" + (i + 1) }));
s.addNotes("ORATEUR : Elios. Rappel de la variante d'architecture (exigé en minute 1). Option B distribuée : le PC Serveur Local est réparti sur des VM Proxmox. La caméra du robot remplace la webcam USB, variante validée par les coachs. Flèches rouges = flux chiffrés TLS.");

// =====================================================================
// 4. Teaser
// =====================================================================
pres.addSection({ title: "Teaser et démo" });
s = pres.addSlide({ masterName: "TITRE_SOMBRE", sectionTitle: "Teaser et démo" });
s.addText("TEASER · 60 SECONDES", { placeholder: "kicker" });
s.addText("Sentinel Drop", { placeholder: "title" });
s.addText("60 secondes · format vertical", { placeholder: "body" });
s.addShape(pres.ShapeType.ellipse, { x: 10.2, y: 2.2, w: 2.0, h: 2.0, fill: { color: C.accent1 }, line: { color: C.accent1 }, objectName: "bouton-lecture" });
s.addShape(pres.ShapeType.triangle, { x: 10.85, y: 2.75, w: 0.85, h: 0.9, fill: { color: C.text1 }, line: { color: C.text1 }, rotate: 90, objectName: "icone-lecture" });
s.addNotes("ORATEUR : Personne (vidéo). 1:00 – 2:00 · Lancer la vidéo VidDrop en plein écran. Ne rien dire pendant la lecture.");

// =====================================================================
// 5. Démo live
// =====================================================================
s = pres.addSlide({ masterName: "CONTENU_SOMBRE", sectionTitle: "Teaser et démo" });
s.addText("Démo live : ce que vous allez voir", { placeholder: "title" });
const steps = [
  ["Le boîtier vit", "OLED : IP, mesures, MQTT connecté. Les courbes bougent en direct sur le dashboard."],
  ["Commande à distance", "Un clic sur le dashboard : buzzer et LED du boîtier en moins d'une seconde."],
  ["Dérive détectée avant le seuil", "Chauffe lente du DHT22 : la jauge IA passe au-dessus de 1, l'OLED affiche encore « normal »."],
  ["Intrus repéré", "Une personne devant le robot : détection YOLO, photo, alerte, riposte."],
  ["Chiffrement prouvé", "Wireshark sur le flux MQTT : trafic illisible."],
  ["Serveur durci", "ufw status, connexion SSH par mot de passe refusée."],
];
steps.forEach(([h, b], i) => {
  const col = i % 2, row = Math.floor(i / 2);
  const x = 0.6 + col * 6.15, y = 1.55 + row * 1.7;
  tag(s, String(i + 1), x, y + 0.05, "etape-" + (i + 1) + "-num", true);
  s.addText([{ text: h, options: { bold: true, fontSize: 18, color: C.accent1, breakLine: true } }, { text: b, options: { fontSize: 14, color: C.background1 } }],
    { x: x + 0.75, y, w: 5.1, h: 1.45, valign: "top", margin: 0, isTextBox: true, objectName: "etape-" + (i + 1) });
});
s.addNotes("ORATEUR : Martin au clavier, Matis raconte, Elios (Wireshark) et Benoit (ufw, SSH). 2:00 – 5:00 · Démo live, dans cet ordre. Préparer avant : anomaly_service lancé depuis plus de 60 s, boîtier chauffé depuis 60 s, Wireshark ouvert sur le port 8883, terminal SSH prêt. Plan B si le boîtier tombe : simulate.py --scenario demo --publish --speed 5.");

// =====================================================================
// 6. Boîtier
// =====================================================================
pres.addSection({ title: "Pitch technique" });
s = pres.addSlide({ masterName: "CONTENU", sectionTitle: "Pitch technique" });
s.addText("Le boîtier : capter, afficher, alerter", { placeholder: "title" });
const pins = [["DHT22", "D2", "température, humidité · toutes les 2 s"], ["MQ-135", "A0", "gaz · référence adaptative, chauffe 60 s"], ["PIR HC-SR501", "D5", "présence · calibration 30 s"], ["OLED 0,96\"", "D6/D7", "IP, mesures, état MQTT"], ["Buzzer · LED", "D0/D1", "alarme sur commande uniquement"]];
const rows = [[
  { text: "Composant", options: { bold: true, color: C.background1, fill: { color: C.text1 } } },
  { text: "Broche", options: { bold: true, color: C.background1, fill: { color: C.text1 } } },
  { text: "Rôle", options: { bold: true, color: C.background1, fill: { color: C.text1 } } },
]].concat(pins.map(([a, b, c], i) => [
  { text: a, options: { bold: true, fill: { color: i % 2 ? "FFFFFF" : "F1F4F6" } } },
  { text: b, options: { fontFace: "Courier New", fill: { color: i % 2 ? "FFFFFF" : "F1F4F6" } } },
  { text: c, options: { fill: { color: i % 2 ? "FFFFFF" : "F1F4F6" } } },
]));
s.addTable(rows, { x: 0.6, y: 1.55, w: 7.4, colW: [1.9, 1.1, 4.4], fontSize: 14, color: HEX.dk1, rowH: 0.62, border: { type: "none" }, valign: "middle", objectName: "tableau-capteurs" });
stat(s, { x: 8.45, y: 1.55, w: 4.25, h: 1.45, big: "TLS 8883", label: "MQTT chiffré, CA embarqué, chaîne du broker vérifiée", name: "stat-tls" });
stat(s, { x: 8.45, y: 3.15, w: 4.25, h: 1.45, big: "1 Hz", label: "télémétrie JSON, Last Will « offline » si le boîtier tombe", name: "stat-1hz" });
stat(s, { x: 8.45, y: 4.75, w: 4.25, h: 1.45, big: "0 delay()", label: "boucle non bloquante : capteurs actifs même sans réseau", name: "stat-delay" });
s.addText("Firmware C++ PlatformIO · RAM 39 % · Flash 40 % · le boîtier ne déclenche aucune alarme seul : c'est le centre de commandement qui décide.", { x: 0.6, y: 5.6, w: 7.4, h: 0.75, fontSize: 13, color: C.text2, margin: 0, valign: "top", isTextBox: true, objectName: "note-firmware" });
s.addNotes("ORATEUR : Felis. Le boîtier. Points à dire : TLS avec CA embarqué (pas juste chiffré : le broker est authentifié), Last Will pour détecter une coupure, boucle sans delay. Question probable du jury : pourquoi MQ-135 ? Même brochage analogique que le MQ-2, détection relative à l'air calme.");

// =====================================================================
// 7. IA vision
// =====================================================================
s = pres.addSlide({ masterName: "CONTENU", sectionTitle: "Pitch technique" });
s.addText("IA de vision : voir et riposter", { placeholder: "title" });
const flow = [["Caméra du robot", "640×480 · 25 i/s, encodée par le GPU du robot"], ["YOLO26n", "classe « person » uniquement, entrée 640 px, confiance 0,40"], ["Alerte + preuve", "compteur, photo JPEG en base, alerte d'intrusion"], ["Riposte", "le robot lève les bras puis frappe, statut publié en MQTT"]];
flow.forEach(([h, b], i) => {
  const x = 0.6 + i * 3.1;
  s.addShape(pres.ShapeType.roundRect, { x, y: 1.6, w: 2.75, h: 2.3, fill: { color: i === 1 ? C.text1 : C.background2 }, line: { color: i === 1 ? C.text1 : C.background2 }, rectRadius: 0.06, objectName: "vision-etape-" + (i + 1) + "-fond" });
  tag(s, String(i + 1), x + 0.2, 1.8, "vision-etape-" + (i + 1) + "-num", i === 1);
  s.addText([{ text: h, options: { bold: true, fontSize: 18, color: i === 1 ? C.accent1 : C.text1, breakLine: true } }, { text: b, options: { fontSize: 14, color: i === 1 ? C.background1 : C.text2 } }],
    { x: x + 0.2, y: 2.4, w: 2.35, h: 1.4, valign: "top", margin: 0, isTextBox: true, objectName: "vision-etape-" + (i + 1) });
  if (i < 3) arrow(s, x + 2.78, 2.9, 0.3, 0, HEX.accent2, "vision-fleche-" + (i + 1));
});
stat(s, { x: 0.6, y: 4.3, w: 3.9, h: 1.5, big: "< 100 ms", label: "objectif par trame (sujet), inférence CPU", name: "stat-latence", dark: false });
stat(s, { x: 4.7, y: 4.3, w: 3.9, h: 1.5, big: "1 / 10 s", label: "photo de preuve maximum : le broker n'est pas saturé", name: "stat-photo", dark: false });
stat(s, { x: 8.8, y: 4.3, w: 3.9, h: 1.5, big: "5 s", label: "anti-rebond entre deux alertes ou ripostes", name: "stat-rebond", dark: false });
s.addNotes("ORATEUR : Martin. La vidéo ne passe pas par MQTT (25 i/s saturerait le broker) : seuls les événements y transitent. YOLO26n nano = plus léger de la famille, temps réel sur CPU. Donner la latence mesurée en démo.");

// =====================================================================
// 8. IA prédictive : chiffres
// =====================================================================
s = pres.addSlide({ masterName: "CONTENU", sectionTitle: "Pitch technique" });
s.addText("IA prédictive : la dérive vue avant le seuil", { placeholder: "title" });
s.addChart(pres.ChartType.bar, [{ name: "Avance (min)", labels: ["Fuite de gaz lente", "Chauffe + dérive gaz (démo)", "Surchauffe lente"], values: [9, 18, 22] }], {
  x: 0.6, y: 1.5, w: 7.2, h: 3.9, barDir: "bar", chartColors: [HEX.dk1],
  showTitle: true, title: "Avance médiane sur le seuil critique (minutes)", titleFontSize: 14, titleColor: HEX.dk1, titleFontFace: "+mn-lt",
  showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 14, dataLabelFontBold: true, dataLabelColor: HEX.dk1, dataLabelFontFace: "+mn-lt",
  catAxisLabelColor: HEX.dk2, catAxisLabelFontSize: 13, catAxisLabelFontFace: "+mn-lt", valAxisHidden: true,
  valGridLine: { style: "none" }, catGridLine: { style: "none" }, showLegend: false, barGapWidthPct: 60, objectName: "graphique-avance",
});
s.addText([{ text: "Firmware seul : ", options: { bold: true, color: C.accent2 } }, { text: "ne détecte jamais ces dérives lentes, sa référence les absorbe." }],
  { x: 0.6, y: 5.55, w: 7.2, h: 0.6, fontSize: 14, color: C.text1, margin: 0, isTextBox: true, objectName: "note-firmware-aveugle" });
stat(s, { x: 8.3, y: 1.5, w: 4.4, h: 1.45, big: "0,15 / h", label: "fausses alertes sur 47 h de normal simulé", name: "stat-fp" });
stat(s, { x: 8.3, y: 3.1, w: 4.4, h: 1.45, big: "20 / 20", label: "diagnostics corrects sur 4 scénarios sur 5", name: "stat-diag" });
s.addShape(pres.ShapeType.roundRect, { x: 8.3, y: 4.7, w: 4.4, h: 1.45, fill: { color: "FFF4CC" }, line: { color: "FFF4CC" }, rectRadius: 0.06, objectName: "modele-fond" });
s.addText([{ text: "Pas de if temp > 40", options: { bold: true, breakLine: true } }, { text: "Isolation Forest (le normal) + Random Forest (le diagnostic), un modèle par capteur." }],
  { x: 8.5, y: 4.8, w: 4.0, h: 1.25, fontSize: 14, color: C.text1, margin: 0, valign: "middle", isTextBox: true, objectName: "modele-texte" });
s.addNotes("ORATEUR : Matis. Le cœur de l'innovation. Le firmware a des seuils avec une référence adaptative : une fuite lente est absorbée par la référence, il ne la voit jamais. L'IA apprend le normal par capteur et prévient 9 à 22 minutes avant le seuil. Évaluation sur données inédites, 20 tirages par scénario.");

// =====================================================================
// 9. IA prédictive : la preuve
// =====================================================================
s = pres.addSlide({ masterName: "CONTENU", sectionTitle: "Pitch technique" });
s.addText("Le scénario de démo, seconde par seconde", { placeholder: "title" });
s.addImage({ path: path.join(DIR, "scenario_demo_ia.png"), x: 0.6, y: 1.45, w: 7.9, h: 3.4, objectName: "graphique-scenario" });
s.addText("Scénario simulé : chauffe lente + micro-dérive de gaz, incident à 10 min.", { x: 0.6, y: 4.95, w: 7.9, h: 0.35, fontSize: 11, color: C.accent5, margin: 0, isTextBox: true, objectName: "legende-scenario" });
const proofs = [["10 min", "début de l'incident : le gaz monte lentement"], ["≈ 11 min", "l'indice de risque IA franchit 1 : alerte et diagnostic « fuite lente »"], ["toujours", "la référence du firmware suit le gaz : il reste à « normal »"]];
proofs.forEach(([a, b], i) => {
  s.addText([{ text: a, options: { bold: true, fontSize: 22, color: i === 1 ? C.accent2 : C.text1, breakLine: true } }, { text: b, options: { fontSize: 14, color: C.text2 } }],
    { x: 8.9, y: 1.5 + i * 1.3, w: 3.8, h: 1.15, valign: "top", margin: 0, isTextBox: true, objectName: "preuve-" + (i + 1) });
});
band(s, [{ text: "Enregistrement réel du 06/10, jamais vu à l'entraînement : ", options: { bold: true } }, { text: "surchauffe, souffle et pic de gaz correctement diagnostiqués." }], { x: 0.6, y: 5.6, w: 12.1, h: 0.7, fill: "F1F4F6", name: "preuve-reelle" });
s.addNotes("ORATEUR : Matis. Haut : gaz brut et référence du firmware (pointillés), confondus. Bas : indice de risque par capteur, seuil à 1. L'IA déclenche vers 11 min, le firmware jamais. Limite honnête : normal simulé, à réentraîner sur une heure réelle de la salle.");

// =====================================================================
// 10. Infra
// =====================================================================
s = pres.addSlide({ masterName: "CONTENU", sectionTitle: "Pitch technique" });
s.addText("Une infrastructure qui encaisse la panne", { placeholder: "title" });
const vlans = [["VLAN 10 · WEB", "172.16.137.0/26", "Mosquitto .4 · API et dashboard .5 · IA YOLO .6", "FFF4CC"], ["VLAN 20 · INFRA", "172.16.137.64/26", "Galera .1 .2 .3 derrière la VIP HAProxy .10", "E8EEF3"], ["VLAN 30 · SUPERVISION", "172.16.137.128/26", "Zabbix .8 : CPU, RAM, disque, disponibilité", "E0F2E8"], ["VLAN 40 · AUTOMATISATION", "172.16.137.192/26", "Ansible .7 : déploie Galera, Zabbix et les agents", "EDE7F6"]];
vlans.forEach(([h, net, b, f], i) => {
  const x = 0.6 + (i % 2) * 3.85, y = 1.55 + Math.floor(i / 2) * 2.3;
  s.addShape(pres.ShapeType.roundRect, { x, y, w: 3.65, h: 2.1, fill: { color: f }, line: { color: f }, rectRadius: 0.06, objectName: "vlan-" + (i + 1) + "-fond" });
  s.addText([{ text: h, options: { bold: true, fontSize: 17, color: C.text1, breakLine: true } }, { text: net, options: { fontSize: 13, color: C.accent5, breakLine: true } }, { text: b, options: { fontSize: 15, color: C.text1 } }],
    { x: x + 0.2, y: y + 0.2, w: 3.25, h: 1.7, valign: "top", margin: 0, isTextBox: true, objectName: "vlan-" + (i + 1), paraSpaceAfter: 6 });
});
stat(s, { x: 8.5, y: 1.55, w: 4.2, h: 1.45, big: "3 nœuds", label: "Galera synchrone : le quorum tient si un nœud tombe", name: "stat-galera" });
stat(s, { x: 8.5, y: 3.15, w: 4.2, h: 1.45, big: "1 VIP", label: "HAProxy : l'API ne voit jamais un nœud isolé", name: "stat-vip" });
stat(s, { x: 8.5, y: 4.75, w: 4.2, h: 1.45, big: "100 %", label: "des machines supervisées par Zabbix", name: "stat-zabbix" });
s.addNotes("ORATEUR : Benoit. Proxmox, 4 VLAN en /26. Pourquoi 3 nœuds Galera et pas 2 : avec 2, la perte d'un nœud bloque le cluster (plus de majorité). Démo possible : arrêter un nœud, l'API continue.");

// =====================================================================
// 11. Sécurité
// =====================================================================
s = pres.addSlide({ masterName: "CONTENU", sectionTitle: "Pitch technique" });
s.addText("Sécurité : ce que nous prouvons", { placeholder: "title" });
const sec = [
  ["MQTT ESP8266 → broker", "TLS 8883, CA embarqué", "Wireshark", "En place"],
  ["Dashboard et API", "HTTPS / WSS", "Cadenas navigateur", "En place"],
  ["Pare-feu", "UFW, deny par défaut", "ufw status verbose", "En place"],
  ["Accès serveurs", "SSH par clé uniquement", "sshd -T", "En place"],
  ["Segmentation", "4 VLAN, base isolée", "Schéma réseau", "En place"],
  ["Secrets", "hors dépôt, modèles .example", "git grep vide", "En place"],
  ["Broker MQTT", "authentification obligatoire", "mosquitto.conf", "En place"],
];
const head = ["Domaine", "Mesure", "Preuve", "État"].map(t => ({ text: t, options: { bold: true, color: C.background1, fill: { color: C.text1 } } }));
const stateColor = { "En place": HEX.accent3, "Corrigé": HEX.accent3, "Partiel": HEX.accent4 };
const secRows = [head].concat(sec.map((r, i) => r.map((c, j) => ({
  text: c, options: { fill: { color: i % 2 ? "FFFFFF" : "F1F4F6" }, bold: j === 0 || j === 3, color: j === 3 ? stateColor[c] : HEX.dk1, fontFace: j === 2 ? "Courier New" : undefined },
}))));
s.addTable(secRows, { x: 0.6, y: 1.5, w: 12.1, colW: [2.9, 4.0, 3.4, 1.8], fontSize: 14, color: HEX.dk1, rowH: 0.56, border: { type: "none" }, valign: "middle", objectName: "matrice-securite" });
s.addNotes("ORATEUR : Elios. Tout ce qui est sur cette diapo se démontre en direct : Wireshark, ufw status, connexion SSH par mot de passe refusée.");

// =====================================================================
// 12. Audit
// =====================================================================
s = pres.addSlide({ masterName: "CONTENU", sectionTitle: "Pitch technique" });
s.addText("Auto-audit et pentest croisé", { placeholder: "title" });
const fixes = [
  ["MQTT exclusivement sur TLS", "le boîtier ne parle plus jamais en clair"],
  ["Secrets hors du dépôt", ".env, secrets.h, vault.yml exclus, modèles fournis"],
  ["Clés obligatoires", "robot et API refusent de démarrer sans secret"],
  ["Flux annoté au dashboard", "l'API relaie le flux YOLO, robot en repli"],
];
stat(s, { x: 0.6, y: 1.6, w: 6.1, h: 1.35, big: "5 correctifs", label: "appliqués avant le pentest, après revue de toutes les briques", name: "stat-correctifs" });
fixes.forEach(([a, b], i) => {
  const y = 3.2 + i * 0.75;
  s.addShape(pres.ShapeType.ellipse, { x: 0.6, y: y + 0.08, w: 0.3, h: 0.3, fill: { color: C.accent3 }, line: { color: C.accent3 }, objectName: "correctif-" + (i + 1) + "-puce" });
  s.addText([{ text: a + " : ", options: { bold: true } }, { text: b, options: { color: C.text2 } }], { x: 1.1, y, w: 5.6, h: 0.5, fontSize: 14, color: C.text1, valign: "middle", margin: 0, isTextBox: true, objectName: "correctif-" + (i + 1) });
});
s.addShape(pres.ShapeType.roundRect, { x: 7.1, y: 1.6, w: 5.6, h: 4.55, fill: { color: C.text1 }, line: { color: C.text1 }, rectRadius: 0.06, objectName: "pentest-fond" });
s.addText([
  { text: "PENTEST CROISÉ · 8 OCTOBRE", options: { bold: true, fontSize: 12, color: C.accent1, charSpacing: 2, breakLine: true } },
  { text: "Attaques subies : …", options: { fontSize: 16, color: C.background1, breakLine: true } },
  { text: "Attaques bloquées : …", options: { fontSize: 16, color: C.background1, breakLine: true } },
  { text: "Failles exploitées : …", options: { fontSize: 16, color: C.background1, breakLine: true } },
  { text: "Correctifs appliqués : …", options: { fontSize: 16, color: C.background1 } },
], { x: 7.35, y: 1.8, w: 5.1, h: 4.15, valign: "top", margin: 0, isTextBox: true, objectName: "pentest-resultats", paraSpaceAfter: 14 });
s.addNotes("ORATEUR : Benoit. À gauche, l'auto-audit du matin et ses correctifs (détail dans le dossier, section 11). À droite, À COMPLÉTER avec le bilan du pentest de l'après-midi.");

// =====================================================================
// 13. Équipe
// =====================================================================
s = pres.addSlide({ masterName: "CONTENU", sectionTitle: "Pitch technique" });
s.addText("Un consortium, deux pôles, un contrat", { placeholder: "title" });
card(s, { x: 0.6, y: 1.55, w: 5.9, h: 2.3, kicker: "PÔLE INFRA", head: "Elios · Benoit", body: "Proxmox et VLAN, Galera et HAProxy, Mosquitto et TLS, Ansible, Zabbix, durcissement.", name: "pole-infra", headH: 1.0 });
card(s, { x: 6.8, y: 1.55, w: 5.9, h: 2.3, kicker: "PÔLE DEV", head: "Felis · Martin · Matis", body: "Firmware ESP8266, API, dashboard React, IA de vision et prédictive, robot Yanshee.", name: "pole-dev", headH: 1.0 });
const days = [["Lun", "Contrat d'interface figé, plan IP, VM"], ["Mar", "Câblage, firmware, broker, Galera, API"], ["Mer", "Bout en bout, IA, robot, tournage"], ["Jeu", "TLS seul, secrets, audit, pentest"]];
days.forEach(([d, t], i) => {
  const x = 0.6 + i * 3.1;
  tag(s, d, x, 4.3, "jour-" + (i + 1) + "-tag");
  s.addText(t, { x: x + 0.7, y: 4.25, w: 2.3, h: 0.9, fontSize: 13, color: C.text1, valign: "top", margin: 0, isTextBox: true, objectName: "jour-" + (i + 1) });
});
band(s, [{ text: "Méthode : ", options: { bold: true } }, { text: "Jira pour les tâches · une branche par brique, fusion par pull request · commits sémantiques · tests automatisés sur l'API et les IA" }], { x: 0.6, y: 5.55, w: 12.1, h: 0.7, fill: "F1F4F6", name: "methode", fontSize: 14 });
s.addNotes("ORATEUR : Martin. Le risque n°1 identifié lundi était l'intégration : on a figé topics MQTT, payloads et routes dès le premier jour. C'est ce qui a permis le bout en bout mercredi.");

// =====================================================================
// 14. Conclusion
// =====================================================================
pres.addSection({ title: "Conclusion" });
s = pres.addSlide({ masterName: "TITRE_SOMBRE", sectionTitle: "Conclusion" });
s.addText("SENTINEL-X", { placeholder: "kicker" });
s.addText("La sécurité\nà la bordure.", { placeholder: "title" });
s.addText("Merci. Vos questions ?", { placeholder: "body" });
s.addImage({ path: path.join(DIR, "shield.png"), x: 8.9, y: 0.9, w: 4.6, h: 4.6, transparency: 70, objectName: "logo-bouclier-fin" });
const takeaways = [["Bout en bout", "du capteur au dashboard, chiffré"], ["IA qui anticipe", "9 à 22 min avant le seuil"], ["Infra résiliente", "Galera ×3, VLAN, supervision"]];
takeaways.forEach(([a, b], i) => s.addText([{ text: a, options: { bold: true, color: C.accent1, breakLine: true } }, { text: b, options: { color: C.background2 } }],
  { x: 0.8 + i * 4.0, y: 5.6, w: 3.7, h: 0.9, fontSize: 16, valign: "top", margin: 0, isTextBox: true, objectName: "a-retenir-" + (i + 1) }));
s.addNotes("ORATEUR : Felis. Conclure en 15 secondes sur les trois points, puis ouvrir les questions. Si on demande la suite : cluster Mosquitto, réentraînement de l'IA sur les données de la salle, sauvegardes automatisées de la base.");

(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("OK", OUT);
})();
