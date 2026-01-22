# Procédure de modification du serveur flask

## Ajout d'un bouton

Voici la liste des ajouts à faire pour ajouter un nouveau bouton:

- Ajouter une **route** pour lié a une fonction de callback:
    ```python
    # Page principale de l'interface web
    @app.route('/nom_fonction')
    def nom_fonction():
        # ces ici qu'on gère le back end du serveur
        # on appelle les fonctions qu'on souhaite exécuter a l'appui du bouton.

    ```
- Ajouter le style du nouveau bouton dans le `<body>` du `HTML`.

    ```css
    /* Ajout du nouveau bouton */
    .nouveau-btn {
        background-color: #4caf50;
        color: white;
        border: none;
        border-radius: 10px;
        padding: 10px 20px;
        cursor: pointer;
        font-size: 16px;
    }
        
    .nouveau-btn:hover {
        background-color: #388e3c;
    }
    ```

- Ajouter la fonction *OnClick* dans le script JS.
    ```JS
    function OnClick_nouveau_btn() { 
        console.log("OnClick_nouveau_btn() appelée"); // pour debug

        fetch('/nom_fonction', { method: 'POST' }) // appel de la fonction callback associé au bouton 
            .then(response => response.json()) // attend la réponse du serveur et la convertie en json
            .catch(err => { alert('Erreur lors de lappel de la fonction : ' + err);
                console.log("Erreur lors de la communication avec le serveur : " + err); // pour debug
            });
    }
    ```
    ici on utilise les commandes request avec la fonction fetch pour intéragir avec le serveur. On sen sert principalement pour appeler les fonction de callback qui eux gère les api du robot. on peut également intéragir avec l'interface web en intéragissant avec les styles.

- Liaison du bouton à la fonction *OnClick* du script JS.
    ```python
    html += "<button class='nouveau-btn' id='nouveaubouton' onclick='OnClick_nouveau_btn()'>Texte affiché sur le bouton</button>" 
    ```
    c'est ici qu'on vient lier le style et la fonction *OnClic* qui elle appel les donction de callback.


