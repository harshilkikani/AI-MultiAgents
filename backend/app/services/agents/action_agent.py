import json

from app.models.schemas import (
    IntakeOutput,
    QualificationOutput,
    ResponseOutput,
    FollowUpOutput,
    ActionOutput,
)
from app.services.agents.base import BaseAgent


class ActionAgent(BaseAgent):
    name = "Action Agent"
    prompt_file = "action_prompt.txt"
    output_model = ActionOutput

    def process(
        self,
        intake: IntakeOutput,
        qualification: QualificationOutput,
        response: ResponseOutput,
        follow_up: FollowUpOutput,
    ) -> ActionOutput:
        payload = {
            "intake": json.loads(intake.model_dump_json()),
            "qualification": json.loads(qualification.model_dump_json()),
            "response": json.loads(response.model_dump_json()),
            "follow_up": json.loads(follow_up.model_dump_json()),
        }
        user_prompt = (
            "Recommend the single best next action for the business.\n\n"
            f"{json.dumps(payload, indent=2)}"
        )
        return self.run(user_prompt)
