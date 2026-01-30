// Code Arduino pour Pont et Lumières - Mode Esclave
#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>

const char* ssid = "ZumiAccessoire"; // Le nom du réseau Wi-Fi créé
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
  
  // Configuration du Point d'Accès (Le Zumi se connectera ici)
  WiFi.softAP(ssid);
  IPAddress myIP = WiFi.softAPIP();
  Serial.print("Adresse IP du Pont: ");
  Serial.println(myIP); // Devrait être 192.168.4.1

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

  // --- Routes API (commandées par le Zumi) ---
  
  server.on("/", []() {
    server.send(200, "text/plain", "Pont est en ligne. Connectez-vous au Zumi pour le controler.");
  });

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
}

void loop() {
  server.handleClient();
  // Note: J'ai retiré la logique automatique complexe pour cet exemple 
  // afin de garantir que les commandes manuelles du Zumi fonctionnent en priorité.
}