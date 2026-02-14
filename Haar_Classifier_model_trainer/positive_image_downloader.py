# positive_image_downloader.py
# Ce scipt sert à télécharger massivement des images en ligne. 
# Il utilise la bibliothèque icrawler `pip install icrawler` pour faire le travail.
# pour l'utiliser, il suffit de lancer ce script et modifier les requêtes 
# dans la liste `queries` pour correspondre à ce que vous voulez télécharger.
# il va créer un dossier "positives" avec des sous-dossiers pour chaque requête, 
# contenant les images téléchargées il suffit ensuite de faire le tri manuel 
# pour ne garder que les images positives (celles qui contiennent le sujet d'intérêt) 
# et les mettre dans le dossier "data/positive" pour la suite du pipeline.

from icrawler.builtin import BingImageCrawler

crawler = BingImageCrawler(
    storage={'root_dir': 'positives'},
)

queries = [
    
"minifigure lego sfondo bianco foto", 
"minifigure lego in piedi vista frontale", 
"minifigure lego isolata foto", 
"minifigure lego vista laterale foto", 
"minifigure lego vista posteriore foto"


]

for q in queries:
    crawler = BingImageCrawler(
        storage={'root_dir': f'positives/{q.replace(" ", "_")}'}
    )

    crawler.crawl(
        keyword=q,
        max_num=50,
        filters={
            'type': 'photo',
            'size': 'medium'
        }
    )