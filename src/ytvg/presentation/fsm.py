from aiogram.fsm.state import State, StatesGroup


class PipelineSG(StatesGroup):
    """FSM for approval gateways. The bot never advances a stage without an explicit click."""

    idle = State()
    collecting_prompt = State()
    processing = State()
    awaiting_script = State()
    awaiting_audio = State()
    awaiting_images = State()
