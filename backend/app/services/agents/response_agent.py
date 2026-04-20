import json

from app.models.schemas import IntakeOutput, QualificationOutput, ResponseOutput
from app.services.agents.base import BaseAgent


class ResponseAgent(BaseAgent):
    name = "Response Agent"
    prompt_file = "response_prompt.txt"
    output_model = ResponseOutput

    def process(self, intake: IntakeOutput, qualification: QualificationOutput) -> ResponseOutput:
        payload = {
            "intake": json.loads(intake.model_dump_json()),
            "qualification": json.loads(qualification.model_dump_json()),
        }
        user_prompt = (
            "Draft the first response message. Adjust tone based on tier and urgency.\n\n"
            f"{json.dumps(payload, indent=2)}"
        )
        return self.run(user_prompt)
