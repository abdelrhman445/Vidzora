from aiogram.fsm.state import State, StatesGroup


class VideoCreationStates(StatesGroup):
    waiting_for_mode_choice = State()
    waiting_for_prompt = State()          # AI-generated script path
    waiting_for_custom_script = State()   # bring-your-own-script path
    awaiting_script_approval = State()
    awaiting_audio_approval = State()
    awaiting_images_approval = State()
    rendering = State()
