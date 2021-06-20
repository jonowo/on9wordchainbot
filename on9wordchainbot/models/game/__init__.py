from .banned_letters import BannedLettersGame
from .chaos import ChaosGame
from .chosen_first_letter import ChosenFirstLetterGame
from .classic import ClassicGame
from .elimination import EliminationGame
from .hard_mode import HardModeGame
from .mixed_elimination import MixedEliminationGame
from .required_letter import RequiredLetterGame

GAME_MODES = [
    ClassicGame,
    HardModeGame,
    ChaosGame,
    ChosenFirstLetterGame,
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
    "BannedLettersGame",
    "RequiredLetterGame",
    "EliminationGame",
    "MixedEliminationGame",
    "GAME_MODES"
)
