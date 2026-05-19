# py -m PyInstaller --onefile --noconsole --add-data "index.html;." main.py
# pyinstaller --onefile --noconsole --add-data "index.html:." main.py

import random
import time
import json
import os
import threading
import queue
import webview
import http.server
import socketserver
import socket
import sys

# Ensure PyInstaller finds the unpacked folder path on Linux
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    os.chdir(sys._MEIPASS)

CARD_NAMES = {
    1: "I (The Fool)", 2: "II (The Fly)", 3: "III (Spit)", 4: "IV (Winter)", 5: "V (Hunger)",
    16: "XVI (Home)", 17: "XVII (The Bride)", 18: "XVIII (Fire)", 19: "XIX (The Beast)", 20: "XX (The Well)"
}

ACHIEVEMENTS = {
    "first_plunge": {"name": "The First Plunge", "desc": "Play your first match of Pozzo."},
    "the_fool": {"name": "The Fool", "desc": "Stay silent with XX (The Well)"},
    "sunken_one": {"name": "The Sunken One", "desc": "Survive a game."},
    "awakened": {"name": "The Awakening", "desc": "Win a game with 18 or more total lives claimed."},
    "curse_survived": {"name": "'I See' Said the Blind Man", "desc": "Successfully guess an Odd/Even Blind Bet."},
    "beast_bitten": {"name": "Maul Mark", "desc": "Attempt to trade with the holder of XIX (The Beast)."},
    "well_spring": {"name": "Thirst Quenched", "desc": "Successfully declare 'Well!' and gain a life."},
    "double_slay": {"name": "Cursed End", "desc": "Die or lose someone due to a Cursed Execution (double damage)."},
    "unworthy_end": {"name": "Flesh to Dust", "desc": "Run out of lives and become Unworthy."},
    "serial_diver": {"name": "Obsession", "desc": "Play a total of 10 matches."}
}

DECKS = {
    1: {
        "name": "The Shallows",
        "desc": "The standard set. Balanced and forgiving. (Standard 40 cards)",
        "build": lambda: list(range(1, 21)) * 2
    },
    2: {
        "name": "The Murk",
        "desc": "Safety is scarce. Fewer Major Arcana to protect you. (35 cards)",
        "build": lambda: list(range(1, 16)) * 2 + list(range(16, 21))
    },
    3: {
        "name": "The Trench",
        "desc": "The Well is dry. The Beasts are multiplying. (40 cards)",
        "build": lambda: list(range(1, 19)) * 2 + [19, 19, 19, 19]
    },
    4: {
        "name": "The Abyss",
        "desc": "The Fool abandons you. Low cards swarm. Despair. (41 cards)",
        "build": lambda: list(range(2, 11)) * 3 + list(range(11, 19)) + [19, 19, 19, 19] + [20, 20]
    }
}

def card_str(val):
    return CARD_NAMES.get(val, f"Standard {val}")


class WebBridge:
    def __init__(self):
        self._input_queue = queue.Queue()
        self._window = None

    def submit_input(self, text):
        self._input_queue.put(text)

    def write(self, text):
        if self._window:
            self._window.evaluate_js(f"addText({json.dumps(text)});")

    def read(self, prompt=""):
        if prompt:
            self.write(prompt)
        if self._window:
            self._window.evaluate_js("requestInput();")
        return self._input_queue.get()

    def clear(self):
        if self._window:
            self._window.evaluate_js("clearOutput();")

    def set_window(self, window):
        self._window = window


class MetaManager:
    def __init__(self, bridge, filename="pozzo_stats.json"):
        self.bridge = bridge
        self.filename = filename
        self.stats = {
            "games_played": 0, "games_won": 0, "highest_score": 0,
            "net_life_force": 0, "successful_bets": 0, "failed_bets": 0,
            "beast_encounters": 0, "unlocked_achievements": [],
            "unlocked_decks": [1]
        }
        self.save_path = self.get_save_path()
        self.load_stats()
    
    def get_save_path(self):
        """Returns a persistent directory path outside of the temporary PyInstall folder."""
        if getattr(sys, 'frozen', False):
            user_home = os.path.expanduser("~")
            save_dir = os.path.join(user_home, ".pozzo")
        else:
            save_dir = os.path.dirname(os.path.abspath(__file__))

        os.makedirs(save_dir, exist_ok=True)
        return os.path.join(save_dir, self.filename)

    def load_stats(self):
        if os.path.exists(self.save_path):
            try:
                with open(self.save_path, "r") as f:
                    self.stats.update(json.load(f))
                    # Ensure pre-existing stats profiles default to having deck 1 unlocked
                    if "unlocked_decks" not in self.stats:
                        self.stats["unlocked_decks"] = [1]
                    # Convert to standard integers for consistency
                    self.stats["unlocked_decks"] = [int(x) for x in self.stats["unlocked_decks"]]
            except Exception:
                self.bridge.write("Corrupted save file. Starting fresh.\n")

    def save_stats(self):
        try:
            with open(self.save_path, "w") as f:
                json.dump(self.stats, f, indent=4)
        except Exception as e:
            self.bridge.write(f"Failed to access stats: {e}\n")

    def unlock_achievement(self, ach_id):
        if ach_id in ACHIEVEMENTS and ach_id not in self.stats["unlocked_achievements"]:
            self.stats["unlocked_achievements"].append(ach_id)
            self.bridge.write(f"\n>>> ACHIEVEMENT UNLOCKED: {ACHIEVEMENTS[ach_id]['name']} <<<\n")
            self.bridge.write(f"    ({ACHIEVEMENTS[ach_id]['desc']})\n\n")
            self.save_stats()
            time.sleep(2)


class PozzoGame:
    def __init__(self, meta_manager, bridge, deck_id=1):
        self.meta = meta_manager
        self.bridge = bridge
        self.deck_id = deck_id
        self.deck_info = DECKS[deck_id]
        self.players = ["You", "The Mouth", "The Eye", "The Skin", "The Heart", "The Throat"]
        self.lives = {p: 3 for p in self.players}
        self.dealer_idx = 0
        self.round_num = 1
        self.well = 0
        # AI holds higher cards more aggressively on harder decks
        deck_difficulty_modifier = (deck_id - 1) * 2 
        self.ai_thresholds = {
            "The Mouth": min(18, 12 + deck_difficulty_modifier), 
            "The Eye": min(16, 7 + deck_difficulty_modifier), 
            "The Skin": min(17, 9 + deck_difficulty_modifier), 
            "The Throat": min(15, 5 + deck_difficulty_modifier)
        }

    def get_active_players(self):
        return [p for p in self.players if self.lives[p] > 0]

    def get_next_active_player(self, current_player, active_list):
        idx = active_list.index(current_player)
        return active_list[(idx + 1) % len(active_list)]

    def play_round(self):
        active = self.get_active_players()
        dealer = active[self.dealer_idx % len(active)]
        is_sudden_death = len(active) == 2

        self.bridge.write(f"\n=== ROUND {self.round_num} ===\n")
        if is_sudden_death:
            self.bridge.write("SUDDEN DEATH: THE WELL IS OPENING\n")
        self.bridge.write(f"Current Dealer: {dealer}\n")
        self.bridge.write(f"The Well Contains: {self.well} Lives\n")
        self.bridge.write("Current Lives: " + ", ".join([f"{p}: {'*' * self.lives[p]}" for p in active]) + "\n")
        time.sleep(1.5)

        # Build dynamic deck based on unlocked tier
        deck = self.deck_info["build"]()
        random.shuffle(deck)

        hands = {p: deck.pop(0) for p in active}

        if "You" in active:
            self.bridge.write(f"\n[DEAL] You look at your card... It's the *{card_str(hands['You'])}*.\n")
        else:
            self.bridge.write(f"\n[DEAL] As an Unworthy, you watch the remaining players receive their cards.\n")
        time.sleep(1)

        self.bridge.write("\n--- THE BLIND MAN'S BET ---\n")
        peeks = {}
        cursed_players = set()

        for p in active:
            idx = active.index(p)
            left_neighbor = active[(idx + 1) % len(active)]
            right_neighbor = active[(idx - 1) % len(active)]
            random_target = random.choice([left_neighbor, right_neighbor])

            if p == "You":
                choice = self.bridge.read(f"Invoke a Blind Bet to peek at {random_target}'s card? (y/n): ").strip().lower()
                if choice == 'y':
                    guess = self.bridge.read(f"Predict if {random_target}'s card is [o]dd or [e]ven: ").strip().lower()
                    target_is_even = (hands[random_target] % 2 == 0)

                    if (guess == 'e' and target_is_even) or (guess == 'o' and not target_is_even):
                        peeks["You"] = (random_target, hands[random_target])
                        self.bridge.write(f"SUCCESS! Your intuition was correct. You see that {random_target} holds: {card_str(hands[random_target])}\n")
                        self.meta.stats["successful_bets"] += 1
                        self.meta.unlock_achievement("curse_survived")
                    else:
                        peeks["You"] = (random_target, hands[random_target])
                        cursed_players.add("You")
                        self.bridge.write(f"INCORRECT! The Well brands you with The Curse. You will take DOUBLE damage if you fail this round!\n")
                        self.meta.stats["failed_bets"] += 1
                else:
                    self.bridge.write("You refuse to gamble in the dark.\n")
                time.sleep(1)
            else:
                will_gamble = False
                if p == "The Eye": will_gamble = True
                elif p == "The Throat" and hands[p] < 7: will_gamble = True
                elif p == "The Mouth" and random.random() < 0.4: will_gamble = True
                elif p == "The Heart" and random.random() < 0.6: will_gamble = True

                if will_gamble:
                    ai_guess_even = random.choice([True, False])
                    target_is_even = (hands[random_target] % 2 == 0)

                    # On harder decks, AI gets supernatural intuition
                    if self.deck_id > 1 and random.random() < (self.deck_id * 0.15):
                        ai_guess_even = target_is_even

                    peeks[p] = (random_target, hands[random_target])
                    if ai_guess_even == target_is_even:
                        self.bridge.write(f"{p} gazes intensely at {random_target} and nods. Their sight was true.\n")
                    else:
                        cursed_players.add(p)
                        self.bridge.write(f"{p} tries to read {random_target} but winces. A thick smoke surrounds them! They are cursed.\n")
                    time.sleep(0.5)

        time.sleep(1)

        well_triggered = False
        well_holder = None
        for p in active:
            if hands[p] == 20:
                well_holder = p
                break

        if well_holder:
            if well_holder == "You":
                self.bridge.write("\nALERT: You hold XX (The Well)!\n")
                call = self.bridge.read("Type 'Well!' immediately to claim it (or press Enter to ignore): ").strip()
                if call.lower() == "well!":
                    self.bridge.write("\nYou shout 'WELL!' and halt all trading!\n")
                    well_triggered = True
                    if self.lives["You"] < 3:
                        if self.well > 0:
                            self.lives["You"] += 1
                            self.well -= 1
                            self.bridge.write("* You reclaimed 1 life from the Well!\n")
                        else:
                            self.bridge.write("* The Well is dry. No lives could be pulled back.\n")
                        self.meta.unlock_achievement("well_spring")
                else:
                    self.bridge.write("\nYou didn't declare it! You lose 1 life to the Well instead.\n")
                    self.meta.unlock_achievement("the_fool")
                    self.lives["You"] -= 1
                    self.well += 1
                    well_triggered = True
            else:
                self.bridge.write(f"\n{well_holder} reveals XX (The Well) and shouts 'WELL!' Halting all trades.\n")
                well_triggered = True
                if self.lives[well_holder] < 3:
                    if self.well > 0:
                        self.lives[well_holder] += 1
                        self.well -= 1
                        self.bridge.write(f"* {well_holder} reclaimed 1 life from the Well.\n")
                    else:
                        self.bridge.write(f"* The Well is dry. {well_holder} could not reclaim a life.\n")
                time.sleep(1.5)

        if not well_triggered:
            non_dealers = [p for p in active if p != dealer]
            random.shuffle(non_dealers)
            trade_order = non_dealers + [dealer]

            for p in trade_order:
                if p not in self.get_active_players(): continue
                target = self.get_next_active_player(p, active)

                if p == dealer:
                    if p == "You":
                        choice = self.bridge.read(f"\nYou are the Dealer. Draw a random card from the deck? (y/n): ").strip().lower()
                        if choice == 'y':
                            hands["You"] = deck.pop()
                            self.bridge.write(f"You put your card away. Your new card is: {card_str(hands['You'])}\n")
                            time.sleep(1)
                    else:
                        threshold = self.ai_thresholds.get(p, 9)
                        if p in cursed_players: threshold += 3
                        if hands[p] < threshold:
                            hands[p] = deck.pop()
                            self.bridge.write(f"\nThe Dealer ({p}) decided to swap their card with the deck.\n")
                            time.sleep(1)
                    continue

                if p == "You":
                    prompt = f"\nYour Turn (Holding {card_str(hands['You'])})."
                    if p in cursed_players: prompt += "\nYou are CURSED!"
                    choice = self.bridge.read(prompt + f" Target to your left is {target}. [s]kip or [t]rade?: ").strip().lower()
                    action = "trade" if choice == 't' else "skip"
                else:
                    if p in peeks and peeks[p][0] == target:
                        target_card = peeks[p][1]
                        action = "skip" if (target_card < hands[p] or target_card in [16, 17, 18, 19]) else "trade"
                    else:
                        threshold = self.ai_thresholds.get(p, 9)
                        if target in cursed_players and p in ["The Mouth", "The Eye"]:
                            action = "trade" if hands[p] < 14 else "skip"
                        else:
                            action = "trade" if hands[p] < threshold else "skip"
                        if p == "The Heart" and random.random() < 0.25:
                            action = "skip" if action == "trade" else "trade"

                if action == "trade":
                    self.bridge.write(f"\n{p} wants to trade cards with {target}...\n")
                    time.sleep(1)
                else:
                    self.bridge.write(f"\n{p} chooses to Skip.\n")
                    time.sleep(0.5)

                if action == "trade":
                    target_card = hands[target]
                    if target_card == 16:
                        self.bridge.write(f"{target} reveals XVI (Home)! The trade is BLOCKED.\n")
                    elif target_card == 17:
                        self.bridge.write(f"{target} reveals XVII (The Bride)! The trade is BLOCKED.\n")
                        other_players = [o for o in active if o != p and o != target]
                        if other_players:
                            chosen_other = random.choice(other_players)
                            hands[p], hands[chosen_other] = hands[chosen_other], hands[p]
                            self.bridge.write(f"The Bride's curse forces {p} to trade with {chosen_other} instead!\n")
                            if p == "You": self.bridge.write(f"Your new card is: {card_str(hands['You'])}\n")
                            elif chosen_other == "You": self.bridge.write(f"Your card was swept up in the redirection! Your new card is: {card_str(hands['You'])}\n")
                        else:
                            self.bridge.write("No other path available. The trade shatters completely.\n")
                    elif target_card == 18:
                        self.bridge.write(f"{target} reveals XVIII (Fire)! The trade is BLOCKED.\n")
                        next_after_target = self.get_next_active_player(target, active)
                        if next_after_target != p:
                            hands[p], hands[next_after_target] = hands[next_after_target], hands[p]
                            self.bridge.write(f"The Fire rages! {p} is forced to trade with {next_after_target} (the player after {target})!\n")
                            if p == "You": self.bridge.write(f"Your new card is: {card_str(hands['You'])}\n")
                            elif next_after_target == "You": self.bridge.write(f"Your card caught fire and swapped! Your new card is: {card_str(hands['You'])}\n")
                        else:
                            self.bridge.write("The fire loops back onto yourself and fizzles out. No trade occurs.\n")
                    elif target_card == 19:
                        self.bridge.write(f"{target} reveals XIX (The Beast)! The trade is BLOCKED and {p} loses 1 life to the Well!\n")
                        self.lives[p] -= 1
                        self.well += 1
                        if p == "You":
                            self.meta.stats["beast_encounters"] += 1
                            self.meta.unlock_achievement("beast_bitten")
                    else:
                        hands[p], hands[target] = hands[target], hands[p]
                        if p == "You": self.bridge.write(f"Trade complete! Your new card is: {card_str(hands['You'])}\n")
                        elif target == "You": self.bridge.write(f"Your card was forcefully taken! Your new card is: {card_str(hands['You'])}\n")
                        else: self.bridge.write(f"Cards were swapped between {p} and {target}.\n")
                    time.sleep(1.5)

        self.bridge.write(f"\n--- THE BIG REVEAL ---\n")
        time.sleep(1)

        self.bridge.write("Final Hands:\n")
        for p in active:
            status = " [CURSED]" if p in cursed_players else ""
            self.bridge.write(f" - {p}: {card_str(hands[p])}{status}\n")
            time.sleep(0.5)

        immune_players = set()
        fool_protection = False

        card_counts = {}
        for p in active:
            val = hands[p]
            if 1 <= val <= 5:
                card_counts[val] = card_counts.get(val, []) + [p]

        for val, players_with_card in card_counts.items():
            if len(players_with_card) >= 2:
                if val == 1:
                    self.bridge.write(f"\n[TWIN FOOLS] Multiple players uncover I (The Fool)!\n")
                    self.bridge.write("The Depths are appeased: NO ONE loses lives this turn.\n")
                    fool_protection = True
                    for p in players_with_card:
                        if self.lives[p] < 3:
                            if self.well > 0:
                                self.lives[p] += 1
                                self.well -= 1
                                self.bridge.write(f"* {p} safely gains a life from the Well pool!\n")
                            else:
                                self.bridge.write(f"* The Well pool is dry. {p} cannot extract life.\n")
                else:
                    self.bridge.write(f"\n[TWIN TRIGGER] Multiple players hold {card_str(val)} and are immune to execution!\n")
                    for p in players_with_card: immune_players.add(p)

        if not fool_protection:
            vulnerable_players = [p for p in active if p not in immune_players and self.lives[p] > 0]
            if vulnerable_players:
                min_val = min(hands[p] for p in vulnerable_players)
                losers = [p for p in vulnerable_players if hands[p] == min_val]

                for l in losers:
                    damage = 2 if l in cursed_players else 1
                    self.lives[l] -= damage
                    self.well += damage
                    if damage == 2:
                        self.bridge.write(f"\n[CURSE CARNAGE] {l} held lowest card ({card_str(min_val)}) while CURSED. Loses 2 lives!\n")
                        self.meta.unlock_achievement("double_slay")
                    else:
                        self.bridge.write(f"\n[EXECUTION] {l} held lowest card ({card_str(min_val)}). Loses 1 life!\n")
            else:
                self.bridge.write("\nEveryone is shielded! No souls harvested.\n")

        for p in active:
            if self.lives[p] <= 0:
                verb = "have" if p == "You" else "has"
                self.bridge.write(f"\n{p} {verb} run out of lives and become *UNWORTHY*!\n")
                if p == "You": self.meta.unlock_achievement("unworthy_end")

        self.dealer_idx += 1
        self.round_num += 1
        time.sleep(2)

    def start(self):
        self.bridge.clear()

        self.bridge.write("====================================\n")
        self.bridge.write(f" DESCENDING INTO: {self.deck_info['name'].upper()} \n")
        self.bridge.write("====================================\n")

        while len(self.get_active_players()) > 1:
            self.play_round()

        winner = self.get_active_players()[0]
        total_won_lives = self.lives[winner] + self.well

        self.bridge.write(f"\n====================================\n")
        self.meta.stats["games_played"] += 1
        self.meta.unlock_achievement("first_plunge")
        if self.meta.stats["games_played"] >= 5: self.meta.unlock_achievement("serial_diver")
        
        self.bridge.write(f"GAME OVER\n")

        ending_lives = self.lives.get("You", 0)
        match_net = (total_won_lives - 3) if winner == "You" else (ending_lives - 3)
        self.meta.stats["net_life_force"] += match_net

        if winner == "You":
            self.meta.stats["games_won"] += 1
            self.meta.unlock_achievement("sunken_one")
            if total_won_lives > self.meta.stats["highest_score"]:
                self.meta.stats["highest_score"] = total_won_lives
            
            # Check and unlock the next sequential deck only if winning on the current one
            next_deck = self.deck_id + 1
            unlocked_list = self.meta.stats.setdefault("unlocked_decks", [1])
            if next_deck in DECKS and next_deck not in unlocked_list:
                unlocked_list.append(next_deck)
                self.bridge.write(f"\n>>> DEPTH CONQUERED! NEW DECK UNLOCKED: {DECKS[next_deck]['name']} <<<\n")
                self.bridge.write(f"    ({DECKS[next_deck]['desc']})\n\n")
                time.sleep(2.5)

        if total_won_lives >= 18:
            self.bridge.write(f"THE AWAKENING\n")
            self.bridge.write(f"{winner} has claimed all {total_won_lives} lives.\n")
            if winner == "You": self.meta.unlock_achievement("awakened")
        else:
            self.bridge.write(f"The final survivor and *The Sunken One* is: {winner}!\n")
            self.bridge.write(f"Possessing {total_won_lives} total lives.\n")

        self.bridge.write(f"====================================\n\n")
        self.meta.save_stats()
        self.bridge.read("Press Enter to return to the menu...")


def run_game_loop(bridge):
    meta = MetaManager(bridge)
    while True:
        bridge.clear()
        bridge.write("="*36 + "\n")
        bridge.write("             P O Z Z O              \n")
        bridge.write("="*36 + "\n")
        bridge.write(" 1] Play\n")
        bridge.write(" 2] Stats & Achievements\n")
        bridge.write(" 3] Rules\n")
        bridge.write(" 4] Exit\n")
        bridge.write("="*36 + "\n")

        choice = bridge.read("Select an option: ").strip()

        if choice == "1":
            # Handle Deck Selection dynamically based on sequential progression
            unlocked_list = meta.stats.get("unlocked_decks", [1])
            available_decks = {k: v for k, v in DECKS.items() if k in unlocked_list}
            
            selected_deck = 1
            if len(available_decks) > 1:
                bridge.clear()
                bridge.write("--- SELECT YOUR DEPTH ---\n")
                for k, v in available_decks.items():
                    bridge.write(f" [{k}] {v['name']} \n")
                    bridge.write(f"     > {v['desc']}\n")
                
                while True:
                    d_choice = bridge.read("\nSelect depth by number: ").strip()
                    if d_choice.isdigit() and int(d_choice) in available_decks:
                        selected_deck = int(d_choice)
                        break
                    bridge.write("Invalid selection. The depths reject you.\n")
            else:
                bridge.write(f"\nDescending into {DECKS[1]['name']}...\n")
                time.sleep(1)

            game = PozzoGame(meta, bridge, selected_deck)
            game.start()

        elif choice == "2":
            bridge.clear()
            net = meta.stats['net_life_force']
            net_str = f"+{net}" if net > 0 else f"{net}"
            bridge.write("--- STATISTICAL MEMORY ---\n")
            bridge.write(f" Journeys Undertaken: {meta.stats['games_played']}\n")
            bridge.write(f" Depths Conquered:    {meta.stats['games_won']}\n")
            bridge.write(f" Highest Life Force:  {meta.stats['highest_score']}\n")
            bridge.write(f" Lifetime Net Force:  {net_str} Lives\n")
            bridge.write(f" Prophecies Fulfilled: {meta.stats['successful_bets']}\n")
            bridge.write(f" False Visions:       {meta.stats['failed_bets']}\n\n")

            bridge.write("--- DECK UNLOCKS ---\n")
            unlocked_list = meta.stats.get("unlocked_decks", [1])
            for k, v in DECKS.items():
                if k in unlocked_list:
                    bridge.write(f" [UNLOCKED] {v['name']}\n")
                else:
                    prev_deck = k - 1
                    if prev_deck in unlocked_list:
                        bridge.write(f" [ LOCKED ] {v['name']} (Conquer {DECKS[prev_deck]['name']} to unlock)\n")
                    else:
                        bridge.write(f" [ LOCKED ] {v['name']} (Conquer previous depths first)\n")
            bridge.write("\n")

            bridge.write("--- INSCRIPTIONS ---\n")
            unlocked = meta.stats["unlocked_achievements"]
            for a_id, data in ACHIEVEMENTS.items():
                status = "[UNLOCKED]" if a_id in unlocked else "[ LOCKED ]"
                bridge.write(f" {status} {data['name']} - {data['desc']}\n")
            bridge.read("\nPress Enter to return to menu...")
            
        elif choice == "3":
            bridge.clear()
            bridge.write("==========================================================\n")
            bridge.write("                        LAWS OF POZZO                       \n")
            bridge.write("==========================================================\n")
            bridge.write(" Pozzo is a tactical card game where players must survive  \n")
            bridge.write(" by trading cards to avoid holding the lowest rank.       \n\n")
            bridge.write("--- CORE MECHANICS ---\n")
            bridge.write(" * Ranks range from 1 (Lowest) to 20 (Highest).\n")
            bridge.write(" * At the end of a round, the lowest card loses a life.\n")
            bridge.write(" * The last player remaining keeps their lives + all lives\n")
            bridge.write("   accumulated inside the Well, winning the match.\n\n")
            bridge.write("--- TWIN IMMUNITY (RANKS I TO V) ---\n")
            bridge.write(" If TWO players reveal identical lower-tier cards:\n")
            bridge.write(" * I (The Fool)    : Shuts down execution entirely. NO ONE\n")
            bridge.write("                      loses life. Both fools recover +1 life\n")
            bridge.write("                      from the Well if it contains any.\n")
            bridge.write(" * II to V         : Those matching players are completely\n")
            bridge.write("   (Fly/Spit/        immune to losing a life, even if their\n")
            bridge.write("   Winter/Hunger)    card is the lowest rank at the table.\n\n")
            bridge.write("--- MAJOR ARCANA (DEFENSIVE RANKS) ---\n")
            bridge.write(" Triggers when a player on your right attempts to trade:\n")
            bridge.write(" * XVI (Home)      : Blocks the trade completely.\n")
            bridge.write(" * XVII (The Bride): Blocks trade. Initiator is instantly\n")
            bridge.write("                      forced to trade with any other player.\n")
            bridge.write(" * XVIII (Fire)    : Blocks trade. Initiator is forced to\n")
            bridge.write("                      trade with the player after the holder.\n")
            bridge.write(" * XIX (The Beast) : Blocks trade. Initiator instantly\n")
            bridge.write("                      loses 1 life directly to the Well.\n")
            bridge.write(" * XX (The Well)   : Revealed BEFORE trading begins. Halts\n")
            bridge.write("                      all trading. Reclaim 1 life from the\n")
            bridge.write("                      Well by shouting 'Well!', or lose 1\n")
            bridge.write("                      life for hesitation.\n")
            bridge.write("==========================================================\n")
            bridge.read("\nPress Enter to return to menu...")
        elif choice == "4":
            bridge.clear()
            bridge.write("\nThank you for playing Pozzo!\n")
            time.sleep(1)
            os._exit(0)

def find_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 0))
    port = s.getsockname()[1]
    s.close()
    return port

def run_local_asset_server(port):
    handler = http.server.SimpleHTTPRequestHandler
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", port), handler) as httpd:
        httpd.serve_forever()

def on_loaded():
    game_thread = threading.Thread(target=run_game_loop, args=(bridge,), daemon=True)
    game_thread.start()


if __name__ == "__main__":
    bridge = WebBridge()

    server_port = find_free_port()
    server_thread = threading.Thread(target=run_local_asset_server, args=(server_port,), daemon=True)
    server_thread.start()

    window = webview.create_window(
        title="POZZO",
        url=f"http://localhost:{server_port}/index.html",
        js_api=bridge,
        width=1250,
        height=875,
        resizable=True
    )
    bridge.set_window(window)

    webview.start(on_loaded)
