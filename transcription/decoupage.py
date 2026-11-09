"""Découpage des enregistrements longs, comme Handy v0.10.0 (src-tauri/src/audio_toolkit/chunking.rs).

Jusqu'à 40 s : un seul morceau. Au-delà : coupes au milieu des pauses, morceaux de 5 s au moins, 30 s visés ;
sans pause utilisable, coupe franche à 40 s (ou à mi-chemin si le reste ferait moins de 5 s).
Pas de chevauchement : chaque morceau est transcrit seul, puis les textes sont joints par une espace.
"""
TAUX = 16000
UN_SEUL = 40 * TAUX
MINIMUM = 5 * TAUX
CIBLE = 30 * TAUX
MAXIMUM = 40 * TAUX


def pauses(segments, longueur):
    """Pauses (début, fin) en échantillons, entre les segments de parole donnés par Silero."""
    resultat, fin_prec = [], 0
    for s in segments:
        if s.start_sample > fin_prec:
            resultat.append((fin_prec, s.start_sample))
        fin_prec = max(fin_prec, s.end_sample)
    if fin_prec < longueur:
        resultat.append((fin_prec, longueur))
    return resultat


def _score(pause_echantillons, position):
    """Pause longue (plafonnée à 1 s) préférée ; pénalité selon l'écart à 30 s."""
    duree = min(pause_echantillons / TAUX, 1.0)
    pos = position / TAUX
    return duree - (0.05 * (30 - pos) if pos < 30 else 0.1 * (pos - 30))


def coupes(longueur, liste_pauses):
    """Positions de coupe (en échantillons) pour un enregistrement de `longueur` échantillons."""
    if longueur <= UN_SEUL:
        return []
    resultat, debut = [], 0
    while longueur - debut > UN_SEUL:
        meilleure, score_max = None, float("-inf")
        for p0, p1 in liste_pauses:
            milieu = (p0 + p1) // 2
            taille = milieu - debut
            if taille < MINIMUM or taille > MAXIMUM or longueur - milieu < MINIMUM:
                continue
            s = _score(p1 - p0, taille)
            if s > score_max:
                meilleure, score_max = milieu, s
        if meilleure is None:
            meilleure = debut + MAXIMUM
            if longueur - meilleure < MINIMUM:
                meilleure = debut + (longueur - debut) // 2
        resultat.append(meilleure)
        debut = meilleure
    return resultat
