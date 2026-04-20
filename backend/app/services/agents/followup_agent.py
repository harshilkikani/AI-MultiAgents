import json

from app.models.schemas import (
    IntakeOutput,
    QualificationOutput,
    ResponseOutput,
    FollowUpOutput,
)
from app.services.agents.base import BaseAgent


class FollowUpAgent(BaseAgent):
    name = "Follow-Up Agent"
    prompt_file = "followup_prompt.txt"
    output_model = FollowUpOutput

    def process(
        self,
        intake: IntakeOutput,
        qualification: QualificationOutput,
        response: ResponseOutput,
    ) -> FollowUpOutput:
        payload = {
            "intake": json.loads(intake.model_dump_json()),
            "qualification": json.loads(qualification.model_dump_json()),
            "initial_response": json.loads(response.model_dump_json()),
        }
        user_prompt = (
            "Design the follow-up cadence if the lead does not reply.\n\n"
            f"{json.dumps(payload, indent=2)}"
        )
        return self.run(user_prompt)
