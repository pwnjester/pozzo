import random
import time
import json
import os

CARD_NAMES = {
    1: "I (The Fool)", 2: "II (The Fly)", 3: "III (Spit)", 4: "IV (Winter)", 5: "V (Hunger)",
    16: "XVI (Home)", 17: "XVII (The Bride)", 18: "XVIII (Fire)", 19: "XIX (The Beast)", 20: "XX (The Well)"
}

ACHIEVEMENTS = {
    "first_plunge": {"name": "The First Plunge", "desc": "Play your first match of Pozzo."},
    "sunken_one": {"name": "The Sunken One", "desc": "Survive the depths and win a game."},
    "awakened": {"name": "The Awakening", "desc": "Win a game with 18 or more total lives claimed."},
    "curse_survived": {"name": "Defying the Well", "desc": "Successfully guess an Odd/Even Blind Bet."},
    "beast_bitten": {"name": "Maul Mark", "desc": "Attempt to trade with the holder of XIX (The Beast)."},
    "well_spring": {"name": "Thirst Quenched", "desc": "Successfully declare 'Well!' and gain a life."},
    "double_slay": {"name": "Cursed End", "desc": "Die or lose someone due to a Cursed Execution (double damage)."},
    "unworthy_end": {"name": "Flesh to Dust", "desc": "Run out of lives and become Unworthy."},
    "serial_diver": {"name": "Obsession", "desc": "Play a total of 10 matches."}
}

def card_str(val):
    return CARD_NAMES.get(val, f"Standard {val}")

def clear_screen():
    """Clears the terminal screen across Windows, Mac, and Linux platforms."""
    os.system('cls' if os.name == 'nt' else 'clear')


class MetaManager:
    """Handles persistent stats, saving/loading, and achievements via JSON."""
    def __init__(self, filename="pozzo_stats.json"):
        self.filename = filename
        self.stats = {
            "games_played": 0,
            "games_won": 0,
            "highest_score": 0,
            "net_life_force": 0,
            "successful_bets": 0,
            "failed_bets": 0,
            "beast_encounters": 0,
            "unlocked_achievements": []
        }
        self.load_stats()

    def load_stats(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, "r") as f:
                    loaded = json.load(f)
                    self.stats.update(loaded)
            except Exception:
                print("Corrupted save file. Starting fresh.")

    def save_stats(self):
        try:
            with open(self.filename, "w") as f:
                json.dump(self.stats, f, indent=4)
        except Exception as e:
            print(f"Failed to access stats: {e}")

    def unlock_achievement(self, ach_id):
        if ach_id in ACHIEVEMENTS and ach_id not in self.stats["unlocked_achievements"]:
            self.stats["unlocked_achievements"].append(ach_id)
            print(f"\n>>> ACHIEVEMENT UNLOCKED: {ACHIEVEMENTS[ach_id]['name']} <<<")
            print(f"    ({ACHIEVEMENTS[ach_id]['desc']})\n")
            self.save_stats()


class PozzoGame:
    def __init__(self, meta_manager):
        self.meta = meta_manager
        self.players = ["You", "The Mouth", "The Eye", "The Skin", "The Heart", "The Throat"]
        self.lives = {p: 3 for p in self.players}
        self.dealer_idx = 0
        self.round_num = 1
        self.well = 0  # The Sunken Pot / The Well pool

        # AI Personality thresholds
        self.ai_thresholds = {
            "The Mouth": 12,
            "The Eye": 7,
            "The Skin": 9,
            "The Throat": 5
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

        print(f"\n=== ROUND {self.round_num} ===")
        if is_sudden_death:
            print("SUDDEN DEATH DETECTED: THE WELL IS OPENING")
        print(f"Current Dealer: {dealer}")
        print(f"The Well Contains: {self.well} Lives")
        print("Current Lives: " + ", ".join([f"{p}: {'*' * self.lives[p]}" for p in active]))
        time.sleep(1.5)

        # Prepare and deal deck
        deck = list(range(1, 21)) * 2
        random.shuffle(deck)

        hands = {}
        for p in active:
            hands[p] = deck.pop(0)

        if "You" in active:
            print(f"\n[DEAL] You look at your card... It's the *{card_str(hands['You'])}*.")
        else:
            print(f"\n[DEAL] As an Unworthy, you watch the remaining players receive their cards.")
        time.sleep(1)

        print("\n--- THE BLIND MAN'S BET ---")
        peeks = {}
        cursed_players = set()

        for p in active:
            idx = active.index(p)
            left_neighbor = active[(idx + 1) % len(active)]
            right_neighbor = active[(idx - 1) % len(active)]
            random_target = random.choice([left_neighbor, right_neighbor])

            if p == "You":
                choice = input(f"Invoke a Blind Bet to peek at {random_target}'s card? (y/n): ").strip().lower()
                if choice == 'y':
                    guess = input(f"Predict if {random_target}'s card is [o]dd or [e]ven: ").strip().lower()
                    target_is_even = (hands[random_target] % 2 == 0)

                    if (guess == 'e' and target_is_even) or (guess == 'o' and not target_is_even):
                        peeks["You"] = (random_target, hands[random_target])
                        print(f"SUCCESS! Your intuition was correct. You see that {random_target} holds: {card_str(hands[random_target])}")
                        self.meta.stats["successful_bets"] += 1
                        self.meta.unlock_achievement("curse_survived")
                    else:
                        peeks["You"] = (random_target, hands[random_target])
                        cursed_players.add("You")
                        print(f"INCORRECT! The Well brands you with The Curse. You will take DOUBLE damage if you fail this round!")
                        self.meta.stats["failed_bets"] += 1
                else:
                    print("You refuse to gamble with the dark.")
                time.sleep(1)
            else:
                will_gamble = False
                if p == "The Eye":
                    will_gamble = True
                elif p == "The Throat" and hands[p] < 7:
                    will_gamble = True
                elif p == "The Mouth" and random.random() < 0.4:
                    will_gamble = True
                elif p == "The Heart" and random.random() < 0.6:
                    will_gamble = True

                if will_gamble:
                    ai_guess_even = random.choice([True, False])
                    target_is_even = (hands[random_target] % 2 == 0)

                    peeks[p] = (random_target, hands[random_target])
                    if ai_guess_even == target_is_even:
                        print(f"{p} gazes intensely at {random_target} and nods. Their sight was true.")
                    else:
                        cursed_players.add(p)
                        print(f"{p} tries to read {random_target} but winces. A dark aura surrounds them! THEY ARE CURSED.")
                    time.sleep(0.5)

        time.sleep(1)

        # Check for Well (XX)
        well_triggered = False
        well_holder = None

        for p in active:
            if hands[p] == 20:
                well_holder = p
                break

        if well_holder:
            if well_holder == "You":
                print("\nALERT: You hold XX (The Well)!")
                call = input("Type 'Well!' immediately to claim it (or press Enter to ignore): ").strip()
                if call.lower() == "well!":
                    print("\nYou shout 'WELL!' and halt all trading!")
                    well_triggered = True
                    if self.lives["You"] < 3:
                        if self.well > 0:
                            self.lives["You"] += 1
                            self.well -= 1
                            print("* You reclaimed 1 life from the Well!")
                        else:
                            print("* The Well is dry. No lives could be pulled back.")
                        self.meta.unlock_achievement("well_spring")
                else:
                    print("\nYou didn't declare it in time! You lose 1 life to the Well instead.")
                    self.lives["You"] -= 1
                    self.well += 1
                    well_triggered = True
            else:
                print(f"\n{well_holder} reveals XX (The Well) and shouts 'WELL!' Halting all trades.")
                well_triggered = True
                if self.lives[well_holder] < 3:
                    if self.well > 0:
                        self.lives[well_holder] += 1
                        self.well -= 1
                        print(f"* {well_holder} reclaimed 1 life from the Well.")
                    else:
                        print(f"* The Well is dry. {well_holder} could not reclaim a life.")
                time.sleep(1.5)

        # Trading phase
        if not well_triggered:
            non_dealers = [p for p in active if p != dealer]
            random.shuffle(non_dealers)
            trade_order = non_dealers + [dealer]

            for p in trade_order:
                if p not in self.get_active_players():
                    continue

                target = self.get_next_active_player(p, active)

                if p == dealer:
                    if p == "You":
                        choice = input(f"\nYou are the Dealer. Draw a random card from the deck? (y/n): ").strip().lower()
                        if choice == 'y':
                            hands["You"] = deck.pop()
                            print(f"You put your card away! Your new card is: {card_str(hands['You'])}")
                            time.sleep(1)
                    else:
                        threshold = self.ai_thresholds.get(p, 9)
                        if p in cursed_players:
                            threshold += 3
                        if hands[p] < threshold:
                            hands[p] = deck.pop()
                            print(f"\nThe Dealer ({p}) decided to swap their card with the deck.")
                            time.sleep(1)
                    continue

                if p == "You":
                    prompt = f"\nYour Turn (Holding {card_str(hands['You'])})."
                    if p in cursed_players:
                        prompt += "\nYOU ARE CURSED!"
                    choice = input(prompt + f" Target to your left is {target}. [s]kip or [t]rade?: ").strip().lower()
                    action = "trade" if choice == 't' else "skip"
                else:
                    # AI updated behavior to account for the newly added defensive cards
                    if p in peeks and peeks[p][0] == target:
                        target_card = peeks[p][1]
                        if target_card < hands[p] or target_card in [16, 17, 18, 19]:
                            action = "skip"
                        else:
                            action = "trade"
                    else:
                        threshold = self.ai_thresholds.get(p, 9)
                        if target in cursed_players and p in ["The Mouth", "The Eye"]:
                            action = "trade" if hands[p] < 14 else "skip"
                        else:
                            action = "trade" if hands[p] < threshold else "skip"

                        if p == "The Heart" and random.random() < 0.25:
                            action = "skip" if action == "trade" else "trade"

                    if action == "trade":
                        print(f"\n{p} wants to trade cards with {target}...")
                        time.sleep(1)
                    else:
                        print(f"\n{p} chooses to Skip.")
                        time.sleep(0.5)

                if action == "trade":
                    target_card = hands[target]

                    if target_card == 16:
                        print(f"{target} reveals XVI (Home)! The trade is BLOCKED.")
                    elif target_card == 17:
                        print(f"{target} reveals XVII (The Bride)! The trade is BLOCKED.")
                        other_players = [o for o in active if o != p and o != target]
                        if other_players:
                            chosen_other = random.choice(other_players)
                            hands[p], hands[chosen_other] = hands[chosen_other], hands[p]
                            print(f"The Bride's curse forces {p} to trade with {chosen_other} instead!")
                            if p == "You":
                                print(f"Your new card is: {card_str(hands['You'])}")
                            elif chosen_other == "You":
                                print(f"Your card was swept up in the redirection! Your new card is: {card_str(hands['You'])}")
                        else:
                            print("No other dynamic path available. The trade shatters completely.")
                    elif target_card == 18:
                        print(f"{target} reveals XVIII (Fire)! The trade is BLOCKED.")
                        next_after_target = self.get_next_active_player(target, active)
                        if next_after_target != p:
                            hands[p], hands[next_after_target] = hands[next_after_target], hands[p]
                            print(f"The Fire rages! {p} is forced to trade with {next_after_target} (the player after {target})!")
                            if p == "You":
                                print(f"Your new card is: {card_str(hands['You'])}")
                            elif next_after_target == "You":
                                print(f"Your card caught fire and swapped! Your new card is: {card_str(hands['You'])}")
                        else:
                            print("The chaotic fire loops back onto yourself and fizzles out. No trade occurs.")
                    elif target_card == 19:
                        print(f"{target} reveals XIX (The Beast)! The trade is BLOCKED and {p} loses 1 life to the Well!")
                        self.lives[p] -= 1
                        self.well += 1
                        if p == "You":
                            self.meta.stats["beast_encounters"] += 1
                            self.meta.unlock_achievement("beast_bitten")
                    else:
                        hands[p], hands[target] = hands[target], hands[p]
                        if p == "You":
                            print(f"Trade complete! Your new card is: {card_str(hands['You'])}")
                        elif target == "You":
                            print(f"Your card was forcefully taken! Your new card is: {card_str(hands['You'])}")
                        else:
                            print(f"Cards were swapped between {p} and {target}.")
                    time.sleep(1.5)

        # End of round / Official Reveal Phase execution logic
        print(f"\n--- REVEAL PHASE ---")
        time.sleep(1)

        print("Final Hands:")
        for p in active:
            status = " [CURSED]" if p in cursed_players else ""
            print(f" - {p}: {card_str(hands[p])}{status}")
            time.sleep(0.5)

        immune_players = set()
        fool_protection = False

        card_counts = {}
        for p in active:
            val = hands[p]
            if 1 <= val <= 5:
                card_counts[val] = card_counts.get(val, []) + [p]

        # Process Twin Rules and The Fool exact triggers
        for val, players_with_card in card_counts.items():
            if len(players_with_card) == 2:
                if val == 1:
                    print(f"\n[TWIN FOOLS] Both {players_with_card[0]} and {players_with_card[1]} uncover I (The Fool)!")
                    print("The Depths are appeased: NO ONE loses lives this turn.")
                    fool_protection = True
                    for p in players_with_card:
                        if self.lives[p] < 3:
                            if self.well > 0:
                                self.lives[p] += 1
                                self.well -= 1
                                print(f"* {p} safely gains a life from the Well pool!")
                            else:
                                print(f"* The Well pool is dry. {p} cannot extract life.")
                else:
                    print(f"\n[TWIN TRIGGER] Both {players_with_card[0]} and {players_with_card[1]} hold {card_str(val)} and are immune to execution!")
                    for p in players_with_card:
                        immune_players.add(p)

        # Execution evaluation based entirely on the lowest card tier
        if not fool_protection:
            vulnerable_players = [p for p in active if p not in immune_players and self.lives[p] > 0]

            if vulnerable_players:
                min_val = min(hands[p] for p in vulnerable_players)
                losers = [p for p in vulnerable_players if hands[p] == min_val]

                print("")
                for l in losers:
                    damage = 2 if l in cursed_players else 1
                    self.lives[l] -= damage
                    self.well += damage

                    if damage == 2:
                        print(f"[CURSE CARNAGE] {l} held the lowest vulnerable card ({card_str(min_val)}) while CURSED and drains 2 lives into the Well!")
                        self.meta.unlock_achievement("double_slay")
                    else:
                        print(f"[EXECUTION] {l} held the lowest vulnerable card ({card_str(min_val)}) and drops 1 life into the Well!")
            else:
                print("\nEveryone is shielded! No souls are harvested this round.")

        # Handle players becoming Unworthy
        for p in active:
            if self.lives[p] <= 0:
                verb = "have" if p == "You" else "has"
                print(f"\n{p} {verb} run out of lives and has become *UNWORTHY*!")
                if p == "You":
                    self.meta.unlock_achievement("unworthy_end")

        self.dealer_idx += 1
        self.round_num += 1
        time.sleep(2)

    def start(self):
        clear_screen()

        print("====================================")
        print("        THE WELL ACCEPTS YOU        ")
        print("====================================")

        while len(self.get_active_players()) > 1:
            self.play_round()

        winner = self.get_active_players()[0]
        total_won_coins = self.lives[winner] + self.well

        print(f"\n====================================")
        self.meta.stats["games_played"] += 1
        self.meta.unlock_achievement("first_plunge")
        if self.meta.stats["games_played"] >= 10:
            self.meta.unlock_achievement("serial_diver")
        self.meta.save_stats()
        print(f"GAME OVER")

        ending_lives = self.lives.get("You", 0)
        match_net = 0

        if winner == "You":
            self.meta.stats["games_won"] += 1
            self.meta.unlock_achievement("sunken_one")
            if total_won_coins > self.meta.stats["highest_score"]:
                self.meta.stats["highest_score"] = total_won_coins

            match_net = total_won_coins - 3
        else:
            match_net = ending_lives - 3

        self.meta.stats["net_life_force"] += match_net

        if total_won_coins >= 18:
            print(f"THE AWAKENING")
            print(f"{winner} has claimed all {total_won_coins} lives from the table and the depths.")
            print(f"You do not sink. You transcend. The entities bow.")
            if winner == "You":
                self.meta.unlock_achievement("awakened")
        else:
            print(f"The final survivor and *The Sunken One* is: {winner}!")
            print(f"Possessing {total_won_coins} total lives.")

        print(f"====================================\n")
        self.meta.save_stats()
        input("Press Enter to ascend back to the menu...")


def main_menu():
    meta = MetaManager()

    while True:
        clear_screen()
        print("="*36)
        print("             P O Z Z O              ")
        print("="*36)
        print(" 1] Play")
        print(" 2] Stats & Achievements")
        print(" 3] Rules")
        print(" 4] Exit")
        print("="*36)

        choice = input("Select an option: ").strip()

        if choice == "1":
            game = PozzoGame(meta)
            game.start()
        elif choice == "2":
            clear_screen()
            net = meta.stats['net_life_force']
            net_str = f"+{net}" if net > 0 else f"{net}"

            print("--- STATISTICAL MEMORY ---")
            print(f" Journeys Undertaken: {meta.stats['games_played']}")
            print(f" Depths Conquered:    {meta.stats['games_won']}")
            print(f" Highest Life Force:  {meta.stats['highest_score']}")
            print(f" Lifetime Net Force:  {net_str} Lives")
            print(f" Prophecies Fulfilled: {meta.stats['successful_bets']}")
            print(f" False Visions:       {meta.stats['failed_bets']}")

            print("\n--- INSCRIPTIONS ---")
            unlocked = meta.stats["unlocked_achievements"]
            for a_id, data in ACHIEVEMENTS.items():
                status = "[UNLOCKED]" if a_id in unlocked else "[ LOCKED ]"
                print(f" {status} {data['name']} - {data['desc']}")
            input("\nPress Enter to return to menu...")
        elif choice == "3":
            clear_screen()
            print("==========================================================")
            print("                       LAWS OF POZZO                      ")
            print("==========================================================")
            print(" Pozzo is a tactical card game where players must survive  ")
            print(" by trading cards to avoid holding the lowest rank.       ")
            time.sleep(2)
            print("\n--- CORE MECHANICS ---")
            print(" * Ranks range from 1 (Lowest) to 20 (Highest).")
            print(" * At the end of a round, the lowest card loses a life.")
            print(" * The last player remaining keeps their lives + all lives")
            print("   accumulated inside the Well, winning the match.")
            time.sleep(2)
            print("\n--- TWIN IMMUNITY ---")
            print(" If TWO players reveal identical lower-tier cards:")
            print(" * I (The Fool)    : Shuts down execution entirely. NO ONE")
            print("                      loses life. Both fools recover +1 life")
            print("                      from the Well if it contains any.")
            print(" * II to V         : Those matching players are completely")
            print("   (Fly/Spit/       immune to losing a life, even if their")
            print("   Winter/Hunger)   card is the lowest rank at the table.")
            time.sleep(2)
            print("\n--- MAJOR ARCANA ---")
            print(" Triggers when a player on your right attempts to trade:")
            print(" * XVI (Home)      : Blocks the trade completely.")
            print(" * XVII (The Bride): Blocks trade. Initiator is instantly")
            print("                      forced to trade with any other player.")
            print(" * XVIII (Fire)    : Blocks trade. Initiator is forced to")
            print("                      trade with the player after the holder.")
            print(" * XIX (The Beast) : Blocks trade. Initiator instantly")
            print("                      loses 1 life directly to the Well.")
            print(" * XX (The Well)   : Revealed BEFORE trading begins. Halts")
            print("                      all trading. Reclaim 1 life from the")
            print("                      Well by shouting 'Well!', or lose 1")
            print("                      life for hesitation.")
            print("==========================================================")
            input("\nPress Enter to return to menu...")
        elif choice == "4":
            clear_screen()
            print("\nThank you for playing Pozzo!")
            break
        else:
            input("\nInvalid invocation. Choose wisely. (Press Enter to continue)")

if __name__ == "__main__":
    main_menu()
