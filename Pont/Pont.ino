//**********************************************************************************************************************************************
// Nom du fichier: Lumiere_Pont_Mode_Station
// Projet: Gestion des accessoires du Zumi (Modifié pour intégration réseau)
// Auteur Original : Dany Lauzon
// Modification : Connexion WiFi Station pour intégration Zumi
// Date : 2026-02-03
// Description: Gère les lumières, le pont-levis, la page web et se connecte au WiFi de la maison.
//**********************************************************************************************************************************************

//Inclusion de bibliothèques
#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>

// --- CONFIGURATION WIFI (MODIFICATION ICI) ---
// Remplacez ces valeurs par celles de votre réseau (le même que le Zumi)
const char* ssid = "zumi-robot";      // ⚠️ Mettre le nom de votre WiFi ici
const char* password = "zumirobot";  // ⚠️ Mettre le mot de passe de votre WiFi ici

ESP8266WebServer server(80);

//Définition des GPIOS
#define LedVert 5
#define LedRouge 16
#define Moteur 13
#define IRAvant 14
#define IRArriere 12

//Définition de variables globales
bool etatLedVert = true;
bool etatLedRouge = false;
bool moteurActif = false;
bool porteOuverte = true; //La porte doit être ouverte avant d'alimenter le ESP8266. L'initialisation fermera la porte
bool lumiereModeAuto = true;
bool moteurModeAuto = true;
bool attenteAvantFermeturePorte = false;
bool attenteAvantOuverturePorte = false;
bool demandeOuverture = false;
bool demandeFermeture = false;
unsigned long ledTemps = 0;
unsigned long delaiPorte = 0;
const unsigned long delaiEntreOuvertureFermeturePorte = 5000;
const int tempsPulseMoteurOuvrir = 116; //110 avec alimentation ordinateur, 116 avec batterie portative
const int tempsPulseMoteurFermer = 130; //120 avec alimentation ordinateur, 130 avec batterie portative
const int tempsLedRouge = 5000;
const int tempsLedVert = 10000;

//**********************************************************************************************************************************************
// Fonction: PageWeb()
// Description: Construction de la page Web (Code original de Dany Lauzon)
//**********************************************************************************************************************************************

/***************************************
 * NOTE IMPORTANTE SUR LA PAGE WEB :
 * - Voir si il est vraiment ncessaire de faire un serveur web pour le pont.
 *   Comme le zumi est celui qui host le serveur principal celui-ci ne sert a rien.
*/
String PageWeb()
{
  String html = "<!DOCTYPE html><html lang=\\\"en\\\">";
  html += "<head><meta charset=\\\"UTF-8\\\"><meta name=\\\"viewport\\\" content=\\\"width=device-width, initial-scale=1\\\">";
  html += "<title>Interface Zumi - Pont</title><link rel=\\\"icon\\\" href=\\\"data:,\\\">"; // Titre légèrement modifié

  //CSS (Définition des styles - Conservé tel quel)
  html += "<style>";
  html += ".body {margin: 0; padding: 0; width: 100vw; height: 100vh; box-sizing: border-box; overflow: hidden; font-family: Arial, sans-serif; display: flex; flex-direction: column; }";
  html += ".container { display: flex; background-color: turquoise; padding: clamp(10px, 2vw, 20px); gap: clamp(15px, 3vw, 40px); height: calc(100vh - clamp(10px, 2vw, 20px) * 2); box-sizing: border-box; }";
  html += ".left-panel, .right-panel { display: flex; flex-direction: column; gap: clamp(10px, 2vw, 20px); flex-grow: 1; flex-basis: 0; min-width: 300px; height: 100%; }";
  html += ".left-panel { display: flex; flex-direction: column; flex: 1.5; min-width: 300px; height: 100%; gap: clamp(10px, 2vh, 15px); }";
  html += ".left-panel > .spacer { flex-grow: 0.01; }";
  html += ".right-panel { display: flex; flex-direction: column; flex: 1; min-width: 300px; height: 100%; }";
  html += ".live-feed { background-color: black; color: white; border: 5px solid white; border-radius: 30px; width: 100%; flex-grow: 10; display: flex; justify-content: center; align-items: center; min-height: 0; }";
  html += ".live-feed h2 { font-size: clamp(1.2rem, 2.5vw, 2.5rem); margin: 0; padding: 0; }";
  html += ".scenario { background-color: #dca0ee; color: black; display: flex; flex-wrap: wrap; justify-content: center; align-items: center; border: 5px solid white; border-radius: 30px; gap: clamp(5px, 1vw, 15px); padding: clamp(5px, 1vw, 12px); }";
  html += ".scenario h3 { margin: 0; font-size: clamp(0.8em, 2vw, 1.8em); display: flex; align-items: center; height: 100%; }";
  html += ".button-choix-scenario { border: none; color: white; background-color: black; padding: clamp(6px, 1vw, 12px) clamp(12px, 1.8vw, 20px); text-align: center; text-decoration: underline; display: flex; justify-content: center; align-items: center; font-size: clamp(1rem, 1.8vw, 1.8rem); cursor: pointer; border-radius: 50%; min-width: clamp(35px, 5.5vw, 55px);  min-height: clamp(35px, 5.5vw, 55px);  flex-shrink: 1; }";
  html += ".button-choix-scenario:hover { background-color: #2b2b2b; color: white; transform: scale(1.05); box-shadow: 3px 3px 8px rgba(0, 0, 0, 0.5) }";
  html += ".title-section, .title-section h1 { display: flex; justify-content: center; align-items: center; text-align: center; color: white; font-family: 'Chalkboard SE', cursive; font-size: clamp(2rem, 5vw, 4rem);  text-shadow: 3px 3px black; border: none; line-height: 0; height: fit-content; padding-bottom: clamp(2px, 0.5vw, 5px); flex-shrink: 0; }";
  html += ".commands-section { background-color: wheat; border: 5px solid white; border-radius: 30px; padding: clamp(8px, 1.5vw, 15px) 0; flex-grow: 1; display: flex; flex-direction: column; align-items: center; }";
  html += ".commands-section h2 { margin: 0; padding: 0; margin-bottom: clamp(6px, 1vw, 12px); text-align: center; width: 100%; font-size: clamp(1.4rem, 2.2vw, 1.8rem); flex-shrink: 0; }";
  html += ".command-category { display: flex; flex-direction: column; align-items: center; width: 100%; max-width: 450px;  gap: clamp(3px, 0.7vw, 15px);  padding-bottom: clamp(6px, 1vw, 25px);  border-bottom: 1px solid rgba(0, 0, 0, 0.2); flex-shrink: 1;  min-height: 0; margin-bottom: 0;  border-bottom: none; gap:clamp(10px, 1vw, 30px); }";
  html += ".command-category-title { text-align: center; margin: 0; color: white; background-color: #444; padding: clamp(3px, 0.7vw, 6px) clamp(6px, 1.2vw, 10px); border-radius: 15px;font-size: clamp(0.8rem, 1.3vw, 1rem);  font-weight: bold; text-transform: uppercase; width: fit-content; flex-shrink: 0; }";
  html += ".manual-button-row { display: grid; grid-template-columns: 1fr clamp(20px, 4vw, 60px) 1fr; grid-template-rows: clamp(20px, 4vw, 60px) clamp(30px, 4vw, 60px) clamp(20px, 4vw, 60px); justify-items: center; align-items: center; max-width: 200px; max-height: 160px; width: 100%; height: 100%; position: relative; margin-top: clamp(3px, 0.7vw, 8px); padding-bottom: clamp(5px, 1vw, 15px); flex-shrink: 1; }";
  html += ".manual-button-row .button-manual { grid-area: 2 / 2 / 3 / 3; z-index: 1; }";
  html += ".manual-button-row .arrow-up { grid-area: 1 / 2 / 2 / 3; }";
  html += ".manual-button-row .arrow-left { grid-area: 2 / 1 / 3 / 2; }";
  html += ".manual-button-row .arrow-right { grid-area: 2 / 3 / 3 / 4; }";
  html += ".manual-button-row .arrow-down { grid-area: 3 / 2 / 4 / 3; }";
  html += ".button-row { display: flex; justify-content: center; align-items: center; width: 100%; padding: clamp(2px, 0.5vw, 6px) 0; gap: clamp(3px, 0.7vw, 8px); flex-wrap: wrap; flex-shrink: 1;  min-height: 0; }";
  html += ".command-button { width: clamp(35px, 6vw, 60px);  height: clamp(35px, 6vw, 60px); border-radius: 50%; border: 2px solid #333; color: white; display: flex; justify-content: center; align-items: center; font-size: clamp(0.5rem, 1vw, 0.8rem);  font-weight: bold; text-transform: uppercase; cursor: pointer; transition: background-color 0.3s ease, transform 0.1s ease, box-shadow 0.3s ease; box-shadow: 2px 2px 5px rgba(0, 0, 0, 0.3); flex-shrink: 0; }";
  html += ".command-button:hover { transform: scale(1.05); box-shadow: 3px 3px 8px rgba(0, 0, 0, 0.5); }";
  html += ".button-light-green { background-color: #4CAF50; }";
  html += ".button-light-red { background-color: #F44336; }";
  html += ".button-manual, .button-bridge { background-color: rgb(14, 14, 14); }";
  html += ".arrow-button { display: flex; justify-content: center; align-items: center; width: clamp(30px, 6vw, 60px); height: clamp(30px, 6vw, 60px); background-color: #262626; border-radius: 50%; position: relative; cursor: pointer; text-decoration: none; transition: box-shadow 0.3s ease, transform 0.1s ease; }";
  html += ".arrow-button:hover { box-shadow: 3px 3px 8px rgba(0, 0, 0, 0.5); transform: scale(1.05); }";
  html += ".arrow-icon { width: 0; height: 0; border-left: clamp(4px, 0.8vw, 10px) solid transparent;  border-right: clamp(4px, 0.8vw, 10px) solid transparent;  border-bottom: clamp(7px, 1.4vw, 12px) solid white;  position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); transition: transform 0.3s ease; }";
  html += ".arrow-up .arrow-icon { transform: translate(-50%, -50%) rotate(0deg); }";
  html += ".arrow-down .arrow-icon { transform: translate(-50%, -40%) rotate(180deg); }";
  html += ".arrow-left .arrow-icon { transform: translate(-50%, -50%) rotate(-90deg); }";
  html += ".arrow-right .arrow-icon { transform: translate(-40%, -50%) rotate(90deg); }";
  html += ".arrow-up:hover .arrow-icon { transform: translate(-50%, -50%) rotate(0deg) scale(1.1); }";
  html += ".arrow-down:hover .arrow-icon { transform: translate(-50%, -40%) rotate(180deg) scale(1.1); }";
  html += ".arrow-left:hover .arrow-icon { transform: translate(-50%, -50%) rotate(-90deg) scale(1.1); }";
  html += ".arrow-right:hover .arrow-icon { transform: translate(-40%, -50%) rotate(90deg) scale(1.1); }";
  html += ".switch-label { display: flex; align-items: center; gap: 8px; cursor: pointer; color: white; font-size: clamp(0.8rem, 1.2vw, 1.2rem); font-weight: bold; }";
  html += ".switch-label input[type='checkbox'] { display: none; }";
  html += ".check-switch { background-color: #111; width: clamp(35px, 6vw, 60px); height: clamp(35px, 6vw, 60px); border-radius: 50%; border: 2px solid #333; display: flex; justify-content: center; align-items: center; font-size: clamp(0.5rem, 1vw, 0.8rem); font-weight: bold; text-transform: uppercase; font-family: Arial, sans-serif; color: white; cursor: pointer; box-shadow: 2px 2px 5px rgba(0, 0, 0, 0.3); user-select: none; }";
  html += "input[type='checkbox']:checked + .check-switch { background-color: #4CAF50; color: white; }";
  html += ".disabled { opacity: 0.5; pointer-events: none; }";
  html += "</style>";

  //HTML (Définition de la page web)
  html += "</head><body>";
  html += "<div class='container'> ";
  html += "<div class='left-panel'> ";
  html += "<div class='live-feed'> ";
  html += " <h2>LIVE FEED</h2> ";
  html += "</div> ";
  html += "<div class='spacer'></div>";
  html += "<div class='scenario'> ";
  html += "<h3>Choix du scenario :</h3> ";
  html += "<button class='button-choix-scenario' id='btnscenario1'>1</button> ";
  html += "<button class='button-choix-scenario' id='btnscenario2'>2</button> ";
  html += "<button class='button-choix-scenario' id='btnscenario3'>3</button> ";
  html += "<button class='button-choix-scenario' id='btnscenario4'>4</button> ";
  html += "</div> ";
  html += "</div> ";
  html += "<div class='right-panel'> ";
  html += "<div class='title-section'> ";
  html += "<h1>Zumi</h1> ";
  html += "</div> ";
  html += "<div class='commands-section'> "; 
  html += "<h2>Commandes</h2>"; 

  //Section Manuel
  html += "<div class='command-category'> ";
  html += "<h3 class='command-category-title'>Manuel</h3> ";
  html += "<div class='button-row'> ";
  html += "<button class='command-button button-manual' id='btnmanuel' style='grid-area: 2 / 2 / 3 / 3; transform: translateY(-8px);'>auto</button>";
  html += "<div class='manual-button-row'> ";
  html += "<div class='arrow-button arrow-up'><div class='arrow-icon'></div></div> ";
  html += "<div class='arrow-button arrow-left'><div class='arrow-icon'></div></div> ";
  html += "<div class='arrow-button arrow-right'><div class='arrow-icon'></div></div> ";
  html += "<div class='arrow-button arrow-down'><div class='arrow-icon'></div></div> ";
  html += "</div> ";
  html += "</div> ";
  html += "</div> ";

 //Section Lumières
  html += "<div class='command-category'>";
  html += "<h3 class='command-category-title'>Lumieres</h3>";
  html += "<div class='button-row'>";
  html += "<label class='switch-label'>";
  html += "<input type='checkbox' id='autoLed' onchange='majModeLed(this.checked)' ";
  html += lumiereModeAuto ? "checked" : "";
  html += "><span class='check-switch'>auto</span>";
  html += "</label>";                             
  
  if (lumiereModeAuto) 
  {
    html += "<button class='command-button button-light-green disabled' id='btnVert'>Vert</button>";
    html += "<button class='command-button button-light-red disabled' id='btnRouge'>Rouge</button>";
  } else 
  {
    html += "<a href='/vert'><button class='command-button button-light-green' id='btnVert'>Vert</button></a>";
    html += "<a href='/rouge'><button class='command-button button-light-red' id='btnRouge'>Rouge</button></a>";
  }
  html += "</div>";
  html += "</div>";

  //Section Moteurs 
  html +="<div class='command-category'>";
  html +="<h3 class='command-category-title'>Pont</h3>";
  html +="<div class='button-row'>";
  html += "<label class='switch-label'>";
  html += "<input type='checkbox' id='autoMoteur' onchange='majModeMoteur(this.checked)' ";
  html += moteurModeAuto ? "checked" : "";
  html += "><span class='check-switch'>auto</span>";
  html += "</label>";

  if (moteurModeAuto) 
  {
    html += "<button class='command-button button-bridge disabled' id='btnOuvrir'>Ouvrir</button>";
    html += "<button class='command-button button-bridge disabled' id='btnFermer'>Fermer</button>";
  } else 
  {
    html += "<a href='/ouvrir'><button class='command-button button-bridge' id='btnOuvrir'>Ouvrir</button></a>";
    html += "<a href='/fermer'><button class='command-button button-bridge' id='btnFermer'>Fermer</button></a>";
  }
  html += "</div>";
  html += "</div>";  
  html += "</div>";

  //JavaScript
  html += "<script>";
  html += "function majModeLed(etat) {";
  html += "fetch('/majAutoLed?etat=' + (etat ? '1' : '0'))";
  html += ".then(() => {";
  html += "document.getElementById('btnVert').classList.toggle('disabled', etat);";
  html += "document.getElementById('btnRouge').classList.toggle('disabled', etat);";
  html += "if (!etat) { window.location.href = '/'; }";
  html += "});";
  html += "}";
  html += "function majModeMoteur(etat) {";
  html += "fetch('/majAutoMoteur?etat=' + (etat ? '1' : '0'))";
  html += ".then(() => {";
  html += "document.getElementById('btnOuvrir').classList.toggle('disabled', etat);";
  html += "document.getElementById('btnFermer').classList.toggle('disabled', etat);";
  html += "if (!etat) { window.location.href = '/'; }";
  html += "});";
  html += "}";
  html += "</script>";

  html += "</body></html>";
  return html;
}

//**********************************************************************************************************************************************
// Fonction: TournerMoteur()
// Description: Contrôle du moteur
//**********************************************************************************************************************************************
void TournerMoteur(bool sens) 
{
  int pulse=0;

  if(sens && !porteOuverte)
  {
    pulse = 2000; //Vmax antihoraire
    moteurActif = true;

    for (int i = 0; i < tempsPulseMoteurOuvrir; i++) 
    {
      EnvoyerPulse(Moteur, pulse);
      delay(20);
    }
    porteOuverte = true;
  }
  else if (!sens && porteOuverte)
  {
    pulse = 1000; //Vmax horaire
    moteurActif = true;

    for (int i = 0; i < tempsPulseMoteurFermer; i++) 
    {
      EnvoyerPulse(Moteur, pulse);
      delay(20);
    }
    porteOuverte = false;
  }
  moteurActif = false;
}

//**********************************************************************************************************************************************
// Fonction: EnvoyerPulse()
// Description: Simule PWM
//**********************************************************************************************************************************************
void EnvoyerPulse(int pin, int microsec) 
{
  digitalWrite(pin, HIGH);
  delayMicroseconds(microsec);
  digitalWrite(pin, LOW);
}

//**********************************************************************************************************************************************
// Fonction: Setup()
// Description: Initialisation et CONNEXION WIFI (Modifiée)
//**********************************************************************************************************************************************
void setup() 
{
  Serial.begin(115200);

  // --- MODIFICATION : CONNEXION WIFI (MODE STATION) AU LIEU DE AP ---
  Serial.println();
  Serial.print("Connexion au WiFi: ");
  Serial.println(ssid);

  WiFi.mode(WIFI_STA); // Mode Station (Client)
  WiFi.begin(ssid, password);

  // Attente de la connexion
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("");
  Serial.println("WiFi connecte!");
  Serial.print("Adresse IP du Pont : ");
  Serial.println(WiFi.localIP()); 
  // ⚠️ UTILISEZ CETTE IP POUR CONFIGURER VOTRE CODE PYTHON SUR LE ZUMI ⚠️
  // ------------------------------------------------------------------

  server.begin();
  server.enableCORS(true); // Ajout important pour permettre au Zumi de communiquer facilement
  
  server.on("/", []() { server.send(200, "text/html", PageWeb());});

  pinMode(LedVert, OUTPUT);
  pinMode(LedRouge, OUTPUT);
  pinMode(Moteur, OUTPUT);
  pinMode(IRAvant, INPUT_PULLUP);
  pinMode(IRArriere, INPUT_PULLUP);

  digitalWrite(LedVert,HIGH);
  digitalWrite(LedRouge,LOW);
  TournerMoteur(false);
  attenteAvantOuverturePorte = true;

  //Routes pour les boutons manuels
  server.on("/ouvrir", []() 
  {
    if (!moteurModeAuto) 
    {
      TournerMoteur(true);
    }
    server.send(200, "text/html", PageWeb());
  });

  server.on("/fermer", []() 
  {
    if (!moteurModeAuto) 
    {
      TournerMoteur(false);
    }
    server.send(200, "text/html", PageWeb());
  });

  server.on("/vert", []() 
  {
    if (!lumiereModeAuto) 
    {
      digitalWrite(LedVert, HIGH);
      digitalWrite(LedRouge, LOW);
    }
    server.send(200, "text/html", PageWeb());
  });

  server.on("/rouge", []() 
  {
    if (!lumiereModeAuto) 
    {
      digitalWrite(LedVert, LOW);
      digitalWrite(LedRouge, HIGH);
    }
    server.send(200, "text/html", PageWeb());
  });

  //Routes pour changer le mode auto des lumières et moteur
  server.on("/majAutoLed", []() 
  {
    if (server.hasArg("etat")) 
    {
      lumiereModeAuto = (server.arg("etat") == "1");
    }
    server.send(200, "text/plain", "Superbe");
  });

  server.on("/majAutoMoteur", []() 
  {
    if (server.hasArg("etat")) 
    {
      moteurModeAuto = (server.arg("etat") == "1");
      if (!moteurModeAuto)
      {
        attenteAvantFermeturePorte = false;
        attenteAvantOuverturePorte = false;
        demandeFermeture = false;
        demandeOuverture = false;
      }
    }
    server.send(200, "text/plain", "C'est fait!");
  });
}

//**********************************************************************************************************************************************
// Fonction: loop()
// Description: Programme principal (Gestion automatique)
//**********************************************************************************************************************************************
void loop() 
{
  bool irAvant = digitalRead(IRAvant); //LOW -> Détection, HIGH -> Aucune détection
  bool irArriere = digitalRead(IRArriere); //LOW -> Détection, HIGH -> Aucune détection
  bool LedSwitch = false;
  server.handleClient();

  //Gestion automatique des lumières
  if(lumiereModeAuto)
  {
    if(etatLedVert && !LedSwitch)
    {
      if(millis()-ledTemps>=tempsLedVert)
      {
        digitalWrite(LedVert,LOW);
        digitalWrite(LedRouge,HIGH);
        etatLedVert = false;
        etatLedRouge = true;
        LedSwitch = true;
        ledTemps = millis();
      }
    }
    if(etatLedRouge && !LedSwitch)
    {
      if(millis()-ledTemps>=tempsLedRouge)
      {
        digitalWrite(LedRouge,LOW);
        digitalWrite(LedVert,HIGH);
        etatLedVert = true;
        etatLedRouge = false;
        LedSwitch = true;
        ledTemps = millis();
      }
    }
  }

  //Gestion automatique de la porte
  if(moteurModeAuto)
  {
    if(attenteAvantOuverturePorte && millis()-delaiPorte <= delaiEntreOuvertureFermeturePorte) //Mise en mémoire d'une demande d'ouverture si pendant délai
    {
      if(!irAvant)
      {
        demandeOuverture = true;
      }
    }
    if(attenteAvantFermeturePorte && millis()-delaiPorte <= delaiEntreOuvertureFermeturePorte) //Mise en mémoire d'une demande de fermeture si pendant délai
    {
      if(!irArriere)
      {
        demandeFermeture = true;
      }
    }
    if(attenteAvantOuverturePorte && millis()-delaiPorte >= delaiEntreOuvertureFermeturePorte) //Réinitialisation des attentes pour ouverture
    {
        attenteAvantOuverturePorte = false;
    }
    if(attenteAvantFermeturePorte && millis()-delaiPorte >= delaiEntreOuvertureFermeturePorte) //Réinitialisation des attentes pour fermeture
    {
        attenteAvantFermeturePorte = false;
    }
    if((!irAvant || demandeOuverture) && !porteOuverte && !moteurActif && !attenteAvantOuverturePorte) //Ouvrir
    {
      TournerMoteur(true);
      attenteAvantFermeturePorte = true;
      delaiPorte = millis();
      demandeOuverture = false;
    }
    if((!irArriere || demandeFermeture) && porteOuverte && !moteurActif && !attenteAvantFermeturePorte) //Fermer
    {
      TournerMoteur(false);
      attenteAvantOuverturePorte = true;
      delaiPorte = millis();
      demandeFermeture = false;
    }
  }  
}