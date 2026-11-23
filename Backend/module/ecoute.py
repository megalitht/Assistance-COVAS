"""
ecoute.py — Met l'écoute du COVAS en pause.

Levée tant que le studio vocal est ouvert dans les réglages : une réplique lue au micro
(« Covas par-ci... ») ne doit pas devenir une commande, et le COVAS ne doit pas prendre la
parole pendant une prise. Module sans dépendance, importable avant le chargement du COVAS.
"""
import threading

PAUSE = threading.Event()
