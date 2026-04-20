import json

from app.models.schemas import IntakeOutput, LeadInput
from app.services.agents.base import BaseAgent


class IntakeAgent(BaseAgent):
    name = "Intake Agent"
    prompt_file = "intake_prompt.txt"
    output_model = IntakeOutput

    def process(self, lead: LeadInput) -> IntakeOutput:
        payload = {
            "raw_message": lead.message,
            "metadata": {
                "source": lead.source,
                "budget": lead.budget,
                "service_requested": lead.service_requested,
                "urgency": lead.urgency,
            },
        }
        user_prompt = (
            "Here is the inbound lead. Extract structured fields per the schema.\n\n"
            f"{json.dumps(payload, indent=2)}"
        )
        return self.run(user_prompt)
