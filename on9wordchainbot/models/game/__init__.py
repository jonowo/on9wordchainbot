from on9wordchainbot.models.game.banned_letters import BannedLettersGame
from on9wordchainbot.models.game.chaos import ChaosGame
from on9wordchainbot.models.game.chosen_first_letter import ChosenFirstLetterGame
from on9wordchainbot.models.game.classic import ClassicGame
from on9wordchainbot.models.game.elimination import EliminationGame
from on9wordchainbot.models.game.hard_mode import HardModeGame
from on9wordchainbot.models.game.mixed_elimination import MixedEliminationGame
from on9wordchainbot.models.game.random_first_letter import RandomFirstLetterGame
from on9wordchainbot.models.game.required_letter import RequiredLetterGame

GAME_MODES = [
    ClassicGame,
    HardModeGame,
    ChaosGame,
    ChosenFirstLetterGame,
    RandomFirstLetterGame,
    BannedLettersGame,
    RequiredLetterGame,
    EliminationGame,
    MixedEliminationGame
]

__all__ = (
    "ClassicGame",
    "HardModeGame",
    "ChaosGame",
    "ChosenFirstLetterGame",
    "RandomFirstLetterGame",
    "BannedLettersGame",
    "RequiredLetterGame",
    "EliminationGame",
    "MixedEliminationGame",
    "GAME_MODES"
)
