import json

from app.models.schemas import (
    IntakeOutput,
    QualificationOutput,
    ResponseOutput,
    FollowUpOutput,
    ActionOutput,
)
from app.services.agents.base import BaseAgent


class ManagerAgent(BaseAgent):
    name = "Manager Agent"
    prompt_file = "manager_prompt.txt"

    def process(
        self,
        intake: IntakeOutput,
        qualification: QualificationOutput,
        response: ResponseOutput,
        follow_up: FollowUpOutput,
        action: ActionOutput,
    ) -> str:
        payload = {
            "intake": json.loads(intake.model_dump_json()),
            "qualification": json.loads(qualification.model_dump_json()),
            "response": json.loads(response.model_dump_json()),
            "follow_up": json.loads(follow_up.model_dump_json()),
            "action": json.loads(action.model_dump_json()),
        }
        user_prompt = (
            "Summarize the full multi-agent decision for the business owner.\n\n"
            f"{json.dumps(payload, indent=2)}"
        )
        return self.run_text(user_prompt)
