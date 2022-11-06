from settings import END_TURN_SIGNAL
from settings import TWENTY_SIDED_DICE
from settings import SUCCESSFUL_MOVE_SIGNAL
from settings import UNSUCCESSFUL_MOVE_SIGNAL
from settings import INVALID_ATTACK_SIGNAL
from settings import SUCCESSFUL_ATTACK_SIGNAL
from settings import MISSED_ATTACK_SIGNAL
from utils.dnd_utils import roll_dice
from utils.dnd_utils import calculate_distance

import numpy as np

import logging
logger = logging.getLogger("ACTION_HANDLER")


class Action:
    """
    Represents an action
    """


class Reaction:
    """
    Represents a reaction
    """
    pass


class AttackOfOpportunity:
    """
    Melee attack as target creature moves away
    """
    pass


# Added advantage, disadvantage possibilities for actions

class Attack(Action):
    """
    Represents a melee or ranged attack
    """

    def __init__(self, hit_bonus, damage_bonus, num_damage_dice, damage_dice, range, self_advantage_turns=0, self_disadvantage_turns=0, enemy_disadvantage_turns=0, enemy_advantage_turns=0, name="", attack_type='attack', spell_level = 0, auto_hit = False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hit_bonus = hit_bonus
        self.damage_bonus = damage_bonus
        self.num_damage_dice = num_damage_dice
        self.damage_dice = damage_dice
        self.range = range
        self.name = name
        self.self_advantage_turns = self_advantage_turns
        self.self_disadvantage_turns = self_disadvantage_turns
        self.enemy_advantage_turns = enemy_advantage_turns
        self.enemy_disadvantage_turns = enemy_disadvantage_turns
        self.attack_type = attack_type
        self.auto_hit = auto_hit
        self.spell_level = spell_level

    def use(self, source_creature, target_creature, **kwargs):
        """
        Uses an attack to hit a target creature
        """
        meta_data = None
        # Check for illegal attacks
        is_under_attacks_allowed = source_creature.attacks_used < source_creature.attacks_allowed
        distance = calculate_distance(
            source_creature.location, target_creature.location)
        is_in_range = distance <= self.range
        if not is_in_range:
            logger.info(("                                INVALID ATTACK - RANGE: "+str(meta_data)))
            return INVALID_ATTACK_SIGNAL, meta_data
        elif not is_under_attacks_allowed:
            logger.info(("                                INVALID ATTACK - ATTACKS_ALLOWED: "+str(meta_data)))
            return INVALID_ATTACK_SIGNAL, meta_data

        
        if self.attack_type == "spell":
            result = self.spell_slot_check(source_creature)

            if result == "INVALID":
                logger.info(("                                INVALID ATTACK - SPELL SLOT: "+str(meta_data)))
                return INVALID_ATTACK_SIGNAL, meta_data

        # Legal attack:
        hit_roll = self.roll_dice_to_hit(source_creature)
        source_creature.attacks_used += 1
        meta_data = {
            "type": type(self),
            "source_creature": source_creature,
            "target_creature": target_creature,
            "hit_roll": hit_roll,
            "damage": 0,
        }

        if hit_roll >= target_creature.armor_class or self.auto_hit:
            # damage = self.damage_dice * self.num_damage_dice / 2
            damage = self.calculate_damage(target_creature)
            target_creature.hit_points -= damage
            meta_data.update({"damage": damage})
            # adding adv, disadv for action
            self.apply_vantage(source_creature, target_creature)
            logger.info(("                                VALID ATTACK: "+str(meta_data)))
            return SUCCESSFUL_ATTACK_SIGNAL, meta_data
        else:
            logger.info(("                                MISSED ATTACK: "+str(meta_data)))
            return MISSED_ATTACK_SIGNAL, meta_data

    def roll_dice_to_hit(self, source_creature, **kwargs):

        if (source_creature.advantage_counter == 0 and source_creature.disadvantage_counter == 0):

            return roll_dice(TWENTY_SIDED_DICE) + self.hit_bonus

        elif (source_creature.advantage_counter > 0 and source_creature.disadvantage_counter > 0):
            source_creature.advantage_counter = source_creature.advantage_counter - 1
            source_creature.disadvantage_counter = source_creature.disadvantage_counter - 1

            return roll_dice(TWENTY_SIDED_DICE) + self.hit_bonus

        elif source_creature.advantage_counter > 0 and source_creature.disadvantage_counter == 0:
            source_creature.advantage_counter = source_creature.advantage_counter - 1

            return max([roll_dice(TWENTY_SIDED_DICE) + self.hit_bonus for _ in range(2)])

        elif source_creature.advantage_counter == 0 and source_creature.disadvantage_counter > 0:
            source_creature.disadvantage_counter = source_creature.disadvantage_counter - 1

            return min([roll_dice(TWENTY_SIDED_DICE) + self.hit_bonus for _ in range(2)])

    def apply_vantage(self, source_creature, target_creature, **kwargs):

        source_creature.advantage_counter = source_creature.advantage_counter + \
            self.self_advantage_turns
        source_creature.disadvantage_counter = source_creature.disadvantage_counter + \
            self.self_disadvantage_turns
        target_creature.advantage_counter = target_creature.advantage_counter + \
            self.enemy_advantage_turns
        target_creature.disadvantage_counter = target_creature.disadvantage_counter + \
            self.enemy_disadvantage_turns

    def calculate_damage(self, target_creature):

        damage = np.sum([roll_dice(self.damage_dice)
                         for _ in range(self.num_damage_dice)])

        # check if resistances
        if target_creature.resistance == 1:
            damage = damage/2

        return damage

    def spell_slot_check(self, source_creature):
        
        if self.spell_level == 1 and source_creature.level_1_spell_slots_counter > 0:
            source_creature.level_1_spell_slots_counter = source_creature.level_1_spell_slots_counter - 1
            return "VALID"

        elif self.spell_level == 2 and source_creature.level_2_spell_slots_counter > 0:
            source_creature.level_2_spell_slots_counter = source_creature.level_2_spell_slots_counter - 1
            return "VALID"

        elif self.spell_level == 0:
            return "VALID"

        else:
            return "INVALID"

class Move(Action):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.coord_index = None
        self.sign = None

    def use(self, source_creature, combat_handler, **kwargs):
        """
        Moves the character
        """
        distance = 5  # five feet
        has_movement = source_creature.movement_remaining >= distance
        meta_data = None

        if not has_movement:
            return UNSUCCESSFUL_MOVE_SIGNAL, meta_data

        # Determine where creature wants to me to
        target_location = source_creature.location.copy()
        target_location[self.coord_index] = source_creature.location[self.coord_index] + \
            distance * self.sign

        # Check if target location is allowable
        is_legal_env_target_location = combat_handler.environment.check_if_legal(
            target_location=target_location)
        is_legal_collision_target_location = combat_handler.check_legal_movement(
            source_location=source_creature.location, target_location=target_location)
        is_legal_target_location = is_legal_env_target_location and is_legal_collision_target_location

        # Move if allowed
        if is_legal_target_location:
            old_location = source_creature.location
            source_creature.location = target_location
            source_creature.movement_remaining -= distance
            meta_data = {"old_location": old_location,
                         "new_location": source_creature.location}
            logger.info(("                                VALID MOVE: "+str(meta_data)))
            return SUCCESSFUL_MOVE_SIGNAL, meta_data
        else:
            logger.info(("                                INVALID MOVE: "+str(meta_data)))
            return UNSUCCESSFUL_MOVE_SIGNAL, meta_data


class MoveLeft(Move):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.coord_index = 0
        self.sign = -1
        self.name = "move_left"


class MoveRight(Move):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.coord_index = 0
        self.sign = 1
        self.name = "move_right"


class MoveUp(Move):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.coord_index = 1
        self.sign = 1
        self.name = "move_up"


class MoveDown(Move):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.coord_index = 1
        self.sign = -1
        self.name = "move_down"


class EndTurn(Action):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "end_turn"

    def use(self, source_creature, **kwargs):
        meta_attributes = None
        return END_TURN_SIGNAL, meta_attributes

class DoNotMove(Move):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.coord_index = 0
        self.sign = 0
        self.name = "do_not_move"

# Todo: Move into DB
vampire_bite = Attack(hit_bonus=10, damage_bonus=10, num_damage_dice=2,
                      damage_dice=12, range=5, name="Vampire Bite")
sword_slash = Attack(hit_bonus=5, damage_bonus=3, num_damage_dice=1,
                     damage_dice=12, range=5, name="Sword Slash")
arrow_shot = Attack(hit_bonus=5, damage_bonus=3, num_damage_dice=1,
                    damage_dice=12, range=60, name="Arrow Shot")
cataclysm = Attack(hit_bonus=200, damage_bonus=20,
                   num_damage_dice=1, damage_dice=12, range=60, name="Cataclysm")


# Barbarian is always raging +2 to dmg
barbarian_axe_slash_reckless = Attack(hit_bonus=6, damage_bonus=5, num_damage_dice=1, damage_dice=12,
                             range=5, self_advantage_turns=1, self_disadvantage_turns=0, enemy_advantage_turns=1, enemy_disadvantage_turns=0, name="Greataxe slash reckless")

barbarian_axe_slash = Attack(hit_bonus=6, damage_bonus=5, num_damage_dice=1, damage_dice=12,
                             range=5, self_advantage_turns=0, self_disadvantage_turns=0, enemy_advantage_turns=0, enemy_disadvantage_turns=0, name="Greataxe slash")


#Wizard - School of evocation
#cantrips
fire_bolt_cantrip = Attack(hit_bonus=3, damage_bonus=0, num_damage_dice=1, damage_dice=10,
                             range=40, name="Fire Bolt", attack_type="spell", spell_level=0)

ray_of_frost_cantrip = Attack(hit_bonus=3, damage_bonus=0, num_damage_dice=1, damage_dice=8,
                             range=15, name="Ray of Frost", attack_type="spell", spell_level=0)

#Level 1
chromatic_orb_level_1 = Attack(hit_bonus=3, damage_bonus=0, num_damage_dice=3, damage_dice=8,
                             range=30, name="Chromatic Orb", attack_type="spell", spell_level=1)

magic_missile_level_1 = Attack(hit_bonus=3, damage_bonus=3, num_damage_dice=3, damage_dice=4,
                             range=40, name="Magic Missile", attack_type="spell", spell_level=1, auto_hit=True)


#Level 2
scorching_ray_level_2 = Attack(hit_bonus=3, damage_bonus=0, num_damage_dice=6, damage_dice=6,
                             range=40, name="Scorching Ray", attack_type="spell", spell_level=2)

aganazzars_scorcher_level_2 = Attack(hit_bonus=3, damage_bonus=0, num_damage_dice=3, damage_dice=8,
                             range=10, enemy_disadvantage_turns=1, name="Aganazzars Scorcher", attack_type="spell", spell_level=2)


#Ranger - Hunter's mark always on (only 1 enemy) - avg of 1d6 i.e +3 bonus, Hunter path
shortsword_slash = Attack(hit_bonus=5, damage_bonus=6, num_damage_dice=1, damage_dice=6,
                             range=5, name="Shortsword slash")

handcrossbow_shot = Attack(hit_bonus=5, damage_bonus=6, num_damage_dice=1, damage_dice=6,
                             range=30, name="Hand Crossbow shot")

#cure wounds - should ?


#Manticore - underpowered
bite = Attack(hit_bonus=5, damage_bonus=5, num_damage_dice=1, damage_dice=8,
                             range=5, name="Bite")

tail_spike = Attack(hit_bonus=5, damage_bonus=3, num_damage_dice=1, damage_dice=8,
                             range=30, name="Tail Spike", attack_type="spell", spell_level=1)