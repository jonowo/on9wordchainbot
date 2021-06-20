from .classic import ClassicGame
from ...constants import GameSettings


class HardModeGame(ClassicGame):
    name = "hard mode game"
    command = "starthard"

    def __init__(self, group_id: int) -> None:
        super().__init__(group_id)
        # Hardest settings available
        self.time_limit = GameSettings.MIN_TURN_SECONDS
        self.min_letters_limit = GameSettings.MAX_WORD_LENGTH_LIMIT
