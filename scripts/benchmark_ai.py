import argparse
import sys
import os
import concurrent.futures
from collections import defaultdict
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts.headless_game import HeadlessGame

def play_single_match(args_tuple):
    """
    Fonction de travail pour le multiprocessing.
    args_tuple: (id_match, joueur_blanc, joueur_noir, taille_plateau, limite_temps)
    """
    match_id, p_white, p_black, size, time_limit, depth, turn_time = args_tuple
    
    game = HeadlessGame(size=size, time_limit_sec=time_limit, turn_limit_sec=turn_time)
    
    start_cpu = time.process_time()
    
            # Appel de la partie headless avec stdout ignoré
    stats = game.play_match(white_mode=p_white, black_mode=p_black, white_depth=depth, black_depth=depth)
    
    cpu_time = time.process_time() - start_cpu
    stats["cpu_time"] = cpu_time
    stats["id"] = match_id
    stats["p_blanc"] = p_white
    stats["p_noir"] = p_black
    
    return stats


def run_benchmark(p1, p2, games, size, time_limit, workers, depth, turn_time):
    print(f"=== BENCHMARK: {p1} vs {p2} ===")
    print(f"Parties: {games} | Plateau: {size}x{size} | Temps Global: {time_limit}s | Temps/Coup: {turn_time}s | Profondeur: {depth} | Threads: {workers}")
    print("Lancement des matchs en cours...\n")
    
    # Préparer les matchs (alterner les couleurs pour l'équité)
    tasks = []
    for i in range(games):
        if i % 2 == 0:
            tasks.append((i, p1, p2, size, time_limit, depth, turn_time))
        else:
            tasks.append((i, p2, p1, size, time_limit, depth, turn_time))
            
    results = []
    
    start_wall_time = time.time()
    
    # Exécution parallèle
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
        for stat in executor.map(play_single_match, tasks):
            results.append(stat)
            # Barre de progression simple
            sys.stdout.write(f"\rProgression : {len(results)}/{games}")
            sys.stdout.flush()
            
    wall_time = time.time() - start_wall_time
    print("\n\n=== RÉSULTATS ===")
    
    # Agrégation des statistiques
    wins = {p1: 0, p2: 0, "egalite/erreur": 0}
    reasons = defaultdict(int)
    total_moves = 0
    total_cpu_time = 0.0
    
    for r in results:
        w = r["vainqueur"]
        if w == "white":
            wins[r["p_blanc"]] += 1
        elif w == "black":
            wins[r["p_noir"]] += 1
        else:
            wins["egalite/erreur"] += 1
            
        reasons[r["raison"]] += 1
        total_moves += r["coups"]
        total_cpu_time += r["cpu_time"]
        
    print(f"\nMatch: {p1} vs {p2} ({games} parties)")
    print("-" * 30)
    print(f"Victoires {p1}: {wins[p1]} ({wins[p1]/games*100:.1f}%)")
    print(f"Victoires {p2}: {wins[p2]} ({wins[p2]/games*100:.1f}%)")
    print(f"Égalités/Erreurs: {wins['egalite/erreur']}")
    print("-" * 30)
    print("Raisons de victoire :")
    for reason, count in reasons.items():
        print(f" - {reason}: {count}")
    
    # Check for actual error messages if any
    errors_seen = set(r.get("erreur") for r in results if r.get("erreur"))
    if errors_seen:
        print("-" * 30)
        print("Détail des erreurs (exceptions) rencontrées :")
        for err in errors_seen:
            print(f" - {err}")
            
    print("-" * 30)
    print(f"Moyenne de coups par partie : {total_moves / games:.1f}")
    print(f"Temps CPU total (somme de tous les cœurs) : {total_cpu_time:.2f}s")
    print(f"Temps réel écoulé : {wall_time:.2f}s (Accélération x{total_cpu_time/wall_time:.1f})")
    print("==================\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark IA vs IA pour le Jeu des Amazones")
    parser.add_argument("--p1", type=str, default="random", choices=["random", "minimax", "iterative", "mcts"], help="Moteur IA 1")
    parser.add_argument("--p2", type=str, default="random", choices=["random", "minimax", "iterative", "mcts"], help="Moteur IA 2")
    parser.add_argument("-n", "--games", type=int, default=10, help="Nombre total de parties à jouer")
    parser.add_argument("--size", type=int, default=6, help="Taille du plateau (nxn)")
    parser.add_argument("--time", type=float, default=10.0, help="Limite de temps en secondes par joueur")
    parser.add_argument("--turn-time", type=float, default=5.0, help="Limite de temps en secondes par coup (défaut: 5.0)")
    parser.add_argument("--depth", type=int, default=2, help="Profondeur fixée pour l'IA Minimax (défaut: 2)")
    parser.add_argument("--workers", type=int, default=os.cpu_count(), help="Nombre de processus parallèles (par défaut: tous les cœurs)")
    
    args = parser.parse_args()
    
    run_benchmark(args.p1, args.p2, args.games, args.size, args.time, args.workers, args.depth, args.turn_time)
