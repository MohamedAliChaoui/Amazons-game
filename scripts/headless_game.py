import time
import os
import sys

# Ajouter le dossier racine au path pour les imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from amazons.model.board.board import Board
from amazons.model.players.ai_player import AIPlayer

class HeadlessGame:
    def __init__(self, size=10, time_limit_sec=60.0, turn_limit_sec=5.0):
        self.size = size
        self.time_limit = float(time_limit_sec)
        self.turn_limit = float(turn_limit_sec)

    def play_match(self, white_mode, black_mode, white_depth=None, black_depth=None, white_eval="hybrid", black_eval="hybrid"):
        """
        Joue une partie IA vs IA sans aucun affichage (headless)
        Retourne un dictionnaire avec les stats du match.
        """
        board = Board(self.size)
        timers = {'white': self.time_limit, 'black': self.time_limit}
        
        # Rediriger stdout temporairement pour couper les prints internes des IAs
        original_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')
        
        try:
            player_w = AIPlayer("W", "white", ai_mode=white_mode, ai_depth=white_depth, ai_evaluator=white_eval)
            player_b = AIPlayer("B", "black", ai_mode=black_mode, ai_depth=black_depth, ai_evaluator=black_eval)
            joueurs = [player_w, player_b]
            
            joueur_actuel = 0
            tour = 0
            stats = {
                "vainqueur": None,
                "raison": None,
                "score_blancs": 0,
                "score_noirs": 0,
                "coups": 0,
                "temps_blancs": 0.0,
                "temps_noirs": 0.0,
                "erreur": None
            }

            while True:
                joueur = joueurs[joueur_actuel]
                color_code = 'W' if joueur.couleur == "white" else 'B'
                color_key = joueur.couleur

                # --- VÉRIFICATION DU BLOCAGE ---
                if not list(board.get_legal_moves(color_code)):
                    stats["vainqueur"] = "black" if color_key == "white" else "white"
                    stats["raison"] = "bloque"
                    break

                start_time = time.time()
                
                # --- TOUR IA ---
                think_budget = min(self.turn_limit, timers[color_key])
                move = joueur.get_action(board, think_budget)
                
                elapsed = time.time() - start_time
                timers[color_key] -= elapsed
                
                if color_key == "white":
                    stats["temps_blancs"] += elapsed
                else:
                    stats["temps_noirs"] += elapsed

                if timers[color_key] <= 0:
                    stats["vainqueur"] = "black" if color_key == "white" else "white"
                    stats["raison"] = "temps ecoule"
                    break

                if move:
                    board.make_move(move, color_code)
                    stats["coups"] += 1
                else:
                    stats["vainqueur"] = "black" if color_key == "white" else "white"
                    stats["raison"] = "aucun coup legal"
                    break

                joueur_actuel = 1 - joueur_actuel
                tour += 1

            # Calcul des scores finaux de territoire
            score_w, score_b = board.calculate_territory_scores()
            stats["score_blancs"] = score_w
            stats["score_noirs"] = score_b

        except Exception as e:
            stats["erreur"] = str(e)
            stats["vainqueur"] = "erreur"
            stats["raison"] = "exception"
        
        finally:
            # Restaurer stdout
            sys.stdout.close()
            sys.stdout = original_stdout

        return stats
