import random
import time

CARD_NAMES = {
    1: "I (The Fool)", 2: "II (The Fly)", 3: "III (Spit)", 4: "IV (Winter)", 5: "V (Hunger)",
    16: "XVI (Home)", 17: "XVII (The Bride)", 18: "XVIII (Fire)", 19: "XIX (The Beast)", 20: "XX (The Well)"
}

def card_str(val):
    return CARD_NAMES.get(val, f"Standard {val}")

class PozzoGame:
    def __init__(self):
        self.players = ["You", "The Mouth", "The Eye", "The Skin", "The Heart", "The Throat"]
        self.coins = {p: 3 for p in self.players}
        self.dealer_idx = 0
        self.round_num = 1
        self.pit = 0  # The Sunken Pot

        # AI Personality (Cards below this value prompt a trade)
        self.ai_thresholds = {
            "The Mouth": 12,   # Deeply aggressive and paranoid
            "The Eye": 7,      # Calculating; comfortable holding lower cards
            "The Skin": 9,     # Baseline survivalist instinct
            "The Throat": 5    # Paralyzed by risk; rarely willing to blind-trade
        }

    def get_active_players(self):
        return [p for p in self.players if self.coins[p] > 0]

    def get_next_active_player(self, current_player, active_list):
        idx = active_list.index(current_player)
        return active_list[(idx + 1) % len(active_list)]

    def play_round(self):
        active = self.get_active_players()
        dealer = active[self.dealer_idx % len(active)]
        is_sudden_death = len(active) == 2

        print(f"\n=== ROUND {self.round_num} ===")
        if is_sudden_death:
            print("SUDDEN DEATH DETECTED: THE PIT IS OPENING")
        print(f"Current Dealer: {dealer}")
        print(f"The Pit Contains: {self.pit} Lives")
        print("Current Lives: " + ", ".join([f"{p}: {'*' * self.coins[p]}" for p in active]))
        time.sleep(2)

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
        time.sleep(1.5)

        print("\n--- THE BLIND MAN'S BET ---")
        peeks = {}        # Tracks who successfully peeked: {peeker: (target_name, target_card)}
        cursed_players = set() # Tracks who failed their wager and suffers double damage

        for p in active:
            # Look only at immediate neighbors (Left = index + 1, Right = index - 1)
            idx = active.index(p)
            left_neighbor = active[(idx + 1) % len(active)]
            right_neighbor = active[(idx - 1) % len(active)]

            # 50-50 chance to peek at either the left neighbor (your trade target) or right neighbor
            random_target = random.choice([left_neighbor, right_neighbor])

            if p == "You":
                choice = input(f"Invoke a Blind Bet to peek at {random_target}'s card? (y/n): ").strip().lower()
                if choice == 'y':
                    guess = input(f"Predict if {random_target}'s card is [o]dd or [e]ven: ").strip().lower()
                    target_is_even = (hands[random_target] % 2 == 0)

                    # Evaluate the gamble
                    if (guess == 'e' and target_is_even) or (guess == 'o' and not target_is_even):
                        peeks["You"] = (random_target, hands[random_target])
                        print(f"SUCCESS! Your intuition was correct. You see that {random_target} holds: {card_str(hands[random_target])}")
                    else:
                        peeks["You"] = (random_target, hands[random_target])
                        cursed_players.add("You")
                        print(f"INCORRECT! The Pit brands you with The Curse. You will take DOUBLE damage if you fail this round!")
                else:
                    print("You refuse to gamble with the dark.")
                time.sleep(1.5)
            else:
                will_gamble = False
                if p == "The Eye":
                    will_gamble = True # Confident analyst
                elif p == "The Throat" and hands[p] < 7:
                    will_gamble = True # Panic-driven risk
                elif p == "The Mouth" and random.random() < 0.4:
                    will_gamble = True # Impulsive
                elif p == "The Heart" and random.random() < 0.6:
                    will_gamble = True # Erratic

                if will_gamble:
                    # AI flips a coin for its prediction
                    ai_guess_even = random.choice([True, False])
                    target_is_even = (hands[random_target] % 2 == 0)

                    peeks[p] = (random_target, hands[random_target])
                    if ai_guess_even == target_is_even:
                        print(f"{p} gazes intensely at {random_target} and nods. Their sight was true.")
                    else:
                        cursed_players.add(p)
                        print(f"{p} tries to read {random_target} but winces. A dark aura surrounds them! THEY ARE CURSED.")
                    time.sleep(1)

        time.sleep(1)

        # Check for Well
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
                    if self.coins["You"] < 3:
                        self.coins["You"] += 1
                        print("* You gained 1 life from the Well!")
                else:
                    print("\nYou didn't declare it in time! You lose 1 life instead.")
                    self.coins["You"] -= 1
                    self.pit += 1
                    well_triggered = True
            else:
                print(f"\n{well_holder} reveals XX (The Well) and shouts 'WELL!'")
                well_triggered = True
                if self.coins[well_holder] < 3:
                    self.coins[well_holder] += 1
                    print(f"* {well_holder} gained 1 life from the Well.")
                time.sleep(2.5)

        # Trading phase (if no well triggered)
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
                            time.sleep(2)
                    else:
                        threshold = self.ai_thresholds.get(p, 9)
                        # Cursed AI dealers are desperate and swap more aggressively
                        if p in cursed_players:
                            threshold += 3
                        if hands[p] < threshold:
                            hands[p] = deck.pop()
                            print(f"\nThe Dealer ({p}) decided to swap their card with the deck.")
                            time.sleep(2)
                    continue

                if p == "You":
                    prompt = f"\nYour Turn (Holding {card_str(hands['You'])})."
                    if p in cursed_players:
                        prompt += "\nYOU ARE CURSED!"
                    choice = input(prompt + f" Target to your left is {target}. [s]kip or [t]rade?: ").strip().lower()
                    action = "trade" if choice == 't' else "skip"
                else:
                    # AI decision logic
                    if p in peeks and peeks[p][0] == target:
                        target_card = peeks[p][1]
                        if target_card < hands[p] or target_card in [16, 19]:
                            action = "skip"
                        else:
                            action = "trade"
                    else:
                        threshold = self.ai_thresholds.get(p, 9)
                        # Aggressive AI preys on cursed targets nearby
                        if target in cursed_players and p in ["The Mouth", "The Eye"]:
                            action = "trade" if hands[p] < 14 else "skip"
                        else:
                            action = "trade" if hands[p] < threshold else "skip"

                        if p == "The Heart" and random.random() < 0.25:
                            action = "skip" if action == "trade" else "trade"

                    if action == "trade":
                        print(f"\n{p} wants to trade cards with {target}...")
                        time.sleep(1.5)
                    else:
                        print(f"\n{p} chooses to Skip.")
                        time.sleep(1)

                if action == "trade":
                    target_card = hands[target]

                    if target_card == 16:
                        print(f"{target} reveals XVI (Home)! The trade is BLOCKED.")
                    elif target_card == 19:
                        print(f"{target} reveals XIX (The Beast)! The trade is BLOCKED and {p} loses 1 life!")
                        self.coins[p] -= 1
                        self.pit += 1
                    else:
                        hands[p], hands[target] = hands[target], hands[p]
                        if p == "You":
                            print(f"Trade complete! Your new card is: {card_str(hands['You'])}")
                        elif target == "You":
                            print(f"Your card was forcefully taken! Your new card is: {card_str(hands['You'])}")
                        else:
                            print(f"Cards were swapped between {p} and {target}.")
                    time.sleep(2)

        # End of round
        executioner = deck.pop(0)
        print(f"\n--- REVEAL PHASE ---")
        print(f"The Executioner card is: {card_str(executioner)}")
        time.sleep(1.5)

        print("\nFinal Hands:")
        for p in active:
            status = " [CURSED]" if p in cursed_players else ""
            print(f" - {p}: {card_str(hands[p])}{status}")
            time.sleep(1)

        immune_players = set()
        for p in active:
            if hands[p] == executioner:
                print(f"\n[SAFE] {p} matches the Executioner and is SAFE!")
                immune_players.add(p)

        card_counts = {}
        for p in active:
            val = hands[p]
            if 1 <= val <= 5:
                card_counts[val] = card_counts.get(val, []) + [p]

        for val, players_with_card in card_counts.items():
            if len(players_with_card) == 2:
                print(f"\n[TWIN TRIGGER] Both {players_with_card[0]} and {players_with_card[1]} hold {card_str(val)} and are immune!")
                for p in players_with_card:
                    immune_players.add(p)
                if val == 1:
                    for p in players_with_card:
                        if self.coins[p] < 3:
                            self.coins[p] += 1
                            print(f"* {p} gains a life from the Fool effect!")

        # Score lowest card
        vulnerable_players = [p for p in active if p not in immune_players and self.coins[p] > 0]

        if vulnerable_players:
            min_val = min(hands[p] for p in vulnerable_players)
            losers = [p for p in vulnerable_players if hands[p] == min_val]

            print("")
            for l in losers:
                damage = 2 if l in cursed_players else 1
                self.coins[l] -= damage
                self.pit += damage

                if damage == 2:
                    print(f"[CURSE CARNAGE] {l} held the lowest card ({card_str(min_val)}) while CURSED and loses 2 lives to the Pit!")
                else:
                    print(f"[EXECUTION] {l} held the lowest card ({card_str(min_val)}) and loses 1 life to the Pit!")
        else:
            print("\nEveryone is immune! No one loses a life this round.")

        # Handle players becoming Unworthy
        for p in active:
            if self.coins[p] <= 0:
                verb = "have" if p == "You" else "has"
                print(f"\n{p} {verb} run out of lives and has become *UNWORTHY*!")

        self.dealer_idx += 1
        self.round_num += 1
        time.sleep(2.5)

    def start(self):
        print("====================================")
        print("          WELCOME TO POZZO          ")
        print("====================================")

        while len(self.get_active_players()) > 1:
            self.play_round()

        winner = self.get_active_players()[0]
        total_won_coins = self.coins[winner] + self.pit

        print(f"\n====================================")
        print(f"GAME OVER")

        if total_won_coins >= 18:
            print(f"THE AWAKENING")
            print(f"{winner} has claimed all {total_won_coins} lives from the table and the depths.")
            print(f"You do not sink. You transcend. The entities bow.")
        else:
            print(f"The final survivor and *The Sunken One* is: {winner}!")
            print(f"Possessing {total_won_coins} total lives.")
        print(f"====================================\n")

if __name__ == "__main__":
    game = PozzoGame()
    game.start()
