# Blockchain simulation for Share or Perish: https://github.com/monero-project/research-lab/issues/146
# (c) 2025 tevador
# MIT license

import random

HONEST_HR = 6
ATTACK_HR = 3

UNIQUE_SHARES = False
UNCLE_BLOCKS = True

W = 8
K = 3
STUBBORNNESS = 5
GAMMA = 0.5
SIM_ROUNDS = 10000

##########################################################################

BLOCK_DIFF = HONEST_HR * 120
SHARE_DIFF = BLOCK_DIFF / W

def get_random_hash_diff():
    # uniform random number [0,1] simulates a hash value divided by 2^256
    u = random.random()
    # difficulty = 2^256 / H = 1.0 / u
    return int(1.0 / u)

class Blockchain:
    def __init__(self, name, hr):
        self.name = name
        self.hr = hr
        self.reset()

    def reset(self):
        self.shares = set() if UNIQUE_SHARES else list()
        self.num_blocks = 0
        self.weight = 0

    def soft_reset(self):
        self.num_blocks = 0
        self.weight = 0

    def add_share(self, shr):
        if isinstance(self.shares, set):
            self.shares.add(shr)
        else:
            self.shares.append(shr)

    def adopt_shares(self, shares):
        self.shares.clear()
        for shr in shares:
            self.add_share(shr)

    def total_work(self):
        return self.weight + len(self.shares)

    def mine(self, output, other_bc):
        for j in range(self.hr):
            h = get_random_hash_diff()
            if h >= BLOCK_DIFF:
                # found block
                wt = 1 + len(self.shares)
                self.num_blocks += 1
                self.weight += wt
                self.shares.clear()
                #output += f"{self.name} found a block: {h}, wt: {wt} !!!\n"
                # the attacker can use honest blocks as uncles
                if UNCLE_BLOCKS and other_bc and self.num_blocks == 1 and other_bc.num_blocks == 0:
                    other_bc.add_share(-1)
                    #output += f"    uncle block added\n"
            elif h >= SHARE_DIFF:
                # found share
                shr = len(self.shares)
                #output += f"{self.name} found a share #{shr}: {h}\n"
                self.add_share(shr)
                # the attacker can use honest shares
                if other_bc and self.num_blocks == 0 and other_bc.num_blocks == 0:
                    other_bc.add_share(shr)
        return output

print(f"W={W}")
print(f"STUBBORNNESS={STUBBORNNESS}")
print(f"UNIQUE_SHARES={UNIQUE_SHARES}")
print(f"UNCLE_BLOCKS={UNCLE_BLOCKS}")

honest_bc = Blockchain("honest", HONEST_HR)
attack_bc = Blockchain("attacker", ATTACK_HR)

def print_stats(i, diff, note):
    msg = f"Round {i} {note} diff={diff}, attack_blocks={attack_bc.num_blocks}, attack_weight={attack_bc.weight}, honest_blocks={honest_bc.num_blocks}, honest_weight={honest_bc.weight}"
    print(msg)

total_seconds = 0
num_attacks = 0
reorg = False

for i in range(SIM_ROUNDS):
    if reorg:
        honest_bc.reset()
        attack_bc.soft_reset() # keep shares
    else:
        honest_bc.soft_reset() # keep shares
        attack_bc.reset()
        attack_bc.adopt_shares(honest_bc.shares)
    output = ""
    reorg = False
    while (honest_bc.total_work() - attack_bc.total_work()) <= STUBBORNNESS:
        output = honest_bc.mine(output, attack_bc)
        output = attack_bc.mine(output, None)
        total_seconds += 1
        if attack_bc.weight > honest_bc.weight and honest_bc.num_blocks >= 10:
            break
    diff = honest_bc.weight - attack_bc.weight
    if attack_bc.weight < W * K or honest_bc.num_blocks < 10:
        #print_stats(i, diff, "FAIL")
        continue
    if diff < 0 or (diff == 0 and random.random() > GAMMA):
        print_stats(i, diff, "SUCCESS")
        num_attacks += 1
        reorg = True
        #print(output)
        #exit()
        continue
    if diff < 3:
        print_stats(i, diff, "NEAR")

days_per_attack = total_seconds / num_attacks / 86400 if num_attacks > 0 else "???"

print()
print(f"Time: {total_seconds}, attacks: {num_attacks}, {days_per_attack} days/attack")
print()
print(f"W={W}")
print(f"STUBBORNNESS={STUBBORNNESS}")
print(f"UNIQUE_SHARES={UNIQUE_SHARES}")
print(f"UNCLE_BLOCKS={UNCLE_BLOCKS}")
