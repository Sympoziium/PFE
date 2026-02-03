#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>

// --- CONFIGURATION WIFI (DOIT ÊTRE LE MÊME QUE LE ZUMI) ---
const char* ssid = "dlink-8D39";      // ⚠️ Mettre le nom de votre WiFi ici
const char* password = "xdvxj79799";  // ⚠️ Mettre le mot de passe de votre WiFi ici

ESP8266WebServer server(80);

// Définition des GPIOS
#define LedVert 5
#define LedRouge 16
#define Moteur 13
#define IRAvant 14
#define IRArriere 12

// Variables
bool porteOuverte = true;
const int tempsPulseMoteurOuvrir = 116;
const int tempsPulseMoteurFermer = 130;

void TournerMoteur(bool sens) {
  int pulse = 0;
  if (sens && !porteOuverte) { // Ouvrir
    pulse = 2000;
    for (int i = 0; i < tempsPulseMoteurOuvrir; i++) {
      EnvoyerPulse(Moteur, pulse);
      delay(20);
    }
    porteOuverte = true;
  } else if (!sens && porteOuverte) { // Fermer
    pulse = 1000;
    for (int i = 0; i < tempsPulseMoteurFermer; i++) {
      EnvoyerPulse(Moteur, pulse);
      delay(20);
    }
    porteOuverte = false;
  }
}

void EnvoyerPulse(int pin, int microsec) {
  digitalWrite(pin, HIGH);
  delayMicroseconds(microsec);
  digitalWrite(pin, LOW);
}

void setup() {
  Serial.begin(115200);
  
  // --- Connexion au Wi-Fi (Mode Station) ---
  Serial.println();
  Serial.print("Connexion a ");
  Serial.println(ssid);

  WiFi.mode(WIFI_STA); // Important : Mode Station pour rejoindre un réseau existant
  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("");
  Serial.println("WiFi connecte");
  Serial.print("Adresse IP du Pont : ");
  Serial.println(WiFi.localIP()); 
  // ⚠️ NOTEZ CETTE IP POUR LA METTRE DANS server_controller.py ⚠️

  // Configuration des Pins
  pinMode(LedVert, OUTPUT);
  pinMode(LedRouge, OUTPUT);
  pinMode(Moteur, OUTPUT);
  pinMode(IRAvant, INPUT_PULLUP);
  pinMode(IRArriere, INPUT_PULLUP);

  // État initial
  digitalWrite(LedVert, HIGH);
  digitalWrite(LedRouge, LOW);
  TournerMoteur(false); // Ferme la porte au démarrage

  // --- Routes API ---
  server.on("/", []() {
    server.send(200, "text/plain", "Le Pont est en ligne (Mode Station).");
  });

  // Activation des headers CORS pour permettre les requêtes depuis le Zumi si nécessaire
  server.enableCORS(true); 

  server.on("/ouvrir", []() {
    TournerMoteur(true);
    server.send(200, "text/plain", "OK");
  });

  server.on("/fermer", []() {
    TournerMoteur(false);
    server.send(200, "text/plain", "OK");
  });

  server.on("/vert", []() {
    digitalWrite(LedVert, HIGH);
    digitalWrite(LedRouge, LOW);
    server.send(200, "text/plain", "OK");
  });

  server.on("/rouge", []() {
    digitalWrite(LedVert, LOW);
    digitalWrite(LedRouge, HIGH);
    server.send(200, "text/plain", "OK");
  });

  server.begin();
  Serial.println("Serveur HTTP demarre");
}

void loop() {
  server.handleClient();
}