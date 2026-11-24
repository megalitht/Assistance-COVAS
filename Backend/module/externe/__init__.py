"""
module/externe — Données venues d'Internet (EDSM, Spansh, Inara).

Le COVAS fonctionne sans : tout se désactive dans data/config.toml (section [externe]), chaque requête
a un délai court, tourne hors de la boucle principale (asyncio.to_thread) et une panne affiche
« Données indisponibles » sans rien bloquer (alertes, voix, macros).

  reseau.py  : requêtes HTTP (User-Agent du projet, délai, erreurs ramenées à ErreurExterne)
  cache.py   : cache local SQLite (data/suivi/cache_externe.sqlite) avec durée de vie
  edsm.py    : fiche du système (stations, corps, valeur estimée), systèmes à portée de saut
  spansh.py  : tracé de route neutron et « galaxy plotter » (API non documentée : tout est ici)
  inara.py   : profil du commandant, seulement avec une clé, 2 requêtes par minute au plus
  service.py : ce que lecteur_logs.py appelle (tâches de fond, état pour l'interface)
"""
