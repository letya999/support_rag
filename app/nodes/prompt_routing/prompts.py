from typing import Dict
import os

def _load_prompt(filename: str) -> str:
    path = os.path.join(os.path.dirname(__file__), filename)
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()

SYSTEM_INSTRUCTIONS: Dict[str, str] = {
    "INITIAL": _load_prompt("prompt_instruction_initial.txt"),
    "ANSWER_PROVIDED": _load_prompt("prompt_instruction_answer_provided.txt"),
    "AWAITING_CLARIFICATION": _load_prompt("prompt_instruction_awaiting_clarification.txt"),
    "RESOLVED": _load_prompt("prompt_instruction_resolved.txt"),
    "ESCALATION_NEEDED": _load_prompt("prompt_instruction_escalation_needed.txt"),
    "ESCALATION_REQUESTED": _load_prompt("prompt_instruction_escalation_requested.txt"),
    "DEFAULT": _load_prompt("prompt_instruction_default.txt")
}
