"""
service.py — Les données externes vues par le reste du COVAS : chaque demande part en tâche de fond,
avec une limite de temps ; l'état (pour l'interface, ETAT["externe"]) passe par la fonction
`publier`. Une panne ne bloque rien : la partie concernée affiche « Données indisponibles ».

  systeme(nom)               fiche EDSM du système où l'on arrive (stations, corps, valeur)
  tracer(demande, ...)       route Spansh (neutron ou galaxie) demandée depuis l'interface
  inara(commandant)          profil Inara, seulement avec une clé
Réglages : data/config.toml [externe].
"""
import asyncio

from module.externe import edsm, inara, spansh
from module.externe.cache import Cache
from module.externe.reseau import ErreurExterne

INDISPONIBLE = "Données indisponibles"


def etat_vierge():
    return {"systeme": {"etat": "attente"}, "route": None, "inara": None}


class ServiceExterne:
    def __init__(self, reglages, publier, cache=None):
        self.reglages = reglages              # fonction : section [externe] de config.toml
        self.publier = publier                # async fonction(etat) : met à jour l'interface
        self.cache = cache
        self.etat = etat_vierge()
        self._taches = set()
        self._systeme_demande = None

    # ---------- Outils ----------
    def _actif(self, service):
        r = self.reglages()
        return bool(r.get("actif")) and bool(r.get(service, True))

    def _delai(self):
        return max(1, min(30, self.reglages().get("delai_secondes") or 5))

    def _cache(self):
        if self.cache is None:
            try:
                self.cache = Cache(edsm_chemin_cache())
                self.cache.purger()
            except Exception as erreur:          # disque plein, droits... : sans cache
                print(f"[Externe] Cache indisponible ({erreur!r}) : sans cache.")
                self.cache = Cache()
        return self.cache

    def lancer(self, coroutine):
        """Tâche de fond (gardée en référence, ses erreurs sont affichées, jamais propagées)."""
        tache = asyncio.create_task(coroutine)
        self._taches.add(tache)
        tache.add_done_callback(self._fin)
        return tache

    def _fin(self, tache):
        self._taches.discard(tache)
        if not tache.cancelled() and tache.exception():
            print(f"[Externe] Erreur : {tache.exception()!r}")

    async def _en_fond(self, fonction, *args, marge=2, **kwargs):
        """Fonction bloquante dans un thread, avec une limite de temps."""
        limite = kwargs.pop("limite", self._delai() * 3 + marge)
        return await asyncio.wait_for(asyncio.to_thread(fonction, *args, **kwargs), limite)

    # ---------- EDSM : fiche du système ----------
    async def systeme(self, nom, estimation_covas=None):
        if not nom:
            return
        if not self._actif("edsm"):
            self.etat["systeme"] = {"etat": "desactive", "systeme": nom}
            await self.publier(self.etat)
            return
        self._systeme_demande = nom
        self.etat["systeme"] = {"etat": "recherche", "systeme": nom}
        await self.publier(self.etat)
        duree = (self.reglages().get("cache_heures") or 12) * 3600
        try:
            fiche = await self._en_fond(edsm.fiche_systeme, nom, self._delai(), self._cache(), duree)
            fiche["etat"] = "ok" if fiche["connu"] else ("inconnu" if not fiche["erreurs"] else "indisponible")
        except (ErreurExterne, asyncio.TimeoutError, OSError) as erreur:
            fiche = {"etat": "indisponible", "systeme": nom, "erreurs": [str(erreur) or "délai dépassé"]}
        if self._systeme_demande != nom:
            return                                # on a ressauté entre-temps
        fiche["estimation_covas"] = estimation_covas
        self.etat["systeme"] = fiche
        await self.publier(self.etat)

    # ---------- Spansh : route ----------
    async def tracer(self, demande, systeme_actuel, loadout):
        """demande : {"route": "neutron" | "galaxie", "destination": str, "efficacite": int}"""
        destination = str(demande.get("destination") or "").strip()[:80]
        genre = demande.get("route") if demande.get("route") in ("neutron", "galaxie") else "neutron"
        if not self._actif("spansh"):
            self.etat["route"] = {"etat": "desactive"}
        elif not destination or not systeme_actuel:
            self.etat["route"] = {"etat": "erreur", "message": "Destination ou position inconnue."}
        else:
            vaisseau = spansh.parametres_vaisseau(loadout)
            if not vaisseau:
                self.etat["route"] = {"etat": "erreur", "message": "FSD du vaisseau inconnu (Loadout pas encore lu)."}
            else:
                self.etat["route"] = {"etat": "recherche", "type": genre, "depart": systeme_actuel, "arrivee": destination}
                await self.publier(self.etat)
                # Portée : celle que le jeu écrit (MaxJumpRange) ; le calcul ne sert qu'à défaut (il dépasse
                # de 0,65 al celle du jeu pour un Python Mk II des journaux : des sauts seraient impossibles)
                portee_jeu = (loadout or {}).get("MaxJumpRange")
                portee_al = portee_jeu if isinstance(portee_jeu, (int, float)) and portee_jeu > 0 else spansh.portee(vaisseau)
                self.etat["route"] = await self._route(genre, systeme_actuel, destination, vaisseau, demande, portee_al)
        await self.publier(self.etat)

    async def _route(self, genre, depart, arrivee, vaisseau, demande, portee_al):
        delai = self._delai()
        try:
            if genre == "neutron":
                efficacite = max(1, min(100, int(demande.get("efficacite") or 60)))
                route = await self._en_fond(spansh.route_neutron, depart, arrivee, portee_al,
                                            efficacite, delai, limite=spansh.ATTENTE_MAX + delai * 2)
            else:
                route = await self._en_fond(spansh.route_galaxie, depart, arrivee, vaisseau, True, delai,
                                            limite=spansh.ATTENTE_MAX + delai * 2)
            route["etat"] = "ok" if route["etapes"] else "erreur"
            if not route["etapes"]:
                route["message"] = "Spansh n'a trouvé aucune route."
            route["portee"] = round(portee_al, 2)
            return route
        except (ErreurExterne, asyncio.TimeoutError, OSError, ValueError) as erreur:
            return {"etat": "erreur", "type": genre, "depart": depart, "arrivee": arrivee,
                    "message": f"{INDISPONIBLE} ({erreur or 'délai dépassé'})"}

    def oublier_route(self):
        self.etat["route"] = None

    # ---------- Inara ----------
    async def inara(self, commandant, forcer=False):
        reglages = self.reglages()
        cle = (reglages.get("inara_cle") or "").strip()
        nom = (reglages.get("inara_commandant") or "").strip() or commandant
        if not reglages.get("actif") or not cle or not nom:
            if self.etat["inara"] is not None:
                self.etat["inara"] = None
                await self.publier(self.etat)
            return
        cle_cache = f"inara:profil:{nom}"
        profil = None if forcer else self._cache().lire(cle_cache)
        if profil is None:
            try:
                profil = await self._en_fond(inara.profil, cle, nom, self._delai())
                self._cache().ecrire(cle_cache, profil, 3600)
            except (ErreurExterne, asyncio.TimeoutError, OSError) as erreur:
                profil = {"etat": "indisponible", "message": str(erreur) or "délai dépassé"}
        self.etat["inara"] = {"etat": "ok", **profil} if "etat" not in profil else profil
        await self.publier(self.etat)


def edsm_chemin_cache():
    from module.externe.cache import CHEMIN
    return CHEMIN
